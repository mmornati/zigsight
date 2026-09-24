"""Options flow for ZigSight."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries

from .const import (
    CONF_BATTERY_DRAIN_THRESHOLD,
    CONF_RECONNECT_RATE_THRESHOLD,
    CONF_RECONNECT_RATE_WINDOW_HOURS,
    DEFAULT_BATTERY_DRAIN_THRESHOLD,
    DEFAULT_RECONNECT_RATE_THRESHOLD,
    DEFAULT_RECONNECT_RATE_WINDOW_HOURS,
)


class ZigSightOptionsFlowHandler(config_entries.OptionsFlowWithReload):
    """Handle options flow for ZigSight.

    Note: ``OptionsFlow.config_entry`` has been a read-only property
    (backed by ``self.hass.config_entries``) since Home Assistant 2024.11;
    *assigning* to ``self.config_entry`` in ``__init__`` (as this handler
    used to do) still worked by accident until it started raising in
    2025.12. So this handler no longer takes or stores a ``config_entry``
    argument in ``__init__``.

    It also extends ``OptionsFlowWithReload`` (available since at least HA
    2025.10, our minimum supported version) instead of registering a
    config-entry update listener in ``__init__.py`` -- HA schedules the
    entry reload automatically when options change, and explicitly
    disallows combining ``OptionsFlowWithReload`` with an update listener
    on the same entry.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the analytics threshold options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options or self.config_entry.data

        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_BATTERY_DRAIN_THRESHOLD,
                    default=current.get(
                        CONF_BATTERY_DRAIN_THRESHOLD, DEFAULT_BATTERY_DRAIN_THRESHOLD
                    ),
                ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=100.0)),
                vol.Optional(
                    CONF_RECONNECT_RATE_THRESHOLD,
                    default=current.get(
                        CONF_RECONNECT_RATE_THRESHOLD,
                        DEFAULT_RECONNECT_RATE_THRESHOLD,
                    ),
                ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=100.0)),
                vol.Optional(
                    CONF_RECONNECT_RATE_WINDOW_HOURS,
                    default=current.get(
                        CONF_RECONNECT_RATE_WINDOW_HOURS,
                        DEFAULT_RECONNECT_RATE_WINDOW_HOURS,
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=168)),
            }
        )

        return self.async_show_form(step_id="init", data_schema=options_schema)
