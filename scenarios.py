"""Scenario assembly: build the salabim Environment and run one lighting strategy."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List

import salabim as sim

import config as cfg
import layout
from components.agv import AGV
from components.light import Light as EnergyLight
from components.order_generator import OrderGenerator
from components.pickup_location import PickupLocation
from components.sls import SmartLightingSystem
from routing import build_graph


@dataclass
class SimResult:
    scenario: str
    duration_s: float
    lights: List[EnergyLight]
    agvs: List[AGV]
    orders_created: int = 0
    orders_completed: int = 0
    completed_orders: list = field(default_factory=list)  # list[Order]
    sls_by_seg: Dict[str, SmartLightingSystem] = field(default_factory=dict)


def _build_environment(
    scenario: str,
    duration_s: float,
    seed: int,
    animate: bool = False,
):
    """Wire up all components for a single scenario run."""
    sim.yieldless(False)  # use yield-based generator components (see components/*)
    env = sim.Environment(trace=False, random_seed=seed, time_unit="seconds")

    # 1) Build the static warehouse layout & routing graph -------------------
    segments, layout_lights, pickup_points = layout.build_layout()
    graph = build_graph(pickup_points)

    # 2) Build the energy-accounting Light objects (one per layout.Light).
    #    Index them by their stable light_id so the SLS knows what to toggle.
    energy_lights: Dict[str, EnergyLight] = {}
    for ll in layout_lights:
        el = EnergyLight(light_id=ll.light_id, power_w=ll.power_w, env=env)
        el.bind(env)
        energy_lights[ll.light_id] = el

    # Map: segment_id -> list[EnergyLight covering that segment]
    seg_to_lights: Dict[str, List[EnergyLight]] = {s.seg_id: [] for s in segments}
    for ll in layout_lights:
        seg_to_lights[ll.segment_id].append(energy_lights[ll.light_id])

    # 3) Build one SmartLightingSystem per segment ----------------------------
    sls_by_seg: Dict[str, SmartLightingSystem] = {}
    for seg in segments:
        sls = SmartLightingSystem(
            name=f"sls_{seg.seg_id}",
            seg_id=seg.seg_id,
            lights=seg_to_lights[seg.seg_id],
        )
        sls_by_seg[seg.seg_id] = sls

    # 4) Always-on baseline: turn every light ON at t=0 and leave it on.
    if scenario == "always_on":
        for el in energy_lights.values():
            el.turn_on()

    # 5) Build PickupLocations (one per pickup point) -------------------------
    pickup_locations: Dict[int, PickupLocation] = {}
    for p in pickup_points:
        pickup_locations[p.pickup_id] = PickupLocation(
            name=f"pickup_loc_{p.pickup_id}",
            pickup_id=p.pickup_id,
        )

    # 6) Shared order queue. Plain deque because Order is a dataclass, not
    #    a sim.Component (which is what sim.Queue expects).
    order_queue = deque()

    # 7) AGVs -----------------------------------------------------------------
    agvs: List[AGV] = []
    for i in range(1, cfg.N_AGVS + 1):
        agv = AGV(
            name=f"agv_{i}",
            agv_id=i,
            order_queue=order_queue,
            graph=graph,
            pickup_locations=pickup_locations,
            sls_by_seg=sls_by_seg,
            lighting_mode=scenario,
        )
        agvs.append(agv)

    # 8) Order generator ------------------------------------------------------
    pickup_ids = [p.pickup_id for p in pickup_points]
    order_gen = OrderGenerator(
        name="order_generator",
        order_queue=order_queue,
        pickup_ids=pickup_ids,
        agvs=agvs,
        rng_seed=seed,
    )

    return env, agvs, energy_lights, sls_by_seg, order_gen


def run_scenario(
    scenario: str,
    duration_s: float = cfg.SHIFT_DURATION_S,
    seed: int = cfg.RANDOM_SEED,
    animate: bool = False,
) -> SimResult:
    assert scenario in {"always_on", "sensor_based", "route_based"}

    env, agvs, energy_lights, sls_by_seg, order_gen = _build_environment(
        scenario=scenario,
        duration_s=duration_s,
        seed=seed,
        animate=animate,
    )

    if animate:
        from visualization import attach_animation
        attach_animation(env, agvs, energy_lights, sls_by_seg)

    env.run(till=duration_s)

    # Finalise lights so any still-on lights accumulate their residual on-time.
    for el in energy_lights.values():
        el.finalise()

    completed_orders = [o for o in order_gen.orders_created if o.completion_time is not None]

    return SimResult(
        scenario=scenario,
        duration_s=duration_s,
        lights=list(energy_lights.values()),
        agvs=agvs,
        orders_created=len(order_gen.orders_created),
        orders_completed=len(completed_orders),
        completed_orders=completed_orders,
        sls_by_seg=sls_by_seg,
    )
