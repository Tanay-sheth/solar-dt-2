"""Optimizer FMU: 2° coarse sweep + dual-side binary search with error comparison."""

from __future__ import annotations

import math
from typing import Any

from pythonfmu import Fmi2Slave
from pythonfmu.enums import Fmi2Causality, Fmi2Variability
from pythonfmu.variables import Integer, Real


class Optimizer(Fmi2Slave):
    """FMU optimizer: 2° coarse sweep + binary search on LEFT/RIGHT of MPP on each axis."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.in_current_power: float = 0.0
        self.start_mode: int = 1
        self.initial_target_power: float = 10.0
        self.out_target_pan: float = 90.0
        self.out_target_tilt: float = 45.0

        self._pan_min: float = 0.0
        self._pan_max: float = 180.0
        self._tilt_min: float = 0.0
        self._tilt_max: float = 90.0

        self._coarse_step_deg: float = 2.0
        self._tolerance_w: float = 0.3

        self.state: int = 0
        self._target_snapshot: float = self.initial_target_power

        # State 1: Coarse sweep
        self._sweep_points: list[tuple[float, float]] = []
        self._sweep_index: int = 0
        self._pending_sweep_point: tuple[float, float] | None = None
        self._max_power: float = -1.0
        self._mpp_pan: float = 90.0
        self._mpp_tilt: float = 45.0

        # State 2: Pan binary search (LEFT and RIGHT)
        self._pan_low: float = 0.0
        self._pan_high: float = 180.0
        self._pan_mid: float = 90.0
        self._bs_pan_power_low: float = 0.0
        self._bs_pan_power_mid: float = 0.0
        self._bs_pan_power_high: float = 0.0
        self._bs_pan_phase: int = 0
        self._bs_pan_side: str = "left"  # "left", "right", or "done"
        self._bs_pan_best_error_left: float = float("inf")
        self._bs_pan_best_pan_left: float = 90.0
        self._bs_pan_best_error_right: float = float("inf")
        self._bs_pan_best_pan_right: float = 90.0
        self._bs_pan_best_pan: float = 90.0

        # State 3: Tilt binary search (DOWN and UP)
        self._tilt_low: float = 0.0
        self._tilt_high: float = 90.0
        self._tilt_mid: float = 45.0
        self._bs_tilt_power_low: float = 0.0
        self._bs_tilt_power_mid: float = 0.0
        self._bs_tilt_power_high: float = 0.0
        self._bs_tilt_phase: int = 0
        self._bs_tilt_side: str = "down"  # "down", "up", or "done"
        self._bs_tilt_best_error_down: float = float("inf")
        self._bs_tilt_best_error_up: float = float("inf")
        self._bs_tilt_best_tilt: float = 45.0

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
                causality=Fmi2Causality.parameter,
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

    def _build_sweep_points(self) -> list[tuple[float, float]]:
        """Build 2D grid with 2° steps, serpentine to reduce backtracking."""
        points: list[tuple[float, float]] = []
        tilt = self._tilt_min
        row = 0
        while tilt <= self._tilt_max + 1e-9:
            pan_values: list[float] = []
            pan = self._pan_min
            while pan <= self._pan_max + 1e-9:
                pan_values.append(round(pan, 3))
                pan += self._coarse_step_deg
            if row % 2 == 1:
                pan_values.reverse()
            for pv in pan_values:
                points.append((round(min(pv, self._pan_max), 3), round(tilt, 3)))
            row += 1
            tilt += self._coarse_step_deg
        return points

    def _begin_inverse_search(self) -> None:
        """Start optimization: coarse sweep to find MPP."""
        self.state = 1
        self._target_snapshot = float(self.initial_target_power)
        self._sweep_points = self._build_sweep_points()
        self._sweep_index = 0
        self._pending_sweep_point = None
        self._max_power = -1.0
        self._mpp_pan = 90.0
        self._mpp_tilt = 45.0
        # Reset pan search
        self._pan_low = self._pan_min
        self._pan_high = self._pan_max
        self._pan_mid = (self._pan_low + self._pan_high) / 2.0
        self._bs_pan_phase = 0
        self._bs_pan_side = "left"
        self._bs_pan_best_error_left = float("inf")
        self._bs_pan_best_pan_left = 90.0
        self._bs_pan_best_error_right = float("inf")
        self._bs_pan_best_pan_right = 90.0
        # Reset tilt search
        self._tilt_low = self._tilt_min
        self._tilt_high = self._tilt_max
        self._tilt_mid = (self._tilt_low + self._tilt_high) / 2.0
        self._bs_tilt_phase = 0
        self._bs_tilt_side = "down"
        self._bs_tilt_best_error_down = float("inf")
        self._bs_tilt_best_error_up = float("inf")

    def _run_sweep(self) -> None:
        """State 1: Execute coarse 2° sweep to find MPP."""
        if self._pending_sweep_point is not None and self.in_current_power > self._max_power:
            self._max_power = self.in_current_power
            self._mpp_pan, self._mpp_tilt = self._pending_sweep_point

        if self._sweep_index >= len(self._sweep_points):
            self._enter_pan_search()
            return

        pan, tilt = self._sweep_points[self._sweep_index]
        self._sweep_index += 1
        self.out_target_pan = pan
        self.out_target_tilt = tilt
        self._pending_sweep_point = (pan, tilt)

    def _enter_pan_search(self) -> None:
        """Transition to State 2: binary search pan (LEFT side first)."""
        self.state = 2
        self._pan_low = self._pan_min
        self._pan_high = self._mpp_pan
        self._pan_mid = (self._pan_low + self._pan_high) / 2.0
        self._bs_pan_phase = 0
        self._bs_pan_side = "left"
        self.out_target_pan = self._pan_low
        self.out_target_tilt = self._mpp_tilt

    def _run_pan_search(self) -> None:
        """State 2: Binary search on pan. LEFT side, then RIGHT side, compare errors."""
        target = float(self.initial_target_power)

        if self._bs_pan_side == "left":
            if self._bs_pan_phase == 0:
                self._bs_pan_power_low = self.in_current_power
                error = abs(self._bs_pan_power_low - target)
                if error < self._bs_pan_best_error_left:
                    self._bs_pan_best_error_left = error
                    self._bs_pan_best_pan_left = self._pan_low
                self._bs_pan_phase = 1
                self.out_target_pan = self._pan_mid
                self.out_target_tilt = self._mpp_tilt

            elif self._bs_pan_phase == 1:
                self._bs_pan_power_mid = self.in_current_power
                error = abs(self._bs_pan_power_mid - target)
                if error < self._bs_pan_best_error_left:
                    self._bs_pan_best_error_left = error
                    self._bs_pan_best_pan_left = self._pan_mid
                self._bs_pan_phase = 2
                self.out_target_pan = self._pan_high
                self.out_target_tilt = self._mpp_tilt

            elif self._bs_pan_phase == 2:
                self._bs_pan_power_high = self.in_current_power
                error = abs(self._bs_pan_power_high - target)
                if error < self._bs_pan_best_error_left:
                    self._bs_pan_best_error_left = error
                    self._bs_pan_best_pan_left = self._pan_high
                self._bs_pan_phase = 3

                # Check convergence
                if self._pan_high - self._pan_low < 2.0:
                    # LEFT converged, switch to RIGHT
                    self._bs_pan_side = "right"
                    self._bs_pan_phase = 0
                    self._pan_low = self._mpp_pan
                    self._pan_high = self._pan_max
                    self._pan_mid = (self._pan_low + self._pan_high) / 2.0
                    self.out_target_pan = self._pan_low
                    self.out_target_tilt = self._mpp_tilt
                    return

                # Narrow LEFT range
                mid_err = abs(self._bs_pan_power_mid - target)
                low_err = abs(self._bs_pan_power_low - target)
                high_err = abs(self._bs_pan_power_high - target)
                if high_err <= low_err and high_err <= mid_err:
                    self._pan_low = self._pan_mid
                elif low_err <= mid_err and low_err <= high_err:
                    self._pan_high = self._pan_mid
                else:
                    self._pan_low = max(self._pan_min, self._pan_mid - (self._pan_mid - self._pan_low) / 4.0)
                    self._pan_high = min(self._mpp_pan, self._pan_mid + (self._pan_high - self._pan_mid) / 4.0)

                self._pan_mid = (self._pan_low + self._pan_high) / 2.0
                self._bs_pan_phase = 0
                self.out_target_pan = self._pan_low
                self.out_target_tilt = self._mpp_tilt

        elif self._bs_pan_side == "right":
            if self._bs_pan_phase == 0:
                self._bs_pan_power_low = self.in_current_power
                error = abs(self._bs_pan_power_low - target)
                if error < self._bs_pan_best_error_right:
                    self._bs_pan_best_error_right = error
                    self._bs_pan_best_pan_right = self._pan_low
                self._bs_pan_phase = 1
                self.out_target_pan = self._pan_mid
                self.out_target_tilt = self._mpp_tilt

            elif self._bs_pan_phase == 1:
                self._bs_pan_power_mid = self.in_current_power
                error = abs(self._bs_pan_power_mid - target)
                if error < self._bs_pan_best_error_right:
                    self._bs_pan_best_error_right = error
                    self._bs_pan_best_pan_right = self._pan_mid
                self._bs_pan_phase = 2
                self.out_target_pan = self._pan_high
                self.out_target_tilt = self._mpp_tilt

            elif self._bs_pan_phase == 2:
                self._bs_pan_power_high = self.in_current_power
                error = abs(self._bs_pan_power_high - target)
                if error < self._bs_pan_best_error_right:
                    self._bs_pan_best_error_right = error
                    self._bs_pan_best_pan_right = self._pan_high
                self._bs_pan_phase = 3

                # Check convergence
                if self._pan_high - self._pan_low < 2.0:
                    # RIGHT converged, compare LEFT vs RIGHT
                    if self._bs_pan_best_error_left <= self._bs_pan_best_error_right:
                        self._bs_pan_best_pan = self._bs_pan_best_pan_left
                    else:
                        self._bs_pan_best_pan = self._bs_pan_best_pan_right
                    self._enter_tilt_search()
                    return

                # Narrow RIGHT range
                mid_err = abs(self._bs_pan_power_mid - target)
                low_err = abs(self._bs_pan_power_low - target)
                high_err = abs(self._bs_pan_power_high - target)
                if low_err <= mid_err and low_err <= high_err:
                    self._pan_high = self._pan_mid
                elif high_err <= mid_err and high_err <= low_err:
                    self._pan_low = self._pan_mid
                else:
                    self._pan_low = max(self._mpp_pan, self._pan_mid - (self._pan_mid - self._pan_low) / 4.0)
                    self._pan_high = min(self._pan_max, self._pan_mid + (self._pan_high - self._pan_mid) / 4.0)

                self._pan_mid = (self._pan_low + self._pan_high) / 2.0
                self._bs_pan_phase = 0
                self.out_target_pan = self._pan_low
                self.out_target_tilt = self._mpp_tilt

    def _enter_tilt_search(self) -> None:
        """Transition to State 3: binary search tilt (DOWN side first)."""
        self.state = 3
        self._tilt_low = self._tilt_min
        self._tilt_high = self._mpp_tilt
        self._tilt_mid = (self._tilt_low + self._tilt_high) / 2.0
        self._bs_tilt_phase = 0
        self._bs_tilt_side = "down"
        self.out_target_pan = self._bs_pan_best_pan
        self.out_target_tilt = self._tilt_low

    def _run_tilt_search(self) -> None:
        """State 3: Binary search on tilt. DOWN side, then UP side, compare errors."""
        target = float(self.initial_target_power)

        if self._bs_tilt_side == "down":
            if self._bs_tilt_phase == 0:
                self._bs_tilt_power_low = self.in_current_power
                error = abs(self._bs_tilt_power_low - target)
                if error < self._bs_tilt_best_error_down:
                    self._bs_tilt_best_error_down = error
                    self._bs_tilt_best_tilt = self._tilt_low
                self._bs_tilt_phase = 1
                self.out_target_pan = self._bs_pan_best_pan
                self.out_target_tilt = self._tilt_mid

            elif self._bs_tilt_phase == 1:
                self._bs_tilt_power_mid = self.in_current_power
                error = abs(self._bs_tilt_power_mid - target)
                if error < self._bs_tilt_best_error_down:
                    self._bs_tilt_best_error_down = error
                    self._bs_tilt_best_tilt = self._tilt_mid
                self._bs_tilt_phase = 2
                self.out_target_pan = self._bs_pan_best_pan
                self.out_target_tilt = self._tilt_high

            elif self._bs_tilt_phase == 2:
                self._bs_tilt_power_high = self.in_current_power
                error = abs(self._bs_tilt_power_high - target)
                if error < self._bs_tilt_best_error_down:
                    self._bs_tilt_best_error_down = error
                    self._bs_tilt_best_tilt = self._tilt_high
                self._bs_tilt_phase = 3

                # Check convergence
                if self._tilt_high - self._tilt_low < 2.0:
                    # DOWN converged, switch to UP
                    self._bs_tilt_side = "up"
                    self._bs_tilt_phase = 0
                    self._tilt_low = self._mpp_tilt
                    self._tilt_high = self._tilt_max
                    self._tilt_mid = (self._tilt_low + self._tilt_high) / 2.0
                    self.out_target_pan = self._bs_pan_best_pan
                    self.out_target_tilt = self._tilt_low
                    return

                # Narrow DOWN range
                mid_err = abs(self._bs_tilt_power_mid - target)
                low_err = abs(self._bs_tilt_power_low - target)
                high_err = abs(self._bs_tilt_power_high - target)
                if high_err <= low_err and high_err <= mid_err:
                    self._tilt_low = self._tilt_mid
                elif low_err <= mid_err and low_err <= high_err:
                    self._tilt_high = self._tilt_mid
                else:
                    self._tilt_low = max(self._tilt_min, self._tilt_mid - (self._tilt_mid - self._tilt_low) / 4.0)
                    self._tilt_high = min(self._mpp_tilt, self._tilt_mid + (self._tilt_high - self._tilt_mid) / 4.0)

                self._tilt_mid = (self._tilt_low + self._tilt_high) / 2.0
                self._bs_tilt_phase = 0
                self.out_target_pan = self._bs_pan_best_pan
                self.out_target_tilt = self._tilt_low

        elif self._bs_tilt_side == "up":
            if self._bs_tilt_phase == 0:
                self._bs_tilt_power_low = self.in_current_power
                error = abs(self._bs_tilt_power_low - target)
                if error < self._bs_tilt_best_error_up:
                    self._bs_tilt_best_error_up = error
                    self._bs_tilt_best_tilt = self._tilt_low
                self._bs_tilt_phase = 1
                self.out_target_pan = self._bs_pan_best_pan
                self.out_target_tilt = self._tilt_mid

            elif self._bs_tilt_phase == 1:
                self._bs_tilt_power_mid = self.in_current_power
                error = abs(self._bs_tilt_power_mid - target)
                if error < self._bs_tilt_best_error_up:
                    self._bs_tilt_best_error_up = error
                    self._bs_tilt_best_tilt = self._tilt_mid
                self._bs_tilt_phase = 2
                self.out_target_pan = self._bs_pan_best_pan
                self.out_target_tilt = self._tilt_high

            elif self._bs_tilt_phase == 2:
                self._bs_tilt_power_high = self.in_current_power
                error = abs(self._bs_tilt_power_high - target)
                if error < self._bs_tilt_best_error_up:
                    self._bs_tilt_best_error_up = error
                    self._bs_tilt_best_tilt = self._tilt_high
                self._bs_tilt_phase = 3

                # Check convergence
                if self._tilt_high - self._tilt_low < 2.0:
                    # UP converged, compare DOWN vs UP
                    if self._bs_tilt_best_error_down <= self._bs_tilt_best_error_up:
                        self.out_target_tilt = self._bs_tilt_best_tilt
                    else:
                        # Find best from UP side by re-running narrowing
                        pass
                    return

                # Narrow UP range
                mid_err = abs(self._bs_tilt_power_mid - target)
                low_err = abs(self._bs_tilt_power_low - target)
                high_err = abs(self._bs_tilt_power_high - target)
                if low_err <= mid_err and low_err <= high_err:
                    self._tilt_high = self._tilt_mid
                elif high_err <= mid_err and high_err <= low_err:
                    self._tilt_low = self._tilt_mid
                else:
                    self._tilt_low = max(self._mpp_tilt, self._tilt_mid - (self._tilt_mid - self._tilt_low) / 4.0)
                    self._tilt_high = min(self._tilt_max, self._tilt_mid + (self._tilt_high - self._tilt_mid) / 4.0)

                self._tilt_mid = (self._tilt_low + self._tilt_high) / 2.0
                self._bs_tilt_phase = 0
                self.out_target_pan = self._bs_pan_best_pan
                self.out_target_tilt = self._tilt_low

    def do_step(self, current_time: float, step_size: float) -> bool:
        """Main FMU step."""
        del current_time, step_size

        if int(self.start_mode) == 0:
            self.state = 0
            self._pending_sweep_point = None
            return True

        if self.state == 0 or abs(float(self.initial_target_power) - self._target_snapshot) > 1e-9:
            self._begin_inverse_search()

        if self.state == 1:
            self._run_sweep()
        elif self.state == 2:
            self._run_pan_search()
        elif self.state == 3:
            self._run_tilt_search()

        return True


if __name__ == "__main__":
    import socketio

    GATEWAY_URL = "http://localhost:4000"
    MAX_POWER_W = 20.0

    sio = socketio.Client()
    model = Optimizer(instance_name="optimizer_twin")
    runtime_state = {"mode": "inverse"}

    def _safe_number(value: Any) -> float | None:
        if isinstance(value, (int, float)):
            number = float(value)
            if math.isfinite(number):
                return number
        return None

    def _emit_model_update(current_power: float) -> None:
        target = float(model.initial_target_power)
        max_available = model._max_power if model._max_power > 0.0 else MAX_POWER_W
        achievable = target <= (max_available + model._tolerance_w)

        payload = {
            "target_pan": float(model.out_target_pan),
            "target_tilt": float(model.out_target_tilt),
            "achievable": achievable,
            "current_power": current_power,
            "estimated_max_power": max_available,
        }
        sio.emit("model_update", payload)

    @sio.on("connect")
    def on_connect() -> None:
        print("Optimizer Digital Twin connected to Gateway")
        _emit_model_update(current_power=model.in_current_power)

    @sio.on("control_mode")
    def on_control_mode(data: Any) -> None:
        next_mode = "inverse"
        if isinstance(data, dict) and data.get("mode") == "forward":
            next_mode = "forward"
        runtime_state["mode"] = next_mode
        model.start_mode = 1 if next_mode == "inverse" else 0

    @sio.on("update_target_power")
    def on_target_update(data: Any) -> None:
        if runtime_state["mode"] != "inverse" or not isinstance(data, dict):
            return
        next_target = _safe_number(data.get("target"))
        if next_target is None:
            return
        model.initial_target_power = max(0.0, next_target)
        model.do_step(0.0, 0.1)
        _emit_model_update(current_power=model.in_current_power)

    @sio.on("set_target_power")
    def on_legacy_target_update(data: Any) -> None:
        on_target_update(data)

    @sio.on("telemetry_update")
    def on_data(data: Any) -> None:
        if not isinstance(data, dict):
            return
        current_power = _safe_number(data.get("current_power"))
        if current_power is None:
            return
        model.in_current_power = current_power
        model.start_mode = 1 if runtime_state["mode"] == "inverse" else 0
        model.do_step(0.0, 0.1)
        if runtime_state["mode"] == "inverse":
            _emit_model_update(current_power=current_power)

    @sio.on("data_update")
    def on_legacy_data(data: Any) -> None:
        on_data(data)

    try:
        sio.connect(GATEWAY_URL, transports=["polling"])
        sio.wait()
    except Exception as e:
        print(f"Failed to connect: {e}")
