"""Tests for the ZigSight config flow and options flow using the real flow manager."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
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
    """The Zigbee2MQTT path: user -> zigbee2mqtt -> common -> create entry.

    ``async_setup_entry`` is patched out here: once the flow reaches
    CREATE_ENTRY, Home Assistant's flow manager immediately adds *and sets
    up* the resulting config entry for real. Since no `mqtt` config entry
    (and no ``mqtt_mock``) exists in this test, the coordinator's MQTT
    subscribe would fall back to the direct-``aiomqtt`` path, which isn't
    installed in the test environment (it's only pulled in when the
    integration actually needs it) and would fail with
    ``ModuleNotFoundError`` -- silently, since a config-entry setup failure
    only shows up as ``ConfigEntryState.SETUP_ERROR``, not a raised
    exception here. This test only cares about the *flow* steps, so real
    entry setup is stubbed out.
    """
    with patch(
        "custom_components.zigsight.async_setup_entry", return_value=True
    ) as mock_setup_entry:
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

        mock_setup_entry.assert_called_once()


@pytest.mark.asyncio
async def test_zha_full_flow(hass: HomeAssistant) -> None:
    """The ZHA path: user -> common -> create entry (no MQTT step).

    ``async_setup_entry`` is patched out for the same reason as in
    ``test_zigbee2mqtt_full_flow`` -- this test only cares about the flow
    steps, not about actually setting up the resulting entry.
    """
    with patch(
        "custom_components.zigsight.async_setup_entry", return_value=True
    ) as mock_setup_entry:
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

        mock_setup_entry.assert_called_once()


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


@pytest.mark.asyncio
async def test_options_flow_form_defaults_from_entry_data(
    hass: HomeAssistant,
) -> None:
    """With no options set yet, the form should default from entry.data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_ZHA,
            CONF_BATTERY_DRAIN_THRESHOLD: 42.0,
            CONF_RECONNECT_RATE_THRESHOLD: 3.5,
            CONF_RECONNECT_RATE_WINDOW_HOURS: 6,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    schema = result["data_schema"].schema
    defaults = {str(key): key.default() for key in schema if hasattr(key, "default")}
    assert defaults[CONF_BATTERY_DRAIN_THRESHOLD] == 42.0
    assert defaults[CONF_RECONNECT_RATE_THRESHOLD] == 3.5
    assert defaults[CONF_RECONNECT_RATE_WINDOW_HOURS] == 6


@pytest.mark.asyncio
async def test_options_flow_reloads_zigbee2mqtt_entry(
    hass: HomeAssistant, mqtt_mock: None
) -> None:
    """Changing options on a loaded Z2M entry should reload it.

    The new analytics threshold should then be applied to the coordinator.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_ZIGBEE2MQTT,
            CONF_MQTT_TOPIC_PREFIX: "zigbee2mqtt",
            CONF_BATTERY_DRAIN_THRESHOLD: 10.0,
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_BATTERY_DRAIN_THRESHOLD: 25.0,
            CONF_RECONNECT_RATE_THRESHOLD: 5.0,
            CONF_RECONNECT_RATE_WINDOW_HOURS: 24,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert coordinator._analytics.battery_drain_threshold == 25.0
