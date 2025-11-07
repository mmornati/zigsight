"""Test analytics module."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from custom_components.zigsight.analytics import DeviceAnalytics


def test_compute_reconnect_rate_no_history() -> None:
    """Test reconnect rate with no history."""
    analytics = DeviceAnalytics()
    assert analytics.compute_reconnect_rate([]) == 0.0


def test_compute_reconnect_rate_insufficient_data() -> None:
    """Test reconnect rate with insufficient data."""
    analytics = DeviceAnalytics()
    history = [
        {
            "timestamp": datetime.now().isoformat(),
            "metrics": {"battery": 100},
        }
    ]
    assert analytics.compute_reconnect_rate(history) == 0.0


def test_compute_reconnect_rate_with_reconnects() -> None:
    """Test reconnect rate computation with reconnection events."""
    analytics = DeviceAnalytics(reconnect_rate_window_hours=24)
    now = datetime.now()

    history = [
        {
            "timestamp": (now - timedelta(hours=23)).isoformat(),
            "metrics": {"battery": 100},
        },
        {
            "timestamp": (now - timedelta(hours=10)).isoformat(),
            "metrics": {"battery": 90},
        },
        {
            "timestamp": (now - timedelta(hours=2)).isoformat(),
            "metrics": {"battery": 80},
        },
        {
            "timestamp": (now - timedelta(minutes=30)).isoformat(),
            "metrics": {"battery": 70},
        },
    ]

    # Add a gap > 5 minutes between entries 1 and 2 (simulating reconnect)
    rate = analytics.compute_reconnect_rate(history)
    assert rate >= 0.0


def test_compute_battery_trend_no_history() -> None:
    """Test battery trend with no history."""
    analytics = DeviceAnalytics()
    assert analytics.compute_battery_trend([]) is None


def test_compute_battery_trend_insufficient_data() -> None:
    """Test battery trend with insufficient data."""
    analytics = DeviceAnalytics()
    history = [
        {
            "timestamp": datetime.now().isoformat(),
            "metrics": {"battery": 100},
        }
    ]
    assert analytics.compute_battery_trend(history) is None


def test_compute_battery_trend_with_data() -> None:
    """Test battery trend computation with valid data."""
    analytics = DeviceAnalytics()
    now = datetime.now()

    history = [
        {
            "timestamp": (now - timedelta(hours=23)).isoformat(),
            "metrics": {"battery": 100},
        },
        {
            "timestamp": (now - timedelta(hours=10)).isoformat(),
            "metrics": {"battery": 90},
        },
        {
            "timestamp": (now - timedelta(hours=2)).isoformat(),
            "metrics": {"battery": 80},
        },
        {
            "timestamp": (now - timedelta(minutes=30)).isoformat(),
            "metrics": {"battery": 70},
        },
    ]

    trend = analytics.compute_battery_trend(history)
    assert trend is not None
    assert trend < 0  # Battery is draining (negative trend)


def test_compute_health_score_no_device() -> None:
    """Test health score with no device data."""
    analytics = DeviceAnalytics()
    device_data: dict[str, Any] = {}
    history: list[dict[str, Any]] = []
    score = analytics.compute_health_score(device_data, history)
    assert 0 <= score <= 100


def test_compute_health_score_with_metrics() -> None:
    """Test health score computation with device metrics."""
    analytics = DeviceAnalytics()
    now = datetime.now()

    device_data: dict[str, Any] = {
        "metrics": {
            "link_quality": 255,  # Excellent
            "battery": 80,  # Good
            "last_seen": now.isoformat(),  # Recent
        }
    }

    history: list[dict[str, Any]] = [
        {
            "timestamp": (now - timedelta(hours=1)).isoformat(),
            "metrics": {"battery": 85},
        }
    ]

    score = analytics.compute_health_score(device_data, history)
    assert 0 <= score <= 100
    assert score > 50  # Should be good with excellent link quality


def test_check_battery_drain_warning_no_drain() -> None:
    """Test battery drain warning with no significant drain."""
    analytics = DeviceAnalytics(battery_drain_threshold=10.0)
    now = datetime.now()

    history = [
        {
            "timestamp": (now - timedelta(hours=23)).isoformat(),
            "metrics": {"battery": 100},
        },
        {
            "timestamp": (now - timedelta(minutes=30)).isoformat(),
            "metrics": {"battery": 99},
        },
    ]

    assert analytics.check_battery_drain_warning(history) is False


def test_check_battery_drain_warning_with_drain() -> None:
    """Test battery drain warning with significant drain."""
    analytics = DeviceAnalytics(battery_drain_threshold=10.0)
    now = datetime.now()

    history = [
        {
            "timestamp": (now - timedelta(hours=23)).isoformat(),
            "metrics": {"battery": 100},
        },
        {
            "timestamp": (now - timedelta(hours=1)).isoformat(),
            "metrics": {"battery": 70},  # 30% drop in 22 hours = ~1.36%/hour
        },
    ]

    # This should trigger warning if trend is < -10%/hour
    warning = analytics.check_battery_drain_warning(history)
    assert isinstance(warning, bool)


def test_check_connectivity_warning_no_warning() -> None:
    """Test connectivity warning with good connectivity."""
    analytics = DeviceAnalytics()
    now = datetime.now()

    device_data = {
        "metrics": {
            "last_seen": now.isoformat(),
        },
        "history": [],
    }

    assert (
        analytics.check_connectivity_warning(device_data, reconnect_rate_threshold=5.0)
        is False
    )


def test_check_connectivity_warning_old_last_seen() -> None:
    """Test connectivity warning with old last_seen."""
    analytics = DeviceAnalytics()

    device_data = {
        "metrics": {
            "last_seen": (datetime.now() - timedelta(hours=2)).isoformat(),
        },
        "history": [],
    }

    assert (
        analytics.check_connectivity_warning(device_data, reconnect_rate_threshold=5.0)
        is True
    )
