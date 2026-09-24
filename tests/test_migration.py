"""Config entry and registry migration tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.zigsight.const import (
    CONF_BATTERY_DRAIN_THRESHOLD,
    CONF_ENABLE_ZHA,
    CONF_INTEGRATION_TYPE,
    CONF_MQTT_TOPIC_PREFIX,
    DOMAIN,
    INTEGRATION_TYPE_ZHA,
    INTEGRATION_TYPE_ZIGBEE2MQTT,
)

from .z2m_replay import async_fire_messages, session_messages

CLIMATE = "0x00158d0001a2b3c4"
PLUG = "0x000d6ffffe1a2b3c"
MOTION = "0x001788010b2c3d4e"

LEGACY_Z2M_DATA = {
    CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_ZIGBEE2MQTT,
    "mqtt_broker": "core-mosquitto",
    "mqtt_port": 1883,
    "mqtt_username": "addons",
    "mqtt_password": "secret",
    CONF_MQTT_TOPIC_PREFIX: "zigbee2mqtt",
    CONF_ENABLE_ZHA: False,
    CONF_BATTERY_DRAIN_THRESHOLD: 12.0,
}


async def test_migrate_zigbee2mqtt_entry(
    hass: HomeAssistant, mqtt_mock: MagicMock
) -> None:
    """1.1 entries lose broker settings and the legacy enable_zha flag."""
    entry = MockConfigEntry(
        domain=DOMAIN, version=1, minor_version=1, data=LEGACY_Z2M_DATA
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 1
    assert entry.minor_version == 2
    assert entry.data == {
        CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_ZIGBEE2MQTT,
        CONF_MQTT_TOPIC_PREFIX: "zigbee2mqtt",
        CONF_BATTERY_DRAIN_THRESHOLD: 12.0,
    }


@pytest.mark.parametrize(
    ("data", "expected_type"),
    [
        # Very old entries only had enable_zha
        ({CONF_ENABLE_ZHA: True, "mqtt_broker": "localhost"}, INTEGRATION_TYPE_ZHA),
        (
            {
                CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_ZHA,
                CONF_ENABLE_ZHA: True,
                "mqtt_broker": "localhost",
                "mqtt_port": 1883,
                "mqtt_username": "",
                "mqtt_password": "",
                CONF_MQTT_TOPIC_PREFIX: "zigbee2mqtt",
            },
            INTEGRATION_TYPE_ZHA,
        ),
    ],
)
async def test_migrate_zha_entry(
    hass: HomeAssistant, data: dict[str, object], expected_type: str
) -> None:
    """ZHA entries keep only ZHA relevant settings (no MQTT needed)."""
    entry = MockConfigEntry(domain=DOMAIN, version=1, minor_version=1, data=data)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert entry.minor_version == 2
    assert entry.data == {CONF_INTEGRATION_TYPE: expected_type}


async def test_migrate_legacy_entry_without_type_defaults_to_z2m(
    hass: HomeAssistant, mqtt_mock: MagicMock
) -> None:
    """Missing integration_type and enable_zha=False -> Zigbee2MQTT."""
    entry = MockConfigEntry(
        domain=DOMAIN, version=1, minor_version=1, data={"mqtt_broker": "localhost"}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.data == {
        CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_ZIGBEE2MQTT,
        CONF_MQTT_TOPIC_PREFIX: "zigbee2mqtt",
    }


async def test_future_major_version_is_rejected(hass: HomeAssistant) -> None:
    """Downgrading from a future major version fails the migration."""
    entry = MockConfigEntry(domain=DOMAIN, version=2, data={})
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.MIGRATION_ERROR


async def test_future_minor_version_loads(hass: HomeAssistant) -> None:
    """A newer minor version of the same major version still loads."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=9,
        data={CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_ZHA},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert entry.minor_version == 9


async def test_legacy_entities_are_migrated_to_ieee_unique_ids(
    hass: HomeAssistant, mqtt_mock: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Friendly-name based unique ids/devices move to IEEE based ones."""
    freezer.move_to("2026-09-24T08:20:00+00:00")
    entry = MockConfigEntry(
        domain=DOMAIN, version=1, minor_version=1, data=LEGACY_Z2M_DATA
    )
    entry.add_to_hass(hass)

    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    # What the previous release created: device (zigsight, <friendly name>)
    # with a self referencing via_device and zigsight_<name>_<key> unique ids.
    legacy_device = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "Bedroom Climate")},
        name="Bedroom Climate",
        manufacturer="ZigSight",
    )
    battery = ent_reg.async_get_or_create(
        "sensor",
        DOMAIN,
        "zigsight_Bedroom Climate_battery",
        config_entry=entry,
        device_id=legacy_device.id,
        suggested_object_id="bedroom_climate_battery",
    )
    warning = ent_reg.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        "zigsight_Bedroom Climate_connectivity_warning",
        config_entry=entry,
        device_id=legacy_device.id,
        suggested_object_id="bedroom_climate_connectivity_warning",
    )
    # "Kitchen" was both the plug and the (truncated) motion sensor: the
    # exact name wins.
    kitchen = ent_reg.async_get_or_create(
        "sensor",
        DOMAIN,
        "zigsight_Kitchen_link_quality",
        config_entry=entry,
        suggested_object_id="kitchen_link_quality",
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    async_fire_messages(
        hass, [m for m in session_messages() if not m.topic.endswith("networkmap")]
    )
    await hass.async_block_till_done()

    migrated = ent_reg.async_get(battery.entity_id)
    assert migrated is not None
    assert migrated.unique_id == f"{CLIMATE}_battery"
    assert migrated.entity_id == "sensor.bedroom_climate_battery"
    assert hass.states.get("sensor.bedroom_climate_battery").state == "87"

    migrated_warning = ent_reg.async_get(warning.entity_id)
    assert migrated_warning is not None
    assert migrated_warning.unique_id == f"{CLIMATE}_connectivity_warning"

    migrated_kitchen = ent_reg.async_get(kitchen.entity_id)
    assert migrated_kitchen is not None
    assert migrated_kitchen.unique_id == f"{PLUG}_link_quality"
    assert ent_reg.async_get_entity_id("sensor", DOMAIN, f"{MOTION}_link_quality")

    # The legacy device now carries the IEEE identifier (same device id, so
    # areas/customisations are kept) and no longer points at itself.
    device = dev_reg.async_get(legacy_device.id)
    assert device is not None
    assert device.identifiers == {(DOMAIN, CLIMATE)}
    assert device.via_device_id != device.id
    assert device.manufacturer == "Aqara"
    assert dev_reg.async_get_device(identifiers={(DOMAIN, "Bedroom Climate")}) is None
    # No duplicate entity was created
    assert (
        len(
            [
                e
                for e in er.async_entries_for_config_entry(ent_reg, entry.entry_id)
                if e.unique_id.endswith("_battery") and CLIMATE in e.unique_id
            ]
        )
        == 1
    )


async def test_legacy_duplicate_is_removed(
    hass: HomeAssistant, mqtt_mock: MagicMock
) -> None:
    """If both old and new unique ids exist, the legacy entry is dropped."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=2,
        data={
            CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_ZIGBEE2MQTT,
            CONF_MQTT_TOPIC_PREFIX: "zigbee2mqtt",
        },
    )
    entry.add_to_hass(hass)
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    old_device = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "Kitchen")}
    )
    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, PLUG)}
    )
    legacy = ent_reg.async_get_or_create(
        "sensor", DOMAIN, "zigsight_Kitchen_link_quality", config_entry=entry
    )
    current = ent_reg.async_get_or_create(
        "sensor", DOMAIN, f"{PLUG}_link_quality", config_entry=entry
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    async_fire_messages(
        hass, [m for m in session_messages() if m.topic.endswith("bridge/devices")]
    )
    await hass.async_block_till_done()

    assert ent_reg.async_get(legacy.entity_id) is None
    assert ent_reg.async_get(current.entity_id) is not None
    assert dev_reg.async_get(old_device.id) is None
