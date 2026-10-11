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

from actuator import Actuator
from contract import (
    ActuatorInitialState,
    G1Parameters,
    IMUInitialState,
    PlantInitialState,
    SensorTruth,
    TorqueCommand,
    load_g1_parameters,
)
from imu import IMU
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
    actuator = Actuator(parameters)
    actuator.reset(ActuatorInitialState(), 0.0)
    target = np.array([0.1, -0.1, 0.05])
    actuator_dt = 0.015
    command = TorqueCommand(
        target,
        target,
        0.0,
        limits_Nm=parameters.actuator_limits_Nm,
    )
    actuator_feedback = actuator.step(command, actuator_dt)
    actuator_reference = target * (
        1.0 - np.exp(-actuator_dt / parameters.actuator_time_constant_s)
    )
    zero_noise_parameters = G1Parameters(
        inertia_kg_m2=parameters.inertia_kg_m2,
        actuator_time_constant_s=parameters.actuator_time_constant_s,
        actuator_limits_Nm=parameters.actuator_limits_Nm,
        gravity_n_m_s2=parameters.gravity_n_m_s2,
        gyro_noise_std_rad_s=np.zeros(3),
        gyro_bias_rad_s=np.zeros(3),
        accelerometer_noise_std_m_s2=np.zeros(3),
        accelerometer_bias_m_s2=np.zeros(3),
    )
    imu = IMU(zero_noise_parameters)
    imu.reset(IMUInitialState(), 0.0, 7)
    stationary = imu.sample(
        SensorTruth([1.0, 0.0, 0.0, 0.0], np.zeros(3), np.zeros(3)),
        0.002,
    )
    imu_a = IMU(parameters)
    imu_b = IMU(parameters)
    imu_a.reset(IMUInitialState(), 0.0, 7)
    imu_b.reset(IMUInitialState(), 0.0, 7)
    replay_truth = SensorTruth([1.0, 0.0, 0.0, 0.0], [0.1, 0.2, 0.3], [1.0, -2.0, 0.5])
    replay_a = imu_a.sample(replay_truth, 0.002)
    replay_b = imu_b.sample(replay_truth, 0.002)
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
        "actuator": {
            "zoh_dt_s": actuator_dt,
            "zoh_max_error_Nm": float(np.max(np.abs(actuator_feedback.actual_torque_body_Nm - actuator_reference))),
        },
        "imu": {
            "stationary_specific_force_error_m_s2": float(
                np.max(np.abs(stationary.specific_force_b_m_s2 - [0.0, 0.0, -9.80665]))
            ),
            "same_seed_replay_equal": bool(
                np.array_equal(replay_a.gyro_b_rad_s, replay_b.gyro_b_rad_s)
                and np.array_equal(replay_a.specific_force_b_m_s2, replay_b.specific_force_b_m_s2)
            ),
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
