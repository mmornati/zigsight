"""Zigbee channel recommendation based on Wi-Fi interference analysis."""

from __future__ import annotations

from typing import Any

# Wi-Fi channel to frequency mapping (2.4 GHz)
WIFI_CHANNEL_FREQ = {
    1: 2412,
    2: 2417,
    3: 2422,
    4: 2427,
    5: 2432,
    6: 2437,
    7: 2442,
    8: 2447,
    9: 2452,
    10: 2457,
    11: 2462,
    12: 2467,
    13: 2472,
    14: 2484,
}

# Zigbee channel to frequency mapping (2.4 GHz)
ZIGBEE_CHANNEL_FREQ = {
    11: 2405,
    12: 2410,
    13: 2415,
    14: 2420,
    15: 2425,
    16: 2430,
    17: 2435,
    18: 2440,
    19: 2445,
    20: 2450,
    21: 2455,
    22: 2460,
    23: 2465,
    24: 2470,
    25: 2475,
    26: 2480,
}

# Recommended Zigbee channels for evaluation
RECOMMENDED_ZIGBEE_CHANNELS = [11, 15, 20, 25]


def calculate_overlap_factor(
    wifi_channel: int, zigbee_channel: int, rssi: float
) -> float:
    """Calculate interference factor between Wi-Fi and Zigbee channels.

    Args:
        wifi_channel: Wi-Fi channel number (1-14)
        zigbee_channel: Zigbee channel number (11-26)
        rssi: Wi-Fi access point RSSI in dBm (typically -30 to -90)

    Returns:
        Interference factor (0-100), where higher means more interference
    """
    if wifi_channel not in WIFI_CHANNEL_FREQ:
        return 0.0

    if zigbee_channel not in ZIGBEE_CHANNEL_FREQ:
        return 0.0

    # Calculate frequency distance
    wifi_freq = WIFI_CHANNEL_FREQ[wifi_channel]
    zigbee_freq = ZIGBEE_CHANNEL_FREQ[zigbee_channel]
    freq_distance = abs(wifi_freq - zigbee_freq)

    # Wi-Fi channels have ~22 MHz bandwidth, Zigbee has ~2 MHz
    # Significant overlap occurs within ~11 MHz
    if freq_distance > 22:
        # No overlap
        return 0.0

    # Calculate overlap factor based on frequency distance
    # Closer frequencies = more overlap
    overlap_percentage = max(0, 1 - (freq_distance / 22))

    # Factor in signal strength (RSSI)
    # Normalize RSSI: -30 dBm (strong) to -90 dBm (weak)
    # Strong signals cause more interference
    normalized_rssi = max(0, min(100, (rssi + 90) * 100 / 60))

    # Combine overlap and RSSI
    interference_factor = overlap_percentage * normalized_rssi

    return interference_factor


def score_zigbee_channel(
    zigbee_channel: int, wifi_aps: list[dict[str, Any]]
) -> float:
    """Calculate interference score for a Zigbee channel.

    Args:
        zigbee_channel: Zigbee channel number (11-26)
        wifi_aps: List of Wi-Fi access points with 'channel' and 'rssi' keys

    Returns:
        Interference score (0-100), where 0 is best (no interference)
        and 100 is worst (maximum interference)
    """
    total_interference = 0.0

    for ap in wifi_aps:
        wifi_channel = ap.get("channel")
        rssi = ap.get("rssi", -90)

        if wifi_channel is None:
            continue

        interference = calculate_overlap_factor(wifi_channel, zigbee_channel, rssi)
        total_interference += interference

    # Cap the score at 100
    return min(100.0, total_interference)


def recommend_zigbee_channel(
    wifi_aps: list[dict[str, Any]]
) -> dict[str, Any]:
    """Recommend the best Zigbee channel based on Wi-Fi interference.

    Args:
        wifi_aps: List of Wi-Fi access points, each with:
            - channel: Wi-Fi channel number (1-14)
            - rssi: Signal strength in dBm
            - ssid (optional): Network name for logging

    Returns:
        Dictionary with:
            - recommended_channel: Best Zigbee channel (11, 15, 20, or 25)
            - scores: Dict of {channel: score} for all evaluated channels
            - explanation: Human-readable explanation of the recommendation
    """
    if not wifi_aps:
        # No Wi-Fi data, default to channel 25 (least overlap with common Wi-Fi channels)
        return {
            "recommended_channel": 25,
            "scores": {11: 0, 15: 0, 20: 0, 25: 0},
            "explanation": (
                "No Wi-Fi interference data available. "
                "Defaulting to Zigbee channel 25 (common default)."
            ),
        }

    # Score each recommended Zigbee channel
    scores = {}
    for zigbee_ch in RECOMMENDED_ZIGBEE_CHANNELS:
        scores[zigbee_ch] = score_zigbee_channel(zigbee_ch, wifi_aps)

    # Find channel with lowest interference
    best_channel = min(scores.items(), key=lambda x: x[1])[0]
    best_score = scores[best_channel]

    # Generate explanation
    wifi_channel_summary: dict[int, list[float]] = {}
    for ap in wifi_aps:
        ch = ap.get("channel")
        if ch:
            if ch not in wifi_channel_summary:
                wifi_channel_summary[ch] = []
            wifi_channel_summary[ch].append(ap.get("rssi", -90))

    # Summarize Wi-Fi usage
    wifi_channels_used = sorted(wifi_channel_summary.keys())
    wifi_summary = ", ".join(
        f"Ch{ch} ({len(wifi_channel_summary[ch])} APs)"
        for ch in wifi_channels_used[:5]  # Show first 5
    )

    explanation = (
        f"Analyzed {len(wifi_aps)} Wi-Fi access points on channels: {wifi_summary}. "
        f"Zigbee channel {best_channel} has the lowest interference score ({best_score:.1f}/100). "
    )

    # Add context about the recommendation
    if best_score < 20:
        explanation += "This channel has minimal Wi-Fi interference."
    elif best_score < 50:
        explanation += "This channel has moderate Wi-Fi interference."
    else:
        explanation += "All channels have significant interference; this is the best available option."

    return {
        "recommended_channel": best_channel,
        "scores": scores,
        "explanation": explanation,
    }
