"""API views for ZigSight."""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timedelta
from typing import Any

import voluptuous as vol
from aiohttp import web
from homeassistant.components.http import HomeAssistantView, require_admin
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
from voluptuous.humanize import humanize_error

from .const import DOMAIN
from .coordinator import ZigSightCoordinator
from .recommender import recommend_zigbee_channel
from .topology import build_topology
from .wifi_scanner import create_scanner

_LOGGER = logging.getLogger(__name__)

DATA_API_VIEWS_REGISTERED = f"{DOMAIN}_api_views_registered"
RECOMMENDATION_HISTORY_MAX = 10
VALID_TREND_METRICS = {"health_score", "battery", "link_quality", "reconnect_rate"}
VALID_EXPORT_FORMATS = {"json", "csv"}
# CSV formula-injection: a leading one of these characters is interpreted by
# spreadsheet applications (Excel, LibreOffice, Google Sheets) as the start
# of a formula. Prefixing with a single quote defuses it while keeping the
# value readable.
CSV_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

WIFI_ACCESS_POINT_SCHEMA = vol.Schema(
    {
        vol.Required("channel"): vol.All(vol.Coerce(int), vol.Range(min=1, max=14)),
        vol.Required("rssi"): vol.All(vol.Coerce(float), vol.Range(min=-120, max=0)),
        vol.Optional("ssid"): vol.Any(None, vol.All(str, vol.Length(max=64))),
    },
    extra=vol.REMOVE_EXTRA,
)
WIFI_SCAN_DATA_SCHEMA = vol.All(
    vol.Any(
        [WIFI_ACCESS_POINT_SCHEMA],
        vol.All(
            {vol.Required("access_points"): [WIFI_ACCESS_POINT_SCHEMA]},
            lambda value: value["access_points"],
        ),
    ),
    vol.Length(max=500),
)
CHANNEL_RECOMMENDATION_SCHEMA = vol.Schema(
    {
        vol.Optional("mode", default="manual"): vol.In(["manual", "host_scan"]),
        vol.Optional("wifi_scan_data"): WIFI_SCAN_DATA_SCHEMA,
    }
)


def get_coordinator(hass: HomeAssistant) -> ZigSightCoordinator | None:
    """Return the (single) loaded ZigSight coordinator, if any."""
    for value in hass.data.get(DOMAIN, {}).values():
        if isinstance(value, ZigSightCoordinator):
            return value
    return None


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _csv_safe(value: Any) -> Any:
    """Escape a value that could be interpreted as a CSV formula.

    Prefixes a leading ``=``, ``+``, ``-``, ``@``, tab or carriage return
    with a single quote, matching OWASP's CSV injection guidance. Non-string
    values are returned unchanged.
    """
    if isinstance(value, str) and value.startswith(CSV_FORMULA_PREFIXES):
        return f"'{value}"
    return value


def _current_channel(coordinator: ZigSightCoordinator | None) -> int | None:
    if coordinator is None:
        return None
    network_info = coordinator.get_network_info() or {}
    channel = network_info.get("channel")
    return channel if isinstance(channel, int) else None


class ChannelRecommendationError(HomeAssistantError):
    """A Wi-Fi scan or channel recommendation computation failed.

    The underlying error (which may contain host/network details, e.g. a
    subprocess error message) is logged with a traceback where this is
    raised; only this generic message is meant to reach the caller.
    """


async def async_generate_channel_recommendation(
    hass: HomeAssistant, mode: str, wifi_scan_data: Any
) -> dict[str, Any]:
    """Scan, compute and store a channel recommendation.

    Shared by the REST API (POST /api/zigsight/channel-recommendation) and
    the ``recommend_channel`` service so both behave identically: same
    manual-mode validation, same ``last_recommendation`` /
    ``recommendation_history`` bookkeeping.

    Raises:
        ValueError: manual mode without (non-empty) ``wifi_scan_data``, a
            caller-input problem the caller should surface directly.
        ChannelRecommendationError: the scan or computation itself failed;
            already logged with a traceback here.
    """
    if mode == "manual" and not wifi_scan_data:
        raise ValueError("wifi_scan_data is required in manual mode")

    try:
        scanner = create_scanner(mode=mode, scan_data=wifi_scan_data)
        wifi_aps = await scanner.scan()
        result = recommend_zigbee_channel(wifi_aps)
    except Exception as err:
        _LOGGER.exception("Error during channel recommendation")
        raise ChannelRecommendationError(
            "Failed to generate a channel recommendation"
        ) from err

    timestamp = dt_util.utcnow().isoformat()
    _LOGGER.info(
        "Zigbee channel recommendation: channel %s (score: %.1f)",
        result["recommended_channel"],
        result["scores"][result["recommended_channel"]],
    )
    _LOGGER.info("Recommendation: %s", result["explanation"])

    domain_data = hass.data.setdefault(DOMAIN, {})
    domain_data["last_recommendation"] = {**result, "timestamp": timestamp}
    history = domain_data.setdefault("recommendation_history", [])
    history.append({**result, "timestamp": timestamp, "wifi_aps_count": len(wifi_aps)})
    del history[:-RECOMMENDATION_HISTORY_MAX]

    return {
        "recommended_channel": result["recommended_channel"],
        "scores": result["scores"],
        "explanation": result["explanation"],
        "wifi_aps": wifi_aps,
        "wifi_aps_count": len(wifi_aps),
        "timestamp": timestamp,
    }


class ZigSightTopologyView(HomeAssistantView):
    """View to serve network topology data."""

    url = "/api/zigsight/topology"
    name = "api:zigsight:topology"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the topology view."""
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        """Handle GET request for topology data.

        Deliberately *not* admin-only, unlike the other ZigSight GET
        endpoints: ``topology-card.js`` and ``topology-visualization.js``
        (Lovelace cards usable by any authenticated user, on dashboards a
        non-admin may view) poll this endpoint every 60 seconds. Gating it
        behind ``@require_admin`` made every such poll a failed admin check,
        which Home Assistant's login-attempt tracking treats like a failed
        login (``process_wrong_login``), spamming "Login attempt failed"
        notifications and eventually IP-banning the viewer (or a reverse
        proxy) when ``ip_ban_enabled`` is on. The same device/network data
        is already visible to any authenticated user through entity states,
        so there is nothing gained by restricting it here.
        """
        try:
            coordinator = get_coordinator(self.hass)
            if coordinator is None:
                return self.json(
                    {"error": "No ZigSight coordinator found"},
                    status_code=404,
                )

            topology = build_topology(
                coordinator.get_all_devices(),
                links=coordinator.get_network_links(),
                coordinator_id=coordinator.coordinator_ieee,
                map_nodes=coordinator.get_network_nodes(),
            )
            topology["network_map"] = {
                "supported": coordinator.network_map_supported,
                "updated": _iso(coordinator.network_map_updated),
                "requested": _iso(coordinator.network_map_requested),
                "pending": coordinator.network_map_pending,
            }
            topology["network"] = coordinator.get_network_info()
            return self.json(topology)

        except Exception as err:
            _LOGGER.error("Error generating topology: %s", err, exc_info=True)
            return self.json(
                {"error": "Failed to generate topology"},
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

    @require_admin
    async def get(self, request: web.Request) -> web.Response:
        """Handle GET request for devices data (admin only)."""
        try:
            coordinator = get_coordinator(self.hass)
            if coordinator is None:
                return self.json(
                    {"error": "No ZigSight coordinator found"},
                    status_code=404,
                )

            # Get all devices
            devices = coordinator.get_all_devices()

            # Convert to list format for frontend
            devices_list = []
            for device_id, device_data in devices.items():
                # Skip bridge device
                if device_id == "bridge":
                    continue
                devices_list.append(device_data)

            return self.json({"devices": devices_list})

        except Exception as err:
            _LOGGER.error("Error fetching devices: %s", err, exc_info=True)
            return self.json(
                {"error": "Failed to fetch devices"},
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

    @require_admin
    async def get(self, request: web.Request) -> web.Response:
        """Handle GET request for analytics overview data (admin only)."""
        try:
            coordinator = get_coordinator(self.hass)
            if coordinator is None:
                return self.json(
                    {"error": "No ZigSight coordinator found"},
                    status_code=404,
                )

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
            avg_health_score = (
                sum(health_scores) / len(health_scores) if health_scores else 0
            )

            # Count devices with warnings
            devices_with_warnings = sum(
                1
                for d in device_list
                if d.get("analytics_metrics", {}).get("battery_drain_warning")
                or d.get("analytics_metrics", {}).get("connectivity_warning")
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
                "excellent (200-255)": sum(
                    1 for lq in link_qualities if 200 <= lq <= 255
                ),
            }

            overview = {
                "total_devices": total_devices,
                "average_health_score": round(avg_health_score, 1),
                "devices_with_warnings": devices_with_warnings,
                "battery_distribution": battery_distribution,
                "link_quality_distribution": link_quality_distribution,
                "devices_by_type": {
                    "coordinator": sum(
                        1
                        for d in device_list
                        if d.get("metrics", {}).get("type") == "coordinator"
                    ),
                    "router": sum(
                        1
                        for d in device_list
                        if d.get("metrics", {}).get("type") == "router"
                    ),
                    "end_device": sum(
                        1
                        for d in device_list
                        if d.get("metrics", {}).get("type") == "end_device"
                    ),
                },
            }

            return self.json(overview)

        except Exception as err:
            _LOGGER.error("Error generating analytics overview: %s", err, exc_info=True)
            return self.json(
                {"error": "Failed to generate analytics overview"},
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

    @require_admin
    async def get(self, request: web.Request) -> web.Response:
        """Handle GET request for analytics trends data (admin only)."""
        try:
            # Get query parameters
            device_id = request.query.get("device_id")
            metric = request.query.get("metric", "health_score")
            hours_param = request.query.get("hours", "24")
            try:
                hours = int(hours_param)
            except (ValueError, TypeError):
                return self.json(
                    {"error": f"Invalid 'hours' parameter: {hours_param!r}"},
                    status_code=400,
                )
            if hours < 1 or hours > 720:  # Max 30 days
                return self.json(
                    {"error": "'hours' must be between 1 and 720"},
                    status_code=400,
                )
            if metric not in VALID_TREND_METRICS:
                return self.json(
                    {
                        "error": (
                            f"Invalid 'metric' parameter: {metric!r}. Must be "
                            f"one of {sorted(VALID_TREND_METRICS)}"
                        )
                    },
                    status_code=400,
                )

            coordinator = get_coordinator(self.hass)
            if coordinator is None:
                return self.json(
                    {"error": "No ZigSight coordinator found"},
                    status_code=404,
                )

            if device_id:
                # Get trends for specific device
                device_history = coordinator.get_device_history(device_id)

                # Filter history by time window
                cutoff_time = dt_util.utcnow() - timedelta(hours=hours)
                filtered_history = []
                for entry in device_history:
                    try:
                        timestamp_str = entry.get("timestamp", "")
                        if timestamp_str:
                            timestamp = dt_util.parse_datetime(timestamp_str)
                            if timestamp is None:
                                continue
                            if timestamp.tzinfo is None:
                                timestamp = dt_util.as_utc(timestamp)
                            if timestamp > cutoff_time:
                                filtered_history.append(entry)
                    except (ValueError, TypeError):
                        # Skip entries with invalid timestamps
                        continue

                # Extract metric data
                trends = []
                for entry in filtered_history:
                    entry_timestamp = entry.get("timestamp")
                    metrics = entry.get("metrics", {})

                    if metric == "health_score":
                        # Health score needs to be computed
                        device = coordinator.get_device(device_id)
                        if device:
                            value = device.get("analytics_metrics", {}).get(
                                "health_score"
                            )
                    elif metric == "battery":
                        value = metrics.get("battery")
                    elif metric == "link_quality":
                        value = metrics.get("link_quality")
                    elif metric == "reconnect_rate":
                        device = coordinator.get_device(device_id)
                        value = (
                            device.get("analytics_metrics", {}).get("reconnect_rate")
                            if device
                            else None
                        )
                    else:
                        value = None

                    if value is not None:
                        trends.append(
                            {
                                "timestamp": entry_timestamp,
                                "value": value,
                            }
                        )

                return self.json(
                    {
                        "device_id": device_id,
                        "metric": metric,
                        "hours": hours,
                        "data": trends,
                    }
                )
            else:
                # Get network-wide trends
                # Calculate aggregate metrics over time
                # For now, return current aggregates
                # TODO: Implement time-series aggregation

                return self.json(
                    {
                        "metric": metric,
                        "hours": hours,
                        "data": [],
                        "message": "Network-wide trends require time-series aggregation (not yet implemented)",
                    }
                )

        except Exception as err:
            _LOGGER.error("Error generating analytics trends: %s", err, exc_info=True)
            return self.json(
                {"error": "Failed to generate analytics trends"},
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

    @require_admin
    async def get(self, request: web.Request) -> web.Response:
        """Handle GET request for analytics export (admin only)."""
        try:
            # Get query parameters
            export_format = request.query.get("format", "json").lower()
            if export_format not in VALID_EXPORT_FORMATS:
                return self.json(
                    {
                        "error": (
                            f"Invalid 'format' parameter: {export_format!r}. "
                            f"Must be one of {sorted(VALID_EXPORT_FORMATS)}"
                        )
                    },
                    status_code=400,
                )
            devices_param = request.query.get("devices", "")
            device_ids = (
                [d.strip() for d in devices_param.split(",") if d.strip()]
                if devices_param
                else None
            )
            if device_ids is not None and not device_ids:
                return self.json(
                    {"error": "'devices' parameter did not contain any device id"},
                    status_code=400,
                )

            coordinator = get_coordinator(self.hass)
            if coordinator is None:
                return self.json(
                    {"error": "No ZigSight coordinator found"},
                    status_code=404,
                )

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

                export_data.append(
                    {
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
                    }
                )

            if export_format == "csv":
                # Convert to CSV, escaping values that would otherwise be
                # interpreted as spreadsheet formulas when the file is
                # opened in Excel/LibreOffice/Google Sheets (CSV formula
                # injection).
                output = io.StringIO()
                if export_data:
                    escaped_rows = [
                        {key: _csv_safe(value) for key, value in row.items()}
                        for row in export_data
                    ]
                    writer = csv.DictWriter(output, fieldnames=export_data[0].keys())
                    writer.writeheader()
                    writer.writerows(escaped_rows)

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
                {"error": "Failed to export analytics"},
                status_code=500,
            )


class ZigSightNetworkMapRequestView(HomeAssistantView):
    """Ask Zigbee2MQTT for a fresh raw network map (admin only)."""

    url = "/api/zigsight/topology/networkmap"
    name = "api:zigsight:topology:networkmap"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the network map request view."""
        self.hass = hass

    @require_admin
    async def post(self, request: web.Request) -> web.Response:
        """Publish a raw network map request.

        The scan runs asynchronously in Zigbee2MQTT (it can take a minute or
        more on large networks and generates Zigbee traffic); the result is
        served by the topology endpoint once it arrives.
        """
        coordinator = get_coordinator(self.hass)
        if coordinator is None:
            return self.json(
                {"error": "No ZigSight coordinator found"}, status_code=404
            )
        if not coordinator.network_map_supported:
            return self.json(
                {"error": "Network maps are only available with Zigbee2MQTT"},
                status_code=400,
            )
        if coordinator.network_map_pending:
            # A scan is already running: don't load the mesh again.
            return self.json(
                {
                    "requested": True,
                    "pending": True,
                    "requested_at": _iso(coordinator.network_map_requested),
                },
                status_code=202,
            )
        try:
            await coordinator.async_request_network_map()
        except HomeAssistantError as err:
            _LOGGER.error("Could not request a network map: %s", err)
            return self.json(
                {"error": "Failed to request a network map"}, status_code=500
            )
        return self.json(
            {
                "requested": True,
                "pending": False,
                "requested_at": _iso(coordinator.network_map_requested),
            },
            status_code=202,
        )


class ZigSightChannelRecommendationView(HomeAssistantView):
    """View to serve channel recommendation data."""

    url = "/api/zigsight/channel-recommendation"
    name = "api:zigsight:channel-recommendation"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the channel recommendation view."""
        self.hass = hass

    @require_admin
    async def get(self, request: web.Request) -> web.Response:
        """Return the current Zigbee channel and the last recommendation.

        Admin only, for consistency with the rest of the (admin-only) panel
        data; the POST below is admin-only regardless since ``host_scan``
        mode runs subprocesses on the Home Assistant host.
        """
        coordinator = get_coordinator(self.hass)
        response: dict[str, Any] = {
            "current_channel": _current_channel(coordinator),
            "network": coordinator.get_network_info() if coordinator else None,
        }
        last_recommendation = self.hass.data.get(DOMAIN, {}).get("last_recommendation")
        if not last_recommendation:
            response.update(
                {
                    "has_recommendation": False,
                    "message": (
                        "No channel recommendation available yet. Enter Wi-Fi "
                        "scan data in the ZigSight panel or call the "
                        "'zigsight.recommend_channel' service."
                    ),
                }
            )
            return self.json(response)

        response.update(
            {
                "has_recommendation": True,
                "recommended_channel": last_recommendation.get("recommended_channel"),
                "scores": last_recommendation.get("scores", {}),
                "explanation": last_recommendation.get("explanation", ""),
                "timestamp": last_recommendation.get("timestamp"),
            }
        )
        return self.json(response)

    @require_admin
    async def post(self, request: web.Request) -> web.Response:
        """Compute a channel recommendation from Wi-Fi scan data (admin only).

        ``host_scan`` runs a Wi-Fi scan on the Home Assistant host, hence the
        admin requirement.
        """
        try:
            body = await request.json()
        except ValueError:
            return self.json({"error": "Invalid JSON body"}, status_code=400)
        try:
            data = CHANNEL_RECOMMENDATION_SCHEMA(body)
        except vol.Invalid as err:
            return self.json(
                {"error": f"Invalid request: {humanize_error(body, err)}"},
                status_code=400,
            )
        mode = data["mode"]
        wifi_scan_data = data.get("wifi_scan_data")

        try:
            outcome = await async_generate_channel_recommendation(
                self.hass, mode, wifi_scan_data
            )
        except ValueError as err:
            return self.json({"error": str(err)}, status_code=400)
        except ChannelRecommendationError as err:
            return self.json({"error": str(err)}, status_code=500)

        return self.json(
            {
                "has_recommendation": True,
                "recommended_channel": outcome["recommended_channel"],
                "current_channel": _current_channel(get_coordinator(self.hass)),
                "scores": outcome["scores"],
                "explanation": outcome["explanation"],
                "wifi_aps": outcome["wifi_aps"],
                "timestamp": outcome["timestamp"],
            }
        )


class ZigSightRecommendationHistoryView(HomeAssistantView):
    """View to serve recommendation history."""

    url = "/api/zigsight/recommendation-history"
    name = "api:zigsight:recommendation-history"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the recommendation history view."""
        self.hass = hass

    @require_admin
    async def get(self, request: web.Request) -> web.Response:
        """Handle GET request for recommendation history (admin only)."""
        history = self.hass.data.get(DOMAIN, {}).get("recommendation_history", [])
        return self.json({"history": history, "count": len(history)})


def setup_api_views(hass: HomeAssistant) -> None:
    """Register the ZigSight API views (once per Home Assistant run).

    aiohttp routes can't be removed, so reloading the config entry must not
    register them again; the views look the coordinator up on every request.
    """
    if hass.data.get(DATA_API_VIEWS_REGISTERED):
        return
    hass.data[DATA_API_VIEWS_REGISTERED] = True
    for view in (
        ZigSightTopologyView,
        ZigSightNetworkMapRequestView,
        ZigSightDevicesView,
        ZigSightAnalyticsOverviewView,
        ZigSightAnalyticsTrendsView,
        ZigSightAnalyticsExportView,
        ZigSightChannelRecommendationView,
        ZigSightRecommendationHistoryView,
    ):
        hass.http.register_view(view(hass))
    _LOGGER.debug("ZigSight API views registered")
