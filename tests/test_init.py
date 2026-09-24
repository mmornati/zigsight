"""Integration tests for ZigSight setup/unload against a real ``hass``.

Unlike the rest of the unit-test suite (which uses a ``MagicMock`` hass to
exercise pure logic), these tests use the real Home Assistant test harness
(`pytest-homeassistant-custom-component`) to verify the integration actually
loads through the real config-entry / platform-setup machinery.
"""

from __future__ import annotations

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.zigsight.const import (
    CONF_INTEGRATION_TYPE,
    CONF_MQTT_TOPIC_PREFIX,
    DOMAIN,
    INTEGRATION_TYPE_ZHA,
    INTEGRATION_TYPE_ZIGBEE2MQTT,
)


@pytest.mark.asyncio
async def test_setup_and_unload_zigbee2mqtt_entry(
    hass: HomeAssistant, mqtt_mock: None
) -> None:
    """A Zigbee2MQTT config entry should load and unload cleanly."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_ZIGBEE2MQTT,
            CONF_MQTT_TOPIC_PREFIX: "zigbee2mqtt",
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert DOMAIN in hass.data
    assert entry.entry_id in hass.data[DOMAIN]

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert entry.entry_id not in hass.data.get(DOMAIN, {})


@pytest.mark.asyncio
async def test_setup_and_unload_zha_entry(hass: HomeAssistant) -> None:
    """A ZHA config entry should currently still load and unload cleanly.

    NOTE: the ZHA data collection path (``ZHACollector.collect_devices``) is
    known-broken against modern ZHA (see REVIEW.md C2 / the follow-up PR that
    rewrites ``zha_collector.py``): because the real ``zha`` integration is
    not set up in this test, ``ZHACollector.is_available()`` returns False
    and no devices are ever collected, so today this does NOT raise -- it
    just means ZigSight silently reports zero ZHA devices. That "silently
    does nothing useful for ZHA" behaviour is what a later PR fixes; this
    test only pins down today's (non-erroring) setup/unload behaviour.
    """
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

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
