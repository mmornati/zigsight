"""ZigSight - Home Assistant diagnostics and optimization toolkit for Zigbee networks."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_BATTERY_DRAIN_THRESHOLD,
    CONF_ENABLE_ZHA,
    CONF_INTEGRATION_TYPE,
    CONF_MQTT_BROKER,
    CONF_MQTT_PASSWORD,
    CONF_MQTT_PORT,
    CONF_MQTT_TOPIC_PREFIX,
    CONF_MQTT_USERNAME,
    CONF_RECONNECT_RATE_THRESHOLD,
    CONF_RECONNECT_RATE_WINDOW_HOURS,
    DEFAULT_BATTERY_DRAIN_THRESHOLD,
    DEFAULT_ENABLE_ZHA,
    DEFAULT_INTEGRATION_TYPE,
    DEFAULT_MQTT_BROKER,
    DEFAULT_MQTT_PORT,
    DEFAULT_MQTT_TOPIC_PREFIX,
    DEFAULT_RECONNECT_RATE_THRESHOLD,
    DEFAULT_RECONNECT_RATE_WINDOW_HOURS,
    DOMAIN,
    INTEGRATION_TYPE_ZHA,
)
from .coordinator import ZigSightCoordinator
from .recommender import recommend_zigbee_channel
from .wifi_scanner import create_scanner

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["sensor", "binary_sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ZigSight from a config entry."""
    # Determine integration type and enable_zha (backward compatibility)
    integration_type = entry.data.get(CONF_INTEGRATION_TYPE, DEFAULT_INTEGRATION_TYPE)
    # For backward compatibility, check CONF_ENABLE_ZHA first
    if CONF_ENABLE_ZHA in entry.data:
        enable_zha = entry.data.get(CONF_ENABLE_ZHA, DEFAULT_ENABLE_ZHA)
    else:
        # New config flow: derive from integration_type
        enable_zha = integration_type == INTEGRATION_TYPE_ZHA

    # Only use MQTT parameters if not using ZHA
    if enable_zha:
        # ZHA mode: don't use MQTT at all
        mqtt_prefix = DEFAULT_MQTT_TOPIC_PREFIX
        mqtt_broker = None
        mqtt_port = None
        mqtt_username = None
        mqtt_password = None
    else:
        # Zigbee2MQTT mode: use MQTT parameters
        mqtt_prefix = entry.data.get(CONF_MQTT_TOPIC_PREFIX, DEFAULT_MQTT_TOPIC_PREFIX)
        mqtt_broker_raw = entry.data.get(CONF_MQTT_BROKER, DEFAULT_MQTT_BROKER)
        mqtt_port_raw = entry.data.get(CONF_MQTT_PORT, DEFAULT_MQTT_PORT)
        mqtt_username_raw = entry.data.get(CONF_MQTT_USERNAME, "")
        mqtt_password_raw = entry.data.get(CONF_MQTT_PASSWORD, "")

        # Only pass non-default values to avoid triggering direct MQTT connection
        # when using Home Assistant's MQTT integration
        mqtt_broker = (
            mqtt_broker_raw
            if mqtt_broker_raw and mqtt_broker_raw != DEFAULT_MQTT_BROKER
            else None
        )
        mqtt_port = (
            mqtt_port_raw
            if mqtt_port_raw and mqtt_port_raw != DEFAULT_MQTT_PORT
            else None
        )
        mqtt_username = mqtt_username_raw if mqtt_username_raw else None
        mqtt_password = mqtt_password_raw if mqtt_password_raw else None

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
        mqtt_broker=mqtt_broker,
        mqtt_port=mqtt_port,
        mqtt_username=mqtt_username,
        mqtt_password=mqtt_password,
        battery_drain_threshold=battery_drain_threshold,
        reconnect_rate_threshold=reconnect_rate_threshold,
        reconnect_rate_window_hours=reconnect_rate_window_hours,
        enable_zha=enable_zha,
    )

    # Start coordinator (sets up MQTT subscriptions)
    await coordinator.async_start()

    # Request first data update
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    await _async_setup_services(hass)

    # Register API views
    from .api import setup_api_views

    setup_api_views(hass)

    # Register frontend panel (only once)
    await _async_register_panel(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok: bool = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: ZigSightCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()

    return unload_ok


async def _async_setup_services(hass: HomeAssistant) -> None:
    """Set up ZigSight services."""

    # Only register services once
    if hass.services.has_service(DOMAIN, "recommend_channel"):
        return

    async def async_recommend_channel(call: ServiceCall) -> None:
        """Handle recommend_channel service call."""
        mode = call.data.get("mode", "manual")
        wifi_scan_data = call.data.get("wifi_scan_data")

        try:
            # Create appropriate scanner
            scanner = create_scanner(
                mode=mode,
                scan_data=wifi_scan_data,
            )

            # Perform scan
            wifi_aps = await scanner.scan()

            # Get recommendation
            result = recommend_zigbee_channel(wifi_aps)

            _LOGGER.info(
                "Zigbee channel recommendation: Channel %s (score: %.1f)",
                result["recommended_channel"],
                result["scores"][result["recommended_channel"]],
            )
            _LOGGER.info("Recommendation: %s", result["explanation"])

            # Store result in hass.data for retrieval
            hass.data.setdefault(DOMAIN, {})
            hass.data[DOMAIN]["last_recommendation"] = result

        except Exception as e:
            _LOGGER.error("Error during channel recommendation: %s", e)
            raise

    # Service schema
    recommend_channel_schema = vol.Schema(
        {
            vol.Optional("mode", default="manual"): cv.string,
            vol.Optional("wifi_scan_data"): vol.Any(dict, list),
        }
    )

    hass.services.async_register(
        DOMAIN,
        "recommend_channel",
        async_recommend_channel,
        schema=recommend_channel_schema,
    )


async def _async_register_panel(hass: HomeAssistant) -> None:
    """Register the ZigSight frontend panel automatically.

    Note: In Home Assistant 2025+, programmatic panel registration is deprecated.
    Panels must be registered via panel_custom in configuration.yaml.
    This function provides helpful setup instructions.
    """
    # Check if panel is already registered
    frontend_panels = hass.data.setdefault("frontend_panels", {})
    if "zigsight" in frontend_panels:
        _LOGGER.debug("ZigSight panel already registered")
        return

    # In Home Assistant 2025+, async_register_built_in_panel is deprecated
    # and custom panels must be registered via panel_custom in configuration.yaml
    # We'll log clear instructions for the user

    _LOGGER.info(
        "ZigSight frontend panel setup required. "
        "In Home Assistant 2025+, panels must be registered manually.\n"
        "\n"
        "STEP 1: Copy the panel file to your www directory:\n"
        "  For HACS: mkdir -p config/www/community/zigsight && "
        "cp config/custom_components/zigsight/www/zigsight-panel.js config/www/community/zigsight/\n"
        "  For manual: mkdir -p config/www/zigsight && "
        "cp custom_components/zigsight/www/zigsight-panel.js config/www/zigsight/\n"
        "\n"
        "STEP 2: Add to configuration.yaml:\n"
        "  For HACS:\n"
        "    panel_custom:\n"
        "      - name: zigsight\n"
        "        sidebar_title: ZigSight\n"
        "        sidebar_icon: mdi:zigbee\n"
        "        url_path: zigsight\n"
        "        module_url: /local/community/zigsight/zigsight-panel.js\n"
        "        require_admin: false\n"
        "  For manual:\n"
        "    panel_custom:\n"
        "      - name: zigsight\n"
        "        sidebar_title: ZigSight\n"
        "        sidebar_icon: mdi:zigbee\n"
        "        url_path: zigsight\n"
        "        module_url: /local/zigsight/zigsight-panel.js\n"
        "        require_admin: false\n"
        "\n"
        "STEP 3: Restart Home Assistant.\n"
        "\n"
        "See docs/frontend_panel.md for complete instructions."
    )
