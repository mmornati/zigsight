"""Pytest configuration and fixtures for ZigSight tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.zigsight.coordinator import ZigSightCoordinator

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: Any) -> None:
    """Enable custom integrations for every test.

    ``pytest-homeassistant-custom-component`` disables custom (non-core)
    integrations by default so that ``hass`` fixtures stay fast/hermetic.
    ZigSight IS a custom integration, so real integration tests need it
    re-enabled; this autouse fixture wraps the plugin's own
    ``enable_custom_integrations`` fixture so every test gets it for free.
    """
    return


@pytest.fixture
def mock_hass() -> MagicMock:
    """Mock Home Assistant instance."""
    hass = MagicMock()
    hass.config.path.return_value = "/tmp/test_hass"
    hass.data = {}
    hass.services = MagicMock()
    hass.services.async_register = AsyncMock()
    hass.config_entries = MagicMock()
    hass.config_entries.async_get_entry = MagicMock()
    hass.helpers = MagicMock()
    hass.helpers.update_coordinator = MagicMock()
    hass.helpers.dispatcher = MagicMock()
    hass.helpers.dispatcher.async_dispatcher_send = AsyncMock()
    return hass


@pytest.fixture
def mock_config_entry() -> MagicMock:
    """Mock Home Assistant config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {}
    entry.options = {}
    entry.title = "ZigSight"
    return entry


@pytest.fixture
def coordinator(mock_hass: MagicMock) -> ZigSightCoordinator:
    """Create a ZigSight coordinator for testing."""
    return ZigSightCoordinator(mock_hass)


@pytest.fixture
async def async_coordinator(mock_hass: MagicMock) -> ZigSightCoordinator:
    """Create and start an async ZigSight coordinator for testing."""
    coordinator = ZigSightCoordinator(mock_hass)
    await coordinator.async_start()
    return coordinator


@pytest.fixture
def sample_device_data() -> dict[str, Any]:
    """Sample device data for testing."""
    return {
        "device_id": "test_device",
        "link_quality": 100,
        "battery": 80,
        "voltage": 3.0,
        "last_seen": "2024-01-01T12:00:00Z",
        "available": True,
    }


@pytest.fixture
def sample_coordinator_data() -> dict[str, Any]:
    """Sample coordinator data for testing."""
    return {
        "test_device": {
            "link_quality": 100,
            "battery": 80,
            "voltage": 3.0,
            "last_seen": "2024-01-01T12:00:00Z",
            "available": True,
        }
    }
