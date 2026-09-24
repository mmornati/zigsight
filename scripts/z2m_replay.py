#!/usr/bin/env python3
"""Replay a Zigbee2MQTT session onto an MQTT broker, like a real bridge.

Publishes messages the way a real Zigbee2MQTT bridge would, so ZigSight (or
any Zigbee2MQTT consumer) can be exercised end to end against a real Home
Assistant + MQTT broker without touching production:

* the retained bridge/state, bridge/info, bridge/devices, bridge/groups and
  per-device availability messages are published on every (re)connect, like
  Zigbee2MQTT does; ``bridge/state`` is backed by a retained ``offline``
  last will, so a crashed replay never leaves a stale ``online`` behind;
* device state messages are then re-sent every round (initial
  non-retained states are lost if nobody is subscribed yet, e.g. while Home
  Assistant is still starting) with small, realistic jitter added to
  linkquality/battery, plus occasional availability flaps;
* a *scenario* - rename one device (``bridge/response/device/rename``, old
  retained topics cleared, ``bridge/devices`` republished) and a new device
  ("New Sensor") joining (``bridge/event`` ``device_joined`` and
  ``device_interview`` started/successful, ``bridge/devices`` republished
  after each step) - runs once, either when a message is published on
  ``zigsight-e2e/replay/scenario`` (what scripts/e2e_bootstrap.py does, so
  it happens *after* Home Assistant has seen the original names) or after
  ``--scenario-after`` rounds;
* ``bridge/request/networkmap`` is answered on ``bridge/response/networkmap``
  with the raw networkmap fixture (or the one found in a capture).

Command topics (``/set``, ``/get``) are never replayed.

Data sources: the recorded fixtures in tests/fixtures/z2m/ (default, via
tests/z2m_replay.py, the loader shared with the pytest suite), or a capture
recorded read-only from a real broker (``--capture-file``; JSON lines from
``mosquitto_sub -F '%j'`` preferred, see docs/testing.md). Captures are
redacted and filtered while loading.

Safety: ``--host`` is mandatory (no implicit localhost/env default), and the
replay refuses to start if ``<prefix>/bridge/state`` already holds a
retained ``online`` - i.e. a live Zigbee2MQTT (or another replay) owns that
base topic on this broker. Never point this at a production broker.

Dev/e2e tooling only: requires paho-mqtt (requirements-e2e.txt), not a
runtime dependency of ZigSight.
"""

from __future__ import annotations

import argparse
import copy
import json
import logging
import os
import random
import signal
import sys
import threading
import time
import uuid
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
ROUND_SECONDS = 5.0
BRIDGE_STATE_PROBE_SECONDS = 2.0
SCENARIO_TOPIC = "zigsight-e2e/replay/scenario"
NETWORKMAP_REQUEST_TOPIC = "bridge/request/networkmap"
NETWORKMAP_RESPONSE_TOPIC = "bridge/response/networkmap"
REPLAY_MARKER = "zigsight_replay"
DROPPED_SUFFIXES = ("/set", "/get")

# Fixture-mode rename: a friendly name containing "/" (the tricky case for
# topic parsing) moved to a different "/"-prefix.
DEFAULT_RENAME = ("Kitchen/Motion Sensor", "Hallway/Motion Sensor")
NEW_DEVICE_NAME = "New Sensor"
NEW_DEVICE_IEEE = "0x00158d00aabbccdd"
NEW_DEVICE_STATE = {
    "battery": 100,
    "contact": True,
    "linkquality": 180,
    "voltage": 3025,
}
NEW_DEVICE_DEFINITION = {
    "description": "Door and window sensor",
    "exposes": [
        {
            "access": 1,
            "label": "Contact",
            "name": "contact",
            "property": "contact",
            "type": "binary",
            "value_off": True,
            "value_on": False,
        },
        {
            "access": 1,
            "category": "diagnostic",
            "label": "Battery",
            "name": "battery",
            "property": "battery",
            "type": "numeric",
            "unit": "%",
            "value_max": 100,
            "value_min": 0,
        },
        {
            "access": 1,
            "category": "diagnostic",
            "label": "Voltage",
            "name": "voltage",
            "property": "voltage",
            "type": "numeric",
            "unit": "mV",
        },
        {
            "access": 1,
            "category": "diagnostic",
            "label": "Linkquality",
            "name": "linkquality",
            "property": "linkquality",
            "type": "numeric",
            "unit": "lqi",
            "value_max": 255,
            "value_min": 0,
        },
    ],
    "model": "MCCGQ11LM",
    "options": [],
    "source": "native",
    "supports_ota": False,
    "vendor": "Aqara",
}


@dataclass
class DeviceState:
    """Mutable per-device state the jitter loop drifts over time."""

    friendly_name: str
    ieee_address: str
    payload: dict[str, Any]
    online: bool = True
    flap_countdown: int = field(default_factory=lambda: random.randint(6, 18))


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--host",
        required=True,
        help="MQTT broker host. Mandatory on purpose: there is no default, so "
        "the replay can't end up publishing to whatever broker happens to "
        "answer on localhost.",
    )
    parser.add_argument("--port", type=int, default=1883, help="default: 1883")
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
        help=f"Round delay multiplier (a round is {ROUND_SECONDS:g}s at 1.0): "
        ">1 slower, <1 faster (default: 1.0)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Publish the initial state and one round of device state "
        "messages, then exit instead of looping forever.",
    )
    parser.add_argument(
        "--scenario-after",
        type=int,
        default=3,
        help="Run the rename/join scenario after this many rounds, even "
        f"without a message on {SCENARIO_TOPIC}. 0 = only on that message "
        "(default: 3).",
    )
    parser.add_argument(
        "--capture-file",
        type=Path,
        default=None,
        help="Replay a capture file (mosquitto_sub -F '%%j' JSON lines, "
        "-F '%%t\\t%%p' tab-separated, or legacy -v) instead of the recorded "
        "tests/fixtures/z2m/ session. Redacted and filtered while loading.",
    )
    return parser.parse_args(argv)


def _is_command_topic(topic: str) -> bool:
    return topic.endswith(DROPPED_SUFFIXES)


class Replay:
    """A fake Zigbee2MQTT bridge driven from recorded messages."""

    def __init__(self, args: argparse.Namespace, stop_event: threading.Event) -> None:
        """Load the session and prepare (but don't connect) the MQTT client."""
        self.args = args
        self.prefix: str = args.prefix.rstrip("/")
        self.stop_event = stop_event
        self.scenario_event = threading.Event()
        self.connected_event = threading.Event()
        self._closing = False
        self._lock = threading.Lock()
        # Current retained state (topic -> payload), republished on connect.
        self.retained: dict[str, str] = {}
        self.initial_transient: list[Z2MMessage] = []
        self.bridge_devices: list[dict[str, Any]] = []
        self.devices: dict[str, DeviceState] = {}
        self.networkmap_raw: dict[str, Any] | None = None
        self.rename: tuple[str, str] | None = None
        self._load()
        self.client = self._make_client(
            f"zigsight-z2m-replay-{uuid.uuid4().hex[:12]}", with_will=True
        )

    # -- loading -----------------------------------------------------------
    def _relative(self, topic: str) -> str | None:
        base = self.prefix + "/"
        return topic[len(base) :] if topic.startswith(base) else None

    def _load(self) -> None:
        if self.args.capture_file is not None:
            messages = capture_messages(self.args.capture_file, base_topic=self.prefix)
        else:
            messages = session_messages(base_topic=self.prefix)
        messages = [m for m in messages if not _is_command_topic(m.topic)]

        states: dict[str, dict[str, Any]] = {}
        for message in messages:
            relative = self._relative(message.topic)
            if relative == "bridge/state":
                continue  # replaced by our own (marked) online/offline
            if relative == "bridge/devices":
                try:
                    devices = json.loads(message.payload)
                except (json.JSONDecodeError, TypeError):
                    devices = None
                if isinstance(devices, list):
                    self.bridge_devices = [d for d in devices if isinstance(d, dict)]
            elif relative == NETWORKMAP_RESPONSE_TOPIC:
                try:
                    self.networkmap_raw = json.loads(message.payload)
                except (json.JSONDecodeError, TypeError):
                    pass
            elif relative is not None and not relative.startswith("bridge/"):
                try:
                    payload = json.loads(message.payload)
                except (json.JSONDecodeError, TypeError):
                    payload = None
                if isinstance(payload, dict):
                    states.setdefault(relative, {}).update(payload)

            if message.retain:
                if message.payload:
                    self.retained[message.topic] = message.payload
                else:
                    self.retained.pop(message.topic, None)
            else:
                self.initial_transient.append(message)

        if self.networkmap_raw is None and self.args.capture_file is None:
            self.networkmap_raw = load_fixture("networkmap_raw.json")

        # Device state topics are matched against friendly names *exactly*
        # (names may contain "/", e.g. "Kitchen/Motion Sensor"); anything
        # else (groups, "<name>/availability", ...) is not device state.
        for device in self.bridge_devices:
            name = device.get("friendly_name")
            ieee = device.get("ieee_address")
            if not name or not ieee or device.get("type") == "Coordinator":
                continue
            self.devices[name] = DeviceState(name, ieee, dict(states.get(name, {})))

        names = [n for n, s in self.devices.items() if s.payload]
        if self.args.capture_file is None and DEFAULT_RENAME[0] in self.devices:
            self.rename = DEFAULT_RENAME
        elif names:
            self.rename = (names[0], f"{names[0]} (renamed)")

    # -- MQTT plumbing -----------------------------------------------------
    def _make_client(self, client_id: str, *, with_will: bool) -> mqtt.Client:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        if self.args.username:
            client.username_pw_set(self.args.username, self.args.password)
        if with_will:
            client.will_set(
                f"{self.prefix}/bridge/state",
                encode_payload({"state": "offline", REPLAY_MARKER: True}),
                qos=1,
                retain=True,
            )
            client.reconnect_delay_set(min_delay=1, max_delay=15)
            client.on_connect = self._on_connect
            client.on_disconnect = self._on_disconnect
            client.on_message = self._on_message
        return client

    def publish(self, topic: str, payload: str, retain: bool = False) -> None:
        """Publish without blocking; retained messages are remembered."""
        if retain:
            with self._lock:
                if payload:
                    self.retained[topic] = payload
                else:
                    self.retained.pop(topic, None)
        info = self.client.publish(topic, payload, qos=0, retain=retain)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            _LOGGER.debug("not connected, dropped %s (rc=%s)", topic, info.rc)
        else:
            _LOGGER.debug("published %s%s", topic, " (retained)" if retain else "")

    def _on_connect(
        self, client: mqtt.Client, _userdata: Any, _flags: Any, reason: Any, _p: Any
    ) -> None:
        if reason.is_failure:
            _LOGGER.warning("broker refused the connection: %s", reason)
            return
        client.subscribe(
            [(f"{self.prefix}/{NETWORKMAP_REQUEST_TOPIC}", 0), (SCENARIO_TOPIC, 0)]
        )
        with self._lock:
            retained = list(self.retained.items())
        client.publish(
            f"{self.prefix}/bridge/state",
            encode_payload({"state": "online", REPLAY_MARKER: True}),
            retain=True,
        )
        for topic, payload in retained:
            client.publish(topic, payload, retain=True)
        _LOGGER.info("connected, (re)published %d retained messages", len(retained))
        self.connected_event.set()

    def _on_disconnect(self, *_args: Any) -> None:
        if not self._closing:
            _LOGGER.warning("disconnected from the broker, reconnecting ...")

    def _on_message(self, _client: mqtt.Client, _userdata: Any, msg: Any) -> None:
        if msg.topic == SCENARIO_TOPIC:
            _LOGGER.info("scenario requested over MQTT")
            self.scenario_event.set()
        elif msg.topic == f"{self.prefix}/{NETWORKMAP_REQUEST_TOPIC}":
            if self.networkmap_raw is None:
                _LOGGER.info("networkmap requested, but no map to answer with")
                return
            _LOGGER.info("networkmap requested, responding")
            # Non-blocking publish: never wait for an ack inside a callback
            # (it runs on the network thread that would deliver that ack).
            self.publish(
                f"{self.prefix}/{NETWORKMAP_RESPONSE_TOPIC}",
                encode_payload(self.networkmap_raw),
            )

    def check_bridge_not_owned(self) -> None:
        """Abort if a live bridge already holds ``<prefix>/bridge/state`` online.

        Uses a separate, will-less client: if this probe's connection dropped
        the broker must not publish our ``offline`` will over a real bridge's
        retained state.
        """
        probe = self._make_client(
            f"zigsight-z2m-replay-probe-{uuid.uuid4().hex[:12]}", with_will=False
        )
        found: list[str] = []
        topic = f"{self.prefix}/bridge/state"

        def _on_probe_message(_c: mqtt.Client, _u: Any, msg: Any) -> None:
            if msg.retain and msg.topic == topic:
                found.append(msg.payload.decode("utf-8", "replace"))

        probe.on_message = _on_probe_message
        probe.connect(self.args.host, self.args.port, keepalive=30)
        probe.loop_start()
        try:
            probe.subscribe(topic)
            self.stop_event.wait(BRIDGE_STATE_PROBE_SECONDS)
        finally:
            probe.disconnect()
            probe.loop_stop()
        for payload in found:
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                data = payload
            state = data.get("state") if isinstance(data, dict) else data
            if isinstance(state, str) and state.strip().lower() == "online":
                raise SystemExit(
                    f"refusing to replay: {topic} already holds a retained "
                    f"'online' ({payload}) - a live Zigbee2MQTT or another replay "
                    "owns this base topic on this broker. Use a disposable broker "
                    "(make e2e-up) or a different --prefix."
                )

    # -- the fake bridge -----------------------------------------------------
    def _publish_bridge_devices(self) -> None:
        self.publish(
            f"{self.prefix}/bridge/devices",
            encode_payload(self.bridge_devices),
            retain=True,
        )

    def _publish_event(self, event_type: str, data: dict[str, Any]) -> None:
        self.publish(
            f"{self.prefix}/bridge/event",
            encode_payload({"type": event_type, "data": data}),
        )

    def _publish_state(self, state: DeviceState) -> None:
        payload = _jitter_device_payload(state)
        if payload:
            self.publish(
                f"{self.prefix}/{state.friendly_name}", encode_payload(payload)
            )

    def _maybe_flap_availability(self, state: DeviceState) -> None:
        """Occasionally take a device offline, then bring it back online."""
        state.flap_countdown -= 1
        if state.flap_countdown > 0:
            return
        state.online = not state.online
        # Offline spells are short so the jitter loop keeps feeding states.
        state.flap_countdown = random.randint(10, 25) if state.online else 2
        self.publish(
            f"{self.prefix}/{state.friendly_name}/availability",
            encode_payload({"state": "online" if state.online else "offline"}),
            retain=True,
        )
        _LOGGER.info(
            "%s is now %s", state.friendly_name, "online" if state.online else "offline"
        )

    def do_rename(self) -> None:
        """Rename a device like ``bridge/request/device/rename`` would."""
        if self.rename is None or self.rename[0] not in self.devices:
            _LOGGER.info("nothing to rename")
            return
        old, new = self.rename
        _LOGGER.info("renaming %r -> %r", old, new)
        state = self.devices.pop(old)
        state.friendly_name = new
        self.devices[new] = state
        for device in self.bridge_devices:
            if device.get("friendly_name") == old:
                device["friendly_name"] = new
        # Zigbee2MQTT clears the old retained topics, answers the request,
        # republishes bridge/devices and then carries on under the new name.
        self.publish(f"{self.prefix}/{old}/availability", "", retain=True)
        self.publish(f"{self.prefix}/{old}", "", retain=True)
        self.publish(
            f"{self.prefix}/bridge/response/device/rename",
            encode_payload(
                {
                    "data": {"from": old, "homeassistant_rename": False, "to": new},
                    "status": "ok",
                }
            ),
        )
        self._publish_bridge_devices()
        self.publish(
            f"{self.prefix}/{new}/availability",
            encode_payload({"state": "online" if state.online else "offline"}),
            retain=True,
        )
        self._publish_state(state)

    def do_join_start(self) -> None:
        """A new device joins and its interview starts."""
        _LOGGER.info("simulating device join: %s", NEW_DEVICE_NAME)
        self._publish_event(
            "device_joined",
            {"friendly_name": NEW_DEVICE_NAME, "ieee_address": NEW_DEVICE_IEEE},
        )
        self._publish_event(
            "device_interview",
            {
                "friendly_name": NEW_DEVICE_NAME,
                "ieee_address": NEW_DEVICE_IEEE,
                "status": "started",
            },
        )
        self.bridge_devices.append(
            {
                "definition": None,
                "disabled": False,
                "endpoints": {},
                "friendly_name": NEW_DEVICE_NAME,
                "ieee_address": NEW_DEVICE_IEEE,
                "interview_completed": False,
                "interview_state": "IN_PROGRESS",
                "interviewing": True,
                "network_address": 4660,
                "supported": False,
                "type": "EndDevice",
            }
        )
        self._publish_bridge_devices()

    def do_join_complete(self) -> None:
        """The new device's interview succeeds; it starts reporting."""
        _LOGGER.info("interview of %s successful", NEW_DEVICE_NAME)
        for device in self.bridge_devices:
            if device.get("ieee_address") == NEW_DEVICE_IEEE:
                device.update(
                    {
                        "definition": copy.deepcopy(NEW_DEVICE_DEFINITION),
                        "interview_completed": True,
                        "interview_state": "SUCCESSFUL",
                        "interviewing": False,
                        "manufacturer": "LUMI",
                        "model_id": "lumi.sensor_magnet.aq2",
                        "power_source": "Battery",
                        "supported": True,
                    }
                )
        self._publish_event(
            "device_interview",
            {
                "definition": copy.deepcopy(NEW_DEVICE_DEFINITION),
                "friendly_name": NEW_DEVICE_NAME,
                "ieee_address": NEW_DEVICE_IEEE,
                "status": "successful",
                "supported": True,
            },
        )
        self._publish_bridge_devices()
        state = DeviceState(NEW_DEVICE_NAME, NEW_DEVICE_IEEE, dict(NEW_DEVICE_STATE))
        self.devices[NEW_DEVICE_NAME] = state
        self.publish(
            f"{self.prefix}/{NEW_DEVICE_NAME}/availability",
            encode_payload({"state": "online"}),
            retain=True,
        )
        self._publish_state(state)

    def publish_round(self) -> None:
        """Send every online device's (jittered) state, maybe flap one."""
        for state in list(self.devices.values()):
            if state.online:
                self._publish_state(state)
            self._maybe_flap_availability(state)

    # -- main loop -------------------------------------------------------
    def run(self) -> None:
        """Connect, publish the session, then loop until stopped."""
        self.check_bridge_not_owned()
        self.client.connect_async(self.args.host, self.args.port, keepalive=30)
        self.client.loop_start()
        try:
            while not self.connected_event.wait(1):
                if self.stop_event.is_set():
                    return
            _LOGGER.info(
                "publishing %d initial non-retained messages under %r",
                len(self.initial_transient),
                self.prefix,
            )
            for message in self.initial_transient:
                self.publish(message.topic, message.payload)
            if self.args.once:
                self.publish_round()
                return
            self._loop()
        finally:
            self._shutdown()

    def _loop(self) -> None:
        delay = max(0.1, ROUND_SECONDS * self.args.speed)
        round_no = 0
        scenario_step: int | None = None
        while not self.stop_event.is_set():
            round_no += 1
            self.publish_round()
            if scenario_step is None and (
                self.scenario_event.is_set()
                or (self.args.scenario_after and round_no >= self.args.scenario_after)
            ):
                scenario_step = 0
            if scenario_step is not None:
                if scenario_step == 0:
                    self.do_rename()
                elif scenario_step == 1:
                    self.do_join_start()
                elif scenario_step == 2:
                    self.do_join_complete()
                scenario_step += 1
            self.stop_event.wait(delay)

    def _shutdown(self) -> None:
        self._closing = True
        # A clean disconnect doesn't fire the will: say offline ourselves.
        if self.client.is_connected():
            info = self.client.publish(
                f"{self.prefix}/bridge/state",
                encode_payload({"state": "offline", REPLAY_MARKER: True}),
                qos=1,
                retain=True,
            )
            try:
                info.wait_for_publish(timeout=3)
            except (RuntimeError, ValueError):
                pass
        self.client.disconnect()
        self.client.loop_stop()
        _LOGGER.info("stopped")


def _jitter_device_payload(state: DeviceState) -> dict[str, Any] | None:
    """Return a mutated copy of the device's last known payload, or None to skip."""
    if not state.payload:
        return None
    payload = copy.deepcopy(state.payload)
    if isinstance(payload.get("linkquality"), int | float):
        payload["linkquality"] = max(
            1, min(255, int(payload["linkquality"]) + random.randint(-15, 15))
        )
    if isinstance(payload.get("battery"), int | float):
        # Batteries only drain: remember the new level for the next round.
        payload["battery"] = max(
            0, min(100, int(payload["battery"]) - random.choice([0, 0, 0, 1]))
        )
        state.payload["battery"] = payload["battery"]
    payload["last_seen"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    return payload


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = _parse_args(argv)
    stop_event = threading.Event()

    def _handle_signal(*_: Any) -> None:
        stop_event.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)
    Replay(args, stop_event).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
