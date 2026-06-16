"""AGV: pulls orders from the shared queue, travels, picks, returns.

`lighting_mode` selects how it drives the SLS: "always_on" not at all,
"sensor_based" via per-segment enter/exit, "route_based" via activate/release
of the whole route.
"""
from __future__ import annotations

from collections import deque
from typing import Deque, Dict, List, Optional

import networkx as nx
import salabim as sim

import config as cfg
from components.order import Order
from components.pickup_location import PickupLocation
from components.sls import SmartLightingSystem
from routing import (
    NODE_BASE,
    RouteStep,
    node_pickup,
    path_to_steps,
    segments_touched,
    shortest_path,
)


class AGV(sim.Component):
    """A single AGV."""

    def setup(  # type: ignore[override]
        self,
        agv_id: int,
        order_queue: Deque[Order],
        graph: nx.Graph,
        pickup_locations: Dict[int, PickupLocation],
        sls_by_seg: Dict[str, SmartLightingSystem],
        lighting_mode: str,
        speed: float = cfg.AGV_SPEED,
    ):
        assert lighting_mode in {"always_on", "sensor_based", "route_based"}
        self.agv_id = agv_id
        self.order_queue = order_queue
        self.graph = graph
        self.pickup_locations = pickup_locations
        self.sls_by_seg = sls_by_seg
        self.lighting_mode = lighting_mode
        self.speed = speed

        self.current_node = NODE_BASE
        self.total_distance_m = 0.0
        self.total_time_travelled_s = 0.0
        self.orders_served: int = 0
        self.x, self.y = self.graph.nodes[NODE_BASE]["pos"]  # animation position

    def _segments_for_route(self, steps: List[RouteStep]) -> List[str]:
        return segments_touched(steps)

    def _activate_route_lights(self, segs: List[str]) -> None:
        for seg in segs:
            sls = self.sls_by_seg.get(seg)
            if sls is not None:
                sls.route_activate(self.agv_id)

    def _release_route_lights(self, segs: List[str]) -> None:
        for seg in segs:
            sls = self.sls_by_seg.get(seg)
            if sls is not None:
                sls.route_release(self.agv_id)

    def _traverse(self, steps: List[RouteStep]):
        """Hold for each step; in sensor mode fire enter/exit on transitions."""
        prev_seg: Optional[str] = None

        for step in steps:
            if self.lighting_mode == "sensor_based":
                if step.segment_id != prev_seg:
                    if prev_seg is not None and prev_seg in self.sls_by_seg:
                        self.sls_by_seg[prev_seg].sensor_exit()
                    if step.segment_id in self.sls_by_seg:
                        self.sls_by_seg[step.segment_id].sensor_enter()

            travel_time = step.length / self.speed
            assert step.length >= 0.0 and travel_time >= 0.0, (
                f"[verify] non-physical step {step.from_node}->{step.to_node}: "
                f"len={step.length}, t={travel_time}"
            )
            yield self.hold(travel_time)

            self.total_distance_m += step.length
            self.total_time_travelled_s += travel_time
            self.current_node = step.to_node
            self.x, self.y = self.graph.nodes[step.to_node]["pos"]

            prev_seg = step.segment_id

        if self.lighting_mode == "sensor_based" and prev_seg is not None:
            if prev_seg in self.sls_by_seg:
                self.sls_by_seg[prev_seg].sensor_exit()

    def process(self):  # type: ignore[override]
        while True:
            while len(self.order_queue) == 0:
                yield self.passivate()

            order: Order = self.order_queue.popleft()
            order.served_by_agv = self.agv_id

            # Build the full out-and-back route once (route mode pre-lights it).
            full_path = [self.current_node]
            running_node = self.current_node
            for pickup_id in order.pickup_ids:
                out = shortest_path(self.graph, running_node, node_pickup(pickup_id))
                full_path.extend(out[1:])
                running_node = node_pickup(pickup_id)
            back = shortest_path(self.graph, running_node, NODE_BASE)
            full_path.extend(back[1:])
            all_steps = path_to_steps(self.graph, full_path)
            full_route_segments_for_lighting = self._segments_for_route(all_steps)

            if self.lighting_mode == "route_based":
                self._activate_route_lights(full_route_segments_for_lighting)

            # Travel to each pickup, do the pickup, then continue.
            running_node = self.current_node
            for pickup_id in order.pickup_ids:
                target_node = node_pickup(pickup_id)
                out_path = shortest_path(self.graph, running_node, target_node)
                out_steps = path_to_steps(self.graph, out_path)
                yield from self._traverse(out_steps)

                # Enter the pickup location's queue and passivate
                pl = self.pickup_locations[pickup_id]
                self.enter(pl.my_queue)
                if pl.ispassive():
                    pl.activate()
                yield self.passivate()  # reactivated by PickupLocation
                running_node = target_node

            # Return to base
            back_path = shortest_path(self.graph, running_node, NODE_BASE)
            back_steps = path_to_steps(self.graph, back_path)
            yield from self._traverse(back_steps)

            if self.lighting_mode == "route_based":
                self._release_route_lights(full_route_segments_for_lighting)

            # Order complete
            order.completion_time = self.env.now()
            assert order.completion_time >= order.creation_time, (
                f"[verify] order {order.order_id} completes before it was created"
            )
            assert order.served_by_agv == self.agv_id
            self.orders_served += 1

