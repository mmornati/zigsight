"""Test API views."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import web
from homeassistant.core import HomeAssistant

from custom_components.zigsight.api import (
    ZigSightAnalyticsExportView,
    ZigSightAnalyticsOverviewView,
    ZigSightAnalyticsTrendsView,
    ZigSightTopologyView,
)
from custom_components.zigsight.const import DOMAIN


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.get_all_devices.return_value = {
        "device1": {
            "device_id": "device1",
            "friendly_name": "Test Device 1",
            "metrics": {
                "battery": 85,
                "link_quality": 200,
                "type": "end_device",
                "last_seen": datetime.now().isoformat(),
            },
            "analytics_metrics": {
                "health_score": 92.5,
                "reconnect_rate": 0.2,
                "battery_trend": -0.05,
                "battery_drain_warning": False,
                "connectivity_warning": False,
            },
            "reconnect_count": 2,
            "last_update": datetime.now().isoformat(),
        },
        "device2": {
            "device_id": "device2",
            "friendly_name": "Test Device 2",
            "metrics": {
                "battery": 15,
                "link_quality": 80,
                "type": "end_device",
                "last_seen": datetime.now().isoformat(),
            },
            "analytics_metrics": {
                "health_score": 45.0,
                "reconnect_rate": 5.5,
                "battery_trend": -2.5,
                "battery_drain_warning": True,
                "connectivity_warning": True,
            },
            "reconnect_count": 50,
            "last_update": datetime.now().isoformat(),
        },
    }
    coordinator.get_device_history.return_value = [
        {
            "timestamp": (datetime.now()).isoformat(),
            "metrics": {"battery": 85, "link_quality": 200},
        }
    ]
    coordinator.get_device.return_value = coordinator.get_all_devices()["device1"]
    return coordinator


@pytest.fixture
def mock_hass(mock_coordinator):
    """Create a mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {DOMAIN: {"test_entry": mock_coordinator}}
    hass.http = MagicMock()
    return hass


class TestZigSightAnalyticsOverviewView:
    """Test the analytics overview view."""

    async def test_get_overview_success(self, mock_hass):
        """Test successful overview request."""
        view = ZigSightAnalyticsOverviewView(mock_hass)
        request = MagicMock(spec=web.Request)

        response = await view.get(request)

        assert response.status == 200
        data = response.body
        # Basic checks - the actual response is JSON
        assert data is not None

    async def test_get_overview_no_coordinator(self):
        """Test overview request with no coordinator."""
        hass = MagicMock(spec=HomeAssistant)
        hass.data = {DOMAIN: {}}

        view = ZigSightAnalyticsOverviewView(hass)
        request = MagicMock(spec=web.Request)

        response = await view.get(request)

        assert response.status == 404


class TestZigSightAnalyticsTrendsView:
    """Test the analytics trends view."""

    async def test_get_trends_with_device_id(self, mock_hass):
        """Test trends request for specific device."""
        view = ZigSightAnalyticsTrendsView(mock_hass)
        request = MagicMock(spec=web.Request)
        request.query = {"device_id": "device1", "metric": "battery", "hours": "24"}

        response = await view.get(request)

        assert response.status == 200

    async def test_get_trends_network_wide(self, mock_hass):
        """Test trends request for network-wide data."""
        view = ZigSightAnalyticsTrendsView(mock_hass)
        request = MagicMock(spec=web.Request)
        request.query = {"metric": "health_score", "hours": "24"}

        response = await view.get(request)

        assert response.status == 200

    async def test_get_trends_no_coordinator(self):
        """Test trends request with no coordinator."""
        hass = MagicMock(spec=HomeAssistant)
        hass.data = {DOMAIN: {}}

        view = ZigSightAnalyticsTrendsView(hass)
        request = MagicMock(spec=web.Request)
        request.query = {"metric": "health_score", "hours": "24"}

        response = await view.get(request)

        assert response.status == 404


class TestZigSightAnalyticsExportView:
    """Test the analytics export view."""

    async def test_export_json(self, mock_hass):
        """Test JSON export."""
        view = ZigSightAnalyticsExportView(mock_hass)
        request = MagicMock(spec=web.Request)
        request.query = {"format": "json"}

        response = await view.get(request)

        assert response.status == 200

    async def test_export_csv(self, mock_hass):
        """Test CSV export."""
        view = ZigSightAnalyticsExportView(mock_hass)
        request = MagicMock(spec=web.Request)
        request.query = {"format": "csv"}

        response = await view.get(request)

        assert response.status == 200
        # CSV responses should have text/csv content type
        assert "text/csv" in str(response.content_type)

    async def test_export_filtered_devices(self, mock_hass):
        """Test export with device filter."""
        view = ZigSightAnalyticsExportView(mock_hass)
        request = MagicMock(spec=web.Request)
        request.query = {"format": "json", "devices": "device1"}

        response = await view.get(request)

        assert response.status == 200

    async def test_export_no_coordinator(self):
        """Test export with no coordinator."""
        hass = MagicMock(spec=HomeAssistant)
        hass.data = {DOMAIN: {}}

        view = ZigSightAnalyticsExportView(hass)
        request = MagicMock(spec=web.Request)
        request.query = {"format": "json"}

        response = await view.get(request)

        assert response.status == 404


class TestZigSightTopologyView:
    """Test the topology view."""

    async def test_get_topology_success(self, mock_hass, mock_coordinator):
        """Test successful topology request."""
        # Mock the build_topology function
        with patch(
            "custom_components.zigsight.api.build_topology"
        ) as mock_build_topology:
            mock_build_topology.return_value = {
                "nodes": [],
                "edges": [],
                "device_count": 2,
            }

            view = ZigSightTopologyView(mock_hass)
            request = MagicMock(spec=web.Request)

            response = await view.get(request)

            assert response.status == 200
            mock_build_topology.assert_called_once()

    async def test_get_topology_no_coordinator(self):
        """Test topology request with no coordinator."""
        hass = MagicMock(spec=HomeAssistant)
        hass.data = {DOMAIN: {}}

        view = ZigSightTopologyView(hass)
        request = MagicMock(spec=web.Request)

        response = await view.get(request)

        assert response.status == 404
