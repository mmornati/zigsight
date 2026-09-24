"""ZigSight - Home Assistant diagnostics and optimization toolkit for Zigbee networks."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import cast

import voluptuous as vol
from homeassistant.components import frontend, mqtt, panel_custom
from homeassistant.components.frontend import DATA_PANELS
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY, ConfigEntry
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import (
    ConfigEntryNotReady,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration
from homeassistant.util.json import JsonValueType

from .api import (
    WIFI_SCAN_DATA_SCHEMA,
    ChannelRecommendationError,
    async_generate_channel_recommendation,
    setup_api_views,
)
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
    ISSUE_LEGACY_PANEL,
    ISSUE_ZHA_DIAGNOSTICS_DISABLED,
    LEGACY_MQTT_KEYS,
)
from .coordinator import ZigSightCoordinator
from .zha_collector import (
    async_enable_diagnostic_entities,
    async_get_zha_config_entries,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["sensor", "binary_sensor"]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# Static files (panel + Lovelace cards) served from custom_components/zigsight/www
STATIC_URL_PATH = "/zigsight_static"
WWW_PATH = Path(__file__).parent / "www"

# Sidebar panel
PANEL_URL_PATH = "zigsight"
PANEL_WEBCOMPONENT = "zigsight-panel"
PANEL_MODULE = "zigsight-panel.js"
PANEL_TITLE = "ZigSight"
PANEL_ICON = "mdi:zigbee"

DATA_STATIC_PATH_REGISTERED = f"{DOMAIN}_static_path_registered"
DATA_PANEL_REGISTERED = f"{DOMAIN}_panel_registered"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the parts of ZigSight shared by all config entries.

    The static files (panel, Lovelace cards) and the REST API are
    registered once per Home Assistant run; aiohttp routes can't be removed.
    """
    await _async_register_static_path(hass)
    setup_api_views(hass)
    return True


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

    # Sidebar panel, served from the integration folder.
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
        # Don't assume hass.data[DOMAIN] exists: nothing else creates it when
        # the entry was loaded without our async_setup_entry storing a
        # coordinator (e.g. setup patched out, as the config-flow tests do).
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        # hass.data[DOMAIN] is not a reliable "any entry left?" signal: the
        # recommend_channel service stashes a "last_recommendation" key
        # there that outlives every config entry, so the dict is never
        # actually empty. single_config_entry means at most one entry can
        # be loaded anyway; async_loaded_entries reflects that (excluding
        # this entry, whose own state hasn't flipped to NOT_LOADED yet at
        # this point in config_entries.async_unload).
        other_loaded_entries = [
            other
            for other in hass.config_entries.async_loaded_entries(DOMAIN)
            if other.entry_id != entry.entry_id
        ]
        if not other_loaded_entries:
            # Last entry gone: drop the services (PR series follow-up may
            # generalise this cleanup; kept minimal/self-contained here).
            for service in ("recommend_channel", "enable_zha_diagnostic_entities"):
                if hass.services.has_service(DOMAIN, service):
                    hass.services.async_remove(DOMAIN, service)
            ir.async_delete_issue(hass, DOMAIN, ISSUE_ZHA_DIAGNOSTICS_DISABLED)
            ir.async_delete_issue(hass, DOMAIN, ISSUE_LEGACY_PANEL)
            _async_remove_panel(hass)

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

    async def async_recommend_channel(call: ServiceCall) -> ServiceResponse:
        """Handle the recommend_channel service call and return the result.

        Shares its scan/compute/store logic with the REST API (POST
        /api/zigsight/channel-recommendation) via
        ``async_generate_channel_recommendation`` so both behave the same
        way, including recording the call in ``recommendation_history``.
        """
        mode = call.data.get("mode", "manual")
        wifi_scan_data = call.data.get("wifi_scan_data")

        try:
            outcome = await async_generate_channel_recommendation(
                hass, mode, wifi_scan_data
            )
        except ValueError as err:
            # Caller-input problem (e.g. manual mode without scan data):
            # surfaced as a validation error, not a generic failure.
            raise ServiceValidationError(str(err)) from err
        except ChannelRecommendationError as err:
            raise HomeAssistantError(str(err)) from err

        return cast(
            ServiceResponse,
            {
                "recommended_channel": outcome["recommended_channel"],
                "scores": outcome["scores"],
                "explanation": outcome["explanation"],
                "wifi_aps_count": outcome["wifi_aps_count"],
                "timestamp": outcome["timestamp"],
            },
        )

    # "host_scan" mode runs iwlist/nmcli subprocesses on the Home Assistant
    # host, so the whole service is admin-only (Home Assistant has no way to
    # gate a single service field behind admin instead of the whole call).
    recommend_channel_schema = vol.Schema(
        {
            vol.Optional("mode", default="manual"): vol.In(["manual", "host_scan"]),
            vol.Optional("wifi_scan_data"): WIFI_SCAN_DATA_SCHEMA,
        }
    )

    async_register_admin_service(
        hass,
        DOMAIN,
        "recommend_channel",
        async_recommend_channel,
        schema=recommend_channel_schema,
        supports_response=SupportsResponse.OPTIONAL,
    )


@callback
def _async_setup_enable_zha_diagnostics_service(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, "enable_zha_diagnostic_entities"):
        return

    async def async_enable_zha_diagnostics(call: ServiceCall) -> ServiceResponse:
        """Enable ZHA LQI/RSSI sensors ZigSight/ZHA left disabled by default."""
        zha_mode_loaded = any(
            loaded_entry.data.get(CONF_INTEGRATION_TYPE) == INTEGRATION_TYPE_ZHA
            for loaded_entry in hass.config_entries.async_loaded_entries(DOMAIN)
        )
        if not zha_mode_loaded:
            _LOGGER.warning(
                "zigsight.enable_zha_diagnostic_entities called without a "
                "loaded ZHA-mode ZigSight config entry; nothing to do"
            )
            return {
                "enabled_count": 0,
                "entity_ids": cast(list[JsonValueType], []),
                "error": "No ZHA-mode ZigSight config entry is loaded",
            }

        enabled = async_enable_diagnostic_entities(hass)
        if enabled:
            ir.async_delete_issue(hass, DOMAIN, ISSUE_ZHA_DIAGNOSTICS_DISABLED)
            _LOGGER.info(
                "Enabled %d ZHA diagnostic entities: %s; Home Assistant will "
                "reload the ZHA config entry ~%s seconds afterwards to "
                "create them",
                len(enabled),
                ", ".join(enabled),
                RELOAD_AFTER_UPDATE_DELAY,
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


async def _async_register_static_path(hass: HomeAssistant) -> None:
    """Serve the panel and card files from the integration folder (once).

    aiohttp routes can't be removed, so this runs once per Home Assistant
    run no matter how often the config entry is reloaded. Cache headers are
    disabled: the files import each other with relative URLs, which the
    ``?v=`` cache buster of the panel module URL doesn't cover.
    """
    if hass.data.get(DATA_STATIC_PATH_REGISTERED):
        return
    hass.data[DATA_STATIC_PATH_REGISTERED] = True
    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC_URL_PATH, str(WWW_PATH), cache_headers=False)]
    )


def _legacy_panels(hass: HomeAssistant) -> list[str]:
    """Describe registered panels that aren't ours but load a ZigSight panel.

    That is the panel at ``/zigsight`` when it isn't served from
    ``/zigsight_static`` (a ``panel_custom`` YAML entry from the old manual
    setup), and any other panel defining the ``zigsight-panel`` custom
    element (only one definition of a custom element can win in a browser).
    """
    legacy: list[str] = []
    for url_path, panel in hass.data.get(DATA_PANELS, {}).items():
        custom = (panel.config or {}).get("_panel_custom") or {}
        module_url = str(custom.get("module_url") or custom.get("js_url") or "")
        if module_url.startswith(f"{STATIC_URL_PATH}/"):
            continue
        if url_path == PANEL_URL_PATH or custom.get("name") == PANEL_WEBCOMPONENT:
            legacy.append(f"/{url_path} ({module_url or 'unknown module'})")
    return sorted(legacy)


@callback
def _async_update_legacy_panel_issue(hass: HomeAssistant) -> None:
    """Raise (or clear) the repair issue about an old manual panel setup."""
    legacy = _legacy_panels(hass)
    if not legacy:
        ir.async_delete_issue(hass, DOMAIN, ISSUE_LEGACY_PANEL)
        return
    _LOGGER.warning(
        "Found a ZigSight panel from the old manual setup: %s. ZigSight now "
        "registers its panel itself: remove the 'panel_custom' entry from "
        "configuration.yaml and the copied zigsight-panel.js from your www "
        "folder, then restart Home Assistant",
        ", ".join(legacy),
    )
    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_LEGACY_PANEL,
        is_fixable=False,
        is_persistent=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_LEGACY_PANEL,
        translation_placeholders={"panels": ", ".join(legacy)},
        learn_more_url=(
            "https://github.com/mmornati/zigsight/blob/main/docs/frontend_panel.md"
            "#upgrading-from-zigsight-1x-manual-panel-setup"
        ),
    )


async def _async_register_panel(hass: HomeAssistant) -> None:
    """Register the ZigSight sidebar panel (admin only)."""
    if hass.data.get(DATA_PANEL_REGISTERED):
        return
    integration = await async_get_integration(hass, DOMAIN)
    try:
        await panel_custom.async_register_panel(
            hass,
            frontend_url_path=PANEL_URL_PATH,
            webcomponent_name=PANEL_WEBCOMPONENT,
            sidebar_title=PANEL_TITLE,
            sidebar_icon=PANEL_ICON,
            module_url=f"{STATIC_URL_PATH}/{PANEL_MODULE}?v={integration.version}",
            embed_iframe=False,
            require_admin=True,
        )
    except ValueError:
        # Most likely a panel_custom entry in configuration.yaml, as older
        # ZigSight versions required. It is kept (removing a user's panel
        # would be surprising) and reported as a repair issue below.
        pass
    else:
        hass.data[DATA_PANEL_REGISTERED] = True
    _async_update_legacy_panel_issue(hass)


@callback
def _async_remove_panel(hass: HomeAssistant) -> None:
    """Remove the sidebar panel registered by ZigSight (not a YAML one)."""
    if hass.data.pop(DATA_PANEL_REGISTERED, False):
        frontend.async_remove_panel(hass, PANEL_URL_PATH, warn_if_unknown=False)
