"""Manhattan routing on the warehouse graph.

The warehouse is modelled as an undirected weighted graph:

Nodes
-----
- "base":                          AGV start/end point at BASE_CENTER
- "base_exit":                     where base meets the middle cross-aisle (x=BASE_WIDTH, y=middle_y)
- "xa_<name>_<aisle>" intersection: cross-aisle <name> meets picking-aisle <aisle>  (aisle = 1..14)
- "pickup_<id>":                   one node per pickup point

Edges
-----
- base <-> base_exit                                       (BASE_WIDTH/2 metres)
- base_exit <-> xa_middle_1                                (aisle_1_x - BASE_WIDTH metres)
- xa_<name>_k <-> xa_<name>_{k+1}                          (RACK_WIDTH+AISLE_WIDTH metres)
- xa_bottom_k <-> xa_middle_k <-> xa_top_k                 (full picking-aisle segments)
- pickup nodes connect to the two cross-aisle intersection nodes that bound their segment

Each edge also carries a `segment` attribute that names the warehouse Segment
it traverses (one of the seg_ids built in layout.py). This is what lets the
sensor- and route-based scenarios know which lights to control as the AGV
moves through the graph.
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
    """One traversal between two adjacent nodes.

    `segment` names the warehouse Segment the AGV is physically inside while
    making this hop. `length` is in metres.
    """
    from_node: str
    to_node: str
    segment_id: str
    length: float


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------
def build_graph(pickups: List[PickupPoint]) -> nx.Graph:
    g = nx.Graph()

    # Position metadata (for animation / debug)
    g.add_node(NODE_BASE, pos=cfg.BASE_CENTER)
    g.add_node(NODE_BASE_EXIT, pos=(cfg.BASE_WIDTH, CROSS_AISLE_Y["middle"]))

    # Cross-aisle / picking-aisle intersection nodes
    for xa in CROSS_AISLE_NAMES:
        y = CROSS_AISLE_Y[xa]
        for a in range(1, cfg.N_AISLES + 1):
            g.add_node(node_xa(xa, a), pos=(aisle_center_x(a), y))

    # -- Edges --------------------------------------------------------------

    # 1) base <-> base_exit  (inside the base zone)
    g.add_edge(
        NODE_BASE, NODE_BASE_EXIT,
        weight=cfg.BASE_WIDTH / 2,
        segment_id=SEG_ID_BASE,
    )

    # 2) base_exit <-> xa_middle_1  (inside middle cross-aisle, between base
    #    edge and first picking aisle centerline)
    g.add_edge(
        NODE_BASE_EXIT, node_xa("middle", 1),
        weight=aisle_center_x(1) - cfg.BASE_WIDTH,
        # this stretch overlaps the first cross-aisle sub-segment
        segment_id=_seg_id_cross("middle", 1),
    )

    # 3) Cross-aisle horizontal edges between adjacent picking-aisle columns.
    #    The edge from aisle k to aisle k+1 lies inside the column-(k+1)
    #    sub-segment of that cross-aisle (we pick the destination column so
    #    the segment seen when "entering" the next column is consistent).
    step = cfg.RACK_WIDTH + cfg.AISLE_WIDTH
    for xa in CROSS_AISLE_NAMES:
        for a in range(1, cfg.N_AISLES):
            g.add_edge(
                node_xa(xa, a), node_xa(xa, a + 1),
                weight=step,
                segment_id=_seg_id_cross(xa, a + 1),
            )

    # 4) Vertical edges inside picking aisles (between cross-aisle nodes).
    #    bottom-cross to middle-cross  -> aisle bottom segment
    #    middle-cross to top-cross     -> aisle top segment
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

    # 5) Pickup-point nodes. Each pickup connects to BOTH the cross-aisle
    #    nodes that bound its segment, so Dijkstra can pick whichever
    #    approach is shorter.
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
    """Return the list of node ids on the shortest path from src to dst."""
    return nx.shortest_path(graph, src, dst, weight="weight")


def path_to_steps(graph: nx.Graph, path: List[str]) -> List[RouteStep]:
    """Convert a list of node ids into a list of RouteSteps."""
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


def route_base_to_pickup_and_back(
    graph: nx.Graph, pickup_id: int
) -> List[RouteStep]:
    """Full out-and-back route from base to a pickup and back."""
    out = shortest_path(graph, NODE_BASE, node_pickup(pickup_id))
    back = shortest_path(graph, node_pickup(pickup_id), NODE_BASE)
    # Drop the duplicated pickup node when concatenating
    full_path = out + back[1:]
    return path_to_steps(graph, full_path)


def segments_touched(steps: List[RouteStep]) -> List[str]:
    """Return the ordered, de-duplicated list of segment_ids the route visits."""
    seen: List[str] = []
    seen_set = set()
    for s in steps:
        if s.segment_id not in seen_set:
            seen.append(s.segment_id)
            seen_set.add(s.segment_id)
    return seen


if __name__ == "__main__":  # smoke test
    from layout import build_pickup_points

    pks = build_pickup_points()
    g = build_graph(pks)
    print(f"graph: {g.number_of_nodes()} nodes, {g.number_of_edges()} edges")

    # Verify the report's example: base -> aisle 6 bottom segment pickup -> base
    # Report says total inside the rack/aisle area is 67.25 m
    sample_pickup = next(p for p in pks if p.aisle == 6 and p.segment == "bottom")
    steps = route_base_to_pickup_and_back(g, sample_pickup.pickup_id)
    total_distance = sum(s.length for s in steps)
    print(f"route to pickup_{sample_pickup.pickup_id} "
          f"(aisle 6, bottom, y={sample_pickup.y:.2f}): "
          f"total distance = {total_distance:.2f} m, {len(steps)} steps")
    print("segments touched (in order):", segments_touched(steps))
