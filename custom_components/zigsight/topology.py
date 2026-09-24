"""Network topology builder for ZigSight.

Nodes are keyed by IEEE address and labelled with the friendly name. Edges
come from a Zigbee2MQTT raw network map when one is available (real
neighbour links with their LQI). Without a network map (none requested yet,
or ZHA), every device is linked to the coordinator and the edges are marked
``inferred``: they only say "this device is part of the network", not how it
is actually routed.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from typing import Any

from .const import (
    DEVICE_SOURCE_UNKNOWN,
    DEVICE_TYPE_COORDINATOR,
    DEVICE_TYPE_END_DEVICE,
    DEVICE_TYPE_ROUTER,
)

_LOGGER = logging.getLogger(__name__)

NODE_TYPE_COORDINATOR = "coordinator"
NODE_TYPE_ROUTER = "router"
NODE_TYPE_END_DEVICE = "end_device"
NODE_TYPE_UNKNOWN = "unknown"

_NODE_TYPES = {
    DEVICE_TYPE_COORDINATOR: NODE_TYPE_COORDINATOR,
    DEVICE_TYPE_ROUTER: NODE_TYPE_ROUTER,
    DEVICE_TYPE_END_DEVICE: NODE_TYPE_END_DEVICE,
}

# Where the edges of a topology come from.
LINKS_SOURCE_NETWORK_MAP = "networkmap"
LINKS_SOURCE_INFERRED = "inferred"

# Zigbee neighbour table relationship of ``source`` to ``target``.
_RELATIONSHIP_PARENT = 0
_RELATIONSHIP_CHILD = 1
_RELATIONSHIP_NAMES = {
    0: "parent",
    1: "child",
    2: "sibling",
    3: "none",
    4: "previous_child",
}

DEFAULT_COORDINATOR_ID = "coordinator"


def node_type(raw_type: Any) -> str:
    """Map a Zigbee2MQTT device type to a topology node type."""
    return _NODE_TYPES.get(str(raw_type), NODE_TYPE_UNKNOWN)


def _device_node(device_id: str, device: Mapping[str, Any]) -> dict[str, Any]:
    metrics = device.get("metrics") or {}
    analytics = device.get("analytics_metrics") or {}
    return {
        "id": device_id,
        "label": device.get("friendly_name") or device_id,
        "type": node_type(device.get("type")),
        "model": device.get("model"),
        "manufacturer": device.get("manufacturer"),
        "available": device.get("available"),
        "link_quality": metrics.get("link_quality"),
        "battery": metrics.get("battery"),
        "last_seen": metrics.get("last_seen"),
        "health_score": analytics.get("health_score"),
        "source": device.get("source", DEVICE_SOURCE_UNKNOWN),
        "analytics": {
            "reconnect_rate": analytics.get("reconnect_rate"),
            "battery_trend": analytics.get("battery_trend"),
            "battery_drain_warning": analytics.get("battery_drain_warning"),
            "connectivity_warning": analytics.get("connectivity_warning"),
        },
    }


def _extra_node(
    node_id: str, label: str, kind: str, source: str = DEVICE_SOURCE_UNKNOWN
) -> dict[str, Any]:
    return {
        "id": node_id,
        "label": label,
        "type": kind,
        "model": None,
        "manufacturer": None,
        "available": None,
        "link_quality": None,
        "battery": None,
        "last_seen": None,
        "health_score": None,
        "source": source,
        "analytics": {},
    }


def _map_edges(
    links: Iterable[Mapping[str, Any]], node_ids: set[str]
) -> list[dict[str, Any]]:
    """Turn raw network map links into one edge per pair of devices.

    A raw map usually reports a pair twice (each router lists the other in
    its neighbour table), with a different LQI for each direction. The edge
    keeps the best LQI and is oriented parent -> child when the relationship
    is known.
    """
    edges: dict[frozenset[str], dict[str, Any]] = {}
    for link in links:
        source = link.get("source")
        target = link.get("target")
        if not source or not target or source == target:
            continue
        if source not in node_ids or target not in node_ids:
            # Stale map (device removed since) or unknown device.
            continue
        relationship = link.get("relationship")
        if not isinstance(relationship, int):
            relationship = None
        lqi = link.get("lqi")
        # ``target`` listed ``source`` in its neighbour table.
        if relationship == _RELATIONSHIP_PARENT:
            from_id, to_id = source, target
        else:
            from_id, to_id = target, source
        key = frozenset((source, target))
        edge = edges.get(key)
        if edge is None:
            edges[key] = {
                "from": from_id,
                "to": to_id,
                "link_quality": lqi,
                "relationship": (
                    _RELATIONSHIP_NAMES.get(relationship)
                    if relationship is not None
                    else None
                ),
                "depth": link.get("depth"),
                "inferred": False,
            }
            continue
        if lqi is not None and (
            edge["link_quality"] is None or lqi > edge["link_quality"]
        ):
            edge["link_quality"] = lqi
        if relationship in (_RELATIONSHIP_PARENT, _RELATIONSHIP_CHILD) and edge[
            "relationship"
        ] not in ("parent", "child"):
            edge.update(
                {
                    "from": from_id,
                    "to": to_id,
                    "relationship": _RELATIONSHIP_NAMES[relationship],
                }
            )
    return list(edges.values())


def build_topology(
    devices: Mapping[str, Mapping[str, Any]],
    links: Iterable[Mapping[str, Any]] | None = None,
    coordinator_id: str | None = None,
    map_nodes: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the network topology of the tracked devices.

    Args:
        devices: IEEE -> device record (``ZigSightCoordinator.get_all_devices``).
        links: Links of a Zigbee2MQTT raw network map (``{"source", "target",
            "lqi", "depth", "relationship"}``, see
            ``ZigSightCoordinator.get_network_links``). ``target`` is the
            device whose neighbour table listed ``source``.
        coordinator_id: IEEE address of the Zigbee coordinator, if known.
        map_nodes: Nodes of the same network map; used to label devices the
            map knows but ZigSight doesn't track (e.g. the coordinator).

    Returns:
        ``{"nodes", "edges", "links_source", ...counts}``.
    """
    nodes: list[dict[str, Any]] = []
    for device_id, device in devices.items():
        if device_id == "bridge":  # legacy pseudo device
            continue
        nodes.append(_device_node(device_id, device))

    map_node_list = list(map_nodes or [])
    if coordinator_id is None:
        coordinator_id = next(
            (
                n.get("ieee_address")
                for n in map_node_list
                if n.get("type") == DEVICE_TYPE_COORDINATOR
            ),
            None,
        )
    coordinator_node_id = coordinator_id or DEFAULT_COORDINATOR_ID
    known = {node["id"] for node in nodes}
    coordinator = next((n for n in nodes if n["type"] == NODE_TYPE_COORDINATOR), None)
    if coordinator is None:
        coordinator = _extra_node(
            coordinator_node_id, "Coordinator", NODE_TYPE_COORDINATOR
        )
        nodes.insert(0, coordinator)
        known.add(coordinator_node_id)
    coordinator_node_id = coordinator["id"]

    link_list = list(links or [])
    if link_list:
        # Devices the map knows but ZigSight doesn't track (yet).
        for map_node in map_node_list:
            ieee = map_node.get("ieee_address")
            if not ieee or ieee in known:
                continue
            nodes.append(
                _extra_node(
                    ieee,
                    map_node.get("friendly_name") or ieee,
                    node_type(map_node.get("type")),
                )
            )
            known.add(ieee)
        edges = _map_edges(link_list, known)
    else:
        edges = []

    if edges:
        links_source = LINKS_SOURCE_NETWORK_MAP
    else:
        links_source = LINKS_SOURCE_INFERRED
        edges = [
            {
                "from": coordinator_node_id,
                "to": node["id"],
                "link_quality": node["link_quality"],
                "relationship": None,
                "depth": None,
                "inferred": True,
            }
            for node in nodes
            if node["id"] != coordinator_node_id
        ]

    topology = {
        "nodes": nodes,
        "edges": edges,
        "links_source": links_source,
        "coordinator_id": coordinator_node_id,
        "device_count": len(nodes),
        "coordinator_count": sum(
            1 for n in nodes if n["type"] == NODE_TYPE_COORDINATOR
        ),
        "router_count": sum(1 for n in nodes if n["type"] == NODE_TYPE_ROUTER),
        "end_device_count": sum(1 for n in nodes if n["type"] == NODE_TYPE_END_DEVICE),
        "unknown_count": sum(1 for n in nodes if n["type"] == NODE_TYPE_UNKNOWN),
    }

    _LOGGER.debug(
        "Built topology with %d nodes and %d %s edges",
        len(nodes),
        len(edges),
        links_source,
    )
    return topology
