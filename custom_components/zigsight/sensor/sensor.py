"""Sensor entities for ZigSight."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
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
        
        device_data = coordinator.get_device(device_id) or {}
        friendly_name = device_data.get("friendly_name", device_id)
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=friendly_name,
            manufacturer="ZigSight",
            via_device=(DOMAIN, device_id),
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        device = self.coordinator.get_device(self._device_id)
        return device is not None


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
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        """Return the link quality value."""
        metrics = self.coordinator.get_device_metrics(self._device_id)
        if metrics:
            link_quality = metrics.get("link_quality")
            if link_quality is not None:
                try:
                    return int(link_quality)
                except (ValueError, TypeError):
                    pass
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
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        """Return the battery level."""
        metrics = self.coordinator.get_device_metrics(self._device_id)
        if metrics:
            battery = metrics.get("battery")
            if battery is not None:
                try:
                    return int(battery)
                except (ValueError, TypeError):
                    pass
        return None


class ZigSightVoltageSensor(ZigbeeDeviceSensor):
    """Sensor for device voltage."""

    def __init__(
        self,
        coordinator: ZigSightCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the voltage sensor."""
        super().__init__(coordinator, device_id, "voltage")
        self._attr_native_unit_of_measurement = "V"
        self._attr_device_class = "voltage"
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return the voltage value."""
        metrics = self.coordinator.get_device_metrics(self._device_id)
        if metrics:
            voltage = metrics.get("voltage")
            if voltage is not None:
                try:
                    return float(voltage)
                except (ValueError, TypeError):
                    pass
        return None


class ZigSightReconnectRateSensor(ZigbeeDeviceSensor):
    """Sensor for device reconnect rate."""

    def __init__(
        self,
        coordinator: ZigSightCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the reconnect rate sensor."""
        super().__init__(coordinator, device_id, "reconnect_rate")
        self._attr_native_unit_of_measurement = "reconnects"
        self._attr_icon = "mdi:connection"
        self._attr_state_class = SensorStateClass.TOTAL

    @property
    def native_value(self) -> int | None:
        """Return the reconnect count."""
        device = self.coordinator.get_device(self._device_id)
        if device:
            return device.get("reconnect_count", 0)
        return None
