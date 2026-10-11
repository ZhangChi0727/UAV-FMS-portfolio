"""Emit compact, deterministic G1 component evidence.

This script reports only component-oracle errors and provenance. It does not
claim closed-loop, real-time, HIL, flight, or statistical performance.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import argparse
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


def _actuator_evidence(parameters) -> dict[str, object]:
    dt = parameters.base_period_s
    duration = 0.05
    steps = round(duration / dt)
    errors = []
    for axis in range(3):
        for sign in (-1.0, 1.0):
            target = np.zeros(3)
            target[axis] = sign * parameters.actuator_limits_Nm[axis]
            saturated = np.zeros(3, dtype=bool)
            command = TorqueCommand(
                target,
                target,
                0.0,
                saturated,
                limits_Nm=parameters.actuator_limits_Nm,
            )
            actuator = Actuator(parameters)
            actuator.reset(
                ActuatorInitialState(
                    actual_torque_body_Nm=np.zeros(3),
                    held_limited_torque_body_Nm=target,
                    held_command_timestamp_s=0.0,
                    held_saturated=saturated,
                    held_requested_torque_body_Nm=target,
                ),
                0.0,
            )
            for _ in range(steps):
                feedback = actuator.step(command, dt)
            reference = target * (1.0 - np.exp(-duration / parameters.actuator_time_constant_s))
            errors.append(float(np.max(np.abs(feedback.actual_torque_body_Nm - reference))))
    return {
        "dt_s": dt,
        "duration_s": duration,
        "steps": steps,
        "signed_axis_max_error_Nm": max(errors),
        "tolerance_Nm": 1e-12,
        "gate_pass": max(errors) <= 1e-12,
    }


def _imu_evidence(parameters) -> dict[str, object]:
    zero_noise_parameters = G1Parameters(
        inertia_kg_m2=parameters.inertia_kg_m2,
        actuator_time_constant_s=parameters.actuator_time_constant_s,
        actuator_limits_Nm=parameters.actuator_limits_Nm,
        gravity_n_m_s2=parameters.gravity_n_m_s2,
        gyro_noise_std_rad_s=np.zeros(3),
        gyro_bias_rad_s=np.zeros(3),
        accelerometer_noise_std_m_s2=np.zeros(3),
        accelerometer_bias_m_s2=np.zeros(3),
        base_period_s=parameters.base_period_s,
        imu_period_ticks=parameters.imu_period_ticks,
    )
    imu = IMU(zero_noise_parameters)
    imu.reset(IMUInitialState(), 0.0, 7)
    stationary = imu.sample(
        SensorTruth([1.0, 0.0, 0.0, 0.0], np.zeros(3), np.zeros(3)),
        parameters.imu_period_s,
    )
    imu_a = IMU(parameters)
    imu_b = IMU(parameters)
    seed = 7
    imu_a.reset(IMUInitialState(), 0.0, seed)
    imu_b.reset(IMUInitialState(), 0.0, seed)
    replay_truth = SensorTruth([1.0, 0.0, 0.0, 0.0], [0.1, 0.2, 0.3], [1.0, -2.0, 0.5])
    replay_a = imu_a.sample(replay_truth, parameters.imu_period_s)
    replay_b = imu_b.sample(replay_truth, parameters.imu_period_s)
    stationary_error = float(
        np.max(np.abs(stationary.specific_force_b_m_s2 - [0.0, 0.0, -parameters.gravity_n_m_s2[2]]))
    )
    replay_equal = bool(
        np.array_equal(replay_a.gyro_b_rad_s, replay_b.gyro_b_rad_s)
        and np.array_equal(replay_a.specific_force_b_m_s2, replay_b.specific_force_b_m_s2)
    )
    return {
        "period_s": parameters.imu_period_s,
        "period_ticks": parameters.imu_period_ticks,
        "seed": seed,
        "stationary_specific_force_error_m_s2": stationary_error,
        "stationary_tolerance_m_s2": 1e-12,
        "stationary_gate_pass": stationary_error <= 1e-12,
        "same_seed_replay_equal": replay_equal,
        "replay_gate_pass": replay_equal,
    }


def _build_evidence() -> dict[str, object]:
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
    actuator_evidence = _actuator_evidence(parameters)
    imu_evidence = _imu_evidence(parameters)
    coarse_attitude_error = quaternion_distance_rad(reference_q, coarse_q)
    half_attitude_error = quaternion_distance_rad(reference_q, half_q)
    coarse_rate_error = float(np.linalg.norm(coarse_omega - reference_omega))
    half_rate_error = float(np.linalg.norm(half_omega - reference_omega))
    rounding_floor = 1e-15
    attitude_refinement = (
        "reduced"
        if half_attitude_error < coarse_attitude_error
        else "indistinguishable_roundoff"
        if max(coarse_attitude_error, half_attitude_error) <= rounding_floor
        else "not_reduced"
    )
    rate_refinement = (
        "reduced"
        if half_rate_error < coarse_rate_error
        else "indistinguishable_roundoff"
        if max(coarse_rate_error, half_rate_error) <= rounding_floor
        else "not_reduced"
    )
    evidence = {
        "record": "b0-g1-component-evidence",
        "scope": ["plant", "actuator_contract_consumption", "imu_contract_boundary"],
        "closed_loop_or_hil_or_flight_claim": False,
        "git_sha": _git_sha(),
        "config_sha256": config_hash,
        "python": sys.version.split()[0],
        "parameters": {
            "base_period_s": parameters.base_period_s,
            "imu_period_ticks": parameters.imu_period_ticks,
            "imu_period_s": parameters.imu_period_s,
            "actuator_time_constant_s": parameters.actuator_time_constant_s,
            "actuator_limits_Nm": parameters.actuator_limits_Nm.tolist(),
            "imu_seed": 7,
        },
        "principal_axis": principal_axis_errors,
        "rk4": {
            "coarse_dt_s": 0.0025,
            "half_dt_s": 0.00125,
            "reference_dt_s": 0.00015625,
            "coarse_attitude_error_rad": coarse_attitude_error,
            "half_attitude_error_rad": half_attitude_error,
            "coarse_rate_error_rad_s": coarse_rate_error,
            "half_rate_error_rad_s": half_rate_error,
            "rounding_floor": rounding_floor,
            "attitude_refinement": attitude_refinement,
            "rate_refinement": rate_refinement,
            "endpoint_gate_pass": (
                coarse_attitude_error <= 1e-8
                and half_attitude_error <= 1e-8
                and coarse_rate_error <= 1e-8
                and half_rate_error <= 1e-8
            ),
        },
        "actuator": actuator_evidence,
        "imu": imu_evidence,
        "principal_axis_gate_pass": all(
            item["omega_error_rad_s"] <= 1e-10 and item["attitude_error_rad"] <= 1e-10
            for item in principal_axis_errors
        ),
        "tolerances": {
            "principal_axis_omega_rad_s": 1e-10,
            "principal_axis_attitude_rad": 1e-10,
            "rk4_endpoint_attitude_rad": 1e-8,
            "rk4_endpoint_rate_rad_s": 1e-8,
        },
    }
    evidence["all_component_gates_pass"] = bool(
        evidence["principal_axis_gate_pass"]
        and evidence["rk4"]["endpoint_gate_pass"]
        and evidence["actuator"]["gate_pass"]
        and evidence["imu"]["stationary_gate_pass"]
        and evidence["imu"]["replay_gate_pass"]
        and attitude_refinement in {"reduced", "indistinguishable_roundoff"}
        and rate_refinement in {"reduced", "indistinguishable_roundoff"}
    )
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser(description="Emit deterministic B0 G1 component evidence")
    parser.add_argument("--output", type=Path, help="optional JSON evidence output path")
    args = parser.parse_args()
    evidence = _build_evidence()
    rendered = json.dumps(evidence, indent=2, sort_keys=True)
    print(rendered)
    if args.output is not None:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    if not evidence["all_component_gates_pass"]:
        raise SystemExit("G1 component evidence gate failed")


if __name__ == "__main__":
    main()
