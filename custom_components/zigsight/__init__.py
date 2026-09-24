"""ZigSight - Home Assistant diagnostics and optimization toolkit for Zigbee networks."""

from __future__ import annotations

import logging
from typing import cast

import voluptuous as vol
from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.util.json import JsonValueType

from .const import (
    CONF_BATTERY_DRAIN_THRESHOLD,
    CONF_ENABLE_ZHA,
    CONF_INTEGRATION_TYPE,
    CONF_MQTT_TOPIC_PREFIX,
    CONF_RECONNECT_RATE_THRESHOLD,
    CONF_RECONNECT_RATE_WINDOW_HOURS,
    CONFIG_ENTRY_MINOR_VERSION,
    CONFIG_ENTRY_VERSION,
    DEFAULT_BATTERY_DRAIN_THRESHOLD,
    DEFAULT_INTEGRATION_TYPE,
    DEFAULT_MQTT_TOPIC_PREFIX,
    DEFAULT_RECONNECT_RATE_THRESHOLD,
    DEFAULT_RECONNECT_RATE_WINDOW_HOURS,
    DOMAIN,
    INTEGRATION_TYPE_ZHA,
    INTEGRATION_TYPE_ZIGBEE2MQTT,
    ISSUE_ZHA_DIAGNOSTICS_DISABLED,
    LEGACY_MQTT_KEYS,
)
from .coordinator import ZigSightCoordinator
from .recommender import recommend_zigbee_channel
from .wifi_scanner import create_scanner
from .zha_collector import (
    async_enable_diagnostic_entities,
    async_get_zha_config_entries,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["sensor", "binary_sensor"]


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entries.

    1.1 -> 1.2: drop the direct-MQTT connection settings (the integration now
    always uses Home Assistant's MQTT integration) and the legacy
    ``enable_zha`` flag (replaced by ``integration_type``).
    """
    if entry.version > CONFIG_ENTRY_VERSION:
        # Downgrade from a future major version: not supported.
        return False

    if entry.version == 1 and entry.minor_version < 2:
        data = dict(entry.data)
        if CONF_INTEGRATION_TYPE not in data:
            data[CONF_INTEGRATION_TYPE] = (
                INTEGRATION_TYPE_ZHA
                if data.get(CONF_ENABLE_ZHA)
                else DEFAULT_INTEGRATION_TYPE
            )
        data.pop(CONF_ENABLE_ZHA, None)
        for key in LEGACY_MQTT_KEYS:
            data.pop(key, None)
        if data[CONF_INTEGRATION_TYPE] == INTEGRATION_TYPE_ZHA:
            data.pop(CONF_MQTT_TOPIC_PREFIX, None)
        else:
            data.setdefault(CONF_MQTT_TOPIC_PREFIX, DEFAULT_MQTT_TOPIC_PREFIX)
        hass.config_entries.async_update_entry(
            entry,
            data=data,
            version=CONFIG_ENTRY_VERSION,
            minor_version=CONFIG_ENTRY_MINOR_VERSION,
        )
        _LOGGER.info(
            "Migrated ZigSight config entry to version %s.%s",
            CONFIG_ENTRY_VERSION,
            CONFIG_ENTRY_MINOR_VERSION,
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ZigSight from a config entry."""
    integration_type = entry.data.get(CONF_INTEGRATION_TYPE, DEFAULT_INTEGRATION_TYPE)
    enable_zha = integration_type == INTEGRATION_TYPE_ZHA

    if integration_type == INTEGRATION_TYPE_ZIGBEE2MQTT and not (
        await mqtt.async_wait_for_mqtt_client(hass)
    ):
        # Retried by Home Assistant with backoff until MQTT is available.
        raise ConfigEntryNotReady(
            "The MQTT integration is not set up or not available; ZigSight "
            "needs it to receive Zigbee2MQTT messages"
        )

    if integration_type == INTEGRATION_TYPE_ZHA and not async_get_zha_config_entries(
        hass
    ):
        # Retried by Home Assistant with backoff until ZHA is loaded (e.g.
        # ZHA config entry set up after ZigSight, or still starting up).
        raise ConfigEntryNotReady(
            "The ZHA integration is not set up or not loaded yet; ZigSight "
            "needs it to collect Zigbee device diagnostics"
        )

    # Analytics thresholds can be tuned later via the options flow; options
    # (when set) take precedence over the original config-entry data.
    battery_drain_threshold = entry.options.get(
        CONF_BATTERY_DRAIN_THRESHOLD,
        entry.data.get(CONF_BATTERY_DRAIN_THRESHOLD, DEFAULT_BATTERY_DRAIN_THRESHOLD),
    )
    reconnect_rate_threshold = entry.options.get(
        CONF_RECONNECT_RATE_THRESHOLD,
        entry.data.get(CONF_RECONNECT_RATE_THRESHOLD, DEFAULT_RECONNECT_RATE_THRESHOLD),
    )
    reconnect_rate_window_hours = entry.options.get(
        CONF_RECONNECT_RATE_WINDOW_HOURS,
        entry.data.get(
            CONF_RECONNECT_RATE_WINDOW_HOURS, DEFAULT_RECONNECT_RATE_WINDOW_HOURS
        ),
    )

    # The coordinator registers its own async_shutdown with
    # entry.async_on_unload, so MQTT subscriptions are released on unload
    # and also when any later setup step fails.
    coordinator = ZigSightCoordinator(
        hass,
        mqtt_prefix=entry.data.get(CONF_MQTT_TOPIC_PREFIX, DEFAULT_MQTT_TOPIC_PREFIX),
        battery_drain_threshold=battery_drain_threshold,
        reconnect_rate_threshold=reconnect_rate_threshold,
        reconnect_rate_window_hours=reconnect_rate_window_hours,
        enable_zha=enable_zha,
        config_entry=entry,
    )

    # The bridge device must exist before entities reference it as via_device.
    coordinator.async_setup_bridge_device()

    # Store the coordinator before subscribing: retained messages may be
    # delivered (and new devices announced to the platforms) right away.
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    try:
        await coordinator.async_start()
        await coordinator.async_config_entry_first_refresh()
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        raise

    # Register services
    await _async_setup_services(hass)

    # Register API views
    from .api import setup_api_views

    setup_api_views(hass)

    # Register frontend panel (only once)
    await _async_register_panel(hass)

    # Note: reloading the entry when options change (e.g. analytics
    # thresholds tuned via the options flow) is handled by
    # ZigSightOptionsFlowHandler extending OptionsFlowWithReload
    # (see options_flow.py) rather than a config-entry update listener here
    # -- HA does not allow combining both on the same entry.

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry.

    The coordinator's async_shutdown (MQTT unsubscribe) runs through the
    entry's on-unload callbacks.
    """
    unload_ok: bool = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            # Last entry gone: drop the services (PR series follow-up may
            # generalise this cleanup; kept minimal/self-contained here).
            for service in ("recommend_channel", "enable_zha_diagnostic_entities"):
                if hass.services.has_service(DOMAIN, service):
                    hass.services.async_remove(DOMAIN, service)

    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Allow removing stale devices (no longer known to Zigbee2MQTT/ZHA)."""
    coordinator: ZigSightCoordinator | None = hass.data.get(DOMAIN, {}).get(
        entry.entry_id
    )
    if coordinator is None:
        return True
    for domain, identifier in device_entry.identifiers:
        if domain != DOMAIN:
            continue
        if identifier == coordinator.bridge_identifier[1]:
            return False
        if coordinator.get_device(identifier) is not None:
            return False
    return True


async def _async_setup_services(hass: HomeAssistant) -> None:
    """Set up ZigSight services (each registered once)."""
    await _async_setup_recommend_channel_service(hass)
    _async_setup_enable_zha_diagnostics_service(hass)


async def _async_setup_recommend_channel_service(hass: HomeAssistant) -> None:
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


@callback
def _async_setup_enable_zha_diagnostics_service(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, "enable_zha_diagnostic_entities"):
        return

    async def async_enable_zha_diagnostics(call: ServiceCall) -> ServiceResponse:
        """Enable ZHA LQI/RSSI sensors ZigSight/ZHA left disabled by default."""
        enabled = async_enable_diagnostic_entities(hass)
        if enabled:
            ir.async_delete_issue(hass, DOMAIN, ISSUE_ZHA_DIAGNOSTICS_DISABLED)
            _LOGGER.info(
                "Enabled %d ZHA diagnostic entities: %s; Home Assistant will "
                "reload the ZHA config entry to create them, which can take "
                "a few seconds",
                len(enabled),
                ", ".join(enabled),
            )
        return {
            "enabled_count": len(enabled),
            "entity_ids": cast(list[JsonValueType], enabled),
        }

    hass.services.async_register(
        DOMAIN,
        "enable_zha_diagnostic_entities",
        async_enable_zha_diagnostics,
        supports_response=SupportsResponse.OPTIONAL,
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
