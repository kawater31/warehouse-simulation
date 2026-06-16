"""Post-run invariant checks. Inline asserts live in sls.py and agv.py."""
from __future__ import annotations

from typing import List


def assert_invariants(result) -> List[str]:
    """Return a list of invariant violations (empty == all pass)."""
    errors: List[str] = []
    dur = result.duration_s
    tol = 1e-6

    # on-time within [0, shift]
    for l in result.lights:
        if l.total_on_time_s < -tol:
            errors.append(f"I1 light {l.light_id}: negative on-time {l.total_on_time_s}")
        if l.total_on_time_s > dur + tol:
            errors.append(f"I1 light {l.light_id}: on-time {l.total_on_time_s} > shift {dur}")

    # always_on: every fixture lit the whole shift
    if result.scenario == "always_on":
        for l in result.lights:
            if abs(l.total_on_time_s - dur) > tol:
                errors.append(f"I2 light {l.light_id}: on-time {l.total_on_time_s} != shift {dur}")

    # completed orders are consistent
    for o in result.completed_orders:
        if o.completion_time < o.creation_time - tol:
            errors.append(f"I3 order {o.order_id}: completion < creation")
        if o.served_by_agv is None:
            errors.append(f"I3 order {o.order_id}: completed but served_by_agv is None")

    # AGVs still mid-order at the horizon may legitimately hold resources
    in_flight_agvs = {
        o.served_by_agv
        for o in result.all_orders
        if o.served_by_agv is not None and o.completion_time is None
    }

    # route_based: only an in-flight AGV may still hold a segment
    if result.scenario == "route_based":
        for sid, sls in result.sls_by_seg.items():
            leaked = sls.route_holders - in_flight_agvs
            if leaked:
                errors.append(f"I4 segment {sid}: leaked route_holders {leaked} "
                              f"(not in-flight {in_flight_agvs})")

    # sensor_based: ending occupancy cannot exceed in-flight AGVs
    if result.scenario == "sensor_based":
        total_occ = sum(sls.occupancy for sls in result.sls_by_seg.values())
        if total_occ > len(in_flight_agvs):
            errors.append(f"I5 total ending occupancy {total_occ} > "
                          f"in-flight AGVs {len(in_flight_agvs)}")

    return errors
