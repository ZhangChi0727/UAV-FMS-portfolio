"""B0 G1 rotational rigid-body plant with fixed-step RK4 integration."""

from __future__ import annotations

from typing import Any

import numpy as np

try:
    from .contract import (
        ContractValidationError,
        G1Parameters,
        PlantInitialState,
        PlantState,
        _scalar,
        _vector,
        load_g1_parameters,
    )
    from .quaternion import normalize_quaternion, quaternion_multiply
except ImportError:  # pragma: no cover - supports direct track execution
    from contract import (
        ContractValidationError,
        G1Parameters,
        PlantInitialState,
        PlantState,
        _scalar,
        _vector,
        load_g1_parameters,
    )
    from quaternion import normalize_quaternion, quaternion_multiply


class Plant:
    """Integrate ``I*dot(omega)+omega x (I omega)=tau`` in body FRD axes."""

    def __init__(self, parameters: G1Parameters | None = None) -> None:
        self._parameters = parameters or load_g1_parameters()
        self._inertia = self._parameters.inertia_kg_m2
        self._inertia_inverse = np.linalg.inv(self._inertia)
        self._state: PlantState | None = None
        self._last_reset_epoch: float | None = None
        self._epoch_origin_s: float | None = None
        self._local_tick = 0
        self._mode: str | None = None

    @property
    def parameters(self) -> G1Parameters:
        return self._parameters

    @property
    def epoch_origin_s(self) -> float:
        if self._epoch_origin_s is None:
            raise ContractValidationError("plant must be reset before use")
        return self._epoch_origin_s

    @property
    def local_tick(self) -> int:
        if self._state is None:
            raise ContractValidationError("plant must be reset before use")
        return self._local_tick

    @property
    def state(self) -> PlantState:
        if self._state is None:
            raise ContractValidationError("plant must be reset before use")
        return PlantState(self._state.q_nb, self._state.omega_b_rad_s, self._state.timestamp_s)

    def reset(self, initial_state: PlantInitialState, reset_epoch: Any) -> PlantState:
        if not isinstance(initial_state, PlantInitialState):
            raise ContractValidationError("reset requires PlantInitialState")
        epoch = _scalar(reset_epoch, "reset_epoch")
        current_timestamp = self._state.timestamp_s if self._state is not None else self._last_reset_epoch
        if current_timestamp is not None and epoch < current_timestamp - 1e-12:
            raise ContractValidationError("reset epoch cannot move the scenario clock backwards")
        q = normalize_quaternion(initial_state.q_nb)
        self._state = PlantState(q, initial_state.omega_b_rad_s, epoch)
        self._last_reset_epoch = epoch
        self._epoch_origin_s = epoch
        self._local_tick = 0
        self._mode = None
        return self.state

    def step(self, actual_torque_body_Nm: Any, dt_s: Any) -> PlantState:
        if self._state is None:
            raise ContractValidationError("plant must be reset before use")
        if self._mode == "g0":
            raise ContractValidationError("cannot mix G0 tick steps with oracle substeps")
        torque = _vector(actual_torque_body_Nm, 3, "actual_torque_body_Nm")
        dt = _scalar(dt_s, "dt_s")
        if dt <= 0.0:
            raise ContractValidationError("dt_s must be strictly positive")
        state = self._advance(torque, dt, self._state.timestamp_s + dt)
        self._mode = "oracle"
        return state

    def _advance(self, torque: np.ndarray, dt: float, next_timestamp: float) -> PlantState:
        q0 = self._state.q_nb
        omega0 = self._state.omega_b_rad_s

        def derivative(q: np.ndarray, omega: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
            quaternion_rate = 0.5 * quaternion_multiply(q, [0.0, *omega])
            angular_rate = self._inertia_inverse @ (torque - np.cross(omega, self._inertia @ omega))
            return quaternion_rate, angular_rate

        k1_q, k1_w = derivative(q0, omega0)
        k2_q, k2_w = derivative(q0 + 0.5 * dt * k1_q, omega0 + 0.5 * dt * k1_w)
        k3_q, k3_w = derivative(q0 + 0.5 * dt * k2_q, omega0 + 0.5 * dt * k2_w)
        k4_q, k4_w = derivative(q0 + dt * k3_q, omega0 + dt * k3_w)
        q_next = q0 + (dt / 6.0) * (k1_q + 2.0 * k2_q + 2.0 * k3_q + k4_q)
        omega_next = omega0 + (dt / 6.0) * (k1_w + 2.0 * k2_w + 2.0 * k3_w + k4_w)
        if not np.all(np.isfinite(q_next)) or not np.all(np.isfinite(omega_next)):
            raise ContractValidationError("plant integration produced non-finite state")
        self._state = PlantState(
            normalize_quaternion(q_next),
            omega_next,
            next_timestamp,
        )
        return self.state

    def step_base(self, actual_torque_body_Nm: Any, dt_s: Any | None = None) -> PlantState:
        """Integrate one G0 base interval; ``step`` remains an oracle substep."""

        dt = self._parameters.base_period_s if dt_s is None else _scalar(dt_s, "dt_s")
        if abs(dt - self._parameters.base_period_s) > 1e-12:
            raise ContractValidationError("G0 plant step must use base_period_s")
        if self._state is None:
            raise ContractValidationError("plant must be reset before use")
        if self._mode == "oracle":
            raise ContractValidationError("cannot mix oracle substeps with G0 tick steps")
        torque = _vector(actual_torque_body_Nm, 3, "actual_torque_body_Nm")
        next_tick = self._local_tick + 1
        next_timestamp = self.epoch_origin_s + next_tick * self._parameters.base_period_s
        state = self._advance(torque, dt, next_timestamp)
        self._mode = "g0"
        self._local_tick = next_tick
        return state


__all__ = ["Plant"]
