"""OrderGenerator: samples exponential inter-arrival times and emits orders.

Orders are deposited into a shared salabim Queue. AGVs poll this queue.
"""
from __future__ import annotations

import random
from collections import deque
from typing import Deque, List

import salabim as sim

import config as cfg
from components.order import Order


class OrderGenerator(sim.Component):
    """salabim component that creates orders on an exponential inter-arrival time.

    The order queue is a plain `collections.deque` of `Order` objects (not a
    `sim.Queue`) because `Order` is a passive dataclass, not a `sim.Component`.
    """

    def setup(  # type: ignore[override]
        self,
        order_queue: Deque[Order],
        pickup_ids: List[int],
        agvs=None,
        mean_interarrival_s: float = cfg.INTER_ARRIVAL_MEAN_S,
        rng_seed: int | None = None,
    ):
        self.order_queue = order_queue
        self.pickup_ids = pickup_ids
        self.agvs = agvs or []
        self.mean = mean_interarrival_s
        self.next_order_id = 0
        # local RNG so order arrivals & pickup choices are reproducible
        # independently of any other module's random use
        self._rng = random.Random(rng_seed)
        self.orders_created: List[Order] = []

    def process(self):  # type: ignore[override]
        while True:
            iat = self._rng.expovariate(1.0 / self.mean)
            yield self.hold(iat)

            self.next_order_id += 1
            pickup_id = self._rng.choice(self.pickup_ids)
            order = Order(
                order_id=self.next_order_id,
                pickup_ids=[pickup_id],
                creation_time=self.env.now(),
            )
            self.order_queue.append(order)
            self.orders_created.append(order)

            # Wake up any standby AGV
            for agv in self.agvs:
                if agv.ispassive():
                    agv.activate()
                    break
