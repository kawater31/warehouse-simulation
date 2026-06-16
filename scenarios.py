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
from components.recorder import Recorder
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
    completed_orders: list = field(default_factory=list)
    all_orders: list = field(default_factory=list)      # incl. in-flight orders
    sls_by_seg: Dict[str, SmartLightingSystem] = field(default_factory=dict)
    recorder: object = None


def _build_environment(
    scenario: str,
    duration_s: float,
    seed: int,
    animate: bool = False,
    trace: bool = False,
):
    """Wire up all components for a single scenario run."""
    sim.yieldless(False)
    env = sim.Environment(trace=trace, random_seed=seed, time_unit="seconds")

    segments, layout_lights, pickup_points = layout.build_layout()
    graph = build_graph(pickup_points)

    # energy-accounting lights, indexed by light_id
    energy_lights: Dict[str, EnergyLight] = {}
    for ll in layout_lights:
        el = EnergyLight(light_id=ll.light_id, power_w=ll.power_w, env=env)
        el.bind(env)
        energy_lights[ll.light_id] = el

    seg_to_lights: Dict[str, List[EnergyLight]] = {s.seg_id: [] for s in segments}
    for ll in layout_lights:
        seg_to_lights[ll.segment_id].append(energy_lights[ll.light_id])

    sls_by_seg: Dict[str, SmartLightingSystem] = {}
    for seg in segments:
        sls_by_seg[seg.seg_id] = SmartLightingSystem(
            name=f"sls_{seg.seg_id}",
            seg_id=seg.seg_id,
            lights=seg_to_lights[seg.seg_id],
        )

    if scenario == "always_on":
        for el in energy_lights.values():
            el.turn_on()

    pickup_locations: Dict[int, PickupLocation] = {}
    for p in pickup_points:
        pickup_locations[p.pickup_id] = PickupLocation(
            name=f"pickup_loc_{p.pickup_id}",
            pickup_id=p.pickup_id,
        )

    order_queue = deque()  # plain deque: Order is a dataclass, not a sim.Component

    agvs: List[AGV] = []
    for i in range(1, cfg.N_AGVS + 1):
        agvs.append(AGV(
            name=f"agv_{i}",
            agv_id=i,
            order_queue=order_queue,
            graph=graph,
            pickup_locations=pickup_locations,
            sls_by_seg=sls_by_seg,
            lighting_mode=scenario,
        ))

    pickup_ids = [p.pickup_id for p in pickup_points]
    order_gen = OrderGenerator(
        name="order_generator",
        order_queue=order_queue,
        pickup_ids=pickup_ids,
        agvs=agvs,
        rng_seed=seed,
    )

    recorder = Recorder(
        name="recorder",
        order_queue=order_queue,
        energy_lights=energy_lights,
        sls_by_seg=sls_by_seg,
    )

    return env, agvs, energy_lights, sls_by_seg, order_gen, recorder


def run_scenario(
    scenario: str,
    duration_s: float = cfg.SHIFT_DURATION_S,
    seed: int = cfg.RANDOM_SEED,
    animate: bool = False,
    trace: bool = False,
    verify: bool = True,
) -> SimResult:
    assert scenario in {"always_on", "sensor_based", "route_based"}

    env, agvs, energy_lights, sls_by_seg, order_gen, recorder = _build_environment(
        scenario=scenario,
        duration_s=duration_s,
        seed=seed,
        animate=animate,
        trace=trace,
    )

    if animate:
        from visualization import attach_animation
        attach_animation(env, agvs, energy_lights, sls_by_seg, order_gen, recorder,
                         scenario=scenario)

    if trace:
        import contextlib
        import os
        os.makedirs(cfg.RESULTS_DIR, exist_ok=True)
        trace_path = os.path.join(cfg.RESULTS_DIR, f"trace_{scenario}.log")
        with open(trace_path, "w") as f, contextlib.redirect_stdout(f):
            env.run(till=duration_s)
        print(f"  -> wrote {trace_path}")
    else:
        env.run(till=duration_s)

    for el in energy_lights.values():
        el.finalise()

    completed_orders = [o for o in order_gen.orders_created if o.completion_time is not None]

    result = SimResult(
        scenario=scenario,
        duration_s=duration_s,
        lights=list(energy_lights.values()),
        agvs=agvs,
        orders_created=len(order_gen.orders_created),
        orders_completed=len(completed_orders),
        completed_orders=completed_orders,
        all_orders=list(order_gen.orders_created),
        sls_by_seg=sls_by_seg,
        recorder=recorder,
    )

    if verify:
        from verification import assert_invariants
        errors = assert_invariants(result)
        if errors:
            print(f"  [verify] {len(errors)} INVARIANT VIOLATION(S) in {scenario}:")
            for e in errors:
                print("   -", e)
            raise AssertionError(f"invariant violations in {scenario}")
        print(f"  [verify] all post-run invariants passed ({scenario}); "
              f"queue mean={recorder.qlen.mean():.2f}, "
              f"lights-on mean={recorder.lights_on.mean():.1f}, "
              f"occupancy max={recorder.occupancy.maximum():.0f}")

    return result
