"""Unit tests for the entity descriptions / builders."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from homeassistant.const import UnitOfElectricPotential
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.util import dt as dt_util

from custom_components.zigsight.binary_sensor.binary_sensor import (
    ZigSightBinarySensor,
    build_binary_sensors,
)
from custom_components.zigsight.const import DOMAIN
from custom_components.zigsight.coordinator import ZigSightCoordinator
from custom_components.zigsight.sensor.sensor import (
    ZigSightSensor,
    ZigSightVoltageSensor,
    build_sensors,
)

IEEE = "0x00158d0001a2b3c4"


@pytest.fixture
def coordinator() -> ZigSightCoordinator:
    """Coordinator with a mocked hass (no MQTT)."""
    hass = MagicMock()
    hass.data = {}
    return ZigSightCoordinator(hass)


def _add(coordinator: ZigSightCoordinator, **fields: Any) -> dict[str, Any]:
    record = coordinator._new_record(
        IEEE, "zigbee2mqtt", "Bedroom Climate", dt_util.utcnow()
    )
    record.update(fields)
    coordinator._devices[IEEE] = record
    return record


def test_mains_device_gets_no_battery_entities(
    coordinator: ZigSightCoordinator,
) -> None:
    """Routers only get link quality, reconnect rate and health score."""
    _add(coordinator, type="Router")
    keys = {
        sensor.entity_description.key for sensor in build_sensors(coordinator, IEEE)
    }
    assert keys == {"link_quality", "reconnect_rate", "health_score"}
    binary = {
        sensor.entity_description.key
        for sensor in build_binary_sensors(coordinator, IEEE)
    }
    assert binary == {"connectivity_warning"}


def test_battery_device_entities_and_ids(coordinator: ZigSightCoordinator) -> None:
    """Battery devices get battery entities; ids are IEEE based."""
    _add(coordinator, battery_powered=True, has_voltage=True, voltage_unit="mV")
    sensors = list(build_sensors(coordinator, IEEE))
    assert {sensor.unique_id for sensor in sensors} == {
        f"{IEEE}_link_quality",
        f"{IEEE}_battery",
        f"{IEEE}_voltage",
        f"{IEEE}_reconnect_rate",
        f"{IEEE}_battery_trend",
        f"{IEEE}_health_score",
    }
    for sensor in sensors:
        assert sensor.has_entity_name
        assert sensor.translation_key == sensor.entity_description.key
        assert isinstance(sensor, ZigSightSensor)
    voltage = next(s for s in sensors if isinstance(s, ZigSightVoltageSensor))
    assert voltage.native_unit_of_measurement == UnitOfElectricPotential.MILLIVOLT
    assert len(list(build_binary_sensors(coordinator, IEEE))) == 2


def test_voltage_unit_from_definition(coordinator: ZigSightCoordinator) -> None:
    """Devices exposing voltage in V keep V."""
    _add(coordinator, has_voltage=True, voltage_unit="V")
    voltage = next(
        s
        for s in build_sensors(coordinator, IEEE)
        if isinstance(s, ZigSightVoltageSensor)
    )
    assert voltage.native_unit_of_measurement == UnitOfElectricPotential.VOLT


def test_device_info(coordinator: ZigSightCoordinator) -> None:
    """DeviceInfo uses the IEEE identifier and the bridge as via device."""
    _add(coordinator, manufacturer="Aqara", model="Sensor", model_id="WSDCGQ11LM")
    sensor = next(iter(build_sensors(coordinator, IEEE)))
    info = sensor.device_info
    assert info == DeviceInfo(
        identifiers={(DOMAIN, IEEE)},
        name="Bedroom Climate",
        manufacturer="Aqara",
        model="Sensor",
        model_id="WSDCGQ11LM",
        sw_version=None,
        via_device=(DOMAIN, f"{DOMAIN}_bridge"),
    )
    assert info["via_device"] != (DOMAIN, IEEE)


def test_values(coordinator: ZigSightCoordinator) -> None:
    """Values come from merged metrics; non numeric values are ignored."""
    record = _add(coordinator, battery_powered=True, has_voltage=True)
    record["metrics"].update({"link_quality": 120, "battery": "bad", "voltage": True})
    by_key = {s.entity_description.key: s for s in build_sensors(coordinator, IEEE)}
    assert by_key["link_quality"].native_value == 120
    assert by_key["battery"].native_value is None
    assert by_key["voltage"].native_value is None
    assert by_key["reconnect_rate"].native_value == 0.0
    assert by_key["battery_trend"].native_value is None
    assert isinstance(by_key["health_score"].native_value, float)


def test_binary_sensor_values_and_attributes(coordinator: ZigSightCoordinator) -> None:
    """Connectivity warning exposes slow changing attributes only."""
    record = _add(coordinator, battery_powered=True, type="EndDevice")
    record["available"] = False
    record["reconnect_count"] = 3
    sensors = {
        s.entity_description.key: s for s in build_binary_sensors(coordinator, IEEE)
    }
    connectivity = sensors["connectivity_warning"]
    assert isinstance(connectivity, ZigSightBinarySensor)
    assert connectivity.is_on is True
    assert connectivity.extra_state_attributes == {
        "available": False,
        "reconnect_count": 3,
    }
    drain = sensors["battery_drain_warning"]
    assert drain.is_on is False
    assert drain.extra_state_attributes is None


def test_unknown_device(coordinator: ZigSightCoordinator) -> None:
    """Accessors are safe for unknown devices."""
    assert coordinator.get_device_reconnect_rate("nope") is None
    assert coordinator.get_device_health_score("nope") is None
    assert coordinator.get_device_battery_drain_warning("nope") is False
    assert coordinator.get_device_connectivity_warning("nope") is False
    assert not coordinator.wants_entities("nope")
