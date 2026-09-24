#!/usr/bin/env python3
"""Replay a Zigbee2MQTT session onto a real MQTT broker.

Publishes messages the way a real Zigbee2MQTT bridge would, so ZigSight (or
any Z2M consumer) can be exercised end to end against a real Home Assistant
+ MQTT broker without touching production:

* the retained bridge/state, bridge/info, bridge/devices and per-device
  availability messages are published first (retained), like Z2M does on
  (re)connect;
* device state messages are then replayed in a loop with small, realistic
  jitter added to linkquality/battery, occasional availability flaps
  (online -> offline -> online), a friendly-name rename, and a new device
  joining (interview in progress, then success);
* a bridge/request/networkmap request is answered on
  bridge/response/networkmap with the raw networkmap fixture, like a real
  bridge would.

Two data sources are supported:

* the recorded fixtures in tests/fixtures/z2m/ (default, via
  tests/z2m_replay.py, so there is a single fixture loader shared with the
  pytest suite);
* a capture file recorded read-only from a production broker with
  ``mosquitto_sub -v -t 'zigbee2mqtt/#' -C 2000 > capture.txt`` (--capture-file).
  bridge/info secrets (network key, MQTT credentials) are redacted while
  loading, never held or replayed as-is. See docs/testing.md before
  recording or sharing a capture.

This script is dev/e2e tooling only: it is not imported by the integration
or by the pytest suite (which uses tests/z2m_replay.py directly, without a
real broker). Requires paho-mqtt (requirements-e2e.txt), not a runtime
dependency of ZigSight itself.
"""

from __future__ import annotations

import argparse
import copy
import json
import logging
import os
import random
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
# Reuse the fixture/capture loader used by the pytest suite instead of
# duplicating fixture parsing here.
sys.path.insert(0, str(REPO_ROOT))

from tests.z2m_replay import (  # noqa: E402
    Z2MMessage,
    capture_messages,
    encode_payload,
    load_fixture,
    session_messages,
)

try:
    import paho.mqtt.client as mqtt
except ImportError as err:  # pragma: no cover - exercised only when missing
    raise SystemExit(
        "paho-mqtt is required to run this script: pip install -r requirements-e2e.txt"
    ) from err

_LOGGER = logging.getLogger("z2m_replay")

DEFAULT_PREFIX = "zigbee2mqtt"
DEFAULT_SPEED = 1.0
NETWORKMAP_REQUEST_TOPIC = "bridge/request/networkmap"
NETWORKMAP_RESPONSE_TOPIC = "bridge/response/networkmap"


@dataclass
class DeviceState:
    """Mutable per-device state the jitter loop drifts over time."""

    friendly_name: str
    ieee_address: str
    payload: dict[str, Any]
    online: bool = True
    flap_countdown: int = field(default_factory=lambda: random.randint(6, 18))


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--host",
        default=os.environ.get("MQTT_HOST", "localhost"),
        help="MQTT broker host (env MQTT_HOST, default localhost)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("MQTT_PORT", "1883")),
        help="MQTT broker port (env MQTT_PORT, default 1883)",
    )
    parser.add_argument(
        "--username",
        default=os.environ.get("MQTT_USERNAME"),
        help="MQTT username (env MQTT_USERNAME)",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("MQTT_PASSWORD"),
        help="MQTT password (env MQTT_PASSWORD)",
    )
    parser.add_argument(
        "--prefix",
        default=DEFAULT_PREFIX,
        help=f"Zigbee2MQTT base topic to publish under (default: {DEFAULT_PREFIX})",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=DEFAULT_SPEED,
        help="Loop delay multiplier: >1 slower, <1 faster (default: 1.0)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Publish the initial retained state and one round of device "
        "state messages, then exit instead of looping forever.",
    )
    parser.add_argument(
        "--capture-file",
        type=Path,
        default=None,
        help="Replay a mosquitto_sub -v capture file instead of the "
        "recorded tests/fixtures/z2m/ session. bridge/info secrets are "
        "redacted while loading.",
    )
    return parser.parse_args(argv)


def _make_client(args: argparse.Namespace) -> mqtt.Client:
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2, client_id="zigsight-z2m-replay"
    )
    if args.username:
        client.username_pw_set(args.username, args.password)
    return client


def _publish(client: mqtt.Client, topic: str, payload: str, retain: bool) -> None:
    info = client.publish(topic, payload, qos=0, retain=retain)
    info.wait_for_publish(timeout=5)
    _LOGGER.debug("published %s%s", topic, " (retained)" if retain else "")


def _initial_messages_and_devices(
    prefix: str, capture_file: Path | None
) -> tuple[list[Z2MMessage], dict[str, DeviceState], dict[str, Any] | None]:
    """Return the initial retained batch, live device states, and the raw networkmap payload."""
    if capture_file is not None:
        messages = capture_messages(capture_file, base_topic=prefix)
        devices_by_name: dict[str, DeviceState] = {}
        networkmap_raw: dict[str, Any] | None = None
        for message in messages:
            relative = message.topic[len(prefix) + 1 :]
            if relative == "bridge/devices":
                try:
                    for device in json.loads(message.payload):
                        name = device.get("friendly_name")
                        ieee = device.get("ieee_address")
                        if name and ieee and device.get("type") != "Coordinator":
                            devices_by_name[name] = DeviceState(name, ieee, {})
                except (json.JSONDecodeError, TypeError):
                    pass
            elif relative == NETWORKMAP_RESPONSE_TOPIC:
                try:
                    networkmap_raw = json.loads(message.payload)
                except (json.JSONDecodeError, TypeError):
                    pass
            elif "/" not in relative and relative in devices_by_name:
                try:
                    payload = json.loads(message.payload)
                except (json.JSONDecodeError, TypeError):
                    continue
                if isinstance(payload, dict):
                    devices_by_name[relative].payload.update(payload)
        return messages, devices_by_name, networkmap_raw

    messages = session_messages(base_topic=prefix)
    bridge_devices = load_fixture("bridge_devices.json")
    devices_by_name = {
        device["friendly_name"]: DeviceState(
            device["friendly_name"], device["ieee_address"], {}
        )
        for device in bridge_devices
        if device.get("type") != "Coordinator"
    }
    for entry in load_fixture("session.json")["messages"]:
        topic = entry["topic"]
        if "/" in topic or topic not in devices_by_name:
            continue
        payload = entry.get("payload")
        if isinstance(payload, dict):
            devices_by_name[topic].payload.update(payload)
    networkmap_raw = load_fixture("networkmap_raw.json")
    return messages, devices_by_name, networkmap_raw


def _publish_initial_batch(client: mqtt.Client, messages: list[Z2MMessage]) -> None:
    """Publish the recorded/captured session once, in order, like a real Z2M startup."""
    for message in messages:
        _publish(client, message.topic, message.payload, message.retain)


def _jitter_device_payload(state: DeviceState) -> dict[str, Any] | None:
    """Return a mutated copy of the device's last known payload, or None to skip this round."""
    if not state.payload:
        return None
    payload = copy.deepcopy(state.payload)
    if "linkquality" in payload:
        payload["linkquality"] = max(
            0, min(255, int(payload["linkquality"]) + random.randint(-15, 15))
        )
    if "battery" in payload:
        payload["battery"] = max(
            0, min(100, int(payload["battery"]) - random.choice([0, 0, 0, 1]))
        )
    payload["last_seen"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    return payload


def _maybe_flap_availability(
    client: mqtt.Client, prefix: str, state: DeviceState
) -> None:
    """Occasionally take a device offline, then bring it back online."""
    state.flap_countdown -= 1
    if state.flap_countdown > 0:
        return
    state.flap_countdown = random.randint(10, 25)
    state.online = not state.online
    _publish(
        client,
        f"{prefix}/{state.friendly_name}/availability",
        encode_payload({"state": "online" if state.online else "offline"}),
        retain=True,
    )
    _LOGGER.info(
        "%s is now %s", state.friendly_name, "online" if state.online else "offline"
    )


def _rename_device_once(
    client: mqtt.Client, prefix: str, devices: dict[str, DeviceState], round_no: int
) -> None:
    """Rename one device around the third loop iteration, like a user renaming it in Z2M."""
    if round_no != 3 or not devices:
        return
    name, state = next(iter(devices.items()))
    new_name = f"{name} (renamed)"
    _LOGGER.info("renaming %s -> %s", name, new_name)
    # Z2M publishes an empty retained message on the old topic to clear it,
    # then republishes bridge/devices and the state under the new name.
    _publish(client, f"{prefix}/{name}", "", retain=True)
    _publish(client, f"{prefix}/{name}/availability", "", retain=True)
    state.friendly_name = new_name
    devices[new_name] = devices.pop(name)
    _publish(
        client,
        f"{prefix}/{new_name}/availability",
        encode_payload({"state": "online" if state.online else "offline"}),
        retain=True,
    )


def _join_new_device_once(
    client: mqtt.Client, prefix: str, devices: dict[str, DeviceState], round_no: int
) -> None:
    """Simulate a new device joining: interview in progress, then success."""
    if round_no != 5:
        return
    name = "New Sensor"
    ieee = "0x00158d00aabbccdd"
    _LOGGER.info("simulating device join: %s", name)
    _publish(
        client,
        f"{prefix}/bridge/event",
        encode_payload(
            {
                "type": "device_interview",
                "data": {
                    "friendly_name": ieee,
                    "ieee_address": ieee,
                    "status": "started",
                },
            }
        ),
        retain=False,
    )
    time.sleep(0.5)
    _publish(
        client,
        f"{prefix}/bridge/event",
        encode_payload(
            {
                "type": "device_interview",
                "data": {
                    "friendly_name": name,
                    "ieee_address": ieee,
                    "status": "successful",
                    "supported": True,
                },
            }
        ),
        retain=False,
    )
    state = DeviceState(
        name, ieee, {"battery": 100, "linkquality": 180, "contact": True}
    )
    devices[name] = state
    _publish(
        client,
        f"{prefix}/{name}/availability",
        encode_payload({"state": "online"}),
        retain=True,
    )
    _publish(client, f"{prefix}/{name}", encode_payload(state.payload), retain=False)


def _install_networkmap_responder(
    client: mqtt.Client, prefix: str, networkmap_raw: dict[str, Any] | None
) -> None:
    if networkmap_raw is None:
        return
    request_topic = f"{prefix}/{NETWORKMAP_REQUEST_TOPIC}"
    response_topic = f"{prefix}/{NETWORKMAP_RESPONSE_TOPIC}"

    def _on_message(_client: mqtt.Client, _userdata: Any, msg: Any) -> None:
        if msg.topic != request_topic:
            return
        _LOGGER.info("networkmap requested, responding")
        _publish(client, response_topic, encode_payload(networkmap_raw), retain=False)

    client.subscribe(request_topic)
    client.on_message = _on_message


def run(args: argparse.Namespace) -> None:
    messages, devices, networkmap_raw = _initial_messages_and_devices(
        args.prefix, args.capture_file
    )
    client = _make_client(args)
    client.connect(args.host, args.port, keepalive=30)
    client.loop_start()
    try:
        _install_networkmap_responder(client, args.prefix, networkmap_raw)
        _LOGGER.info(
            "publishing initial retained state (%d messages) under prefix %r",
            len(messages),
            args.prefix,
        )
        _publish_initial_batch(client, messages)

        if args.once:
            for state in devices.values():
                payload = _jitter_device_payload(state)
                if payload:
                    _publish(
                        client,
                        f"{args.prefix}/{state.friendly_name}",
                        encode_payload(payload),
                        retain=False,
                    )
            return

        round_no = 0
        while True:
            round_no += 1
            for state in list(devices.values()):
                if not state.online:
                    continue
                payload = _jitter_device_payload(state)
                if payload:
                    _publish(
                        client,
                        f"{args.prefix}/{state.friendly_name}",
                        encode_payload(payload),
                        retain=False,
                    )
                _maybe_flap_availability(client, args.prefix, state)
            _rename_device_once(client, args.prefix, devices, round_no)
            _join_new_device_once(client, args.prefix, devices, round_no)
            time.sleep(max(0.1, 5.0 * args.speed))
    finally:
        client.loop_stop()
        client.disconnect()


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = _parse_args(argv)
    stop_event = threading.Event()

    def _handle_sigterm(*_: Any) -> None:
        stop_event.set()

    try:
        import signal

        signal.signal(signal.SIGTERM, _handle_sigterm)
    except (ImportError, ValueError):
        pass

    try:
        run(args)
    except KeyboardInterrupt:
        _LOGGER.info("interrupted, exiting")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
