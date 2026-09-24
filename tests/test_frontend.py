"""Panel, static files and panel API tests against a real ``hass``.

The REST endpoints are called over HTTP with ``hass_client`` (admin and
read-only users) after replaying the recorded Zigbee2MQTT session.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components import panel_custom
from homeassistant.components.frontend import DATA_PANELS
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.zigsight import (
    DATA_PANEL_REGISTERED,
    PANEL_URL_PATH,
    STATIC_URL_PATH,
)
from custom_components.zigsight.const import (
    CONF_INTEGRATION_TYPE,
    CONF_MQTT_TOPIC_PREFIX,
    DOMAIN,
    INTEGRATION_TYPE_ZIGBEE2MQTT,
    ISSUE_LEGACY_PANEL,
)
from custom_components.zigsight.coordinator import ZigSightCoordinator

from .z2m_replay import async_fire_messages, session_messages

BASE = "zigbee2mqtt"
NOW = "2026-09-24T08:20:00+00:00"

COORDINATOR = "0x00124b0024c1a2b3"
LAMP = "0x0017880104e45517"
PLUG = "0x000d6ffffe1a2b3c"
CLIMATE = "0x00158d0001a2b3c4"
MOTION = "0x001788010b2c3d4e"
DOOR = "0x00158d000aabbccd"

WIFI_SCAN = [
    {"channel": 1, "rssi": -40, "ssid": "home"},
    {"channel": 6, "rssi": -45},
    {"channel": 11, "rssi": -50},
]


@pytest.fixture
def entry(hass: HomeAssistant) -> MockConfigEntry:
    """A Zigbee2MQTT ZigSight config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=2,
        data={
            CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_ZIGBEE2MQTT,
            CONF_MQTT_TOPIC_PREFIX: BASE,
        },
    )
    config_entry.add_to_hass(hass)
    return config_entry


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> ZigSightCoordinator:
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    coordinator: ZigSightCoordinator = hass.data[DOMAIN][entry.entry_id]
    return coordinator


@pytest.fixture
async def coordinator(
    hass: HomeAssistant,
    mqtt_mock: MagicMock,
    entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> ZigSightCoordinator:
    """Set up the integration and replay the session (without network map)."""
    freezer.move_to(NOW)
    coord = await _setup(hass, entry)
    async_fire_messages(
        hass, [m for m in session_messages() if not m.topic.endswith("networkmap")]
    )
    await hass.async_block_till_done()
    return coord


def _fire_network_map(hass: HomeAssistant) -> None:
    async_fire_messages(
        hass, [m for m in session_messages() if m.topic.endswith("networkmap")]
    )


# ---------------------------------------------------------------------------
# Panel and static files
# ---------------------------------------------------------------------------
async def test_panel_registered_and_removed(
    hass: HomeAssistant, mqtt_mock: MagicMock, entry: MockConfigEntry
) -> None:
    """The sidebar panel is registered on setup and removed on unload."""
    await _setup(hass, entry)

    panel = hass.data[DATA_PANELS][PANEL_URL_PATH]
    assert panel.component_name == "custom"
    assert panel.sidebar_title == "ZigSight"
    assert panel.sidebar_icon == "mdi:zigbee"
    assert panel.require_admin is True
    custom = panel.config["_panel_custom"]
    assert custom["name"] == "zigsight-panel"
    assert custom["embed_iframe"] is False
    assert custom["module_url"] == f"{STATIC_URL_PATH}/zigsight-panel.js?v=1.1.0"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert PANEL_URL_PATH not in hass.data[DATA_PANELS]
    assert DATA_PANEL_REGISTERED not in hass.data

    # Registered again when the entry is set up again
    await _setup(hass, entry)
    assert PANEL_URL_PATH in hass.data[DATA_PANELS]


async def test_static_path_registered_once(
    hass: HomeAssistant, mqtt_mock: MagicMock, entry: MockConfigEntry
) -> None:
    """The www folder is served once, however often the entry reloads."""
    calls: list[list[StaticPathConfig]] = []
    original = hass.http.async_register_static_paths

    async def _spy(configs: list[StaticPathConfig]) -> None:
        calls.append(list(configs))
        await original(configs)

    with patch.object(hass.http, "async_register_static_paths", _spy):
        await _setup(hass, entry)
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED

    assert len(calls) == 1
    (config,) = calls[0]
    assert config.url_path == STATIC_URL_PATH
    assert config.path.endswith("custom_components/zigsight/www")
    assert config.cache_headers is False


async def test_static_files_served(
    hass: HomeAssistant,
    mqtt_mock: MagicMock,
    entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """The panel, its vendored Lit build and the cards are served."""
    await _setup(hass, entry)
    client = await hass_client_no_auth()

    for path in (
        "zigsight-panel.js",
        "topology-card.js",
        "topology-visualization.js",
        "lib/topology-graph.js",
        "vendor/lit-core.min.js",
    ):
        response = await client.get(f"{STATIC_URL_PATH}/{path}")
        assert response.status == 200, path
        body = await response.text()
        assert "unpkg.com" not in body
        assert "cdn.jsdelivr" not in body

    response = await client.get(f"{STATIC_URL_PATH}/../manifest.json")
    assert response.status in (403, 404)


def _legacy_issue(hass: HomeAssistant) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_LEGACY_PANEL)


async def test_yaml_panel_is_kept_and_reported(
    hass: HomeAssistant,
    mqtt_mock: MagicMock,
    entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A leftover panel_custom YAML panel is kept and raises a repair issue."""
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name="zigsight-panel",
        module_url="/local/zigsight/zigsight-panel.js",
    )

    with caplog.at_level(logging.WARNING):
        await _setup(hass, entry)
    assert "remove the 'panel_custom' entry" in caplog.text
    assert DATA_PANEL_REGISTERED not in hass.data

    issue = _legacy_issue(hass)
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.translation_key == ISSUE_LEGACY_PANEL
    assert issue.translation_placeholders == {
        "panels": "/zigsight (/local/zigsight/zigsight-panel.js)"
    }

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    # Not ours: left alone; the issue goes with the integration
    panel = hass.data[DATA_PANELS][PANEL_URL_PATH]
    assert (
        panel.config["_panel_custom"]["module_url"]
        == "/local/zigsight/zigsight-panel.js"
    )
    assert _legacy_issue(hass) is None


async def test_duplicate_panel_element_reported(
    hass: HomeAssistant,
    mqtt_mock: MagicMock,
    entry: MockConfigEntry,
) -> None:
    """Another panel defining <zigsight-panel> is reported, ours still registers."""
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path="zigbee-tools",
        webcomponent_name="zigsight-panel",
        js_url="/local/community/zigsight/zigsight-panel.js",
    )
    # Unrelated custom panels are ignored
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path="other",
        webcomponent_name="other-panel",
        module_url="/local/other.js",
    )

    await _setup(hass, entry)
    assert hass.data[DATA_PANEL_REGISTERED] is True
    issue = _legacy_issue(hass)
    assert issue is not None
    assert issue.translation_placeholders == {
        "panels": "/zigbee-tools (/local/community/zigsight/zigsight-panel.js)"
    }


async def test_legacy_issue_cleared_when_fixed(
    hass: HomeAssistant,
    mqtt_mock: MagicMock,
    entry: MockConfigEntry,
) -> None:
    """Once the old panel is gone our panel registers and the issue clears."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_LEGACY_PANEL,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_LEGACY_PANEL,
        translation_placeholders={"panels": "/zigsight (old)"},
    )
    await _setup(hass, entry)
    assert hass.data[DATA_PANEL_REGISTERED] is True
    assert _legacy_issue(hass) is None


# ---------------------------------------------------------------------------
# Topology API
# ---------------------------------------------------------------------------
async def _get_json(client: Any, path: str) -> Any:
    response = await client.get(path)
    assert response.status == 200, await response.text()
    return await response.json()


async def test_topology_inferred_then_network_map(
    hass: HomeAssistant,
    coordinator: ZigSightCoordinator,
    hass_client: ClientSessionGenerator,
) -> None:
    """Nodes keyed by IEEE; star edges until a network map arrives."""
    client = await hass_client()

    topology = await _get_json(client, "/api/zigsight/topology")
    nodes = {node["id"]: node for node in topology["nodes"]}
    assert set(nodes) == {COORDINATOR, LAMP, PLUG, CLIMATE, MOTION, DOOR}
    assert topology["nodes"][0]["id"] == COORDINATOR
    assert nodes[COORDINATOR]["type"] == "coordinator"
    assert nodes[LAMP]["label"] == "Living Room Lamp"
    assert nodes[LAMP]["type"] == "router"
    assert nodes[PLUG]["type"] == "router"
    assert nodes[MOTION]["label"] == "Kitchen/Motion Sensor"
    assert nodes[MOTION]["type"] == "end_device"
    assert topology["links_source"] == "inferred"
    assert {(e["from"], e["to"]) for e in topology["edges"]} == {
        (COORDINATOR, ieee) for ieee in (LAMP, PLUG, CLIMATE, MOTION, DOOR)
    }
    assert all(edge["inferred"] for edge in topology["edges"])
    assert topology["network_map"] == {
        "supported": True,
        "updated": None,
        "requested": None,
        "pending": False,
    }
    assert topology["network"]["channel"] == 15

    _fire_network_map(hass)
    await hass.async_block_till_done()

    topology = await _get_json(client, "/api/zigsight/topology")
    assert topology["links_source"] == "networkmap"
    assert topology["network_map"]["updated"] == NOW
    assert {(e["from"], e["to"], e["link_quality"]) for e in topology["edges"]} == {
        (COORDINATOR, LAMP, 156),
        (COORDINATOR, PLUG, 201),
        (LAMP, PLUG, 180),
        (LAMP, CLIMATE, 72),
        (PLUG, MOTION, 110),
    }
    assert not any(edge["inferred"] for edge in topology["edges"])


async def test_topology_requires_auth(
    hass: HomeAssistant,
    coordinator: ZigSightCoordinator,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """The API is not public."""
    client = await hass_client_no_auth()
    response = await client.get("/api/zigsight/topology")
    assert response.status == 401


async def test_request_network_map_admin(
    hass: HomeAssistant,
    mqtt_mock: MagicMock,
    coordinator: ZigSightCoordinator,
    hass_client: ClientSessionGenerator,
) -> None:
    """Admins can ask Zigbee2MQTT for a raw network map."""
    client = await hass_client()
    response = await client.post("/api/zigsight/topology/networkmap")
    assert response.status == 202
    body = await response.json()
    assert body == {"requested": True, "pending": False, "requested_at": NOW}

    mqtt_mock.async_publish.assert_called_once()
    topic, payload = mqtt_mock.async_publish.call_args.args[:2]
    assert topic == f"{BASE}/bridge/request/networkmap"
    assert '"type": "raw"' in payload

    topology = await _get_json(client, "/api/zigsight/topology")
    assert topology["network_map"]["requested"] == NOW
    assert topology["network_map"]["pending"] is True


async def test_request_network_map_rate_limited(
    hass: HomeAssistant,
    mqtt_mock: MagicMock,
    coordinator: ZigSightCoordinator,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A pending request isn't re-published; it expires after 2 minutes."""
    client = await hass_client()
    response = await client.post("/api/zigsight/topology/networkmap")
    assert response.status == 202
    assert mqtt_mock.async_publish.call_count == 1

    freezer.tick(timedelta(seconds=90))
    response = await client.post("/api/zigsight/topology/networkmap")
    assert response.status == 202
    assert await response.json() == {
        "requested": True,
        "pending": True,
        "requested_at": NOW,
    }
    assert mqtt_mock.async_publish.call_count == 1

    # The response arrives: no longer pending, a new request is published
    _fire_network_map(hass)
    await hass.async_block_till_done()
    assert not coordinator.network_map_pending
    response = await client.post("/api/zigsight/topology/networkmap")
    assert (await response.json())["pending"] is False
    assert mqtt_mock.async_publish.call_count == 2

    # No response within 2 minutes: the request is considered lost
    freezer.tick(timedelta(minutes=2, seconds=1))
    assert not coordinator.network_map_pending
    response = await client.post("/api/zigsight/topology/networkmap")
    assert (await response.json())["pending"] is False
    assert mqtt_mock.async_publish.call_count == 3


async def test_request_network_map_non_admin(
    hass: HomeAssistant,
    mqtt_mock: MagicMock,
    coordinator: ZigSightCoordinator,
    hass_client: ClientSessionGenerator,
    hass_read_only_access_token: str,
) -> None:
    """Non-admin users can't trigger a (mesh loading) network scan."""
    client = await hass_client(hass_read_only_access_token)
    response = await client.post("/api/zigsight/topology/networkmap")
    assert response.status == 401
    mqtt_mock.async_publish.assert_not_called()

    # Reading the topology is fine for any authenticated user
    response = await client.get("/api/zigsight/topology")
    assert response.status == 200


async def test_request_network_map_unsupported(
    hass: HomeAssistant,
    coordinator: ZigSightCoordinator,
    hass_client: ClientSessionGenerator,
) -> None:
    """ZHA mode has no raw network map."""
    client = await hass_client()
    with patch.object(
        ZigSightCoordinator,
        "network_map_supported",
        new_callable=lambda: property(lambda self: False),
    ):
        response = await client.post("/api/zigsight/topology/networkmap")
    assert response.status == 400


async def test_request_network_map_no_coordinator(
    hass: HomeAssistant,
    coordinator: ZigSightCoordinator,
    entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Endpoints answer 404 once the entry is unloaded."""
    client = await hass_client()
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    response = await client.post("/api/zigsight/topology/networkmap")
    assert response.status == 404
    response = await client.get("/api/zigsight/topology")
    assert response.status == 404


async def test_request_network_map_publish_error(
    hass: HomeAssistant,
    coordinator: ZigSightCoordinator,
    hass_client: ClientSessionGenerator,
) -> None:
    """A failing MQTT publish is reported without details."""
    from homeassistant.exceptions import HomeAssistantError  # noqa: PLC0415

    client = await hass_client()
    with patch.object(
        coordinator,
        "async_request_network_map",
        side_effect=HomeAssistantError("broker gone"),
    ):
        response = await client.post("/api/zigsight/topology/networkmap")
    assert response.status == 500
    assert "broker" not in await response.text()


# ---------------------------------------------------------------------------
# Channel recommendation API
# ---------------------------------------------------------------------------
async def test_channel_recommendation_flow(
    hass: HomeAssistant,
    coordinator: ZigSightCoordinator,
    hass_client: ClientSessionGenerator,
) -> None:
    """Current channel from bridge/info; POST computes, GET returns it."""
    client = await hass_client()

    body = await _get_json(client, "/api/zigsight/channel-recommendation")
    assert body["has_recommendation"] is False
    assert body["current_channel"] == 15
    assert body["network"]["pan_id"] == 6754

    response = await client.post(
        "/api/zigsight/channel-recommendation",
        json={"mode": "manual", "wifi_scan_data": WIFI_SCAN},
    )
    assert response.status == 200, await response.text()
    result = await response.json()
    assert result["has_recommendation"] is True
    assert result["recommended_channel"] in (11, 15, 20, 25)
    assert result["current_channel"] == 15
    assert set(result["scores"]) == {"11", "15", "20", "25"}
    assert len(result["wifi_aps"]) == 3
    assert result["explanation"]

    body = await _get_json(client, "/api/zigsight/channel-recommendation")
    assert body["has_recommendation"] is True
    assert body["recommended_channel"] == result["recommended_channel"]
    assert body["timestamp"] == result["timestamp"]
    assert body["current_channel"] == 15

    history = await _get_json(client, "/api/zigsight/recommendation-history")
    assert history["count"] == 1
    assert history["history"][0]["wifi_aps_count"] == 3


async def test_channel_recommendation_access_points_dict(
    hass: HomeAssistant,
    coordinator: ZigSightCoordinator,
    hass_client: ClientSessionGenerator,
) -> None:
    """The {"access_points": [...]} format is accepted; history is capped."""
    client = await hass_client()
    for _ in range(12):
        response = await client.post(
            "/api/zigsight/channel-recommendation",
            json={"wifi_scan_data": {"access_points": WIFI_SCAN[:1]}},
        )
        assert response.status == 200
    history = await _get_json(client, "/api/zigsight/recommendation-history")
    assert history["count"] == 10


@pytest.mark.parametrize(
    "payload",
    [
        {"mode": "manual"},
        {"mode": "manual", "wifi_scan_data": []},
        {"mode": "router_api", "wifi_scan_data": WIFI_SCAN},
        {"wifi_scan_data": [{"channel": 99, "rssi": -40}]},
        {"wifi_scan_data": [{"channel": 6, "rssi": 20}]},
        {"wifi_scan_data": [{"channel": 6}]},
        {"wifi_scan_data": "nope"},
        ["not", "a", "dict"],
    ],
)
async def test_channel_recommendation_invalid(
    hass: HomeAssistant,
    coordinator: ZigSightCoordinator,
    hass_client: ClientSessionGenerator,
    payload: Any,
) -> None:
    """Invalid scan data is rejected with 400."""
    client = await hass_client()
    response = await client.post("/api/zigsight/channel-recommendation", json=payload)
    assert response.status == 400
    assert "error" in await response.json()


async def test_channel_recommendation_invalid_json(
    hass: HomeAssistant,
    coordinator: ZigSightCoordinator,
    hass_client: ClientSessionGenerator,
) -> None:
    """A body that isn't JSON is rejected."""
    client = await hass_client()
    response = await client.post(
        "/api/zigsight/channel-recommendation", data=b"{not json"
    )
    assert response.status == 400


async def test_channel_recommendation_non_admin(
    hass: HomeAssistant,
    coordinator: ZigSightCoordinator,
    hass_client: ClientSessionGenerator,
    hass_read_only_access_token: str,
) -> None:
    """Only admins can run a recommendation (host_scan runs on the host)."""
    client = await hass_client(hass_read_only_access_token)
    response = await client.post(
        "/api/zigsight/channel-recommendation",
        json={"mode": "manual", "wifi_scan_data": WIFI_SCAN},
    )
    assert response.status == 401
    response = await client.get("/api/zigsight/channel-recommendation")
    assert response.status == 200


async def test_channel_recommendation_scanner_error(
    hass: HomeAssistant,
    coordinator: ZigSightCoordinator,
    hass_client: ClientSessionGenerator,
) -> None:
    """Scanner failures return a generic 500."""
    client = await hass_client()
    with patch(
        "custom_components.zigsight.api.create_scanner",
        side_effect=RuntimeError("iwlist: secret path"),
    ):
        response = await client.post(
            "/api/zigsight/channel-recommendation",
            json={"mode": "host_scan"},
        )
    assert response.status == 500
    assert "secret" not in await response.text()
