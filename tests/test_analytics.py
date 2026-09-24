"""Test analytics module."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pytest
from homeassistant.util import dt as dt_util

from custom_components.zigsight.analytics import (
    DeviceAnalytics,
    as_datetime,
)
from custom_components.zigsight.const import (
    END_DEVICE_CONNECTIVITY_TIMEOUT,
    ROUTER_CONNECTIVITY_TIMEOUT,
)

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=dt_util.UTC)


def _battery_history(readings: list[tuple[float, float]]) -> list[dict[str, Any]]:
    """(hours ago, battery) -> history entries."""
    return [
        {"timestamp": NOW - timedelta(hours=hours), "battery": battery}
        for hours, battery in readings
    ]


class TestInit:
    """DeviceAnalytics initialization."""

    def test_defaults(self) -> None:
        """Default thresholds."""
        analytics = DeviceAnalytics()
        assert analytics.reconnect_rate_window_hours == 24
        assert analytics.battery_drain_threshold == 10
        assert analytics.router_timeout == ROUTER_CONNECTIVITY_TIMEOUT
        assert analytics.end_device_timeout == END_DEVICE_CONNECTIVITY_TIMEOUT

    def test_custom(self) -> None:
        """Custom thresholds."""
        analytics = DeviceAnalytics(
            reconnect_rate_window_hours=12,
            battery_drain_threshold=5.0,
            router_timeout=timedelta(minutes=3),
            end_device_timeout=timedelta(hours=2),
        )
        assert analytics.reconnect_rate_window_hours == 12
        assert analytics.battery_drain_threshold == 5.0
        assert analytics.connectivity_timeout({"type": "Router"}) == timedelta(
            minutes=3
        )
        assert analytics.connectivity_timeout({"type": "EndDevice"}) == timedelta(
            hours=2
        )
        assert analytics.connectivity_timeout({}) == timedelta(hours=2)


class TestAsDatetime:
    """Timestamp normalisation."""

    def test_values(self) -> None:
        """Strings, aware and naive datetimes are normalised to aware UTC."""
        assert as_datetime(NOW) == NOW
        assert as_datetime(NOW.isoformat()) == NOW
        assert as_datetime("2026-09-24T14:00:00+02:00") == NOW
        assert as_datetime("2026-09-24T12:00:00") == NOW
        assert as_datetime("garbage") is None
        assert as_datetime(None) is None
        assert as_datetime(123) is None


class TestReconnectRate:
    """Reconnect rate from recorded offline -> online transitions."""

    def test_no_events(self) -> None:
        """No reconnects -> 0."""
        assert DeviceAnalytics().compute_reconnect_rate([], now=NOW) == 0.0

    def test_events_in_window(self) -> None:
        """Only events inside the window count."""
        events = [
            NOW - timedelta(hours=1),
            (NOW - timedelta(hours=2)).isoformat(),
            NOW - timedelta(hours=30),
            "garbage",
        ]
        assert DeviceAnalytics().compute_reconnect_rate(events, now=NOW) == round(
            2 / 24, 3
        )
        assert DeviceAnalytics().compute_reconnect_rate(
            events, window_hours=48, now=NOW
        ) == round(3 / 48, 3)

    def test_zero_window(self) -> None:
        """A zero window never divides by zero."""
        assert DeviceAnalytics().compute_reconnect_rate([NOW], window_hours=0) == 0.0

    def test_regular_reporting_is_not_a_reconnect(self) -> None:
        """Sleepy devices reporting every hour no longer look like reconnects."""
        # The old implementation counted every >5 minute gap between messages
        # as a reconnect; reconnects are now explicit availability events.
        assert DeviceAnalytics().compute_reconnect_rate([], now=NOW) == 0.0


class TestBatteryTrend:
    """Battery trend (linear regression)."""

    def test_insufficient_data(self) -> None:
        """Fewer than 2 readings -> None."""
        analytics = DeviceAnalytics()
        assert analytics.compute_battery_trend([], now=NOW) is None
        assert (
            analytics.compute_battery_trend(_battery_history([(1, 90)]), now=NOW)
            is None
        )

    def test_minimum_span(self) -> None:
        """Readings a few minutes apart don't extrapolate to a huge drain."""
        analytics = DeviceAnalytics()
        history = _battery_history([(0.1, 100), (0.05, 99)])
        assert analytics.compute_battery_trend(history, now=NOW) is None

    def test_draining(self) -> None:
        """A steady drain gives a negative slope in %/h."""
        history = _battery_history([(4, 90), (3, 80), (2, 70), (1, 60)])
        assert DeviceAnalytics().compute_battery_trend(history, now=NOW) == -10.0

    def test_charging(self) -> None:
        """A rising battery gives a positive slope."""
        history = _battery_history([(3, 50), (2, 60), (1, 70)])
        assert DeviceAnalytics().compute_battery_trend(history, now=NOW) == 10.0

    def test_low_battery_values_are_used(self) -> None:
        """Values below 20% are no longer ignored."""
        history = _battery_history([(3, 18), (2, 12), (1, 6)])
        assert DeviceAnalytics().compute_battery_trend(history, now=NOW) == -6.0

    def test_ignores_invalid_and_old_entries(self) -> None:
        """Invalid values, missing timestamps and old entries are skipped."""
        history: list[dict[str, Any]] = [
            *_battery_history([(30, 100), (3, 90), (1, 80)]),
            {"timestamp": NOW, "battery": "bad"},
            {"timestamp": NOW, "battery": True},
            {"battery": 10},
            {"timestamp": "garbage", "battery": 10},
            {"timestamp": NOW, "battery": None},
        ]
        assert DeviceAnalytics().compute_battery_trend(history, now=NOW) == -5.0

    def test_string_timestamps(self) -> None:
        """ISO string timestamps are accepted."""
        history = [
            {"timestamp": (NOW - timedelta(hours=2)).isoformat(), "battery": 50},
            {"timestamp": NOW.isoformat(), "battery": 48},
        ]
        assert DeviceAnalytics().compute_battery_trend(history, now=NOW) == -1.0


class TestConnectivity:
    """Connectivity score and warning."""

    def test_availability_is_authoritative(self) -> None:
        """Z2M availability wins over last_seen."""
        analytics = DeviceAnalytics()
        old = {"last_seen": (NOW - timedelta(days=3)).isoformat()}
        assert (
            analytics.compute_connectivity_score(
                {"available": True, "metrics": old}, NOW
            )
            == 100.0
        )
        assert analytics.compute_connectivity_score({"available": False}, NOW) == 0.0
        assert not analytics.check_connectivity_warning(
            {"available": True, "metrics": old}, now=NOW
        )
        assert analytics.check_connectivity_warning({"available": False}, now=NOW)

    @pytest.mark.parametrize(
        ("device_type", "silent_for", "warning"),
        [
            ("Router", timedelta(minutes=5), False),
            ("Router", timedelta(minutes=11), True),
            ("EndDevice", timedelta(hours=2), False),
            ("EndDevice", timedelta(hours=24), False),
            ("EndDevice", timedelta(hours=26), True),
            (None, timedelta(hours=2), False),
        ],
    )
    def test_type_dependent_timeouts(
        self, device_type: str | None, silent_for: timedelta, warning: bool
    ) -> None:
        """Routers must be chatty, sleepy end devices may be silent for hours."""
        device = {
            "type": device_type,
            "metrics": {"last_seen": (NOW - silent_for).isoformat()},
        }
        assert DeviceAnalytics().check_connectivity_warning(device, now=NOW) is warning

    def test_no_last_seen(self) -> None:
        """Unknown last_seen is neutral and not a warning."""
        analytics = DeviceAnalytics()
        assert analytics.compute_connectivity_score({"metrics": {}}, NOW) == 50.0
        assert not analytics.check_connectivity_warning({"metrics": {}}, now=NOW)
        assert not analytics.check_connectivity_warning(
            {"metrics": {"last_seen": "garbage"}}, now=NOW
        )

    def test_linear_decay(self) -> None:
        """The score decays with the time since last seen."""
        analytics = DeviceAnalytics()
        half = {
            "type": "Router",
            "metrics": {"last_seen": (NOW - timedelta(minutes=5)).isoformat()},
        }
        assert analytics.compute_connectivity_score(half, NOW) == pytest.approx(50.0)

    def test_reconnect_rate_threshold(self) -> None:
        """Flapping devices get a warning even when online."""
        analytics = DeviceAnalytics()
        device = {"available": True}
        assert analytics.check_connectivity_warning(device, 6.0, 5.0, NOW)
        assert not analytics.check_connectivity_warning(device, 1.0, 5.0, NOW)


class TestHealthScore:
    """Health score aggregation."""

    def test_excellent(self) -> None:
        """Great metrics -> high score."""
        device = {
            "available": True,
            "metrics": {"link_quality": 255, "battery": 100},
        }
        assert DeviceAnalytics().compute_health_score(device, 0.0, NOW) == 100.0

    def test_poor(self) -> None:
        """Offline, weak, empty and flapping -> low score."""
        device = {
            "available": False,
            "metrics": {"link_quality": 10, "battery": 5},
        }
        assert DeviceAnalytics().compute_health_score(device, 12.0, NOW) < 10

    def test_mains_devices_are_not_penalised_for_missing_battery(self) -> None:
        """No battery reading -> the battery component is left out."""
        device = {"available": True, "metrics": {"link_quality": 255}}
        assert DeviceAnalytics().compute_health_score(device, 0.0, NOW) == 100.0

    def test_invalid_and_missing_values(self) -> None:
        """Invalid values fall back to neutral scores."""
        analytics = DeviceAnalytics()
        score = analytics.compute_health_score(
            {"metrics": {"link_quality": "bad", "battery": "bad"}}, 0.0, NOW
        )
        assert 0 <= score <= 100
        assert 0 <= analytics.compute_health_score({}) <= 100

    def test_reconnect_rate_penalty(self) -> None:
        """Higher reconnect rates lower the score."""
        analytics = DeviceAnalytics()
        device = {"available": True, "metrics": {"link_quality": 200}}
        assert analytics.compute_health_score(
            device, 5.0, NOW
        ) < analytics.compute_health_score(device, 0.0, NOW)


class TestBatteryDrainWarning:
    """Battery drain warning."""

    def test_threshold(self) -> None:
        """Warning when the drain is faster than the threshold."""
        analytics = DeviceAnalytics(battery_drain_threshold=10.0)
        assert not analytics.check_battery_drain_warning(None)
        assert not analytics.check_battery_drain_warning(-5.0)
        assert analytics.check_battery_drain_warning(-11.0)
        assert analytics.check_battery_drain_warning(-3.0, threshold=2.0)
        assert not analytics.check_battery_drain_warning(5.0)
