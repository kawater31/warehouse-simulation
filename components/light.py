"""Light: an energy-accounting record (not a salabim Component).

On-time accumulates whenever the light switches off or is finalised while on.
"""
from __future__ import annotations


class Light:

    __slots__ = (
        "light_id",
        "power_w",
        "state",
        "_on_since",
        "total_on_time_s",
        "_env",
    )

    def __init__(self, light_id: str, power_w: float, env=None):
        self.light_id = light_id
        self.power_w = power_w
        self.state = "off"
        self._on_since: float | None = None
        self.total_on_time_s = 0.0
        self._env = env

    def bind(self, env) -> None:
        self._env = env

    def turn_on(self) -> None:
        if self.state == "on":
            return
        self.state = "on"
        self._on_since = self._env.now()

    def turn_off(self) -> None:
        if self.state == "off":
            return
        elapsed = self._env.now() - self._on_since
        self.total_on_time_s += elapsed
        self.state = "off"
        self._on_since = None

    def finalise(self) -> None:
        """Book residual on-time at end of simulation."""
        if self.state == "on":
            self.total_on_time_s += self._env.now() - self._on_since
            self._on_since = self._env.now()

    @property
    def total_energy_wh(self) -> float:
        return self.power_w * self.total_on_time_s / 3600.0

    def live_energy_wh(self, now: float) -> float:
        """Energy so far, including the in-progress on-period (for live readouts)."""
        on = self.total_on_time_s
        if self.state == "on" and self._on_since is not None:
            on += now - self._on_since
        return self.power_w * on / 3600.0
