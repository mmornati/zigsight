"""Binary sensor entities for ZigSight."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

from ..coordinator import ZigSightCoordinator
from ..entity import ZigSightDeviceEntity


@dataclass(frozen=True, kw_only=True)
class ZigSightBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a ZigSight binary sensor."""

    value_fn: Callable[[ZigSightCoordinator, str], bool]
    # Only created for battery powered devices
    battery_only: bool = False


BATTERY_DRAIN_WARNING = ZigSightBinarySensorEntityDescription(
    key="battery_drain_warning",
    translation_key="battery_drain_warning",
    device_class=BinarySensorDeviceClass.PROBLEM,
    battery_only=True,
    value_fn=lambda coordinator, ieee: coordinator.get_device_battery_drain_warning(
        ieee
    ),
)
# This is a *warning*: "on" means there is a connectivity problem, hence the
# PROBLEM device class (CONNECTIVITY would render "on" as "Connected").
CONNECTIVITY_WARNING = ZigSightBinarySensorEntityDescription(
    key="connectivity_warning",
    translation_key="connectivity_warning",
    device_class=BinarySensorDeviceClass.PROBLEM,
    value_fn=lambda coordinator, ieee: coordinator.get_device_connectivity_warning(
        ieee
    ),
)

BINARY_SENSOR_DESCRIPTIONS: tuple[ZigSightBinarySensorEntityDescription, ...] = (
    BATTERY_DRAIN_WARNING,
    CONNECTIVITY_WARNING,
)


class ZigSightBinarySensor(ZigSightDeviceEntity, BinarySensorEntity):
    """A ZigSight per-device binary sensor."""

    entity_description: ZigSightBinarySensorEntityDescription

    @property
    def is_on(self) -> bool:
        """Return True if the warning is active."""
        return self.entity_description.value_fn(self.coordinator, self.ieee)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return slow changing context for the connectivity warning."""
        if self.entity_description.key != CONNECTIVITY_WARNING.key:
            return None
        device = self.coordinator.get_device(self.ieee) or {}
        return {
            "available": device.get("available"),
            "reconnect_count": device.get("reconnect_count", 0),
        }


def build_binary_sensors(
    coordinator: ZigSightCoordinator, ieee: str
) -> Iterable[BinarySensorEntity]:
    """Return the binary sensors to create for one device."""
    record = coordinator.get_device(ieee) or {}
    battery_powered = bool(record.get("battery_powered"))
    return [
        ZigSightBinarySensor(coordinator, ieee, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
        if battery_powered or not description.battery_only
    ]
