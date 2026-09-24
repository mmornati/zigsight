#!/usr/bin/env python3
"""Bootstrap and verify the ZigSight end-to-end environment.

Drives a freshly-started Home Assistant instance (docker-compose.yml's
``home-assistant`` service, pointed at ``mosquitto`` + ``z2m-replay``)
through:

1. onboarding (creates the owner user, obtains an API token) -- Home
   Assistant has no "create the first user" YAML option, only the
   onboarding REST API;
2. the MQTT integration's config flow (broker: mosquitto) -- MQTT can no
   longer be configured via YAML either;
3. the ZigSight integration's config flow (type: zigbee2mqtt).

It then verifies, each phase polling with a bounded timeout (HTTP and
websocket errors are retried too, the websocket is reconnected):

* **initial state** - the ZigSight config entry is ``loaded``; the device
  registry holds *exactly* the expected devices (the bridge + every enabled
  device of ``bridge/devices``: no group, no ``<name>/set`` device); every
  device that sent a state has a link-quality sensor whose state isn't
  ``unknown``/``unavailable``; the ZigSight panel is registered; the
  topology endpoint returns nodes;
* **dynamic path** - it asks the replay (over MQTT, through Home Assistant's
  ``mqtt.publish`` service) to rename ``Kitchen/Motion Sensor`` to
  ``Hallway/Motion Sensor`` and to join a new device, ``New Sensor``; then
  waits until the rename is reflected (same registry device, same entity
  unique ids, new name, old name gone) and ``New Sensor`` exists with a
  usable link-quality state;
* **network map** - ``POST /api/zigsight/topology/networkmap`` (admin) and
  waits for the replay's response to show up as topology links;
* **soak** - keeps the stack running until ``--soak`` seconds after the
  entry loaded (default 90) so availability flaps and further state
  rounds happen before the caller checks the Home Assistant log
  (scripts/ci_check_ha_log.py), then re-checks the device set.

Exits non-zero with a clear message on any failure. Requires aiohttp
(requirements-e2e.txt). See docs/testing.md and `make e2e`.
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import os
import sys
import time
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

import aiohttp

DEFAULT_BASE_URL = "http://localhost:8123"
DEFAULT_USERNAME = os.environ.get("E2E_HA_USERNAME", "zigsight-e2e")
DEFAULT_PASSWORD = os.environ.get("E2E_HA_PASSWORD", "ZigSight-e2e-local-only!2026")
CLIENT_ID = DEFAULT_BASE_URL + "/"

BRIDGE_DEVICE_NAME = "Zigbee2MQTT bridge"
RENAME_FROM = "Kitchen/Motion Sensor"
RENAME_TO = "Hallway/Motion Sensor"
JOINED_DEVICE = "New Sensor"
# Devices of tests/fixtures/z2m/bridge_devices.json that get entities (the
# coordinator never does, "Old Door Sensor" is disabled in Zigbee2MQTT), plus
# the ZigSight bridge (service) device. All of them send state messages.
STATE_DEVICES = {"Living Room Lamp", "Kitchen", "Bedroom Climate", RENAME_FROM}
EXPECTED_INITIAL_DEVICES = {BRIDGE_DEVICE_NAME, *STATE_DEVICES}
EXPECTED_FINAL_DEVICES = (EXPECTED_INITIAL_DEVICES - {RENAME_FROM}) | {
    RENAME_TO,
    JOINED_DEVICE,
}
SCENARIO_TOPIC = "zigsight-e2e/replay/scenario"
LINK_QUALITY_SUFFIX = "_link_quality"
UNUSABLE_STATES = (None, "unknown", "unavailable")

POLL_TIMEOUT = float(os.environ.get("E2E_POLL_TIMEOUT", "180"))
PHASE_TIMEOUT = float(os.environ.get("E2E_PHASE_TIMEOUT", "90"))
POLL_INTERVAL = 3.0
RETRYABLE_ERRORS = (aiohttp.ClientError, TimeoutError, ConnectionError)


class BootstrapError(RuntimeError):
    """A step failed; message is printed as-is and the script exits 1."""


def _log(message: str) -> None:
    print(f"[e2e_bootstrap] {message}", flush=True)


async def wait_for_http(
    session: aiohttp.ClientSession, base_url: str, timeout: float
) -> None:
    _log(f"waiting for {base_url} to respond ...")
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            async with session.get(
                base_url, timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status < 500:
                    _log("Home Assistant is responding")
                    return
        except (TimeoutError, aiohttp.ClientError) as err:
            last_error = err
        await asyncio.sleep(2)
    raise BootstrapError(
        f"Home Assistant did not respond within {timeout}s ({last_error})"
    )


async def _onboarding_steps(
    session: aiohttp.ClientSession, base_url: str
) -> list[dict[str, Any]]:
    async with session.get(f"{base_url}/api/onboarding") as resp:
        if resp.status == 404:
            # Onboarding already completed (no steps left to do); the caller
            # is expected to already have valid credentials in that case.
            return []
        resp.raise_for_status()
        result: list[dict[str, Any]] = await resp.json()
        return result


async def complete_onboarding(
    session: aiohttp.ClientSession, base_url: str, username: str, password: str
) -> str:
    """Run onboarding end to end, returning a bearer access token."""
    steps = await _onboarding_steps(session, base_url)
    step_names = {step["step"] for step in steps if not step.get("done")}
    if not step_names:
        raise BootstrapError(
            "Onboarding already completed but no cached credentials are "
            "available; start from a clean HA volume for e2e (make e2e-down "
            "then make e2e-up)."
        )
    if "user" not in step_names:
        raise BootstrapError(
            f"Unexpected onboarding steps (no 'user' step): {step_names}"
        )

    _log(f"onboarding: creating owner user {username!r}")
    async with session.post(
        f"{base_url}/api/onboarding/users",
        json={
            "client_id": CLIENT_ID,
            "name": "ZigSight E2E",
            "username": username,
            "password": password,
            "language": "en",
        },
    ) as resp:
        if resp.status != 200:
            raise BootstrapError(
                f"onboarding/users failed: {resp.status} {await resp.text()}"
            )
        auth_code = (await resp.json())["auth_code"]

    async with session.post(
        f"{base_url}/auth/token",
        data={
            "grant_type": "authorization_code",
            "code": auth_code,
            "client_id": CLIENT_ID,
        },
    ) as resp:
        if resp.status != 200:
            raise BootstrapError(
                f"token exchange failed: {resp.status} {await resp.text()}"
            )
        token: str = (await resp.json())["access_token"]

    headers = {"Authorization": f"Bearer {token}"}

    # Best-effort: remaining onboarding steps (core_config, analytics, ...)
    # only gate the onboarding *wizard UI*, not the REST/WS API used below,
    # so failures here are logged but not fatal.
    for step in ("core_config", "analytics", "integration"):
        if step not in step_names:
            continue
        try:
            body = (
                {"client_id": CLIENT_ID, "redirect_uri": CLIENT_ID}
                if step == "integration"
                else {}
            )
            async with session.post(
                f"{base_url}/api/onboarding/{step}", json=body, headers=headers
            ) as resp:
                if resp.status != 200:
                    _log(f"onboarding/{step} returned {resp.status} (non-fatal)")
        except aiohttp.ClientError as err:
            _log(f"onboarding/{step} failed (non-fatal): {err}")

    _log("onboarding complete, obtained API token")
    return token


_MISSING = object()


def _default_for_field(field: dict[str, Any], overrides: dict[str, Any]) -> Any:
    """Value for one serialized data_schema field, recursing into sections.

    Priority: ``overrides`` (by field name, at any nesting depth), then the
    serialized ``default``. Sections (``type: expandable``) are always
    synthesized from their fields. Without either:

    * optional fields are left out (``_MISSING``);
    * a required boolean becomes False (don't enable an optional extra --
      some Home Assistant releases don't serialize e.g. MQTT's
      ``set_client_cert`` default);
    * any other required field (in particular a select, where guessing the
      first option could silently configure the wrong thing) fails, naming
      the field, so the override list can be extended deliberately.
    """
    name = field.get("name")
    if name in overrides:
        return overrides[name]
    if "default" in field:
        return field["default"]
    if field.get("type") == "expandable":
        nested: dict[str, Any] = {}
        for sub_field in field.get("schema", []):
            sub_name = sub_field.get("name")
            if sub_name is None:
                continue
            value = _default_for_field(sub_field, overrides)
            if value is not _MISSING:
                nested[sub_name] = value
        return nested
    if not field.get("required"):
        return _MISSING
    # Leaf selectors are serialized as {"selector": {"boolean": {}}} /
    # {"selector": {"select": {...}}}, not with a top-level "type".
    selector = field.get("selector") or {}
    if "boolean" in selector or field.get("type") == "boolean":
        return False
    kind = next(iter(selector), field.get("type", "unknown"))
    raise BootstrapError(
        f"required {kind} field {name!r} has no default and no override "
        f"(field: {field}); add it to the overrides in e2e_bootstrap.py"
    )


async def run_config_flow(
    session: aiohttp.ClientSession,
    base_url: str,
    headers: dict[str, str],
    handler: str,
    overrides: dict[str, Any],
) -> dict[str, Any]:
    """Drive a config flow to completion, filling forms from ``overrides``/schema defaults."""
    async with session.post(
        f"{base_url}/api/config/config_entries/flow",
        json={"handler": handler},
        headers=headers,
    ) as resp:
        if resp.status != 200:
            raise BootstrapError(
                f"{handler}: could not start config flow: {await resp.text()}"
            )
        result = await resp.json()

    for _ in range(20):
        flow_type = result.get("type")
        if flow_type == "create_entry":
            _log(f"{handler}: config entry created ({result.get('title')})")
            return result
        if flow_type == "abort":
            reason = result.get("reason")
            if reason in ("already_configured", "single_instance_allowed"):
                _log(f"{handler}: already configured ({reason}), treating as success")
                return result
            raise BootstrapError(f"{handler}: config flow aborted: {reason}")
        if flow_type != "form":
            raise BootstrapError(f"{handler}: unexpected flow response: {result}")

        step_id = result.get("step_id")
        data: dict[str, Any] = {}
        for field in result.get("data_schema", []):
            name = field.get("name")
            if name is None:
                continue
            try:
                value = _default_for_field(field, overrides)
            except BootstrapError as err:
                raise BootstrapError(f"{handler}: step {step_id!r}: {err}") from err
            if value is not _MISSING:
                data[name] = value
        _log(f"{handler}: submitting step {step_id!r} with {sorted(data)}")

        async with session.post(
            f"{base_url}/api/config/config_entries/flow/{result['flow_id']}",
            json=data,
            headers=headers,
        ) as resp:
            if resp.status != 200:
                raise BootstrapError(
                    f"{handler}: step {step_id!r} failed: {resp.status} {await resp.text()}"
                )
            result = await resp.json()

    raise BootstrapError(f"{handler}: config flow never completed")


class WebsocketClient:
    """Tiny Home Assistant websocket API client (auth + id-tracked commands)."""

    def __init__(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        """Wrap an authenticated websocket."""
        self._ws = ws
        self._next_id = itertools.count(1)

    @classmethod
    async def connect(
        cls, session: aiohttp.ClientSession, base_url: str, token: str
    ) -> WebsocketClient:
        """Open and authenticate a websocket connection."""
        ws_url = (
            base_url.replace("http://", "ws://").replace("https://", "wss://")
            + "/api/websocket"
        )
        ws = await session.ws_connect(ws_url, heartbeat=20)
        first = await ws.receive_json(timeout=10)
        if first.get("type") != "auth_required":
            raise BootstrapError(f"unexpected websocket handshake: {first}")
        await ws.send_json({"type": "auth", "access_token": token})
        auth_result = await ws.receive_json(timeout=10)
        if auth_result.get("type") != "auth_ok":
            raise BootstrapError(f"websocket auth failed: {auth_result}")
        return cls(ws)

    @property
    def closed(self) -> bool:
        """Return True once the connection is gone."""
        return self._ws.closed

    async def command(self, command_type: str, **kwargs: Any) -> Any:
        """Send a command and return its result (raises on failure)."""
        msg_id = next(self._next_id)
        await self._ws.send_json({"id": msg_id, "type": command_type, **kwargs})
        while True:
            raw = await self._ws.receive(timeout=30)
            if raw.type in (
                aiohttp.WSMsgType.CLOSE,
                aiohttp.WSMsgType.CLOSED,
                aiohttp.WSMsgType.CLOSING,
                aiohttp.WSMsgType.ERROR,
            ):
                raise ConnectionError(f"websocket closed during {command_type}")
            message = json.loads(raw.data)
            if message.get("id") == msg_id:
                if not message.get("success", True):
                    raise BootstrapError(
                        f"{command_type} failed: {message.get('error')}"
                    )
                return message.get("result")

    async def close(self) -> None:
        """Close the connection."""
        await self._ws.close()


class HomeAssistant:
    """The REST + websocket calls the checks need, with reconnecting websocket."""

    def __init__(
        self, session: aiohttp.ClientSession, base_url: str, token: str
    ) -> None:
        """Remember how to reach Home Assistant."""
        self.session = session
        self.base_url = base_url
        self.token = token
        self.headers = {"Authorization": f"Bearer {token}"}
        self._ws: WebsocketClient | None = None

    async def ws(self, command_type: str, **kwargs: Any) -> Any:
        """Run a websocket command, (re)connecting first if needed."""
        if self._ws is None or self._ws.closed:
            self._ws = await WebsocketClient.connect(
                self.session, self.base_url, self.token
            )
        try:
            return await self._ws.command(command_type, **kwargs)
        except RETRYABLE_ERRORS:
            await self._ws.close()
            self._ws = None
            raise

    async def get(self, path: str) -> Any:
        """GET a JSON API path, raising BootstrapError on a non-200."""
        async with self.session.get(
            f"{self.base_url}{path}",
            headers=self.headers,
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            if resp.status != 200:
                raise BootstrapError(f"GET {path} returned {resp.status}")
            return await resp.json()

    async def post(self, path: str, body: dict[str, Any]) -> tuple[int, Any]:
        """POST JSON, returning (status, parsed body or text)."""
        async with self.session.post(
            f"{self.base_url}{path}",
            json=body,
            headers=self.headers,
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            try:
                return resp.status, await resp.json()
            except (aiohttp.ContentTypeError, json.JSONDecodeError):
                return resp.status, await resp.text()

    async def close(self) -> None:
        """Close the websocket, if any."""
        if self._ws is not None:
            await self._ws.close()


async def poll(what: str, check: Callable[[], Awaitable[Any]], timeout: float) -> Any:
    """Retry ``check`` until it returns, BootstrapError/HTTP/websocket errors included."""
    deadline = time.monotonic() + timeout
    last_error = "never ran"
    while True:
        try:
            return await check()
        except BootstrapError as err:
            last_error = str(err)
        except RETRYABLE_ERRORS as err:
            last_error = f"{type(err).__name__}: {err}"
        if time.monotonic() >= deadline:
            raise BootstrapError(
                f"{what}: not reached within {timeout:.0f}s: {last_error}"
            )
        _log(f"{what}: not yet ({last_error}), retrying ...")
        await asyncio.sleep(POLL_INTERVAL)


class Snapshot:
    """Registry + state view of the ZigSight config entry at one moment."""

    def __init__(
        self,
        entry: dict[str, Any],
        devices: list[dict[str, Any]],
        entities: list[dict[str, Any]],
        states: dict[str, str],
    ) -> None:
        """Index the raw registry/state lists by device name."""
        self.entry = entry
        entry_id = entry["entry_id"]
        self.devices_by_name: dict[str, dict[str, Any]] = {}
        for device in devices:
            if entry_id in (device.get("config_entries") or []):
                name = device.get("name_by_user") or device.get("name")
                self.devices_by_name[name] = device
        self.entities = [e for e in entities if e.get("config_entry_id") == entry_id]
        self.states = states

    def device(self, name: str) -> dict[str, Any]:
        """Return the registry device called ``name``."""
        try:
            return self.devices_by_name[name]
        except KeyError:
            raise BootstrapError(
                f"device {name!r} not in the device registry"
            ) from None

    def unique_ids(self, name: str) -> set[str]:
        """Return the entity unique ids of the device called ``name``."""
        device_id = self.device(name)["id"]
        return {
            e["unique_id"] for e in self.entities if e.get("device_id") == device_id
        }

    def assert_device_set(self, expected: set[str]) -> None:
        """Fail unless the entry's devices are exactly ``expected``."""
        names = set(self.devices_by_name)
        if names != expected:
            raise BootstrapError(
                f"device set mismatch: missing {sorted(expected - names)}, "
                f"unexpected {sorted(names - expected)}"
            )

    def assert_link_quality(self, names: set[str]) -> None:
        """Fail unless every device in ``names`` has a usable link quality."""
        problems = {}
        for name in sorted(names):
            device_id = self.device(name)["id"]
            entity_ids = [
                e["entity_id"]
                for e in self.entities
                if e.get("device_id") == device_id
                and str(e.get("unique_id", "")).endswith(LINK_QUALITY_SUFFIX)
            ]
            if not entity_ids:
                problems[name] = "no link-quality entity"
                continue
            state = self.states.get(entity_ids[0])
            if state in UNUSABLE_STATES:
                problems[name] = f"{entity_ids[0]} is {state!r}"
        if problems:
            raise BootstrapError(f"link quality not usable: {problems}")


async def snapshot(ha: HomeAssistant) -> Snapshot:
    """Read the ZigSight config entry, registries and states."""
    entries = await ha.get("/api/config/config_entries/entry")
    entry = next((e for e in entries if e.get("domain") == "zigsight"), None)
    if entry is None:
        raise BootstrapError("no zigsight config entry found")
    if entry.get("state") != "loaded":
        raise BootstrapError(f"zigsight config entry state is {entry.get('state')!r}")
    devices = await ha.ws("config/device_registry/list")
    entities = await ha.ws("config/entity_registry/list")
    states = {s["entity_id"]: s["state"] for s in await ha.get("/api/states")}
    return Snapshot(entry, devices, entities, states)


async def check_initial(ha: HomeAssistant) -> Snapshot:
    """Entry loaded, exact devices, link quality, panel, topology nodes."""
    snap = await snapshot(ha)
    snap.assert_device_set(EXPECTED_INITIAL_DEVICES)
    snap.assert_link_quality(STATE_DEVICES)
    panels = await ha.ws("get_panels")
    if "zigsight" not in panels:
        raise BootstrapError(
            f"zigsight panel not registered (panels: {sorted(panels)})"
        )
    topology = await ha.get("/api/zigsight/topology")
    if not topology.get("nodes"):
        raise BootstrapError(f"topology has no nodes yet: {topology}")
    _log(
        f"initial state OK: {len(snap.devices_by_name)} devices, "
        f"{len(snap.entities)} entities, panel registered, "
        f"{len(topology['nodes'])} topology nodes"
    )
    return snap


async def trigger_scenario(ha: HomeAssistant) -> None:
    """Ask the replay (over MQTT, via Home Assistant) to rename + join."""
    status, body = await ha.post(
        "/api/services/mqtt/publish", {"topic": SCENARIO_TOPIC, "payload": "start"}
    )
    if status != 200:
        raise BootstrapError(
            f"mqtt.publish to {SCENARIO_TOPIC} failed: {status} {body}"
        )
    _log("asked the replay to rename a device and join a new one")


async def check_dynamic(
    ha: HomeAssistant, renamed_device_id: str, renamed_unique_ids: set[str]
) -> Snapshot:
    """Rename reflected on the same device/entities; the joined device works."""
    snap = await snapshot(ha)
    snap.assert_device_set(EXPECTED_FINAL_DEVICES)
    renamed = snap.device(RENAME_TO)
    if renamed["id"] != renamed_device_id:
        raise BootstrapError(
            f"{RENAME_TO!r} is a new registry device ({renamed['id']}), "
            f"expected the renamed {renamed_device_id}"
        )
    unique_ids = snap.unique_ids(RENAME_TO)
    if unique_ids != renamed_unique_ids:
        raise BootstrapError(
            f"unique ids changed on rename: {sorted(renamed_unique_ids)} -> "
            f"{sorted(unique_ids)}"
        )
    if not snap.unique_ids(JOINED_DEVICE):
        raise BootstrapError(f"{JOINED_DEVICE!r} has no entities yet")
    snap.assert_link_quality(
        (STATE_DEVICES - {RENAME_FROM}) | {RENAME_TO, JOINED_DEVICE}
    )
    _log(
        f"rename {RENAME_FROM!r} -> {RENAME_TO!r} reflected (same device, "
        f"{len(unique_ids)} unique ids kept); {JOINED_DEVICE!r} joined with "
        f"{len(snap.unique_ids(JOINED_DEVICE))} entities"
    )
    return snap


async def request_network_map(ha: HomeAssistant) -> None:
    """POST a network map request and wait for its links to show up."""
    status, body = await ha.post("/api/zigsight/topology/networkmap", {})
    if status != 202 or not isinstance(body, dict) or not body.get("requested"):
        raise BootstrapError(f"POST /api/zigsight/topology/networkmap: {status} {body}")
    requested_at = datetime.fromisoformat(body["requested_at"])

    async def _links() -> int:
        topology = await ha.get("/api/zigsight/topology")
        updated = (topology.get("network_map") or {}).get("updated")
        if not updated or datetime.fromisoformat(updated) < requested_at:
            raise BootstrapError(f"network map not updated since {requested_at}")
        edges = [e for e in topology.get("edges") or [] if not e.get("inferred")]
        if topology.get("links_source") != "networkmap" or not edges:
            raise BootstrapError(
                "network map updated but topology still has no network-map "
                f"links (links_source={topology.get('links_source')!r})"
            )
        return len(edges)

    count = await poll("network map response", _links, PHASE_TIMEOUT)
    _log(f"network map requested and received: {count} links")


async def verify_environment(ha: HomeAssistant, soak: float) -> None:
    """Run every verification phase in order."""
    initial = await poll("initial state", lambda: check_initial(ha), POLL_TIMEOUT)
    loaded_at = time.monotonic()
    renamed = initial.device(RENAME_FROM)
    renamed_unique_ids = initial.unique_ids(RENAME_FROM)

    await poll("trigger scenario", lambda: trigger_scenario(ha), PHASE_TIMEOUT)
    await poll(
        "rename + join",
        lambda: check_dynamic(ha, renamed["id"], renamed_unique_ids),
        PHASE_TIMEOUT,
    )
    await request_network_map(ha)

    remaining = soak - (time.monotonic() - loaded_at)
    if remaining > 0:
        _log(f"soaking {remaining:.0f}s more so replay rounds/flaps reach HA ...")
        await asyncio.sleep(remaining)

    async def _still_fine() -> None:
        snap = await snapshot(ha)
        snap.assert_device_set(EXPECTED_FINAL_DEVICES)

    await poll("post-soak check", _still_fine, PHASE_TIMEOUT)
    _log("all checks passed")


async def async_main(args: argparse.Namespace) -> None:
    """Onboard, configure MQTT + ZigSight, verify."""
    async with aiohttp.ClientSession() as session:
        await wait_for_http(session, args.base_url, args.startup_timeout)
        token = await complete_onboarding(
            session, args.base_url, args.username, args.password
        )
        headers = {"Authorization": f"Bearer {token}"}

        await run_config_flow(
            session,
            args.base_url,
            headers,
            "mqtt",
            {
                "broker": "mosquitto",
                "port": 1883,
                "discovery": True,
                "set_ca_cert": "off",
                "set_client_cert": False,
            },
        )
        await run_config_flow(
            session,
            args.base_url,
            headers,
            "zigsight",
            {"integration_type": "zigbee2mqtt", "mqtt_topic_prefix": "zigbee2mqtt"},
        )

        ha = HomeAssistant(session, args.base_url, token)
        try:
            await verify_environment(ha, args.soak)
        finally:
            await ha.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--base-url", default=os.environ.get("HA_BASE_URL", DEFAULT_BASE_URL)
    )
    parser.add_argument("--username", default=DEFAULT_USERNAME)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument(
        "--startup-timeout",
        type=float,
        default=float(os.environ.get("E2E_STARTUP_TIMEOUT", "120")),
        help="Seconds to wait for Home Assistant's HTTP server to answer.",
    )
    parser.add_argument(
        "--soak",
        type=float,
        default=float(os.environ.get("E2E_SOAK_SECONDS", "90")),
        help="Keep going until this many seconds after the ZigSight entry "
        "loaded, so replay rounds and availability flaps reach Home "
        "Assistant before its log is checked (default 90, env "
        "E2E_SOAK_SECONDS).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    args = parse_args(argv)
    try:
        asyncio.run(async_main(args))
    except BootstrapError as err:
        _log(f"FAILED: {err}")
        return 1
    except Exception as err:  # noqa: BLE001 - top-level CLI: report, don't crash bare
        _log(f"FAILED (unexpected error): {err!r}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
