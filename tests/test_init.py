"""Integration tests for ZigSight setup/unload against a real ``hass``.

Unlike the pure unit tests (which use a ``MagicMock`` hass to exercise
logic), these tests use the real Home Assistant test harness
(`pytest-homeassistant-custom-component`) to verify the integration actually
loads through the real config-entry / platform-setup machinery.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    MockUser,
    async_fire_mqtt_message,
)

from custom_components.zigsight import async_remove_config_entry_device
from custom_components.zigsight.const import (
    CONF_INTEGRATION_TYPE,
    CONF_MQTT_TOPIC_PREFIX,
    DOMAIN,
    INTEGRATION_TYPE_ZHA,
    INTEGRATION_TYPE_ZIGBEE2MQTT,
)

from .z2m_replay import load_fixture_text
from .zha_test_helpers import add_mock_zha_config_entry

Z2M_DATA = {
    CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_ZIGBEE2MQTT,
    CONF_MQTT_TOPIC_PREFIX: "zigbee2mqtt",
}


@pytest.mark.asyncio
async def test_setup_and_unload_zigbee2mqtt_entry(
    hass: HomeAssistant, mqtt_mock: MagicMock
) -> None:
    """A Zigbee2MQTT config entry should load, subscribe, and unload cleanly."""
    entry = MockConfigEntry(domain=DOMAIN, version=1, minor_version=2, data=Z2M_DATA)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert DOMAIN in hass.data
    assert entry.entry_id in hass.data[DOMAIN]

    # The coordinator should have subscribed to the wildcard Z2M topic
    # through Home Assistant's MQTT integration.
    subscribed_topics = {
        call.args[0] for call in mqtt_mock.async_subscribe.call_args_list
    }
    assert "zigbee2mqtt/#" in subscribed_topics

    # The ZigSight bridge device exists before any Zigbee device
    bridge = dr.async_get(hass).async_get_device(
        identifiers={(DOMAIN, f"{entry.entry_id}_bridge")}
    )
    assert bridge is not None
    assert bridge.name == "Zigbee2MQTT bridge"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert entry.entry_id not in hass.data.get(DOMAIN, {})


@pytest.mark.asyncio
async def test_setup_and_unload_zha_entry(hass: HomeAssistant) -> None:
    """A ZHA config entry loads and unloads cleanly without MQTT.

    A loaded ZHA config entry is required (ConfigEntryNotReady otherwise,
    see test_setup_zha_entry_not_ready_without_zha); no real ZHA
    radio/gateway is involved, and with no ZHA devices registered no
    ZigSight devices are collected.
    """
    add_mock_zha_config_entry(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_ZHA},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert coordinator.data is not None
    assert coordinator.data["devices"] == {}
    bridge = dr.async_get(hass).async_get_device(
        identifiers={(DOMAIN, f"{entry.entry_id}_bridge")}
    )
    assert bridge is not None
    assert bridge.name == "ZHA network"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.asyncio
async def test_setup_zha_entry_not_ready_without_zha(hass: HomeAssistant) -> None:
    """A ZHA entry retries setup until the ZHA integration is loaded."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_ZHA},
    )
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert entry.entry_id not in hass.data.get(DOMAIN, {})


@pytest.mark.asyncio
async def test_failed_first_refresh_releases_mqtt_subscription(
    hass: HomeAssistant, mqtt_mock: MagicMock
) -> None:
    """If setup fails after subscribing, nothing keeps listening to MQTT."""
    entry = MockConfigEntry(domain=DOMAIN, version=1, minor_version=2, data=Z2M_DATA)
    entry.add_to_hass(hass)
    with patch(
        "custom_components.zigsight.coordinator.ZigSightCoordinator._async_update_data",
        side_effect=UpdateFailed("boom"),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert entry.entry_id not in hass.data.get(DOMAIN, {})
    subscribed = {sub.topic for sub in hass.data["mqtt"].client.subscriptions}
    assert "zigbee2mqtt/#" not in subscribed

    async_fire_mqtt_message(
        hass, "zigbee2mqtt/bridge/devices", load_fixture_text("bridge_devices.json")
    )
    await hass.async_block_till_done()
    assert not er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)


@pytest.mark.asyncio
async def test_remove_device_without_coordinator(hass: HomeAssistant) -> None:
    """Devices of a not loaded entry, or unknown devices, can be removed."""
    add_mock_zha_config_entry(hass)
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_ZHA}
    )
    entry.add_to_hass(hass)
    device = MagicMock()
    device.identifiers = {("other", "x"), (DOMAIN, "0x1")}
    assert await async_remove_config_entry_device(hass, entry, device)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert await async_remove_config_entry_device(hass, entry, device)


@pytest.mark.asyncio
async def test_services_unregistered_after_last_entry_unload(
    hass: HomeAssistant,
) -> None:
    """Services are dropped once the last entry unloads.

    ``recommend_channel`` stashes a ``last_recommendation`` key straight in
    ``hass.data[DOMAIN]`` (not scoped to any entry_id), so that dict is
    never actually empty once the service has run -- it must not be used
    to decide whether any entry is still loaded.
    """
    add_mock_zha_config_entry(hass)
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_ZHA}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, "recommend_channel")
    assert hass.services.has_service(DOMAIN, "enable_zha_diagnostic_entities")

    # Simulate recommend_channel having already stored its last result.
    hass.data[DOMAIN]["last_recommendation"] = {"recommended_channel": 15}

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.services.has_service(DOMAIN, "recommend_channel")
    assert not hass.services.has_service(DOMAIN, "enable_zha_diagnostic_entities")


@pytest.mark.asyncio
async def test_recommend_channel_service_returns_response(
    hass: HomeAssistant,
) -> None:
    """The service validates its schema and returns the recommendation."""
    add_mock_zha_config_entry(hass)
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_ZHA}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.services.async_call(
        DOMAIN,
        "recommend_channel",
        {
            "mode": "manual",
            "wifi_scan_data": [
                {"channel": 1, "rssi": -40, "ssid": "home"},
                {"channel": 6, "rssi": -45},
            ],
        },
        blocking=True,
        return_response=True,
    )

    assert result["recommended_channel"] in (11, 15, 20, 25)
    assert set(result["scores"]) == {11, 15, 20, 25}
    assert result["wifi_aps_count"] == 2
    assert result["explanation"]
    assert (
        hass.data[DOMAIN]["last_recommendation"]["recommended_channel"]
        == (result["recommended_channel"])
    )

    # Schema rejects unsupported modes (e.g. the non-functional router_api).
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "recommend_channel",
            {"mode": "router_api"},
            blocking=True,
        )


@pytest.mark.asyncio
async def test_recommend_channel_service_requires_admin(
    hass: HomeAssistant, hass_read_only_user: MockUser
) -> None:
    """host_scan runs subprocesses on the host, so the service is admin-only."""
    add_mock_zha_config_entry(hass)
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_ZHA}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            "recommend_channel",
            {"mode": "manual", "wifi_scan_data": []},
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )
