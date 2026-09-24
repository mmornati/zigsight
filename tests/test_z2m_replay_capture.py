"""Unit tests for the mosquitto_sub -v capture-file loader in z2m_replay.

These exercise the pure parsing/redaction helpers used both by pytest (for
recorded fixtures) and by scripts/z2m_replay.py (for replaying a capture
recorded read-only from a production broker). No Home Assistant dependency.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.z2m_replay import (
    REDACTED_PLACEHOLDER,
    capture_messages,
    infer_retain,
    iter_capture_lines,
    parse_capture_line,
    redact_bridge_info,
)


def test_parse_capture_line_splits_on_first_space() -> None:
    assert parse_capture_line('zigbee2mqtt/Kitchen {"state": "ON"}') == (
        "zigbee2mqtt/Kitchen",
        '{"state": "ON"}',
    )


def test_parse_capture_line_blank_returns_none() -> None:
    assert parse_capture_line("\n") is None
    assert parse_capture_line("   \n") is None


def test_parse_capture_line_no_separator_raises() -> None:
    with pytest.raises(ValueError, match="no topic/payload separator"):
        parse_capture_line("zigbee2mqtt/bridge/state")


def test_parse_capture_line_empty_payload_ok() -> None:
    # mosquitto_sub prints "topic " (trailing space, empty payload) for an
    # empty/retained-clear message.
    assert parse_capture_line("zigbee2mqtt/bridge/state ") == (
        "zigbee2mqtt/bridge/state",
        "",
    )


def test_iter_capture_lines_skips_blanks() -> None:
    text = "zigbee2mqtt/a 1\n\nzigbee2mqtt/b 2\n   \n"
    assert list(iter_capture_lines(text)) == [
        ("zigbee2mqtt/a", "1"),
        ("zigbee2mqtt/b", "2"),
    ]


@pytest.mark.parametrize(
    ("topic", "expected"),
    [
        ("zigbee2mqtt/bridge/state", True),
        ("zigbee2mqtt/bridge/info", True),
        ("zigbee2mqtt/bridge/devices", True),
        ("zigbee2mqtt/Kitchen/availability", True),
        ("zigbee2mqtt/Kitchen/Motion Sensor/availability", True),
        ("zigbee2mqtt/Kitchen", False),
        ("zigbee2mqtt/Kitchen/set", False),
        ("zigbee2mqtt/bridge/response/networkmap", False),
    ],
)
def test_infer_retain(topic: str, expected: bool) -> None:
    assert infer_retain(topic) is expected


def test_redact_bridge_info_strips_network_key_and_mqtt_credentials() -> None:
    payload = json.dumps(
        {
            "config": {
                "advanced": {"network_key": "01:02:03", "pan_id": 6754},
                "mqtt": {
                    "server": "mqtt://core-mosquitto:1883",
                    "user": "addons",
                    "password": "hunter2",
                },
            },
            "version": "2.1.3",
        }
    )
    redacted = json.loads(redact_bridge_info("zigbee2mqtt/bridge/info", payload))

    assert redacted["config"]["advanced"]["network_key"] == REDACTED_PLACEHOLDER
    assert redacted["config"]["mqtt"]["password"] == REDACTED_PLACEHOLDER
    assert redacted["config"]["mqtt"]["user"] == REDACTED_PLACEHOLDER
    # Unrelated fields survive untouched.
    assert redacted["config"]["advanced"]["pan_id"] == 6754
    assert redacted["version"] == "2.1.3"


def test_redact_bridge_info_passthrough_for_other_topics() -> None:
    payload = '{"state": "ON"}'
    assert redact_bridge_info("zigbee2mqtt/Kitchen", payload) == payload


def test_redact_bridge_info_tolerates_non_json_or_missing_keys() -> None:
    assert redact_bridge_info("zigbee2mqtt/bridge/info", "not json") == "not json"
    assert redact_bridge_info("zigbee2mqtt/bridge/info", "{}") == "{}"


def test_capture_messages_from_file(tmp_path: Path) -> None:
    capture = tmp_path / "capture.txt"
    capture.write_text(
        "\n".join(
            [
                'zigbee2mqtt/bridge/state {"state": "online"}',
                'zigbee2mqtt/bridge/info {"config": {"advanced": {"network_key": "secret"}}}',
                'zigbee2mqtt/Kitchen/availability {"state": "online"}',
                'zigbee2mqtt/Kitchen {"state": "ON", "linkquality": 200}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    messages = capture_messages(capture)

    assert [m.topic for m in messages] == [
        "zigbee2mqtt/bridge/state",
        "zigbee2mqtt/bridge/info",
        "zigbee2mqtt/Kitchen/availability",
        "zigbee2mqtt/Kitchen",
    ]
    assert [m.retain for m in messages] == [True, True, True, False]
    bridge_info_payload = json.loads(messages[1].payload)
    assert (
        bridge_info_payload["config"]["advanced"]["network_key"] == REDACTED_PLACEHOLDER
    )
    assert "secret" not in messages[1].payload


def test_capture_messages_rewrites_base_topic(tmp_path: Path) -> None:
    capture = tmp_path / "capture.txt"
    capture.write_text(
        'zigbee2mqtt/Kitchen {"state": "ON"}\nzigbee2mqtt/bridge/state {"state": "online"}\n',
        encoding="utf-8",
    )

    messages = capture_messages(capture, base_topic="z2m-test")

    assert [m.topic for m in messages] == ["z2m-test/Kitchen", "z2m-test/bridge/state"]
