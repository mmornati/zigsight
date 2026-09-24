"""Device registry helpers working across supported Home Assistant versions.

Home Assistant 2026.8 reworked the device registry: a device now belongs to a
single config entry, identifiers are only unique per config entry, and new
lookup APIs (``async_get_device_by_identifier``) and a ``via_device_id``
device info key were added. Home Assistant 2026.9 then started reporting the
old APIs as deprecated (removal in 2027.8 / 2027.9):

* ``DeviceRegistry.async_get_device``
* ``via_device`` in device info / ``async_get_or_create``
* ``async_update_device(remove_config_entry_id=...)``
* using ``DeviceRegistry.devices`` as a mapping (``.values()``, ``[id]``)

ZigSight supports Home Assistant 2025.10 and later, so these helpers use the
new APIs when available and fall back to the previous ones otherwise.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from homeassistant.helpers import device_registry as dr

# Home Assistant >= 2026.8: per config entry devices and the new lookup APIs.
PER_ENTRY_DEVICES: bool = hasattr(dr.DeviceRegistry, "async_get_device_by_identifier")


def async_get_entry_device(
    dev_reg: dr.DeviceRegistry, config_entry_id: str, identifier: tuple[str, str]
) -> dr.DeviceEntry | None:
    """Return the device of the config entry with the given identifier."""
    if PER_ENTRY_DEVICES:
        device: dr.DeviceEntry | None = dev_reg.async_get_device_by_identifier(  # type: ignore[attr-defined,unused-ignore]
            identifier, config_entry_id
        )
        return device
    return dev_reg.async_get_device(identifiers={identifier})


def async_remove_entry_device(
    dev_reg: dr.DeviceRegistry, device: dr.DeviceEntry, config_entry_id: str
) -> None:
    """Remove a device of the config entry from the registry.

    Before Home Assistant 2026.8 a device may be shared by several config
    entries, so only this entry is detached from it (the registry removes the
    device once no config entry is left). Since 2026.8 a device belongs to a
    single config entry and is removed directly.
    """
    if PER_ENTRY_DEVICES:
        dev_reg.async_remove_device(device.id)
    else:
        dev_reg.async_update_device(device.id, remove_config_entry_id=config_entry_id)


def via_device_info(
    dev_reg: dr.DeviceRegistry, config_entry_id: str, identifier: tuple[str, str]
) -> dict[str, Any]:
    """Return the device info keys linking a device through a via device.

    Since Home Assistant 2026.8 the via device is referenced by its registry
    id (``via_device_id``); earlier versions only support the identifier
    (``via_device``). Returns an empty dict when the via device is unknown.
    """
    if not PER_ENTRY_DEVICES:
        return {"via_device": identifier}
    if (via := async_get_entry_device(dev_reg, config_entry_id, identifier)) is None:
        return {}
    return {"via_device_id": via.id}


def async_all_devices(dev_reg: dr.DeviceRegistry) -> Iterable[dr.DeviceEntry]:
    """Return all main device entries of the registry.

    ``DeviceRegistry.devices`` is a device id -> entry mapping before Home
    Assistant 2026.9; since then it is a collection of entries, and using it
    as a mapping is deprecated.
    """
    devices: Any = dev_reg.devices
    if isinstance(devices, Mapping):
        return list(devices.values())
    return list(devices)
