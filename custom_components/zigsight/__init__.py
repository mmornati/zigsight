"""ZigSight - Home Assistant diagnostics and optimization toolkit for Zigbee networks."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_BATTERY_DRAIN_THRESHOLD,
    CONF_MQTT_BROKER,
    CONF_MQTT_PASSWORD,
    CONF_MQTT_PORT,
    CONF_MQTT_TOPIC_PREFIX,
    CONF_MQTT_USERNAME,
    CONF_RECONNECT_RATE_THRESHOLD,
    CONF_RECONNECT_RATE_WINDOW_HOURS,
    DEFAULT_BATTERY_DRAIN_THRESHOLD,
    DEFAULT_MQTT_BROKER,
    DEFAULT_MQTT_PORT,
    DEFAULT_MQTT_TOPIC_PREFIX,
    DEFAULT_RECONNECT_RATE_THRESHOLD,
    DEFAULT_RECONNECT_RATE_WINDOW_HOURS,
    DOMAIN,
)
from .coordinator import ZigSightCoordinator

PLATFORMS: list[str] = ["sensor", "binary_sensor", "diagnostics"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ZigSight from a config entry."""
    mqtt_prefix = entry.data.get(CONF_MQTT_TOPIC_PREFIX, DEFAULT_MQTT_TOPIC_PREFIX)
    mqtt_broker = entry.data.get(CONF_MQTT_BROKER, DEFAULT_MQTT_BROKER)
    mqtt_port = entry.data.get(CONF_MQTT_PORT, DEFAULT_MQTT_PORT)
    mqtt_username = entry.data.get(CONF_MQTT_USERNAME, "")
    mqtt_password = entry.data.get(CONF_MQTT_PASSWORD, "")
    battery_drain_threshold = entry.data.get(
        CONF_BATTERY_DRAIN_THRESHOLD, DEFAULT_BATTERY_DRAIN_THRESHOLD
    )
    reconnect_rate_threshold = entry.data.get(
        CONF_RECONNECT_RATE_THRESHOLD, DEFAULT_RECONNECT_RATE_THRESHOLD
    )
    reconnect_rate_window_hours = entry.data.get(
        CONF_RECONNECT_RATE_WINDOW_HOURS, DEFAULT_RECONNECT_RATE_WINDOW_HOURS
    )

    coordinator = ZigSightCoordinator(
        hass,
        mqtt_prefix=mqtt_prefix,
        mqtt_broker=mqtt_broker if mqtt_broker != DEFAULT_MQTT_BROKER else None,
        mqtt_port=mqtt_port if mqtt_port != DEFAULT_MQTT_PORT else None,
        mqtt_username=mqtt_username if mqtt_username else None,
        mqtt_password=mqtt_password if mqtt_password else None,
        battery_drain_threshold=battery_drain_threshold,
        reconnect_rate_threshold=reconnect_rate_threshold,
        reconnect_rate_window_hours=reconnect_rate_window_hours,
    )

    # Start coordinator (sets up MQTT subscriptions)
    await coordinator.async_start()

    # Request first data update
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok: bool = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: ZigSightCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()

    return unload_ok
