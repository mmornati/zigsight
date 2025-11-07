"""Binary sensor platform for ZigSight."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import DOMAIN
from ..coordinator import ZigSightCoordinator
from .binary_sensor import (
    ZigSightBatteryDrainWarningBinarySensor,
    ZigSightConnectivityWarningBinarySensor,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ZigSight binary sensor platform."""
    coordinator: ZigSightCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Get devices from coordinator data
    data = coordinator.data
    devices = data.get("devices", {}) if data else {}

    entities = []
    for device_id in devices:
        # Skip bridge device
        if device_id == "bridge":
            continue

        # Create binary sensors for each device
        entities.append(ZigSightBatteryDrainWarningBinarySensor(coordinator, device_id))
        entities.append(ZigSightConnectivityWarningBinarySensor(coordinator, device_id))

    async_add_entities(entities)

    # Note: Dynamic binary sensor creation will be handled via platform discovery
    # when new devices are detected through MQTT messages
