"""Binary sensor entities for ZigSight."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from ..const import DOMAIN
from ..coordinator import ZigSightCoordinator


class ZigSightBinarySensor(CoordinatorEntity[ZigSightCoordinator], BinarySensorEntity):
    """Base class for ZigSight binary sensor entities."""

    def __init__(
        self,
        coordinator: ZigSightCoordinator,
        device_id: str,
        sensor_type: str,
    ) -> None:
        """Initialize the binary sensor."""
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
                    }
                )
        return attrs


class ZigSightBatteryDrainWarningBinarySensor(ZigSightBinarySensor):
    """Binary sensor for device battery drain warning."""

    def __init__(
        self,
        coordinator: ZigSightCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the battery drain warning binary sensor."""
        super().__init__(coordinator, device_id, "battery_drain_warning")
        self._attr_icon = "mdi:battery-alert"
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool:
        """Return if battery drain warning is active."""
        return self.coordinator.get_device_battery_drain_warning(self._device_id)


class ZigSightConnectivityWarningBinarySensor(ZigSightBinarySensor):
    """Binary sensor for device connectivity warning."""

    def __init__(
        self,
        coordinator: ZigSightCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the connectivity warning binary sensor."""
        super().__init__(coordinator, device_id, "connectivity_warning")
        self._attr_icon = "mdi:connection"
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def is_on(self) -> bool:
        """Return if connectivity warning is active."""
        return self.coordinator.get_device_connectivity_warning(self._device_id)
