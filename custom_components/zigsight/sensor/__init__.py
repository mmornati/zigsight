"""Sensor platform for ZigSight."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ..const import DOMAIN
from ..coordinator import ZigSightCoordinator
from .sensor import (
    ZigSightBatterySensor,
    ZigSightLinkQualitySensor,
    ZigSightReconnectRateSensor,
    ZigSightVoltageSensor,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ZigSight sensor platform."""
    coordinator: ZigSightCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Get devices from coordinator data
    data = coordinator.data
    devices = data.get("devices", {}) if data else {}

    entities = []
    for device_id, device_data in devices.items():
        # Skip bridge device
        if device_id == "bridge":
            continue
        
        # Create sensors for each device
        entities.append(ZigSightLinkQualitySensor(coordinator, device_id))
        entities.append(ZigSightBatterySensor(coordinator, device_id))
        entities.append(ZigSightVoltageSensor(coordinator, device_id))
        entities.append(ZigSightReconnectRateSensor(coordinator, device_id))

    async_add_entities(entities)

    # Note: Dynamic sensor creation will be handled via platform discovery
    # when new devices are detected through MQTT messages
