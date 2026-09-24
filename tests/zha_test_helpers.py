"""Shared helpers to build a fake, real-registry ZHA setup for tests.

No real ZHA radio/gateway is ever involved: a ``MockConfigEntry(domain="zha")``
with ``state=ConfigEntryState.LOADED`` stands in for a loaded ZHA config
entry, and devices/entities are registered directly in the real device and
entity registries the way ZHA would (``("zha", ieee)`` device identifiers,
``sensor`` entities with ``translation_key`` ``lqi``/``rssi`` disabled by
``RegistryEntryDisabler.INTEGRATION``, and a battery sensor).
"""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    MockModule,
    mock_integration,
)

ZHA_DOMAIN = "zha"


def add_mock_zha_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Add a loaded (mock) ZHA config entry.

    The real ``zha`` component is also mocked out (``mock_integration``):
    ``pytest-homeassistant-custom-component`` unloads every still-LOADED
    config entry when the ``hass`` fixture tears down, which would otherwise
    import and call the real ``homeassistant.components.zha`` unload path
    for an entry that was never actually set up.
    """
    mock_integration(
        hass,
        MockModule(
            ZHA_DOMAIN,
            async_setup_entry=AsyncMock(return_value=True),
            async_unload_entry=AsyncMock(return_value=True),
        ),
    )
    entry = MockConfigEntry(domain=ZHA_DOMAIN, title="ZHA")
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)
    return entry


def add_mock_zha_device(
    hass: HomeAssistant,
    zha_entry: MockConfigEntry,
    ieee: str,
    *,
    name: str = "Test ZHA Device",
    manufacturer: str | None = "Test Manufacturer",
    model: str | None = "Test Model",
    lqi_state: str | None = "180",
    rssi_state: str | None = "-55",
    battery_state: str | None = "85",
    lqi_disabled_by: er.RegistryEntryDisabler | None = (
        er.RegistryEntryDisabler.INTEGRATION
    ),
    rssi_disabled_by: er.RegistryEntryDisabler | None = (
        er.RegistryEntryDisabler.INTEGRATION
    ),
    create_battery: bool = True,
) -> dr.DeviceEntry:
    """Register a ("zha", ieee) device with LQI/RSSI/battery entities.

    Mirrors what the real ``zha`` library creates: LQI/RSSI as diagnostic
    sensors (``translation_key`` ``lqi``/``rssi``) disabled by default
    (``disabled_by=RegistryEntryDisabler.INTEGRATION``), plus a battery
    sensor (``device_class="battery"``) that is enabled.
    """
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)

    device = dev_reg.async_get_or_create(
        config_entry_id=zha_entry.entry_id,
        identifiers={(ZHA_DOMAIN, ieee)},
        name=name,
        manufacturer=manufacturer,
        model=model,
    )

    object_id = ieee.replace(":", "")

    lqi_entry = ent_reg.async_get_or_create(
        "sensor",
        ZHA_DOMAIN,
        f"{ieee}-lqi",
        config_entry=zha_entry,
        device_id=device.id,
        translation_key="lqi",
        original_name="LQI",
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_object_id=f"{object_id}_lqi",
        disabled_by=lqi_disabled_by,
    )
    if lqi_state is not None and lqi_disabled_by is None:
        hass.states.async_set(lqi_entry.entity_id, lqi_state)

    rssi_entry = ent_reg.async_get_or_create(
        "sensor",
        ZHA_DOMAIN,
        f"{ieee}-rssi",
        config_entry=zha_entry,
        device_id=device.id,
        translation_key="rssi",
        original_name="RSSI",
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_object_id=f"{object_id}_rssi",
        disabled_by=rssi_disabled_by,
    )
    if rssi_state is not None and rssi_disabled_by is None:
        hass.states.async_set(rssi_entry.entity_id, rssi_state)

    if create_battery:
        battery_entry = ent_reg.async_get_or_create(
            "sensor",
            ZHA_DOMAIN,
            f"{ieee}-battery",
            config_entry=zha_entry,
            device_id=device.id,
            original_device_class="battery",
            original_name="Battery",
            entity_category=EntityCategory.DIAGNOSTIC,
            suggested_object_id=f"{object_id}_battery",
        )
        if battery_state is not None:
            hass.states.async_set(battery_entry.entity_id, battery_state)

    return device
