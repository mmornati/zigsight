"""Sensor entities for ZigSight."""

from __future__ import annotations

from typing import Any

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

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs: dict[str, Any] = {}
        device = self.coordinator.get_device(self._device_id)
        if device:
            attrs["device_id"] = self._device_id
            attrs["friendly_name"] = device.get("friendly_name", self._device_id)
            attrs["last_update"] = device.get("last_update")
            # Include analytics metrics in attributes
            analytics = device.get("analytics_metrics", {})
            if analytics:
                attrs.update(
                    {
                        "reconnect_rate": analytics.get("reconnect_rate"),
                        "battery_trend": analytics.get("battery_trend"),
                        "health_score": analytics.get("health_score"),
                        "battery_drain_warning": analytics.get("battery_drain_warning"),
                        "connectivity_warning": analytics.get("connectivity_warning"),
                    }
                )
        return attrs


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
        self._attr_native_unit_of_measurement = "events/hour"
        self._attr_icon = "mdi:connection"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return the reconnect rate."""
        return self.coordinator.get_device_reconnect_rate(self._device_id)


class ZigSightBatteryTrendSensor(ZigbeeDeviceSensor):
    """Sensor for device battery trend."""

    def __init__(
        self,
        coordinator: ZigSightCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the battery trend sensor."""
        super().__init__(coordinator, device_id, "battery_trend")
        self._attr_native_unit_of_measurement = "%/hour"
        self._attr_icon = "mdi:trending-down"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return the battery trend."""
        return self.coordinator.get_device_battery_trend(self._device_id)


class ZigSightHealthScoreSensor(ZigbeeDeviceSensor):
    """Sensor for device health score."""

    def __init__(
        self,
        coordinator: ZigSightCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the health score sensor."""
        super().__init__(coordinator, device_id, "health_score")
        self._attr_native_unit_of_measurement = None
        self._attr_icon = "mdi:heart-pulse"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Return the health score."""
        return self.coordinator.get_device_health_score(self._device_id)
