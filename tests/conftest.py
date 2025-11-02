"""Pytest configuration and fixtures for ZigSight tests."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.zigsight.coordinator import ZigSightCoordinator


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


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
