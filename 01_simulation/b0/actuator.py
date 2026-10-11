"""B0 G1 bounded first-order actuator with exact ZOH propagation."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

try:
    from .contract import (
        ActuatorFeedback,
        ActuatorInitialState,
        ContractValidationError,
        G1Parameters,
        TorqueCommand,
        _scalar,
        load_g1_parameters,
    )
except ImportError:  # pragma: no cover - supports direct track execution
    from contract import (
        ActuatorFeedback,
        ActuatorInitialState,
        ContractValidationError,
        G1Parameters,
        TorqueCommand,
        _scalar,
        load_g1_parameters,
    )


class Actuator:
    """Advance only the controller-paired limited target; never re-clamp it."""

    def __init__(self, parameters: G1Parameters | None = None) -> None:
        self._parameters = parameters or load_g1_parameters()
        self._limits = self._parameters.actuator_limits_Nm
        self._time_constant = self._parameters.actuator_time_constant_s
        self._actual = np.zeros(3, dtype=np.float64)
        self._target = np.zeros(3, dtype=np.float64)
        self._command_timestamp = 0.0
        self._timestamp = 0.0
        self._reset = False

    @property
    def parameters(self) -> G1Parameters:
        return self._parameters

    @property
    def feedback(self) -> ActuatorFeedback:
        if not self._reset:
            raise ContractValidationError("actuator must be reset before use")
        return ActuatorFeedback(
            self._actual,
            self._target,
            self._command_timestamp,
            self._timestamp,
        )

    def reset(self, initial_state: ActuatorInitialState, reset_epoch: Any) -> ActuatorFeedback:
        if not isinstance(initial_state, ActuatorInitialState):
            raise ContractValidationError("reset requires ActuatorInitialState")
        epoch = _scalar(reset_epoch, "reset_epoch")
        actual = initial_state.actual_torque_body_Nm
        target = initial_state.held_limited_torque_body_Nm
        if np.any(np.abs(actual) > self._limits + 1e-12):
            raise ContractValidationError("initial actual torque exceeds actuator limits")
        if np.any(np.abs(target) > self._limits + 1e-12):
            raise ContractValidationError("initial limited torque exceeds actuator limits")
        command_timestamp = initial_state.held_command_timestamp_s
        self._actual = actual
        self._target = target
        self._command_timestamp = epoch if command_timestamp is None else command_timestamp
        if self._command_timestamp > epoch + 1e-12:
            raise ContractValidationError("held command timestamp cannot be after reset epoch")
        self._timestamp = epoch
        self._reset = True
        return self.feedback

    def step(self, torque_command: TorqueCommand, dt_s: Any) -> ActuatorFeedback:
        if not self._reset:
            raise ContractValidationError("actuator must be reset before use")
        if not isinstance(torque_command, TorqueCommand):
            raise ContractValidationError("step requires TorqueCommand")
        dt = _scalar(dt_s, "dt_s")
        if dt <= 0.0:
            raise ContractValidationError("dt_s must be strictly positive")
        target = torque_command.limited_torque_body_Nm
        if np.any(np.abs(target) > self._limits + 1e-12):
            raise ContractValidationError("limited torque exceeds actuator limits; actuator does not clamp")
        if torque_command.command_timestamp_s < self._command_timestamp - 1e-12:
            raise ContractValidationError("command timestamps must be non-decreasing")
        if torque_command.command_timestamp_s > self._timestamp + 1e-12:
            raise ContractValidationError("command timestamp cannot be in the future")
        next_actual = target + (self._actual - target) * math.exp(-dt / self._time_constant)
        if not np.all(np.isfinite(next_actual)):
            raise ContractValidationError("actuator propagation produced non-finite state")
        self._actual = next_actual
        self._target = target
        self._command_timestamp = torque_command.command_timestamp_s
        self._timestamp += dt
        return self.feedback


__all__ = ["Actuator"]
