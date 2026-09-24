"""Tests for the ZigSight config flow and options flow using the real flow manager."""

from __future__ import annotations

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.zigsight.const import (
    CONF_BATTERY_DRAIN_THRESHOLD,
    CONF_INTEGRATION_TYPE,
    CONF_MQTT_BROKER,
    CONF_MQTT_TOPIC_PREFIX,
    CONF_RECONNECT_RATE_THRESHOLD,
    CONF_RECONNECT_RATE_WINDOW_HOURS,
    DOMAIN,
    INTEGRATION_TYPE_ZHA,
    INTEGRATION_TYPE_ZIGBEE2MQTT,
)


@pytest.mark.asyncio
async def test_zigbee2mqtt_full_flow(hass: HomeAssistant) -> None:
    """The Zigbee2MQTT path: user -> zigbee2mqtt -> common -> create entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_ZIGBEE2MQTT},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zigbee2mqtt"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_MQTT_BROKER: "core-mosquitto",
            "mqtt_port": 1883,
            CONF_MQTT_TOPIC_PREFIX: "zigbee2mqtt",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "common"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ZigSight"
    assert result["data"][CONF_INTEGRATION_TYPE] == INTEGRATION_TYPE_ZIGBEE2MQTT
    assert result["data"][CONF_MQTT_BROKER] == "core-mosquitto"

    await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_zha_full_flow(hass: HomeAssistant) -> None:
    """The ZHA path: user -> common -> create entry (no MQTT step)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_ZHA},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "common"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_INTEGRATION_TYPE] == INTEGRATION_TYPE_ZHA

    await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_single_instance_allowed(hass: HomeAssistant) -> None:
    """A second config entry should be aborted."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_ZHA},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


@pytest.mark.asyncio
async def test_options_flow_defaults_and_update(hass: HomeAssistant) -> None:
    """The options flow should show current thresholds and persist changes."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_ZHA},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_BATTERY_DRAIN_THRESHOLD: 15.0,
            CONF_RECONNECT_RATE_THRESHOLD: 7.5,
            CONF_RECONNECT_RATE_WINDOW_HOURS: 12,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    assert entry.options[CONF_BATTERY_DRAIN_THRESHOLD] == 15.0
    assert entry.options[CONF_RECONNECT_RATE_THRESHOLD] == 7.5
    assert entry.options[CONF_RECONNECT_RATE_WINDOW_HOURS] == 12
