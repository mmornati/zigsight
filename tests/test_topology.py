"""Tests for ZigSight topology builder."""

from __future__ import annotations

import pytest

from custom_components.zigsight.topology import build_topology


def test_build_topology_empty_devices() -> None:
    """Test topology building with empty device list."""
    devices = {}
    topology = build_topology(devices)

    assert topology is not None
    assert "nodes" in topology
    assert "edges" in topology
    assert len(topology["nodes"]) == 1  # Coordinator should be added
    assert topology["nodes"][0]["type"] == "coordinator"
    assert topology["device_count"] == 1
    assert topology["coordinator_count"] == 1
    assert topology["router_count"] == 0
    assert topology["end_device_count"] == 0


def test_build_topology_with_coordinator() -> None:
    """Test topology building with explicit coordinator."""
    devices = {
        "bridge": {
            "state": "online",
        }
    }
    topology = build_topology(devices)

    assert topology is not None
    assert len(topology["nodes"]) == 1  # Coordinator added automatically
    assert topology["coordinator_count"] == 1


def test_build_topology_with_end_devices() -> None:
    """Test topology building with end devices."""
    devices = {
        "device1": {
            "friendly_name": "Living Room Sensor",
            "metrics": {
                "link_quality": 150,
                "battery": 80,
                "last_seen": "2024-01-01T12:00:00Z",
                "last_message": {
                    "type": "EndDevice",
                },
            },
            "analytics_metrics": {
                "health_score": 85.0,
                "reconnect_rate": 0.5,
            },
        },
        "device2": {
            "friendly_name": "Bedroom Sensor",
            "metrics": {
                "link_quality": 200,
                "battery": 90,
                "last_seen": "2024-01-01T12:05:00Z",
                "last_message": {
                    "type": "EndDevice",
                },
            },
            "analytics_metrics": {
                "health_score": 95.0,
            },
        },
    }

    topology = build_topology(devices)

    assert topology is not None
    assert len(topology["nodes"]) == 3  # 2 devices + coordinator
    assert topology["device_count"] == 3
    assert topology["end_device_count"] == 2

    # Check device nodes
    device_nodes = [n for n in topology["nodes"] if n["type"] == "end_device"]
    assert len(device_nodes) == 2

    device1_node = next((n for n in device_nodes if n["id"] == "device1"), None)
    assert device1_node is not None
    assert device1_node["label"] == "Living Room Sensor"
    assert device1_node["link_quality"] == 150
    assert device1_node["battery"] == 80
    assert device1_node["health_score"] == 85.0


def test_build_topology_with_routers() -> None:
    """Test topology building with router devices."""
    devices = {
        "router1": {
            "friendly_name": "Router 1",
            "metrics": {
                "link_quality": 255,
                "last_seen": "2024-01-01T12:00:00Z",
                "last_message": {
                    "type": "Router",
                },
            },
            "analytics_metrics": {
                "health_score": 98.0,
            },
        },
    }

    topology = build_topology(devices)

    assert topology is not None
    assert len(topology["nodes"]) == 2  # Router + coordinator
    assert topology["router_count"] == 1

    router_node = next((n for n in topology["nodes"] if n["id"] == "router1"), None)
    assert router_node is not None
    assert router_node["type"] == "router"
    assert router_node["label"] == "Router 1"


def test_build_topology_with_edges() -> None:
    """Test topology building with parent-child relationships."""
    devices = {
        "router1": {
            "friendly_name": "Router 1",
            "metrics": {
                "link_quality": 255,
                "last_message": {
                    "type": "Router",
                    "parent_ieee": "coordinator",
                },
            },
            "analytics_metrics": {},
        },
        "device1": {
            "friendly_name": "Device 1",
            "metrics": {
                "link_quality": 150,
                "last_message": {
                    "type": "EndDevice",
                    "parent_ieee": "router1",
                },
            },
            "analytics_metrics": {},
        },
    }

    topology = build_topology(devices)

    assert topology is not None
    assert len(topology["edges"]) == 2

    # Check edge from coordinator to router
    coordinator_edge = next(
        (e for e in topology["edges"] if e["from"] == "coordinator"), None
    )
    assert coordinator_edge is not None
    assert coordinator_edge["to"] == "router1"

    # Check edge from router to device
    router_edge = next((e for e in topology["edges"] if e["from"] == "router1"), None)
    assert router_edge is not None
    assert router_edge["to"] == "device1"
    assert router_edge["link_quality"] == 150


def test_build_topology_mixed_devices() -> None:
    """Test topology building with mixed device types."""
    devices = {
        "router1": {
            "friendly_name": "Router 1",
            "metrics": {
                "link_quality": 255,
                "last_message": {"type": "Router"},
            },
            "analytics_metrics": {},
        },
        "router2": {
            "friendly_name": "Router 2",
            "metrics": {
                "link_quality": 240,
                "last_message": {"type": "Router"},
            },
            "analytics_metrics": {},
        },
        "device1": {
            "friendly_name": "Device 1",
            "metrics": {
                "link_quality": 150,
                "last_message": {"type": "EndDevice"},
            },
            "analytics_metrics": {},
        },
        "device2": {
            "friendly_name": "Device 2",
            "metrics": {
                "link_quality": 180,
                "last_message": {"type": "EndDevice"},
            },
            "analytics_metrics": {},
        },
    }

    topology = build_topology(devices)

    assert topology is not None
    assert topology["device_count"] == 5  # 2 routers + 2 devices + coordinator
    assert topology["coordinator_count"] == 1
    assert topology["router_count"] == 2
    assert topology["end_device_count"] == 2


def test_build_topology_with_warnings() -> None:
    """Test topology building with devices having warnings."""
    devices = {
        "device1": {
            "friendly_name": "Problem Device",
            "metrics": {
                "link_quality": 50,
                "battery": 10,
                "last_message": {"type": "EndDevice"},
            },
            "analytics_metrics": {
                "health_score": 30.0,
                "battery_drain_warning": True,
                "connectivity_warning": True,
            },
        },
    }

    topology = build_topology(devices)

    assert topology is not None
    device_node = next((n for n in topology["nodes"] if n["id"] == "device1"), None)
    assert device_node is not None
    assert device_node["analytics"]["battery_drain_warning"] is True
    assert device_node["analytics"]["connectivity_warning"] is True


def test_build_topology_with_missing_metrics() -> None:
    """Test topology building with devices missing metrics."""
    devices = {
        "device1": {
            "friendly_name": "Device 1",
            "metrics": {},
            "analytics_metrics": {},
        },
    }

    topology = build_topology(devices)

    assert topology is not None
    device_node = next((n for n in topology["nodes"] if n["id"] == "device1"), None)
    assert device_node is not None
    assert device_node["link_quality"] is None
    assert device_node["battery"] is None
    assert device_node["health_score"] is None
