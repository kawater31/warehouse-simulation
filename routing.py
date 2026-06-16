"""Manhattan routing on an undirected weighted NetworkX graph of the warehouse.

Nodes are the base, the cross-aisle/picking-aisle intersections, and the pickup
points. Each edge carries a weight (distance in metres) and the seg_id of the
Segment it lies in, so the lighting scenarios know which segment an AGV is in.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import networkx as nx

import config as cfg
from layout import (
    CROSS_AISLE_NAMES,
    CROSS_AISLE_Y,
    PickupPoint,
    RACK_SEGMENT_Y_RANGES,
    SEG_ID_BASE,
    _seg_id_cross,
    _seg_id_picking,
    aisle_center_x,
)


# ---------------------------------------------------------------------------
# Node naming
# ---------------------------------------------------------------------------
NODE_BASE = "base"
NODE_BASE_EXIT = "base_exit"


def node_xa(xa_name: str, aisle_idx: int) -> str:
    return f"xa_{xa_name}_{aisle_idx}"


def node_pickup(pickup_id: int) -> str:
    return f"pickup_{pickup_id}"


# ---------------------------------------------------------------------------
# Route step description (consumed by the AGV component)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RouteStep:
    """One hop between two adjacent nodes, inside `segment_id`, `length` metres."""
    from_node: str
    to_node: str
    segment_id: str
    length: float


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------
def build_graph(pickups: List[PickupPoint]) -> nx.Graph:
    g = nx.Graph()

    g.add_node(NODE_BASE, pos=cfg.BASE_CENTER)
    g.add_node(NODE_BASE_EXIT, pos=(cfg.BASE_WIDTH, CROSS_AISLE_Y["middle"]))

    for xa in CROSS_AISLE_NAMES:
        y = CROSS_AISLE_Y[xa]
        for a in range(1, cfg.N_AISLES + 1):
            g.add_node(node_xa(xa, a), pos=(aisle_center_x(a), y))

    # base -> base_exit -> first picking aisle
    g.add_edge(
        NODE_BASE, NODE_BASE_EXIT,
        weight=cfg.BASE_WIDTH / 2,
        segment_id=SEG_ID_BASE,
    )
    g.add_edge(
        NODE_BASE_EXIT, node_xa("middle", 1),
        weight=aisle_center_x(1) - cfg.BASE_WIDTH,
        segment_id=_seg_id_cross("middle", 1),
    )

    # horizontal cross-aisle edges (edge into column k+1 belongs to that column)
    step = cfg.RACK_WIDTH + cfg.AISLE_WIDTH
    for xa in CROSS_AISLE_NAMES:
        for a in range(1, cfg.N_AISLES):
            g.add_edge(
                node_xa(xa, a), node_xa(xa, a + 1),
                weight=step,
                segment_id=_seg_id_cross(xa, a + 1),
            )

    # vertical picking-aisle edges
    for a in range(1, cfg.N_AISLES + 1):
        g.add_edge(
            node_xa("bottom", a), node_xa("middle", a),
            weight=CROSS_AISLE_Y["middle"] - CROSS_AISLE_Y["bottom"],
            segment_id=_seg_id_picking(a, "bottom"),
        )
        g.add_edge(
            node_xa("middle", a), node_xa("top", a),
            weight=CROSS_AISLE_Y["top"] - CROSS_AISLE_Y["middle"],
            segment_id=_seg_id_picking(a, "top"),
        )

    # pickup nodes connect to both bounding cross-aisle nodes
    for p in pickups:
        node_p = node_pickup(p.pickup_id)
        g.add_node(node_p, pos=(p.x, p.y))
        seg_id = _seg_id_picking(p.aisle, p.segment)
        if p.segment == "bottom":
            g.add_edge(node_p, node_xa("bottom", p.aisle),
                       weight=p.y - CROSS_AISLE_Y["bottom"],
                       segment_id=seg_id)
            g.add_edge(node_p, node_xa("middle", p.aisle),
                       weight=CROSS_AISLE_Y["middle"] - p.y,
                       segment_id=seg_id)
        else:  # top
            g.add_edge(node_p, node_xa("middle", p.aisle),
                       weight=p.y - CROSS_AISLE_Y["middle"],
                       segment_id=seg_id)
            g.add_edge(node_p, node_xa("top", p.aisle),
                       weight=CROSS_AISLE_Y["top"] - p.y,
                       segment_id=seg_id)

    return g


# ---------------------------------------------------------------------------
# Route computation
# ---------------------------------------------------------------------------
def shortest_path(graph: nx.Graph, src: str, dst: str) -> List[str]:
    return nx.shortest_path(graph, src, dst, weight="weight")


def path_to_steps(graph: nx.Graph, path: List[str]) -> List[RouteStep]:
    steps: List[RouteStep] = []
    for u, v in zip(path[:-1], path[1:]):
        data = graph.edges[u, v]
        steps.append(
            RouteStep(
                from_node=u,
                to_node=v,
                segment_id=data["segment_id"],
                length=data["weight"],
            )
        )
    return steps


def segments_touched(steps: List[RouteStep]) -> List[str]:
    """Ordered, de-duplicated list of segment_ids the route visits."""
    seen: List[str] = []
    seen_set = set()
    for s in steps:
        if s.segment_id not in seen_set:
            seen.append(s.segment_id)
            seen_set.add(s.segment_id)
    return seen
