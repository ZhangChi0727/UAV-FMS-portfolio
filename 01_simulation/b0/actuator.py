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
        self._requested = np.zeros(3, dtype=np.float64)
        self._saturated = np.zeros(3, dtype=bool)
        self._command_timestamp = 0.0
        self._timestamp = 0.0
        self._last_reset_epoch: float | None = None
        self._epoch_origin_s: float | None = None
        self._local_tick = 0
        self._mode: str | None = None
        self._reset = False

    @property
    def parameters(self) -> G1Parameters:
        return self._parameters

    @property
    def epoch_origin_s(self) -> float:
        if not self._reset or self._epoch_origin_s is None:
            raise ContractValidationError("actuator must be reset before use")
        return self._epoch_origin_s

    @property
    def local_tick(self) -> int:
        if not self._reset:
            raise ContractValidationError("actuator must be reset before use")
        return self._local_tick

    @property
    def feedback(self) -> ActuatorFeedback:
        if not self._reset:
            raise ContractValidationError("actuator must be reset before use")
        return ActuatorFeedback(
            self._actual,
            self._target,
            self._saturated,
            self._timestamp,
            self._command_timestamp,
        )

    def reset(self, initial_state: ActuatorInitialState, reset_epoch: Any) -> ActuatorFeedback:
        if not isinstance(initial_state, ActuatorInitialState):
            raise ContractValidationError("reset requires ActuatorInitialState")
        epoch = _scalar(reset_epoch, "reset_epoch")
        actual = initial_state.actual_torque_body_Nm
        target = initial_state.held_limited_torque_body_Nm
        requested = initial_state.held_requested_torque_body_Nm
        saturated = initial_state.held_saturated
        if np.any(np.abs(actual) > self._limits + 1e-12):
            raise ContractValidationError("initial actual torque exceeds actuator limits")
        if np.any(np.abs(target) > self._limits + 1e-12):
            raise ContractValidationError("initial limited torque exceeds actuator limits")
        expected_target = np.clip(requested, -self._limits, self._limits)
        if not np.allclose(target, expected_target, rtol=0.0, atol=1e-12):
            raise ContractValidationError("initial reset torque fields are not paired")
        if not np.array_equal(saturated, np.abs(requested) > self._limits):
            raise ContractValidationError("initial reset saturation flag is not paired")
        command_timestamp = initial_state.held_command_timestamp_s
        command_timestamp = epoch if command_timestamp is None else command_timestamp
        if abs(command_timestamp - epoch) > 1e-12:
            raise ContractValidationError("reset command timestamp must equal reset epoch")
        current_timestamp = self._timestamp if self._reset else self._last_reset_epoch
        if current_timestamp is not None and epoch < current_timestamp - 1e-12:
            raise ContractValidationError("reset epoch cannot move the scenario clock backwards")
        self._actual = actual.copy()
        self._target = target.copy()
        self._requested = requested.copy()
        self._saturated = saturated.copy()
        self._command_timestamp = command_timestamp
        self._timestamp = epoch
        self._last_reset_epoch = epoch
        self._epoch_origin_s = epoch
        self._local_tick = 0
        self._mode = None
        self._reset = True
        return self.feedback

    def step(self, torque_command: TorqueCommand, dt_s: Any) -> ActuatorFeedback:
        if not self._reset:
            raise ContractValidationError("actuator must be reset before use")
        if not isinstance(torque_command, TorqueCommand):
            raise ContractValidationError("step requires TorqueCommand")
        if self._mode == "g0":
            raise ContractValidationError("cannot mix G0 tick steps with oracle ZOH steps")
        dt = _scalar(dt_s, "dt_s")
        if dt <= 0.0:
            raise ContractValidationError("dt_s must be strictly positive")
        target = torque_command.limited_torque_body_Nm
        if np.any(np.abs(target) > self._limits + 1e-12):
            raise ContractValidationError("limited torque exceeds actuator limits; actuator does not clamp")
        expected_target = np.clip(torque_command.requested_torque_body_Nm, -self._limits, self._limits)
        if not np.allclose(target, expected_target, rtol=0.0, atol=1e-12):
            raise ContractValidationError("torque command was paired with a different actuator limit")
        if not np.array_equal(torque_command.saturated, np.abs(torque_command.requested_torque_body_Nm) > self._limits):
            raise ContractValidationError("torque command saturation flag uses a different actuator limit")
        timestamp = torque_command.timestamp_s
        if timestamp < self._command_timestamp - 1e-12:
            raise ContractValidationError("command timestamps must be non-decreasing")
        if timestamp > self._timestamp + 1e-12:
            raise ContractValidationError("command timestamp cannot be in the future")
        same_timestamp = abs(timestamp - self._command_timestamp) <= 1e-12
        if same_timestamp and (
            not np.array_equal(torque_command.requested_torque_body_Nm, self._requested)
            or not np.array_equal(target, self._target)
            or not np.array_equal(torque_command.saturated, self._saturated)
        ):
            raise ContractValidationError("a held command timestamp cannot carry a different command")
        next_actual = target + (self._actual - target) * math.exp(-dt / self._time_constant)
        if not np.all(np.isfinite(next_actual)):
            raise ContractValidationError("actuator propagation produced non-finite state")
        self._actual = next_actual
        self._target = target
        self._requested = torque_command.requested_torque_body_Nm
        self._saturated = torque_command.saturated
        self._command_timestamp = timestamp
        self._timestamp += dt
        self._mode = "oracle"
        return self.feedback

    def step_base(self, torque_command: TorqueCommand, dt_s: Any | None = None) -> ActuatorFeedback:
        """Consume one G0 base interval; ``step`` remains an explicit ZOH oracle."""

        dt = self._parameters.base_period_s if dt_s is None else _scalar(dt_s, "dt_s")
        if abs(dt - self._parameters.base_period_s) > 1e-12:
            raise ContractValidationError("G0 actuator step must use base_period_s")
        if not self._reset:
            raise ContractValidationError("actuator must be reset before use")
        if self._mode == "oracle":
            raise ContractValidationError("cannot mix oracle ZOH steps with G0 tick steps")
        current_tick = self._local_tick
        previous_mode = self._mode
        self._mode = None
        try:
            self.step(torque_command, dt)
        except Exception:
            self._mode = previous_mode
            raise
        self._mode = "g0"
        self._local_tick = current_tick + 1
        self._timestamp = self.epoch_origin_s + self._local_tick * self._parameters.base_period_s
        return self.feedback


__all__ = ["Actuator"]
