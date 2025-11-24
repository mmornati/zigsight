"""API views for ZigSight."""

from __future__ import annotations

import logging

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import ZigSightCoordinator
from .topology import build_topology

_LOGGER = logging.getLogger(__name__)


class ZigSightTopologyView(HomeAssistantView):
    """View to serve network topology data."""

    url = "/api/zigsight/topology"
    name = "api:zigsight:topology"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the topology view."""
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        """Handle GET request for topology data."""
        try:
            # Get coordinator from hass data
            # There might be multiple coordinators if multiple config entries
            coordinators = []
            for coordinator in self.hass.data.get(DOMAIN, {}).values():
                if isinstance(coordinator, ZigSightCoordinator):
                    coordinators.append(coordinator)

            if not coordinators:
                return self.json(
                    {"error": "No ZigSight coordinator found"},
                    status_code=404,
                )

            # Use the first coordinator
            coordinator = coordinators[0]

            # Build topology from coordinator devices
            devices = coordinator._devices  # noqa: SLF001
            topology = build_topology(devices)

            return self.json(topology)

        except Exception as err:
            _LOGGER.error("Error generating topology: %s", err, exc_info=True)
            return self.json(
                {"error": f"Failed to generate topology: {err}"},
                status_code=500,
            )


def setup_api_views(hass: HomeAssistant) -> None:
    """Set up API views for ZigSight."""
    _LOGGER.info("Setting up ZigSight API views")

    # Register topology view
    hass.http.register_view(ZigSightTopologyView(hass))

    _LOGGER.info("ZigSight API views registered")
