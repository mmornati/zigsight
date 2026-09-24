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

It then polls until:

* the ZigSight config entry state is ``loaded``;
* the expected devices exist in the device registry;
* the expected entities exist with a state that isn't
  ``unknown``/``unavailable`` (in particular a link-quality sensor, which
  only appears once a device state message has actually been processed);
* the ZigSight panel is registered (``get_panels`` over the websocket API);
* ``GET /api/zigsight/topology`` returns at least one node.

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
from typing import Any

import aiohttp

DEFAULT_BASE_URL = "http://localhost:8123"
DEFAULT_USERNAME = os.environ.get("E2E_HA_USERNAME", "zigsight-e2e")
DEFAULT_PASSWORD = os.environ.get("E2E_HA_PASSWORD", "ZigSight-e2e-local-only!2026")
CLIENT_ID = DEFAULT_BASE_URL + "/"

EXPECTED_DEVICE_NAMES = {
    "Living Room Lamp",
    "Kitchen",
    "Bedroom Climate",
    "Kitchen/Motion Sensor",
}
POLL_TIMEOUT = float(os.environ.get("E2E_POLL_TIMEOUT", "180"))
POLL_INTERVAL = 3.0


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

    for _ in itertools.count():
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
            if name in overrides:
                data[name] = overrides[name]
            elif "default" in field:
                data[name] = field["default"]
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

    raise BootstrapError(f"{handler}: config flow never completed")  # pragma: no cover


class WebsocketClient:
    """Tiny Home Assistant websocket API client (auth + id-tracked commands)."""

    def __init__(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        self._ws = ws
        self._next_id = itertools.count(1)

    @classmethod
    async def connect(
        cls, session: aiohttp.ClientSession, base_url: str, token: str
    ) -> WebsocketClient:
        ws_url = (
            base_url.replace("http://", "ws://").replace("https://", "wss://")
            + "/api/websocket"
        )
        ws = await session.ws_connect(ws_url)
        first = json.loads((await ws.receive()).data)
        if first.get("type") != "auth_required":
            raise BootstrapError(f"unexpected websocket handshake: {first}")
        await ws.send_json({"type": "auth", "access_token": token})
        auth_result = json.loads((await ws.receive()).data)
        if auth_result.get("type") != "auth_ok":
            raise BootstrapError(f"websocket auth failed: {auth_result}")
        return cls(ws)

    async def command(self, command_type: str, **kwargs: Any) -> Any:
        msg_id = next(self._next_id)
        await self._ws.send_json({"id": msg_id, "type": command_type, **kwargs})
        while True:
            raw = await self._ws.receive()
            message = json.loads(raw.data)
            if message.get("id") == msg_id:
                if not message.get("success", True):
                    raise BootstrapError(
                        f"{command_type} failed: {message.get('error')}"
                    )
                return message.get("result")

    async def close(self) -> None:
        await self._ws.close()


async def find_zigsight_entry(
    session: aiohttp.ClientSession, base_url: str, headers: dict[str, str]
) -> dict[str, Any]:
    async with session.get(
        f"{base_url}/api/config/config_entries/entry", headers=headers
    ) as resp:
        resp.raise_for_status()
        entries: list[dict[str, Any]] = await resp.json()
    for entry in entries:
        if entry.get("domain") == "zigsight":
            return entry
    raise BootstrapError("no zigsight config entry found after config flow")


async def verify_environment(
    session: aiohttp.ClientSession, base_url: str, token: str
) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    ws = await WebsocketClient.connect(session, base_url, token)
    try:
        deadline = time.monotonic() + POLL_TIMEOUT
        last_error = "unknown"
        while time.monotonic() < deadline:
            try:
                await _assert_ready(session, base_url, headers, ws)
                _log("all checks passed")
                return
            except BootstrapError as err:
                last_error = str(err)
                _log(f"not ready yet ({last_error}), retrying ...")
                await asyncio.sleep(POLL_INTERVAL)
        raise BootstrapError(f"environment never became ready: {last_error}")
    finally:
        await ws.close()


async def _assert_ready(
    session: aiohttp.ClientSession,
    base_url: str,
    headers: dict[str, str],
    ws: WebsocketClient,
) -> None:
    entry = await find_zigsight_entry(session, base_url, headers)
    if entry.get("state") != "loaded":
        raise BootstrapError(f"zigsight config entry state is {entry.get('state')!r}")
    entry_id = entry["entry_id"]

    devices = await ws.command("config/device_registry/list")
    device_names = {
        (device.get("name_by_user") or device.get("name"))
        for device in devices
        if entry_id in (device.get("config_entries") or [])
    }
    missing = EXPECTED_DEVICE_NAMES - device_names
    if missing:
        raise BootstrapError(f"missing expected devices in device registry: {missing}")

    entities = await ws.command("config/entity_registry/list")
    zigsight_entity_ids = [
        entity["entity_id"]
        for entity in entities
        if entity.get("config_entry_id") == entry_id
    ]
    if not zigsight_entity_ids:
        raise BootstrapError("no entities registered for the zigsight config entry")

    linkquality_entities = [eid for eid in zigsight_entity_ids if "link_quality" in eid]
    if not linkquality_entities:
        raise BootstrapError("no link-quality entity found in the entity registry")

    async with session.get(f"{base_url}/api/states", headers=headers) as resp:
        resp.raise_for_status()
        states = {state["entity_id"]: state["state"] for state in await resp.json()}

    non_unknown = [
        eid
        for eid in linkquality_entities
        if states.get(eid) not in (None, "unknown", "unavailable")
    ]
    if not non_unknown:
        sample = {eid: states.get(eid) for eid in linkquality_entities}
        raise BootstrapError(
            f"link-quality entities have no usable state yet: {sample}"
        )

    panels = await ws.command("get_panels")
    if "zigsight" not in panels:
        raise BootstrapError(
            f"zigsight panel not registered (panels: {sorted(panels)})"
        )

    async with session.get(
        f"{base_url}/api/zigsight/topology", headers=headers
    ) as resp:
        if resp.status != 200:
            raise BootstrapError(f"GET /api/zigsight/topology returned {resp.status}")
        topology = await resp.json()
    nodes = topology.get("nodes") or []
    if not nodes:
        raise BootstrapError(f"topology has no nodes yet: {topology}")

    _log(
        f"entry loaded, {len(device_names)} devices, {len(zigsight_entity_ids)} entities, "
        f"panel registered, topology has {len(nodes)} nodes"
    )


async def async_main(args: argparse.Namespace) -> None:
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
            {"broker": "mosquitto", "port": 1883, "discovery": True},
        )
        await run_config_flow(
            session,
            args.base_url,
            headers,
            "zigsight",
            {"integration_type": "zigbee2mqtt", "mqtt_topic_prefix": "zigbee2mqtt"},
        )

        await verify_environment(session, args.base_url, token)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
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
