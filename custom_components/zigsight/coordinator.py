"""DataUpdateCoordinator for ZigSight."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ZigSightCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching ZigSight data."""

    def __init__(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
        )
        self._tasks: list[asyncio.Task[None]] = []

    async def async_start(self) -> None:
        """Start the coordinator and schedule background tasks."""
        self.logger.info("Starting ZigSight coordinator")
        # Placeholder for future task scheduling
        # Tasks will be added here when collectors are implemented

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from ZigSight.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            # Placeholder: will be implemented when collectors are added
            return {}
        except Exception as err:
            raise UpdateFailed(f"Error fetching ZigSight data: {err}") from err

    async def async_shutdown(self) -> None:
        """Cancel any background tasks."""
        for task in self._tasks:
            if not task.done():
                task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
