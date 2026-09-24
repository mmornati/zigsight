"""Unit tests for ZigSightCoordinator internals (mocked hass).

End-to-end MQTT behaviour is covered by test_z2m_integration.py.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest
from homeassistant.util import dt as dt_util

from custom_components.zigsight.const import (
    DEVICE_SOURCE_ZHA,
    DEVICE_SOURCE_ZIGBEE2MQTT,
    DOMAIN,
)
from custom_components.zigsight.coordinator import (
    PENDING_MESSAGES_MAX,
    ZigSightCoordinator,
    _legacy_z2m_ids,
)

NOW = datetime(2026, 9, 24, 8, 20, tzinfo=dt_util.UTC)


@pytest.fixture
def mock_hass() -> MagicMock:
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.data = {}
    hass.bus = MagicMock()
    hass.bus.async_fire = MagicMock()
    return hass


def _record(
    coordinator: ZigSightCoordinator, ieee: str, name: str, source: str = "zigbee2mqtt"
) -> dict[str, Any]:
    record = coordinator._new_record(ieee, source, name, NOW)
    coordinator._devices[ieee] = record
    return record


def test_construction_defaults(mock_hass: MagicMock) -> None:
    """Defaults, identifiers and signals."""
    coordinator = ZigSightCoordinator(mock_hass, mqtt_prefix="custom/prefix/")
    assert coordinator.name == DOMAIN
    assert coordinator.mqtt_prefix == "custom/prefix"
    assert coordinator.source == DEVICE_SOURCE_ZIGBEE2MQTT
    assert coordinator.bridge_identifier == (DOMAIN, f"{DOMAIN}_bridge")
    assert coordinator.coordinator_ieee is None
    assert coordinator.get_network_info() is None
    assert coordinator.get_network_links() == []
    assert coordinator.get_bridge_devices() == []
    assert coordinator.device_signal("0x1") != coordinator.device_signal("0x2")
    assert coordinator.signal_new_device != coordinator.signal_device_removed
    assert ZigSightCoordinator(mock_hass, enable_zha=True).source == DEVICE_SOURCE_ZHA


def test_signals_are_per_entry(mock_hass: MagicMock) -> None:
    """Signals include the config entry id."""
    entry = MagicMock()
    entry.entry_id = "abc"
    coordinator = ZigSightCoordinator(mock_hass, config_entry=entry)
    assert "abc" in coordinator.signal_new_device
    assert "abc" in coordinator.device_signal("0x1")
    assert coordinator.bridge_identifier == (DOMAIN, "abc_bridge")


async def test_update_data_shape(mock_hass: MagicMock) -> None:
    """The periodic refresh returns the live device map and recomputes analytics."""
    coordinator = ZigSightCoordinator(mock_hass)
    record = _record(coordinator, "0x1", "Plug")
    data = await coordinator._async_update_data()
    assert data["devices"] is coordinator._devices
    assert data["device_count"] == 1
    assert data["bridge_state"] is None
    assert data["network"] is None
    assert set(record["analytics_metrics"]) == {
        "reconnect_rate",
        "battery_trend",
        "health_score",
        "battery_drain_warning",
        "connectivity_warning",
    }


async def test_async_shutdown_is_idempotent(mock_hass: MagicMock) -> None:
    """Shutdown releases subscriptions once and can be called again."""
    coordinator = ZigSightCoordinator(mock_hass)
    unsub = MagicMock()
    coordinator._unsub_mqtt.append(unsub)
    keepalive = MagicMock()
    coordinator._unsub_keepalive = keepalive
    await coordinator.async_shutdown()
    await coordinator.async_shutdown()
    unsub.assert_called_once()
    keepalive.assert_called_once()


async def test_request_network_map_in_zha_mode(mock_hass: MagicMock) -> None:
    """ZHA mode has no Zigbee2MQTT network map."""
    coordinator = ZigSightCoordinator(mock_hass, enable_zha=True)
    assert await coordinator.async_request_network_map() is False


def test_pending_buffer_is_bounded(mock_hass: MagicMock) -> None:
    """Unknown names (e.g. groups) can't grow memory unbounded."""
    coordinator = ZigSightCoordinator(mock_hass)
    for index in range(PENDING_MESSAGES_MAX + 50):
        coordinator._buffer_pending(f"group {index}", "", "{}", NOW)
    assert len(coordinator._pending) == PENDING_MESSAGES_MAX
    # Existing keys are still updated when full
    coordinator._buffer_pending("group 0", "", '{"state":"ON"}', NOW)
    assert coordinator._pending[("group 0", "")][0] == '{"state":"ON"}'


def test_legacy_ids() -> None:
    """Legacy ids were the first topic segment."""
    assert _legacy_z2m_ids("Kitchen") == ("Kitchen", True)
    assert _legacy_z2m_ids("Kitchen/Motion Sensor") == ("Kitchen", False)


def test_legacy_id_map(mock_hass: MagicMock) -> None:
    """Exact names win; ambiguous truncated names are not migrated."""
    coordinator = ZigSightCoordinator(mock_hass)
    _record(coordinator, "0xplug", "Kitchen")
    _record(coordinator, "0xmotion", "Kitchen/Motion Sensor")
    _record(coordinator, "0xhall1", "Hall/Sensor 1")
    _record(coordinator, "0xhall2", "Hall/Sensor 2")
    _record(coordinator, "0xbath", "Bath/Sensor")
    _record(coordinator, "00:11:22:33:44:55:66:77", "ZHA plug", DEVICE_SOURCE_ZHA)
    mapping = coordinator._legacy_id_map(coordinator.device_ids())
    assert mapping == {
        "Kitchen": "0xplug",
        "Bath": "0xbath",
        "00:11:22:33:44:55:66:77": "00:11:22:33:44:55:66:77",
    }
    assert coordinator._legacy_id_map(["0xbath"]) == {"Bath": "0xbath"}


def test_history_rate_limit(mock_hass: MagicMock) -> None:
    """History points are rate limited; battery changes are kept sooner."""
    coordinator = ZigSightCoordinator(mock_hass)
    record = _record(coordinator, "0x1", "Sensor")
    record["metrics"].update({"battery": 90, "link_quality": 100})
    coordinator._record_history("0x1", NOW, {"link_quality": 100})
    coordinator._record_history("0x1", NOW + timedelta(minutes=1), {"link_quality": 99})
    assert len(coordinator.get_device_history("0x1")) == 1
    record["metrics"]["battery"] = 89
    coordinator._record_history(
        "0x1", NOW + timedelta(minutes=2), {"battery": 89, "link_quality": 99}
    )
    assert len(coordinator.get_device_history("0x1")) == 2
    coordinator._record_history("0x1", NOW + timedelta(minutes=8), {"link_quality": 1})
    history = coordinator.get_device_history("0x1")
    assert len(history) == 3
    assert history[1] == {
        "timestamp": (NOW + timedelta(minutes=2)).isoformat(),
        "metrics": {"link_quality": 100, "battery": 89, "voltage": None},
    }
    # Nothing recorded when the message has no tracked metric
    coordinator._record_history("0x1", NOW + timedelta(hours=1), {})
    assert len(coordinator.get_device_history("0x1")) == 3


def test_analytics_computed_on_demand(mock_hass: MagicMock) -> None:
    """Accessors compute analytics when they are not cached yet."""
    coordinator = ZigSightCoordinator(mock_hass)
    _record(coordinator, "0x1", "Sensor")
    assert coordinator.get_device_reconnect_rate("0x1") == 0.0
    assert coordinator.get_device_battery_trend("0x1") is None
    assert coordinator.get_device_health_score("0x1") is not None
    assert coordinator.get_device_metrics("0x1") == {}
    assert coordinator.get_device_metrics("nope") is None
    assert coordinator.get_device_history("nope") == []


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (datetime(2026, 9, 24, 8, 0, tzinfo=dt_util.UTC), "2026-09-24T08:00:00+00:00"),
        (1790236800.0, "2026-09-24T08:00:00+00:00"),
        ("1790236800.0", "2026-09-24T08:00:00+00:00"),
        ("2026-09-24T08:00:00+00:00", "2026-09-24T08:00:00+00:00"),
        ("garbage", NOW.isoformat()),
        (None, NOW.isoformat()),
    ],
)
def test_normalize_zha_last_seen(value: Any, expected: str) -> None:
    """ZHA last_seen values (datetime, epoch, ISO) become aware ISO strings."""
    assert ZigSightCoordinator._normalize_zha_last_seen(value, NOW) == expected


def test_zha_device_update_merges_metrics(mock_hass: MagicMock) -> None:
    """Polled ZHA devices are merged, not replaced."""
    coordinator = ZigSightCoordinator(mock_hass, enable_zha=True)
    assert coordinator._process_zha_device_update(
        "00:11",
        {"friendly_name": "Plug", "metrics": {"link_quality": 100, "rssi": -60}},
    )
    assert not coordinator._process_zha_device_update(
        "00:11", {"metrics": {"battery": 80}}
    )
    record = coordinator.get_device("00:11")
    assert record is not None
    assert record["metrics"]["link_quality"] == 100
    assert record["metrics"]["battery"] == 80
    assert record["metrics"]["rssi"] == -60
    assert record["friendly_name"] == "Plug"
    assert record["source"] == DEVICE_SOURCE_ZHA
    assert coordinator.wants_entities("00:11")


async def test_zha_collector_errors_are_contained(mock_hass: MagicMock) -> None:
    """A failing ZHA collector doesn't fail the refresh."""
    coordinator = ZigSightCoordinator(mock_hass, enable_zha=True)
    collector = MagicMock()
    collector.is_available.return_value = True

    async def _boom() -> dict[str, Any]:
        raise RuntimeError("boom")

    collector.collect_devices = _boom
    coordinator._zha_collector = collector
    data = await coordinator._async_update_data()
    assert data["device_count"] == 0


def test_get_all_devices_strips_state(mock_hass: MagicMock) -> None:
    """The API view of devices excludes the raw merged state."""
    coordinator = ZigSightCoordinator(mock_hass)
    record = _record(coordinator, "0x1", "Sensor")
    record["state"] = {"occupancy": True}
    assert "state" not in coordinator.get_all_devices()["0x1"]
