"""Test sensor entities."""
import pytest
from unittest.mock import MagicMock

from custom_components.zigsight.coordinator import ZigSightCoordinator
from custom_components.zigsight.sensor.sensor import (
    ZigSightBatterySensor,
    ZigSightLinkQualitySensor,
)


@pytest.fixture
def mock_coordinator() -> MagicMock:
    """Create a mock coordinator."""
    coordinator = MagicMock(spec=ZigSightCoordinator)
    coordinator.data = {}
    return coordinator


def test_link_quality_sensor_name(mock_coordinator: MagicMock) -> None:
    """Test that link quality sensor has a name."""
    sensor = ZigSightLinkQualitySensor(mock_coordinator, "test_device")
    assert sensor.name is not None
    assert "test_device" in sensor.name


def test_link_quality_sensor_unique_id(mock_coordinator: MagicMock) -> None:
    """Test that link quality sensor has a unique_id."""
    sensor = ZigSightLinkQualitySensor(mock_coordinator, "test_device")
    assert sensor.unique_id is not None
    assert sensor.unique_id == "zigsight_test_device_link_quality"


def test_battery_sensor_name(mock_coordinator: MagicMock) -> None:
    """Test that battery sensor has a name."""
    sensor = ZigSightBatterySensor(mock_coordinator, "test_device")
    assert sensor.name is not None
    assert "test_device" in sensor.name


def test_battery_sensor_unique_id(mock_coordinator: MagicMock) -> None:
    """Test that battery sensor has a unique_id."""
    sensor = ZigSightBatterySensor(mock_coordinator, "test_device")
    assert sensor.unique_id is not None
    assert sensor.unique_id == "zigsight_test_device_battery"


def test_battery_sensor_device_class(mock_coordinator: MagicMock) -> None:
    """Test that battery sensor has correct device class."""
    sensor = ZigSightBatterySensor(mock_coordinator, "test_device")
    assert sensor.device_class == "battery"

