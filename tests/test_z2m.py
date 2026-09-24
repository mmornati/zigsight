"""Unit tests for the Zigbee2MQTT protocol parser."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from homeassistant.util import dt as dt_util

from custom_components.zigsight.z2m import (
    TopicKind,
    classify_topic,
    decode_payload,
    extract_metrics,
    parse_availability,
    parse_bridge_devices,
    parse_bridge_info,
    parse_bridge_state,
    parse_device,
    parse_json,
    parse_last_seen,
    parse_networkmap_response,
)

from .z2m_replay import (
    encode_payload,
    load_fixture_text,
    load_session,
    session_messages,
)

NAMES = {"Kitchen", "Kitchen/Motion Sensor", "Living Room Lamp", "a/b/c"}
NOW = datetime(2026, 9, 24, 8, 20, tzinfo=dt_util.UTC)


@pytest.mark.parametrize(
    ("topic", "kind", "name", "suffix"),
    [
        ("zigbee2mqtt/bridge/devices", TopicKind.BRIDGE_DEVICES, None, ""),
        ("zigbee2mqtt/bridge/info", TopicKind.BRIDGE_INFO, None, ""),
        ("zigbee2mqtt/bridge/state", TopicKind.BRIDGE_STATE, None, ""),
        (
            "zigbee2mqtt/bridge/response/networkmap",
            TopicKind.BRIDGE_NETWORKMAP,
            None,
            "",
        ),
        ("zigbee2mqtt/bridge/logging", TopicKind.BRIDGE_OTHER, None, "logging"),
        ("zigbee2mqtt/Kitchen", TopicKind.DEVICE_STATE, "Kitchen", ""),
        ("zigbee2mqtt/Kitchen/set", TopicKind.DEVICE_OTHER, "Kitchen", "set"),
        ("zigbee2mqtt/Kitchen/get", TopicKind.DEVICE_OTHER, "Kitchen", "get"),
        (
            "zigbee2mqtt/Kitchen/set/state",
            TopicKind.DEVICE_OTHER,
            "Kitchen",
            "set/state",
        ),
        (
            "zigbee2mqtt/Kitchen/availability",
            TopicKind.DEVICE_AVAILABILITY,
            "Kitchen",
            "availability",
        ),
        (
            "zigbee2mqtt/Kitchen/Motion Sensor",
            TopicKind.DEVICE_STATE,
            "Kitchen/Motion Sensor",
            "",
        ),
        (
            "zigbee2mqtt/Kitchen/Motion Sensor/availability",
            TopicKind.DEVICE_AVAILABILITY,
            "Kitchen/Motion Sensor",
            "availability",
        ),
        (
            "zigbee2mqtt/Kitchen/Motion Sensor/set",
            TopicKind.DEVICE_OTHER,
            "Kitchen/Motion Sensor",
            "set",
        ),
        ("zigbee2mqtt/a/b/c", TopicKind.DEVICE_STATE, "a/b/c", ""),
        # Groups and other unknown names
        ("zigbee2mqtt/Living Room Lights", TopicKind.UNKNOWN, "Living Room Lights", ""),
        (
            "zigbee2mqtt/New Device/availability",
            TopicKind.UNKNOWN,
            "New Device",
            "availability",
        ),
        ("other/Kitchen", TopicKind.UNKNOWN, None, ""),
        ("zigbee2mqtt/", TopicKind.UNKNOWN, None, ""),
        ("zigbee2mqtt", TopicKind.UNKNOWN, None, ""),
    ],
)
def test_classify_topic(
    topic: str, kind: TopicKind, name: str | None, suffix: str
) -> None:
    """Topics resolve by longest known friendly name."""
    parsed = classify_topic(topic, "zigbee2mqtt", NAMES)
    assert parsed.kind is kind
    assert parsed.friendly_name == name
    assert parsed.suffix == suffix


def test_classify_topic_nested_prefix() -> None:
    """Base topics may contain '/'."""
    parsed = classify_topic("home/z2m/Kitchen", "home/z2m/", NAMES)
    assert parsed.kind is TopicKind.DEVICE_STATE
    assert parsed.friendly_name == "Kitchen"


def test_parse_bridge_devices_fixture() -> None:
    """The recorded device list parses into typed devices."""
    devices = parse_bridge_devices(load_fixture_text("bridge_devices.json"))
    assert devices is not None
    by_name = {device.friendly_name: device for device in devices}
    assert len(devices) == 6

    coordinator = by_name["Coordinator"]
    assert coordinator.is_coordinator
    assert coordinator.model is None

    lamp = by_name["Living Room Lamp"]
    assert lamp.type == "Router"
    assert lamp.vendor == "Philips"
    assert lamp.model == "9290022166"
    assert lamp.description == "Hue white and color ambiance E26/E27"
    assert not lamp.is_battery_powered
    assert not lamp.exposes_voltage

    climate = by_name["Bedroom Climate"]
    assert climate.ieee_address == "0x00158d0001a2b3c4"
    assert climate.type == "EndDevice"
    assert climate.is_battery_powered
    assert climate.exposes_voltage
    assert climate.voltage_unit == "mV"
    assert climate.interview_state == "SUCCESSFUL"

    motion = by_name["Kitchen/Motion Sensor"]
    assert motion.is_battery_powered and not motion.exposes_voltage

    assert by_name["Old Door Sensor"].disabled
    assert climate.as_dict()["model_id"] == "lumi.weather"


def test_parse_bridge_devices_edge_cases() -> None:
    """Invalid entries are skipped; legacy interview fields are understood."""
    assert parse_bridge_devices("not json") is None
    assert parse_bridge_devices('{"a": 1}') is None
    devices = parse_bridge_devices(
        encode_payload(
            [
                "junk",
                {"friendly_name": "no ieee"},
                {"ieee_address": "0xABC", "interviewing": True},
                {"ieee_address": "0xabc", "friendly_name": "duplicate"},
                {
                    "ieee_address": "0xdef",
                    "friendly_name": "old",
                    "interview_completed": False,
                    "network_address": "bad",
                    "definition": {"exposes": "bad"},
                },
                {"ieee_address": "0x123", "interview_completed": True},
            ]
        )
    )
    assert devices is not None
    assert [d.ieee_address for d in devices] == ["0xabc", "0xdef", "0x123"]
    assert devices[0].friendly_name == "0xabc"
    assert devices[0].interview_state == "IN_PROGRESS"
    assert devices[0].type == "Unknown"
    assert devices[1].interview_state == "PENDING"
    assert devices[1].network_address is None
    assert devices[2].interview_state == "SUCCESSFUL"
    assert parse_device({"ieee_address": "0x1"}) is not None
    assert parse_device({}) is None


def test_parse_bridge_info_fixture() -> None:
    """Only whitelisted fields are extracted."""
    info = parse_bridge_info(load_fixture_text("bridge_info.json"))
    assert info is not None
    assert info.version == "2.1.3"
    assert info.channel == 15
    assert info.pan_id == 6754
    assert info.coordinator_ieee == "0x00124b0024c1a2b3"
    assert info.coordinator_type == "zStack3x0"
    assert info.coordinator_revision == "20240710"
    assert info.availability_enabled is True
    assert info.active_timeout == timedelta(minutes=10)
    assert info.passive_timeout == timedelta(minutes=1500)
    assert info.last_seen_format == "ISO_8601_local"
    assert info.permit_join is False
    dumped = repr(info.as_dict())
    assert "not-a-real-password" not in dumped
    assert "HIDDEN" not in dumped


def test_parse_bridge_info_variants() -> None:
    """Zigbee2MQTT 1.x availability shapes and garbage."""
    assert parse_bridge_info("garbage") is None
    assert parse_bridge_info("[]") is None
    legacy = parse_bridge_info(encode_payload({"config": {"availability": True}}))
    assert legacy is not None and legacy.availability_enabled is True
    disabled = parse_bridge_info(
        encode_payload({"config": {"availability": {"enabled": False}}})
    )
    assert disabled is not None and disabled.availability_enabled is False
    v1 = parse_bridge_info(
        encode_payload({"config": {"availability": {"active": {"timeout": "x"}}}})
    )
    assert v1 is not None
    assert v1.availability_enabled is True
    assert v1.active_timeout is None
    assert v1.as_dict()["active_timeout_minutes"] is None


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ('{"state":"online"}', True),
        ('{"state":"offline"}', False),
        ("online", True),
        ("offline", False),
        (b"online", True),
        ('"online"', True),
        ('{"state": 1}', None),
        ("maybe", None),
        ("", None),
    ],
)
def test_parse_availability(payload: str | bytes, expected: bool | None) -> None:
    """JSON and legacy plain availability payloads."""
    assert parse_availability(payload) is expected


def test_parse_bridge_state() -> None:
    """JSON and legacy bridge/state payloads."""
    assert parse_bridge_state('{"state":"online"}') == "online"
    assert parse_bridge_state("offline") == "offline"
    assert parse_bridge_state("nope") is None


def test_parse_json_and_decode() -> None:
    """Invalid JSON returns None without raising."""
    assert parse_json("{bad") is None
    assert parse_json("  ") is None
    assert parse_json(b'{"a": 1}') == {"a": 1}
    assert decode_payload(b"\xff") == "�"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-09-24T10:15:32+02:00", "2026-09-24T08:15:32+00:00"),
        ("2026-09-24T08:15:32.123Z", "2026-09-24T08:15:32.123000+00:00"),
        ("2026-09-24T08:15:32", "2026-09-24T08:15:32+00:00"),
        (1790237732000, "2026-09-24T08:15:32+00:00"),
        (1790237732000.0, "2026-09-24T08:15:32+00:00"),
        ("2030-01-01T00:00:00Z", None),  # in the future
        ("garbage", None),
        (True, None),
        (None, None),
        (1e30, None),
    ],
)
def test_parse_last_seen(value: object, expected: str | None) -> None:
    """ISO strings (UTC/local) and epoch milliseconds."""
    parsed = parse_last_seen(value, NOW)
    assert (parsed.isoformat() if parsed else None) == expected


def test_extract_metrics() -> None:
    """Only present numeric metrics are returned."""
    assert extract_metrics(
        {"linkquality": 72, "battery": "87", "voltage": 2985, "temperature": 21}
    ) == {"link_quality": 72, "battery": 87, "voltage": 2985}
    assert extract_metrics({"battery": "8.5", "linkquality": None}) == {"battery": 8.5}
    assert extract_metrics({"battery": True, "voltage": "x", "linkquality": []}) == {}
    assert extract_metrics({}) == {}


def test_parse_networkmap_fixture() -> None:
    """Raw network map links use IEEE addresses."""
    network_map = parse_networkmap_response(load_fixture_text("networkmap_raw.json"))
    assert network_map is not None
    assert len(network_map.nodes) == 5
    assert len(network_map.links) == 5
    first = network_map.links[0]
    assert first.source == "0x0017880104e45517"
    assert first.target == "0x00124b0024c1a2b3"
    assert first.lqi == 156
    assert first.relationship == 1


def test_parse_networkmap_variants() -> None:
    """Legacy link keys, errors and non raw maps."""
    legacy = parse_networkmap_response(
        encode_payload(
            {
                "data": {
                    "type": "raw",
                    "value": {
                        "nodes": [{"ieeeAddr": "0xA"}, {"no": "ieee"}, "junk"],
                        "links": [
                            {
                                "sourceIeeeAddr": "0xB",
                                "targetIeeeAddr": "0xA",
                                "linkquality": 90,
                            },
                            {"source": {}, "target": {"ieeeAddr": "0xA"}},
                            "junk",
                        ],
                    },
                },
                "status": "ok",
            }
        )
    )
    assert legacy is not None
    assert [n["ieee_address"] for n in legacy.nodes] == ["0xa"]
    assert [(link.source, link.target, link.lqi) for link in legacy.links] == [
        ("0xb", "0xa", 90)
    ]
    assert parse_networkmap_response('{"status":"error","error":"x"}') is None
    assert parse_networkmap_response('{"data":{"type":"graphviz","value":"x"}}') is None
    assert parse_networkmap_response('{"data":{"type":"raw","value":1}}') is None
    assert parse_networkmap_response('{"data": 1}') is None
    assert parse_networkmap_response("[]") is None


def test_session_fixture_loader() -> None:
    """The replay helper yields absolute topics and encoded payloads."""
    session = load_session()
    messages = session_messages()
    assert len(messages) == len(session["messages"])
    assert messages[0].topic == "zigbee2mqtt/bridge/state"
    assert messages[0].payload == '{"state":"online"}'
    assert messages[0].retain
    assert session_messages(base_topic="custom/")[0].topic == "custom/bridge/state"
    legacy = next(
        m for m in messages if m.topic.endswith("Bedroom Climate/availability")
    )
    assert legacy.payload == "online"
