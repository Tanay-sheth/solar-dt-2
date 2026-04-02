"""Hardware proxy FMU model bridging Maestro and the Node.js gateway."""

from __future__ import annotations

import time
from typing import Any

import socketio
from pythonfmu import Fmi2Slave
from pythonfmu.enums import Fmi2Causality
from pythonfmu.variables import Real


class HardwareProxy(Fmi2Slave):
    """FMU proxy that sends angle commands and receives power telemetry."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.in_target_pan: float = 90.0
        self.in_target_tilt: float = 45.0
        self.out_current_power: float = 0.0

        self._client: socketio.SimpleClient | None = None

        self.register_variable(Real("in_target_pan", causality=Fmi2Causality.input))
        self.register_variable(Real("in_target_tilt", causality=Fmi2Causality.input))
        self.register_variable(Real("out_current_power", causality=Fmi2Causality.output))

    def _ensure_client(self) -> socketio.SimpleClient | None:
        if self._client is not None:
            return self._client

        client = socketio.SimpleClient()
        try:
            client.connect("http://localhost:4000")
        except Exception:
            return None

        self._client = client
        return self._client

    def _extract_power(self, message: Any) -> float | None:
        event_name: str | None = None
        payload: Any = None

        if isinstance(message, tuple) and len(message) == 2:
            event_name, payload = message
        elif isinstance(message, list) and len(message) >= 1:
            event_name = message[0]
            payload = message[1] if len(message) > 1 else None
        elif isinstance(message, dict):
            event_name = str(message.get("name")) if "name" in message else None
            payload = message.get("args", message.get("data"))

        if event_name != "telemetry_update" or not isinstance(payload, dict):
            return None

        value = payload.get("current_power")
        if isinstance(value, (int, float)):
            return float(value)
        return None

    def do_step(self, current_time: float, step_size: float) -> bool:
        del current_time, step_size

        client = self._ensure_client()
        if client is None:
            return True

        try:
            client.emit(
                "set_angles",
                {"pan": float(self.in_target_pan), "tilt": float(self.in_target_tilt)},
            )

            deadline = time.monotonic() + 0.25
            while time.monotonic() < deadline:
                timeout = max(0.0, deadline - time.monotonic())
                message = client.receive(timeout=timeout)
                power = self._extract_power(message)
                if power is not None:
                    self.out_current_power = power
                    break
        except Exception:
            if self._client is not None:
                try:
                    self._client.disconnect()
                except Exception:
                    pass
            self._client = None

        return True
