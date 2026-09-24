"""Config flow for ZigSight."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries

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
    CONF_RECONNECT_THRESHOLD,
    CONF_RETENTION_DAYS,
    DEFAULT_BATTERY_DRAIN_THRESHOLD,
    DEFAULT_INTEGRATION_TYPE,
    DEFAULT_MQTT_BROKER,
    DEFAULT_MQTT_PORT,
    DEFAULT_MQTT_TOPIC_PREFIX,
    DEFAULT_RECONNECT_RATE_THRESHOLD,
    DEFAULT_RECONNECT_RATE_WINDOW_HOURS,
    DEFAULT_RECONNECT_THRESHOLD,
    DEFAULT_RETENTION_DAYS,
    DOMAIN,
    INTEGRATION_TYPE_ZHA,
    INTEGRATION_TYPE_ZIGBEE2MQTT,
)

STEP_INTEGRATION_TYPE_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_INTEGRATION_TYPE,
            default=DEFAULT_INTEGRATION_TYPE,
        ): vol.In([INTEGRATION_TYPE_ZHA, INTEGRATION_TYPE_ZIGBEE2MQTT]),
    }
)

STEP_ZIGBEE2MQTT_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_MQTT_BROKER,
            default=DEFAULT_MQTT_BROKER,
        ): str,
        vol.Required(
            CONF_MQTT_PORT,
            default=DEFAULT_MQTT_PORT,
        ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
        vol.Optional(CONF_MQTT_USERNAME): str,
        vol.Optional(CONF_MQTT_PASSWORD): str,
        vol.Optional(
            CONF_MQTT_TOPIC_PREFIX,
            default=DEFAULT_MQTT_TOPIC_PREFIX,
        ): str,
    }
)

STEP_COMMON_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_RECONNECT_THRESHOLD,
            default=DEFAULT_RECONNECT_THRESHOLD,
        ): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
        vol.Optional(
            CONF_RETENTION_DAYS,
            default=DEFAULT_RETENTION_DAYS,
        ): vol.All(vol.Coerce(int), vol.Range(min=1, max=365)),
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


class ZigsightConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    """Handle a config flow for ZigSight."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._integration_type: str | None = None
        self._integration_data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step - integration type selection."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_INTEGRATION_TYPE_SCHEMA
            )

        self._integration_type = user_input[CONF_INTEGRATION_TYPE]
        # Set enable_zha based on integration type
        self._integration_data[CONF_ENABLE_ZHA] = (
            self._integration_type == INTEGRATION_TYPE_ZHA
        )

        # Move to integration-specific step
        if self._integration_type == INTEGRATION_TYPE_ZIGBEE2MQTT:
            return await self.async_step_zigbee2mqtt()
        elif self._integration_type == INTEGRATION_TYPE_ZHA:
            return await self.async_step_common()

        return self.async_abort(reason="invalid_integration_type")

    async def async_step_zigbee2mqtt(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle Zigbee2MQTT-specific configuration."""
        if user_input is None:
            return self.async_show_form(
                step_id="zigbee2mqtt", data_schema=STEP_ZIGBEE2MQTT_DATA_SCHEMA
            )

        # Validate MQTT connection if credentials provided
        errors: dict[str, str] = {}
        if user_input.get(CONF_MQTT_BROKER) and user_input.get(CONF_MQTT_PORT):
            # Try to validate connection (basic check)
            # In a real implementation, we might test the connection here
            pass

        if errors:
            return self.async_show_form(
                step_id="zigbee2mqtt",
                data_schema=STEP_ZIGBEE2MQTT_DATA_SCHEMA,
                errors=errors,
            )

        # Store Zigbee2MQTT-specific data
        self._integration_data.update(
            {
                CONF_MQTT_BROKER: user_input.get(CONF_MQTT_BROKER, DEFAULT_MQTT_BROKER),
                CONF_MQTT_PORT: user_input.get(CONF_MQTT_PORT, DEFAULT_MQTT_PORT),
                CONF_MQTT_USERNAME: user_input.get(CONF_MQTT_USERNAME, ""),
                CONF_MQTT_PASSWORD: user_input.get(CONF_MQTT_PASSWORD, ""),
                CONF_MQTT_TOPIC_PREFIX: user_input.get(
                    CONF_MQTT_TOPIC_PREFIX, DEFAULT_MQTT_TOPIC_PREFIX
                ),
            }
        )

        return await self.async_step_common()

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
            CONF_RECONNECT_THRESHOLD: user_input.get(
                CONF_RECONNECT_THRESHOLD, DEFAULT_RECONNECT_THRESHOLD
            ),
            CONF_RETENTION_DAYS: user_input.get(
                CONF_RETENTION_DAYS, DEFAULT_RETENTION_DAYS
            ),
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

        # For ZHA, we don't need MQTT fields, but keep them for backward compatibility
        # They will be ignored in __init__.py when enable_zha is True
        if self._integration_type == INTEGRATION_TYPE_ZHA:
            # Set default values that won't trigger MQTT connection
            # These will be converted to None in __init__.py when enable_zha is True
            config_data.setdefault(CONF_MQTT_BROKER, DEFAULT_MQTT_BROKER)
            config_data.setdefault(CONF_MQTT_PORT, DEFAULT_MQTT_PORT)
            config_data.setdefault(CONF_MQTT_USERNAME, "")
            config_data.setdefault(CONF_MQTT_PASSWORD, "")
            config_data.setdefault(CONF_MQTT_TOPIC_PREFIX, DEFAULT_MQTT_TOPIC_PREFIX)

        return self.async_create_entry(title="ZigSight", data=config_data)
