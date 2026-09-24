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
    read). ZigSight instead timestamps a device as "seen" whenever any of
    its tracked diagnostic entities changes state, which is a reasonable
    approximation given the entities update on every ZHA poll/report.

    Likewise, neither the device registry nor the diagnostic entities
    expose the Zigbee power source / device type (router vs. end device);
    that only lives on ZHA's private ``Device`` object. ``device_type`` is
    therefore always ``"unknown"`` for ZHA devices; this is documented in
    ``docs/integrations/zha.md``.

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
    when any tracked entity has a non-unavailable state, and unavailable
    when all of them are unavailable. The coordinator (see
    ``ZigSightCoordinator._process_zha_device_update``) only counts a
    reconnect on the ``False`` -> ``True`` transition of that flag -- never
    once per poll/event -- mirroring the availability based reconnect
    counting introduced for Zigbee2MQTT.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_track_state_change_event,
)

_LOGGER = logging.getLogger(__name__)

ZHA_DOMAIN = "zha"

# Translation keys of the diagnostic sensors defined by the `zha` library
# (zha.application.platforms.sensor.RSSISensor / LQISensor).
TRANSLATION_KEY_RSSI = "rssi"
TRANSLATION_KEY_LQI = "lqi"

_UNAVAILABLE = "unavailable"
_IGNORED_STATES = (_UNAVAILABLE, "unknown", None)


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
        for entity in er.async_entries_for_device(
            ent_reg, device.id, include_disabled_entities=True
        ):
            if entity.domain != "sensor":
                continue
            if entities.lqi is None and _matches(entity, TRANSLATION_KEY_LQI, "lqi"):
                entities.lqi = entity.entity_id
            elif entities.rssi is None and _matches(
                entity, TRANSLATION_KEY_RSSI, "rssi"
            ):
                entities.rssi = entity.entity_id
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
        )
    return devices


def async_enable_diagnostic_entities(hass: HomeAssistant) -> list[str]:
    """Enable ZHA LQI/RSSI entities still disabled by their integration default.

    Only entities with ``disabled_by == RegistryEntryDisabler.INTEGRATION``
    are touched; entities a user explicitly disabled
    (``RegistryEntryDisabler.USER``) are left alone. Home Assistant reloads
    the owning (ZHA) config entry automatically after an entity is enabled
    through the registry -- the entity is not created immediately, it
    materialises a few seconds later once the reload completes.
    """
    ent_reg = er.async_get(hass)
    enabled: list[str] = []
    for info in async_discover_devices(hass).values():
        for entity_id in (info.entities.lqi, info.entities.rssi):
            if entity_id is None:
                continue
            entry = ent_reg.async_get(entity_id)
            if (
                entry is None
                or entry.disabled_by is not er.RegistryEntryDisabler.INTEGRATION
            ):
                continue
            ent_reg.async_update_entity(entity_id, disabled_by=None)
            enabled.append(entity_id)
    return enabled


def async_count_disabled_diagnostic_entities(hass: HomeAssistant) -> int:
    """Count LQI/RSSI entities still disabled by the ZHA integration default."""
    ent_reg = er.async_get(hass)
    count = 0
    for info in async_discover_devices(hass).values():
        for entity_id in (info.entities.lqi, info.entities.rssi):
            if entity_id is None:
                continue
            entry = ent_reg.async_get(entity_id)
            if (
                entry is not None
                and entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
            ):
                count += 1
    return count


class ZHACollector:
    """Collect ZigSight device data from the ZHA integration."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the collector."""
        self.hass = hass
        self._devices: dict[str, ZHADeviceInfo] = {}
        self._unsub_tracking: Callable[[], None] | None = None
        self._on_update: Callable[[str, dict[str, Any]], None] | None = None

    def is_available(self) -> bool:
        """Return True if at least one ZHA config entry is loaded."""
        return bool(async_get_zha_config_entries(self.hass))

    @callback
    def async_setup(self, on_update: Callable[[str, dict[str, Any]], None]) -> None:
        """Start tracking ZHA diagnostic entities for live (push) updates."""
        self._on_update = on_update
        self._async_refresh_tracking()

    @callback
    def async_stop(self) -> None:
        """Stop tracking entity state changes."""
        if self._unsub_tracking is not None:
            self._unsub_tracking()
            self._unsub_tracking = None
        self._on_update = None

    @callback
    def _async_refresh_tracking(self) -> None:
        """Re-discover devices/entities and (re)subscribe to their states."""
        self._devices = async_discover_devices(self.hass)
        if self._unsub_tracking is not None:
            self._unsub_tracking()
            self._unsub_tracking = None
        entity_ids = [
            entity_id
            for info in self._devices.values()
            for entity_id in info.entities.as_tuple()
        ]
        if entity_ids and self._on_update is not None:
            self._unsub_tracking = async_track_state_change_event(
                self.hass, entity_ids, self._async_state_changed
            )

    @callback
    def _async_state_changed(self, event: Event[EventStateChangedData]) -> None:
        entity_id = event.data["entity_id"]
        for ieee, info in self._devices.items():
            if entity_id in info.entities.as_tuple():
                if self._on_update is not None:
                    self._on_update(ieee, self._collect_device(info))
                return

    def _collect_device(self, info: ZHADeviceInfo) -> dict[str, Any]:
        """Read the current values of one device's tracked entities."""
        metrics: dict[str, Any] = {}
        available: bool | None = None
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
            if state.state == _UNAVAILABLE:
                if available is None:
                    available = False
                continue
            available = True
            if state.state in _IGNORED_STATES:
                continue
            try:
                metrics[metric_key] = float(state.state)
            except (TypeError, ValueError):
                continue

        return {
            "friendly_name": info.name,
            "model": info.model,
            "manufacturer": info.manufacturer,
            "via_device_ieee": info.via_device_ieee,
            "device_type": info.device_type,
            "available": available,
            "metrics": metrics,
        }

    async def collect_devices(self) -> dict[str, dict[str, Any]]:
        """Return a full snapshot of every known ZHA device.

        Also re-discovers devices/entities from the registries, so newly
        joined ZHA devices are picked up (the coordinator calls this
        periodically as well as at start-up).
        """
        if not self.is_available():
            self._devices = {}
            return {}
        self._async_refresh_tracking()
        return {
            ieee: self._collect_device(info) for ieee, info in self._devices.items()
        }
