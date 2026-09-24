"""Diagnostics platform for ZigSight."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN, LEGACY_MQTT_KEYS
from .coordinator import ZigSightCoordinator

# Legacy entries (before the 1.2 migration) may still carry broker
# credentials; never include them. The network identifiers are not secret
# but are redacted as they identify the user's Zigbee network.
REDACT_CONFIG = set(LEGACY_MQTT_KEYS)
REDACT_NETWORK = {"extended_pan_id", "pan_id"}


def _device_diagnostics(
    coordinator: ZigSightCoordinator, device_id: str, record: dict[str, Any]
) -> dict[str, Any]:
    history = coordinator.get_device_history(device_id)
    return {
        **{key: value for key, value in record.items() if key != "state"},
        # Last merged Zigbee2MQTT state: only the keys, values may be private
        # (e.g. occupancy, lock state).
        "state_keys": sorted(record.get("state", {})),
        "history": {
            "entry_count": len(history),
            "oldest_entry": history[0]["timestamp"] if history else None,
            "newest_entry": history[-1]["timestamp"] if history else None,
        },
        "reconnect_events": coordinator.get_device_reconnect_events(device_id),
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: ZigSightCoordinator = hass.data[DOMAIN][entry.entry_id]
    network = coordinator.get_network_info()
    return {
        "config_entry": async_redact_data(entry.as_dict(), REDACT_CONFIG),
        "coordinator": {
            "source": coordinator.source,
            "mqtt_prefix": coordinator.mqtt_prefix,
            "bridge_state": coordinator.bridge_state,
            "network": async_redact_data(network, REDACT_NETWORK) if network else None,
            "coordinator_ieee": coordinator.coordinator_ieee,
            "device_count": len(coordinator.device_ids()),
            "network_links": len(coordinator.get_network_links()),
            "network_map_updated": (
                coordinator.network_map_updated.isoformat()
                if coordinator.network_map_updated
                else None
            ),
            "analytics_config": {
                "reconnect_rate_window_hours": coordinator._analytics.reconnect_rate_window_hours,
                "battery_drain_threshold": coordinator._analytics.battery_drain_threshold,
                "reconnect_rate_threshold": coordinator._reconnect_rate_threshold,
                "router_timeout_seconds": coordinator._analytics.router_timeout.total_seconds(),
                "end_device_timeout_seconds": coordinator._analytics.end_device_timeout.total_seconds(),
            },
        },
        "devices": {
            device_id: _device_diagnostics(
                coordinator, device_id, coordinator.get_device(device_id) or {}
            )
            for device_id in coordinator.device_ids()
        },
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for one device."""
    coordinator: ZigSightCoordinator = hass.data[DOMAIN][entry.entry_id]
    ieee = next(
        (
            identifier
            for domain, identifier in device.identifiers
            if domain == DOMAIN and coordinator.get_device(identifier) is not None
        ),
        None,
    )
    if ieee is None:
        return {"error": "Device not tracked by ZigSight"}
    data = _device_diagnostics(coordinator, ieee, coordinator.get_device(ieee) or {})
    data["history"]["entries"] = coordinator.get_device_history(ieee)
    return data
