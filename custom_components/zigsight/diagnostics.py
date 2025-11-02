"""Diagnostics platform for ZigSight."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_MQTT_PASSWORD, DOMAIN
from .coordinator import ZigSightCoordinator

REDACT_CONFIG = {CONF_MQTT_PASSWORD}
REDACT_DEVICE_DATA = {"last_message"}  # May contain sensitive device data


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: ZigSightCoordinator = hass.data[DOMAIN][entry.entry_id]

    diagnostics_data = {
        "config_entry": async_redact_data(entry.as_dict(), REDACT_CONFIG),
        "coordinator": {
            "mqtt_prefix": coordinator._mqtt_prefix,
            "mqtt_broker": coordinator._mqtt_broker,
            "mqtt_port": coordinator._mqtt_port,
            "use_direct_mqtt": coordinator._use_direct_mqtt,
            "device_count": len(coordinator._devices),
            "analytics_config": {
                "reconnect_rate_window_hours": coordinator._analytics.reconnect_rate_window_hours,
                "battery_drain_threshold": coordinator._analytics.battery_drain_threshold,
                "reconnect_rate_threshold": coordinator._reconnect_rate_threshold,
            },
        },
        "devices": {},
    }

    # Include device data with analytics metrics
    for device_id, device_data in coordinator._devices.items():
        # Redact sensitive data
        device_diagnostics = async_redact_data(device_data.copy(), REDACT_DEVICE_DATA)

        # Add analytics metrics
        if "analytics_metrics" not in device_diagnostics:
            device_diagnostics["analytics_metrics"] = {}

        # Add history summary
        history = coordinator.get_device_history(device_id)
        device_diagnostics["history"] = {
            "entry_count": len(history),
            "oldest_entry": history[0].get("timestamp") if history else None,
            "newest_entry": history[-1].get("timestamp") if history else None,
        }

        diagnostics_data["devices"][device_id] = device_diagnostics

    return diagnostics_data


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device_id: str
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    coordinator: ZigSightCoordinator = hass.data[DOMAIN][entry.entry_id]

    device = coordinator.get_device(device_id)
    if not device:
        return {"error": "Device not found"}

    # Redact sensitive data
    device_data = async_redact_data(device.copy(), REDACT_DEVICE_DATA)

    # Add full history
    history = coordinator.get_device_history(device_id)
    device_data["history"] = history

    # Add analytics metrics
    if "analytics_metrics" not in device_data:
        device_data["analytics_metrics"] = {}

    # Compute additional metrics
    device_data["analytics_metrics"]["reconnect_rate"] = (
        coordinator.get_device_reconnect_rate(device_id)
    )
    device_data["analytics_metrics"]["battery_trend"] = (
        coordinator.get_device_battery_trend(device_id)
    )
    device_data["analytics_metrics"]["health_score"] = (
        coordinator.get_device_health_score(device_id)
    )
    device_data["analytics_metrics"]["battery_drain_warning"] = (
        coordinator.get_device_battery_drain_warning(device_id)
    )
    device_data["analytics_metrics"]["connectivity_warning"] = (
        coordinator.get_device_connectivity_warning(device_id)
    )

    return device_data
