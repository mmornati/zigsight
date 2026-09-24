"""Config flow for ZigSight."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import mqtt
from homeassistant.core import callback

from .const import (
    CONF_BATTERY_DRAIN_THRESHOLD,
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
)
from .options_flow import ZigSightOptionsFlowHandler

STEP_INTEGRATION_TYPE_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_INTEGRATION_TYPE,
            default=DEFAULT_INTEGRATION_TYPE,
        ): vol.In([INTEGRATION_TYPE_ZHA, INTEGRATION_TYPE_ZIGBEE2MQTT]),
    }
)

# Zigbee2MQTT messages are received through Home Assistant's MQTT
# integration, so only the Zigbee2MQTT base topic is needed here.
STEP_ZIGBEE2MQTT_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_MQTT_TOPIC_PREFIX,
            default=DEFAULT_MQTT_TOPIC_PREFIX,
        ): str,
    }
)

STEP_COMMON_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_BATTERY_DRAIN_THRESHOLD,
            default=DEFAULT_BATTERY_DRAIN_THRESHOLD,
        ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=100.0)),
        vol.Optional(
            CONF_RECONNECT_RATE_THRESHOLD,
            default=DEFAULT_RECONNECT_RATE_THRESHOLD,
        ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=100.0)),
        vol.Optional(
            CONF_RECONNECT_RATE_WINDOW_HOURS,
            default=DEFAULT_RECONNECT_RATE_WINDOW_HOURS,
        ): vol.All(vol.Coerce(int), vol.Range(min=1, max=168)),
    }
)


class ZigsightConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ZigSight."""

    VERSION = CONFIG_ENTRY_VERSION
    MINOR_VERSION = CONFIG_ENTRY_MINOR_VERSION

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._integration_type: str | None = None
        self._integration_data: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ZigSightOptionsFlowHandler:
        """Get the options flow for this handler."""
        return ZigSightOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step - integration type selection.

        A second entry is rejected by Home Assistant itself
        (``single_config_entry`` in manifest.json).
        """
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_INTEGRATION_TYPE_SCHEMA
            )

        self._integration_type = user_input[CONF_INTEGRATION_TYPE]

        # Move to integration-specific step
        if self._integration_type == INTEGRATION_TYPE_ZIGBEE2MQTT:
            if not mqtt.mqtt_config_entry_enabled(self.hass):
                return self.async_abort(reason="mqtt_not_available")
            return await self.async_step_zigbee2mqtt()
        if self._integration_type == INTEGRATION_TYPE_ZHA:
            return await self.async_step_common()

        return self.async_abort(reason="invalid_integration_type")

    async def async_step_zigbee2mqtt(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle Zigbee2MQTT-specific configuration (base topic only)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            prefix = str(user_input.get(CONF_MQTT_TOPIC_PREFIX, "")).strip().strip("/")
            try:
                mqtt.valid_subscribe_topic(f"{prefix}/#")
            except vol.Invalid:
                prefix = ""
            if not prefix or any(char in prefix for char in "+#"):
                errors[CONF_MQTT_TOPIC_PREFIX] = "invalid_topic_prefix"
            else:
                self._integration_data[CONF_MQTT_TOPIC_PREFIX] = prefix
                return await self.async_step_common()

        return self.async_show_form(
            step_id="zigbee2mqtt",
            data_schema=STEP_ZIGBEE2MQTT_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_common(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle common configuration parameters."""
        if user_input is None:
            return self.async_show_form(
                step_id="common", data_schema=STEP_COMMON_DATA_SCHEMA
            )

        # Combine all configuration data
        config_data = {
            CONF_INTEGRATION_TYPE: self._integration_type,
            CONF_BATTERY_DRAIN_THRESHOLD: user_input.get(
                CONF_BATTERY_DRAIN_THRESHOLD, DEFAULT_BATTERY_DRAIN_THRESHOLD
            ),
            CONF_RECONNECT_RATE_THRESHOLD: user_input.get(
                CONF_RECONNECT_RATE_THRESHOLD, DEFAULT_RECONNECT_RATE_THRESHOLD
            ),
            CONF_RECONNECT_RATE_WINDOW_HOURS: user_input.get(
                CONF_RECONNECT_RATE_WINDOW_HOURS,
                DEFAULT_RECONNECT_RATE_WINDOW_HOURS,
            ),
        }

        # Add integration-specific data
        config_data.update(self._integration_data)

        return self.async_create_entry(title="ZigSight", data=config_data)
