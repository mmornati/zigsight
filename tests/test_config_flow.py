"""Tests for the ZigSight config flow and options flow using the real flow manager."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.zigsight.const import (
    CONF_BATTERY_DRAIN_THRESHOLD,
    CONF_INTEGRATION_TYPE,
    CONF_MQTT_TOPIC_PREFIX,
    CONF_RECONNECT_RATE_THRESHOLD,
    CONF_RECONNECT_RATE_WINDOW_HOURS,
    DOMAIN,
    INTEGRATION_TYPE_ZHA,
    INTEGRATION_TYPE_ZIGBEE2MQTT,
)

from .zha_test_helpers import add_mock_zha_config_entry


@pytest.mark.asyncio
async def test_zigbee2mqtt_full_flow(hass: HomeAssistant, mqtt_mock: MagicMock) -> None:
    """The Zigbee2MQTT path: user -> zigbee2mqtt (base topic) -> common.

    No broker settings are asked any more: Zigbee2MQTT messages are received
    through Home Assistant's MQTT integration (``mqtt_mock`` sets it up).
    ``async_setup_entry`` is patched out because this test only covers the
    flow steps.
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
        assert set(map(str, result["data_schema"].schema)) == {CONF_MQTT_TOPIC_PREFIX}

        # Invalid base topics are rejected
        for bad in ("", "zigbee2mqtt/#", "zigbee2mqtt/+/x", "/"):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {CONF_MQTT_TOPIC_PREFIX: bad}
            )
            assert result["type"] is FlowResultType.FORM
            assert result["errors"] == {CONF_MQTT_TOPIC_PREFIX: "invalid_topic_prefix"}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_MQTT_TOPIC_PREFIX: "zigbee2mqtt/"},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "common"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "ZigSight"
        assert result["data"] == {
            CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_ZIGBEE2MQTT,
            CONF_MQTT_TOPIC_PREFIX: "zigbee2mqtt",
            CONF_BATTERY_DRAIN_THRESHOLD: 10.0,
            CONF_RECONNECT_RATE_THRESHOLD: 5.0,
            CONF_RECONNECT_RATE_WINDOW_HOURS: 24,
        }
        assert result["result"].version == 1
        assert result["result"].minor_version == 2

        await hass.async_block_till_done()

        mock_setup_entry.assert_called_once()


@pytest.mark.asyncio
async def test_zigbee2mqtt_flow_aborts_without_mqtt(hass: HomeAssistant) -> None:
    """Choosing Zigbee2MQTT without the MQTT integration aborts clearly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_ZIGBEE2MQTT},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "mqtt_not_available"


@pytest.mark.asyncio
async def test_zha_full_flow(hass: HomeAssistant) -> None:
    """The ZHA path: user -> common -> create entry (no MQTT step).

    ``async_setup_entry`` is patched out for the same reason as in
    ``test_zigbee2mqtt_full_flow`` -- this test only cares about the flow
    steps, not about actually setting up the resulting entry.
    """
    add_mock_zha_config_entry(hass)
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
async def test_zha_not_configured_aborts(hass: HomeAssistant) -> None:
    """Selecting ZHA with no ZHA config entry set up aborts with a clear reason."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_ZHA},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "zha_not_available"


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
    hass: HomeAssistant, mqtt_mock: MagicMock
) -> None:
    """Changing options on a loaded Z2M entry should reload it.

    The new analytics threshold should then be applied to the coordinator.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=2,
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
