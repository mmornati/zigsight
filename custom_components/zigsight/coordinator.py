"""DataUpdateCoordinator for ZigSight.

Zigbee2MQTT mode
    Push based. The coordinator subscribes (through Home Assistant's MQTT
    integration) to ``<prefix>/#`` and dispatches every message by topic:

    - ``bridge/devices`` (retained) is the authoritative device list. It
      creates, updates (renames, re-interviews) and removes devices, keyed by
      IEEE address, and maintains the friendly_name -> IEEE map.
    - ``bridge/info`` / ``bridge/state`` / ``bridge/response/networkmap``
      feed network level information.
    - ``<friendly_name>`` state messages (names may contain ``/``) are merged
      into the device's last state; ``<friendly_name>/availability`` drives
      availability and reconnect counting; ``/set``, ``/get`` and anything
      else is ignored, as are groups and unknown topics.

    Entities are notified per device through a dispatcher signal; the global
    coordinator listeners are only called by the periodic refresh (which
    recomputes time dependent analytics).

ZHA mode
    Poll based: the periodic refresh collects devices through ZHACollector.
"""

from __future__ import annotations

import json
import logging
from collections import deque
from collections.abc import Callable, Iterable
from datetime import datetime
from typing import Any

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .analytics import DeviceAnalytics, as_datetime
from .const import (
    ANALYTICS_MIN_INTERVAL,
    DEFAULT_BATTERY_DRAIN_THRESHOLD,
    DEFAULT_MQTT_TOPIC_PREFIX,
    DEFAULT_RECONNECT_RATE_THRESHOLD,
    DEFAULT_RECONNECT_RATE_WINDOW_HOURS,
    DEVICE_SOURCE_ZHA,
    DEVICE_SOURCE_ZIGBEE2MQTT,
    DEVICE_TYPE_COORDINATOR,
    DEVICE_TYPE_END_DEVICE,
    DEVICE_TYPE_ROUTER,
    DOMAIN,
    EVENT_DEVICE_UPDATE,
    EVENT_MIN_INTERVAL,
    HISTORY_MAX_ENTRIES,
    HISTORY_MIN_INTERVAL,
    HISTORY_MIN_INTERVAL_ON_BATTERY_CHANGE,
    ISSUE_ZHA_DIAGNOSTICS_DISABLED,
    RECONNECT_EVENTS_MAX,
    SIGNAL_DEVICE_REMOVED,
    SIGNAL_DEVICE_UPDATE,
    SIGNAL_NEW_DEVICE,
    SILENT_DEVICE_TIMEOUT,
    UPDATE_INTERVAL,
)
from .z2m import (
    NetworkLink,
    TopicKind,
    Z2MBridgeInfo,
    Z2MDevice,
    classify_topic,
    extract_metrics,
    parse_availability,
    parse_bridge_devices,
    parse_bridge_info,
    parse_bridge_state,
    parse_json,
    parse_last_seen,
    parse_networkmap_response,
)
from .zha_collector import ZHACollector

_LOGGER = logging.getLogger(__name__)

# Per-device entity keys of the previous (friendly-name based) releases, used
# to migrate their unique ids. Kept here (not imported from the platforms) to
# avoid an import cycle.
LEGACY_ENTITY_KEYS: tuple[tuple[str, str], ...] = (
    ("sensor", "link_quality"),
    ("sensor", "battery"),
    ("sensor", "voltage"),
    ("sensor", "reconnect_rate"),
    ("sensor", "battery_trend"),
    ("sensor", "health_score"),
    ("binary_sensor", "battery_drain_warning"),
    ("binary_sensor", "connectivity_warning"),
)

# Entity keys created for every device / only for battery powered devices
# (the platforms build their entities from ZigSightCoordinator.entity_keys).
BASE_ENTITY_KEYS = frozenset(
    {"link_quality", "reconnect_rate", "health_score", "connectivity_warning"}
)
BATTERY_ENTITY_KEYS = frozenset({"battery", "battery_trend", "battery_drain_warning"})

# Maximum number of messages buffered for not-yet-known friendly names (e.g.
# retained availability delivered before the retained bridge/devices).
PENDING_MESSAGES_MAX = 256

_TRACKED_METRICS = ("link_quality", "battery", "voltage")

_TYPE_TO_TOPOLOGY = {
    DEVICE_TYPE_COORDINATOR: "coordinator",
    DEVICE_TYPE_ROUTER: "router",
    DEVICE_TYPE_END_DEVICE: "end_device",
}


def _legacy_z2m_ids(friendly_name: str) -> tuple[str, bool]:
    """Return the id the pre-IEEE releases used for a Z2M device.

    Those releases used the first topic segment after the prefix, so names
    containing ``/`` were truncated. The flag tells whether the legacy id is
    the full (exact) name.
    """
    first = friendly_name.split("/", 1)[0]
    return first, first == friendly_name


class ZigSightCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Track Zigbee devices and their diagnostics for one config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        mqtt_prefix: str = DEFAULT_MQTT_TOPIC_PREFIX,
        battery_drain_threshold: float = DEFAULT_BATTERY_DRAIN_THRESHOLD,
        reconnect_rate_threshold: float = DEFAULT_RECONNECT_RATE_THRESHOLD,
        reconnect_rate_window_hours: int = DEFAULT_RECONNECT_RATE_WINDOW_HOURS,
        enable_zha: bool = False,
        config_entry: ConfigEntry | None = None,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self._mqtt_prefix = (mqtt_prefix or DEFAULT_MQTT_TOPIC_PREFIX).rstrip("/")
        self._enable_zha = enable_zha
        self._signal_id = config_entry.entry_id if config_entry else DOMAIN

        # Device records keyed by IEEE address (see _new_record for the shape)
        self._devices: dict[str, dict[str, Any]] = {}
        self._z2m_devices: dict[str, Z2MDevice] = {}
        self._name_to_ieee: dict[str, str] = {}
        self._history: dict[str, deque[dict[str, Any]]] = {}
        self._reconnect_events: dict[str, deque[datetime]] = {}
        self._analytics_computed_at: dict[str, datetime] = {}
        self._last_event: dict[str, tuple[datetime, tuple[Any, ...]]] = {}
        self._pending: dict[tuple[str, str], tuple[Any, datetime]] = {}
        self._migrated: set[str] = set()
        self._registry_reconciled = False

        # Network level information (Zigbee2MQTT)
        self.bridge_state: str | None = None
        self.bridge_info: Z2MBridgeInfo | None = None
        self.coordinator_device: Z2MDevice | None = None
        self._network_links: list[NetworkLink] = []
        self._network_nodes: list[dict[str, Any]] = []
        self.network_map_updated: datetime | None = None

        self._unsub_mqtt: list[Callable[[], None]] = []
        self._unsub_keepalive: Callable[[], None] | None = None

        self._analytics = DeviceAnalytics(
            reconnect_rate_window_hours=reconnect_rate_window_hours,
            battery_drain_threshold=battery_drain_threshold,
        )
        self._reconnect_rate_threshold = reconnect_rate_threshold
        self._zha_collector: ZHACollector | None = None
        if enable_zha:
            self._zha_collector = ZHACollector(hass)

    # ------------------------------------------------------------------
    # Identifiers / signals
    # ------------------------------------------------------------------
    @property
    def mqtt_prefix(self) -> str:
        """Return the Zigbee2MQTT base topic."""
        return self._mqtt_prefix

    @property
    def source(self) -> str:
        """Return the device source handled by this coordinator."""
        return DEVICE_SOURCE_ZHA if self._enable_zha else DEVICE_SOURCE_ZIGBEE2MQTT

    @property
    def bridge_identifier(self) -> tuple[str, str]:
        """Device registry identifier of the ZigSight bridge device."""
        return (DOMAIN, f"{self._signal_id}_bridge")

    @property
    def coordinator_ieee(self) -> str | None:
        """Return the IEEE address of the Zigbee coordinator, if known."""
        if self.coordinator_device is not None:
            return self.coordinator_device.ieee_address
        if self.bridge_info is not None:
            return self.bridge_info.coordinator_ieee
        return None

    @property
    def signal_new_device(self) -> str:
        """Dispatcher signal sent (with the IEEE) when entities may be added."""
        return SIGNAL_NEW_DEVICE.format(entry_id=self._signal_id)

    @property
    def signal_device_removed(self) -> str:
        """Dispatcher signal sent (with the IEEE) when a device is removed."""
        return SIGNAL_DEVICE_REMOVED.format(entry_id=self._signal_id)

    def device_signal(self, ieee: str) -> str:
        """Dispatcher signal sent when one device's data changed."""
        return SIGNAL_DEVICE_UPDATE.format(entry_id=self._signal_id, ieee=ieee)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def async_start(self) -> None:
        """Start the coordinator (subscribe to Zigbee2MQTT topics).

        In Zigbee2MQTT mode the caller must have checked that Home Assistant's
        MQTT integration is available (see async_setup_entry).
        """
        # Keep the periodic refresh running even before any entity exists:
        # it drives ZHA polling and time based analytics.
        if self._unsub_keepalive is None:
            self._unsub_keepalive = self.async_add_listener(lambda: None)

        if self._enable_zha:
            self.logger.debug("Starting ZigSight coordinator in ZHA mode")
            if self._zha_collector is not None:
                # Live (push) updates for devices/entities already known;
                # the periodic refresh (_collect_zha_devices) additionally
                # re-discovers devices ZHA adds later.
                self._zha_collector.async_setup(self._handle_zha_push_update)
                await self._collect_zha_devices()
            return

        self.logger.debug(
            "Starting ZigSight coordinator with MQTT prefix: %s", self._mqtt_prefix
        )
        # One wildcard subscription, dispatched by parsed topic: subscribing
        # to the individual bridge topics as well would deliver those
        # messages twice.
        unsub = await mqtt.async_subscribe(
            self.hass, f"{self._mqtt_prefix}/#", self._async_handle_message, 0
        )
        self._unsub_mqtt.append(unsub)

    async def async_shutdown(self) -> None:
        """Unsubscribe from MQTT/ZHA and stop the periodic refresh."""
        for unsub in self._unsub_mqtt:
            unsub()
        self._unsub_mqtt.clear()
        if self._zha_collector is not None:
            self._zha_collector.async_stop()
        if self._unsub_keepalive is not None:
            self._unsub_keepalive()
            self._unsub_keepalive = None
        await super().async_shutdown()

    @callback
    def async_setup_bridge_device(self) -> None:
        """Create the ZigSight bridge device all devices are linked through."""
        if self.config_entry is None:
            return
        dev_reg = dr.async_get(self.hass)
        if self._enable_zha:
            name, manufacturer, model = "ZHA network", "ZigSight", "ZHA"
        else:
            name, manufacturer, model = (
                "Zigbee2MQTT bridge",
                "Zigbee2MQTT",
                "Zigbee2MQTT bridge",
            )
        dev_reg.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            identifiers={self.bridge_identifier},
            name=name,
            manufacturer=manufacturer,
            model=model,
            entry_type=DeviceEntryType.SERVICE,
        )

    # ------------------------------------------------------------------
    # MQTT message handling (Zigbee2MQTT)
    # ------------------------------------------------------------------
    @callback
    def _async_handle_message(self, msg: mqtt.ReceiveMessage) -> None:
        """Dispatch one message received under the Zigbee2MQTT base topic."""
        received_at = dt_util.utcnow()
        parsed = classify_topic(msg.topic, self._mqtt_prefix, self._name_to_ieee)
        kind = parsed.kind
        try:
            if kind is TopicKind.BRIDGE_DEVICES:
                self._handle_bridge_devices(msg.payload, received_at)
            elif kind is TopicKind.BRIDGE_INFO:
                self._handle_bridge_info(msg.payload)
            elif kind is TopicKind.BRIDGE_STATE:
                self._handle_bridge_state(msg.payload)
            elif kind is TopicKind.BRIDGE_NETWORKMAP:
                self._handle_networkmap(msg.payload, received_at)
            elif kind is TopicKind.DEVICE_STATE and parsed.friendly_name:
                self._handle_device_state(
                    self._name_to_ieee[parsed.friendly_name], msg.payload, received_at
                )
            elif kind is TopicKind.DEVICE_AVAILABILITY and parsed.friendly_name:
                self._handle_availability(
                    self._name_to_ieee[parsed.friendly_name], msg.payload, received_at
                )
            elif kind is TopicKind.UNKNOWN and parsed.friendly_name:
                self._buffer_pending(
                    parsed.friendly_name, parsed.suffix, msg.payload, received_at
                )
            # DEVICE_OTHER (/set, /get, ...) and BRIDGE_OTHER are ignored.
        except Exception:
            self.logger.exception(
                "Error processing Zigbee2MQTT message on %s", msg.topic
            )

    @callback
    def _buffer_pending(
        self, name: str, suffix: str, payload: Any, received_at: datetime
    ) -> None:
        """Remember the last message of a not (yet) known device/group.

        Wildcard subscriptions don't guarantee that the retained bridge/devices
        is delivered before the retained per-device availability, so the
        latest message per (name, kind) is kept until the next bridge/devices.
        Groups end up here too and are simply dropped at that point.
        """
        key = (name, suffix)
        if key not in self._pending and len(self._pending) >= PENDING_MESSAGES_MAX:
            return
        self._pending[key] = (payload, received_at)

    @callback
    def _replay_pending(self) -> None:
        pending, self._pending = self._pending, {}
        for (name, suffix), (payload, received_at) in pending.items():
            ieee = self._name_to_ieee.get(name)
            if ieee is None:
                continue
            if suffix == "availability":
                self._handle_availability(ieee, payload, received_at)
            else:
                self._handle_device_state(ieee, payload, received_at)

    @callback
    def _handle_bridge_state(self, payload: Any) -> None:
        state = parse_bridge_state(payload)
        if state is None:
            self.logger.debug("Ignoring unexpected bridge/state payload: %s", payload)
            return
        previous, self.bridge_state = self.bridge_state, state
        if state != "offline" or previous == "offline":
            return
        # While Zigbee2MQTT is down nobody tracks the devices: their last
        # availability is stale. Make it unknown so that no warning is based
        # on it, and so that the "online" Zigbee2MQTT publishes after its
        # restart is not counted as a reconnect.
        now = dt_util.utcnow()
        for ieee, record in self._devices.items():
            if (
                record["source"] != DEVICE_SOURCE_ZIGBEE2MQTT
                or record.get("available") is None
            ):
                continue
            record["available"] = None
            self._maybe_update_analytics(ieee, now, force=True)
            async_dispatcher_send(self.hass, self.device_signal(ieee))

    @callback
    def _handle_bridge_info(self, payload: Any) -> None:
        info = parse_bridge_info(payload)
        if info is None:
            self.logger.debug("Ignoring unexpected bridge/info payload")
            return
        self.bridge_info = info
        # Zigbee2MQTT's "passive" availability timeout is the longest time it
        # lets a device stay silent; use it when configured.
        self._analytics.silent_timeout = info.passive_timeout or SILENT_DEVICE_TIMEOUT
        if self.config_entry is not None:
            dev_reg = dr.async_get(self.hass)
            if device := dev_reg.async_get_device(identifiers={self.bridge_identifier}):
                dev_reg.async_update_device(
                    device.id,
                    sw_version=info.version,
                    model=info.coordinator_type or "Zigbee2MQTT bridge",
                )

    @callback
    def _handle_networkmap(self, payload: Any, received_at: datetime) -> None:
        network_map = parse_networkmap_response(payload)
        if network_map is None:
            self.logger.debug("Ignoring unusable network map response")
            return
        self._network_links = network_map.links
        self._network_nodes = network_map.nodes
        self.network_map_updated = received_at

    @callback
    def _handle_bridge_devices(self, payload: Any, received_at: datetime) -> None:
        """Reconcile tracked devices with the authoritative device list."""
        devices = parse_bridge_devices(payload)
        if devices is None:
            self.logger.debug("Ignoring unexpected bridge/devices payload")
            return
        if not any(not device.is_coordinator for device in devices):
            # An empty list (e.g. a retained "[]" left by a broken or freshly
            # reset Zigbee2MQTT) must not wipe every device and its history.
            self.logger.warning("Ignoring a Zigbee2MQTT device list without any device")
            return

        name_map: dict[str, str] = {}
        seen: set[str] = set()
        changed: list[str] = []
        for device in devices:
            if device.is_coordinator:
                self.coordinator_device = device
                continue
            ieee = device.ieee_address
            seen.add(ieee)
            name_map[device.friendly_name] = ieee
            previous = self._z2m_devices.get(ieee)
            self._z2m_devices[ieee] = device
            record = self._devices.get(ieee)
            if record is None:
                record = self._new_record(
                    ieee, DEVICE_SOURCE_ZIGBEE2MQTT, device.friendly_name, received_at
                )
                self._devices[ieee] = record
            elif previous is not None and previous != device:
                # Dataclass equality: covers renames, re-interviews and
                # capability changes (battery / voltage exposes).
                changed.append(ieee)
            self._apply_definition(record, device)

        removed = [
            ieee
            for ieee, record in self._devices.items()
            if record["source"] == DEVICE_SOURCE_ZIGBEE2MQTT and ieee not in seen
        ]
        self._name_to_ieee = name_map
        for ieee in removed:
            self._remove_device(ieee)

        # Registry migration once a device is fully known (interviewed), so
        # its final entity set is known. Disabled devices are migrated too:
        # their entities (areas, names, user settings) must survive.
        self._migrate_legacy_registry_entries(
            [
                ieee
                for ieee in self._devices
                if ieee not in self._migrated and self.interview_complete(ieee)
            ]
        )
        if not self._registry_reconciled:
            self._registry_reconciled = True
            self._remove_stale_registry_devices()
        for ieee in changed:
            self._update_registry_device(ieee)
            self._remove_unprovided_entities(ieee)
            async_dispatcher_send(self.hass, self.device_signal(ieee))
        # Platforms de-duplicate per unique id; re-sending for known devices
        # lets them add entities for devices that finished their interview,
        # gained capabilities or were re-enabled in Zigbee2MQTT.
        for ieee in self._devices:
            if self.wants_entities(ieee):
                async_dispatcher_send(self.hass, self.signal_new_device, ieee)

        self._replay_pending()
        self.async_set_updated_data(self._build_data())

    @callback
    def _remove_stale_registry_devices(self) -> None:
        """Remove registry devices of this entry unknown to Zigbee2MQTT.

        Runs on the first device list after start-up, so devices removed from
        Zigbee2MQTT while Home Assistant was not running are cleaned up too.
        """
        if self.config_entry is None:
            return
        dev_reg = dr.async_get(self.hass)
        entry_id = self.config_entry.entry_id
        # Legacy (friendly name based) identifiers of devices that are still
        # known, but not migrated yet (e.g. interview in progress), are kept.
        known = set(self._devices) | set(self._legacy_id_map(self._devices))
        for device in dr.async_entries_for_config_entry(dev_reg, entry_id):
            ids = {ident for domain, ident in device.identifiers if domain == DOMAIN}
            if not ids or self.bridge_identifier[1] in ids:
                continue
            if ids & known:
                continue
            self.logger.debug("Removing stale device %s", device.name)
            dev_reg.async_update_device(device.id, remove_config_entry_id=entry_id)

    @callback
    def _remove_unprovided_entities(self, ieee: str) -> None:
        """Remove entities of capabilities a device no longer has.

        E.g. a device re-interviewed as mains powered loses its battery
        entities instead of keeping orphans.
        """
        if self.config_entry is None or not self.interview_complete(ieee):
            return
        ent_reg = er.async_get(self.hass)
        keys = self.entity_keys(ieee)
        for domain, key in LEGACY_ENTITY_KEYS:
            if key in keys:
                continue
            entity_id = ent_reg.async_get_entity_id(domain, DOMAIN, f"{ieee}_{key}")
            if entity_id is not None:
                self.logger.debug(
                    "Removing %s: capability no longer exposed", entity_id
                )
                ent_reg.async_remove(entity_id)

    @callback
    def _handle_device_state(
        self, ieee: str, payload: Any, received_at: datetime
    ) -> None:
        data = parse_json(payload)
        if not isinstance(data, dict):
            self.logger.debug("Ignoring non JSON state payload for %s", ieee)
            return
        record = self._devices.get(ieee)
        if record is None:
            return

        # Merge partial updates: only keys present in this payload change.
        record["state"].update(data)
        # Record level only (API/panel); not an entity attribute.
        record["last_update"] = received_at.isoformat()
        metrics_update = extract_metrics(data)
        record["metrics"].update(metrics_update)
        last_seen = (
            parse_last_seen(data.get("last_seen"), received_at)
            if "last_seen" in data
            else None
        ) or received_at
        previous = as_datetime(record["metrics"].get("last_seen"))
        if previous is None or last_seen >= previous:
            record["metrics"]["last_seen"] = last_seen.isoformat()

        self._record_history(ieee, last_seen, metrics_update)
        self._maybe_update_analytics(ieee, received_at)
        self._maybe_fire_event(ieee, received_at)
        async_dispatcher_send(self.hass, self.device_signal(ieee))

    @callback
    def _handle_availability(
        self, ieee: str, payload: Any, received_at: datetime
    ) -> None:
        if self.bridge_state == "offline":
            # Retained availability is stale while Zigbee2MQTT is down (e.g.
            # HA starting while Zigbee2MQTT is stopped); Zigbee2MQTT publishes
            # fresh availability when it comes back.
            return
        available = parse_availability(payload)
        record = self._devices.get(ieee)
        if available is None or record is None:
            return
        previous = record.get("available")
        record["available"] = available
        if previous is False and available:
            # offline -> online: a reconnect
            record["reconnect_count"] += 1
            record["last_reconnect"] = received_at.isoformat()
            self._reconnect_events.setdefault(
                ieee, deque(maxlen=RECONNECT_EVENTS_MAX)
            ).append(received_at)
        if previous == available:
            return
        self._maybe_update_analytics(ieee, received_at, force=True)
        self._maybe_fire_event(ieee, received_at, force=True)
        async_dispatcher_send(self.hass, self.device_signal(ieee))

    async def async_request_network_map(self, routes: bool = False) -> bool:
        """Ask Zigbee2MQTT for a raw network map.

        The (possibly slow) response arrives on bridge/response/networkmap
        and is stored by _handle_networkmap. Not requested periodically: a
        network scan generates a lot of Zigbee traffic.
        """
        if self._enable_zha:
            return False
        await mqtt.async_publish(
            self.hass,
            f"{self._mqtt_prefix}/bridge/request/networkmap",
            json.dumps({"type": "raw", "routes": routes}),
        )
        return True

    # ------------------------------------------------------------------
    # Device records
    # ------------------------------------------------------------------
    def _new_record(
        self, ieee: str, source: str, friendly_name: str, first_seen: datetime
    ) -> dict[str, Any]:
        """Create a device record.

        Only small, JSON friendly values are stored here; the API, topology
        and diagnostics read these records.
        """
        return {
            "device_id": ieee,
            "ieee_address": ieee,
            "friendly_name": friendly_name,
            "source": source,
            "type": None,
            "manufacturer": None,
            "model": None,
            "model_id": None,
            "power_source": None,
            "disabled": False,
            "battery_powered": False,
            "has_voltage": False,
            "voltage_unit": None,
            "first_seen": first_seen.isoformat(),
            "available": None,
            "reconnect_count": 0,
            "last_reconnect": None,
            "last_update": None,
            "metrics": {},
            "state": {},
            "analytics_metrics": {},
        }

    @staticmethod
    def _apply_definition(record: dict[str, Any], device: Z2MDevice) -> None:
        record.update(
            {
                "friendly_name": device.friendly_name,
                "type": device.type,
                "network_address": device.network_address,
                "manufacturer": device.vendor or device.manufacturer,
                "model": device.description or device.model,
                "model_id": device.model or device.model_id,
                "power_source": device.power_source,
                "sw_version": device.software_build_id,
                "interview_state": device.interview_state,
                "has_definition": device.model is not None,
                "supported": device.supported,
                "disabled": device.disabled,
                "battery_powered": device.is_battery_powered,
                "has_voltage": device.exposes_voltage,
                "voltage_unit": device.voltage_unit,
            }
        )
        record["metrics"]["type"] = _TYPE_TO_TOPOLOGY.get(device.type, "end_device")

    @callback
    def _remove_device(self, ieee: str) -> None:
        """Forget a device that is no longer part of the network."""
        record = self._devices.pop(ieee, None)
        self._z2m_devices.pop(ieee, None)
        self._history.pop(ieee, None)
        self._reconnect_events.pop(ieee, None)
        self._analytics_computed_at.pop(ieee, None)
        self._last_event.pop(ieee, None)
        self.logger.debug(
            "Device %s (%s) removed",
            ieee,
            record.get("friendly_name") if record else None,
        )
        if self.config_entry is not None:
            dev_reg = dr.async_get(self.hass)
            if device := dev_reg.async_get_device(identifiers={(DOMAIN, ieee)}):
                dev_reg.async_update_device(
                    device.id, remove_config_entry_id=self.config_entry.entry_id
                )
        async_dispatcher_send(self.hass, self.signal_device_removed, ieee)

    @callback
    def _update_registry_device(self, ieee: str) -> None:
        """Push renamed / re-interviewed device details to the registry."""
        if self.config_entry is None:
            return
        record = self._devices[ieee]
        dev_reg = dr.async_get(self.hass)
        if device := dev_reg.async_get_device(identifiers={(DOMAIN, ieee)}):
            dev_reg.async_update_device(
                device.id,
                name=record["friendly_name"],
                manufacturer=record.get("manufacturer"),
                model=record.get("model"),
                model_id=record.get("model_id"),
                sw_version=record.get("sw_version"),
            )

    def _legacy_id_map(self, ieees: Iterable[str]) -> dict[str, str]:
        """Map legacy (pre-IEEE) device ids to IEEE addresses.

        Z2M: the legacy id was the first topic segment of the friendly name;
        when several devices share it, only an exact name match is migrated.
        ZHA: the legacy id already was the IEEE address.
        """
        wanted = set(ieees)
        exact: dict[str, str] = {}
        truncated: dict[str, set[str]] = {}
        for ieee, record in self._devices.items():
            if record["source"] == DEVICE_SOURCE_ZHA:
                exact[ieee] = ieee
                continue
            legacy, is_exact = _legacy_z2m_ids(record["friendly_name"])
            if is_exact:
                exact[legacy] = ieee
            else:
                truncated.setdefault(legacy, set()).add(ieee)
        mapping = dict(exact)
        for legacy, candidates in truncated.items():
            if legacy not in mapping and len(candidates) == 1:
                mapping[legacy] = next(iter(candidates))
        return {legacy: ieee for legacy, ieee in mapping.items() if ieee in wanted}

    @callback
    def _migrate_legacy_registry_entries(self, ieees: Iterable[str]) -> None:
        """Move registry entries of previous releases to IEEE based ids.

        Earlier releases used ``zigsight_<device id>_<key>`` unique ids and
        ``(zigsight, <device id>)`` device identifiers, where the device id
        was the Zigbee2MQTT friendly name. This runs synchronously before the
        platforms are told about the devices, so the entities are added with
        their migrated registry entries (keeping entity ids and history).

        Legacy entities whose key is no longer created for the device (e.g.
        battery sensors of mains powered devices, voltage without a voltage
        expose) are removed instead of lingering as "no longer provided".
        """
        ieees = list(ieees)
        self._migrated.update(ieees)
        if self.config_entry is None or not ieees:
            return
        ent_reg = er.async_get(self.hass)
        dev_reg = dr.async_get(self.hass)
        entry_id = self.config_entry.entry_id
        for legacy, ieee in self._legacy_id_map(ieees).items():
            keys = self.entity_keys(ieee)
            for domain, key in LEGACY_ENTITY_KEYS:
                old_unique_id = f"{DOMAIN}_{legacy}_{key}"
                entity_id = ent_reg.async_get_entity_id(domain, DOMAIN, old_unique_id)
                if entity_id is None:
                    continue
                if key not in keys:
                    self.logger.info(
                        "Removing legacy entity %s: not provided for this device",
                        entity_id,
                    )
                    ent_reg.async_remove(entity_id)
                    continue
                new_unique_id = f"{ieee}_{key}"
                if ent_reg.async_get_entity_id(domain, DOMAIN, new_unique_id):
                    self.logger.debug(
                        "Removing duplicate legacy entity %s (%s already exists)",
                        entity_id,
                        new_unique_id,
                    )
                    ent_reg.async_remove(entity_id)
                    continue
                self.logger.info(
                    "Migrating %s unique id %s -> %s",
                    entity_id,
                    old_unique_id,
                    new_unique_id,
                )
                ent_reg.async_update_entity(entity_id, new_unique_id=new_unique_id)

            if legacy == ieee:
                continue
            old_device = dev_reg.async_get_device(identifiers={(DOMAIN, legacy)})
            if old_device is None:
                continue
            if dev_reg.async_get_device(identifiers={(DOMAIN, ieee)}) is None:
                dev_reg.async_update_device(
                    old_device.id,
                    new_identifiers={(DOMAIN, ieee)},
                    via_device_id=None,
                )
            else:
                dev_reg.async_update_device(
                    old_device.id, remove_config_entry_id=entry_id
                )

    # ------------------------------------------------------------------
    # History / analytics / events
    # ------------------------------------------------------------------
    @callback
    def _record_history(
        self, ieee: str, timestamp: datetime, metrics_update: dict[str, Any]
    ) -> None:
        """Append a numeric history point (rate limited, bounded)."""
        if not metrics_update:
            return
        history = self._history.setdefault(ieee, deque(maxlen=HISTORY_MAX_ENTRIES))
        metrics = self._devices[ieee]["metrics"]
        if history:
            last = history[-1]
            elapsed = timestamp - last["timestamp"]
            battery_changed = (
                "battery" in metrics_update
                and metrics_update["battery"] != last["battery"]
            )
            if elapsed < HISTORY_MIN_INTERVAL and not (
                battery_changed and elapsed >= HISTORY_MIN_INTERVAL_ON_BATTERY_CHANGE
            ):
                return
        history.append(
            {
                "timestamp": timestamp,
                "link_quality": metrics.get("link_quality"),
                "battery": metrics.get("battery"),
                "voltage": metrics.get("voltage"),
            }
        )

    @callback
    def _maybe_update_analytics(
        self, ieee: str, now: datetime, force: bool = False
    ) -> None:
        last = self._analytics_computed_at.get(ieee)
        if force or last is None or now - last >= ANALYTICS_MIN_INTERVAL:
            self._update_analytics(ieee, now)

    @callback
    def _update_analytics(self, ieee: str, now: datetime | None = None) -> None:
        """Recompute the analytics metrics of one device."""
        record = self._devices.get(ieee)
        if record is None:
            return
        now = now or dt_util.utcnow()
        reconnect_rate = self._analytics.compute_reconnect_rate(
            self._reconnect_events.get(ieee, ()), now=now
        )
        battery_trend = self._analytics.compute_battery_trend(
            self._history.get(ieee, ()), now=now
        )
        record["analytics_metrics"] = {
            "reconnect_rate": reconnect_rate,
            "battery_trend": battery_trend,
            "health_score": self._analytics.compute_health_score(
                record, reconnect_rate, now
            ),
            "battery_drain_warning": self._analytics.check_battery_drain_warning(
                battery_trend
            ),
            "connectivity_warning": self._analytics.check_connectivity_warning(
                record, reconnect_rate, self._reconnect_rate_threshold, now
            ),
        }
        self._analytics_computed_at[ieee] = now

    @callback
    def _maybe_fire_event(self, ieee: str, now: datetime, force: bool = False) -> None:
        """Fire a slim, rate limited ``zigsight_device_update`` event."""
        record = self._devices[ieee]
        metrics = record["metrics"]
        # Link quality changes with nearly every report: it is included in the
        # payload but doesn't trigger an event on its own.
        snapshot = (
            metrics.get("battery"),
            metrics.get("voltage"),
            record.get("available"),
        )
        last = self._last_event.get(ieee)
        if last is not None:
            last_time, last_snapshot = last
            if snapshot == last_snapshot:
                return
            if not force and now - last_time < EVENT_MIN_INTERVAL:
                return
        self._last_event[ieee] = (now, snapshot)
        self.hass.bus.async_fire(
            EVENT_DEVICE_UPDATE,
            {
                "device_id": ieee,
                "friendly_name": record["friendly_name"],
                "source": record["source"],
                "available": record.get("available"),
                "metrics": {
                    **{key: metrics.get(key) for key in _TRACKED_METRICS},
                    "last_seen": metrics.get("last_seen"),
                },
            },
        )

    # ------------------------------------------------------------------
    # ZHA
    # ------------------------------------------------------------------
    async def _collect_zha_devices(self) -> None:
        """Collect devices from ZHA (registry discovery + entity states).

        Called at start-up and by the periodic refresh: re-discovering
        devices/entities from the registries is cheap (the collector only
        resubscribes if the tracked entity set actually changed) and is a
        safety net for ZHA devices added/removed between registry update
        events. Values in between are pushed live by the collector's
        state-change tracking (see ``_handle_zha_push_update``), not polled
        here -- in particular, ``last_seen`` is only ever advanced from a
        push update (see ``_process_zha_device_update``).

        While no ZHA config entry is loaded (e.g. it hasn't started yet, or
        was removed), ZHA devices' availability is marked unknown instead
        of being polled -- see ``_mark_zha_devices_unknown``.
        """
        if not self._zha_collector:
            return
        if not self._zha_collector.is_available():
            self._mark_zha_devices_unknown()
            return

        try:
            zha_devices = await self._zha_collector.collect_devices()
        except Exception as err:
            self.logger.error("Error collecting ZHA devices: %s", err)
            return

        new: list[str] = []
        for device_id, device_data in zha_devices.items():
            if self._process_zha_device_update(device_id, device_data):
                new.append(device_id)
        if new:
            self._migrate_legacy_registry_entries(
                ieee for ieee in new if ieee not in self._migrated
            )
            for ieee in new:
                async_dispatcher_send(self.hass, self.signal_new_device, ieee)

        # A ZHA device no longer in the snapshot was removed/unpaired: drop
        # it (and let it be deleted from the UI -- see
        # async_remove_config_entry_device in __init__.py).
        removed = [
            ieee
            for ieee, record in self._devices.items()
            if record["source"] == DEVICE_SOURCE_ZHA and ieee not in zha_devices
        ]
        for ieee in removed:
            self._remove_device(ieee)

        self.logger.debug("Collected %d ZHA devices", len(zha_devices))
        self._update_zha_diagnostics_issue()

    @callback
    def _mark_zha_devices_unknown(self) -> None:
        """Mark ZHA devices' availability unknown while ZHA isn't loaded.

        Mirrors ``_handle_bridge_state`` for Zigbee2MQTT going offline:
        while no ZHA config entry is loaded nobody is tracking device
        availability, so a later "available" reading (once ZHA reloads)
        must not look like a reconnect.
        """
        now = dt_util.utcnow()
        for ieee, record in self._devices.items():
            if record["source"] != DEVICE_SOURCE_ZHA or record.get("available") is None:
                continue
            record["available"] = None
            self._maybe_update_analytics(ieee, now, force=True)
            async_dispatcher_send(self.hass, self.device_signal(ieee))
        if self.config_entry is not None:
            # Nothing can be said about disabled diagnostics without a
            # loaded ZHA entry to inspect; don't leave a stale issue.
            ir.async_delete_issue(self.hass, DOMAIN, ISSUE_ZHA_DIAGNOSTICS_DISABLED)

    @callback
    def _update_zha_diagnostics_issue(self) -> None:
        """Create/clear the repair issue for disabled ZHA LQI/RSSI sensors."""
        if self.config_entry is None or self._zha_collector is None:
            return
        # Reuses the device map the collector just (re-)discovered instead
        # of walking the entity registry again.
        disabled_count = self._zha_collector.count_disabled_diagnostics()
        if disabled_count:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                ISSUE_ZHA_DIAGNOSTICS_DISABLED,
                is_fixable=False,
                is_persistent=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_ZHA_DIAGNOSTICS_DISABLED,
                translation_placeholders={"count": str(disabled_count)},
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, ISSUE_ZHA_DIAGNOSTICS_DISABLED)

    @callback
    def _handle_zha_push_update(self, ieee: str, device_data: dict[str, Any]) -> None:
        """Handle a live state-change pushed by the ZHA collector."""
        is_new = self._process_zha_device_update(ieee, device_data, is_push=True)
        if is_new:
            self._migrate_legacy_registry_entries(
                [ieee] if ieee not in self._migrated else []
            )
            async_dispatcher_send(self.hass, self.signal_new_device, ieee)

    def _process_zha_device_update(
        self, device_id: str, device_data: dict[str, Any], *, is_push: bool = False
    ) -> bool:
        """Store one ZHA device update; return True if the device is new.

        ``is_push`` distinguishes a live state-change push from a periodic
        registry re-discovery snapshot: only a push may advance an
        *existing* device's ``last_seen`` (to the entity's own
        ``last_reported``/``last_updated``). A snapshot must never bump it
        to "now" -- doing so previously masked devices going silent
        (analytics falls back to ``last_seen`` for the connectivity
        warning whenever ``available`` is unknown, which it is for any
        device whose LQI/RSSI/battery entities are all still disabled) and
        would defeat the purpose of that warning entirely. A brand new
        device's ``last_seen`` is still seeded once, from whatever the
        discovery snapshot that found it observed -- see below.
        """
        now = dt_util.utcnow()
        record = self._devices.get(device_id)
        is_new = record is None
        if record is None:
            record = self._new_record(
                device_id,
                DEVICE_SOURCE_ZHA,
                device_data.get("friendly_name", device_id),
                now,
            )
            # The power source is not known for ZHA devices (see
            # zha_collector docstring): create the battery entities too.
            record["battery_powered"] = True
            self._devices[device_id] = record
        record["friendly_name"] = device_data.get(
            "friendly_name", record["friendly_name"]
        )
        record["manufacturer"] = device_data.get("manufacturer") or record.get(
            "manufacturer"
        )
        record["model"] = device_data.get("model") or record.get("model")

        device_metrics = device_data.get("metrics") or {}
        record["metrics"].update(device_metrics)
        # Only link_quality/battery/voltage are "tracked" for history and
        # the zigsight_device_update event; rssi is kept in the record
        # (API/diagnostics) but isn't one of them.
        metrics_update = {
            key: value
            for key, value in device_metrics.items()
            if key in _TRACKED_METRICS and isinstance(value, int | float)
        }

        if is_new:
            # Seed last_seen once, from whatever the discovery snapshot
            # itself observed (a tracked entity's own last_reported /
            # last_updated, only for a non-unavailable, non-restored
            # state -- see zha_collector._collect_device). A freshly
            # discovered device would otherwise have no last_seen at all
            # until its first live push, which may not happen for a long
            # time on an idle device.
            seed_last_seen = device_data.get("last_seen")
            if isinstance(seed_last_seen, datetime):
                record["metrics"]["last_seen"] = seed_last_seen.isoformat()

        if is_push:
            pushed_last_seen = device_data.get("last_seen")
            if isinstance(pushed_last_seen, datetime):
                previous_last_seen = as_datetime(record["metrics"].get("last_seen"))
                if previous_last_seen is None or pushed_last_seen >= previous_last_seen:
                    record["metrics"]["last_seen"] = pushed_last_seen.isoformat()

        record["last_update"] = now.isoformat()

        # Availability transitions drive reconnect counting, exactly like
        # Zigbee2MQTT's <name>/availability handling: never once per
        # poll/event, only on False -> True.
        available = device_data.get("available")
        previous_available = record.get("available")
        availability_changed = False
        if available is not None and available != previous_available:
            availability_changed = True
            record["available"] = available
            if previous_available is False and available:
                record["reconnect_count"] += 1
                record["last_reconnect"] = now.isoformat()
                self._reconnect_events.setdefault(
                    device_id, deque(maxlen=RECONNECT_EVENTS_MAX)
                ).append(now)

        self._record_history(device_id, now, metrics_update)
        self._maybe_update_analytics(device_id, now, force=availability_changed)
        self._maybe_fire_event(device_id, now, force=availability_changed)
        async_dispatcher_send(self.hass, self.device_signal(device_id))
        return is_new

    # ------------------------------------------------------------------
    # DataUpdateCoordinator
    # ------------------------------------------------------------------
    def _build_data(self) -> dict[str, Any]:
        return {
            "devices": self._devices,
            "device_count": len(self._devices),
            "bridge_state": self.bridge_state,
            "network": self.get_network_info(),
        }

    async def _async_update_data(self) -> dict[str, Any]:
        """Collect ZHA devices (ZHA mode) and recompute analytics."""
        try:
            if self._enable_zha and self._zha_collector:
                await self._collect_zha_devices()
            now = dt_util.utcnow()
            for ieee in list(self._devices):
                self._update_analytics(ieee, now)
            return self._build_data()
        except Exception as err:
            raise UpdateFailed(f"Error fetching ZigSight data: {err}") from err

    # ------------------------------------------------------------------
    # Accessors used by the platforms, the API and diagnostics
    # ------------------------------------------------------------------
    def device_ids(self) -> list[str]:
        """Return the IEEE addresses of all tracked devices."""
        return list(self._devices)

    def interview_complete(self, ieee: str) -> bool:
        """Return True once a device's entity set is known.

        Zigbee2MQTT devices need a finished interview or a definition: before
        that, their power source and exposes are unknown. A FAILED interview
        is final too: such devices still report link quality, so they get the
        entities their (possibly partial) information allows, at least the
        base ones.
        """
        record = self._devices.get(ieee)
        if record is None:
            return False
        if record["source"] != DEVICE_SOURCE_ZIGBEE2MQTT:
            return True
        return record.get("interview_state") in ("SUCCESSFUL", "FAILED") or bool(
            record.get("has_definition")
        )

    def wants_entities(self, ieee: str) -> bool:
        """Return True if entities should exist for this device."""
        record = self._devices.get(ieee)
        if record is None or record.get("disabled"):
            return False
        return self.interview_complete(ieee)

    def entity_keys(self, ieee: str) -> set[str]:
        """Return the entity description keys to create for a device."""
        record = self._devices.get(ieee) or {}
        keys = set(BASE_ENTITY_KEYS)
        if record.get("battery_powered"):
            keys |= BATTERY_ENTITY_KEYS
        if record.get("has_voltage"):
            keys.add("voltage")
        return keys

    def device_info(self, ieee: str) -> DeviceInfo:
        """Return the DeviceInfo for a tracked device."""
        record = self._devices.get(ieee) or {}
        return DeviceInfo(
            identifiers={(DOMAIN, ieee)},
            name=record.get("friendly_name") or ieee,
            manufacturer=record.get("manufacturer"),
            model=record.get("model"),
            model_id=record.get("model_id"),
            sw_version=record.get("sw_version"),
            via_device=self.bridge_identifier,
        )

    def get_device(self, device_id: str) -> dict[str, Any] | None:
        """Get device data by device ID (IEEE address)."""
        return self._devices.get(device_id)

    def get_device_metrics(self, device_id: str) -> dict[str, Any] | None:
        """Get current metrics for a device."""
        device = self.get_device(device_id)
        if device:
            return device.get("metrics")
        return None

    def get_device_history(self, device_id: str) -> list[dict[str, Any]]:
        """Get the numeric metric history of a device (oldest first)."""
        return [
            {
                "timestamp": entry["timestamp"].isoformat(),
                "metrics": {key: entry.get(key) for key in _TRACKED_METRICS},
            }
            for entry in self._history.get(device_id, ())
        ]

    def get_device_reconnect_events(self, device_id: str) -> list[str]:
        """Get the recorded reconnect timestamps of a device."""
        return [ts.isoformat() for ts in self._reconnect_events.get(device_id, ())]

    def _analytics_value(self, device_id: str, key: str) -> Any:
        device = self.get_device(device_id)
        if device is None:
            return None
        if key not in device.get("analytics_metrics", {}):
            self._update_analytics(device_id)
        return device["analytics_metrics"].get(key)

    def get_device_reconnect_rate(self, device_id: str) -> float | None:
        """Get reconnect rate (events/hour) for a device."""
        value = self._analytics_value(device_id, "reconnect_rate")
        return float(value) if value is not None else None

    def get_device_battery_trend(self, device_id: str) -> float | None:
        """Get battery trend (%/hour) for a device."""
        return self._analytics_value(device_id, "battery_trend")

    def get_device_health_score(self, device_id: str) -> float | None:
        """Get health score for a device."""
        return self._analytics_value(device_id, "health_score")

    def get_device_battery_drain_warning(self, device_id: str) -> bool:
        """Get battery drain warning status for a device."""
        return bool(self._analytics_value(device_id, "battery_drain_warning"))

    def get_device_connectivity_warning(self, device_id: str) -> bool:
        """Get connectivity warning status for a device."""
        return bool(self._analytics_value(device_id, "connectivity_warning"))

    def get_all_devices(self) -> dict[str, dict[str, Any]]:
        """Return shallow copies of all device records (without raw state)."""
        return {
            ieee: {key: value for key, value in record.items() if key != "state"}
            for ieee, record in self._devices.items()
        }

    def get_bridge_devices(self) -> list[dict[str, Any]]:
        """Return the raw Zigbee2MQTT device list (including the coordinator)."""
        devices = [device.as_dict() for device in self._z2m_devices.values()]
        if self.coordinator_device is not None:
            devices.insert(0, self.coordinator_device.as_dict())
        return devices

    def get_network_info(self) -> dict[str, Any] | None:
        """Return network information (channel, PAN id, versions)."""
        if self.bridge_info is None:
            return None
        return self.bridge_info.as_dict()

    def get_network_links(self) -> list[dict[str, Any]]:
        """Return links of the last received raw network map."""
        return [link.as_dict() for link in self._network_links]

    def get_network_nodes(self) -> list[dict[str, Any]]:
        """Return nodes of the last received raw network map."""
        return list(self._network_nodes)
