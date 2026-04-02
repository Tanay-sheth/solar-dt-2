"""Optimizer FMU model implementing forward and inverse control logic."""

from __future__ import annotations

from typing import Any

from pythonfmu import Fmi2Slave
from pythonfmu.enums import Fmi2Causality, Fmi2Variability
from pythonfmu.variables import Integer, Real


class Optimizer(Fmi2Slave):
    """FMU optimizer with a persistent state machine for inverse mode."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.in_current_power: float = 0.0
        self.start_mode: int = 1
        self.initial_target_power: float = 10.0
        self.out_target_pan: float = 90.0
        self.out_target_tilt: float = 45.0

        self.state: int = 0
        self._target_snapshot: float = self.initial_target_power
        self._sweep_points: list[tuple[float, float]] = [
            (70.0, 20.0),
            (80.0, 30.0),
            (90.0, 45.0),
            (100.0, 60.0),
            (110.0, 70.0),
        ]
        self._sweep_index: int = 0
        self._pending_sweep_point: tuple[float, float] | None = None
        self._mpp_pan: float = 90.0
        self._mpp_tilt: float = 45.0
        self._max_power: float = -1.0
        self._low_tilt: float = 0.0
        self._high_tilt: float = 45.0
        self._pending_binary_tilt: float | None = None
        self._tolerance_w: float = 0.5

        self.register_variable(
            Real(
                "in_current_power",
                causality=Fmi2Causality.input,
                variability=Fmi2Variability.continuous,
            )
        )
        self.register_variable(
            Integer(
                "start_mode",
                causality=Fmi2Causality.input,
                variability=Fmi2Variability.discrete,
            )
        )
        self.register_variable(
            Real(
                "initial_target_power",
                causality=Fmi2Causality.parameter,
                variability=Fmi2Variability.fixed,
            )
        )
        self.register_variable(
            Real(
                "out_target_pan",
                causality=Fmi2Causality.output,
                variability=Fmi2Variability.continuous,
            )
        )
        self.register_variable(
            Real(
                "out_target_tilt",
                causality=Fmi2Causality.output,
                variability=Fmi2Variability.continuous,
            )
        )

    def _begin_inverse_search(self) -> None:
        self.state = 1
        self._target_snapshot = float(self.initial_target_power)
        self._sweep_index = 0
        self._pending_sweep_point = None
        self._mpp_pan = self.out_target_pan
        self._mpp_tilt = self.out_target_tilt
        self._max_power = -1.0
        self._low_tilt = 0.0
        self._high_tilt = self._mpp_tilt
        self._pending_binary_tilt = None

    def _record_sweep_measurement(self) -> None:
        if self._pending_sweep_point is None:
            return
        if self.in_current_power > self._max_power:
            self._max_power = self.in_current_power
            self._mpp_pan, self._mpp_tilt = self._pending_sweep_point
        self._pending_sweep_point = None

    def _run_sweep(self) -> None:
        self._record_sweep_measurement()

        if self._sweep_index >= len(self._sweep_points):
            self.state = 2
            self._low_tilt = 0.0
            self._high_tilt = self._mpp_tilt
            self._pending_binary_tilt = None
            self.out_target_pan = self._mpp_pan
            self.out_target_tilt = self._mpp_tilt
            return

        pan, tilt = self._sweep_points[self._sweep_index]
        self.out_target_pan = pan
        self.out_target_tilt = tilt
        self._pending_sweep_point = (pan, tilt)
        self._sweep_index += 1

    def _run_binary(self) -> None:
        target = float(self.initial_target_power)

        if self._pending_binary_tilt is not None:
            if abs(self.in_current_power - target) <= self._tolerance_w:
                self.out_target_pan = self._mpp_pan
                self.out_target_tilt = self._pending_binary_tilt
                return
            if self.in_current_power > target:
                self._high_tilt = self._pending_binary_tilt
            else:
                self._low_tilt = self._pending_binary_tilt

        next_tilt = (self._low_tilt + self._high_tilt) / 2.0
        self._pending_binary_tilt = next_tilt
        self.out_target_pan = self._mpp_pan
        self.out_target_tilt = next_tilt

    def do_step(self, current_time: float, step_size: float) -> bool:
        del current_time, step_size

        if int(self.start_mode) == 0:
            self.state = 0
            self._pending_sweep_point = None
            self._pending_binary_tilt = None
            self.out_target_pan = 90.0
            self.out_target_tilt = 45.0
            return True

        target_changed = abs(float(self.initial_target_power) - self._target_snapshot) > 1e-9
        if self.state == 0 and target_changed:
            self._begin_inverse_search()

        if self.state == 1:
            self._run_sweep()
            return True

        if self.state == 2:
            self._run_binary()
            return True

        self.out_target_pan = 90.0
        self.out_target_tilt = 45.0
        return True
