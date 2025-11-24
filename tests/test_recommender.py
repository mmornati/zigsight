"""Tests for Zigbee channel recommender."""

from __future__ import annotations

from custom_components.zigsight.recommender import (
    calculate_overlap_factor,
    recommend_zigbee_channel,
    score_zigbee_channel,
)


def test_calculate_overlap_factor_no_overlap() -> None:
    """Test overlap calculation when channels don't overlap."""
    # Wi-Fi channel 1 (2412 MHz) and Zigbee channel 25 (2475 MHz)
    # Distance: 63 MHz - no overlap
    factor = calculate_overlap_factor(1, 25, -50)
    assert factor == 0.0


def test_calculate_overlap_factor_full_overlap() -> None:
    """Test overlap calculation with maximum overlap."""
    # Wi-Fi channel 6 (2437 MHz) and Zigbee channel 17 (2435 MHz)
    # Distance: 2 MHz - significant overlap
    factor = calculate_overlap_factor(6, 17, -30)
    assert factor > 80  # Strong signal with high overlap


def test_calculate_overlap_factor_weak_signal() -> None:
    """Test overlap calculation with weak signal."""
    # Same channels but weak signal should result in lower interference
    factor_strong = calculate_overlap_factor(6, 17, -30)
    factor_weak = calculate_overlap_factor(6, 17, -80)
    assert factor_weak < factor_strong


def test_calculate_overlap_factor_invalid_channels() -> None:
    """Test overlap calculation with invalid channels."""
    # Invalid Wi-Fi channel
    assert calculate_overlap_factor(99, 15, -50) == 0.0

    # Invalid Zigbee channel
    assert calculate_overlap_factor(6, 99, -50) == 0.0


def test_score_zigbee_channel_no_aps() -> None:
    """Test scoring with no Wi-Fi APs."""
    score = score_zigbee_channel(15, [])
    assert score == 0.0


def test_score_zigbee_channel_single_ap() -> None:
    """Test scoring with single Wi-Fi AP."""
    aps = [{"channel": 6, "rssi": -50}]
    score = score_zigbee_channel(15, aps)
    assert score >= 0.0
    assert score <= 100.0


def test_score_zigbee_channel_multiple_aps() -> None:
    """Test scoring with multiple Wi-Fi APs."""
    aps = [
        {"channel": 1, "rssi": -40},
        {"channel": 6, "rssi": -50},
        {"channel": 11, "rssi": -60},
    ]
    score = score_zigbee_channel(15, aps)
    assert score >= 0.0
    assert score <= 100.0


def test_score_zigbee_channel_missing_rssi() -> None:
    """Test scoring with missing RSSI data."""
    aps = [{"channel": 6}]
    score = score_zigbee_channel(15, aps)
    # Should use default RSSI of -90 (weak signal)
    assert score >= 0.0


def test_score_zigbee_channel_missing_channel() -> None:
    """Test scoring with missing channel data."""
    aps = [{"rssi": -50}]
    score = score_zigbee_channel(15, aps)
    assert score == 0.0


def test_recommend_zigbee_channel_no_aps() -> None:
    """Test recommendation with no Wi-Fi data."""
    result = recommend_zigbee_channel([])

    assert result["recommended_channel"] == 25
    assert "scores" in result
    assert "explanation" in result
    assert len(result["scores"]) == 4  # 4 recommended channels


def test_recommend_zigbee_channel_single_ap() -> None:
    """Test recommendation with single Wi-Fi AP."""
    aps = [{"channel": 1, "rssi": -40, "ssid": "TestNetwork"}]
    result = recommend_zigbee_channel(aps)

    assert result["recommended_channel"] in [11, 15, 20, 25]
    assert "scores" in result
    assert "explanation" in result
    assert len(result["scores"]) == 4


def test_recommend_zigbee_channel_busy_spectrum() -> None:
    """Test recommendation with busy spectrum."""
    # Simulate busy 2.4 GHz spectrum
    aps = [
        {"channel": 1, "rssi": -40},
        {"channel": 1, "rssi": -50},
        {"channel": 6, "rssi": -45},
        {"channel": 6, "rssi": -55},
        {"channel": 11, "rssi": -50},
        {"channel": 11, "rssi": -60},
    ]
    result = recommend_zigbee_channel(aps)

    # Should recommend a channel (any of the 4)
    assert result["recommended_channel"] in [11, 15, 20, 25]

    # All channels should have scores
    assert len(result["scores"]) == 4
    for score in result["scores"].values():
        assert score >= 0.0
        assert score <= 100.0


def test_recommend_zigbee_channel_explanation_quality() -> None:
    """Test that explanation contains useful information."""
    aps = [
        {"channel": 1, "rssi": -40},
        {"channel": 6, "rssi": -50},
    ]
    result = recommend_zigbee_channel(aps)

    explanation = result["explanation"]
    assert "Analyzed" in explanation
    assert str(len(aps)) in explanation
    assert str(result["recommended_channel"]) in explanation


def test_recommend_zigbee_channel_scores_are_different() -> None:
    """Test that different APs produce different scores."""
    # Wi-Fi on channel 1 should favor Zigbee channels farther away
    aps_ch1 = [{"channel": 1, "rssi": -40}]
    result_ch1 = recommend_zigbee_channel(aps_ch1)

    # Wi-Fi on channel 11 should favor different Zigbee channels
    aps_ch11 = [{"channel": 11, "rssi": -40}]
    result_ch11 = recommend_zigbee_channel(aps_ch11)

    # The scores should be different for at least one channel
    assert result_ch1["scores"] != result_ch11["scores"]


def test_score_caps_at_100() -> None:
    """Test that scores are capped at 100 even with many APs."""
    # Create many strong APs
    aps = [{"channel": 6, "rssi": -30} for _ in range(100)]
    score = score_zigbee_channel(17, aps)  # Channel 17 overlaps with Wi-Fi ch 6
    assert score <= 100.0


def test_recommend_preferred_channels_only() -> None:
    """Test that only preferred channels (11, 15, 20, 25) are in scores."""
    aps = [{"channel": 6, "rssi": -50}]
    result = recommend_zigbee_channel(aps)

    assert set(result["scores"].keys()) == {11, 15, 20, 25}


def test_recommend_best_channel_has_lowest_score() -> None:
    """Test that recommended channel has the lowest interference score."""
    aps = [{"channel": 6, "rssi": -40}]
    result = recommend_zigbee_channel(aps)

    recommended = result["recommended_channel"]
    recommended_score = result["scores"][recommended]

    # Recommended channel should have lowest or equal score
    for _channel, score in result["scores"].items():
        assert recommended_score <= score
