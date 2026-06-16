"""Smart Lighting System: one per segment, driven by sensor or route events.

Sensor path: occupancy counting with a restartable switch-off delay.
Route path: lights held on while any AGV has the segment reserved.
"""
from __future__ import annotations

from typing import List, Set

import salabim as sim

import config as cfg
from components.light import Light


class _ShutoffTimer(sim.Component):
    """Holds for the switch-off delay, then turns the segment off if still idle."""

    def setup(self, sls: "SmartLightingSystem"):  # type: ignore[override]
        self.sls = sls

    def process(self):  # type: ignore[override]
        yield self.hold(self.sls.switch_off_delay_s)
        if self.sls.occupancy == 0 and not self.sls.route_active:
            for light in self.sls.lights:
                light.turn_off()


class SmartLightingSystem(sim.Component):
    """One SLS per Segment."""

    def setup(  # type: ignore[override]
        self,
        seg_id: str,
        lights: List[Light],
        switch_off_delay_s: float = cfg.SWITCH_OFF_DELAY_S,
    ):
        self.seg_id = seg_id
        self.lights = lights
        self.switch_off_delay_s = switch_off_delay_s

        self.occupancy: int = 0
        self._timer: _ShutoffTimer | None = None
        self.route_holders: Set[int] = set()

    @property
    def route_active(self) -> bool:
        return len(self.route_holders) > 0

    def _assert_lights_on_if_demanded(self) -> None:
        # One direction only: during the cooldown a segment can be lit while idle.
        if self.occupancy > 0 or self.route_active:
            assert all(l.state == "on" for l in self.lights), (
                f"[verify] {self.seg_id} demanded "
                f"(occ={self.occupancy}, route={self.route_active}) but a light is off"
            )

    def process(self):  # type: ignore[override]
        yield self.passivate()  # event-driven, no continuous loop

    # ---------------- sensor-based API ----------------------------------- #
    def sensor_enter(self) -> None:
        self.occupancy += 1
        for light in self.lights:
            light.turn_on()
        if self._timer is not None and self._timer.isscheduled():
            self._timer.cancel()
            self._timer = None
        self._assert_lights_on_if_demanded()

    def sensor_exit(self) -> None:
        assert self.occupancy > 0, (
            f"[verify] sensor_exit on {self.seg_id} with occupancy={self.occupancy}: "
            "enter/exit calls are unbalanced"
        )
        self.occupancy -= 1
        if self.occupancy == 0 and not self.route_active:
            if self._timer is not None and self._timer.isscheduled():
                self._timer.cancel()
            self._timer = _ShutoffTimer(sls=self)
        self._assert_lights_on_if_demanded()

    # ---------------- route-based API ------------------------------------ #
    def route_activate(self, agv_id: int) -> None:
        self.route_holders.add(agv_id)
        for light in self.lights:
            light.turn_on()
        if self._timer is not None and self._timer.isscheduled():
            self._timer.cancel()
            self._timer = None
        self._assert_lights_on_if_demanded()

    def route_release(self, agv_id: int) -> None:
        assert agv_id in self.route_holders, (
            f"[verify] route_release by AGV {agv_id} on {self.seg_id} "
            "that never activated it"
        )
        self.route_holders.discard(agv_id)
        if not self.route_active and self.occupancy == 0:
            for light in self.lights:
                light.turn_off()
        self._assert_lights_on_if_demanded()
