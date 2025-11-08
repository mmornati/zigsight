"""Config flow for ZigSight."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries

from .const import (
    CONF_BATTERY_DRAIN_THRESHOLD,
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
    DEFAULT_MQTT_BROKER,
    DEFAULT_MQTT_PORT,
    DEFAULT_MQTT_TOPIC_PREFIX,
    DEFAULT_RECONNECT_RATE_THRESHOLD,
    DEFAULT_RECONNECT_RATE_WINDOW_HOURS,
    DEFAULT_RECONNECT_THRESHOLD,
    DEFAULT_RETENTION_DAYS,
    DOMAIN,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
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


class ZigSightConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[misc]
    """Handle a config flow for ZigSight."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        # Validate MQTT connection if credentials provided
        errors: dict[str, str] = {}
        if user_input.get(CONF_MQTT_BROKER) and user_input.get(CONF_MQTT_PORT):
            # Try to validate connection (basic check)
            # In a real implementation, we might test the connection here
            pass

        if errors:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
            )

        return self.async_create_entry(
            title="ZigSight",
            data={
                CONF_MQTT_BROKER: user_input.get(CONF_MQTT_BROKER, DEFAULT_MQTT_BROKER),
                CONF_MQTT_PORT: user_input.get(CONF_MQTT_PORT, DEFAULT_MQTT_PORT),
                CONF_MQTT_USERNAME: user_input.get(CONF_MQTT_USERNAME, ""),
                CONF_MQTT_PASSWORD: user_input.get(CONF_MQTT_PASSWORD, ""),
                CONF_MQTT_TOPIC_PREFIX: user_input.get(
                    CONF_MQTT_TOPIC_PREFIX, DEFAULT_MQTT_TOPIC_PREFIX
                ),
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
            },
        )
