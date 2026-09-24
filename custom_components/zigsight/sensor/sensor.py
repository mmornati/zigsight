"""Sensor entities for ZigSight."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfElectricPotential
from homeassistant.helpers.typing import StateType

from ..coordinator import ZigSightCoordinator
from ..entity import ZigSightDeviceEntity


def _metric(key: str) -> Callable[[ZigSightCoordinator, str], StateType]:
    def _value(coordinator: ZigSightCoordinator, ieee: str) -> StateType:
        metrics = coordinator.get_device_metrics(ieee) or {}
        value = metrics.get(key)
        if isinstance(value, bool) or not isinstance(value, int | float):
            return None
        return value

    return _value


@dataclass(frozen=True, kw_only=True)
class ZigSightSensorEntityDescription(SensorEntityDescription):
    """Describes a ZigSight sensor."""

    value_fn: Callable[[ZigSightCoordinator, str], StateType]
    # Only created for battery powered devices
    battery_only: bool = False


LINK_QUALITY = ZigSightSensorEntityDescription(
    key="link_quality",
    translation_key="link_quality",
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=_metric("link_quality"),
)
BATTERY = ZigSightSensorEntityDescription(
    key="battery",
    translation_key="battery",
    device_class=SensorDeviceClass.BATTERY,
    native_unit_of_measurement=PERCENTAGE,
    state_class=SensorStateClass.MEASUREMENT,
    battery_only=True,
    value_fn=_metric("battery"),
)
VOLTAGE = ZigSightSensorEntityDescription(
    key="voltage",
    translation_key="voltage",
    device_class=SensorDeviceClass.VOLTAGE,
    # Zigbee2MQTT reports battery voltage in mV; the actual unit comes from
    # the device definition (see ZigSightVoltageSensor).
    native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=_metric("voltage"),
)
RECONNECT_RATE = ZigSightSensorEntityDescription(
    key="reconnect_rate",
    translation_key="reconnect_rate",
    native_unit_of_measurement="events/h",
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda coordinator, ieee: coordinator.get_device_reconnect_rate(ieee),
)
BATTERY_TREND = ZigSightSensorEntityDescription(
    key="battery_trend",
    translation_key="battery_trend",
    native_unit_of_measurement="%/h",
    state_class=SensorStateClass.MEASUREMENT,
    battery_only=True,
    value_fn=lambda coordinator, ieee: coordinator.get_device_battery_trend(ieee),
)
HEALTH_SCORE = ZigSightSensorEntityDescription(
    key="health_score",
    translation_key="health_score",
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda coordinator, ieee: coordinator.get_device_health_score(ieee),
)

SENSOR_DESCRIPTIONS: tuple[ZigSightSensorEntityDescription, ...] = (
    LINK_QUALITY,
    BATTERY,
    VOLTAGE,
    RECONNECT_RATE,
    BATTERY_TREND,
    HEALTH_SCORE,
)


class ZigSightSensor(ZigSightDeviceEntity, SensorEntity):
    """A ZigSight per-device sensor."""

    entity_description: ZigSightSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator, self.ieee)


class ZigSightVoltageSensor(ZigSightSensor):
    """Voltage sensor using the unit declared by the device definition."""

    def __init__(
        self,
        coordinator: ZigSightCoordinator,
        ieee: str,
        description: ZigSightSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, ieee, description)
        record = coordinator.get_device(ieee) or {}
        if record.get("voltage_unit") == UnitOfElectricPotential.VOLT:
            self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT


def build_sensors(
    coordinator: ZigSightCoordinator, ieee: str
) -> Iterable[SensorEntity]:
    """Return the sensors to create for one device.

    Battery related sensors are only created for battery powered devices and
    the voltage sensor only for devices exposing a voltage.
    """
    record = coordinator.get_device(ieee) or {}
    battery_powered = bool(record.get("battery_powered"))
    entities: list[SensorEntity] = []
    for description in SENSOR_DESCRIPTIONS:
        if description.battery_only and not battery_powered:
            continue
        if description is VOLTAGE:
            if record.get("has_voltage"):
                entities.append(ZigSightVoltageSensor(coordinator, ieee, description))
            continue
        entities.append(ZigSightSensor(coordinator, ieee, description))
    return entities
