"""Tests for the ZigSight topology builder."""

from __future__ import annotations

from typing import Any

from custom_components.zigsight.topology import build_topology

COORD = "0x00124b0024c1a2b3"
ROUTER = "0xrouter"
ROUTER2 = "0xrouter2"
END = "0xend"


def _devices() -> dict[str, Any]:
    return {
        ROUTER: {
            "friendly_name": "Plug",
            "type": "Router",
            "model": "Smart plug",
            "manufacturer": "IKEA",
            "available": True,
            "source": "zigbee2mqtt",
            "metrics": {"link_quality": 200, "last_seen": "2026-09-24T08:00:00+00:00"},
            "analytics_metrics": {"health_score": 95.0, "reconnect_rate": 0.0},
        },
        ROUTER2: {
            "friendly_name": "Lamp",
            "type": "Router",
            "metrics": {"link_quality": 150},
            "analytics_metrics": {},
        },
        END: {
            "friendly_name": "Sensor",
            "type": "EndDevice",
            "metrics": {"link_quality": 80, "battery": 55},
            "analytics_metrics": {
                "health_score": 40.0,
                "connectivity_warning": True,
            },
        },
    }


def _edges(topology: dict[str, Any]) -> set[tuple[str, str, Any]]:
    return {(e["from"], e["to"], e["link_quality"]) for e in topology["edges"]}


def test_empty_devices_only_coordinator() -> None:
    """Without devices the topology has the coordinator only."""
    topology = build_topology({})

    assert [n["id"] for n in topology["nodes"]] == ["coordinator"]
    assert topology["nodes"][0]["type"] == "coordinator"
    assert topology["edges"] == []
    assert topology["device_count"] == 1
    assert topology["coordinator_count"] == 1
    assert topology["links_source"] == "inferred"


def test_legacy_bridge_record_ignored() -> None:
    """The legacy "bridge" pseudo device is not a node."""
    topology = build_topology({"bridge": {"state": "online"}})
    assert [n["id"] for n in topology["nodes"]] == ["coordinator"]


def test_nodes_keyed_by_ieee_with_names_and_types() -> None:
    """Nodes use the IEEE as id, the friendly name as label, real types."""
    topology = build_topology(_devices(), coordinator_id=COORD)

    nodes = {n["id"]: n for n in topology["nodes"]}
    assert set(nodes) == {COORD, ROUTER, ROUTER2, END}
    assert topology["nodes"][0]["id"] == COORD
    assert nodes[COORD]["label"] == "Coordinator"
    assert nodes[ROUTER]["label"] == "Plug"
    assert nodes[ROUTER]["type"] == "router"
    assert nodes[ROUTER]["model"] == "Smart plug"
    assert nodes[ROUTER]["manufacturer"] == "IKEA"
    assert nodes[ROUTER]["available"] is True
    assert nodes[ROUTER]["source"] == "zigbee2mqtt"
    assert nodes[ROUTER]["health_score"] == 95.0
    assert nodes[END]["type"] == "end_device"
    assert nodes[END]["battery"] == 55
    assert nodes[END]["analytics"]["connectivity_warning"] is True
    assert nodes[END]["source"] == "unknown"
    assert topology["router_count"] == 2
    assert topology["end_device_count"] == 1
    assert topology["unknown_count"] == 0


def test_unknown_device_type() -> None:
    """Devices without a known Zigbee type (e.g. ZHA) are "unknown"."""
    topology = build_topology({"0xzha": {"friendly_name": "ZHA plug", "type": None}})
    node = next(n for n in topology["nodes"] if n["id"] == "0xzha")
    assert node["type"] == "unknown"
    assert topology["unknown_count"] == 1


def test_inferred_star_without_network_map() -> None:
    """Without a network map every device hangs off the coordinator."""
    topology = build_topology(_devices(), links=[], coordinator_id=COORD)

    assert topology["links_source"] == "inferred"
    assert topology["coordinator_id"] == COORD
    assert _edges(topology) == {
        (COORD, ROUTER, 200),
        (COORD, ROUTER2, 150),
        (COORD, END, 80),
    }
    assert all(edge["inferred"] for edge in topology["edges"])


def test_network_map_edges_deduplicated_and_oriented() -> None:
    """Map links become one parent -> child edge per pair with the best LQI."""
    links = [
        # ROUTER is a child of the coordinator (listed by the coordinator)
        {"source": ROUTER, "target": COORD, "lqi": 190, "relationship": 1},
        # ... and the coordinator is ROUTER's parent (listed by ROUTER)
        {"source": COORD, "target": ROUTER, "lqi": 210, "relationship": 0},
        # Siblings, reported by both routers
        {"source": ROUTER2, "target": ROUTER, "lqi": 120, "relationship": 2},
        {"source": ROUTER, "target": ROUTER2, "lqi": None, "relationship": 2},
        # END is a child of ROUTER2
        {"source": END, "target": ROUTER2, "lqi": 70, "relationship": 1, "depth": 2},
        # Invalid / stale links are ignored
        {"source": None, "target": ROUTER},
        {"source": ROUTER, "target": ROUTER},
        {"source": "0xgone", "target": ROUTER, "lqi": 50},
    ]
    topology = build_topology(_devices(), links=links, coordinator_id=COORD)

    assert topology["links_source"] == "networkmap"
    assert _edges(topology) == {
        (COORD, ROUTER, 210),
        (ROUTER, ROUTER2, 120),
        (ROUTER2, END, 70),
    }
    by_pair = {(e["from"], e["to"]): e for e in topology["edges"]}
    assert by_pair[(COORD, ROUTER)]["relationship"] == "child"
    assert by_pair[(ROUTER, ROUTER2)]["relationship"] == "sibling"
    assert by_pair[(ROUTER2, END)]["depth"] == 2
    assert not any(edge["inferred"] for edge in topology["edges"])
    node_ids = {n["id"] for n in topology["nodes"]}
    assert all(e["from"] in node_ids and e["to"] in node_ids for e in topology["edges"])


def test_sibling_then_parent_relationship_wins() -> None:
    """A known parent/child relationship overrides a sibling one."""
    links = [
        {"source": ROUTER, "target": ROUTER2, "lqi": 100, "relationship": 2},
        {"source": ROUTER2, "target": ROUTER, "lqi": 90, "relationship": 0},
        {"source": ROUTER, "target": COORD, "lqi": "bad", "relationship": "x"},
    ]
    topology = build_topology(_devices(), links=links, coordinator_id=COORD)
    by_pair = {(e["from"], e["to"]): e for e in topology["edges"]}
    edge = by_pair[(ROUTER2, ROUTER)]
    assert edge["relationship"] == "parent"
    assert edge["link_quality"] == 100
    assert by_pair[(COORD, ROUTER)]["relationship"] is None


def test_network_map_nodes_add_untracked_devices_and_coordinator() -> None:
    """Map nodes label devices ZigSight doesn't track and give the coordinator."""
    map_nodes = [
        {"ieee_address": COORD, "friendly_name": "Coordinator", "type": "Coordinator"},
        {"ieee_address": "0xnew", "friendly_name": "New Router", "type": "Router"},
        {"ieee_address": None},
    ]
    links = [
        {"source": "0xnew", "target": COORD, "lqi": 99, "relationship": 1},
        {"source": ROUTER, "target": COORD, "lqi": 180, "relationship": 1},
    ]
    topology = build_topology(_devices(), links=links, map_nodes=map_nodes)

    nodes = {n["id"]: n for n in topology["nodes"]}
    assert topology["coordinator_id"] == COORD
    assert topology["coordinator_count"] == 1
    assert nodes["0xnew"]["label"] == "New Router"
    assert nodes["0xnew"]["type"] == "router"
    assert (COORD, "0xnew", 99) in _edges(topology)


def test_network_map_without_usable_links_falls_back_to_inferred() -> None:
    """A map whose links reference only unknown devices is not used."""
    links = [{"source": "0xa", "target": "0xb", "lqi": 10}]
    topology = build_topology(_devices(), links=links, coordinator_id=COORD)
    assert topology["links_source"] == "inferred"
    assert len(topology["edges"]) == 3


def test_coordinator_record_is_reused() -> None:
    """A tracked coordinator record is not duplicated."""
    devices = {COORD: {"friendly_name": "My coordinator", "type": "Coordinator"}}
    topology = build_topology(devices, coordinator_id="0xother")
    assert [n["id"] for n in topology["nodes"]] == [COORD]
    assert topology["coordinator_id"] == COORD
