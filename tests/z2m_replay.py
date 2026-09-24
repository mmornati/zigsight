"""Load and replay recorded Zigbee2MQTT fixtures.

The fixtures in ``tests/fixtures/z2m/`` describe a Zigbee2MQTT session as an
ordered list of MQTT messages (see ``session.json``). This module has no Home
Assistant dependency at import time so it can be reused outside pytest, e.g.
by a script publishing the session to a real broker::

    for message in iter_session_messages(base_topic="zigbee2mqtt"):
        client.publish(message.topic, message.payload, retain=message.retain)

Capture new fixtures read-only from a production broker with (see
docs/testing.md for the full picture and a redaction warning)::

    mosquitto_sub -h <broker> -u <user> -P <password> -F '%j' -t 'zigbee2mqtt/#' -C 2000 > capture.jsonl
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
# Three capture formats are understood, auto-detected per file from its
# first non-blank line:
#
# * JSON Lines (preferred) - ``mosquitto_sub -F '%j' -t 'zigbee2mqtt/#'``:
#   one JSON object per line, at least ``{"topic": ..., "payload": ...}``,
#   optionally ``"retain"`` (0/1). Survives topics/friendly names containing
#   spaces (Zigbee2MQTT friendly names commonly do, e.g. "Living Room Lamp")
#   and carries the real retain flag instead of it having to be guessed.
# * Tab-separated - ``mosquitto_sub -F '%t\t%p' -t 'zigbee2mqtt/#'``: also
#   space-safe, but has no retain flag (inferred, see ``infer_retain``).
# * Legacy verbose - ``mosquitto_sub -v -t 'zigbee2mqtt/#'``: ``<topic>
#   <payload>``, space separated, which is ambiguous as soon as a topic (i.e.
#   a Zigbee2MQTT friendly name, commonly "Living Room Lamp") contains a
#   space. Parsed with a heuristic (see ``parse_capture_line_verbose``):
#   right for JSON payloads and for space-free plain payloads, wrong for a
#   plain-text payload that itself contains a space. Supported only for
#   old captures; prefer one of the formats above; see docs/testing.md.
#
# Topics that Zigbee2MQTT publishes with the MQTT retain flag set aren't
# always known from the capture (tab/verbose formats), so retain is guessed
# from well-known topic suffixes as a fallback.
_RETAINED_TOPIC_SUFFIXES = (
    "/availability",
    "bridge/state",
    "bridge/info",
    "bridge/devices",
    "bridge/groups",
    "bridge/extensions",
)

# Topics that must never be replayed from a capture: command topics (never
# state, and replaying them onto a real broker could actually control a
# device) and bridge request/response topics other than the networkmap
# response (transient RPC traffic, not state; may also embed request-time
# secrets).
_DROPPED_TOPIC_SUFFIXES = ("/set", "/get")
_DROPPED_TOPIC_PREFIXES = ("bridge/request/",)


def _is_dropped_topic(relative_topic: str) -> bool:
    if relative_topic.endswith(_DROPPED_TOPIC_SUFFIXES):
        return True
    if relative_topic.startswith(_DROPPED_TOPIC_PREFIXES):
        return True
    return relative_topic.startswith("bridge/response/") and relative_topic != (
        "bridge/response/networkmap"
    )


# Key names that must never survive into a replayed/committed capture,
# wherever they appear in a ``bridge/*`` JSON payload: the Zigbee network
# key, MQTT/API credentials, and PAN/extended-PAN IDs (identify the network).
# Matched case-insensitively and regardless of nesting depth, since
# Zigbee2MQTT's bridge/info shape has changed across versions and a
# path-based allowlist (the previous approach) silently stops protecting a
# field the moment that shape changes again.
_REDACTED_KEY_NAMES = frozenset(
    {
        "network_key",
        "password",
        "auth_token",
        "install_code",
        "ext_pan_id",
        "extended_pan_id",
        "pan_id",
        "user",
        "username",
    }
)
REDACTED_PLACEHOLDER = "***REDACTED***"


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: REDACTED_PLACEHOLDER
            if isinstance(key, str) and key.lower() in _REDACTED_KEY_NAMES
            else _redact_value(sub_value)
            for key, sub_value in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    return value


def _is_bridge_topic(topic: str) -> bool:
    """True if ``topic`` (full or relative to the base topic) is a bridge/* topic."""
    return topic.startswith("bridge/") or "/bridge/" in topic


def redact_bridge_payload(topic: str, payload: str) -> str:
    """Recursively redact secrets from any ``bridge/*`` JSON payload.

    ``topic`` may be the full topic (with base-topic prefix) or just the
    part after it. Applied to every ``bridge/*`` message (not just
    ``bridge/info``, whose exact shape has already changed across
    Zigbee2MQTT versions) so a field rename or a secret showing up
    somewhere new doesn't silently stop being redacted. Non-``bridge/*``
    topics and non-JSON/undecodable payloads are passed through unchanged.
    """
    if not _is_bridge_topic(topic):
        return payload
    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return payload
    return encode_payload(_redact_value(data))


def infer_retain(topic: str) -> bool:
    """Guess the MQTT retain flag of a captured message from its topic."""
    return topic.endswith(_RETAINED_TOPIC_SUFFIXES)


def parse_capture_line_json(line: str) -> tuple[str, str, bool | None] | None:
    """Parse one ``mosquitto_sub -F '%j'`` JSON-lines record.

    Returns ``(topic, payload, retain)`` (``retain`` is ``None`` if the
    record doesn't carry one), or ``None`` for a blank line. Raises
    ``ValueError`` for invalid JSON or a record missing ``topic``.
    """
    stripped = line.strip()
    if not stripped:
        return None
    try:
        record = json.loads(stripped)
    except json.JSONDecodeError as err:
        raise ValueError(f"Malformed JSON capture line: {line!r}") from err
    if not isinstance(record, dict) or "topic" not in record:
        raise ValueError(f"Capture line missing 'topic': {line!r}")
    payload = record.get("payload", "")
    payload_text = payload if isinstance(payload, str) else encode_payload(payload)
    retain = record.get("retain")
    return record["topic"], payload_text, None if retain is None else bool(retain)


def parse_capture_line_tab(line: str) -> tuple[str, str] | None:
    """Split one ``mosquitto_sub -F '%t\\t%p'`` line into ``(topic, payload)``."""
    stripped = line.rstrip("\n").rstrip("\r")
    if not stripped.strip():
        return None
    if "\t" not in stripped:
        raise ValueError(f"Malformed tab-separated capture line: {line!r}")
    topic, payload = stripped.split("\t", 1)
    if not topic:
        raise ValueError(f"Malformed capture line (empty topic): {line!r}")
    return topic, payload


def parse_capture_line_verbose(line: str) -> tuple[str, str] | None:
    """Split one legacy ``mosquitto_sub -v`` line into ``(topic, payload)``.

    Returns ``None`` for blank lines. Raises ``ValueError`` for a line with
    no space. The format has no unambiguous separator, so a heuristic is
    used that is right for everything Zigbee2MQTT normally publishes:

    * a JSON object/array payload: split before the first `` {`` / `` [``
      (friendly names with spaces are kept whole: ``zigbee2mqtt/Living Room
      Lamp {"state": "ON"}``);
    * otherwise (plain-text payloads such as ``online`` or ``ON``): split at
      the *last* space, so ``zigbee2mqtt/Living Room Lamp/availability
      online`` works too.

    Known limitation: a plain-text payload containing a space (rare; e.g. a
    free-text ``bridge/logging`` message) is split inside the payload, and a
    topic containing `` {`` / `` [`` is split too early. Use the JSON-lines
    (``-F '%j'``) or tab-separated (``-F '%t\\t%p'``) formats instead.
    """
    stripped = line.rstrip("\n").rstrip("\r")
    if not stripped.strip():
        return None
    if " " not in stripped:
        raise ValueError(
            f"Malformed capture line (no topic/payload separator): {line!r}"
        )
    json_starts = [
        index for index in (stripped.find(" {"), stripped.find(" [")) if index >= 0
    ]
    split_at = min(json_starts) if json_starts else stripped.rindex(" ")
    topic, payload = stripped[:split_at], stripped[split_at + 1 :]
    if not topic:
        raise ValueError(f"Malformed capture line (empty topic): {line!r}")
    return topic, payload


def parse_capture_line(line: str) -> tuple[str, str] | None:
    """Parse one capture line in any supported format into ``(topic, payload)``.

    JSON-lines records (starting with ``{``) and tab-separated lines are
    unambiguous; anything else falls back to the legacy ``-v`` heuristic of
    :func:`parse_capture_line_verbose`.
    """
    if line.lstrip().startswith("{"):
        record = parse_capture_line_json(line)
        return None if record is None else (record[0], record[1])
    if "\t" in line:
        return parse_capture_line_tab(line)
    return parse_capture_line_verbose(line)


def iter_capture_lines(text: str) -> Iterator[tuple[str, str]]:
    """Yield ``(topic, payload)`` pairs from capture text (any supported format)."""
    for line in text.splitlines():
        parsed = parse_capture_line(line)
        if parsed is not None:
            yield parsed


def _detect_capture_format(text: str) -> str:
    """Return ``"json"``, ``"tab"`` or ``"verbose"`` from the first data line."""
    for line in text.splitlines():
        if not line.strip():
            continue
        if line.lstrip().startswith("{"):
            return "json"
        if "\t" in line:
            return "tab"
        return "verbose"
    return "json"


def _iter_capture_records(text: str) -> Iterator[tuple[str, str, bool | None]]:
    """Yield ``(topic, payload, retain)`` records, auto-detecting the capture format."""
    capture_format = _detect_capture_format(text)
    for line in text.splitlines():
        if capture_format == "json":
            record = parse_capture_line_json(line)
            if record is not None:
                yield record
        elif capture_format == "tab":
            parsed = parse_capture_line_tab(line)
            if parsed is not None:
                yield (*parsed, None)
        else:
            parsed = parse_capture_line_verbose(line)
            if parsed is not None:
                yield (*parsed, None)


def iter_capture_messages(
    path: Path, base_topic: str | None = None
) -> Iterator[Z2MMessage]:
    """Yield redacted, filtered :class:`Z2MMessage` for a capture file.

    ``base_topic`` rewrites the recorded prefix (the first topic segment of
    every captured line) to a different one, so a capture recorded against
    ``zigbee2mqtt/#`` can be replayed to a broker/prefix used for testing.

    Every ``bridge/*`` payload is redacted via :func:`redact_bridge_payload`
    before it is ever held in memory or replayed; command topics (``/set``,
    ``/get``) and bridge request/response topics other than
    ``bridge/response/networkmap`` are dropped entirely (see
    :func:`_is_dropped_topic`).
    """
    text = path.read_text(encoding="utf-8")
    recorded_prefix: str | None = None
    for topic, payload, retain in _iter_capture_records(text):
        parts = topic.split("/", 1)
        if len(parts) == 2:
            segment_prefix, rest = parts
        else:
            segment_prefix, rest = parts[0], ""
        if recorded_prefix is None:
            recorded_prefix = segment_prefix
        if base_topic and segment_prefix == recorded_prefix:
            topic = f"{base_topic}/{rest}" if rest else base_topic
            relative_topic = rest
        else:
            relative_topic = rest if segment_prefix == recorded_prefix else topic

        if _is_dropped_topic(relative_topic):
            continue

        yield Z2MMessage(
            topic=topic,
            payload=redact_bridge_payload(relative_topic, payload),
            # A retained update that arrives live during the capture is
            # recorded with retain=0 by mosquitto_sub, so also infer it.
            retain=bool(retain) or infer_retain(topic),
        )


def capture_messages(path: Path, base_topic: str | None = None) -> list[Z2MMessage]:
    """Return the messages of a capture file as a list (see ``iter_capture_messages``)."""
    return list(iter_capture_messages(path, base_topic))
