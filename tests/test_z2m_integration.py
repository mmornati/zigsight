"""End-to-end tests: recorded Zigbee2MQTT traffic -> ZigSight devices/entities.

These tests run the real integration against Home Assistant's (mocked) MQTT
integration and replay the fixtures in ``tests/fixtures/z2m`` with
``async_fire_mqtt_message``.
"""

from __future__ import annotations

import copy
import logging
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, UnitOfElectricPotential
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.zigsight import async_remove_config_entry_device
from custom_components.zigsight.const import (
    CONF_INTEGRATION_TYPE,
    CONF_MQTT_TOPIC_PREFIX,
    DOMAIN,
    EVENT_DEVICE_UPDATE,
    INTEGRATION_TYPE_ZIGBEE2MQTT,
)
from custom_components.zigsight.coordinator import ZigSightCoordinator

from .registry_helpers import deprecation_reports, get_device
from .z2m_replay import (
    async_fire,
    async_fire_messages,
    load_fixture,
    session_messages,
)

BASE = "zigbee2mqtt"
NOW = "2026-09-24T08:20:00+00:00"

LAMP = "0x0017880104e45517"
PLUG = "0x000d6ffffe1a2b3c"
CLIMATE = "0x00158d0001a2b3c4"
MOTION = "0x001788010b2c3d4e"
DOOR = "0x00158d000aabbccd"
COORDINATOR = "0x00124b0024c1a2b3"


def _messages_without_networkmap() -> list[Any]:
    return [m for m in session_messages() if not m.topic.endswith("networkmap")]


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


async def _setup(
    hass: HomeAssistant, entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> ZigSightCoordinator:
    freezer.move_to(NOW)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    return hass.data[DOMAIN][entry.entry_id]


@pytest.fixture
async def coordinator(
    hass: HomeAssistant,
    mqtt_mock: MagicMock,
    entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> ZigSightCoordinator:
    """Set up the integration and replay the recorded session."""
    coord = await _setup(hass, entry, freezer)
    async_fire_messages(hass, _messages_without_networkmap())
    await hass.async_block_till_done()
    return coord


def _entity_id(hass: HomeAssistant, domain: str, unique_id: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(domain, DOMAIN, unique_id)
    assert entity_id is not None, f"no {domain} entity with unique id {unique_id}"
    return entity_id


def _state(hass: HomeAssistant, domain: str, unique_id: str) -> Any:
    state = hass.states.get(_entity_id(hass, domain, unique_id))
    assert state is not None
    return state


async def test_subscribes_to_base_topic(
    hass: HomeAssistant,
    mqtt_mock: MagicMock,
    entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A single wildcard subscription through HA's MQTT integration."""
    await _setup(hass, entry, freezer)
    topics = [call.args[0] for call in mqtt_mock.async_subscribe.call_args_list]
    assert f"{BASE}/#" in topics
    # No entities until bridge/devices has been received
    assert not er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)


async def test_entities_created_from_bridge_devices(
    hass: HomeAssistant, entry: MockConfigEntry, coordinator: ZigSightCoordinator
) -> None:
    """Every enabled, non-coordinator device gets IEEE based entities."""
    entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    unique_ids = {entity.unique_id for entity in entities}

    router_keys = {
        "link_quality",
        "reconnect_rate",
        "health_score",
        "connectivity_warning",
    }
    battery_keys = router_keys | {
        "battery",
        "battery_trend",
        "battery_drain_warning",
    }
    expected = (
        {f"{LAMP}_{key}" for key in router_keys}
        | {f"{PLUG}_{key}" for key in router_keys}
        | {f"{CLIMATE}_{key}" for key in battery_keys | {"voltage"}}
        | {f"{MOTION}_{key}" for key in battery_keys}
    )
    assert unique_ids == expected
    # Coordinator and disabled device have no entities
    assert not any(uid.startswith((COORDINATOR, DOOR)) for uid in unique_ids)
    assert all(entity.has_entity_name for entity in entities)
    assert all(entity.translation_key for entity in entities)

    # Entity ids derive from the Zigbee2MQTT friendly name + translated name
    assert _entity_id(hass, "sensor", f"{CLIMATE}_battery") == (
        "sensor.bedroom_climate_battery"
    )
    assert _entity_id(hass, "sensor", f"{MOTION}_link_quality") == (
        "sensor.kitchen_motion_sensor_link_quality"
    )


async def test_device_registry(
    hass: HomeAssistant, entry: MockConfigEntry, coordinator: ZigSightCoordinator
) -> None:
    """Devices carry model/manufacturer from bridge/devices, via the bridge."""
    dev_reg = dr.async_get(hass)
    bridge = get_device(hass, coordinator.bridge_identifier)
    assert bridge is not None
    assert bridge.entry_type is dr.DeviceEntryType.SERVICE
    # bridge/info updated the bridge device
    assert bridge.sw_version == "2.1.3"
    assert bridge.model == "zStack3x0"

    climate = get_device(hass, (DOMAIN, CLIMATE))
    assert climate is not None
    assert climate.name == "Bedroom Climate"
    assert climate.manufacturer == "Aqara"
    assert climate.model == "Temperature, humidity and pressure sensor"
    assert climate.model_id == "WSDCGQ11LM"
    assert climate.via_device_id == bridge.id

    lamp = get_device(hass, (DOMAIN, LAMP))
    assert lamp is not None
    assert lamp.manufacturer == "Philips"
    assert lamp.sw_version == "1.93.11"
    assert lamp.via_device_id == bridge.id

    assert get_device(hass, (DOMAIN, COORDINATOR)) is None
    assert get_device(hass, (DOMAIN, DOOR)) is None
    devices = dr.async_entries_for_config_entry(dev_reg, entry.entry_id)
    # 4 Zigbee devices + the ZigSight bridge device
    assert len(devices) == 5


async def test_states_and_partial_merge(
    hass: HomeAssistant, coordinator: ZigSightCoordinator
) -> None:
    """States come from device messages; partial payloads are merged."""
    # Partial update changed the link quality only
    assert _state(hass, "sensor", f"{CLIMATE}_link_quality").state == "69"
    assert _state(hass, "sensor", f"{CLIMATE}_battery").state == "87"
    voltage = _state(hass, "sensor", f"{CLIMATE}_voltage")
    assert voltage.state == "2985"
    assert (
        voltage.attributes["unit_of_measurement"] == UnitOfElectricPotential.MILLIVOLT
    )
    assert _state(hass, "sensor", f"{MOTION}_battery").state == "64"

    record = coordinator.get_device(CLIMATE)
    assert record is not None
    # last_seen from the payload (ISO_8601_local), stored as aware UTC
    assert record["metrics"]["last_seen"] == "2026-09-24T08:15:32+00:00"
    assert record["state"]["temperature"] == 21.5
    assert record["state"]["humidity"] == 55.12
    assert record["friendly_name"] == "Bedroom Climate"

    health = _state(hass, "sensor", f"{CLIMATE}_health_score")
    assert float(health.state) > 50
    # No volatile attributes on entities
    assert "last_update" not in health.attributes


async def test_set_and_group_topics_ignored(
    hass: HomeAssistant, coordinator: ZigSightCoordinator
) -> None:
    """/set commands, groups and bridge/logging don't create or alter devices."""
    assert _state(hass, "sensor", f"{LAMP}_link_quality").state == "156"
    assert _state(hass, "sensor", f"{PLUG}_link_quality").state == "201"
    lamp = coordinator.get_device(LAMP)
    assert lamp is not None
    assert lamp["state"]["state"] == "ON"
    names = {
        record["friendly_name"] for record in coordinator.get_all_devices().values()
    }
    assert "Living Room Lights" not in names
    assert "Living Room Lamp/set" not in names
    assert "bridge" not in coordinator.get_all_devices()
    assert set(coordinator.device_ids()) == {LAMP, PLUG, CLIMATE, MOTION, DOOR}


async def test_slash_names_resolved(
    hass: HomeAssistant, coordinator: ZigSightCoordinator
) -> None:
    """'Kitchen' and 'Kitchen/Motion Sensor' are distinct devices."""
    motion = coordinator.get_device(MOTION)
    plug = coordinator.get_device(PLUG)
    assert motion is not None and plug is not None
    assert motion["state"]["occupancy"] is False
    assert "occupancy" not in plug["state"]
    assert motion["available"] is True

    async_fire(
        hass, BASE, "Kitchen/Motion Sensor", {"linkquality": 90, "occupancy": True}
    )
    await hass.async_block_till_done()
    assert _state(hass, "sensor", f"{MOTION}_link_quality").state == "90"
    assert _state(hass, "sensor", f"{PLUG}_link_quality").state == "201"


async def test_bridge_info_and_state(coordinator: ZigSightCoordinator) -> None:
    """Network info is extracted without keeping secrets from bridge/info."""
    info = coordinator.get_network_info()
    assert info is not None
    assert info["channel"] == 15
    assert info["pan_id"] == 6754
    assert info["version"] == "2.1.3"
    assert info["availability_enabled"] is True
    assert coordinator.bridge_state == "online"
    assert coordinator.coordinator_ieee == COORDINATOR
    dumped = repr(info)
    assert "not-a-real-password" not in dumped
    assert "network_key" not in dumped
    # Z2M's passive availability timeout is the silent device timeout
    assert coordinator._analytics.silent_timeout == timedelta(minutes=1500)


async def test_bridge_state_legacy_payload(
    hass: HomeAssistant, coordinator: ZigSightCoordinator
) -> None:
    """Legacy plain-text bridge/state is understood."""
    async_fire(hass, BASE, "bridge/state", "offline")
    await hass.async_block_till_done()
    assert coordinator.bridge_state == "offline"
    async_fire(hass, BASE, "bridge/state", "garbage")
    await hass.async_block_till_done()
    assert coordinator.bridge_state == "offline"


async def test_availability_and_reconnects(
    hass: HomeAssistant,
    coordinator: ZigSightCoordinator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """offline -> online transitions count as reconnects."""
    # Retained "online" at startup is not a reconnect
    for ieee in (LAMP, PLUG, CLIMATE, MOTION):
        record = coordinator.get_device(ieee)
        assert record is not None
        assert record["available"] is True
        assert record["reconnect_count"] == 0

    warning = f"{PLUG}_connectivity_warning"
    assert _state(hass, "binary_sensor", warning).state == STATE_OFF

    async_fire(hass, BASE, "Kitchen/availability", {"state": "offline"})
    await hass.async_block_till_done()
    assert _state(hass, "binary_sensor", warning).state == STATE_ON
    assert _state(hass, "binary_sensor", warning).attributes["available"] is False

    freezer.tick(timedelta(minutes=2))
    async_fire(hass, BASE, "Kitchen/availability", {"state": "online"})
    await hass.async_block_till_done()
    record = coordinator.get_device(PLUG)
    assert record is not None
    assert record["reconnect_count"] == 1
    assert record["last_reconnect"] is not None
    assert _state(hass, "binary_sensor", warning).state == STATE_OFF
    assert float(
        _state(hass, "sensor", f"{PLUG}_reconnect_rate").state
    ) == pytest.approx(1 / 24, abs=1e-3)

    # Legacy plain-text availability, repeated "online" is not a reconnect
    async_fire(hass, BASE, "Bedroom Climate/availability", "offline")
    async_fire(hass, BASE, "Bedroom Climate/availability", "online")
    async_fire(hass, BASE, "Bedroom Climate/availability", "online")
    await hass.async_block_till_done()
    record = coordinator.get_device(CLIMATE)
    assert record is not None
    assert record["reconnect_count"] == 1
    assert coordinator.get_device_reconnect_events(CLIMATE)


async def test_flapping_device_raises_connectivity_warning(
    hass: HomeAssistant,
    coordinator: ZigSightCoordinator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A reconnect rate above the threshold is a connectivity problem."""
    for _ in range(125):  # > 5 events/hour over the 24h window
        async_fire(hass, BASE, "Kitchen/availability", {"state": "offline"})
        async_fire(hass, BASE, "Kitchen/availability", {"state": "online"})
        freezer.tick(timedelta(seconds=1))
    await hass.async_block_till_done()
    assert (
        _state(hass, "binary_sensor", f"{PLUG}_connectivity_warning").state == STATE_ON
    )


async def test_rename_keeps_device_and_entities(
    hass: HomeAssistant, coordinator: ZigSightCoordinator
) -> None:
    """A rename (same IEEE, new friendly name) keeps history and entities."""
    entity_id = _entity_id(hass, "sensor", f"{CLIMATE}_battery")
    devices = load_fixture("bridge_devices.json")
    for device in devices:
        if device["ieee_address"] == CLIMATE:
            device["friendly_name"] = "Bedroom Weather"
    async_fire(hass, BASE, "bridge/devices", devices)
    await hass.async_block_till_done()

    device = get_device(hass, (DOMAIN, CLIMATE))
    assert device is not None
    assert device.name == "Bedroom Weather"
    assert _entity_id(hass, "sensor", f"{CLIMATE}_battery") == entity_id
    record = coordinator.get_device(CLIMATE)
    assert record is not None
    assert record["friendly_name"] == "Bedroom Weather"
    assert record["metrics"]["battery"] == 87  # history/state kept

    # New topic is followed, the old one is now unknown
    async_fire(hass, BASE, "Bedroom Weather", {"battery": 86})
    async_fire(hass, BASE, "Bedroom Climate", {"battery": 10})
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "86"


async def test_device_removed(
    hass: HomeAssistant, entry: MockConfigEntry, coordinator: ZigSightCoordinator
) -> None:
    """Devices missing from bridge/devices are purged with their entities."""
    entity_id = _entity_id(hass, "sensor", f"{PLUG}_link_quality")
    devices = [
        d for d in load_fixture("bridge_devices.json") if d["ieee_address"] != PLUG
    ]
    async_fire(hass, BASE, "bridge/devices", devices)
    await hass.async_block_till_done()

    assert coordinator.get_device(PLUG) is None
    assert coordinator.get_device_history(PLUG) == []
    assert get_device(hass, (DOMAIN, PLUG)) is None
    assert er.async_get(hass).async_get(entity_id) is None
    assert hass.states.get(entity_id) is None

    # Re-joining creates the entities again
    async_fire(hass, BASE, "bridge/devices", load_fixture("bridge_devices.json"))
    await hass.async_block_till_done()
    assert _entity_id(hass, "sensor", f"{PLUG}_link_quality")


async def test_new_device_joins(
    hass: HomeAssistant, coordinator: ZigSightCoordinator
) -> None:
    """A device paired after setup gets entities; early messages are kept."""
    new_ieee = "0x54ef441000a1b2c3"
    # Zigbee2MQTT may publish the first state before the updated device list
    async_fire(hass, BASE, "Hallway/Door", {"battery": 100, "linkquality": 130})
    await hass.async_block_till_done()
    assert coordinator.get_device(new_ieee) is None

    devices = load_fixture("bridge_devices.json")
    door = copy.deepcopy(next(d for d in devices if d["ieee_address"] == DOOR))
    door.update(
        {"ieee_address": new_ieee, "friendly_name": "Hallway/Door", "disabled": False}
    )
    devices.append(door)
    async_fire(hass, BASE, "bridge/devices", devices)
    await hass.async_block_till_done()

    assert _state(hass, "sensor", f"{new_ieee}_battery").state == "100"
    assert _state(hass, "sensor", f"{new_ieee}_link_quality").state == "130"
    device = get_device(hass, (DOMAIN, new_ieee))
    assert device is not None
    assert device.model_id == "MCCGQ11LM"


async def test_entities_wait_for_interview_and_follow_capabilities(
    hass: HomeAssistant, entry: MockConfigEntry, coordinator: ZigSightCoordinator
) -> None:
    """Entities are created after the interview; new capabilities add entities."""
    new_ieee = "0x00158d0009f8e7d6"
    devices = load_fixture("bridge_devices.json")
    climate = next(d for d in devices if d["ieee_address"] == CLIMATE)
    interviewing = copy.deepcopy(climate)
    interviewing.update(
        {
            "ieee_address": new_ieee,
            "friendly_name": new_ieee,
            "definition": None,
            "power_source": None,
            "interview_completed": False,
            "interviewing": True,
            "interview_state": "IN_PROGRESS",
        }
    )
    async_fire(hass, BASE, "bridge/devices", [*devices, interviewing])
    await hass.async_block_till_done()

    # Tracked, but no entities while the interview runs
    assert coordinator.get_device(new_ieee) is not None
    ent_reg = er.async_get(hass)
    assert not [
        e
        for e in er.async_entries_for_config_entry(ent_reg, entry.entry_id)
        if e.unique_id.startswith(new_ieee)
    ]

    # Interview completed (without a voltage expose yet): battery entities
    done = copy.deepcopy(climate)
    done.update({"ieee_address": new_ieee, "friendly_name": "Office Climate"})
    done["definition"]["exposes"] = [
        e for e in done["definition"]["exposes"] if e["name"] != "voltage"
    ]
    async_fire(hass, BASE, "bridge/devices", [*devices, done])
    await hass.async_block_till_done()
    for key in ("link_quality", "battery", "battery_trend", "health_score"):
        assert _entity_id(hass, "sensor", f"{new_ieee}_{key}")
    assert _entity_id(hass, "binary_sensor", f"{new_ieee}_battery_drain_warning")
    assert ent_reg.async_get_entity_id("sensor", DOMAIN, f"{new_ieee}_voltage") is None

    # A definition update adding the voltage expose adds just that entity
    with_voltage = copy.deepcopy(climate)
    with_voltage.update({"ieee_address": new_ieee, "friendly_name": "Office Climate"})
    async_fire(hass, BASE, "bridge/devices", [*devices, with_voltage])
    await hass.async_block_till_done()
    assert _entity_id(hass, "sensor", f"{new_ieee}_voltage")


async def test_empty_device_list_is_ignored(
    hass: HomeAssistant, coordinator: ZigSightCoordinator
) -> None:
    """A retained '[]' (or coordinator only) list doesn't wipe everything."""
    coordinator_only = [
        d for d in load_fixture("bridge_devices.json") if d["type"] == "Coordinator"
    ]
    async_fire(hass, BASE, "bridge/devices", [])
    async_fire(hass, BASE, "bridge/devices", coordinator_only)
    await hass.async_block_till_done()
    assert len(coordinator.device_ids()) == 5
    assert _entity_id(hass, "sensor", f"{PLUG}_link_quality")
    assert get_device(hass, (DOMAIN, PLUG))


async def test_invalid_last_seen_falls_back_to_receipt_time(
    hass: HomeAssistant, coordinator: ZigSightCoordinator
) -> None:
    """An impossible last_seen date doesn't break message processing."""
    async_fire(
        hass,
        BASE,
        "Kitchen",
        {"linkquality": 150, "last_seen": "2026-13-45T10:00:00Z"},
    )
    await hass.async_block_till_done()
    assert _state(hass, "sensor", f"{PLUG}_link_quality").state == "150"
    record = coordinator.get_device(PLUG)
    assert record is not None
    assert record["metrics"]["last_seen"] == NOW


async def test_stale_registry_devices_removed_on_startup(
    hass: HomeAssistant,
    mqtt_mock: MagicMock,
    entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Devices removed from Zigbee2MQTT while HA was down are cleaned up."""
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    gone = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "0x00000000deadbeef")}
    )
    gone_entity = ent_reg.async_get_or_create(
        "sensor",
        DOMAIN,
        "0x00000000deadbeef_link_quality",
        config_entry=entry,
        device_id=gone.id,
    )
    kept = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, PLUG)}
    )

    await _setup(hass, entry, freezer)
    async_fire_messages(hass, _messages_without_networkmap())
    await hass.async_block_till_done()

    assert dev_reg.async_get(gone.id) is None
    assert ent_reg.async_get(gone_entity.entity_id) is None
    assert dev_reg.async_get(kept.id) is not None
    bridge = get_device(hass, (DOMAIN, f"{entry.entry_id}_bridge"))
    assert bridge is not None


async def test_failed_interview_gets_base_entities(
    hass: HomeAssistant, entry: MockConfigEntry, coordinator: ZigSightCoordinator
) -> None:
    """A FAILED interview is final: base entities, since LQI is still reported."""
    failed_ieee = "0x00158d000badf00d"
    devices = load_fixture("bridge_devices.json")
    devices.append(
        {
            "ieee_address": failed_ieee,
            "friendly_name": failed_ieee,
            "type": "EndDevice",
            "definition": None,
            "disabled": False,
            "supported": False,
            "interview_completed": False,
            "interviewing": False,
            "interview_state": "FAILED",
        }
    )
    async_fire(hass, BASE, "bridge/devices", devices)
    async_fire(hass, BASE, failed_ieee, {"linkquality": 40})
    await hass.async_block_till_done()

    unique_ids = {
        e.unique_id
        for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
        if e.unique_id.startswith(failed_ieee)
    }
    assert unique_ids == {
        f"{failed_ieee}_{key}"
        for key in (
            "link_quality",
            "reconnect_rate",
            "health_score",
            "connectivity_warning",
        )
    }
    assert _state(hass, "sensor", f"{failed_ieee}_link_quality").state == "40"


async def test_lost_capability_removes_entities(
    hass: HomeAssistant, coordinator: ZigSightCoordinator
) -> None:
    """A device re-interviewed without battery loses its battery entities."""
    ent_reg = er.async_get(hass)
    battery_id = _entity_id(hass, "sensor", f"{CLIMATE}_battery")
    devices = load_fixture("bridge_devices.json")
    climate = next(d for d in devices if d["ieee_address"] == CLIMATE)
    original = copy.deepcopy(climate)
    climate["power_source"] = "Mains (single phase)"
    climate["definition"]["exposes"] = [
        e
        for e in climate["definition"]["exposes"]
        if e["name"] not in ("battery", "voltage")
    ]
    async_fire(hass, BASE, "bridge/devices", devices)
    await hass.async_block_till_done()

    for domain, key in (
        ("sensor", "battery"),
        ("sensor", "battery_trend"),
        ("sensor", "voltage"),
        ("binary_sensor", "battery_drain_warning"),
    ):
        assert ent_reg.async_get_entity_id(domain, DOMAIN, f"{CLIMATE}_{key}") is None
    assert hass.states.get(battery_id) is None
    assert _entity_id(hass, "sensor", f"{CLIMATE}_link_quality")

    # Regaining the capability brings the entities back
    devices = [original if d["ieee_address"] == CLIMATE else d for d in devices]
    async_fire(hass, BASE, "bridge/devices", devices)
    await hass.async_block_till_done()
    assert _state(hass, "sensor", f"{CLIMATE}_battery").state == "87"
    assert _entity_id(hass, "binary_sensor", f"{CLIMATE}_battery_drain_warning")


async def test_availability_ignored_while_bridge_offline(
    hass: HomeAssistant,
    mqtt_mock: MagicMock,
    entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """HA starting while Zigbee2MQTT is down: retained availability is stale."""
    coordinator = await _setup(hass, entry, freezer)
    async_fire(hass, BASE, "bridge/state", {"state": "offline"}, retain=True)
    async_fire(hass, BASE, "bridge/devices", load_fixture("bridge_devices.json"))
    async_fire(hass, BASE, "Kitchen/availability", {"state": "online"}, retain=True)
    async_fire(hass, BASE, "Bedroom Climate/availability", "offline", retain=True)
    await hass.async_block_till_done()
    for ieee in (PLUG, CLIMATE):
        record = coordinator.get_device(ieee)
        assert record is not None
        assert record["available"] is None
    assert (
        _state(hass, "binary_sensor", f"{CLIMATE}_connectivity_warning").state
        == STATE_OFF
    )

    # Zigbee2MQTT comes back and publishes fresh availability
    async_fire(hass, BASE, "bridge/state", {"state": "online"})
    async_fire(hass, BASE, "Kitchen/availability", {"state": "online"})
    await hass.async_block_till_done()
    record = coordinator.get_device(PLUG)
    assert record is not None
    assert record["available"] is True
    assert record["reconnect_count"] == 0


async def test_device_disabled_then_enabled(
    hass: HomeAssistant, coordinator: ZigSightCoordinator
) -> None:
    """Disabling a device makes its entities unavailable; enabling adds them."""
    devices = load_fixture("bridge_devices.json")
    for device in devices:
        if device["ieee_address"] == LAMP:
            device["disabled"] = True
        if device["ieee_address"] == DOOR:
            device["disabled"] = False
    async_fire(hass, BASE, "bridge/devices", devices)
    await hass.async_block_till_done()

    assert _state(hass, "sensor", f"{LAMP}_link_quality").state == "unavailable"
    assert _entity_id(hass, "sensor", f"{DOOR}_battery")
    assert _entity_id(hass, "sensor", f"{DOOR}_voltage")


async def test_non_json_and_unknown_payloads(
    hass: HomeAssistant,
    coordinator: ZigSightCoordinator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Garbage payloads never log errors and never change state."""
    caplog.set_level(logging.DEBUG)
    async_fire(hass, BASE, "Living Room Lamp", "not json at all")
    async_fire(hass, BASE, "Living Room Lamp", "[1, 2, 3]")
    async_fire(hass, BASE, "Living Room Lamp/availability", "maybe")
    async_fire(hass, BASE, "bridge/devices", "not json")
    async_fire(hass, BASE, "bridge/info", "not json")
    async_fire(hass, BASE, "bridge/response/networkmap", "not json")
    async_fire(hass, BASE, "Unknown Device/availability", "online")
    async_fire(hass, BASE, "Some Group", {"state": "ON"})
    await hass.async_block_till_done()

    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert _state(hass, "sensor", f"{LAMP}_link_quality").state == "156"
    assert len(coordinator.device_ids()) == 5
    assert coordinator.get_network_info() is not None


async def test_last_seen_epoch_and_fallback(
    hass: HomeAssistant, coordinator: ZigSightCoordinator
) -> None:
    """Epoch ms last_seen is supported; without it, receipt time is used."""
    async_fire(hass, BASE, "Kitchen", {"linkquality": 190, "last_seen": 1790237640000})
    await hass.async_block_till_done()
    record = coordinator.get_device(PLUG)
    assert record is not None
    assert record["metrics"]["last_seen"] == "2026-09-24T08:14:00+00:00"

    async_fire(hass, BASE, "Kitchen", {"linkquality": 191})
    await hass.async_block_till_done()
    assert record["metrics"]["last_seen"] == NOW


async def test_device_update_event_is_slim_and_rate_limited(
    hass: HomeAssistant,
    coordinator: ZigSightCoordinator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """zigsight_device_update is small, rate limited and ignores LQI churn."""
    events: list[Event] = []

    @callback
    def _listener(event: Event) -> None:
        events.append(event)

    hass.bus.async_listen(EVENT_DEVICE_UPDATE, _listener)
    freezer.tick(timedelta(minutes=5))
    # The battery reported during the replayed session was rate limited
    # (availability had just been reported): it goes out with the next message.
    async_fire(hass, BASE, "Bedroom Climate", {"linkquality": 99})
    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0].data["metrics"]["battery"] == 87
    events.clear()

    freezer.tick(timedelta(minutes=5))
    # Link quality changes alone never fire the event
    for lqi in (100, 101, 102):
        async_fire(hass, BASE, "Bedroom Climate", {"linkquality": lqi})
    await hass.async_block_till_done()
    assert events == []

    async_fire(hass, BASE, "Bedroom Climate", {"battery": 86, "linkquality": 90})
    await hass.async_block_till_done()
    assert len(events) == 1
    data = events[0].data
    assert data["device_id"] == CLIMATE
    assert data["friendly_name"] == "Bedroom Climate"
    assert data["metrics"]["battery"] == 86
    assert data["metrics"]["link_quality"] == 90
    assert "last_message" not in data["metrics"]
    assert set(data) == {"device_id", "friendly_name", "source", "available", "metrics"}

    # Battery changes are rate limited...
    async_fire(hass, BASE, "Bedroom Climate", {"battery": 85})
    await hass.async_block_till_done()
    assert len(events) == 1

    # ... availability changes are always reported
    async_fire(hass, BASE, "Bedroom Climate/availability", "offline")
    await hass.async_block_till_done()
    assert len(events) == 2
    assert events[1].data["available"] is False

    freezer.tick(timedelta(minutes=2))
    async_fire(hass, BASE, "Bedroom Climate", {"battery": 84})
    await hass.async_block_till_done()
    assert len(events) == 3


async def test_network_map(
    hass: HomeAssistant,
    mqtt_mock: MagicMock,
    coordinator: ZigSightCoordinator,
) -> None:
    """A raw network map can be requested and its response is stored."""
    assert await coordinator.async_request_network_map()
    mqtt_mock.async_publish.assert_called_once()
    topic, payload = mqtt_mock.async_publish.call_args.args[:2]
    assert topic == f"{BASE}/bridge/request/networkmap"
    assert '"type": "raw"' in payload

    networkmap = [m for m in session_messages() if m.topic.endswith("networkmap")]
    async_fire_messages(hass, networkmap)
    await hass.async_block_till_done()

    links = coordinator.get_network_links()
    assert len(links) == 5
    assert {
        "source": CLIMATE,
        "target": LAMP,
        "lqi": 72,
        "depth": 2,
        "relationship": 1,
    } in links
    assert len(coordinator.get_network_nodes()) == 5
    assert coordinator.network_map_updated is not None

    # Failed responses keep the previous map
    async_fire(
        hass,
        BASE,
        "bridge/response/networkmap",
        {"data": {}, "status": "error", "error": "Timeout"},
    )
    await hass.async_block_till_done()
    assert len(coordinator.get_network_links()) == 5


async def test_untracked_quiet_router_is_not_flagged(
    hass: HomeAssistant,
    coordinator: ZigSightCoordinator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Without availability, quiet routers only warn after the long timeout.

    ZigSight doesn't ping devices: an idle bulb/plug may send nothing for
    hours, so the 10 minute Zigbee2MQTT router timeout must not apply.
    """
    record = coordinator.get_device(PLUG)
    assert record is not None
    record["available"] = None  # availability not tracked
    warning = f"{PLUG}_connectivity_warning"

    freezer.tick(timedelta(minutes=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert _state(hass, "binary_sensor", warning).state == STATE_OFF

    freezer.tick(timedelta(hours=12))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert _state(hass, "binary_sensor", warning).state == STATE_OFF

    # The periodic refresh flags it once silent for longer than 25 h
    freezer.tick(timedelta(hours=13))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert _state(hass, "binary_sensor", warning).state == STATE_ON


async def test_bridge_offline_resets_availability(
    hass: HomeAssistant, coordinator: ZigSightCoordinator
) -> None:
    """A Zigbee2MQTT restart neither raises warnings nor counts reconnects."""
    async_fire(hass, BASE, "Kitchen/availability", {"state": "offline"})
    await hass.async_block_till_done()
    warning = f"{PLUG}_connectivity_warning"
    assert _state(hass, "binary_sensor", warning).state == STATE_ON

    async_fire(hass, BASE, "bridge/state", {"state": "offline"})
    await hass.async_block_till_done()
    for ieee in (LAMP, PLUG, CLIMATE, MOTION):
        record = coordinator.get_device(ieee)
        assert record is not None
        assert record["available"] is None
    # Stale "offline" no longer drives the warning
    assert _state(hass, "binary_sensor", warning).state == STATE_OFF

    async_fire(hass, BASE, "bridge/state", {"state": "online"})
    async_fire(hass, BASE, "Kitchen/availability", {"state": "online"})
    await hass.async_block_till_done()
    record = coordinator.get_device(PLUG)
    assert record is not None
    assert record["available"] is True
    assert record["reconnect_count"] == 0


async def test_history_is_bounded_and_numeric(
    hass: HomeAssistant,
    coordinator: ZigSightCoordinator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """History stores only numeric metrics, rate limited."""
    for minute in range(0, 60):
        freezer.tick(timedelta(minutes=1))
        async_fire(hass, BASE, "Kitchen", {"linkquality": 100 + minute, "state": "ON"})
    await hass.async_block_till_done()
    history = coordinator.get_device_history(PLUG)
    # One point every HISTORY_MIN_INTERVAL (5 min) at most
    assert 10 <= len(history) <= 14
    assert set(history[0]["metrics"]) == {"link_quality", "battery", "voltage"}


async def test_battery_trend_and_drain_warning(
    hass: HomeAssistant,
    coordinator: ZigSightCoordinator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A fast draining battery (including below 20%) raises the warning."""
    battery = 30
    for _ in range(6):
        freezer.tick(timedelta(minutes=30))
        battery -= 8
        async_fire(hass, BASE, "Kitchen/Motion Sensor", {"battery": battery})
    await hass.async_block_till_done()
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    trend = float(_state(hass, "sensor", f"{MOTION}_battery_trend").state)
    assert trend < -10
    assert (
        _state(hass, "binary_sensor", f"{MOTION}_battery_drain_warning").state
        == STATE_ON
    )


async def test_remove_config_entry_device(
    hass: HomeAssistant, entry: MockConfigEntry, coordinator: ZigSightCoordinator
) -> None:
    """Only stale devices can be removed from the UI."""
    dev_reg = dr.async_get(hass)
    live = get_device(hass, (DOMAIN, LAMP))
    bridge = get_device(hass, coordinator.bridge_identifier)
    stale = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "Stale Name")}
    )
    assert live is not None and bridge is not None
    assert not await async_remove_config_entry_device(hass, entry, live)
    assert not await async_remove_config_entry_device(hass, entry, bridge)
    assert await async_remove_config_entry_device(hass, entry, stale)


async def test_unload_unsubscribes(
    hass: HomeAssistant, entry: MockConfigEntry, coordinator: ZigSightCoordinator
) -> None:
    """Unloading releases the MQTT subscription."""
    assert coordinator._unsub_mqtt
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not coordinator._unsub_mqtt
    # Messages after unload are not processed
    async_fire(hass, BASE, "Kitchen", {"linkquality": 1})
    await hass.async_block_till_done()
    record = coordinator.get_device(PLUG)
    assert record is not None
    assert record["metrics"]["link_quality"] == 201


async def test_setup_retries_without_mqtt(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Without the MQTT integration the entry is retried (not failed)."""
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert entry.entry_id not in hass.data.get(DOMAIN, {})


async def test_bridge_devices_mutation_does_not_leak(
    hass: HomeAssistant, coordinator: ZigSightCoordinator
) -> None:
    """Records returned by get_all_devices are copies without raw state."""
    devices = coordinator.get_all_devices()
    assert "state" not in devices[LAMP]
    snapshot = copy.deepcopy(devices)
    devices[LAMP]["friendly_name"] = "changed"
    assert coordinator.get_device(LAMP)["friendly_name"] == "Living Room Lamp"
    assert snapshot[LAMP]["type"] == "Router"
    bridge_devices = coordinator.get_bridge_devices()
    assert bridge_devices[0]["type"] == "Coordinator"
    assert len(bridge_devices) == 6


async def test_no_deprecated_home_assistant_api_usage(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    coordinator: ZigSightCoordinator,
) -> None:
    """Setup, rename and removal don't use deprecated Home Assistant APIs.

    See ``registry_helpers.deprecation_reports``; the ZHA counterpart is
    ``test_zha_device_removed_from_registry_is_dropped``.
    """
    devices = load_fixture("bridge_devices.json")
    for device in devices:
        if device["ieee_address"] == CLIMATE:
            device["friendly_name"] = "Bedroom Weather"
    async_fire(hass, BASE, "bridge/devices", devices)
    await hass.async_block_till_done()
    async_fire(
        hass,
        BASE,
        "bridge/devices",
        [d for d in devices if d["ieee_address"] != PLUG],
    )
    await hass.async_block_till_done()
    assert get_device(hass, (DOMAIN, PLUG)) is None

    assert not deprecation_reports(caplog)
