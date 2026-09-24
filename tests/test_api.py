"""Test API views."""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import web
from homeassistant.core import HomeAssistant

from custom_components.zigsight.api import (
    ZigSightAnalyticsExportView,
    ZigSightAnalyticsOverviewView,
    ZigSightAnalyticsTrendsView,
    ZigSightChannelRecommendationView,
    ZigSightDevicesView,
    ZigSightRecommendationHistoryView,
    ZigSightTopologyView,
    setup_api_views,
)
from custom_components.zigsight.const import DOMAIN
from custom_components.zigsight.coordinator import ZigSightCoordinator


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock(spec=ZigSightCoordinator)
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
            "timestamp": datetime.now().isoformat(),
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


class TestZigSightDevicesView:
    """Test the devices view."""

    async def test_get_devices_skips_bridge(self, mock_hass, mock_coordinator):
        """Test devices are returned as a list without the bridge entry."""
        devices = dict(mock_coordinator.get_all_devices.return_value)
        devices["bridge"] = {"device_id": "bridge"}
        mock_coordinator.get_all_devices.return_value = devices

        view = ZigSightDevicesView(mock_hass)
        response = await view.get(MagicMock(spec=web.Request))

        assert response.status == 200
        body = json.loads(response.body)
        ids = [device["device_id"] for device in body["devices"]]
        assert ids == ["device1", "device2"]

    async def test_get_devices_no_coordinator(self):
        """Test devices request with no coordinator."""
        hass = MagicMock(spec=HomeAssistant)
        hass.data = {DOMAIN: {}}

        view = ZigSightDevicesView(hass)
        response = await view.get(MagicMock(spec=web.Request))

        assert response.status == 404

    async def test_get_devices_error(self, mock_hass, mock_coordinator):
        """Test devices request when the coordinator raises."""
        mock_coordinator.get_all_devices.side_effect = RuntimeError("boom")

        view = ZigSightDevicesView(mock_hass)
        response = await view.get(MagicMock(spec=web.Request))

        assert response.status == 500

    async def test_get_topology_error(self, mock_hass, mock_coordinator):
        """Test topology request when the coordinator raises."""
        mock_coordinator.get_all_devices.side_effect = RuntimeError("boom")

        view = ZigSightTopologyView(mock_hass)
        response = await view.get(MagicMock(spec=web.Request))

        assert response.status == 500


class TestZigSightChannelRecommendationView:
    """Test the channel recommendation view."""

    async def test_get_without_recommendation(self):
        """Test GET before any recommendation was computed."""
        hass = MagicMock(spec=HomeAssistant)
        hass.data = {DOMAIN: {}}

        view = ZigSightChannelRecommendationView(hass)
        response = await view.get(MagicMock(spec=web.Request))

        assert response.status == 200
        assert json.loads(response.body)["has_recommendation"] is False

    async def test_post_then_get(self):
        """Test POST computes a recommendation that GET and history return."""
        hass = MagicMock(spec=HomeAssistant)
        hass.data = {DOMAIN: {}}

        request = MagicMock(spec=web.Request)
        request.json = AsyncMock(
            return_value={
                "mode": "manual",
                "wifi_scan_data": [
                    {"channel": 1, "rssi": -40},
                    {"channel": 6, "rssi": -45},
                    {"channel": 11, "rssi": -50},
                ],
            }
        )

        view = ZigSightChannelRecommendationView(hass)
        response = await view.post(request)

        assert response.status == 200
        body = json.loads(response.body)
        assert body["has_recommendation"] is True
        assert body["recommended_channel"] in (11, 15, 20, 25)
        assert len(body["wifi_aps"]) == 3

        response = await view.get(MagicMock(spec=web.Request))
        body = json.loads(response.body)
        assert body["has_recommendation"] is True
        assert body["current_channel"] is None

        history_view = ZigSightRecommendationHistoryView(hass)
        response = await history_view.get(MagicMock(spec=web.Request))
        assert json.loads(response.body)["count"] == 1

    async def test_post_history_is_capped(self):
        """Test recommendation history keeps only the last 10 entries."""
        hass = MagicMock(spec=HomeAssistant)
        hass.data = {DOMAIN: {}}
        request = MagicMock(spec=web.Request)
        request.json = AsyncMock(
            return_value={
                "mode": "manual",
                "wifi_scan_data": [{"channel": 6, "rssi": -50}],
            }
        )

        view = ZigSightChannelRecommendationView(hass)
        for _ in range(12):
            await view.post(request)

        assert len(hass.data[DOMAIN]["recommendation_history"]) == 10

    async def test_post_invalid_mode(self):
        """Test POST with an unknown scanner mode returns an error."""
        hass = MagicMock(spec=HomeAssistant)
        hass.data = {DOMAIN: {}}
        request = MagicMock(spec=web.Request)
        request.json = AsyncMock(return_value={"mode": "invalid"})

        view = ZigSightChannelRecommendationView(hass)
        response = await view.post(request)

        assert response.status == 500


def test_setup_api_views_registers_all_views():
    """Test every API view is registered."""
    hass = MagicMock(spec=HomeAssistant)
    hass.http = MagicMock()

    setup_api_views(hass)

    assert hass.http.register_view.call_count == 7
