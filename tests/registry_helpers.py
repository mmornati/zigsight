"""Device registry helpers for tests, working across Home Assistant versions.

``DeviceRegistry.async_get_device`` is deprecated since Home Assistant 2026.9
(and raises for non custom-integration code, i.e. the tests), so tests look
devices up by identifier through this helper instead.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from custom_components.zigsight.device_registry_compat import async_all_devices


def get_device(
    hass: HomeAssistant, identifier: tuple[str, str]
) -> dr.DeviceEntry | None:
    """Return the (first) registered device with the given identifier."""
    for device in async_all_devices(dr.async_get(hass)):
        if identifier in device.identifiers:
            return device
    return None
