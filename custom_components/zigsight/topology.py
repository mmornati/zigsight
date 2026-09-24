"""Network topology builder for ZigSight."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from typing import Any

from .const import DEVICE_SOURCE_UNKNOWN

_LOGGER = logging.getLogger(__name__)

_NODE_TYPES = {
    "Router": "router",
    "Coordinator": "coordinator",
    "EndDevice": "end_device",
}


def _node_type(device_data: Mapping[str, Any]) -> str:
    """Return the topology node type of a device record.

    Zigbee2MQTT records carry the real device type from bridge/devices; the
    ``last_message.type`` fallback keeps older record shapes working.
    """
    raw_type = device_data.get("type")
    if not raw_type:
        metrics = device_data.get("metrics") or {}
        raw_type = (metrics.get("last_message") or {}).get("type")
    return _NODE_TYPES.get(str(raw_type), "end_device")


def build_topology(
    devices: dict[str, Any],
    links: Iterable[Mapping[str, Any]] | None = None,
    coordinator_id: str | None = None,
) -> dict[str, Any]:
    """Build network topology from device data.

    Args:
        devices: Dictionary of device_id -> device_data from coordinator
        links: Optional links from a Zigbee2MQTT raw network map
            (``{"source", "target", "lqi", "depth", "relationship"}``, as
            returned by ``ZigSightCoordinator.get_network_links``). The
            ``target`` is the device whose neighbour table listed ``source``.
        coordinator_id: IEEE address of the Zigbee coordinator, if known

    Returns:
        Dictionary containing nodes and edges for topology visualization
    """
    nodes = []
    edges = []

    for device_id, device_data in devices.items():
        # Skip legacy bridge pseudo-device
        if device_id == "bridge":
            continue

        metrics = device_data.get("metrics", {})
        analytics_metrics = device_data.get("analytics_metrics", {})
        last_message = metrics.get("last_message", {})
        node_type = _node_type(device_data)

        node = {
            "id": device_id,
            "label": device_data.get("friendly_name", device_id),
            "type": node_type,
            "link_quality": metrics.get("link_quality"),
            "battery": metrics.get("battery"),
            "last_seen": metrics.get("last_seen"),
            "health_score": analytics_metrics.get("health_score"),
            "source": device_data.get("source", DEVICE_SOURCE_UNKNOWN),
            "analytics": {
                "reconnect_rate": analytics_metrics.get("reconnect_rate"),
                "battery_trend": analytics_metrics.get("battery_trend"),
                "battery_drain_warning": analytics_metrics.get("battery_drain_warning"),
                "connectivity_warning": analytics_metrics.get("connectivity_warning"),
            },
        }
        nodes.append(node)

        # Legacy parent relationship (only present in older record shapes)
        parent_ieee = last_message.get("parent_ieee")
        if parent_ieee and links is None:
            edges.append(
                {
                    "from": parent_ieee,
                    "to": device_id,
                    "link_quality": metrics.get("link_quality", 0),
                }
            )

    for link in links or []:
        source = link.get("source")
        target = link.get("target")
        if not source or not target:
            continue
        edges.append(
            {
                "from": target,
                "to": source,
                "link_quality": link.get("lqi"),
                "relationship": link.get("relationship"),
                "depth": link.get("depth"),
            }
        )

    # Add coordinator node if not already present
    coordinator_found = any(node["type"] == "coordinator" for node in nodes)
    if not coordinator_found:
        nodes.insert(
            0,
            {
                "id": coordinator_id or "coordinator",
                "label": "Coordinator",
                "type": "coordinator",
                "link_quality": 255,
                "battery": None,
                "last_seen": None,
                "health_score": 100.0,
                "analytics": {},
            },
        )

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
