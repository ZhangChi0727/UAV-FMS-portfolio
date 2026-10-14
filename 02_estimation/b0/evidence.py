"""Generate deterministic G2-A component observations for independent review."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

import numpy as np

from estimator import AttitudeEstimator, EstimatorInitialState, ResetEpoch, load_estimator_parameters


class Sample:
    def __init__(self, timestamp_s, gyro=(0.0, 0.0, 0.0), force=(0.0, 0.0, -9.80665), valid=True):
        self.timestamp_s = timestamp_s
        self.gyro_b_rad_s = np.asarray(gyro, dtype=np.float64)
        self.specific_force_b_m_s2 = np.asarray(force, dtype=np.float64)
        self.valid = valid


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_commit(repo: Path) -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()


def _axis_angle(vector) -> np.ndarray:
    vector = np.asarray(vector, dtype=np.float64)
    angle = float(np.linalg.norm(vector))
    if angle == 0.0:
        return np.array([1.0, 0.0, 0.0, 0.0])
    return np.r_[math.cos(angle / 2.0), math.sin(angle / 2.0) * vector / angle]


def _multiply(left, right) -> np.ndarray:
    lw, lx, ly, lz = np.asarray(left, dtype=np.float64)
    rw, rx, ry, rz = np.asarray(right, dtype=np.float64)
    return np.array(
        [
            lw * rw - lx * rx - ly * ry - lz * rz,
            lw * rx + lx * rw + ly * rz - lz * ry,
            lw * ry - lx * rz + ly * rw + lz * rx,
            lw * rz + lx * ry - ly * rx + lz * rw,
        ]
    )


def build_evidence() -> dict:
    track = Path(__file__).resolve().parent
    repo = track.parents[1]
    parameters = load_estimator_parameters()

    propagation = AttitudeEstimator(parameters)
    propagation.reset(EstimatorInitialState((1, 0, 0, 0), (0, 0, 0)), ResetEpoch(0, 0.0), 7)
    propagated = propagation.step(Sample(0.005, gyro=(0.3, -0.2, 0.1), force=(0, 0, 0)))
    rotation_vector = np.array([0.3, -0.2, 0.1]) * 0.005
    angle = float(np.linalg.norm(rotation_vector))
    expected = np.r_[math.cos(angle / 2), math.sin(angle / 2) * rotation_vector / angle]

    roll_initial = _axis_angle([0.1, 0.0, 0.0])
    fusion = AttitudeEstimator(parameters)
    fusion.reset(EstimatorInitialState(roll_initial, (0, 0, 0)), ResetEpoch(0, 0.0), 7)
    fused = fusion.process(Sample(0.005))
    innovation = np.array([-math.sin(0.1), 0.0, 0.0])
    fusion_expected = _multiply(roll_initial, _axis_angle(0.005 * innovation))
    fusion_expected /= np.linalg.norm(fusion_expected)

    yaw_initial = _axis_angle([0.0, 0.0, 0.4])
    yaw = AttitudeEstimator(parameters)
    yaw.reset(EstimatorInitialState(yaw_initial, (0, 0, 0)), ResetEpoch(0, 0.0), 7)
    yaw_output = yaw.step(Sample(0.005))

    gate_upper = parameters.gravity_m_s2 + parameters.accelerometer_gate_deviation_m_s2
    gate_inside_force = [math.nextafter(gate_upper, parameters.gravity_m_s2), 0.0, 0.0]
    gate_outside_force = [math.nextafter(gate_upper, math.inf), 0.0, 0.0]
    gate_inside_norm = float(np.linalg.norm(gate_inside_force))
    gate_outside_norm = float(np.linalg.norm(gate_outside_force))
    gate_inside = AttitudeEstimator(parameters)
    gate_inside.reset(EstimatorInitialState((1, 0, 0, 0), (0, 0, 0)), ResetEpoch(0, 0.0), 7)
    gate_inside_result = gate_inside.process(Sample(0.005, force=gate_inside_force))
    gate_outside = AttitudeEstimator(parameters)
    gate_outside.reset(EstimatorInitialState((1, 0, 0, 0), (0, 0, 0)), ResetEpoch(0, 0.0), 7)
    gate_outside_result = gate_outside.process(Sample(0.005, force=gate_outside_force))

    gap = AttitudeEstimator(parameters)
    gap.reset(EstimatorInitialState((1, 0, 0, 0), (0, 0, 0)), ResetEpoch(4, 12.0), 7)
    gap.step(Sample(12.005, force=(0, 0, 0)))
    rejected_a = gap.process(Sample(12.010, valid=False)).diagnostics
    rejected_b = gap.process(Sample(12.015, valid=False)).diagnostics
    recovered = gap.process(Sample(12.020, force=(9.80665, 0, 0)))

    atomic = AttitudeEstimator(parameters)
    atomic.reset(EstimatorInitialState((1, 0, 0, 0), (0, 0, 0)), ResetEpoch(0, 0.0), 7)
    before = atomic.estimate
    rejection = atomic.process(Sample(0.005, gyro=(math.nan, 0, 0))).diagnostics
    after = atomic.estimate

    config = track / "configs/b0_g2_estimator.v1.json"
    approval = track / "configs/b0_g2_estimator_approval.v1.json"
    return {
        "schema_version": "b0-g2a-estimator-evidence/v1",
        "source_commit": _source_commit(repo),
        "component": "B0 G2-A six-axis attitude estimator",
        "configuration": {
            "implementation_path": str(config.relative_to(repo)).replace("\\", "/"),
            "implementation_sha256": _sha256(config),
            "approval_path": str(approval.relative_to(repo)).replace("\\", "/"),
            "approval_sha256": _sha256(approval),
            "g0_path": str(Path(parameters.g0_config_path).relative_to(repo)).replace("\\", "/"),
        },
        "environment": {"numpy": np.__version__, "float": "float64", "seed_interface": 7},
        "observations": {
            "propagation": {
                "input_rate_rad_s": [0.3, -0.2, 0.1],
                "dt_s": 0.005,
                "actual_q_nb": propagated.q_nb_estimate.tolist(),
                "independent_expected_q_nb": expected.tolist(),
                "max_component_abs_error": float(np.max(np.abs(propagated.q_nb_estimate - expected))),
                "norm_error": abs(float(np.linalg.norm(propagated.q_nb_estimate)) - 1.0),
            },
            "gap_recovery": {
                "rejected_reasons": [rejected_a.reason, rejected_b.reason],
                "diagnostics": recovered.diagnostics.__dict__,
                "q_nb": recovered.estimate.q_nb_estimate.tolist(),
            },
            "tilt_fusion": {
                "initial_roll_rad": 0.1,
                "actual_q_nb": fused.estimate.q_nb_estimate.tolist(),
                "independent_expected_q_nb": fusion_expected.tolist(),
                "max_component_abs_error": float(np.max(np.abs(fused.estimate.q_nb_estimate - fusion_expected))),
                "correction_applied": fused.diagnostics.correction_applied,
            },
            "yaw_limitation": {
                "initial_yaw_rad": 0.4,
                "actual_q_nb": yaw_output.q_nb_estimate.tolist(),
                "initial_q_nb": yaw_initial.tolist(),
                "max_component_abs_change": float(np.max(np.abs(yaw_output.q_nb_estimate - yaw_initial))),
            },
            "acceleration_contamination_gate": {
                "gravity_m_s2": parameters.gravity_m_s2,
                "maximum_absolute_deviation_m_s2": parameters.accelerometer_gate_deviation_m_s2,
                "boundary": "inclusive",
                "inside": {
                    "specific_force_b_m_s2": gate_inside_force,
                    "computed_norm_m_s2": gate_inside_norm,
                    "independent_expected_eligible": abs(gate_inside_norm - parameters.gravity_m_s2)
                    <= parameters.accelerometer_gate_deviation_m_s2,
                    "diagnostics": gate_inside_result.diagnostics.__dict__,
                },
                "outside": {
                    "specific_force_b_m_s2": gate_outside_force,
                    "computed_norm_m_s2": gate_outside_norm,
                    "independent_expected_eligible": abs(gate_outside_norm - parameters.gravity_m_s2)
                    <= parameters.accelerometer_gate_deviation_m_s2,
                    "diagnostics": gate_outside_result.diagnostics.__dict__,
                },
                "limitation_classification": "selected_module_cases_only_near_g_lateral_acceleration_can_be_indistinguishable",
            },
            "atomic_rejection": {
                "reason": rejection.reason,
                "q_unchanged": bool(np.array_equal(before.q_nb_estimate, after.q_nb_estimate)),
                "timestamp_unchanged": before.timestamp_s == after.timestamp_s,
            },
        },
        "criteria": {
            "propagation_component_abs_le_1e_12": float(np.max(np.abs(propagated.q_nb_estimate - expected))) <= 1e-12,
            "propagation_norm_abs_le_1e_12": abs(float(np.linalg.norm(propagated.q_nb_estimate)) - 1.0) <= 1e-12,
            "gap_elapsed_periods_is_3": recovered.diagnostics.elapsed_periods == 3,
            "gap_missing_periods_is_2": recovered.diagnostics.missing_periods == 2,
            "gap_correction_is_capped": recovered.diagnostics.correction_capped,
            "tilt_fusion_component_abs_le_1e_12": float(np.max(np.abs(fused.estimate.q_nb_estimate - fusion_expected))) <= 1e-12,
            "gravity_does_not_supply_absolute_yaw": float(np.max(np.abs(yaw_output.q_nb_estimate - yaw_initial))) <= 1e-12,
            "contamination_gate_inside_is_eligible": gate_inside_result.diagnostics.correction_eligible,
            "contamination_gate_outside_is_ineligible": not gate_outside_result.diagnostics.correction_eligible,
            "invalid_input_is_atomic": bool(np.array_equal(before.q_nb_estimate, after.q_nb_estimate)) and before.timestamp_s == after.timestamp_s,
        },
        "limitations": [
            "Six-axis gravity fusion does not observe absolute yaw.",
            "Norm gating cannot distinguish every near-g lateral acceleration.",
            "Gap recovery holds the newest gyro measurement across the unobserved interval.",
            "This is component evidence, not G3 closed-loop performance evidence.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evidence = build_evidence()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not all(evidence["criteria"].values()):
        raise SystemExit("G2-A evidence criterion failed")


if __name__ == "__main__":
    main()
