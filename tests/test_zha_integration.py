"""End-to-end ZHA mode tests through the real config-entry setup."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.zigsight.const import (
    CONF_INTEGRATION_TYPE,
    DOMAIN,
    INTEGRATION_TYPE_ZHA,
    ISSUE_ZHA_DIAGNOSTICS_DISABLED,
)
from custom_components.zigsight.zha_collector import async_discover_devices

from .zha_test_helpers import add_mock_zha_config_entry, add_mock_zha_device

IEEE = "00:11:22:33:44:55:66:77"


async def _setup_zigsight_zha_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_ZHA}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    return entry


async def test_zha_device_creates_zigsight_entities(hass: HomeAssistant) -> None:
    """A ZHA device with enabled diagnostics gets ZigSight entities/values."""
    zha_entry = add_mock_zha_config_entry(hass)
    add_mock_zha_device(
        hass,
        zha_entry,
        IEEE,
        lqi_disabled_by=None,
        rssi_disabled_by=None,
        lqi_state="180",
        rssi_state="-55",
        battery_state="90",
    )

    await _setup_zigsight_zha_entry(hass)

    # ZigSight's own entities use ``<ieee>_<key>`` unique ids; look them up
    # in the entity registry rather than guessing the generated entity id.
    ent_reg = er.async_get(hass)
    link_quality_entity_id = ent_reg.async_get_entity_id(
        "sensor", DOMAIN, f"{IEEE}_link_quality"
    )
    assert link_quality_entity_id is not None
    state = hass.states.get(link_quality_entity_id)
    assert state is not None
    assert state.state == "180.0"

    battery_entity_id = ent_reg.async_get_entity_id("sensor", DOMAIN, f"{IEEE}_battery")
    assert battery_entity_id is not None
    battery_state = hass.states.get(battery_entity_id)
    assert battery_state is not None
    assert battery_state.state == "90.0"


async def test_zha_live_update_and_reconnect_counting(hass: HomeAssistant) -> None:
    """State changes push live updates; reconnects count on transitions only.

    A device is reported unavailable only once *all* of its tracked
    entities are unavailable (matching what ZHA/HA actually does when a
    device drops off the network -- every one of its entities becomes
    unavailable together), and available again as soon as any one of them
    reports a value.
    """
    zha_entry = add_mock_zha_config_entry(hass)
    add_mock_zha_device(
        hass,
        zha_entry,
        IEEE,
        lqi_disabled_by=None,
        rssi_disabled_by=None,
        lqi_state="100",
        rssi_state="-60",
        battery_state="80",
    )

    entry = await _setup_zigsight_zha_entry(hass)
    coordinator = hass.data[DOMAIN][entry.entry_id]

    info = async_discover_devices(hass)[IEEE]
    tracked_entities = info.entities.as_tuple()
    assert len(tracked_entities) == 3

    record = coordinator.get_device(IEEE)
    assert record is not None
    assert record["reconnect_count"] == 0

    for entity_id in tracked_entities:
        hass.states.async_set(entity_id, "unavailable")
    await hass.async_block_till_done()
    assert coordinator.get_device(IEEE)["available"] is False
    assert coordinator.get_device(IEEE)["reconnect_count"] == 0

    hass.states.async_set(info.entities.lqi, "150")
    await hass.async_block_till_done()
    assert coordinator.get_device(IEEE)["available"] is True
    assert coordinator.get_device(IEEE)["reconnect_count"] == 1
    assert coordinator.get_device(IEEE)["metrics"]["link_quality"] == 150

    # A repeated update with the same value must not count as another
    # reconnect (no availability transition happened).
    hass.states.async_set(info.entities.lqi, "150")
    await hass.async_block_till_done()
    assert coordinator.get_device(IEEE)["reconnect_count"] == 1


async def test_zha_repair_issue_created_and_cleared(hass: HomeAssistant) -> None:
    """A repair issue is raised while LQI/RSSI stay disabled, cleared after."""
    zha_entry = add_mock_zha_config_entry(hass)
    add_mock_zha_device(hass, zha_entry, IEEE)  # LQI/RSSI disabled by default

    await _setup_zigsight_zha_entry(hass)

    issue_reg = ir.async_get(hass)
    assert issue_reg.async_get_issue(DOMAIN, ISSUE_ZHA_DIAGNOSTICS_DISABLED) is not None

    # The service enables them and clears the issue.
    response = await hass.services.async_call(
        DOMAIN,
        "enable_zha_diagnostic_entities",
        {},
        blocking=True,
        return_response=True,
    )
    assert response["enabled_count"] == 2
    assert len(response["entity_ids"]) == 2
    assert issue_reg.async_get_issue(DOMAIN, ISSUE_ZHA_DIAGNOSTICS_DISABLED) is None


async def test_zha_service_never_reenables_user_disabled(hass: HomeAssistant) -> None:
    """The service never flips an entity a user explicitly disabled."""
    zha_entry = add_mock_zha_config_entry(hass)
    add_mock_zha_device(
        hass,
        zha_entry,
        IEEE,
        rssi_disabled_by=er.RegistryEntryDisabler.USER,
    )

    await _setup_zigsight_zha_entry(hass)

    response = await hass.services.async_call(
        DOMAIN,
        "enable_zha_diagnostic_entities",
        {},
        blocking=True,
        return_response=True,
    )
    assert response["enabled_count"] == 1  # only LQI (default-disabled)

    ent_reg = er.async_get(hass)
    rssi_entity_id = async_discover_devices(hass)[IEEE].entities.rssi
    entry = ent_reg.async_get(rssi_entity_id)
    assert entry is not None
    assert entry.disabled_by is er.RegistryEntryDisabler.USER
