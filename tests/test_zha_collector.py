"""Test ZHA collector."""

from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest

from custom_components.zigsight.zha_collector import ZHACollector


@pytest.fixture
def mock_hass() -> MagicMock:
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.data = {}
    return hass


@pytest.fixture
def mock_zha_device() -> Mock:
    """Create a mock ZHA device."""
    device = Mock()
    device.name = "Test Device"
    device.last_seen = datetime.now()
    device.lqi = 200
    device.rssi = -50
    device.device_info = {"power_source": "battery"}
    return device


@pytest.mark.asyncio
async def test_zha_collector_construction(mock_hass: MagicMock) -> None:
    """Test that ZHA collector can be constructed."""
    collector = ZHACollector(mock_hass)
    assert collector is not None
    assert collector.hass == mock_hass


@pytest.mark.asyncio
async def test_is_available_no_zha(mock_hass: MagicMock) -> None:
    """Test is_available returns False when ZHA not present."""
    collector = ZHACollector(mock_hass)
    assert collector.is_available() is False


@pytest.mark.asyncio
async def test_is_available_with_zha(mock_hass: MagicMock) -> None:
    """Test is_available returns True when ZHA is present."""
    mock_hass.data["zha"] = {"gateway": MagicMock()}
    collector = ZHACollector(mock_hass)
    assert collector.is_available() is True


@pytest.mark.asyncio
async def test_collect_devices_no_zha(mock_hass: MagicMock) -> None:
    """Test collect_devices returns empty dict when ZHA not available."""
    collector = ZHACollector(mock_hass)
    devices = await collector.collect_devices()
    assert devices == {}


@pytest.mark.asyncio
async def test_collect_devices_no_gateway(mock_hass: MagicMock) -> None:
    """Test collect_devices returns empty dict when gateway not found."""
    mock_hass.data["zha"] = {}
    collector = ZHACollector(mock_hass)
    devices = await collector.collect_devices()
    assert devices == {}


@pytest.mark.asyncio
async def test_collect_devices_with_devices(
    mock_hass: MagicMock, mock_zha_device: Mock
) -> None:
    """Test collect_devices returns device data."""
    # Setup mock gateway with devices
    mock_gateway = MagicMock()
    ieee = "00:11:22:33:44:55:66:77"
    mock_gateway.devices = {ieee: mock_zha_device}
    mock_hass.data["zha"] = {"gateway": mock_gateway}

    # Mock the device and entity registries
    with patch(
        "custom_components.zigsight.zha_collector.dr.async_get"
    ) as mock_dr_get, patch(
        "custom_components.zigsight.zha_collector.er.async_get"
    ) as mock_er_get:
        mock_device_registry = MagicMock()
        mock_device_registry.async_get_device.return_value = None
        mock_dr_get.return_value = mock_device_registry

        mock_entity_registry = MagicMock()
        mock_er_get.return_value = mock_entity_registry

        collector = ZHACollector(mock_hass)
        devices = await collector.collect_devices()

        assert len(devices) == 1
        assert ieee in devices
        device_data = devices[ieee]
        assert device_data["device_id"] == ieee
        assert device_data["friendly_name"] == "Test Device"
        assert "metrics" in device_data
        assert device_data["metrics"]["link_quality"] == 200
        assert device_data["metrics"]["rssi"] == -50


@pytest.mark.asyncio
async def test_collect_device_metrics(
    mock_hass: MagicMock, mock_zha_device: Mock
) -> None:
    """Test _collect_device_metrics extracts correct metrics."""
    with patch(
        "custom_components.zigsight.zha_collector.dr.async_get"
    ) as mock_dr_get, patch(
        "custom_components.zigsight.zha_collector.er.async_get"
    ) as mock_er_get:
        mock_dr_get.return_value = MagicMock()
        mock_er_get.return_value = MagicMock()

        collector = ZHACollector(mock_hass)
        metrics = await collector._collect_device_metrics(mock_zha_device)

        assert "link_quality" in metrics
        assert metrics["link_quality"] == 200
        assert "rssi" in metrics
        assert metrics["rssi"] == -50
        assert "last_seen" in metrics
        assert "power_source" in metrics
        assert metrics["power_source"] == "battery"


@pytest.mark.asyncio
async def test_collect_device_metrics_minimal(mock_hass: MagicMock) -> None:
    """Test _collect_device_metrics with minimal device attributes."""
    device = Mock()
    device.name = "Minimal Device"
    device.last_seen = None
    device.lqi = None
    device.rssi = None
    device.device_info = None

    with patch(
        "custom_components.zigsight.zha_collector.dr.async_get"
    ) as mock_dr_get, patch(
        "custom_components.zigsight.zha_collector.er.async_get"
    ) as mock_er_get:
        mock_dr_get.return_value = MagicMock()
        mock_er_get.return_value = MagicMock()

        collector = ZHACollector(mock_hass)
        metrics = await collector._collect_device_metrics(device)

        assert "last_seen" in metrics
        assert "link_quality" not in metrics
        assert "rssi" not in metrics


@pytest.mark.asyncio
async def test_collect_entity_metrics_no_device(mock_hass: MagicMock) -> None:
    """Test _collect_entity_metrics returns empty when device not found."""
    with patch(
        "custom_components.zigsight.zha_collector.dr.async_get"
    ) as mock_dr_get, patch(
        "custom_components.zigsight.zha_collector.er.async_get"
    ) as mock_er_get:
        mock_device_registry = MagicMock()
        mock_device_registry.async_get_device.return_value = None
        mock_dr_get.return_value = mock_device_registry
        mock_er_get.return_value = MagicMock()

        collector = ZHACollector(mock_hass)
        metrics = await collector._collect_entity_metrics("unknown_ieee")

        assert metrics == {}


@pytest.mark.asyncio
async def test_collect_entity_metrics_with_entities(mock_hass: MagicMock) -> None:
    """Test _collect_entity_metrics reads diagnostic entities."""
    ieee = "00:11:22:33:44:55:66:77"

    # Mock device registry
    mock_device = MagicMock()
    mock_device.id = "device_1"
    mock_device.identifiers = {("zha", ieee)}

    with patch("custom_components.zigsight.zha_collector.dr.async_get") as mock_dr_get:
        mock_registry = MagicMock()
        mock_registry.devices = {"device_1": mock_device}
        mock_dr_get.return_value = mock_registry

        # Mock entity registry
        mock_entity_rssi = MagicMock()
        mock_entity_rssi.entity_id = "sensor.test_device_rssi"
        mock_entity_rssi.domain = "sensor"

        mock_entity_lqi = MagicMock()
        mock_entity_lqi.entity_id = "sensor.test_device_lqi"
        mock_entity_lqi.domain = "sensor"

        mock_entity_battery = MagicMock()
        mock_entity_battery.entity_id = "sensor.test_device_battery"
        mock_entity_battery.domain = "sensor"

        with patch(
            "custom_components.zigsight.zha_collector.er.async_get"
        ) as mock_er_get, patch(
            "custom_components.zigsight.zha_collector.er.async_entries_for_device"
        ) as mock_entries:
            mock_er_get.return_value = MagicMock()
            mock_entries.return_value = [
                mock_entity_rssi,
                mock_entity_lqi,
                mock_entity_battery,
            ]

            # Mock entity states
            mock_state_rssi = MagicMock()
            mock_state_rssi.state = "-45"

            mock_state_lqi = MagicMock()
            mock_state_lqi.state = "180"

            mock_state_battery = MagicMock()
            mock_state_battery.state = "85.5"

            mock_hass.states.get.side_effect = lambda entity_id: {
                "sensor.test_device_rssi": mock_state_rssi,
                "sensor.test_device_lqi": mock_state_lqi,
                "sensor.test_device_battery": mock_state_battery,
            }.get(entity_id)

            collector = ZHACollector(mock_hass)
            collector._device_registry = mock_registry
            metrics = await collector._collect_entity_metrics(ieee)

            assert metrics["rssi"] == -45
            assert metrics["link_quality"] == 180
            assert metrics["battery"] == 85.5


@pytest.mark.asyncio
async def test_collect_devices_handles_errors(mock_hass: MagicMock) -> None:
    """Test collect_devices handles device errors gracefully."""
    from unittest.mock import PropertyMock

    # Setup mock gateway with a device that raises an error
    mock_gateway = MagicMock()
    mock_device = MagicMock()
    mock_device.name = "Error Device"
    # Make accessing lqi raise an exception
    type(mock_device).lqi = PropertyMock(side_effect=Exception("Test error"))

    ieee = "00:11:22:33:44:55:66:77"
    mock_gateway.devices = {ieee: mock_device}
    mock_hass.data["zha"] = {"gateway": mock_gateway}

    collector = ZHACollector(mock_hass)
    devices = await collector.collect_devices()

    # Should still return empty or handle gracefully
    # The exact behavior depends on error handling in _collect_device_data
    assert isinstance(devices, dict)
