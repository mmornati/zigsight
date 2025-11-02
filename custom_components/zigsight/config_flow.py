"""Config flow for ZigSight."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.components import mqtt
from homeassistant.data_entry_flow import FlowResult
import voluptuous as vol

from .const import (
    CONF_MQTT_TOPIC_PREFIX,
    CONF_RECONNECT_THRESHOLD,
    CONF_RETENTION_DAYS,
    DEFAULT_MQTT_TOPIC_PREFIX,
    DEFAULT_RECONNECT_THRESHOLD,
    DEFAULT_RETENTION_DAYS,
    DOMAIN,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
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
    }
)


class ZigSightConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    """Handle a config flow for ZigSight."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if not await mqtt.async_wait_for_mqtt_client(self.hass):
            return self.async_abort(reason="mqtt_not_available")

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        return self.async_create_entry(
            title="ZigSight",
            data={
                CONF_MQTT_TOPIC_PREFIX: user_input.get(
                    CONF_MQTT_TOPIC_PREFIX, DEFAULT_MQTT_TOPIC_PREFIX
                ),
                CONF_RECONNECT_THRESHOLD: user_input.get(
                    CONF_RECONNECT_THRESHOLD, DEFAULT_RECONNECT_THRESHOLD
                ),
                CONF_RETENTION_DAYS: user_input.get(
                    CONF_RETENTION_DAYS, DEFAULT_RETENTION_DAYS
                ),
            },
        )
