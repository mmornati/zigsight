"""Test API views."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
from aiohttp import web
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.zigsight.api import (
    ZigSightAnalyticsExportView,
    ZigSightAnalyticsOverviewView,
    ZigSightAnalyticsTrendsView,
    ZigSightChannelRecommendationView,
    ZigSightDevicesView,
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
    coordinator.get_network_links.return_value = []
    coordinator.get_network_nodes.return_value = []
    coordinator.get_network_info.return_value = None
    coordinator.coordinator_ieee = None
    coordinator.network_map_supported = True
    coordinator.network_map_updated = None
    coordinator.network_map_requested = None
    coordinator.network_map_pending = False
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

    async def test_get_trends_filters_aware_timestamps(
        self, mock_hass, mock_coordinator
    ):
        """History timestamps are timezone aware and filtered by window."""
        now = dt_util.utcnow()
        mock_coordinator.get_device_history.return_value = [
            {
                "timestamp": (now - timedelta(hours=48)).isoformat(),
                "metrics": {"battery": 90},
            },
            {
                "timestamp": (now - timedelta(hours=2)).isoformat(),
                "metrics": {"battery": 85},
            },
            {"timestamp": "garbage", "metrics": {"battery": 1}},
        ]
        view = ZigSightAnalyticsTrendsView(mock_hass)
        request = MagicMock(spec=web.Request)
        request.query = {"device_id": "device1", "metric": "battery", "hours": "24"}
        response = await view.get(request)
        assert response.status == 200
        body = json.loads(response.body)
        assert [point["value"] for point in body["data"]] == [85]

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

    async def test_get_trends_invalid_hours_not_a_number(self, mock_hass):
        """A non-numeric 'hours' is rejected with a clear 400."""
        view = ZigSightAnalyticsTrendsView(mock_hass)
        request = MagicMock(spec=web.Request)
        request.query = {"metric": "health_score", "hours": "nope"}

        response = await view.get(request)

        assert response.status == 400
        assert "hours" in json.loads(response.body)["error"]

    @pytest.mark.parametrize("hours", ["0", "-5", "721", "100000"])
    async def test_get_trends_invalid_hours_out_of_range(self, mock_hass, hours):
        """An out-of-range 'hours' is rejected with a clear 400."""
        view = ZigSightAnalyticsTrendsView(mock_hass)
        request = MagicMock(spec=web.Request)
        request.query = {"metric": "health_score", "hours": hours}

        response = await view.get(request)

        assert response.status == 400

    async def test_get_trends_invalid_metric(self, mock_hass):
        """An unknown metric is rejected with a clear 400."""
        view = ZigSightAnalyticsTrendsView(mock_hass)
        request = MagicMock(spec=web.Request)
        request.query = {"metric": "not_a_real_metric", "hours": "24"}

        response = await view.get(request)

        assert response.status == 400
        assert "metric" in json.loads(response.body)["error"]


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

    async def test_export_invalid_format(self, mock_hass):
        """An unsupported export format is rejected with a clear 400."""
        view = ZigSightAnalyticsExportView(mock_hass)
        request = MagicMock(spec=web.Request)
        request.query = {"format": "xml"}

        response = await view.get(request)

        assert response.status == 400
        assert "format" in json.loads(response.body)["error"]

    async def test_export_empty_devices_param(self, mock_hass):
        """A 'devices' parameter with no usable id is rejected with 400."""
        view = ZigSightAnalyticsExportView(mock_hass)
        request = MagicMock(spec=web.Request)
        request.query = {"format": "json", "devices": " , ,"}

        response = await view.get(request)

        assert response.status == 400

    async def test_export_csv_escapes_formula_injection(
        self, mock_hass, mock_coordinator
    ):
        """Values starting with =, +, -, @ are prefixed with a quote in CSV."""
        devices = copy.deepcopy(mock_coordinator.get_all_devices.return_value)
        devices["device1"]["friendly_name"] = "=cmd|' /C calc'!A1"
        mock_coordinator.get_all_devices.return_value = devices

        view = ZigSightAnalyticsExportView(mock_hass)
        request = MagicMock(spec=web.Request)
        request.query = {"format": "csv"}

        response = await view.get(request)

        assert response.status == 200
        text = response.text
        assert "'=cmd|' /C calc'!A1" in text
        assert "\n=cmd" not in text
        assert ",=cmd" not in text


class TestZigSightTopologyView:
    """Test the topology view."""

    async def test_get_topology_success(self, mock_hass, mock_coordinator):
        """Without a network map the edges are an inferred star."""
        view = ZigSightTopologyView(mock_hass)
        response = await view.get(MagicMock(spec=web.Request))

        assert response.status == 200
        body = json.loads(response.body)
        assert body["links_source"] == "inferred"
        assert body["network_map"] == {
            "supported": True,
            "updated": None,
            "requested": None,
            "pending": False,
        }
        assert {(e["from"], e["to"]) for e in body["edges"]} == {
            ("coordinator", "device1"),
            ("coordinator", "device2"),
        }

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


def test_setup_api_views_registers_all_views():
    """Test every API view is registered."""
    hass = MagicMock(spec=HomeAssistant)
    hass.http = MagicMock()

    hass.data = {}

    setup_api_views(hass)
    assert hass.http.register_view.call_count == 8

    # Registered once per Home Assistant run (entry reloads don't re-register)
    setup_api_views(hass)
    assert hass.http.register_view.call_count == 8
