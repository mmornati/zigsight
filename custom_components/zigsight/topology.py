"""Network topology builder for ZigSight."""

from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)


def build_topology(devices: dict[str, Any]) -> dict[str, Any]:
    """Build network topology from device data.

    Args:
        devices: Dictionary of device_id -> device_data from coordinator

    Returns:
        Dictionary containing nodes and edges for topology visualization
    """
    nodes = []
    edges = []

    # Process each device to build nodes and edges
    for device_id, device_data in devices.items():
        # Skip bridge device - it's handled separately as coordinator
        if device_id == "bridge":
            continue

        # Extract device information
        metrics = device_data.get("metrics", {})
        analytics_metrics = device_data.get("analytics_metrics", {})
        last_message = metrics.get("last_message", {})

        # Determine node type based on device data
        # Check if device is a router (can route for other devices)
        node_type = last_message.get("type", "end_device")
        if node_type == "Router":
            node_type = "router"
        elif node_type == "Coordinator":
            node_type = "coordinator"
        else:
            node_type = "end_device"

        # Build node data
        node = {
            "id": device_id,
            "label": device_data.get("friendly_name", device_id),
            "type": node_type,
            "link_quality": metrics.get("link_quality"),
            "battery": metrics.get("battery"),
            "last_seen": metrics.get("last_seen"),
            "health_score": analytics_metrics.get("health_score"),
            "analytics": {
                "reconnect_rate": analytics_metrics.get("reconnect_rate"),
                "battery_trend": analytics_metrics.get("battery_trend"),
                "battery_drain_warning": analytics_metrics.get("battery_drain_warning"),
                "connectivity_warning": analytics_metrics.get("connectivity_warning"),
            },
        }
        nodes.append(node)

        # Extract parent relationship for building edges
        # Zigbee2MQTT provides routing information in device messages
        parent_ieee = last_message.get("parent_ieee")
        if parent_ieee:
            # Create edge from parent to this device
            edges.append(
                {
                    "from": parent_ieee,
                    "to": device_id,
                    "link_quality": metrics.get("link_quality", 0),
                }
            )

    # Add coordinator node if not already present
    coordinator_found = any(node["type"] == "coordinator" for node in nodes)
    if not coordinator_found:
        # Add coordinator as root node
        nodes.insert(
            0,
            {
                "id": "coordinator",
                "label": "Coordinator",
                "type": "coordinator",
                "link_quality": 255,
                "battery": None,
                "last_seen": None,
                "health_score": 100.0,
                "analytics": {},
            },
        )

    # Build topology structure
    topology = {
        "nodes": nodes,
        "edges": edges,
        "device_count": len(nodes),
        "coordinator_count": sum(1 for n in nodes if n["type"] == "coordinator"),
        "router_count": sum(1 for n in nodes if n["type"] == "router"),
        "end_device_count": sum(1 for n in nodes if n["type"] == "end_device"),
    }

    _LOGGER.debug(
        "Built topology with %d nodes and %d edges",
        len(nodes),
        len(edges),
    )

    return topology
