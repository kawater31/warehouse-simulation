"""Order: a passive data carrier passed between OrderGenerator and AGV."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class Order:
    """A pick request.

    `pickup_ids` is structured as a list to keep multi-pickup orders trivial
    to support later. In the current model every order has exactly one entry.
    """
    order_id: int
    pickup_ids: List[int]
    creation_time: float
    completion_time: float | None = None
    served_by_agv: int | None = None

    @property
    def cycle_time(self) -> float | None:
        if self.completion_time is None:
            return None
        return self.completion_time - self.creation_time
