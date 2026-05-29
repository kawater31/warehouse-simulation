"""Smart Lighting System (SLS).

One SLS per warehouse Segment. The SLS owns the segment's light(s) and is
driven by either:

(a) Sensor events from AGVs traversing the segment (sensor-based scenario):
        - On enter:   occupancy += 1, lights ON, cancel pending shutoff.
        - On exit:    occupancy -= 1, if 0 schedule a shutoff in SwitchOffDelay s.
        - If the segment is re-entered while a shutoff is pending, the timer
          is cancelled (so the SwitchOffDelay effectively restarts the next
          time occupancy returns to zero).

(b) Direct route activation (route-based scenario):
        - The AGV calls `route_activate(agv)` at departure, which turns the
          lights on for the duration of the trip.
        - The AGV calls `route_release(agv)` on return; the lights turn off
          immediately (no SwitchOffDelay in the route-based model).

The two activation paths are intentionally separate so a scenario can wire
in whichever pathway it wants.
"""
from __future__ import annotations

from typing import List, Set

import salabim as sim

import config as cfg
from components.light import Light


class _ShutoffTimer(sim.Component):
    """Helper component: holds for SwitchOffDelay then asks the SLS to switch off."""

    def setup(self, sls: "SmartLightingSystem"):  # type: ignore[override]
        self.sls = sls

    def process(self):  # type: ignore[override]
        yield self.hold(self.sls.switch_off_delay_s)
        # Re-check occupancy at fire-time (defensive; cancel() should normally
        # prevent us from reaching here while occupied).
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

        # Sensor-based state
        self.occupancy: int = 0
        self._timer: _ShutoffTimer | None = None

        # Route-based state. We keep a set of AGV ids that have requested the
        # segment so re-entries don't double-toggle.
        self.route_holders: Set[int] = set()

    @property
    def route_active(self) -> bool:
        return len(self.route_holders) > 0

    def process(self):  # type: ignore[override]
        # The SLS itself is event-driven; it has no continuous loop.
        yield self.passivate()

    # ---------------- sensor-based API ----------------------------------- #
    def sensor_enter(self) -> None:
        """An AGV has entered the segment."""
        self.occupancy += 1
        for light in self.lights:
            light.turn_on()
        if self._timer is not None and self._timer.isscheduled():
            self._timer.cancel()
            self._timer = None

    def sensor_exit(self) -> None:
        """An AGV has left the segment."""
        if self.occupancy > 0:
            self.occupancy -= 1
        if self.occupancy == 0 and not self.route_active:
            # Start (or restart) the shutoff timer.
            if self._timer is not None and self._timer.isscheduled():
                self._timer.cancel()
            self._timer = _ShutoffTimer(sls=self)

    # ---------------- route-based API ------------------------------------ #
    def route_activate(self, agv_id: int) -> None:
        """An AGV has reserved this segment for the duration of its route."""
        self.route_holders.add(agv_id)
        for light in self.lights:
            light.turn_on()
        # Cancel any pending shutoff timer (defensive — usually unused in
        # route-based runs, but harmless if the scenario mixes both).
        if self._timer is not None and self._timer.isscheduled():
            self._timer.cancel()
            self._timer = None

    def route_release(self, agv_id: int) -> None:
        """An AGV has released this segment."""
        self.route_holders.discard(agv_id)
        if not self.route_active and self.occupancy == 0:
            for light in self.lights:
                light.turn_off()
