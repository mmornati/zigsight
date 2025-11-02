"""Sensor entities for ZigSight."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..const import DOMAIN
from ..coordinator import ZigSightCoordinator


class ZigbeeDeviceSensor(CoordinatorEntity[ZigSightCoordinator], SensorEntity):
    """Base class for ZigSight sensor entities."""

    def __init__(
        self,
        coordinator: ZigSightCoordinator,
        device_id: str,
        sensor_type: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._sensor_type = sensor_type
        self._attr_name = f"{device_id} {sensor_type}"
        self._attr_unique_id = f"{DOMAIN}_{device_id}_{sensor_type}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device_id,
            manufacturer="ZigSight",
        )

    @property
    def native_value(self) -> str | int | float | None:
        """Return the native value of the sensor."""
        # Placeholder: will return actual value when coordinator has data
        return None


class ZigSightLinkQualitySensor(ZigbeeDeviceSensor):
    """Sensor for device link quality."""

    def __init__(
        self,
        coordinator: ZigSightCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the link quality sensor."""
        super().__init__(coordinator, device_id, "link_quality")
        self._attr_native_unit_of_measurement = None
        self._attr_icon = "mdi:signal"

    @property
    def native_value(self) -> int | None:
        """Return the link quality value."""
        # Placeholder: will be implemented when coordinator has data
        return None


class ZigSightBatterySensor(ZigbeeDeviceSensor):
    """Sensor for device battery level."""

    def __init__(
        self,
        coordinator: ZigSightCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the battery sensor."""
        super().__init__(coordinator, device_id, "battery")
        self._attr_native_unit_of_measurement = "%"
        self._attr_device_class = "battery"
        self._attr_icon = "mdi:battery"

    @property
    def native_value(self) -> int | None:
        """Return the battery level."""
        # Placeholder: will be implemented when coordinator has data
        return None
