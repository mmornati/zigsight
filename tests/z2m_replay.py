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
