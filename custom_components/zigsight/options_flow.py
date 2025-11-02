"""Options flow for ZigSight."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult


class ZigSightOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for ZigSight."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        # Placeholder for future options configuration
        return self.async_create_entry(title="", data={})
