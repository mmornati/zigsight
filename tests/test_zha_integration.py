"""Integration test for ZHA support in coordinator."""

from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest

from custom_components.zigsight.coordinator import ZigSightCoordinator


@pytest.fixture
def mock_hass() -> MagicMock:
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.data = {}
    hass.bus = MagicMock()
    hass.bus.async_fire = MagicMock()
    hass.states = MagicMock()
    hass.states.get = MagicMock(return_value=None)
    return hass


@pytest.fixture
def mock_zha_device() -> Mock:
    """Create a mock ZHA device."""
    device = Mock()
    device.name = "Test ZHA Device"
    device.last_seen = datetime.now()
    device.lqi = 180
    device.rssi = -55
    device.device_info = {"power_source": "mains"}
    return device


@pytest.mark.asyncio
async def test_coordinator_with_zha_enabled(
    mock_hass: MagicMock, mock_zha_device: Mock
) -> None:
    """Test coordinator collects ZHA devices when enabled."""
    # Setup ZHA
    mock_gateway = MagicMock()
    ieee = "00:11:22:33:44:55:66:88"
    mock_gateway.devices = {ieee: mock_zha_device}
    mock_hass.data["zha"] = {"gateway": mock_gateway}

    # Mock registries
    with patch(
        "custom_components.zigsight.zha_collector.dr.async_get"
    ) as mock_dr_get, patch(
        "custom_components.zigsight.zha_collector.er.async_get"
    ) as mock_er_get, patch(
        "custom_components.zigsight.coordinator.mqtt.async_wait_for_mqtt_client"
    ) as mock_mqtt:
        mock_device_registry = MagicMock()
        mock_device_registry.async_get_device.return_value = None
        mock_dr_get.return_value = mock_device_registry
        mock_er_get.return_value = MagicMock()
        mock_mqtt.return_value = False

        # Create coordinator with ZHA enabled
        coordinator = ZigSightCoordinator(
            mock_hass,
            enable_zha=True,
        )

        # Trigger update
        data = await coordinator._async_update_data()

        # Verify ZHA device was collected
        assert len(coordinator._devices) == 1
        assert ieee in coordinator._devices
        device = coordinator._devices[ieee]
        assert device["friendly_name"] == "Test ZHA Device"
        assert device["source"] == "zha"
        assert "metrics" in device
        assert device["metrics"]["link_quality"] == 180
        assert device["metrics"]["rssi"] == -55


@pytest.mark.asyncio
async def test_coordinator_with_zha_disabled(mock_hass: MagicMock) -> None:
    """Test coordinator doesn't collect ZHA devices when disabled."""
    # Setup ZHA (but it should be ignored)
    mock_gateway = MagicMock()
    mock_gateway.devices = {"00:11:22:33:44:55:66:99": MagicMock()}
    mock_hass.data["zha"] = {"gateway": mock_gateway}

    with patch(
        "custom_components.zigsight.coordinator.mqtt.async_wait_for_mqtt_client"
    ) as mock_mqtt:
        mock_mqtt.return_value = False

        # Create coordinator with ZHA disabled
        coordinator = ZigSightCoordinator(
            mock_hass,
            enable_zha=False,
        )

        # Trigger update
        data = await coordinator._async_update_data()

        # Verify no ZHA devices collected
        assert len(coordinator._devices) == 0


@pytest.mark.asyncio
async def test_coordinator_zha_updates_analytics(
    mock_hass: MagicMock, mock_zha_device: Mock
) -> None:
    """Test coordinator updates analytics metrics for ZHA devices."""
    # Setup ZHA
    mock_gateway = MagicMock()
    ieee = "00:11:22:33:44:55:66:AA"
    mock_gateway.devices = {ieee: mock_zha_device}
    mock_hass.data["zha"] = {"gateway": mock_gateway}

    with patch(
        "custom_components.zigsight.zha_collector.dr.async_get"
    ) as mock_dr_get, patch(
        "custom_components.zigsight.zha_collector.er.async_get"
    ) as mock_er_get, patch(
        "custom_components.zigsight.coordinator.mqtt.async_wait_for_mqtt_client"
    ) as mock_mqtt:
        mock_device_registry = MagicMock()
        mock_device_registry.async_get_device.return_value = None
        mock_dr_get.return_value = mock_device_registry
        mock_er_get.return_value = MagicMock()
        mock_mqtt.return_value = False

        coordinator = ZigSightCoordinator(
            mock_hass,
            enable_zha=True,
        )

        # Trigger update
        await coordinator._async_update_data()

        # Verify analytics metrics are computed
        device = coordinator._devices[ieee]
        assert "analytics_metrics" in device
        assert "reconnect_rate" in device["analytics_metrics"]
        assert "health_score" in device["analytics_metrics"]


@pytest.mark.asyncio
async def test_coordinator_zha_fires_events(
    mock_hass: MagicMock, mock_zha_device: Mock
) -> None:
    """Test coordinator fires device update events for ZHA devices."""
    # Setup ZHA
    mock_gateway = MagicMock()
    ieee = "00:11:22:33:44:55:66:BB"
    mock_gateway.devices = {ieee: mock_zha_device}
    mock_hass.data["zha"] = {"gateway": mock_gateway}

    with patch(
        "custom_components.zigsight.zha_collector.dr.async_get"
    ) as mock_dr_get, patch(
        "custom_components.zigsight.zha_collector.er.async_get"
    ) as mock_er_get, patch(
        "custom_components.zigsight.coordinator.mqtt.async_wait_for_mqtt_client"
    ) as mock_mqtt:
        mock_device_registry = MagicMock()
        mock_device_registry.async_get_device.return_value = None
        mock_dr_get.return_value = mock_device_registry
        mock_er_get.return_value = MagicMock()
        mock_mqtt.return_value = False

        coordinator = ZigSightCoordinator(
            mock_hass,
            enable_zha=True,
        )

        # Trigger update
        await coordinator._async_update_data()

        # Verify event was fired
        mock_hass.bus.async_fire.assert_called()
        call_args = mock_hass.bus.async_fire.call_args_list
        # Should have fired event for device
        event_names = [call[0][0] for call in call_args]
        assert "zigsight_device_update" in event_names
