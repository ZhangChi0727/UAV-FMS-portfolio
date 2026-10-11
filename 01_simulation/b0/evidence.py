"""Emit compact, deterministic G1 component evidence.

This script reports only component-oracle errors and provenance. It does not
claim closed-loop, real-time, HIL, flight, or statistical performance.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from contract import PlantInitialState, load_g1_parameters
from plant import Plant
from quaternion import quaternion_distance_rad, quaternion_from_axis_angle


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[2],
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def _integrate(parameters, timestep: float) -> tuple[np.ndarray, np.ndarray]:
    plant = Plant(parameters)
    plant.reset(PlantInitialState([1.0, 0.0, 0.0, 0.0], np.zeros(3)), 0.0)
    torque = np.array([0.01, -0.01, 0.005])
    for _ in range(round(0.05 / timestep)):
        state = plant.step(torque, timestep)
    return state.q_nb, state.omega_b_rad_s


def main() -> None:
    parameters = load_g1_parameters()
    config_path = Path(parameters.config_path)
    config_hash = hashlib.sha256(config_path.read_bytes()).hexdigest()
    principal_axis_errors = []
    for axis in range(3):
        torque = np.zeros(3)
        torque[axis] = 0.01
        plant = Plant(parameters)
        plant.reset(PlantInitialState([1.0, 0.0, 0.0, 0.0], np.zeros(3)), 0.0)
        for _ in range(40):
            state = plant.step(torque, 0.00025)
        expected_omega = torque[axis] * 0.01 / parameters.inertia_kg_m2[axis, axis]
        expected_angle = 0.5 * torque[axis] * 0.01**2 / parameters.inertia_kg_m2[axis, axis]
        expected_q = quaternion_from_axis_angle(np.eye(3)[axis], expected_angle)
        principal_axis_errors.append(
            {
                "axis": axis,
                "omega_error_rad_s": abs(state.omega_b_rad_s[axis] - expected_omega),
                "attitude_error_rad": quaternion_distance_rad(expected_q, state.q_nb),
            }
        )
    coarse_q, coarse_omega = _integrate(parameters, 0.0025)
    half_q, half_omega = _integrate(parameters, 0.00125)
    reference_q, reference_omega = _integrate(parameters, 0.00015625)
    evidence = {
        "record": "b0-g1-component-evidence",
        "scope": ["plant", "actuator_contract_consumption", "imu_contract_boundary"],
        "closed_loop_or_hil_or_flight_claim": False,
        "git_sha": _git_sha(),
        "config_sha256": config_hash,
        "python": sys.version.split()[0],
        "principal_axis": principal_axis_errors,
        "rk4": {
            "coarse_dt_s": 0.0025,
            "half_dt_s": 0.00125,
            "reference_dt_s": 0.00015625,
            "coarse_attitude_error_rad": quaternion_distance_rad(reference_q, coarse_q),
            "half_attitude_error_rad": quaternion_distance_rad(reference_q, half_q),
            "coarse_rate_error_rad_s": float(np.linalg.norm(coarse_omega - reference_omega)),
            "half_rate_error_rad_s": float(np.linalg.norm(half_omega - reference_omega)),
        },
        "tolerances": {
            "principal_axis_omega_rad_s": 1e-10,
            "principal_axis_attitude_rad": 1e-10,
            "rk4_endpoint_attitude_rad": 1e-8,
            "rk4_endpoint_rate_rad_s": 1e-8,
        },
    }
    print(json.dumps(evidence, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
