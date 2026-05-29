"""Light: not a salabim Component, just an energy-accounting record.

A Light is either on or off. Whenever it transitions off (or is finalised at
end-of-simulation while still on), we accumulate Power * elapsed_time into
its TotalOnTime / total_energy_wh counters.
"""
from __future__ import annotations


class Light:
    """Energy-accounting light fixture.

    Parameters
    ----------
    light_id : str
        Stable identifier (matches the layout.Light light_id).
    power_w : float
        Electrical power in watts.
    """

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
        self._env = env  # set by Light.bind(env) before any toggle

    # ------------------------------------------------------------------ #
    def bind(self, env) -> None:
        """Attach a salabim Environment for time queries."""
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
        """Accumulate residual on-time at end-of-simulation."""
        if self.state == "on":
            elapsed = self._env.now() - self._on_since
            self.total_on_time_s += elapsed
            self._on_since = self._env.now()  # leave 'on' but reset baseline

    # ------------------------------------------------------------------ #
    @property
    def total_energy_wh(self) -> float:
        return self.power_w * self.total_on_time_s / 3600.0
