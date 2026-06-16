"""Recorder: periodically samples queue length, occupancy and lights-on."""
from __future__ import annotations

import salabim as sim


class Recorder(sim.Component):
    def setup(  # type: ignore[override]
        self, order_queue, energy_lights, sls_by_seg, interval: float = 60.0
    ):
        self.order_queue = order_queue
        self.energy_lights = energy_lights
        self.sls_by_seg = sls_by_seg
        self.interval = interval
        self.qlen = sim.Monitor(name="order_queue_length", level=True)
        self.lights_on = sim.Monitor(name="lights_on", level=True)
        self.occupancy = sim.Monitor(name="total_occupancy", level=True)

    def process(self):  # type: ignore[override]
        while True:
            self.qlen.tally(len(self.order_queue))
            self.lights_on.tally(sum(1 for l in self.energy_lights.values() if l.state == "on"))
            self.occupancy.tally(sum(s.occupancy for s in self.sls_by_seg.values()))
            yield self.hold(self.interval)
