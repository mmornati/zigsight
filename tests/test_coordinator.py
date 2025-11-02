"""Test coordinator."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from custom_components.zigsight.coordinator import ZigSightCoordinator


@pytest.fixture
def mock_hass() -> MagicMock:
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    return hass


@pytest.mark.asyncio
async def test_coordinator_construction(mock_hass: MagicMock) -> None:
    """Test that coordinator can be constructed."""
    coordinator = ZigSightCoordinator(mock_hass)
    assert coordinator is not None
    assert coordinator.name == "zigsight"


@pytest.mark.asyncio
async def test_coordinator_async_start(mock_hass: MagicMock) -> None:
    """Test that coordinator async_start() schedules its tasks."""
    coordinator = ZigSightCoordinator(mock_hass)
    await coordinator.async_start()
    
    # Verify that async_start completes without errors
    assert coordinator._tasks is not None


@pytest.mark.asyncio
async def test_coordinator_async_update_data(mock_hass: MagicMock) -> None:
    """Test that coordinator _async_update_data returns data."""
    coordinator = ZigSightCoordinator(mock_hass)
    data = await coordinator._async_update_data()
    
    # For now, it should return an empty dict as placeholder
    assert isinstance(data, dict)


@pytest.mark.asyncio
async def test_coordinator_async_shutdown(mock_hass: MagicMock) -> None:
    """Test that coordinator async_shutdown cancels tasks."""
    coordinator = ZigSightCoordinator(mock_hass)
    
    # Create a mock task
    mock_task = AsyncMock()
    mock_task.done.return_value = False
    coordinator._tasks = [mock_task]
    
    await coordinator.async_shutdown()
    
    # Verify task was cancelled
    assert mock_task.cancel.called

