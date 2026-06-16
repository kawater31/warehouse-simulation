"""PickupLocation: holds an AGV for the pickup time, then releases it."""
from __future__ import annotations

import salabim as sim

import config as cfg


class PickupLocation(sim.Component):

    def setup(  # type: ignore[override]
        self,
        pickup_id: int,
        pickup_time_s: float = cfg.PICKUP_TIME_S,
    ):
        self.pickup_id = pickup_id
        self.pickup_time_s = pickup_time_s
        self.my_queue: sim.Queue = sim.Queue(name=f"pickup_q_{pickup_id}")

    def process(self):  # type: ignore[override]
        while True:
            while len(self.my_queue) == 0:
                yield self.passivate()
            agv = self.my_queue.pop()
            yield self.hold(self.pickup_time_s)
            agv.activate()
