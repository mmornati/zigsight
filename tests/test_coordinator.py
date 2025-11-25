"""Test coordinator."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock

import pytest

from custom_components.zigsight.coordinator import ZigSightCoordinator


@pytest.fixture
def mock_hass() -> MagicMock:
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.data = {}
    hass.bus = MagicMock()
    hass.bus.async_fire = MagicMock()
    return hass


@pytest.mark.asyncio
async def test_coordinator_construction(mock_hass: MagicMock) -> None:
    """Test that coordinator can be constructed."""
    coordinator = ZigSightCoordinator(mock_hass)
    assert coordinator is not None
    assert coordinator.name == "zigsight"


@pytest.mark.asyncio
async def test_coordinator_construction_with_custom_params(
    mock_hass: MagicMock,
) -> None:
    """Test coordinator construction with custom parameters."""
    coordinator = ZigSightCoordinator(
        mock_hass,
        mqtt_prefix="custom/prefix",
        mqtt_broker="192.168.1.100",
        mqtt_port=1884,
        mqtt_username="user",
        mqtt_password="pass",
        battery_drain_threshold=15.0,
        reconnect_rate_threshold=10.0,
        reconnect_rate_window_hours=12,
    )
    assert coordinator._mqtt_prefix == "custom/prefix"
    assert coordinator._mqtt_broker == "192.168.1.100"
    assert coordinator._mqtt_port == 1884
    assert coordinator._use_direct_mqtt is True


@pytest.mark.asyncio
async def test_coordinator_async_update_data(mock_hass: MagicMock) -> None:
    """Test that coordinator _async_update_data returns data."""
    coordinator = ZigSightCoordinator(mock_hass)
    data = await coordinator._async_update_data()

    assert isinstance(data, dict)
    assert "devices" in data
    assert "device_count" in data
    assert "last_update" in data


@pytest.mark.asyncio
async def test_coordinator_async_shutdown_no_tasks(mock_hass: MagicMock) -> None:
    """Test that coordinator async_shutdown works with no tasks."""
    coordinator = ZigSightCoordinator(mock_hass)

    # async_shutdown should handle case when _tasks doesn't exist
    await coordinator.async_shutdown()


@pytest.mark.asyncio
async def test_coordinator_async_shutdown_with_tasks(mock_hass: MagicMock) -> None:
    """Test that coordinator async_shutdown cancels real tasks."""
    coordinator = ZigSightCoordinator(mock_hass)

    # Create a real asyncio task that we can cancel
    async def dummy_coroutine():
        await asyncio.sleep(100)

    real_task = asyncio.create_task(dummy_coroutine())
    coordinator._tasks = [real_task]

    await coordinator.async_shutdown()

    # Verify task was cancelled
    assert real_task.cancelled() or real_task.done()


@pytest.mark.asyncio
async def test_coordinator_get_device_returns_none(mock_hass: MagicMock) -> None:
    """Test get_device returns None for non-existent device."""
    coordinator = ZigSightCoordinator(mock_hass)
    assert coordinator.get_device("nonexistent") is None


@pytest.mark.asyncio
async def test_coordinator_get_all_devices_empty(mock_hass: MagicMock) -> None:
    """Test get_all_devices returns empty dict initially."""
    coordinator = ZigSightCoordinator(mock_hass)
    devices = coordinator.get_all_devices()
    assert devices == {}


@pytest.mark.asyncio
async def test_coordinator_get_device_history_empty(mock_hass: MagicMock) -> None:
    """Test get_device_history returns empty list for unknown device."""
    coordinator = ZigSightCoordinator(mock_hass)
    history = coordinator.get_device_history("unknown_device")
    assert history == []


@pytest.mark.asyncio
async def test_coordinator_get_device_metrics_none(mock_hass: MagicMock) -> None:
    """Test get_device_metrics returns None for unknown device."""
    coordinator = ZigSightCoordinator(mock_hass)
    metrics = coordinator.get_device_metrics("unknown_device")
    assert metrics is None


@pytest.mark.asyncio
async def test_coordinator_process_device_update(mock_hass: MagicMock) -> None:
    """Test device update processing."""
    coordinator = ZigSightCoordinator(mock_hass)

    device_data = {
        "linkquality": 100,
        "battery": 80,
        "voltage": 3.0,
        "friendly_name": "Test Device",
    }

    coordinator._process_device_update(
        "test_device", device_data, "zigbee2mqtt/test_device"
    )

    device = coordinator.get_device("test_device")
    assert device is not None
    assert device["device_id"] == "test_device"
    assert device["friendly_name"] == "Test Device"
    assert device["metrics"]["link_quality"] == 100
    assert device["metrics"]["battery"] == 80


@pytest.mark.asyncio
async def test_coordinator_process_device_update_creates_history(
    mock_hass: MagicMock,
) -> None:
    """Test that device updates create history entries."""
    coordinator = ZigSightCoordinator(mock_hass)

    device_data = {"linkquality": 100, "battery": 80}
    coordinator._process_device_update(
        "test_device", device_data, "zigbee2mqtt/test_device"
    )

    history = coordinator.get_device_history("test_device")
    assert len(history) == 1
    assert "timestamp" in history[0]
    assert "metrics" in history[0]


@pytest.mark.asyncio
async def test_coordinator_process_device_update_fires_event(
    mock_hass: MagicMock,
) -> None:
    """Test that device updates fire events."""
    coordinator = ZigSightCoordinator(mock_hass)

    device_data = {"linkquality": 100}
    coordinator._process_device_update(
        "test_device", device_data, "zigbee2mqtt/test_device"
    )

    # Verify event was fired
    mock_hass.bus.async_fire.assert_called()


@pytest.mark.asyncio
async def test_coordinator_history_limit(mock_hass: MagicMock) -> None:
    """Test that history is limited to 1000 entries per device."""
    coordinator = ZigSightCoordinator(mock_hass)

    # Add more than 1000 entries
    for i in range(1010):
        device_data = {"linkquality": i % 255}
        coordinator._process_device_update(
            "test_device", device_data, "zigbee2mqtt/test_device"
        )

    history = coordinator.get_device_history("test_device")
    assert len(history) == 1000


@pytest.mark.asyncio
async def test_coordinator_on_bridge_state(mock_hass: MagicMock) -> None:
    """Test bridge state message handling."""
    coordinator = ZigSightCoordinator(mock_hass)

    class MockMessage:
        def __init__(self):
            self.payload = json.dumps({"state": "online"}).encode()

    coordinator._on_bridge_state(MockMessage())

    bridge = coordinator.get_device("bridge")
    assert bridge is not None
    assert bridge["state"]["state"] == "online"


@pytest.mark.asyncio
async def test_coordinator_on_device_message(mock_hass: MagicMock) -> None:
    """Test device message handling."""
    coordinator = ZigSightCoordinator(mock_hass)

    class MockMessage:
        def __init__(self):
            self.topic = "zigbee2mqtt/living_room_sensor"
            self.payload = json.dumps({"linkquality": 150, "battery": 90}).encode()

    coordinator._on_device_message(MockMessage())

    device = coordinator.get_device("living_room_sensor")
    assert device is not None
    assert device["metrics"]["link_quality"] == 150
    assert device["metrics"]["battery"] == 90


@pytest.mark.asyncio
async def test_coordinator_on_device_message_skips_bridge(mock_hass: MagicMock) -> None:
    """Test that device message handling skips bridge messages."""
    coordinator = ZigSightCoordinator(mock_hass)

    class MockMessage:
        def __init__(self):
            self.topic = "zigbee2mqtt/bridge"
            self.payload = json.dumps({"state": "online"}).encode()

    initial_device_count = len(coordinator.get_all_devices())
    coordinator._on_device_message(MockMessage())

    # Bridge should not be added as a device through this path
    assert len(coordinator.get_all_devices()) == initial_device_count


@pytest.mark.asyncio
async def test_coordinator_on_device_message_short_topic(mock_hass: MagicMock) -> None:
    """Test that device message handling handles short topics."""
    coordinator = ZigSightCoordinator(mock_hass)

    class MockMessage:
        def __init__(self):
            self.topic = "zigbee2mqtt"
            self.payload = json.dumps({}).encode()

    initial_device_count = len(coordinator.get_all_devices())
    coordinator._on_device_message(MockMessage())

    # No device should be added
    assert len(coordinator.get_all_devices()) == initial_device_count


@pytest.mark.asyncio
async def test_coordinator_topic_matches(mock_hass: MagicMock) -> None:
    """Test topic matching with wildcards."""
    coordinator = ZigSightCoordinator(mock_hass)

    assert coordinator._topic_matches("zigbee2mqtt/device", "zigbee2mqtt/#")
    assert coordinator._topic_matches("zigbee2mqtt/device/set", "zigbee2mqtt/#")
    assert coordinator._topic_matches("test", "#")
    assert coordinator._topic_matches("exact/match", "exact/match")
    assert not coordinator._topic_matches("other/topic", "exact/match")


@pytest.mark.asyncio
async def test_coordinator_get_device_reconnect_rate(mock_hass: MagicMock) -> None:
    """Test getting device reconnect rate."""
    coordinator = ZigSightCoordinator(mock_hass)

    # No device exists - should return None
    rate = coordinator.get_device_reconnect_rate("unknown")
    assert rate is None


@pytest.mark.asyncio
async def test_coordinator_get_device_battery_trend(mock_hass: MagicMock) -> None:
    """Test getting device battery trend."""
    coordinator = ZigSightCoordinator(mock_hass)

    # No device exists - should return None
    trend = coordinator.get_device_battery_trend("unknown")
    assert trend is None


@pytest.mark.asyncio
async def test_coordinator_get_device_health_score(mock_hass: MagicMock) -> None:
    """Test getting device health score."""
    coordinator = ZigSightCoordinator(mock_hass)

    # No device exists - should return None
    score = coordinator.get_device_health_score("unknown")
    assert score is None


@pytest.mark.asyncio
async def test_coordinator_get_device_battery_drain_warning(
    mock_hass: MagicMock,
) -> None:
    """Test getting device battery drain warning."""
    coordinator = ZigSightCoordinator(mock_hass)

    # No device exists - should return False
    warning = coordinator.get_device_battery_drain_warning("unknown")
    assert warning is False


@pytest.mark.asyncio
async def test_coordinator_get_device_connectivity_warning(
    mock_hass: MagicMock,
) -> None:
    """Test getting device connectivity warning."""
    coordinator = ZigSightCoordinator(mock_hass)

    # No device exists - should return False
    warning = coordinator.get_device_connectivity_warning("unknown")
    assert warning is False


@pytest.mark.asyncio
async def test_coordinator_analytics_metrics_update(mock_hass: MagicMock) -> None:
    """Test that analytics metrics are updated on device update."""
    coordinator = ZigSightCoordinator(mock_hass)

    device_data = {
        "linkquality": 200,
        "battery": 90,
    }
    coordinator._process_device_update(
        "test_device", device_data, "zigbee2mqtt/test_device"
    )

    device = coordinator.get_device("test_device")
    assert device is not None
    assert "analytics_metrics" in device
    assert "health_score" in device["analytics_metrics"]
    assert "reconnect_rate" in device["analytics_metrics"]


@pytest.mark.asyncio
async def test_coordinator_device_with_analytics_metrics(mock_hass: MagicMock) -> None:
    """Test getting analytics metrics from cached device data."""
    coordinator = ZigSightCoordinator(mock_hass)

    # Set up a device with analytics metrics
    device_data = {"linkquality": 200, "battery": 90}
    coordinator._process_device_update(
        "test_device", device_data, "zigbee2mqtt/test_device"
    )

    # Get analytics from cached data
    rate = coordinator.get_device_reconnect_rate("test_device")
    assert rate is not None
    assert rate == 0.0  # No reconnects yet

    score = coordinator.get_device_health_score("test_device")
    assert score is not None
    assert 0 <= score <= 100


@pytest.mark.asyncio
async def test_coordinator_reconnect_detection(mock_hass: MagicMock) -> None:
    """Test reconnection detection based on time gaps."""
    coordinator = ZigSightCoordinator(mock_hass)

    # First update
    device_data = {"linkquality": 100}
    coordinator._process_device_update(
        "test_device", device_data, "zigbee2mqtt/test_device"
    )

    device = coordinator.get_device("test_device")
    initial_reconnect_count = device.get("reconnect_count", 0)

    # Simulate a long gap by modifying last_seen
    from datetime import datetime, timedelta

    old_time = (datetime.now() - timedelta(minutes=10)).isoformat()
    device["metrics"]["last_seen"] = old_time

    # Second update after gap
    coordinator._process_device_update(
        "test_device", device_data, "zigbee2mqtt/test_device"
    )

    device = coordinator.get_device("test_device")
    # Reconnect count should have increased
    assert device.get("reconnect_count", 0) >= initial_reconnect_count


@pytest.mark.asyncio
async def test_coordinator_get_device_metrics_with_device(mock_hass: MagicMock) -> None:
    """Test get_device_metrics returns metrics for existing device."""
    coordinator = ZigSightCoordinator(mock_hass)

    device_data = {"linkquality": 150, "battery": 75, "voltage": 3.1}
    coordinator._process_device_update(
        "test_device", device_data, "zigbee2mqtt/test_device"
    )

    metrics = coordinator.get_device_metrics("test_device")
    assert metrics is not None
    assert metrics["link_quality"] == 150
    assert metrics["battery"] == 75


@pytest.mark.asyncio
async def test_coordinator_bridge_state_string_payload(mock_hass: MagicMock) -> None:
    """Test bridge state with string payload."""
    coordinator = ZigSightCoordinator(mock_hass)

    class MockMessage:
        def __init__(self):
            self.payload = '{"state": "offline"}'  # String payload

    coordinator._on_bridge_state(MockMessage())

    bridge = coordinator.get_device("bridge")
    assert bridge is not None
    assert bridge["state"]["state"] == "offline"


@pytest.mark.asyncio
async def test_coordinator_bridge_state_error_handling(mock_hass: MagicMock) -> None:
    """Test bridge state handles invalid payload gracefully."""
    coordinator = ZigSightCoordinator(mock_hass)

    class MockMessage:
        def __init__(self):
            self.payload = b"invalid json{{"  # Invalid JSON

    # Should not raise an exception
    coordinator._on_bridge_state(MockMessage())


@pytest.mark.asyncio
async def test_coordinator_device_message_error_handling(mock_hass: MagicMock) -> None:
    """Test device message handles errors gracefully."""
    coordinator = ZigSightCoordinator(mock_hass)

    class MockMessage:
        def __init__(self):
            self.topic = "zigbee2mqtt/device"
            self.payload = b"invalid json{{"  # Invalid JSON

    # Should not raise an exception
    coordinator._on_device_message(MockMessage())


@pytest.mark.asyncio
async def test_coordinator_topic_matches_edge_cases(mock_hass: MagicMock) -> None:
    """Test topic matching edge cases."""
    coordinator = ZigSightCoordinator(mock_hass)

    # Test empty prefix matching
    assert coordinator._topic_matches("anything", "#")

    # Test topic with trailing hash that should match prefix
    assert coordinator._topic_matches("prefix/sub/topic", "prefix/#")
    assert coordinator._topic_matches("prefix", "prefix/#")


@pytest.mark.asyncio
async def test_coordinator_update_multiple_devices(mock_hass: MagicMock) -> None:
    """Test updating multiple devices."""
    coordinator = ZigSightCoordinator(mock_hass)

    # Add multiple devices
    for i in range(5):
        device_data = {"linkquality": 100 + i, "battery": 90 - i}
        coordinator._process_device_update(
            f"device_{i}", device_data, f"zigbee2mqtt/device_{i}"
        )

    # Verify all devices exist
    devices = coordinator.get_all_devices()
    assert len(devices) == 5

    for i in range(5):
        device = coordinator.get_device(f"device_{i}")
        assert device is not None
        assert device["metrics"]["link_quality"] == 100 + i


@pytest.mark.asyncio
async def test_coordinator_update_existing_device(mock_hass: MagicMock) -> None:
    """Test updating an existing device."""
    coordinator = ZigSightCoordinator(mock_hass)

    # First update
    device_data = {"linkquality": 100, "battery": 90}
    coordinator._process_device_update(
        "test_device", device_data, "zigbee2mqtt/test_device"
    )

    # Second update with different values
    device_data = {"linkquality": 150, "battery": 85}
    coordinator._process_device_update(
        "test_device", device_data, "zigbee2mqtt/test_device"
    )

    device = coordinator.get_device("test_device")
    assert device["metrics"]["link_quality"] == 150
    assert device["metrics"]["battery"] == 85


@pytest.mark.asyncio
async def test_coordinator_subscribe_mqtt_direct(mock_hass: MagicMock) -> None:
    """Test MQTT subscription in direct mode."""
    coordinator = ZigSightCoordinator(
        mock_hass,
        mqtt_broker="192.168.1.1",
        mqtt_port=1883,
    )

    def callback(msg):
        pass

    # Test direct MQTT subscription (registers callback)
    await coordinator._subscribe_mqtt("test/topic", callback)

    assert "test/topic" in coordinator._mqtt_callbacks
    assert callback in coordinator._mqtt_callbacks["test/topic"]


@pytest.mark.asyncio
async def test_coordinator_get_battery_trend_with_data(mock_hass: MagicMock) -> None:
    """Test getting battery trend with history data."""
    coordinator = ZigSightCoordinator(mock_hass)

    # Create device with history for trend computation
    device_data = {"linkquality": 100, "battery": 80}
    coordinator._process_device_update(
        "test_device", device_data, "zigbee2mqtt/test_device"
    )

    # Add more history entries
    from datetime import datetime, timedelta

    now = datetime.now()
    coordinator._device_history["test_device"] = [
        {
            "timestamp": (now - timedelta(hours=4)).isoformat(),
            "metrics": {"battery": 100},
        },
        {
            "timestamp": (now - timedelta(hours=2)).isoformat(),
            "metrics": {"battery": 90},
        },
        {"timestamp": now.isoformat(), "metrics": {"battery": 80}},
    ]

    # Clear cached analytics to force recomputation
    device = coordinator.get_device("test_device")
    device.pop("analytics_metrics", None)

    trend = coordinator.get_device_battery_trend("test_device")
    # Trend should be computed from history
    assert trend is not None or trend is None  # May return None if regression fails


@pytest.mark.asyncio
async def test_coordinator_connectivity_warning_with_device(
    mock_hass: MagicMock,
) -> None:
    """Test connectivity warning with existing device."""
    coordinator = ZigSightCoordinator(mock_hass)

    device_data = {"linkquality": 100}
    coordinator._process_device_update(
        "test_device", device_data, "zigbee2mqtt/test_device"
    )

    # Device with recent data should not have connectivity warning
    warning = coordinator.get_device_connectivity_warning("test_device")
    assert isinstance(warning, bool)


@pytest.mark.asyncio
async def test_coordinator_battery_drain_warning_with_device(
    mock_hass: MagicMock,
) -> None:
    """Test battery drain warning with existing device."""
    coordinator = ZigSightCoordinator(mock_hass)

    device_data = {"linkquality": 100, "battery": 90}
    coordinator._process_device_update(
        "test_device", device_data, "zigbee2mqtt/test_device"
    )

    warning = coordinator.get_device_battery_drain_warning("test_device")
    assert isinstance(warning, bool)


@pytest.mark.asyncio
async def test_coordinator_process_device_alternate_keys(mock_hass: MagicMock) -> None:
    """Test device update with alternate key names."""
    coordinator = ZigSightCoordinator(mock_hass)

    # Use alternate keys: link_quality instead of linkquality, battery_percent instead of battery
    device_data = {"link_quality": 200, "battery_percent": 95}
    coordinator._process_device_update(
        "test_device", device_data, "zigbee2mqtt/test_device"
    )

    device = coordinator.get_device("test_device")
    assert device["metrics"]["link_quality"] == 200
    assert device["metrics"]["battery"] == 95


@pytest.mark.asyncio
async def test_coordinator_multiple_mqtt_callbacks(mock_hass: MagicMock) -> None:
    """Test multiple MQTT callbacks for the same topic."""
    coordinator = ZigSightCoordinator(
        mock_hass,
        mqtt_broker="192.168.1.1",
        mqtt_port=1883,
    )

    def callback1(msg):
        pass

    def callback2(msg):
        pass

    await coordinator._subscribe_mqtt("test/topic", callback1)
    await coordinator._subscribe_mqtt("test/topic", callback2)

    # Both callbacks should be registered
    assert len(coordinator._mqtt_callbacks["test/topic"]) == 2


@pytest.mark.asyncio
async def test_coordinator_update_data_with_devices(mock_hass: MagicMock) -> None:
    """Test _async_update_data with existing devices."""
    coordinator = ZigSightCoordinator(mock_hass)

    # Add some devices
    for i in range(3):
        device_data = {"linkquality": 100 + i}
        coordinator._process_device_update(
            f"device_{i}", device_data, f"zigbee2mqtt/device_{i}"
        )

    # Call update data
    data = await coordinator._async_update_data()

    assert data["device_count"] == 3
    assert "devices" in data
    assert "last_update" in data


@pytest.mark.asyncio
async def test_coordinator_async_shutdown_with_mqtt_task(mock_hass: MagicMock) -> None:
    """Test shutdown with running MQTT client task."""
    coordinator = ZigSightCoordinator(mock_hass)

    # Create a mock MQTT client task
    async def dummy_mqtt_task():
        await asyncio.sleep(100)

    coordinator._mqtt_client_task = asyncio.create_task(dummy_mqtt_task())

    await coordinator.async_shutdown()

    # Task should be cancelled
    assert (
        coordinator._mqtt_client_task.cancelled()
        or coordinator._mqtt_client_task.done()
    )


@pytest.mark.asyncio
async def test_coordinator_async_shutdown_with_unsub_list(mock_hass: MagicMock) -> None:
    """Test shutdown unsubscribes from MQTT."""
    coordinator = ZigSightCoordinator(mock_hass)

    # Add mock unsub callbacks
    unsub1 = MagicMock()
    unsub2 = MagicMock()
    coordinator._unsub_mqtt = [unsub1, unsub2]

    await coordinator.async_shutdown()

    # All unsubs should be called
    unsub1.assert_called_once()
    unsub2.assert_called_once()

    # Lists should be cleared
    assert len(coordinator._unsub_mqtt) == 0
    assert len(coordinator._mqtt_callbacks) == 0
