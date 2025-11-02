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
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ZigSight sensor platform."""
    # coordinator: ZigSightCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Placeholder: will create actual sensors when coordinator has device data
    # For now, creating example sensors to satisfy the base structure
    entities: list = []
    # coordinator will be used when creating actual sensors
    # entities.append(ZigSightLinkQualitySensor(coordinator, "example_device"))
    # entities.append(ZigSightBatterySensor(coordinator, "example_device"))

    async_add_entities(entities)
