"""Test coordinator."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.zigsight.coordinator import ZigSightCoordinator


@pytest.mark.asyncio
async def test_coordinator_construction() -> None:
    """Test that coordinator can be constructed."""
    mock_hass = MagicMock()
    coordinator = ZigSightCoordinator(mock_hass)
    assert coordinator is not None
    assert coordinator.name == "zigsight"


@pytest.mark.asyncio
async def test_coordinator_async_start() -> None:
    """Test that coordinator async_start() schedules its tasks."""
    mock_hass = MagicMock()
    coordinator = ZigSightCoordinator(mock_hass)
    await coordinator.async_start()

    # Verify that async_start completes without errors
    assert coordinator._tasks is not None


@pytest.mark.asyncio
async def test_coordinator_async_update_data() -> None:
    """Test that coordinator _async_update_data returns data."""
    mock_hass = MagicMock()
    coordinator = ZigSightCoordinator(mock_hass)
    data = await coordinator._async_update_data()

    # For now, it should return an empty dict as placeholder
    assert isinstance(data, dict)


@pytest.mark.asyncio
async def test_coordinator_async_shutdown() -> None:
    """Test that coordinator async_shutdown cancels tasks."""
    mock_hass = MagicMock()
    coordinator = ZigSightCoordinator(mock_hass)

    # Create a mock task
    mock_task = AsyncMock()
    mock_task.done.return_value = False
    coordinator._tasks = [mock_task]

    await coordinator.async_shutdown()

    # Verify task was cancelled
    assert mock_task.cancel.called
