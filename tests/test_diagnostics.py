"""Diagnostics tests."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.zigsight.const import (
    CONF_INTEGRATION_TYPE,
    CONF_MQTT_TOPIC_PREFIX,
    DOMAIN,
    INTEGRATION_TYPE_ZIGBEE2MQTT,
)
from custom_components.zigsight.diagnostics import (
    async_get_config_entry_diagnostics,
    async_get_device_diagnostics,
)

from .z2m_replay import async_fire_messages, session_messages

CLIMATE = "0x00158d0001a2b3c4"


async def _setup(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, data: dict[str, object]
) -> MockConfigEntry:
    freezer.move_to("2026-09-24T08:20:00+00:00")
    entry = MockConfigEntry(domain=DOMAIN, version=1, minor_version=2, data=data)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    async_fire_messages(hass, session_messages())
    await hass.async_block_till_done()
    return entry


async def test_config_entry_diagnostics(
    hass: HomeAssistant, mqtt_mock: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Diagnostics use the new data shape and contain no secrets."""
    entry = await _setup(
        hass,
        freezer,
        {
            CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_ZIGBEE2MQTT,
            CONF_MQTT_TOPIC_PREFIX: "zigbee2mqtt",
            # A stale credential that somehow survived must still be redacted
            "mqtt_password": "secret",
        },
    )
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    dumped = json.dumps(diagnostics)

    assert diagnostics["config_entry"]["data"]["mqtt_password"] == "**REDACTED**"
    assert "secret" not in dumped
    assert "not-a-real-password" not in dumped
    coordinator = diagnostics["coordinator"]
    assert coordinator["source"] == "zigbee2mqtt"
    assert coordinator["bridge_state"] == "online"
    assert coordinator["network"]["channel"] == 15
    assert coordinator["network"]["pan_id"] == "**REDACTED**"
    assert coordinator["network"]["extended_pan_id"] == "**REDACTED**"
    assert coordinator["device_count"] == 5
    assert coordinator["network_links"] == 5
    # Zigbee2MQTT's passive availability timeout (1500 min)
    assert coordinator["analytics_config"]["silent_device_timeout_seconds"] == 90000

    climate = diagnostics["devices"][CLIMATE]
    assert climate["friendly_name"] == "Bedroom Climate"
    assert "state" not in climate
    assert "temperature" in climate["state_keys"]
    assert "21.5" not in json.dumps(climate)
    assert climate["history"]["entry_count"] >= 1


async def test_device_diagnostics(
    hass: HomeAssistant, mqtt_mock: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Device diagnostics receive a DeviceEntry."""
    entry = await _setup(
        hass,
        freezer,
        {
            CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_ZIGBEE2MQTT,
            CONF_MQTT_TOPIC_PREFIX: "zigbee2mqtt",
        },
    )
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device(identifiers={(DOMAIN, CLIMATE)})
    assert device is not None
    diagnostics = await async_get_device_diagnostics(hass, entry, device)
    assert diagnostics["ieee_address"] == CLIMATE
    assert diagnostics["metrics"]["battery"] == 87
    assert diagnostics["history"]["entries"]
    assert diagnostics["analytics_metrics"]["health_score"] is not None

    bridge = dev_reg.async_get_device(
        identifiers={(DOMAIN, f"{entry.entry_id}_bridge")}
    )
    assert bridge is not None
    assert await async_get_device_diagnostics(hass, entry, bridge) == {
        "error": "Device not tracked by ZigSight"
    }
