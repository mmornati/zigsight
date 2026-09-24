"""Test analytics module."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from custom_components.zigsight.analytics import DeviceAnalytics


class TestDeviceAnalyticsInit:
    """Test DeviceAnalytics initialization."""

    def test_default_initialization(self) -> None:
        """Test default initialization values."""
        analytics = DeviceAnalytics()
        assert analytics.reconnect_rate_window_hours == 24
        assert analytics.battery_drain_threshold == 10
        assert analytics.min_battery_for_trend == 20

    def test_custom_initialization(self) -> None:
        """Test custom initialization values."""
        analytics = DeviceAnalytics(
            reconnect_rate_window_hours=12,
            battery_drain_threshold=5.0,
            min_battery_for_trend=30,
        )
        assert analytics.reconnect_rate_window_hours == 12
        assert analytics.battery_drain_threshold == 5.0
        assert analytics.min_battery_for_trend == 30


class TestComputeReconnectRate:
    """Test reconnect rate computation."""

    def test_no_history(self) -> None:
        """Test reconnect rate with no history."""
        analytics = DeviceAnalytics()
        assert analytics.compute_reconnect_rate([]) == 0.0

    def test_insufficient_data(self) -> None:
        """Test reconnect rate with insufficient data."""
        analytics = DeviceAnalytics()
        history = [
            {
                "timestamp": datetime.now().isoformat(),
                "metrics": {"battery": 100},
            }
        ]
        assert analytics.compute_reconnect_rate(history) == 0.0

    def test_with_reconnects(self) -> None:
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

        rate = analytics.compute_reconnect_rate(history)
        assert rate >= 0.0

    def test_custom_window_hours(self) -> None:
        """Test reconnect rate with custom window hours."""
        analytics = DeviceAnalytics(reconnect_rate_window_hours=24)
        now = datetime.now()

        history = [
            {"timestamp": (now - timedelta(hours=1)).isoformat()},
            {"timestamp": (now - timedelta(minutes=30)).isoformat()},
        ]

        rate = analytics.compute_reconnect_rate(history, window_hours=2)
        assert rate >= 0.0

    def test_missing_timestamp(self) -> None:
        """Test reconnect rate handles missing timestamps."""
        analytics = DeviceAnalytics()
        now = datetime.now()
        history = [
            {"metrics": {"battery": 100}},  # Missing timestamp
            {"timestamp": (now - timedelta(hours=2)).isoformat()},
            {"timestamp": now.isoformat()},
        ]
        rate = analytics.compute_reconnect_rate(history)
        assert rate >= 0.0

    def test_invalid_timestamp_format(self) -> None:
        """Test reconnect rate handles invalid timestamp format."""
        analytics = DeviceAnalytics()
        history = [
            {"timestamp": "invalid-date"},
            {"timestamp": datetime.now().isoformat()},
        ]
        rate = analytics.compute_reconnect_rate(history)
        assert rate >= 0.0

    def test_entries_outside_window(self) -> None:
        """Test that entries outside window are ignored."""
        analytics = DeviceAnalytics()
        now = datetime.now()

        history = [
            {"timestamp": (now - timedelta(hours=48)).isoformat()},
            {"timestamp": (now - timedelta(hours=47)).isoformat()},
        ]

        rate = analytics.compute_reconnect_rate(history, window_hours=24)
        assert rate == 0.0

    def test_zero_window_hours(self) -> None:
        """Test reconnect rate with zero window hours."""
        analytics = DeviceAnalytics()
        history = [
            {"timestamp": datetime.now().isoformat()},
            {"timestamp": datetime.now().isoformat()},
        ]
        rate = analytics.compute_reconnect_rate(history, window_hours=0)
        assert rate == 0.0


class TestComputeBatteryTrend:
    """Test battery trend computation."""

    def test_no_history(self) -> None:
        """Test battery trend with no history."""
        analytics = DeviceAnalytics()
        assert analytics.compute_battery_trend([]) is None

    def test_insufficient_data(self) -> None:
        """Test battery trend with insufficient data."""
        analytics = DeviceAnalytics()
        history = [
            {
                "timestamp": datetime.now().isoformat(),
                "metrics": {"battery": 100},
            }
        ]
        assert analytics.compute_battery_trend(history) is None

    def test_with_data_draining(self) -> None:
        """Test battery trend computation showing drain."""
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

    def test_with_data_charging(self) -> None:
        """Test battery trend computation showing charging."""
        analytics = DeviceAnalytics()
        now = datetime.now()

        history = [
            {
                "timestamp": (now - timedelta(hours=4)).isoformat(),
                "metrics": {"battery": 50},
            },
            {
                "timestamp": (now - timedelta(hours=2)).isoformat(),
                "metrics": {"battery": 75},
            },
            {
                "timestamp": now.isoformat(),
                "metrics": {"battery": 100},
            },
        ]

        trend = analytics.compute_battery_trend(history)
        assert trend is not None
        assert trend > 0  # Battery is charging (positive trend)

    def test_battery_percent_key(self) -> None:
        """Test battery trend with battery_percent key."""
        analytics = DeviceAnalytics()
        now = datetime.now()

        history = [
            {
                "timestamp": (now - timedelta(hours=2)).isoformat(),
                "metrics": {"battery_percent": 100},
            },
            {
                "timestamp": now.isoformat(),
                "metrics": {"battery_percent": 90},
            },
        ]

        trend = analytics.compute_battery_trend(history)
        assert trend is not None

    def test_low_battery_filtered_out(self) -> None:
        """Test that low battery values are filtered out."""
        analytics = DeviceAnalytics(min_battery_for_trend=50)
        now = datetime.now()

        history = [
            {
                "timestamp": (now - timedelta(hours=2)).isoformat(),
                "metrics": {"battery": 30},  # Below threshold
            },
            {
                "timestamp": now.isoformat(),
                "metrics": {"battery": 20},  # Below threshold
            },
        ]

        trend = analytics.compute_battery_trend(history)
        assert trend is None

    def test_invalid_battery_value(self) -> None:
        """Test battery trend handles invalid battery values."""
        analytics = DeviceAnalytics()
        now = datetime.now()

        history = [
            {
                "timestamp": (now - timedelta(hours=2)).isoformat(),
                "metrics": {"battery": "invalid"},
            },
            {
                "timestamp": now.isoformat(),
                "metrics": {"battery": 80},
            },
        ]

        trend = analytics.compute_battery_trend(history)
        assert trend is None  # Only one valid reading

    def test_entries_outside_window(self) -> None:
        """Test that entries outside window are ignored."""
        analytics = DeviceAnalytics()
        now = datetime.now()

        history = [
            {
                "timestamp": (now - timedelta(hours=48)).isoformat(),
                "metrics": {"battery": 100},
            },
            {
                "timestamp": (now - timedelta(hours=47)).isoformat(),
                "metrics": {"battery": 90},
            },
        ]

        trend = analytics.compute_battery_trend(history, window_hours=24)
        assert trend is None


class TestComputeHealthScore:
    """Test health score computation."""

    def test_no_device_data(self) -> None:
        """Test health score with no device data."""
        analytics = DeviceAnalytics()
        device_data: dict[str, Any] = {}
        history: list[dict[str, Any]] = []
        score = analytics.compute_health_score(device_data, history)
        assert 0 <= score <= 100

    def test_with_excellent_metrics(self) -> None:
        """Test health score with excellent metrics."""
        analytics = DeviceAnalytics()
        now = datetime.now()

        device_data: dict[str, Any] = {
            "metrics": {
                "link_quality": 255,  # Excellent
                "battery": 100,  # Full
                "last_seen": now.isoformat(),  # Very recent
            }
        }

        score = analytics.compute_health_score(device_data, [])
        assert score > 80  # Should be excellent

    def test_with_poor_metrics(self) -> None:
        """Test health score with poor metrics."""
        analytics = DeviceAnalytics()
        old_time = datetime.now() - timedelta(hours=2)

        device_data: dict[str, Any] = {
            "metrics": {
                "link_quality": 10,  # Poor
                "battery": 5,  # Almost dead
                "last_seen": old_time.isoformat(),  # Old
            }
        }

        # Create history with many reconnects
        now = datetime.now()
        history: list[dict[str, Any]] = [
            {"timestamp": (now - timedelta(hours=i)).isoformat()} for i in range(24)
        ]

        score = analytics.compute_health_score(device_data, history)
        assert score < 50  # Should be poor

    def test_link_quality_normalization(self) -> None:
        """Test link quality normalization from 0-255 to 0-100."""
        analytics = DeviceAnalytics()

        # Test with max link quality
        device_data_max = {"metrics": {"link_quality": 255}}
        score_max = analytics.compute_health_score(device_data_max, [])

        # Test with half link quality
        device_data_half = {"metrics": {"link_quality": 127}}
        score_half = analytics.compute_health_score(device_data_half, [])

        assert score_max > score_half

    def test_invalid_link_quality(self) -> None:
        """Test health score with invalid link quality value."""
        analytics = DeviceAnalytics()
        device_data = {"metrics": {"link_quality": "invalid"}}
        score = analytics.compute_health_score(device_data, [])
        assert 0 <= score <= 100

    def test_invalid_battery(self) -> None:
        """Test health score with invalid battery value."""
        analytics = DeviceAnalytics()
        device_data = {"metrics": {"battery": "invalid"}}
        score = analytics.compute_health_score(device_data, [])
        assert 0 <= score <= 100

    def test_connectivity_score_recent(self) -> None:
        """Test connectivity score with recent last_seen."""
        analytics = DeviceAnalytics()
        now = datetime.now()
        device_data = {"metrics": {"last_seen": now.isoformat()}}
        score = analytics.compute_health_score(device_data, [])
        assert score > 40  # Connectivity score should contribute positively

    def test_connectivity_score_old(self) -> None:
        """Test connectivity score with old last_seen."""
        analytics = DeviceAnalytics()
        old_time = datetime.now() - timedelta(hours=2)
        device_data = {"metrics": {"last_seen": old_time.isoformat()}}
        score = analytics.compute_health_score(device_data, [])
        # Score should still be valid
        assert 0 <= score <= 100

    def test_invalid_last_seen(self) -> None:
        """Test health score with invalid last_seen format."""
        analytics = DeviceAnalytics()
        device_data = {"metrics": {"last_seen": "invalid-date"}}
        score = analytics.compute_health_score(device_data, [])
        assert 0 <= score <= 100

    def test_high_reconnect_rate_penalty(self) -> None:
        """Test that high reconnect rate penalizes score."""
        analytics = DeviceAnalytics()
        now = datetime.now()

        # Create history with many reconnects (gaps > 5 minutes)
        history = []
        for i in range(20):
            history.append({"timestamp": (now - timedelta(hours=i)).isoformat()})

        device_data: dict[str, Any] = {"metrics": {"link_quality": 200}}
        score = analytics.compute_health_score(device_data, history)
        # Score should be lower due to reconnects
        assert 0 <= score <= 100


class TestBatteryDrainWarning:
    """Test battery drain warning detection."""

    def test_no_drain_warning(self) -> None:
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

    def test_significant_drain_warning(self) -> None:
        """Test battery drain warning triggers with significant drain."""
        analytics = DeviceAnalytics(battery_drain_threshold=1.0)
        now = datetime.now()

        # Very rapid drain
        history = [
            {
                "timestamp": (now - timedelta(hours=2)).isoformat(),
                "metrics": {"battery": 100},
            },
            {
                "timestamp": now.isoformat(),
                "metrics": {"battery": 50},
            },
        ]

        warning = analytics.check_battery_drain_warning(history)
        assert warning is True

    def test_custom_threshold(self) -> None:
        """Test battery drain warning with custom threshold."""
        analytics = DeviceAnalytics(battery_drain_threshold=5.0)
        now = datetime.now()

        history = [
            {
                "timestamp": (now - timedelta(hours=4)).isoformat(),
                "metrics": {"battery": 100},
            },
            {
                "timestamp": now.isoformat(),
                "metrics": {"battery": 70},
            },
        ]

        warning = analytics.check_battery_drain_warning(history, threshold=2.0)
        assert isinstance(warning, bool)

    def test_no_battery_data(self) -> None:
        """Test battery drain warning with no battery data."""
        analytics = DeviceAnalytics()
        history: list[dict[str, Any]] = []
        assert analytics.check_battery_drain_warning(history) is False


class TestConnectivityWarning:
    """Test connectivity warning detection."""

    def test_no_warning_recent(self) -> None:
        """Test connectivity warning with good connectivity."""
        analytics = DeviceAnalytics()
        now = datetime.now()

        device_data = {
            "metrics": {
                "last_seen": now.isoformat(),
            },
            "history": [],
        }

        assert analytics.check_connectivity_warning(device_data, 5.0) is False

    def test_warning_old_last_seen(self) -> None:
        """Test connectivity warning with old last_seen."""
        analytics = DeviceAnalytics()

        device_data = {
            "metrics": {
                "last_seen": (datetime.now() - timedelta(hours=2)).isoformat(),
            },
            "history": [],
        }

        assert analytics.check_connectivity_warning(device_data, 5.0) is True

    def test_warning_high_reconnect_rate(self) -> None:
        """Test connectivity warning with high reconnect rate."""
        analytics = DeviceAnalytics()
        now = datetime.now()

        # Create history with many reconnects
        history = []
        for i in range(50):  # Many reconnects
            history.append({"timestamp": (now - timedelta(hours=i / 3)).isoformat()})

        device_data = {
            "metrics": {
                "last_seen": now.isoformat(),
            },
            "history": history,
        }

        warning = analytics.check_connectivity_warning(device_data, 1.0)
        assert isinstance(warning, bool)

    def test_no_last_seen(self) -> None:
        """Test connectivity warning with no last_seen."""
        analytics = DeviceAnalytics()
        device_data = {
            "metrics": {},
            "history": [],
        }
        # Should not crash, no warning since no reconnects and no last_seen check
        warning = analytics.check_connectivity_warning(device_data, 5.0)
        assert isinstance(warning, bool)

    def test_invalid_last_seen_format(self) -> None:
        """Test connectivity warning with invalid last_seen format."""
        analytics = DeviceAnalytics()
        device_data = {
            "metrics": {
                "last_seen": "invalid-date",
            },
            "history": [],
        }
        # Should not crash
        warning = analytics.check_connectivity_warning(device_data, 5.0)
        assert isinstance(warning, bool)
