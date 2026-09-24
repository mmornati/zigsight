"""Load and replay recorded Zigbee2MQTT fixtures.

The fixtures in ``tests/fixtures/z2m/`` describe a Zigbee2MQTT session as an
ordered list of MQTT messages (see ``session.json``). This module has no Home
Assistant dependency at import time so it can be reused outside pytest, e.g.
by a script publishing the session to a real broker::

    for message in iter_session_messages(base_topic="zigbee2mqtt"):
        client.publish(message.topic, message.payload, retain=message.retain)

Capture new fixtures read-only from a production broker with::

    mosquitto_sub -h <broker> -u <user> -P <password> -v -t 'zigbee2mqtt/#'
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "z2m"
SESSION_FILE = "session.json"


@dataclass(frozen=True)
class Z2MMessage:
    """One MQTT message of a recorded session."""

    topic: str
    payload: str
    retain: bool = False


def load_fixture(name: str) -> Any:
    """Return the parsed JSON content of a fixture file."""
    with (FIXTURES_DIR / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def load_fixture_text(name: str) -> str:
    """Return the raw text of a fixture file."""
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def encode_payload(payload: Any) -> str:
    """Encode a payload the way Zigbee2MQTT publishes it."""
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def load_session(name: str = SESSION_FILE) -> dict[str, Any]:
    """Return the raw session description."""
    return load_fixture(name)


def iter_session_messages(
    base_topic: str | None = None, name: str = SESSION_FILE
) -> Iterator[Z2MMessage]:
    """Yield the messages of a session with absolute topics."""
    session = load_session(name)
    prefix = (base_topic or session["base_topic"]).rstrip("/")
    for entry in session["messages"]:
        if "payload_file" in entry:
            payload = load_fixture_text(entry["payload_file"])
        else:
            payload = encode_payload(entry["payload"])
        yield Z2MMessage(
            topic=f"{prefix}/{entry['topic']}",
            payload=payload,
            retain=bool(entry.get("retain", False)),
        )


def session_messages(
    base_topic: str | None = None, name: str = SESSION_FILE
) -> list[Z2MMessage]:
    """Return the messages of a session as a list."""
    return list(iter_session_messages(base_topic, name))


def async_fire_messages(hass: HomeAssistant, messages: list[Z2MMessage]) -> None:
    """Deliver messages through Home Assistant's (mocked) MQTT client."""
    from pytest_homeassistant_custom_component.common import (  # noqa: PLC0415
        async_fire_mqtt_message,
    )

    for message in messages:
        async_fire_mqtt_message(
            hass, message.topic, message.payload, retain=message.retain
        )


def async_fire(
    hass: HomeAssistant,
    base_topic: str,
    topic: str,
    payload: Any,
    retain: bool = False,
) -> None:
    """Deliver a single message (topic relative to the base topic)."""
    async_fire_messages(
        hass, [Z2MMessage(f"{base_topic}/{topic}", encode_payload(payload), retain)]
    )


# --- Capture-file replay (recorded from a real broker) ----------------------
#
# ``mosquitto_sub -v -t 'zigbee2mqtt/#'`` prints one line per message, in the
# form ``<topic> <payload>``, separated by a single space (the payload itself
# may contain spaces, e.g. JSON). This is the format the owner is expected to
# use when capturing read-only from their production broker; see
# docs/testing.md.
#
# Topics that Zigbee2MQTT publishes with the MQTT retain flag set aren't
# distinguishable from non-retained ones in ``mosquitto_sub -v`` output, so
# retain is inferred from well-known topic suffixes below.
_RETAINED_TOPIC_SUFFIXES = (
    "/availability",
    "bridge/state",
    "bridge/info",
    "bridge/devices",
    "bridge/groups",
    "bridge/extensions",
)

# Secrets that must never be replayed (or committed) as-is: Zigbee2MQTT's
# retained bridge/info payload embeds the network key and the integration's
# own MQTT broker credentials.
_BRIDGE_INFO_REDACTED_PATHS: tuple[tuple[str, ...], ...] = (
    ("config", "advanced", "network_key"),
    ("config", "mqtt", "password"),
    ("config", "mqtt", "user"),
)
REDACTED_PLACEHOLDER = "***REDACTED***"


def _is_bridge_info_topic(topic: str) -> bool:
    return topic.rstrip("/").endswith("bridge/info")


def redact_bridge_info(topic: str, payload: str) -> str:
    """Strip secrets from a ``bridge/info`` payload; passthrough otherwise.

    Zigbee2MQTT's retained ``bridge/info`` message contains the Zigbee
    network key and the MQTT broker credentials it was configured with.
    Both a captured file and anything replayed from it must never leak
    those, so this is applied unconditionally when loading a capture.
    """
    if not _is_bridge_info_topic(topic):
        return payload
    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return payload

    for path in _BRIDGE_INFO_REDACTED_PATHS:
        node: Any = data
        for key in path[:-1]:
            if not isinstance(node, dict) or key not in node:
                node = None
                break
            node = node[key]
        if isinstance(node, dict) and path[-1] in node:
            node[path[-1]] = REDACTED_PLACEHOLDER

    return encode_payload(data)


def infer_retain(topic: str) -> bool:
    """Guess the MQTT retain flag of a captured message from its topic."""
    return topic.endswith(_RETAINED_TOPIC_SUFFIXES)


def parse_capture_line(line: str) -> tuple[str, str] | None:
    """Split one ``mosquitto_sub -v`` line into ``(topic, payload)``.

    Returns ``None`` for blank lines. Raises ``ValueError`` for a line with
    no space (malformed capture: mosquitto_sub always prints at least
    ``topic payload``, including an empty payload after the space).
    """
    stripped = line.rstrip("\n").rstrip("\r")
    if not stripped.strip():
        return None
    if " " not in stripped:
        raise ValueError(
            f"Malformed capture line (no topic/payload separator): {line!r}"
        )
    topic, payload = stripped.split(" ", 1)
    if not topic:
        raise ValueError(f"Malformed capture line (empty topic): {line!r}")
    return topic, payload


def iter_capture_lines(text: str) -> Iterator[tuple[str, str]]:
    """Yield ``(topic, payload)`` pairs from ``mosquitto_sub -v`` capture text."""
    for line in text.splitlines():
        parsed = parse_capture_line(line)
        if parsed is not None:
            yield parsed


def iter_capture_messages(
    path: Path, base_topic: str | None = None
) -> Iterator[Z2MMessage]:
    """Yield redacted :class:`Z2MMessage` for a capture file.

    ``base_topic`` rewrites the recorded prefix (the first topic segment of
    every captured line) to a different one, so a capture recorded against
    ``zigbee2mqtt/#`` can be replayed to a broker/prefix used for testing.
    Every ``bridge/info`` payload is redacted via :func:`redact_bridge_info`
    before it is ever held in memory or replayed.
    """
    text = path.read_text(encoding="utf-8")
    recorded_prefix: str | None = None
    for topic, payload in iter_capture_lines(text):
        parts = topic.split("/", 1)
        if len(parts) == 2:
            segment_prefix, rest = parts
        else:
            segment_prefix, rest = parts[0], ""
        if recorded_prefix is None:
            recorded_prefix = segment_prefix
        if base_topic and segment_prefix == recorded_prefix:
            topic = f"{base_topic}/{rest}" if rest else base_topic
        yield Z2MMessage(
            topic=topic,
            payload=redact_bridge_info(topic, payload),
            retain=infer_retain(topic),
        )


def capture_messages(path: Path, base_topic: str | None = None) -> list[Z2MMessage]:
    """Return the messages of a capture file as a list (see ``iter_capture_messages``)."""
    return list(iter_capture_messages(path, base_topic))
