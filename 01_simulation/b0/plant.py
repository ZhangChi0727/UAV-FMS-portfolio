"""B0 G1 rotational rigid-body plant with fixed-step RK4 integration."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

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

    @property
    def parameters(self) -> G1Parameters:
        return self._parameters

    @property
    def state(self) -> PlantState:
        if self._state is None:
            raise ContractValidationError("plant must be reset before use")
        return PlantState(self._state.q_nb, self._state.omega_b_rad_s, self._state.timestamp_s)

    def reset(self, initial_state: PlantInitialState, reset_epoch: Any) -> PlantState:
        if not isinstance(initial_state, PlantInitialState):
            raise ContractValidationError("reset requires PlantInitialState")
        epoch = _scalar(reset_epoch, "reset_epoch")
        q = normalize_quaternion(initial_state.q_nb)
        self._state = PlantState(q, initial_state.omega_b_rad_s, epoch)
        return self.state

    def step(self, actual_torque_body_Nm: Any, dt_s: Any) -> PlantState:
        if self._state is None:
            raise ContractValidationError("plant must be reset before use")
        torque = _vector(actual_torque_body_Nm, 3, "actual_torque_body_Nm")
        dt = _scalar(dt_s, "dt_s")
        if dt <= 0.0:
            raise ContractValidationError("dt_s must be strictly positive")
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
            self._state.timestamp_s + dt,
        )
        return self.state


__all__ = ["Plant"]
