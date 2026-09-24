"""Binary sensor platform for ZigSight."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from ..entity import async_setup_device_platform
from .binary_sensor import build_binary_sensors


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ZigSight binary sensors (now and whenever a new device appears)."""
    async_setup_device_platform(
        hass, entry, async_add_entities, build_binary_sensors, "binary_sensor"
    )
