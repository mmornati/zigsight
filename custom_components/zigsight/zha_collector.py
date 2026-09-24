"""ZHA collector for ZigSight.

Builds ZigSight device records purely from Home Assistant's device and
entity registries, plus entity states -- it never reaches into ZHA's
private runtime data (``hass.data["zha"]``), which is not a documented,
stable API and changes across ZHA releases (this is what broke the previous
implementation of this module, see REVIEW.md C2).

Discovery
    A Home Assistant device belongs to ZHA when it has a
    ``("zha", <ieee>)`` identifier (see
    ``homeassistant.components.zha.helpers``) and is attached to a *loaded*
    ZHA config entry. For each such device we look up, from the entity
    registry, its diagnostic sensors:

    - the LQI (link quality) and RSSI sensors. These are defined by the
      ``zha`` library (``zha.application.platforms.sensor.RSSISensor`` /
      ``LQISensor``, verified against the ``zha`` package installed in this
      environment's ``.venv``): domain ``sensor``, ``translation_key``
      ``"rssi"`` / ``"lqi"``, ``entity_category`` diagnostic, and
      ``entity_registry_enabled_default = False`` -- i.e. ZHA disables them
      by default (``disabled_by == RegistryEntryDisabler.INTEGRATION``),
      which is exactly what ``async_enable_diagnostic_entities`` (used by
      the ``zigsight.enable_zha_diagnostic_entities`` service) enables.
    - the battery sensor, matched by ``device_class`` /
      ``original_device_class`` ``"battery"``.

    ZHA does not publish a dedicated "last seen" sensor entity or a
    registry-exposed attribute for it (verified against
    ``homeassistant.components.zha`` and the ``zha`` library in this
    environment: ``last_seen`` only exists as a private attribute of the
    internal ``zha.zigbee.device.Device`` object, which ZigSight does not
    read). ZigSight instead timestamps a device as "seen" from the
    ``last_reported``/``last_updated`` of a tracked entity's state whenever
    a live push update is processed -- see ``ZigSightCoordinator.
    _process_zha_device_update`` for why this only happens for pushed
    updates, never for a periodic re-discovery snapshot.

    Likewise, neither the device registry nor the diagnostic entities
    expose the Zigbee power source / device type (router vs. end device);
    that only lives on ZHA's private ``Device`` object. ``device_type`` is
    therefore always ``"unknown"`` for ZHA devices; this is documented in
    ``docs/integrations/zha.md``.

    Discovery itself is triggered by the coordinator's periodic refresh and
    by Home Assistant's device/entity registry update events (debounced),
    so new/removed ZHA devices and newly enabled diagnostic entities are
    picked up without waiting a full refresh interval; re-subscribing to
    entity state changes only happens when the tracked entity id set
    actually changed, not on every discovery pass.

Live updates
    Once ``async_setup`` is called, state changes of the tracked entities
    are delivered live via ``async_track_state_change_event`` -- values are
    pushed to ZigSight as they change instead of being polled on a fixed
    interval. ``collect_devices`` (used by the coordinator's periodic
    refresh) re-discovers devices/entities and returns a full snapshot; it
    exists to notice devices ZHA adds after start-up and as a safety net,
    not as the primary way values are read.

Availability / reconnects
    ZHA marks an entity's state ``unavailable`` when the underlying Zigbee
    device is not reachable. The collector reports a device as available
    when any tracked entity has a non-unavailable, non-"restored" state,
    and unavailable when all of them are unavailable. A state with the
    ``restored`` attribute set is the stub Home Assistant writes for an
    entity that was removed while Home Assistant was running (e.g. ZHA
    reloading, which happens automatically ~30 seconds after
    ``zigsight.enable_zha_diagnostic_entities`` runs, or after any ZHA
    options change) -- it is *not* a real "device went offline" signal and
    is ignored entirely (neither available nor unavailable), so a ZHA
    reload never looks like a spurious reconnect. The coordinator (see
    ``ZigSightCoordinator._process_zha_device_update``) only counts a
    reconnect on the ``False`` -> ``True`` transition of that flag -- never
    once per poll/event -- mirroring the availability based reconnect
    counting introduced for Zigbee2MQTT.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import ATTR_RESTORED, STATE_UNAVAILABLE
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_call_later,
    async_track_state_change_event,
)

_LOGGER = logging.getLogger(__name__)

ZHA_DOMAIN = "zha"

# Translation keys of the diagnostic sensors defined by the `zha` library
# (zha.application.platforms.sensor.RSSISensor / LQISensor).
TRANSLATION_KEY_RSSI = "rssi"
TRANSLATION_KEY_LQI = "lqi"

# Debounce window for device/entity registry change events (several
# entities of the same device are typically added/removed/enabled at once).
_REGISTRY_DEBOUNCE_SECONDS = 2.0


@dataclass(slots=True)
class ZHATrackedEntities:
    """Diagnostic entity ids tracked for one ZHA device."""

    lqi: str | None = None
    rssi: str | None = None
    battery: str | None = None

    def as_tuple(self) -> tuple[str, ...]:
        """Return the non-None tracked entity ids."""
        return tuple(
            entity_id
            for entity_id in (self.lqi, self.rssi, self.battery)
            if entity_id is not None
        )


@dataclass(slots=True)
class ZHADeviceInfo:
    """A ZHA device, as known from the device/entity registries."""

    ieee: str
    ha_device_id: str
    name: str
    model: str | None
    manufacturer: str | None
    via_device_ieee: str | None
    # Router / end device is not derivable from the registries (see module
    # docstring); always "unknown" for now.
    device_type: str = "unknown"
    entities: ZHATrackedEntities = field(default_factory=ZHATrackedEntities)
    # Whether the LQI/RSSI entities are currently disabled by their ZHA
    # integration default (never a user's own choice); tracked here so the
    # repair issue / enable service don't have to re-walk the registry.
    lqi_disabled_by_integration: bool = False
    rssi_disabled_by_integration: bool = False


def async_get_zha_config_entries(hass: HomeAssistant) -> list[ConfigEntry]:
    """Return the loaded ZHA config entries."""
    return [
        entry
        for entry in hass.config_entries.async_entries(ZHA_DOMAIN)
        if entry.state is ConfigEntryState.LOADED
    ]


def _matches(entry: er.RegistryEntry, translation_key: str, suffix: str) -> bool:
    if entry.translation_key == translation_key:
        return True
    unique_id = (entry.unique_id or "").lower()
    return unique_id.endswith(f"-{suffix}") or unique_id.endswith(f"_{suffix}")


def async_discover_devices(hass: HomeAssistant) -> dict[str, ZHADeviceInfo]:
    """Build the ZHA device map from the device/entity registries."""
    zha_entry_ids = {entry.entry_id for entry in async_get_zha_config_entries(hass)}
    if not zha_entry_ids:
        return {}

    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)

    ieee_by_device_id: dict[str, str] = {}
    for device in dev_reg.devices.values():
        for domain, identifier in device.identifiers:
            if domain == ZHA_DOMAIN:
                ieee_by_device_id[device.id] = identifier
                break

    devices: dict[str, ZHADeviceInfo] = {}
    for device in dev_reg.devices.values():
        if not device.config_entries & zha_entry_ids:
            continue
        ieee = ieee_by_device_id.get(device.id)
        if ieee is None:
            continue

        entities = ZHATrackedEntities()
        lqi_disabled_by_integration = False
        rssi_disabled_by_integration = False
        for entity in er.async_entries_for_device(
            ent_reg, device.id, include_disabled_entities=True
        ):
            if entity.domain != "sensor":
                continue
            if entities.lqi is None and _matches(entity, TRANSLATION_KEY_LQI, "lqi"):
                entities.lqi = entity.entity_id
                lqi_disabled_by_integration = (
                    entity.disabled_by is er.RegistryEntryDisabler.INTEGRATION
                )
            elif entities.rssi is None and _matches(
                entity, TRANSLATION_KEY_RSSI, "rssi"
            ):
                entities.rssi = entity.entity_id
                rssi_disabled_by_integration = (
                    entity.disabled_by is er.RegistryEntryDisabler.INTEGRATION
                )
            elif entities.battery is None and "battery" in (
                entity.device_class,
                entity.original_device_class,
            ):
                entities.battery = entity.entity_id

        via_ieee = (
            ieee_by_device_id.get(device.via_device_id)
            if device.via_device_id
            else None
        )
        devices[ieee] = ZHADeviceInfo(
            ieee=ieee,
            ha_device_id=device.id,
            name=device.name_by_user or device.name or ieee,
            model=device.model,
            manufacturer=device.manufacturer,
            via_device_ieee=via_ieee,
            entities=entities,
            lqi_disabled_by_integration=lqi_disabled_by_integration,
            rssi_disabled_by_integration=rssi_disabled_by_integration,
        )
    return devices


def _count_disabled_diagnostics(devices: Iterable[ZHADeviceInfo]) -> int:
    return sum(
        int(info.lqi_disabled_by_integration) + int(info.rssi_disabled_by_integration)
        for info in devices
    )


def async_enable_diagnostic_entities(hass: HomeAssistant) -> list[str]:
    """Enable ZHA LQI/RSSI entities still disabled by their integration default.

    Only entities with ``disabled_by == RegistryEntryDisabler.INTEGRATION``
    are touched; entities a user explicitly disabled
    (``RegistryEntryDisabler.USER``) are left alone. Home Assistant reloads
    the owning (ZHA) config entry automatically ~30 seconds
    (``homeassistant.config_entries.RELOAD_AFTER_UPDATE_DELAY``) after an
    entity is enabled through the registry -- the entity is not created
    immediately.
    """
    ent_reg = er.async_get(hass)
    enabled: list[str] = []
    for info in async_discover_devices(hass).values():
        if info.lqi_disabled_by_integration and info.entities.lqi is not None:
            ent_reg.async_update_entity(info.entities.lqi, disabled_by=None)
            enabled.append(info.entities.lqi)
        if info.rssi_disabled_by_integration and info.entities.rssi is not None:
            ent_reg.async_update_entity(info.entities.rssi, disabled_by=None)
            enabled.append(info.entities.rssi)
    return enabled


def async_count_disabled_diagnostic_entities(hass: HomeAssistant) -> int:
    """Count LQI/RSSI entities still disabled by the ZHA integration default."""
    return _count_disabled_diagnostics(async_discover_devices(hass).values())


class ZHACollector:
    """Collect ZigSight device data from the ZHA integration."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the collector."""
        self.hass = hass
        self._devices: dict[str, ZHADeviceInfo] = {}
        self._entity_to_ieee: dict[str, str] = {}
        self._tracked_entity_ids: frozenset[str] = frozenset()
        self._unsub_tracking: Callable[[], None] | None = None
        self._unsub_registry: list[Callable[[], None]] = []
        self._unsub_debounce: Callable[[], None] | None = None
        self._on_update: Callable[[str, dict[str, Any]], None] | None = None

    def is_available(self) -> bool:
        """Return True if at least one ZHA config entry is loaded."""
        return bool(async_get_zha_config_entries(self.hass))

    def count_disabled_diagnostics(self) -> int:
        """Count disabled LQI/RSSI entities among the last discovered devices.

        Reuses the device map from the last discovery pass instead of
        re-walking the entity registry (the coordinator calls this right
        after ``collect_devices``/live discovery for its repair issue).
        """
        return _count_disabled_diagnostics(self._devices.values())

    @callback
    def async_setup(self, on_update: Callable[[str, dict[str, Any]], None]) -> None:
        """Start tracking ZHA diagnostic entities for live (push) updates.

        Also starts a debounced listener on the device/entity registries so
        devices/entities added, removed or (re-)enabled are noticed without
        waiting for the next periodic refresh.
        """
        self._on_update = on_update
        self._async_refresh_tracking()
        self._unsub_registry = [
            self.hass.bus.async_listen(
                dr.EVENT_DEVICE_REGISTRY_UPDATED,
                self._async_registry_changed,
                event_filter=self._device_event_is_zha,
            ),
            self.hass.bus.async_listen(
                er.EVENT_ENTITY_REGISTRY_UPDATED,
                self._async_registry_changed,
                event_filter=self._entity_event_is_zha,
            ),
        ]

    @callback
    def async_stop(self) -> None:
        """Stop tracking entity state changes and registry updates."""
        if self._unsub_tracking is not None:
            self._unsub_tracking()
            self._unsub_tracking = None
        for unsub in self._unsub_registry:
            unsub()
        self._unsub_registry = []
        if self._unsub_debounce is not None:
            self._unsub_debounce()
            self._unsub_debounce = None
        self._on_update = None

    @callback
    def _device_event_is_zha(
        self, event_data: dr.EventDeviceRegistryUpdatedData
    ) -> bool:
        """event_filter: only device changes relevant to a ZHA device."""
        if event_data["action"] == "remove":
            identifiers = event_data["device"].get("identifiers") or ()
            return any(domain == ZHA_DOMAIN for domain, _ident in identifiers)
        device = dr.async_get(self.hass).async_get(event_data["device_id"])
        return device is not None and any(
            domain == ZHA_DOMAIN for domain, _ident in device.identifiers
        )

    @callback
    def _entity_event_is_zha(
        self, event_data: er.EventEntityRegistryUpdatedData
    ) -> bool:
        """event_filter: only entity changes relevant to a tracked ZHA entity."""
        entity_id = event_data["entity_id"]
        if entity_id in self._entity_to_ieee:
            # A change (e.g. enabled, renamed, removed) to an entity we
            # already track -- always relevant, regardless of platform.
            return True
        entry = er.async_get(self.hass).async_get(entity_id)
        return entry is not None and entry.platform == ZHA_DOMAIN

    @callback
    def _async_registry_changed(self, event: Event[Any]) -> None:
        """Debounce device/entity registry updates into one re-discovery."""
        if self._unsub_debounce is not None:
            return
        self._unsub_debounce = async_call_later(
            self.hass, _REGISTRY_DEBOUNCE_SECONDS, self._async_debounced_refresh
        )

    @callback
    def _async_debounced_refresh(self, _now: datetime) -> None:
        self._unsub_debounce = None
        if not self.is_available():
            # ZHA isn't loaded right now (unloading, or still starting up):
            # a discovery pass would find nothing and tear down the
            # current tracking, leaving push updates unhandled for up to a
            # full periodic refresh interval once ZHA comes back. Keep
            # whatever is currently tracked instead; the periodic refresh
            # (or the next registry event once ZHA is back) will catch up.
            return
        self._async_refresh_tracking()

    @callback
    def _async_refresh_tracking(self) -> None:
        """Re-discover devices/entities; resubscribe only if that changed."""
        self._devices = async_discover_devices(self.hass)
        self._entity_to_ieee = {
            entity_id: ieee
            for ieee, info in self._devices.items()
            for entity_id in info.entities.as_tuple()
        }
        entity_ids = frozenset(self._entity_to_ieee)
        if entity_ids == self._tracked_entity_ids and self._unsub_tracking is not None:
            # Same set of entities to track: no need to churn the
            # subscription (this runs on every periodic refresh).
            return
        self._tracked_entity_ids = entity_ids
        if self._unsub_tracking is not None:
            self._unsub_tracking()
            self._unsub_tracking = None
        if entity_ids and self._on_update is not None:
            self._unsub_tracking = async_track_state_change_event(
                self.hass, list(entity_ids), self._async_state_changed
            )

    @callback
    def _async_state_changed(self, event: Event[EventStateChangedData]) -> None:
        entity_id = event.data["entity_id"]
        ieee = self._entity_to_ieee.get(entity_id)
        if ieee is None or self._on_update is None:
            return
        info = self._devices.get(ieee)
        if info is None:
            return
        self._on_update(ieee, self._collect_device(info))

    def _collect_device(self, info: ZHADeviceInfo) -> dict[str, Any]:
        """Read the current values of one device's tracked entities."""
        metrics: dict[str, Any] = {}
        seen_available = False
        seen_unavailable = False
        last_seen: datetime | None = None
        for entity_id, metric_key in (
            (info.entities.lqi, "link_quality"),
            (info.entities.rssi, "rssi"),
            (info.entities.battery, "battery"),
        ):
            if entity_id is None:
                continue
            state = self.hass.states.get(entity_id)
            if state is None:
                continue
            if state.state == STATE_UNAVAILABLE:
                if state.attributes.get(ATTR_RESTORED):
                    # The stub state Home Assistant writes while an entity
                    # is unloaded (e.g. ZHA reloading after enabling
                    # diagnostics, or any ZHA options change): not a real
                    # "device is offline" signal, so it counts as neither
                    # available nor unavailable.
                    continue
                seen_unavailable = True
                continue
            seen_available = True
            reported = state.last_reported or state.last_updated
            if reported is not None and (last_seen is None or reported > last_seen):
                last_seen = reported
            try:
                metrics[metric_key] = float(state.state)
            except (TypeError, ValueError):
                continue

        available: bool | None
        if seen_available:
            available = True
        elif seen_unavailable:
            available = False
        else:
            available = None

        return {
            "friendly_name": info.name,
            "model": info.model,
            "manufacturer": info.manufacturer,
            "via_device_ieee": info.via_device_ieee,
            "device_type": info.device_type,
            "available": available,
            "last_seen": last_seen,
            "metrics": metrics,
        }

    async def collect_devices(self) -> dict[str, dict[str, Any]]:
        """Return a full snapshot of every known ZHA device.

        Also re-discovers devices/entities from the registries, so newly
        joined (or removed) ZHA devices are picked up (the coordinator
        calls this periodically as well as at start-up). The returned
        ``last_seen`` values are informational only: the coordinator must
        not use them to advance a device's stored ``last_seen`` metric (see
        module docstring) -- only live push updates do that.
        """
        if not self.is_available():
            self._devices = {}
            self._entity_to_ieee = {}
            return {}
        self._async_refresh_tracking()
        return {
            ieee: self._collect_device(info) for ieee, info in self._devices.items()
        }
