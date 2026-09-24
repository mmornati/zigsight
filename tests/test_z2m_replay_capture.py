"""Unit tests for the capture-file loader in z2m_replay.

These exercise the pure parsing/redaction/filtering helpers used both by
pytest (for recorded fixtures) and by scripts/z2m_replay.py (for replaying a
capture recorded read-only from a production broker). No Home Assistant
dependency.
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
    parse_capture_line_json,
    parse_capture_line_tab,
    parse_capture_line_verbose,
    redact_bridge_payload,
)

# --- JSON-lines format (mosquitto_sub -F '%j'), the preferred format --------


def test_parse_capture_line_json_basic() -> None:
    line = json.dumps(
        {"topic": "zigbee2mqtt/Kitchen", "payload": '{"state": "ON"}', "retain": 0}
    )
    assert parse_capture_line_json(line) == (
        "zigbee2mqtt/Kitchen",
        '{"state": "ON"}',
        False,
    )


def test_parse_capture_line_json_survives_spaces_in_topic() -> None:
    # This is the whole point of the JSON format: a friendly name with a
    # space (very common in Zigbee2MQTT) must not be truncated.
    line = json.dumps(
        {
            "topic": "zigbee2mqtt/Living Room Lamp",
            "payload": '{"state": "ON", "brightness": 200}',
            "retain": 1,
        }
    )
    assert parse_capture_line_json(line) == (
        "zigbee2mqtt/Living Room Lamp",
        '{"state": "ON", "brightness": 200}',
        True,
    )


def test_parse_capture_line_json_missing_retain_is_none() -> None:
    line = json.dumps({"topic": "zigbee2mqtt/Kitchen", "payload": "ON"})
    assert parse_capture_line_json(line) == ("zigbee2mqtt/Kitchen", "ON", None)


def test_parse_capture_line_json_blank_returns_none() -> None:
    assert parse_capture_line_json("\n") is None
    assert parse_capture_line_json("   ") is None


def test_parse_capture_line_json_invalid_json_raises() -> None:
    with pytest.raises(ValueError, match="Malformed JSON"):
        parse_capture_line_json("not json")


def test_parse_capture_line_json_missing_topic_raises() -> None:
    with pytest.raises(ValueError, match="missing 'topic'"):
        parse_capture_line_json(json.dumps({"payload": "ON"}))


# --- Tab-separated format (mosquitto_sub -F '%t\t%p') -----------------------


def test_parse_capture_line_tab_survives_spaces_in_topic() -> None:
    assert parse_capture_line_tab('zigbee2mqtt/Living Room Lamp\t{"state": "ON"}') == (
        "zigbee2mqtt/Living Room Lamp",
        '{"state": "ON"}',
    )


def test_parse_capture_line_tab_blank_returns_none() -> None:
    assert parse_capture_line_tab("\n") is None


def test_parse_capture_line_tab_no_separator_raises() -> None:
    with pytest.raises(ValueError, match="tab-separated"):
        parse_capture_line_tab("zigbee2mqtt/bridge/state")


# --- Legacy verbose format (mosquitto_sub -v), space-separated --------------


def test_parse_capture_line_verbose_splits_on_first_space() -> None:
    assert parse_capture_line_verbose('zigbee2mqtt/Kitchen {"state": "ON"}') == (
        "zigbee2mqtt/Kitchen",
        '{"state": "ON"}',
    )


def test_parse_capture_line_verbose_keeps_spaced_topics_with_json_payload() -> None:
    assert parse_capture_line_verbose(
        'zigbee2mqtt/Living Room Lamp {"state": "ON", "note": "a b"}'
    ) == ("zigbee2mqtt/Living Room Lamp", '{"state": "ON", "note": "a b"}')
    assert parse_capture_line_verbose(
        'zigbee2mqtt/bridge/groups [{"friendly_name": "Living Room Lights"}]'
    ) == ("zigbee2mqtt/bridge/groups", '[{"friendly_name": "Living Room Lights"}]')


def test_parse_capture_line_verbose_keeps_spaced_topics_with_plain_payload() -> None:
    assert parse_capture_line_verbose(
        "zigbee2mqtt/Kitchen/Motion Sensor/availability online"
    ) == ("zigbee2mqtt/Kitchen/Motion Sensor/availability", "online")


def test_parse_capture_line_verbose_documented_limitation() -> None:
    # A plain-text payload containing a space is ambiguous in this format:
    # the heuristic splits at the last space. This is why JSON lines / tab
    # are preferred for anything new.
    assert parse_capture_line_verbose("zigbee2mqtt/bridge/logging hello world") == (
        "zigbee2mqtt/bridge/logging hello",
        "world",
    )


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        (
            json.dumps({"topic": "zigbee2mqtt/Living Room Lamp", "payload": "ON"}),
            ("zigbee2mqtt/Living Room Lamp", "ON"),
        ),
        ("zigbee2mqtt/Living Room Lamp\tON", ("zigbee2mqtt/Living Room Lamp", "ON")),
        (
            'zigbee2mqtt/Living Room Lamp {"state": "ON"}',
            ("zigbee2mqtt/Living Room Lamp", '{"state": "ON"}'),
        ),
        ("", None),
        ("\n", None),
    ],
)
def test_parse_capture_line_auto_detects_format(
    line: str, expected: tuple[str, str] | None
) -> None:
    assert parse_capture_line(line) == expected


def test_parse_capture_line_json_blank_record_is_none() -> None:
    assert parse_capture_line("  ") is None


def test_iter_capture_lines_mixed_formats() -> None:
    text = (
        json.dumps({"topic": "zigbee2mqtt/A B", "payload": "1"})
        + "\nzigbee2mqtt/C D\t2\n\nzigbee2mqtt/E F {}\n"
    )
    assert list(iter_capture_lines(text)) == [
        ("zigbee2mqtt/A B", "1"),
        ("zigbee2mqtt/C D", "2"),
        ("zigbee2mqtt/E F", "{}"),
    ]


def test_parse_capture_line_verbose_blank_returns_none() -> None:
    assert parse_capture_line_verbose("\n") is None
    assert parse_capture_line_verbose("   \n") is None


def test_parse_capture_line_verbose_no_separator_raises() -> None:
    with pytest.raises(ValueError, match="no topic/payload separator"):
        parse_capture_line_verbose("zigbee2mqtt/bridge/state")


def test_parse_capture_line_verbose_empty_payload_ok() -> None:
    assert parse_capture_line_verbose("zigbee2mqtt/bridge/state ") == (
        "zigbee2mqtt/bridge/state",
        "",
    )


# --- Retain inference (fallback when the capture format has none) -----------


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


# --- Redaction ----------------------------------------------------------


def test_redact_bridge_payload_strips_known_secret_keys_anywhere_nested() -> None:
    payload = json.dumps(
        {
            "config": {
                "advanced": {
                    "network_key": "01:02:03",
                    "pan_id": 6754,
                    "ext_pan_id": [1, 2, 3],
                },
                "mqtt": {
                    "server": "mqtt://core-mosquitto:1883",
                    "user": "addons",
                    "password": "hunter2",
                },
            },
            "nested": {"deeper": {"auth_token": "abc", "install_code": "xyz"}},
            "version": "2.1.3",
        }
    )
    redacted = json.loads(redact_bridge_payload("zigbee2mqtt/bridge/info", payload))

    assert redacted["config"]["advanced"]["network_key"] == REDACTED_PLACEHOLDER
    assert redacted["config"]["advanced"]["pan_id"] == REDACTED_PLACEHOLDER
    assert redacted["config"]["advanced"]["ext_pan_id"] == REDACTED_PLACEHOLDER
    assert redacted["config"]["mqtt"]["password"] == REDACTED_PLACEHOLDER
    assert redacted["nested"]["deeper"]["auth_token"] == REDACTED_PLACEHOLDER
    assert redacted["nested"]["deeper"]["install_code"] == REDACTED_PLACEHOLDER
    # "user" is not a secret key name any more (only real secrets are
    # redacted, not every MQTT-related field).
    assert redacted["config"]["mqtt"]["user"] == "addons"
    assert redacted["version"] == "2.1.3"


def test_redact_bridge_payload_applies_to_any_bridge_topic_not_just_info() -> None:
    payload = json.dumps({"password": "leak-me"})
    redacted = json.loads(redact_bridge_payload("zigbee2mqtt/bridge/whatever", payload))
    assert redacted["password"] == REDACTED_PLACEHOLDER


def test_redact_bridge_payload_passthrough_for_non_bridge_topics() -> None:
    # A device could coincidentally expose a "password" key; only bridge/*
    # payloads are redacted, not arbitrary device state.
    payload = json.dumps({"state": "ON", "password": "not-actually-a-secret-here"})
    assert redact_bridge_payload("zigbee2mqtt/Kitchen", payload) == payload


def test_redact_bridge_payload_tolerates_non_json_or_missing_keys() -> None:
    assert redact_bridge_payload("zigbee2mqtt/bridge/info", "not json") == "not json"
    assert redact_bridge_payload("zigbee2mqtt/bridge/info", "{}") == "{}"


# --- Full capture loading: format auto-detection, redaction, filtering ------


def test_capture_messages_from_json_lines_file(tmp_path: Path) -> None:
    capture = tmp_path / "capture.jsonl"
    lines = [
        {
            "topic": "zigbee2mqtt/bridge/state",
            "payload": '{"state": "online"}',
            "retain": 1,
        },
        {
            "topic": "zigbee2mqtt/bridge/info",
            "payload": json.dumps({"config": {"advanced": {"network_key": "secret"}}}),
            "retain": 1,
        },
        {
            "topic": "zigbee2mqtt/Living Room Lamp/availability",
            "payload": '{"state": "online"}',
            "retain": 1,
        },
        {
            "topic": "zigbee2mqtt/Living Room Lamp",
            "payload": '{"state": "ON", "linkquality": 200}',
            "retain": 0,
        },
    ]
    capture.write_text(
        "\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8"
    )

    messages = capture_messages(capture)

    assert [m.topic for m in messages] == [
        "zigbee2mqtt/bridge/state",
        "zigbee2mqtt/bridge/info",
        "zigbee2mqtt/Living Room Lamp/availability",
        "zigbee2mqtt/Living Room Lamp",
    ]
    assert [m.retain for m in messages] == [True, True, True, False]
    bridge_info_payload = json.loads(messages[1].payload)
    assert (
        bridge_info_payload["config"]["advanced"]["network_key"] == REDACTED_PLACEHOLDER
    )
    assert "secret" not in messages[1].payload


def test_capture_messages_drops_set_get_and_non_networkmap_bridge_rpc(
    tmp_path: Path,
) -> None:
    capture = tmp_path / "capture.jsonl"
    lines = [
        {"topic": "zigbee2mqtt/Kitchen", "payload": '{"state": "ON"}'},
        {"topic": "zigbee2mqtt/Kitchen/set", "payload": '{"state": "OFF"}'},
        {"topic": "zigbee2mqtt/Kitchen/get", "payload": "{}"},
        {"topic": "zigbee2mqtt/bridge/request/networkmap", "payload": "raw"},
        {"topic": "zigbee2mqtt/bridge/request/permit_join", "payload": "true"},
        {"topic": "zigbee2mqtt/bridge/response/networkmap", "payload": '{"data": {}}'},
        {"topic": "zigbee2mqtt/bridge/response/permit_join", "payload": '{"data": {}}'},
    ]
    capture.write_text(
        "\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8"
    )

    messages = capture_messages(capture)

    assert [m.topic for m in messages] == [
        "zigbee2mqtt/Kitchen",
        "zigbee2mqtt/bridge/response/networkmap",
    ]


def test_capture_messages_from_tab_file_with_spaced_names(tmp_path: Path) -> None:
    capture = tmp_path / "capture.tsv"
    capture.write_text(
        'zigbee2mqtt/Living Room Lamp\t{"state": "ON"}\n'
        'zigbee2mqtt/bridge/state\t{"state": "online"}\n',
        encoding="utf-8",
    )

    messages = capture_messages(capture)

    assert [m.topic for m in messages] == [
        "zigbee2mqtt/Living Room Lamp",
        "zigbee2mqtt/bridge/state",
    ]
    # The Kitchen payload is untouched (not a bridge/* topic); the
    # bridge/state payload round-trips through redact_bridge_payload's JSON
    # re-encoding (compact separators), even though nothing was redacted.
    assert [m.payload for m in messages] == ['{"state": "ON"}', '{"state":"online"}']
    # No explicit retain in this format: falls back to infer_retain.
    assert [m.retain for m in messages] == [False, True]


def test_capture_messages_from_legacy_verbose_file(tmp_path: Path) -> None:
    capture = tmp_path / "capture.txt"
    capture.write_text(
        'zigbee2mqtt/bridge/state {"state": "online"}\n'
        'zigbee2mqtt/Kitchen {"state": "ON", "linkquality": 200}\n',
        encoding="utf-8",
    )

    messages = capture_messages(capture)

    assert [m.topic for m in messages] == [
        "zigbee2mqtt/bridge/state",
        "zigbee2mqtt/Kitchen",
    ]
    assert [m.retain for m in messages] == [True, False]


def test_capture_messages_rewrites_base_topic(tmp_path: Path) -> None:
    capture = tmp_path / "capture.jsonl"
    lines = [
        {"topic": "zigbee2mqtt/Kitchen", "payload": '{"state": "ON"}'},
        {"topic": "zigbee2mqtt/bridge/state", "payload": '{"state": "online"}'},
    ]
    capture.write_text(
        "\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8"
    )

    messages = capture_messages(capture, base_topic="z2m-test")

    assert [m.topic for m in messages] == ["z2m-test/Kitchen", "z2m-test/bridge/state"]
