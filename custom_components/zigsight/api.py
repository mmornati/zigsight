"""API views for ZigSight."""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timedelta

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
            devices = coordinator.get_all_devices()
            topology = build_topology(devices)

            return self.json(topology)

        except Exception as err:
            _LOGGER.error("Error generating topology: %s", err, exc_info=True)
            return self.json(
                {"error": f"Failed to generate topology: {err}"},
                status_code=500,
            )


class ZigSightDevicesView(HomeAssistantView):
    """View to serve device data."""

    url = "/api/zigsight/devices"
    name = "api:zigsight:devices"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the devices view."""
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        """Handle GET request for devices data."""
        try:
            # Get coordinator from hass data
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

<<<<<<< HEAD
            # Collect overview data
            devices = coordinator.get_all_devices()
            
            # Filter out bridge
            device_list = [d for d_id, d in devices.items() if d_id != "bridge"]
            
            total_devices = len(device_list)
            
            # Calculate average health score
            health_scores = [
                d.get("analytics_metrics", {}).get("health_score", 0)
                for d in device_list
                if d.get("analytics_metrics", {}).get("health_score") is not None
            ]
            avg_health_score = sum(health_scores) / len(health_scores) if health_scores else 0
            
            # Count devices with warnings
            devices_with_warnings = sum(
                1 for d in device_list
                if d.get("analytics_metrics", {}).get("battery_drain_warning") or
                   d.get("analytics_metrics", {}).get("connectivity_warning")
            )
            
            # Battery level distribution
            battery_levels = [
                d.get("metrics", {}).get("battery")
                for d in device_list
                if d.get("metrics", {}).get("battery") is not None
            ]
            
            battery_distribution = {
                "0-20": sum(1 for b in battery_levels if b <= 20),
                "21-40": sum(1 for b in battery_levels if 20 < b <= 40),
                "41-60": sum(1 for b in battery_levels if 40 < b <= 60),
                "61-80": sum(1 for b in battery_levels if 60 < b <= 80),
                "81-100": sum(1 for b in battery_levels if 80 < b <= 100),
            }
            
            # Link quality distribution
            link_qualities = [
                d.get("metrics", {}).get("link_quality")
                for d in device_list
                if d.get("metrics", {}).get("link_quality") is not None
            ]
            
            link_quality_distribution = {
                "poor (0-99)": sum(1 for lq in link_qualities if lq < 100),
                "fair (100-149)": sum(1 for lq in link_qualities if 100 <= lq < 150),
                "good (150-199)": sum(1 for lq in link_qualities if 150 <= lq < 200),
                "excellent (200-255)": sum(1 for lq in link_qualities if 200 <= lq <= 255),
            }
            
            overview = {
                "total_devices": total_devices,
                "average_health_score": round(avg_health_score, 1),
                "devices_with_warnings": devices_with_warnings,
                "battery_distribution": battery_distribution,
                "link_quality_distribution": link_quality_distribution,
                "devices_by_type": {
                    "coordinator": sum(1 for d in device_list if d.get("metrics", {}).get("type") == "coordinator"),
                    "router": sum(1 for d in device_list if d.get("metrics", {}).get("type") == "router"),
                    "end_device": sum(1 for d in device_list if d.get("metrics", {}).get("type") == "end_device"),
                },
            }

            return self.json(overview)

        except Exception as err:
            _LOGGER.error("Error generating analytics overview: %s", err, exc_info=True)
            return self.json(
                {"error": f"Failed to generate analytics overview: {err}"},
                status_code=500,
            )


class ZigSightAnalyticsTrendsView(HomeAssistantView):
    """View to serve analytics trends data."""

    url = "/api/zigsight/analytics/trends"
    name = "api:zigsight:analytics:trends"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the analytics trends view."""
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        """Handle GET request for analytics trends data."""
        try:
            # Get query parameters
            device_id = request.query.get("device_id")
            metric = request.query.get("metric", "health_score")
            try:
                hours = int(request.query.get("hours", "24"))
                # Validate hours is within reasonable bounds
                if hours < 1 or hours > 720:  # Max 30 days
                    hours = 24
            except (ValueError, TypeError):
                hours = 24

            # Get coordinator from hass data
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

            if device_id:
                # Get trends for specific device
                device_history = coordinator.get_device_history(device_id)
                
                # Filter history by time window
                cutoff_time = datetime.now() - timedelta(hours=hours)
                filtered_history = []
                for entry in device_history:
                    try:
                        timestamp_str = entry.get("timestamp", "")
                        if timestamp_str:
                            timestamp = datetime.fromisoformat(timestamp_str)
                            if timestamp > cutoff_time:
                                filtered_history.append(entry)
                    except (ValueError, TypeError):
                        # Skip entries with invalid timestamps
                        continue
                
                # Extract metric data
                trends = []
                for entry in filtered_history:
                    timestamp = entry.get("timestamp")
                    metrics = entry.get("metrics", {})
                    
                    if metric == "health_score":
                        # Health score needs to be computed
                        device = coordinator.get_device(device_id)
                        if device:
                            value = device.get("analytics_metrics", {}).get("health_score")
                    elif metric == "battery":
                        value = metrics.get("battery")
                    elif metric == "link_quality":
                        value = metrics.get("link_quality")
                    elif metric == "reconnect_rate":
                        device = coordinator.get_device(device_id)
                        value = device.get("analytics_metrics", {}).get("reconnect_rate") if device else None
                    else:
                        value = None
                    
                    if value is not None:
                        trends.append({
                            "timestamp": timestamp,
                            "value": value,
                        })
                
                return self.json({
                    "device_id": device_id,
                    "metric": metric,
                    "hours": hours,
                    "data": trends,
                })
            else:
                # Get network-wide trends
                devices = coordinator.get_all_devices()
                device_list = [d for d_id, d in devices.items() if d_id != "bridge"]
                
                # Calculate aggregate metrics over time
                # For now, return current aggregates
                # TODO: Implement time-series aggregation
                
                return self.json({
                    "metric": metric,
                    "hours": hours,
                    "data": [],
                    "message": "Network-wide trends require time-series aggregation (not yet implemented)"
                })

        except Exception as err:
            _LOGGER.error("Error generating analytics trends: %s", err, exc_info=True)
            return self.json(
                {"error": f"Failed to generate analytics trends: {err}"},
                status_code=500,
            )


class ZigSightAnalyticsExportView(HomeAssistantView):
    """View to export analytics data."""

    url = "/api/zigsight/analytics/export"
    name = "api:zigsight:analytics:export"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the analytics export view."""
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        """Handle GET request for analytics export."""
        try:
            # Get query parameters
            export_format = request.query.get("format", "json")
            devices_param = request.query.get("devices", "")
            device_ids = devices_param.split(",") if devices_param else None

            # Get coordinator from hass data
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

            # Get devices
            devices = coordinator.get_all_devices()
            
            # Filter by device_ids if specified
            if device_ids:
                devices = {k: v for k, v in devices.items() if k in device_ids}
            
            # Remove bridge
            devices = {k: v for k, v in devices.items() if k != "bridge"}
            
            # Prepare export data
            export_data = []
            for device_id, device in devices.items():
                metrics = device.get("metrics", {})
                analytics = device.get("analytics_metrics", {})
                
                export_data.append({
                    "device_id": device_id,
                    "friendly_name": device.get("friendly_name", device_id),
                    "last_update": device.get("last_update"),
                    "link_quality": metrics.get("link_quality"),
                    "battery": metrics.get("battery"),
                    "last_seen": metrics.get("last_seen"),
                    "health_score": analytics.get("health_score"),
                    "reconnect_rate": analytics.get("reconnect_rate"),
                    "battery_trend": analytics.get("battery_trend"),
                    "battery_drain_warning": analytics.get("battery_drain_warning"),
                    "connectivity_warning": analytics.get("connectivity_warning"),
                    "reconnect_count": device.get("reconnect_count"),
                })
            
            if export_format == "csv":
                # Convert to CSV
                output = io.StringIO()
                if export_data:
                    writer = csv.DictWriter(output, fieldnames=export_data[0].keys())
                    writer.writeheader()
                    writer.writerows(export_data)
                
                csv_data = output.getvalue()
                return web.Response(
                    text=csv_data,
                    content_type="text/csv",
                    headers={
                        "Content-Disposition": "attachment; filename=zigsight-analytics.csv"
                    },
                )
            else:
                # Return JSON
                return self.json(export_data)

        except Exception as err:
            _LOGGER.error("Error exporting analytics: %s", err, exc_info=True)
            return self.json(
                {"error": f"Failed to export analytics: {err}"},
                status_code=500,
            )


class ZigSightChannelRecommendationView(HomeAssistantView):
    """View to serve channel recommendation data."""

    url = "/api/zigsight/channel-recommendation"
    name = "api:zigsight:channel-recommendation"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the channel recommendation view."""
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        """Handle GET request for channel recommendation data."""
        try:
            from .const import DOMAIN

            # Get the last recommendation from service call
            last_recommendation = self.hass.data.get(DOMAIN, {}).get("last_recommendation")
            
            if not last_recommendation:
                # No recommendation available, return empty state
                return self.json({
                    "has_recommendation": False,
                    "message": "No channel recommendation available. Please run the 'zigsight.recommend_channel' service first.",
                })
            
            # Add current Zigbee channel from coordinator if available
            current_channel = None
            for coordinator_data in self.hass.data.get(DOMAIN, {}).values():
                if hasattr(coordinator_data, "get_network_info"):
                    network_info = coordinator_data.get_network_info()
                    if network_info:
                        current_channel = network_info.get("channel")
                        break
            
            response_data = {
                "has_recommendation": True,
                "recommended_channel": last_recommendation.get("recommended_channel"),
                "current_channel": current_channel,
                "scores": last_recommendation.get("scores", {}),
                "explanation": last_recommendation.get("explanation", ""),
                "timestamp": datetime.now().isoformat(),
            }
            
            return self.json(response_data)

        except Exception as err:
            _LOGGER.error("Error getting channel recommendation: %s", err, exc_info=True)
            return self.json(
                {"error": f"Failed to get channel recommendation: {err}"},
                status_code=500,
            )

    async def post(self, request: web.Request) -> web.Response:
        """Handle POST request to trigger channel recommendation."""
        try:
            from .recommender import recommend_zigbee_channel
            from .wifi_scanner import create_scanner

            data = await request.json()
            mode = data.get("mode", "manual")
            wifi_scan_data = data.get("wifi_scan_data")

            # Create appropriate scanner
            scanner = create_scanner(
                mode=mode,
                scan_data=wifi_scan_data,
            )

            # Perform scan
            wifi_aps = await scanner.scan()

            # Get recommendation
            result = recommend_zigbee_channel(wifi_aps)

            _LOGGER.info(
                "Zigbee channel recommendation: Channel %s (score: %.1f)",
                result["recommended_channel"],
                result["scores"][result["recommended_channel"]],
            )

            # Store result in hass.data
            from .const import DOMAIN
            self.hass.data.setdefault(DOMAIN, {})
            self.hass.data[DOMAIN]["last_recommendation"] = result
            
            # Also store in history
            history_key = "recommendation_history"
            if history_key not in self.hass.data[DOMAIN]:
                self.hass.data[DOMAIN][history_key] = []
            
            history_entry = {
                **result,
                "timestamp": datetime.now().isoformat(),
                "wifi_aps_count": len(wifi_aps),
            }
            self.hass.data[DOMAIN][history_key].append(history_entry)
            
            # Keep only last 10 recommendations in history
            self.hass.data[DOMAIN][history_key] = self.hass.data[DOMAIN][history_key][-10:]

            # Return recommendation
            return self.json({
                "has_recommendation": True,
                "recommended_channel": result["recommended_channel"],
                "scores": result["scores"],
                "explanation": result["explanation"],
                "wifi_aps": wifi_aps,
                "timestamp": history_entry["timestamp"],
            })

        except Exception as err:
            _LOGGER.error("Error during channel recommendation: %s", err, exc_info=True)
            return self.json(
                {"error": f"Failed to generate channel recommendation: {err}"},
                status_code=500,
            )


class ZigSightRecommendationHistoryView(HomeAssistantView):
    """View to serve recommendation history."""

    url = "/api/zigsight/recommendation-history"
    name = "api:zigsight:recommendation-history"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the recommendation history view."""
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        """Handle GET request for recommendation history."""
        try:
            from .const import DOMAIN

            history = self.hass.data.get(DOMAIN, {}).get("recommendation_history", [])
            
            return self.json({
                "history": history,
                "count": len(history),
            })

        except Exception as err:
            _LOGGER.error("Error getting recommendation history: %s", err, exc_info=True)
            return self.json(
                {"error": f"Failed to get recommendation history: {err}"},
                status_code=500,
            )


class ZigSightAnalyticsOverviewView(HomeAssistantView):
    """View to serve analytics overview data."""

    url = "/api/zigsight/analytics/overview"
    name = "api:zigsight:analytics:overview"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the analytics overview view."""
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        """Handle GET request for analytics overview data."""
        try:
            # Get coordinator from hass data
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

            # Collect overview data
            devices = coordinator.get_all_devices()
            
            # Filter out bridge
            device_list = [d for d_id, d in devices.items() if d_id != "bridge"]
            
            total_devices = len(device_list)
            
            # Calculate average health score
            health_scores = [
                d.get("analytics_metrics", {}).get("health_score", 0)
                for d in device_list
                if d.get("analytics_metrics", {}).get("health_score") is not None
            ]
            avg_health_score = sum(health_scores) / len(health_scores) if health_scores else 0
            
            # Count devices with warnings
            devices_with_warnings = sum(
                1 for d in device_list
                if d.get("analytics_metrics", {}).get("battery_drain_warning") or
                   d.get("analytics_metrics", {}).get("connectivity_warning")
            )
            
            # Battery level distribution
            battery_levels = [
                d.get("metrics", {}).get("battery")
                for d in device_list
                if d.get("metrics", {}).get("battery") is not None
            ]
            
            battery_distribution = {
                "0-20": sum(1 for b in battery_levels if b <= 20),
                "21-40": sum(1 for b in battery_levels if 20 < b <= 40),
                "41-60": sum(1 for b in battery_levels if 40 < b <= 60),
                "61-80": sum(1 for b in battery_levels if 60 < b <= 80),
                "81-100": sum(1 for b in battery_levels if 80 < b <= 100),
            }
            
            # Link quality distribution
            link_qualities = [
                d.get("metrics", {}).get("link_quality")
                for d in device_list
                if d.get("metrics", {}).get("link_quality") is not None
            ]
            
            link_quality_distribution = {
                "poor (0-99)": sum(1 for lq in link_qualities if lq < 100),
                "fair (100-149)": sum(1 for lq in link_qualities if 100 <= lq < 150),
                "good (150-199)": sum(1 for lq in link_qualities if 150 <= lq < 200),
                "excellent (200-255)": sum(1 for lq in link_qualities if 200 <= lq <= 255),
            }
            
            overview = {
                "total_devices": total_devices,
                "average_health_score": round(avg_health_score, 1),
                "devices_with_warnings": devices_with_warnings,
                "battery_distribution": battery_distribution,
                "link_quality_distribution": link_quality_distribution,
                "devices_by_type": {
                    "coordinator": sum(1 for d in device_list if d.get("metrics", {}).get("type") == "coordinator"),
                    "router": sum(1 for d in device_list if d.get("metrics", {}).get("type") == "router"),
                    "end_device": sum(1 for d in device_list if d.get("metrics", {}).get("type") == "end_device"),
                },
            }

            return self.json(overview)

        except Exception as err:
            _LOGGER.error("Error generating analytics overview: %s", err, exc_info=True)
            return self.json(
                {"error": f"Failed to generate analytics overview: {err}"},
                status_code=500,
            )


def setup_api_views(hass: HomeAssistant) -> None:
    """Set up API views for ZigSight."""
    _LOGGER.info("Setting up ZigSight API views")

    # Register topology view
    hass.http.register_view(ZigSightTopologyView(hass))
    
    # Register devices view
    hass.http.register_view(ZigSightDevicesView(hass))
    
    # Register analytics views
    hass.http.register_view(ZigSightAnalyticsOverviewView(hass))
    hass.http.register_view(ZigSightAnalyticsTrendsView(hass))
    hass.http.register_view(ZigSightAnalyticsExportView(hass))
    
    # Register channel recommendation views
    hass.http.register_view(ZigSightChannelRecommendationView(hass))
    hass.http.register_view(ZigSightRecommendationHistoryView(hass))

    _LOGGER.info("ZigSight API views registered")
