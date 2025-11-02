"""Analytics engine for ZigSight metrics computation."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

_LOGGER = logging.getLogger(__name__)

# Default thresholds
DEFAULT_RECONNECT_RATE_WINDOW_HOURS = 24
DEFAULT_BATTERY_DRAIN_THRESHOLD = 10  # percentage drop per hour
DEFAULT_MIN_BATTERY_FOR_TREND = 20  # minimum battery % to compute trend
DEFAULT_HEALTH_SCORE_WEIGHTS = {
    "link_quality": 0.3,
    "battery": 0.2,
    "reconnect_rate": 0.3,
    "connectivity": 0.2,
}


class DeviceAnalytics:
    """Compute analytics metrics for a Zigbee device."""

    def __init__(
        self,
        reconnect_rate_window_hours: int = DEFAULT_RECONNECT_RATE_WINDOW_HOURS,
        battery_drain_threshold: float = DEFAULT_BATTERY_DRAIN_THRESHOLD,
        min_battery_for_trend: int = DEFAULT_MIN_BATTERY_FOR_TREND,
    ) -> None:
        """Initialize analytics engine with thresholds."""
        self.reconnect_rate_window_hours = reconnect_rate_window_hours
        self.battery_drain_threshold = battery_drain_threshold
        self.min_battery_for_trend = min_battery_for_trend
        self.weights = DEFAULT_HEALTH_SCORE_WEIGHTS.copy()

    def compute_reconnect_rate(
        self, device_history: list[dict[str, Any]], window_hours: int | None = None
    ) -> float:
        """Compute reconnect rate (events per hour) over a sliding window.

        Algorithm:
        - Analyze history entries for gaps > 5 minutes
        - Count reconnection events in the specified time window
        - Return rate as events per hour

        Args:
            device_history: List of historical metric entries
            window_hours: Time window in hours (default: self.reconnect_rate_window_hours)

        Returns:
            Reconnect rate (events per hour) or 0.0 if insufficient data
        """
        if window_hours is None:
            window_hours = self.reconnect_rate_window_hours

        if not device_history or len(device_history) < 2:
            return 0.0

        now = datetime.now()
        window_start = now - timedelta(hours=window_hours)

        reconnect_events = 0
        previous_timestamp = None

        # Sort history by timestamp
        sorted_history = sorted(
            device_history,
            key=lambda x: x.get("timestamp", ""),
        )

        for entry in sorted_history:
            try:
                timestamp_str = entry.get("timestamp")
                if not timestamp_str:
                    continue

                timestamp = datetime.fromisoformat(timestamp_str)
                if timestamp < window_start:
                    continue

                if previous_timestamp:
                    # Check if gap is > 5 minutes (reconnection event)
                    time_diff = (timestamp - previous_timestamp).total_seconds()
                    if time_diff > 300:  # 5 minutes
                        reconnect_events += 1

                previous_timestamp = timestamp
            except (ValueError, TypeError, KeyError):
                continue

        # Calculate rate per hour
        if window_hours > 0:
            return reconnect_events / window_hours
        return 0.0

    def compute_battery_trend(
        self, device_history: list[dict[str, Any]], window_hours: int = 24
    ) -> float | None:
        """Compute battery trend (percentage change per hour).

        Algorithm:
        - Extract battery values from history within time window
        - Filter entries with valid battery readings
        - Compute linear regression slope to get trend
        - Return percentage change per hour

        Args:
            device_history: List of historical metric entries
            window_hours: Time window in hours (default: 24)

        Returns:
            Battery trend (percentage per hour) or None if insufficient data
        """
        if not device_history:
            return None

        now = datetime.now()
        window_start = now - timedelta(hours=window_hours)

        battery_readings: list[tuple[float, datetime]] = []

        for entry in device_history:
            try:
                timestamp_str = entry.get("timestamp")
                if not timestamp_str:
                    continue

                timestamp = datetime.fromisoformat(timestamp_str)
                if timestamp < window_start:
                    continue

                metrics = entry.get("metrics", {})
                battery = metrics.get("battery") or metrics.get("battery_percent")

                if battery is not None:
                    try:
                        battery_val = float(battery)
                        if battery_val >= self.min_battery_for_trend:
                            battery_readings.append((battery_val, timestamp))
                    except (ValueError, TypeError):
                        continue
            except (ValueError, TypeError, KeyError):
                continue

        if len(battery_readings) < 2:
            return None

        # Sort by timestamp
        battery_readings.sort(key=lambda x: x[1])

        # Simple linear regression
        n = len(battery_readings)
        sum_t = sum(
            (ts - battery_readings[0][1]).total_seconds() / 3600
            for _, ts in battery_readings
        )
        sum_b = sum(bat for bat, _ in battery_readings)
        sum_tb = sum(
            (ts - battery_readings[0][1]).total_seconds() / 3600 * bat
            for bat, ts in battery_readings
        )
        sum_t2 = sum(
            ((ts - battery_readings[0][1]).total_seconds() / 3600) ** 2
            for _, ts in battery_readings
        )

        # Calculate slope (battery change per hour)
        if sum_t2 == 0:
            return None

        slope = (n * sum_tb - sum_t * sum_b) / (n * sum_t2 - sum_t**2)
        return round(slope, 2)

    def compute_health_score(
        self,
        device_data: dict[str, Any],
        device_history: list[dict[str, Any]],
    ) -> float:
        """Compute aggregated health score for a device (0-100).

        Algorithm:
        - Extract current metrics: link_quality, battery, reconnect_rate, connectivity
        - Normalize each metric to 0-100 scale
        - Apply weighted average using configured weights
        - Return score from 0 (poor) to 100 (excellent)

        Scoring components:
        - Link quality: normalized to 100 (higher is better)
        - Battery: percentage (higher is better)
        - Reconnect rate: inverted (lower is better, capped at reasonable max)
        - Connectivity: based on last_seen recency (better if recent)

        Args:
            device_data: Current device data dictionary
            device_history: List of historical metric entries

        Returns:
            Health score (0-100) where 100 is excellent
        """
        scores = {}

        # Extract current metrics
        metrics = device_data.get("metrics", {})
        link_quality = metrics.get("link_quality")
        battery = metrics.get("battery")
        last_seen_str = metrics.get("last_seen")

        # Link quality score (normalize to 100, typical range is 0-255)
        if link_quality is not None:
            try:
                link_val = float(link_quality)
                # Normalize 0-255 to 0-100
                scores["link_quality"] = min(100, (link_val / 255) * 100)
            except (ValueError, TypeError):
                scores["link_quality"] = 50  # Default neutral score
        else:
            scores["link_quality"] = 50

        # Battery score (already 0-100)
        if battery is not None:
            try:
                battery_val = float(battery)
                scores["battery"] = max(0, min(100, battery_val))
            except (ValueError, TypeError):
                scores["battery"] = 50
        else:
            scores["battery"] = 50

        # Reconnect rate score (inverted, lower is better)
        reconnect_rate = self.compute_reconnect_rate(device_history)
        # Convert rate to score: 0 reconnects/hour = 100, 10+ reconnects/hour = 0
        if reconnect_rate <= 0:
            scores["reconnect_rate"] = 100
        elif reconnect_rate >= 10:
            scores["reconnect_rate"] = 0
        else:
            scores["reconnect_rate"] = 100 - (reconnect_rate * 10)

        # Connectivity score (based on last_seen recency)
        if last_seen_str:
            try:
                last_seen = datetime.fromisoformat(last_seen_str)
                seconds_since_update = (datetime.now() - last_seen).total_seconds()
                # Recent (< 5 min) = 100, old (> 1 hour) = 0
                if seconds_since_update < 300:
                    scores["connectivity"] = 100
                elif seconds_since_update > 3600:
                    scores["connectivity"] = 0
                else:
                    # Linear decay from 100 to 0
                    scores["connectivity"] = 100 - (
                        (seconds_since_update - 300) / 3300 * 100
                    )
            except (ValueError, TypeError):
                scores["connectivity"] = 50
        else:
            scores["connectivity"] = 0

        # Compute weighted average
        total_score = (
            scores.get("link_quality", 50) * self.weights.get("link_quality", 0.25)
            + scores.get("battery", 50) * self.weights.get("battery", 0.25)
            + scores.get("reconnect_rate", 50)
            * self.weights.get("reconnect_rate", 0.25)
            + scores.get("connectivity", 50) * self.weights.get("connectivity", 0.25)
        )

        return round(max(0, min(100, total_score)), 1)

    def check_battery_drain_warning(
        self, device_history: list[dict[str, Any]], threshold: float | None = None
    ) -> bool:
        """Check if battery drain warning should be triggered.

        Algorithm:
        - Compute battery trend over last 24 hours
        - Compare against threshold (default: 10% per hour)
        - Return True if drain rate exceeds threshold

        Args:
            device_history: List of historical metric entries
            threshold: Drain threshold in %/hour (default: self.battery_drain_threshold)

        Returns:
            True if battery drain warning should be triggered
        """
        if threshold is None:
            threshold = self.battery_drain_threshold

        battery_trend = self.compute_battery_trend(device_history)
        if battery_trend is None:
            return False

        # Negative trend means draining (more negative = worse)
        return battery_trend < -threshold

    def check_connectivity_warning(
        self, device_data: dict[str, Any], reconnect_rate_threshold: float = 5.0
    ) -> bool:
        """Check if connectivity warning should be triggered.

        Algorithm:
        - Get device history and compute reconnect rate
        - Check if reconnect rate exceeds threshold
        - Also check if last_seen is too old (> 1 hour)

        Args:
            device_data: Current device data dictionary
            reconnect_rate_threshold: Threshold for reconnect rate (default: 5.0 events/hour)

        Returns:
            True if connectivity warning should be triggered
        """
        device_history = device_data.get("history", [])
        reconnect_rate = self.compute_reconnect_rate(device_history)

        if reconnect_rate >= reconnect_rate_threshold:
            return True

        # Also check if device hasn't been seen recently
        metrics = device_data.get("metrics", {})
        last_seen_str = metrics.get("last_seen")
        if last_seen_str:
            try:
                last_seen = datetime.fromisoformat(last_seen_str)
                seconds_since_update = (datetime.now() - last_seen).total_seconds()
                if seconds_since_update > 3600:  # > 1 hour
                    return True
            except (ValueError, TypeError):
                pass

        return False
