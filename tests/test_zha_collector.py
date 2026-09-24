"""Tests for zha_collector.py against the real device/entity registries."""

from __future__ import annotations

from datetime import datetime

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.zigsight.zha_collector import (
    ZHACollector,
    async_count_disabled_diagnostic_entities,
    async_discover_devices,
    async_enable_diagnostic_entities,
    async_get_zha_config_entries,
)

from .zha_test_helpers import add_mock_zha_config_entry, add_mock_zha_device

IEEE = "00:11:22:33:44:55:66:77"


async def test_no_zha_entries(hass: HomeAssistant) -> None:
    """Without a loaded ZHA entry, nothing is discovered/available."""
    assert async_get_zha_config_entries(hass) == []
    assert async_discover_devices(hass) == {}
    collector = ZHACollector(hass)
    assert collector.is_available() is False
    assert await collector.collect_devices() == {}


async def test_discover_device_with_disabled_diagnostics(hass: HomeAssistant) -> None:
    """LQI/RSSI (disabled by default) and battery are found for a device."""
    zha_entry = add_mock_zha_config_entry(hass)
    device = add_mock_zha_device(hass, zha_entry, IEEE, name="Living room plug")

    devices = async_discover_devices(hass)
    assert list(devices) == [IEEE]
    info = devices[IEEE]
    assert info.ha_device_id == device.id
    assert info.name == "Living room plug"
    assert info.entities.lqi is not None
    assert info.entities.rssi is not None
    assert info.entities.battery is not None
    # Not derivable from the registries (see zha_collector docstring).
    assert info.device_type == "unknown"


async def test_collect_devices_reads_enabled_entity_states(hass: HomeAssistant) -> None:
    """Values are read from hass.states for enabled tracked entities."""
    zha_entry = add_mock_zha_config_entry(hass)
    add_mock_zha_device(
        hass,
        zha_entry,
        IEEE,
        lqi_disabled_by=None,
        rssi_disabled_by=None,
        lqi_state="200",
        rssi_state="-40",
        battery_state="77",
    )

    collector = ZHACollector(hass)
    assert collector.is_available() is True
    devices = await collector.collect_devices()
    assert list(devices) == [IEEE]
    data = devices[IEEE]
    assert data["metrics"]["link_quality"] == 200
    assert data["metrics"]["rssi"] == -40
    assert data["metrics"]["battery"] == 77
    assert data["available"] is True


async def test_collect_devices_disabled_entities_have_no_state(
    hass: HomeAssistant,
) -> None:
    """Disabled (default) LQI/RSSI entities have no state to read."""
    zha_entry = add_mock_zha_config_entry(hass)
    add_mock_zha_device(hass, zha_entry, IEEE)  # LQI/RSSI disabled by default

    collector = ZHACollector(hass)
    devices = await collector.collect_devices()
    data = devices[IEEE]
    assert "link_quality" not in data["metrics"]
    assert "rssi" not in data["metrics"]
    # Battery is enabled by default and has a state.
    assert data["metrics"]["battery"] == 85


async def test_collect_devices_unavailable_entity(hass: HomeAssistant) -> None:
    """An 'unavailable' tracked entity is reported as such."""
    zha_entry = add_mock_zha_config_entry(hass)
    add_mock_zha_device(
        hass,
        zha_entry,
        IEEE,
        lqi_disabled_by=None,
        rssi_disabled_by=None,
        lqi_state="unavailable",
        rssi_state="unavailable",
        battery_state=None,
        create_battery=False,
    )

    collector = ZHACollector(hass)
    devices = await collector.collect_devices()
    data = devices[IEEE]
    assert data["available"] is False
    assert data["metrics"] == {}


async def test_async_setup_pushes_state_changes(hass: HomeAssistant) -> None:
    """State changes of tracked entities push a live update through."""
    zha_entry = add_mock_zha_config_entry(hass)
    add_mock_zha_device(
        hass,
        zha_entry,
        IEEE,
        lqi_disabled_by=None,
        rssi_disabled_by=None,
        lqi_state="100",
    )
    devices = async_discover_devices(hass)
    lqi_entity_id = devices[IEEE].entities.lqi
    assert lqi_entity_id is not None

    updates: list[tuple[str, dict]] = []
    collector = ZHACollector(hass)
    collector.async_setup(lambda ieee, data: updates.append((ieee, data)))

    hass.states.async_set(lqi_entity_id, "150")
    await hass.async_block_till_done()

    assert updates
    ieee, data = updates[-1]
    assert ieee == IEEE
    assert data["metrics"]["link_quality"] == 150

    collector.async_stop()
    hass.states.async_set(lqi_entity_id, "160")
    await hass.async_block_till_done()
    # No further updates once stopped.
    assert len(updates) == len(updates)  # still the same last entry
    assert updates[-1][1]["metrics"]["link_quality"] == 150


async def test_enable_diagnostic_entities_skips_user_disabled(
    hass: HomeAssistant,
) -> None:
    """Only entities disabled by the integration default are enabled."""
    zha_entry = add_mock_zha_config_entry(hass)
    add_mock_zha_device(
        hass,
        zha_entry,
        IEEE,
        lqi_disabled_by=er.RegistryEntryDisabler.INTEGRATION,
        rssi_disabled_by=er.RegistryEntryDisabler.USER,
    )

    assert async_count_disabled_diagnostic_entities(hass) == 1
    enabled = async_enable_diagnostic_entities(hass)
    assert len(enabled) == 1

    ent_reg = er.async_get(hass)
    devices = async_discover_devices(hass)
    lqi_entry = ent_reg.async_get(devices[IEEE].entities.lqi)
    rssi_entry = ent_reg.async_get(devices[IEEE].entities.rssi)
    assert lqi_entry is not None and lqi_entry.disabled_by is None
    assert rssi_entry is not None
    assert rssi_entry.disabled_by is er.RegistryEntryDisabler.USER

    # Idempotent: nothing left to enable.
    assert async_count_disabled_diagnostic_entities(hass) == 0
    assert async_enable_diagnostic_entities(hass) == []


async def test_enable_diagnostic_entities_no_devices(hass: HomeAssistant) -> None:
    """No ZHA devices -> nothing to enable."""
    assert async_enable_diagnostic_entities(hass) == []
    assert async_count_disabled_diagnostic_entities(hass) == 0


async def test_collect_device_ignores_restored_unavailable_state(
    hass: HomeAssistant,
) -> None:
    """A 'restored' unavailable stub (entity briefly unloaded) is ignored.

    Home Assistant writes this stub state (``unavailable`` with attribute
    ``restored: True``) when an entity is removed while HA keeps running --
    e.g. while ZHA reloads its config entry after
    ``zigsight.enable_zha_diagnostic_entities`` runs. It must not look like
    the underlying Zigbee device actually went offline.
    """
    zha_entry = add_mock_zha_config_entry(hass)
    add_mock_zha_device(
        hass,
        zha_entry,
        IEEE,
        lqi_disabled_by=None,
        lqi_state="100",
        rssi_disabled_by=er.RegistryEntryDisabler.INTEGRATION,
        create_battery=False,
    )
    info = async_discover_devices(hass)[IEEE]
    collector = ZHACollector(hass)

    # Sanity check: a real unavailable state (no restored attribute) does
    # mark the device unavailable.
    hass.states.async_set(info.entities.lqi, "unavailable")
    data = collector._collect_device(info)
    assert data["available"] is False

    # The "restored" stub is different: neither available nor unavailable.
    hass.states.async_set(info.entities.lqi, "unavailable", {"restored": True})
    data = collector._collect_device(info)
    assert data["available"] is None
    assert data["metrics"] == {}


async def test_collect_device_last_seen_from_entity_state(hass: HomeAssistant) -> None:
    """last_seen is derived from a tracked entity's own timestamp."""
    zha_entry = add_mock_zha_config_entry(hass)
    add_mock_zha_device(
        hass,
        zha_entry,
        IEEE,
        lqi_disabled_by=None,
        lqi_state="100",
        create_battery=False,
    )
    info = async_discover_devices(hass)[IEEE]
    collector = ZHACollector(hass)

    data = collector._collect_device(info)
    assert isinstance(data["last_seen"], datetime)

    # No non-restored, non-unavailable tracked entity -> no last_seen.
    for entity_id in info.entities.as_tuple():
        hass.states.async_set(entity_id, "unavailable", {"restored": True})
    data = collector._collect_device(info)
    assert data["last_seen"] is None
