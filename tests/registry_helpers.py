"""Device registry helpers for tests, working across Home Assistant versions.

``DeviceRegistry.async_get_device`` is deprecated since Home Assistant 2026.9
(and raises for non custom-integration code, i.e. the tests), so tests look
devices up by identifier through this helper instead.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from custom_components.zigsight.const import DOMAIN


def all_devices(dev_reg: dr.DeviceRegistry) -> list[dr.DeviceEntry]:
    """Return all main device entries of the registry.

    ``DeviceRegistry.devices`` is a device id -> entry mapping before Home
    Assistant 2026.9; since then it is a collection of entries, and using it
    as a mapping is deprecated.
    """
    devices: Any = dev_reg.devices
    if isinstance(devices, Mapping):
        return list(devices.values())
    return list(devices)


def get_device(
    hass: HomeAssistant, identifier: tuple[str, str]
) -> dr.DeviceEntry | None:
    """Return the (first) registered device with the given identifier."""
    for device in all_devices(dr.async_get(hass)):
        if identifier in device.identifiers:
            return device
    return None


def deprecation_reports(caplog: pytest.LogCaptureFixture) -> list[str]:
    """Return Home Assistant's deprecated API usage reports about ZigSight.

    Home Assistant reports deprecated API usage by a custom integration with
    a "Detected that custom integration 'zigsight' ..." warning (e.g. the
    device registry APIs deprecated in 2026.9). This only bites on Home
    Assistant versions deprecating an API we still use, which is why the CI
    unit tests also run against the latest Home Assistant release.
    """
    return [
        message
        for record in (*caplog.get_records("setup"), *caplog.records)
        if f"custom integration '{DOMAIN}'" in (message := record.getMessage())
        and ("deprecated" in message or "stop working" in message)
    ]
