"""Analytics engine for ZigSight metrics computation.

All timestamps handled here are timezone-aware (UTC) datetimes. History
entries are small mappings holding only numeric metrics::

    {"timestamp": datetime, "link_quality": 120, "battery": 87, "voltage": 2985}
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta
from typing import Any

from homeassistant.util import dt as dt_util

from .const import (
    DEFAULT_BATTERY_DRAIN_THRESHOLD,
    DEFAULT_RECONNECT_RATE_THRESHOLD,
    DEFAULT_RECONNECT_RATE_WINDOW_HOURS,
    DEVICE_TYPE_COORDINATOR,
    DEVICE_TYPE_ROUTER,
    END_DEVICE_CONNECTIVITY_TIMEOUT,
    ROUTER_CONNECTIVITY_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

# Battery trend needs readings spanning at least this long; two readings a
# few seconds apart (e.g. 100% -> 99%) would otherwise extrapolate to a huge
# hourly drain and raise false warnings.
MIN_BATTERY_TREND_SPAN = timedelta(hours=1)
DEFAULT_BATTERY_TREND_WINDOW_HOURS = 24

DEFAULT_HEALTH_SCORE_WEIGHTS = {
    "link_quality": 0.3,
    "battery": 0.2,
    "reconnect_rate": 0.3,
    "connectivity": 0.2,
}


def as_datetime(value: Any) -> datetime | None:
    """Return an aware UTC datetime from a datetime or ISO string."""
    if isinstance(value, datetime):
        parsed: datetime | None = value
    elif isinstance(value, str) and value:
        parsed = dt_util.parse_datetime(value)
    else:
        return None
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_util.UTC)
    return dt_util.as_utc(parsed)


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class DeviceAnalytics:
    """Compute analytics metrics for a Zigbee device."""

    def __init__(
        self,
        reconnect_rate_window_hours: int = DEFAULT_RECONNECT_RATE_WINDOW_HOURS,
        battery_drain_threshold: float = DEFAULT_BATTERY_DRAIN_THRESHOLD,
        router_timeout: timedelta = ROUTER_CONNECTIVITY_TIMEOUT,
        end_device_timeout: timedelta = END_DEVICE_CONNECTIVITY_TIMEOUT,
    ) -> None:
        """Initialize analytics engine with thresholds."""
        self.reconnect_rate_window_hours = reconnect_rate_window_hours
        self.battery_drain_threshold = battery_drain_threshold
        self.router_timeout = router_timeout
        self.end_device_timeout = end_device_timeout
        self.weights = DEFAULT_HEALTH_SCORE_WEIGHTS.copy()

    def connectivity_timeout(self, device: Mapping[str, Any]) -> timedelta:
        """Return how long a device may stay silent before it is suspicious.

        Routers (and the coordinator) are mains powered and chatty; sleepy
        end devices may legitimately stay silent for many hours.
        """
        if device.get("type") in (DEVICE_TYPE_ROUTER, DEVICE_TYPE_COORDINATOR):
            return self.router_timeout
        return self.end_device_timeout

    def compute_reconnect_rate(
        self,
        reconnect_events: Iterable[datetime | str],
        window_hours: int | None = None,
        now: datetime | None = None,
    ) -> float:
        """Compute the reconnect rate (events per hour) over a sliding window.

        A reconnect event is an availability transition offline -> online
        (as published by Zigbee2MQTT), recorded by the coordinator.
        """
        if window_hours is None:
            window_hours = self.reconnect_rate_window_hours
        if window_hours <= 0:
            return 0.0
        now = now or dt_util.utcnow()
        window_start = now - timedelta(hours=window_hours)
        count = 0
        for event in reconnect_events:
            timestamp = as_datetime(event)
            if timestamp is not None and window_start <= timestamp <= now:
                count += 1
        return round(count / window_hours, 3)

    def compute_battery_trend(
        self,
        history: Iterable[Mapping[str, Any]],
        window_hours: int = DEFAULT_BATTERY_TREND_WINDOW_HOURS,
        now: datetime | None = None,
    ) -> float | None:
        """Compute the battery trend (percentage points per hour).

        Uses a least-squares linear regression over the battery readings in
        the window. Every reading counts, including low batteries: a device
        at 15% that keeps draining is exactly what should be reported.

        Returns None when there are fewer than two readings or they span
        less than MIN_BATTERY_TREND_SPAN.
        """
        now = now or dt_util.utcnow()
        window_start = now - timedelta(hours=window_hours)
        readings: list[tuple[datetime, float]] = []
        for entry in history:
            timestamp = as_datetime(entry.get("timestamp"))
            if timestamp is None or timestamp < window_start:
                continue
            battery = _as_float(entry.get("battery"))
            if battery is None:
                continue
            readings.append((timestamp, battery))

        if len(readings) < 2:
            return None
        readings.sort(key=lambda reading: reading[0])
        start = readings[0][0]
        if readings[-1][0] - start < MIN_BATTERY_TREND_SPAN:
            return None

        hours = [(ts - start).total_seconds() / 3600 for ts, _ in readings]
        values = [battery for _, battery in readings]
        n = len(readings)
        sum_t = sum(hours)
        sum_b = sum(values)
        sum_tb = sum(t * b for t, b in zip(hours, values, strict=True))
        sum_t2 = sum(t * t for t in hours)
        denominator = n * sum_t2 - sum_t**2
        if denominator == 0:
            return None
        slope = (n * sum_tb - sum_t * sum_b) / denominator
        return round(slope, 2)

    def compute_connectivity_score(
        self, device: Mapping[str, Any], now: datetime | None = None
    ) -> float:
        """Return a 0-100 connectivity score.

        Zigbee2MQTT availability (when enabled) is authoritative. Otherwise
        the score decays linearly with the time since the device was last
        seen, relative to its device-type dependent timeout.
        """
        available = device.get("available")
        if available is False:
            return 0.0
        if available is True:
            return 100.0
        last_seen = as_datetime((device.get("metrics") or {}).get("last_seen"))
        if last_seen is None:
            return 50.0
        now = now or dt_util.utcnow()
        elapsed = max(0.0, (now - last_seen).total_seconds())
        timeout = self.connectivity_timeout(device).total_seconds()
        return max(0.0, 100.0 * (1 - elapsed / timeout))

    def compute_health_score(
        self,
        device: Mapping[str, Any],
        reconnect_rate: float = 0.0,
        now: datetime | None = None,
    ) -> float:
        """Compute an aggregated health score for a device (0-100).

        Components (weighted average):
        - link quality: LQI 0-255 normalised to 0-100 (neutral 50 if unknown)
        - battery: battery percentage (skipped for mains powered devices)
        - reconnect rate: 0 events/h = 100, >= 10 events/h = 0
        - connectivity: see compute_connectivity_score
        """
        metrics = device.get("metrics") or {}
        scores: dict[str, float] = {}

        link_quality = _as_float(metrics.get("link_quality"))
        scores["link_quality"] = (
            max(0.0, min(100.0, link_quality / 255 * 100))
            if link_quality is not None
            else 50.0
        )

        battery = _as_float(metrics.get("battery"))
        if battery is not None:
            scores["battery"] = max(0.0, min(100.0, battery))

        if reconnect_rate <= 0:
            scores["reconnect_rate"] = 100.0
        elif reconnect_rate >= 10:
            scores["reconnect_rate"] = 0.0
        else:
            scores["reconnect_rate"] = 100.0 - reconnect_rate * 10

        scores["connectivity"] = self.compute_connectivity_score(device, now)

        total_weight = sum(self.weights[name] for name in scores)
        total = sum(score * self.weights[name] for name, score in scores.items())
        return round(max(0.0, min(100.0, total / total_weight)), 1)

    def check_battery_drain_warning(
        self, battery_trend: float | None, threshold: float | None = None
    ) -> bool:
        """Return True when the battery drains faster than the threshold."""
        if battery_trend is None:
            return False
        if threshold is None:
            threshold = self.battery_drain_threshold
        return battery_trend < -threshold

    def check_connectivity_warning(
        self,
        device: Mapping[str, Any],
        reconnect_rate: float = 0.0,
        reconnect_rate_threshold: float = DEFAULT_RECONNECT_RATE_THRESHOLD,
        now: datetime | None = None,
    ) -> bool:
        """Return True when the device has a connectivity problem.

        - it flaps (reconnect rate at or above the threshold), or
        - Zigbee2MQTT reports it offline, or
        - availability is unknown and it hasn't been seen for longer than
          its device-type dependent timeout.
        """
        if reconnect_rate >= reconnect_rate_threshold:
            return True
        available = device.get("available")
        if available is not None:
            return available is False
        last_seen = as_datetime((device.get("metrics") or {}).get("last_seen"))
        if last_seen is None:
            return False
        now = now or dt_util.utcnow()
        return now - last_seen > self.connectivity_timeout(device)
