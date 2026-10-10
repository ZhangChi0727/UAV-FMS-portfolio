"""Strict validation for the proposed B0 G0 configuration contract.

The module deliberately validates declarative inputs only.  It neither models the
vehicle nor evaluates estimator/controller performance.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "b0-g0-contract/v1"

EXPECTED_SCENARIOS = {
    "stationary_zero_command": "in_envelope_performance",
    "initial_attitude_offset": "in_envelope_performance",
    "tri_axis_signed_steps": "in_envelope_performance",
    "external_torque_disturbance": "in_envelope_performance",
    "imu_noise_and_bias": "in_envelope_performance",
    "saturation_withdrawal": "in_envelope_performance",
    "acceleration_contamination": "limitation_characterization",
    "invalid_input_and_reset": "invalid_input",
}

REQUIRED_SEQUENCE = [
    "plant_consumes_actual_torque_for_interval",
    "actuator_advances_previous_limited_target",
    "imu_samples_interval_end_when_due",
    "estimator_consumes_imu_when_due",
    "controller_consumes_current_estimate_when_due",
    "controller_publishes_next_limited_target",
]

OBSERVATIONS = {
    "actuator_actual_torque_Nm",
    "controller_integral_Nm",
    "controller_requested_torque_Nm",
    "external_torque_Nm",
    "imu_gyro_rad_s",
    "imu_specific_force_m_s2",
    "limited_torque_Nm",
    "limitation_status",
    "omega_b_estimate_rad_s",
    "omega_b_truth_rad_s",
    "q_nb_command",
    "q_nb_estimate",
    "q_nb_truth",
    "rejection_reason",
    "requested_torque_Nm",
    "reset_epoch",
    "sample_validity",
}

METRIC_SPECS: dict[str, tuple[set[str], str, str]] = {
    "attitude_error_rad": ({"max_abs", "peak"}, "rad", "number"),
    "attitude_settling_time_s": ({"max"}, "s", "number"),
    "body_rate_error_rad_s": ({"max_abs", "rms"}, "rad/s", "number"),
    "quaternion_norm_error": ({"max_abs"}, "1", "number"),
    "tracking_settling_time_s": ({"max"}, "s", "number"),
    "tracking_overshoot_percent": ({"max"}, "%", "number"),
    "cross_axis_attitude_error_rad": ({"max_abs"}, "rad", "number"),
    "actuator_saturation_time_s": ({"total_time"}, "s", "number"),
    "roll_pitch_estimation_error_rad": ({"rms"}, "rad", "number"),
    "yaw_drift_rad_s": ({"max_abs"}, "rad/s", "number"),
    "controller_integral_Nm": ({"max_abs"}, "Nm", "number"),
    "limitation_event_recorded": ({"all"}, "bool", "bool"),
    "invalid_input_rejection_count": ({"min"}, "count", "number"),
    "reset_replay_match": ({"all"}, "bool", "bool"),
}

EVENT_FIELDS: dict[str, set[str]] = {
    "command_step": {"axis", "value_rad"},
    "external_torque": {"vector_Nm"},
    "imu_bias": {"gyro_bias_rad_s", "accelerometer_bias_m_s2"},
    "specific_force_disturbance": {"vector_m_s2"},
    "invalid_input": {"invalid_kind"},
    "reset": set(),
}

EXPECTED_EVENT_TYPES = {
    "stationary_zero_command": set(),
    "initial_attitude_offset": set(),
    "tri_axis_signed_steps": {"command_step"},
    "external_torque_disturbance": {"external_torque"},
    "imu_noise_and_bias": {"imu_bias"},
    "saturation_withdrawal": {"command_step"},
    "acceleration_contamination": {"specific_force_disturbance"},
    "invalid_input_and_reset": {"invalid_input", "reset"},
}


class ContractValidationError(ValueError):
    """A configuration contract is structurally or semantically invalid."""


def _fail(path: str, message: str) -> None:
    raise ContractValidationError(f"{path}: {message}")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _number(value: Any, path: str, *, positive: bool = False, nonnegative: bool = False) -> float:
    if not _is_number(value) or not math.isfinite(float(value)):
        _fail(path, "must be a finite number")
    numeric = float(value)
    if positive and numeric <= 0.0:
        _fail(path, "must be positive")
    if nonnegative and numeric < 0.0:
        _fail(path, "must be non-negative")
    return numeric


def _integer(value: Any, path: str, *, positive: bool = False, nonnegative: bool = False) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        _fail(path, "must be an integer")
    if positive and value <= 0:
        _fail(path, "must be positive")
    if nonnegative and value < 0:
        _fail(path, "must be non-negative")
    return value


def _mapping(
    value: Any,
    path: str,
    required: set[str],
    allowed: set[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(path, "must be an object")
    keys = set(value)
    missing = required - keys
    if missing:
        _fail(path, f"missing required key(s): {', '.join(sorted(missing))}")
    allowed_keys = required if allowed is None else allowed
    unknown = keys - allowed_keys
    if unknown:
        _fail(path, f"unknown key(s): {', '.join(sorted(unknown))}")
    return value


def _list(value: Any, path: str, *, length: int | None = None) -> list[Any]:
    if not isinstance(value, list):
        _fail(path, "must be an array")
    if length is not None and len(value) != length:
        _fail(path, f"must contain exactly {length} item(s)")
    return value


def _vector(
    value: Any,
    path: str,
    *,
    length: int,
    nonnegative: bool = False,
) -> list[float]:
    values = _list(value, path, length=length)
    return [
        _number(item, f"{path}[{index}]", nonnegative=nonnegative)
        for index, item in enumerate(values)
    ]


def _source_reference(value: Any, path: str, source_ids: set[str]) -> str:
    if not isinstance(value, str) or value not in source_ids:
        _fail(path, "must reference a declared source id")
    return value


def _assert_unique(values: list[Any], path: str) -> None:
    if len(values) != len(set(values)):
        _fail(path, "must contain unique values")


def _strict_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant is forbidden: {value}")


def load_config(path: Path) -> dict[str, Any]:
    """Load JSON while rejecting NaN and infinity tokens."""

    try:
        with path.open(encoding="utf-8") as handle:
            loaded = json.load(handle, parse_constant=_strict_json_constant)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ContractValidationError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(loaded, dict):
        _fail("$", "root must be an object")
    return loaded


def _validate_sources(config: dict[str, Any]) -> set[str]:
    records = _list(config["sources"], "sources")
    if not records:
        _fail("sources", "must not be empty")

    source_ids: list[str] = []
    allowed_kinds = {"repository", "historical_literature_record", "synthetic_assumption"}
    for index, record in enumerate(records):
        path = f"sources[{index}]"
        _mapping(record, path, {"id", "kind", "status", "locator", "use"}, {
            "id", "kind", "status", "locator", "use"
        })
        source_id = record["id"]
        if not isinstance(source_id, str) or not source_id:
            _fail(f"{path}.id", "must be a non-empty string")
        if record["kind"] not in allowed_kinds:
            _fail(f"{path}.kind", "must be a supported source kind")
        for field in ("status", "locator", "use"):
            if not isinstance(record[field], str) or not record[field].strip():
                _fail(f"{path}.{field}", "must be a non-empty string")
        source_ids.append(source_id)

    _assert_unique(source_ids, "sources[].id")
    source_map = {record["id"]: record for record in records}
    historical = source_map.get("LIT-STATUS-001")
    if historical is None or historical["kind"] != "historical_literature_record":
        _fail("sources", "must retain the historical-literature audit record")
    if historical["status"] != "no_source_located_numeric_parameter_reused":
        _fail("sources.LIT-STATUS-001.status", "must not imply unverified numeric reuse")
    return set(source_ids)


def _validate_conventions(config: dict[str, Any]) -> None:
    value = _mapping(config["conventions"], "conventions", {
        "world_frame", "body_frame", "units", "quaternion", "body_angular_rate"
    })
    if value["world_frame"] != "NED":
        _fail("conventions.world_frame", "must be NED")
    if value["body_frame"] != "FRD":
        _fail("conventions.body_frame", "must be FRD")
    if value["units"] != "SI":
        _fail("conventions.units", "must be SI")

    quaternion = _mapping(value["quaternion"], "conventions.quaternion", {
        "name", "representation", "rotation", "normalization_required", "sign_policy",
        "unit_norm_tolerance"
    })
    expected_quaternion = {
        "name": "q_nb",
        "representation": "scalar_first_hamilton",
        "rotation": "body_to_ned",
        "normalization_required": True,
        "sign_policy": "canonical_scalar_nonnegative_then_first_nonzero_vector_positive",
    }
    for field, expected in expected_quaternion.items():
        if quaternion[field] != expected:
            _fail(f"conventions.quaternion.{field}", f"must be {expected!r}")
    _number(quaternion["unit_norm_tolerance"], "conventions.quaternion.unit_norm_tolerance", positive=True)

    angular_rate = _mapping(value["body_angular_rate"], "conventions.body_angular_rate", {
        "name", "frame", "unit"
    })
    if angular_rate != {"name": "omega_b", "frame": "body_frd", "unit": "rad/s"}:
        _fail("conventions.body_angular_rate", "must declare body-FRD omega_b in rad/s")


def _validate_timing(config: dict[str, Any], source_ids: set[str]) -> tuple[float, dict[str, int]]:
    timing = _mapping(config["timing"], "timing", {
        "source_ref", "base_period_s", "schedules", "sequence", "timestamp_policy"
    })
    _source_reference(timing["source_ref"], "timing.source_ref", source_ids)
    base_period_s = _number(timing["base_period_s"], "timing.base_period_s", positive=True)

    schedules = _mapping(timing["schedules"], "timing.schedules", {
        "plant_every_ticks",
        "actuator_every_ticks",
        "imu_every_ticks",
        "estimator_every_ticks",
        "controller_every_ticks",
    })
    normalized = {
        name: _integer(value, f"timing.schedules.{name}", positive=True)
        for name, value in schedules.items()
    }
    if normalized["plant_every_ticks"] != 1 or normalized["actuator_every_ticks"] != 1:
        _fail("timing.schedules", "plant and actuator must run at every base tick")

    sequence = _list(timing["sequence"], "timing.sequence", length=len(REQUIRED_SEQUENCE))
    if sequence != REQUIRED_SEQUENCE:
        _fail("timing.sequence", "must use the declared deterministic publication order")

    policy = _mapping(timing["timestamp_policy"], "timing.timestamp_policy", {
        "strictly_increasing",
        "nonpositive_dt_action",
        "stale_timestamp_action",
        "reset_action",
    })
    expected_policy = {
        "strictly_increasing": True,
        "nonpositive_dt_action": "reject_sample",
        "stale_timestamp_action": "reject_sample_preserve_last_valid_state",
        "reset_action": "clear_internal_state_then_require_explicit_initialization",
    }
    if policy != expected_policy:
        _fail("timing.timestamp_policy", "must define the required reject and reset behavior")
    return base_period_s, normalized


def _validate_spd(matrix: Any, path: str) -> None:
    rows = _list(matrix, path, length=3)
    values = [_vector(row, f"{path}[{index}]", length=3) for index, row in enumerate(rows)]
    for row in range(3):
        for column in range(3):
            if not math.isclose(values[row][column], values[column][row], abs_tol=1e-12):
                _fail(path, "must be symmetric")
    lower = [[0.0] * 3 for _ in range(3)]
    for row in range(3):
        for column in range(row + 1):
            residual = sum(lower[row][k] * lower[column][k] for k in range(column))
            if row == column:
                diagonal = values[row][row] - residual
                if diagonal <= 0.0:
                    _fail(path, "must be positive definite")
                lower[row][column] = math.sqrt(diagonal)
            else:
                lower[row][column] = (values[row][column] - residual) / lower[column][column]


def _validate_plant(config: dict[str, Any], source_ids: set[str]) -> None:
    plant = _mapping(config["plant_contract"], "plant_contract", {
        "source_ref", "implementation_status", "state", "inertia_kg_m2",
        "inertia_reference_frame", "integrator_contract", "truth_visibility"
    })
    _source_reference(plant["source_ref"], "plant_contract.source_ref", source_ids)
    if plant["implementation_status"] != "future_g1_contract_only":
        _fail("plant_contract.implementation_status", "must stay a future G1 contract")
    if plant["state"] != ["q_nb", "omega_b_rad_s"]:
        _fail("plant_contract.state", "must use q_nb and body angular rate")
    if plant["inertia_reference_frame"] != "body_frd":
        _fail("plant_contract.inertia_reference_frame", "must be body_frd")
    _validate_spd(plant["inertia_kg_m2"], "plant_contract.inertia_kg_m2")

    integrator = _mapping(plant["integrator_contract"], "plant_contract.integrator_contract", {
        "method", "step_halving_check_required"
    })
    if integrator != {"method": "rk4", "step_halving_check_required": True}:
        _fail("plant_contract.integrator_contract", "must retain the proposed G1 check")

    visibility = _mapping(plant["truth_visibility"], "plant_contract.truth_visibility", {
        "allowed_consumers", "forbidden_consumers"
    })
    allowed = _list(visibility["allowed_consumers"], "plant_contract.truth_visibility.allowed_consumers")
    forbidden = _list(visibility["forbidden_consumers"], "plant_contract.truth_visibility.forbidden_consumers")
    if set(forbidden) != {"estimator", "controller"}:
        _fail("plant_contract.truth_visibility.forbidden_consumers", "must forbid estimator and controller")
    if {"estimator", "controller"} & set(allowed):
        _fail("plant_contract.truth_visibility.allowed_consumers", "must not expose truth to estimator/controller")


def _validate_actuator(config: dict[str, Any], source_ids: set[str]) -> list[float]:
    actuator = _mapping(config["actuator_contract"], "actuator_contract", {
        "source_ref", "implementation_status", "requested_torque", "limited_target_torque",
        "actual_torque", "model", "time_constant_s", "limits_Nm", "antiwindup"
    })
    _source_reference(actuator["source_ref"], "actuator_contract.source_ref", source_ids)
    expected_names = {
        "requested_torque": "requested_torque_body_Nm",
        "limited_target_torque": "limited_torque_body_Nm",
        "actual_torque": "actual_torque_body_Nm",
        "model": "first_order_bounded",
        "implementation_status": "future_g1_contract_only",
    }
    for field, expected in expected_names.items():
        if actuator[field] != expected:
            _fail(f"actuator_contract.{field}", f"must be {expected!r}")
    _number(actuator["time_constant_s"], "actuator_contract.time_constant_s", positive=True)
    limits = _vector(actuator["limits_Nm"], "actuator_contract.limits_Nm", length=3, nonnegative=True)
    if any(limit == 0.0 for limit in limits):
        _fail("actuator_contract.limits_Nm", "must contain meaningful positive limits")
    antiwindup = _mapping(actuator["antiwindup"], "actuator_contract.antiwindup", {
        "feedback_signal", "recipient"
    })
    expected_antiwindup = {
        "feedback_signal": "actual_minus_limited_target_torque_body_Nm",
        "recipient": "future_rate_pid",
    }
    if antiwindup != expected_antiwindup:
        _fail("actuator_contract.antiwindup", "must use actual-minus-limited feedback")
    return limits


def _validate_imu(
    config: dict[str, Any],
    source_ids: set[str],
    schedules: dict[str, int],
) -> None:
    imu = _mapping(config["imu_contract"], "imu_contract", {
        "source_ref", "implementation_status", "sample_period_ticks", "sample_location",
        "timestamp", "gravity_ned_m_s2", "specific_force_definition", "gyro",
        "accelerometer"
    })
    _source_reference(imu["source_ref"], "imu_contract.source_ref", source_ids)
    if imu["implementation_status"] != "future_g1_contract_only":
        _fail("imu_contract.implementation_status", "must stay a future G1 contract")
    if _integer(imu["sample_period_ticks"], "imu_contract.sample_period_ticks", positive=True) != schedules["imu_every_ticks"]:
        _fail("imu_contract.sample_period_ticks", "must match timing.schedules.imu_every_ticks")
    expected_imu = {
        "sample_location": "center_of_gravity",
        "timestamp": "end_of_interval",
        "specific_force_definition": "f_b = a_b - R_nb_transpose_times_g_n",
    }
    for field, expected in expected_imu.items():
        if imu[field] != expected:
            _fail(f"imu_contract.{field}", f"must be {expected!r}")
    gravity = _vector(imu["gravity_ned_m_s2"], "imu_contract.gravity_ned_m_s2", length=3)
    if gravity[2] <= 0.0:
        _fail("imu_contract.gravity_ned_m_s2", "must use positive Down gravity in NED")

    gyro = _mapping(imu["gyro"], "imu_contract.gyro", {"noise_std_rad_s", "bias_rad_s"})
    _vector(gyro["noise_std_rad_s"], "imu_contract.gyro.noise_std_rad_s", length=3, nonnegative=True)
    _vector(gyro["bias_rad_s"], "imu_contract.gyro.bias_rad_s", length=3)
    accel = _mapping(imu["accelerometer"], "imu_contract.accelerometer", {"noise_std_m_s2", "bias_m_s2"})
    _vector(accel["noise_std_m_s2"], "imu_contract.accelerometer.noise_std_m_s2", length=3, nonnegative=True)
    _vector(accel["bias_m_s2"], "imu_contract.accelerometer.bias_m_s2", length=3)


def _validate_estimator(config: dict[str, Any]) -> None:
    estimator = _mapping(config["estimator_contract"], "estimator_contract", {
        "implementation_status", "input", "output", "truth_inputs_allowed_only_for",
        "truth_inputs_forbidden_after_reset", "normalize_after", "absolute_yaw_observation",
        "invalid_sample_action"
    })
    expected = {
        "implementation_status": "future_g2_contract_only",
        "input": "imu_sample_with_timestamp_and_validity",
        "output": "estimated_q_nb_and_estimated_omega_b_rad_s",
        "truth_inputs_allowed_only_for": "explicit_reset_initialization",
        "truth_inputs_forbidden_after_reset": True,
        "absolute_yaw_observation": "not_available_from_six_axis_imu",
        "invalid_sample_action": "reject_sample_preserve_last_valid_state",
    }
    for field, expected_value in expected.items():
        if estimator[field] != expected_value:
            _fail(f"estimator_contract.{field}", f"must be {expected_value!r}")
    if set(_list(estimator["normalize_after"], "estimator_contract.normalize_after")) != {
        "propagation", "correction"
    }:
        _fail("estimator_contract.normalize_after", "must normalize after propagation and correction")


def _validate_gain(value: Any, path: str) -> None:
    gain = _mapping(value, path, {"initial", "minimum", "maximum"})
    initial = _vector(gain["initial"], f"{path}.initial", length=3, nonnegative=True)
    minimum = _vector(gain["minimum"], f"{path}.minimum", length=3, nonnegative=True)
    maximum = _vector(gain["maximum"], f"{path}.maximum", length=3, nonnegative=True)
    for index, (low, candidate, high) in enumerate(zip(minimum, initial, maximum)):
        if low > candidate or candidate > high:
            _fail(path, f"axis {index} must satisfy minimum <= initial <= maximum")
        if high <= 0.0:
            _fail(path, f"axis {index} maximum must be meaningful and positive")


def _validate_controller(config: dict[str, Any], source_ids: set[str], limits: list[float]) -> None:
    controller = _mapping(config["controller_contract"], "controller_contract", {
        "source_ref", "implementation_status", "input", "output", "truth_inputs_forbidden",
        "attitude_error", "attitude_kp", "rate_pid"
    })
    _source_reference(controller["source_ref"], "controller_contract.source_ref", source_ids)
    expected = {
        "implementation_status": "future_g2_contract_only",
        "input": "estimated_q_nb_and_estimated_omega_b_rad_s_only",
        "output": "requested_torque_body_Nm",
        "truth_inputs_forbidden": True,
    }
    for field, expected_value in expected.items():
        if controller[field] != expected_value:
            _fail(f"controller_contract.{field}", f"must be {expected_value!r}")

    attitude_error = _mapping(controller["attitude_error"], "controller_contract.attitude_error", {
        "equation", "shortest_path", "half_turn_tie_break"
    })
    expected_error = {
        "equation": "conjugate_q_nb_est_hamilton_product_q_nb_command",
        "shortest_path": "negate_error_quaternion_when_scalar_part_is_negative",
        "half_turn_tie_break": "at_zero_scalar_choose_first_nonzero_vector_component_positive",
    }
    if attitude_error != expected_error:
        _fail("controller_contract.attitude_error", "must define deterministic sign and half-turn behavior")

    _validate_gain(controller["attitude_kp"], "controller_contract.attitude_kp")
    rate_pid = _mapping(controller["rate_pid"], "controller_contract.rate_pid", {
        "kp", "ki", "kd", "integrator_limit_Nm", "integration_rule", "derivative_rule"
    })
    for term in ("kp", "ki", "kd"):
        _validate_gain(rate_pid[term], f"controller_contract.rate_pid.{term}")
    integrator_limits = _vector(
        rate_pid["integrator_limit_Nm"],
        "controller_contract.rate_pid.integrator_limit_Nm",
        length=3,
        nonnegative=True,
    )
    for index, (integrator_limit, actuator_limit) in enumerate(zip(integrator_limits, limits)):
        if integrator_limit <= 0.0 or integrator_limit > actuator_limit:
            _fail(
                "controller_contract.rate_pid.integrator_limit_Nm",
                f"axis {index} must be positive and no greater than actuator limit",
            )
    for field, expected_value in {
        "integration_rule": "future_implementation_must_state_discrete_rule",
        "derivative_rule": "future_implementation_must_state_measurement_or_error_rule",
    }.items():
        if rate_pid[field] != expected_value:
            _fail(f"controller_contract.rate_pid.{field}", "must reserve a future implementation decision")


def _validate_seed_policy(config: dict[str, Any]) -> set[int]:
    seeds = _mapping(config["seed_policy"], "seed_policy", {
        "tuning_seed", "acceptance_seeds", "rule"
    })
    tuning_seed = _integer(seeds["tuning_seed"], "seed_policy.tuning_seed", nonnegative=True)
    acceptance = [
        _integer(value, f"seed_policy.acceptance_seeds[{index}]", nonnegative=True)
        for index, value in enumerate(_list(seeds["acceptance_seeds"], "seed_policy.acceptance_seeds", length=8))
    ]
    _assert_unique(acceptance, "seed_policy.acceptance_seeds")
    if tuning_seed in acceptance:
        _fail("seed_policy", "tuning seed must not be an acceptance seed")
    if seeds["rule"] != "acceptance_seeds_are_reserved_and_must_not_be_reused_for_tuning":
        _fail("seed_policy.rule", "must reserve acceptance seeds from tuning")
    return set(acceptance)


def _validate_operating_envelope(config: dict[str, Any], source_ids: set[str]) -> None:
    envelope = _mapping(config["operating_envelope"], "operating_envelope", {
        "source_ref", "status", "statement", "max_command_attitude_rad",
        "max_initial_attitude_offset_rad", "max_body_rate_rad_s", "validity_excludes"
    })
    _source_reference(envelope["source_ref"], "operating_envelope.source_ref", source_ids)
    if envelope["status"] != "proposed_pending_maintainer_approval":
        _fail("operating_envelope.status", "must remain proposed pending maintainer approval")
    if not isinstance(envelope["statement"], str) or "synthetic" not in envelope["statement"].lower():
        _fail("operating_envelope.statement", "must identify this as a synthetic envelope")

    command_limit = _vector(
        envelope["max_command_attitude_rad"],
        "operating_envelope.max_command_attitude_rad",
        length=3,
        nonnegative=True,
    )
    offset_limit = _vector(
        envelope["max_initial_attitude_offset_rad"],
        "operating_envelope.max_initial_attitude_offset_rad",
        length=3,
        nonnegative=True,
    )
    rate_limit = _vector(
        envelope["max_body_rate_rad_s"],
        "operating_envelope.max_body_rate_rad_s",
        length=3,
        nonnegative=True,
    )
    if any(limit <= 0.0 for limit in command_limit + offset_limit + rate_limit):
        _fail("operating_envelope", "must provide meaningful positive bounds")

    exclusions = _list(envelope["validity_excludes"], "operating_envelope.validity_excludes")
    expected_exclusions = {"translation", "aerodynamics", "navigation", "hardware"}
    if set(exclusions) != expected_exclusions:
        _fail("operating_envelope.validity_excludes", "must state the B0 scope exclusions")

    for scenario_index, scenario in enumerate(config["scenarios"]):
        path = f"scenarios[{scenario_index}]"
        initial_rate = _vector(scenario["initial_body_rate_rad_s"], f"{path}.initial_body_rate_rad_s", length=3)
        if any(abs(value) > limit for value, limit in zip(initial_rate, rate_limit)):
            _fail(f"{path}.initial_body_rate_rad_s", "exceeds operating envelope")
        offset = scenario.get("initial_attitude_offset_rad", [0.0, 0.0, 0.0])
        if any(abs(value) > limit for value, limit in zip(offset, offset_limit)):
            _fail(f"{path}.initial_attitude_offset_rad", "exceeds operating envelope")
        for event_index, event in enumerate(scenario["events"]):
            if event["type"] == "command_step":
                axis = {"x": 0, "y": 1, "z": 2}[event["axis"]]
                if abs(float(event["value_rad"])) > command_limit[axis]:
                    _fail(
                        f"{path}.events[{event_index}].value_rad",
                        "exceeds operating envelope",
                    )


def _validate_acceptance_policy(
    config: dict[str, Any],
    source_ids: set[str],
    base_period_s: float,
) -> None:
    policy = _mapping(config["acceptance_policy"], "acceptance_policy", {
        "source_ref", "status", "attitude_error", "settling", "overshoot",
        "outcome_classes"
    })
    _source_reference(policy["source_ref"], "acceptance_policy.source_ref", source_ids)
    if policy["status"] != "proposed_pending_maintainer_approval":
        _fail("acceptance_policy.status", "must remain proposed pending maintainer approval")

    attitude_error = _mapping(policy["attitude_error"], "acceptance_policy.attitude_error", {
        "sign_equivalent_angle_formula", "unit"
    })
    expected_error = {
        "sign_equivalent_angle_formula": "2*acos(clamp(abs(dot(q_reference,q_candidate)),0,1))",
        "unit": "rad",
    }
    if attitude_error != expected_error:
        _fail("acceptance_policy.attitude_error", "must define sign-equivalent quaternion error")

    settling = _mapping(policy["settling"], "acceptance_policy.settling", {
        "band_rad", "dwell_s", "reference"
    })
    _number(settling["band_rad"], "acceptance_policy.settling.band_rad", positive=True)
    dwell = _number(settling["dwell_s"], "acceptance_policy.settling.dwell_s", positive=True)
    if not math.isclose(dwell / base_period_s, round(dwell / base_period_s), abs_tol=1e-9):
        _fail("acceptance_policy.settling.dwell_s", "must be an integer number of base ticks")
    if settling["reference"] != "after_end_of_command_or_disturbance_event":
        _fail("acceptance_policy.settling.reference", "must state the event-end reference")

    overshoot = _mapping(policy["overshoot"], "acceptance_policy.overshoot", {
        "reference", "zero_command_action", "unit"
    })
    expected_overshoot = {
        "reference": "first_signed_target_amplitude_after_nonzero_step",
        "zero_command_action": "not_applicable",
        "unit": "percent",
    }
    if overshoot != expected_overshoot:
        _fail("acceptance_policy.overshoot", "must define nonzero-step overshoot semantics")

    outcomes = _list(policy["outcome_classes"], "acceptance_policy.outcome_classes")
    expected_outcomes = {
        "performance_pass",
        "performance_fail",
        "limitation_characterized",
        "invalid_input_rejected",
        "execution_error_inconclusive",
    }
    if set(outcomes) != expected_outcomes:
        _fail("acceptance_policy.outcome_classes", "must distinguish performance and execution outcomes")
    _assert_unique(outcomes, "acceptance_policy.outcome_classes")
def _validate_quaternion(value: Any, path: str, tolerance: float) -> None:
    quaternion = _vector(value, path, length=4)
    norm = math.sqrt(sum(component * component for component in quaternion))
    if not math.isclose(norm, 1.0, abs_tol=tolerance):
        _fail(path, "must be a unit quaternion within configured tolerance")


def _validate_event(event: Any, path: str, total_ticks: int) -> str:
    required = {"type", "start_tick", "end_tick"}
    event_map = _mapping(
        event, path, required, required | set().union(*EVENT_FIELDS.values())
    )
    event_type = event_map["type"]
    if event_type not in EVENT_FIELDS:
        _fail(f"{path}.type", "must be a supported event type")
    allowed = required | EVENT_FIELDS[event_type]
    unknown = set(event_map) - allowed
    if unknown:
        _fail(path, f"unknown key(s): {', '.join(sorted(unknown))}")

    start = _integer(event_map["start_tick"], f"{path}.start_tick", nonnegative=True)
    end = _integer(event_map["end_tick"], f"{path}.end_tick", positive=True)
    if start >= end or end > total_ticks:
        _fail(path, "must satisfy 0 <= start_tick < end_tick <= scenario ticks")

    if event_type == "command_step":
        if event_map["axis"] not in {"x", "y", "z"}:
            _fail(f"{path}.axis", "must be x, y, or z")
        _number(event_map["value_rad"], f"{path}.value_rad")
    elif event_type == "external_torque":
        _vector(event_map["vector_Nm"], f"{path}.vector_Nm", length=3)
    elif event_type == "imu_bias":
        _vector(event_map["gyro_bias_rad_s"], f"{path}.gyro_bias_rad_s", length=3)
        _vector(event_map["accelerometer_bias_m_s2"], f"{path}.accelerometer_bias_m_s2", length=3)
    elif event_type == "specific_force_disturbance":
        _vector(event_map["vector_m_s2"], f"{path}.vector_m_s2", length=3)
    elif event_type == "invalid_input":
        if event_map["invalid_kind"] not in {"negative_dt", "stale_timestamp"}:
            _fail(f"{path}.invalid_kind", "must be negative_dt or stale_timestamp")
    return event_type


def _validate_criterion(criterion: Any, path: str, total_ticks: int) -> str:
    record = _mapping(criterion, path, {
        "id", "metric", "reducer", "operator", "limit", "unit", "window", "evidence_status"
    })
    if not isinstance(record["id"], str) or not record["id"]:
        _fail(f"{path}.id", "must be a non-empty string")
    metric = record["metric"]
    if metric not in METRIC_SPECS:
        _fail(f"{path}.metric", "must be a supported metric")
    reducers, expected_unit, value_kind = METRIC_SPECS[metric]
    if record["reducer"] not in reducers:
        _fail(f"{path}.reducer", f"is incompatible with metric {metric}")
    if record["unit"] != expected_unit:
        _fail(f"{path}.unit", f"must be {expected_unit!r} for metric {metric}")
    if record["evidence_status"] != "proposed_not_executed":
        _fail(f"{path}.evidence_status", "must not claim unexecuted performance")

    if value_kind == "bool":
        if not isinstance(record["limit"], bool) or record["operator"] != "==":
            _fail(path, "boolean metrics require == and a boolean limit")
    else:
        _number(record["limit"], f"{path}.limit", nonnegative=True)
        if record["operator"] not in {"<=", ">="}:
            _fail(f"{path}.operator", "numeric metrics require <= or >=")

    window = _mapping(record["window"], f"{path}.window", {"start_tick", "end_tick"})
    start = _integer(window["start_tick"], f"{path}.window.start_tick", nonnegative=True)
    end = _integer(window["end_tick"], f"{path}.window.end_tick", positive=True)
    if start >= end or end > total_ticks:
        _fail(f"{path}.window", "must fit inside the scenario tick range")
    return record["id"]


def _validate_tri_axis_steps(events: list[dict[str, Any]], path: str) -> None:
    if len(events) != 6:
        _fail(path, "must provide signed steps for all three body axes")
    by_axis: dict[str, list[float]] = {"x": [], "y": [], "z": []}
    for event in events:
        by_axis[event["axis"]].append(float(event["value_rad"]))
    for axis, values in by_axis.items():
        if len(values) != 2 or not any(value > 0.0 for value in values) or not any(value < 0.0 for value in values):
            _fail(path, f"must provide one positive and one negative {axis}-axis step")


def _validate_scenarios(
    config: dict[str, Any],
    source_ids: set[str],
    acceptance_seeds: set[int],
    base_period_s: float,
    quaternion_tolerance: float,
) -> None:
    scenarios = _list(config["scenarios"], "scenarios", length=len(EXPECTED_SCENARIOS))
    scenario_ids: list[str] = []
    used_seeds: list[int] = []
    artifact_paths: list[str] = []
    criterion_ids: list[str] = []

    required = {
        "id", "class", "source_ref", "seed", "duration_s", "initial_q_nb",
        "initial_body_rate_rad_s", "events", "observations", "artifact_path", "acceptance"
    }
    allowed = required | {"initial_attitude_offset_rad"}

    for index, scenario in enumerate(scenarios):
        path = f"scenarios[{index}]"
        record = _mapping(scenario, path, required, allowed)
        scenario_id = record["id"]
        if scenario_id not in EXPECTED_SCENARIOS:
            _fail(f"{path}.id", "must be one of the eight required G0 scenarios")
        if record["class"] != EXPECTED_SCENARIOS[scenario_id]:
            _fail(f"{path}.class", "does not match the required scenario classification")
        _source_reference(record["source_ref"], f"{path}.source_ref", source_ids)
        seed = _integer(record["seed"], f"{path}.seed", nonnegative=True)
        if seed not in acceptance_seeds:
            _fail(f"{path}.seed", "must use a reserved acceptance seed")
        duration = _number(record["duration_s"], f"{path}.duration_s", positive=True)
        raw_ticks = duration / base_period_s
        total_ticks = round(raw_ticks)
        if not math.isclose(raw_ticks, total_ticks, abs_tol=1e-9):
            _fail(f"{path}.duration_s", "must be an integer number of base ticks")

        _validate_quaternion(record["initial_q_nb"], f"{path}.initial_q_nb", quaternion_tolerance)
        _vector(record["initial_body_rate_rad_s"], f"{path}.initial_body_rate_rad_s", length=3)
        if scenario_id == "initial_attitude_offset":
            _vector(record.get("initial_attitude_offset_rad"), f"{path}.initial_attitude_offset_rad", length=3)
        elif "initial_attitude_offset_rad" in record:
            _fail(f"{path}.initial_attitude_offset_rad", "is reserved for initial_attitude_offset")

        events = _list(record["events"], f"{path}.events")
        event_types = {
            _validate_event(event, f"{path}.events[{event_index}]", total_ticks)
            for event_index, event in enumerate(events)
        }
        if event_types != EXPECTED_EVENT_TYPES[scenario_id]:
            _fail(f"{path}.events", "does not provide the required event class(es)")
        if scenario_id == "tri_axis_signed_steps":
            _validate_tri_axis_steps(events, f"{path}.events")

        observations = _list(record["observations"], f"{path}.observations")
        if not observations or any(item not in OBSERVATIONS for item in observations):
            _fail(f"{path}.observations", "must contain known observation field names")
        _assert_unique(observations, f"{path}.observations")

        artifact_path = record["artifact_path"]
        expected_artifact_path = f"artifacts/b0/{scenario_id}/"
        if artifact_path != expected_artifact_path:
            _fail(f"{path}.artifact_path", f"must be {expected_artifact_path!r}")

        acceptance = _list(record["acceptance"], f"{path}.acceptance")
        if not acceptance:
            _fail(f"{path}.acceptance", "must not be empty")
        for criterion_index, criterion in enumerate(acceptance):
            criterion_ids.append(
                _validate_criterion(
                    criterion,
                    f"{path}.acceptance[{criterion_index}]",
                    total_ticks,
                )
            )

        scenario_ids.append(scenario_id)
        used_seeds.append(seed)
        artifact_paths.append(artifact_path)

    if set(scenario_ids) != set(EXPECTED_SCENARIOS):
        _fail("scenarios[].id", "must contain each required scenario exactly once")
    _assert_unique(scenario_ids, "scenarios[].id")
    _assert_unique(used_seeds, "scenarios[].seed")
    if set(used_seeds) != acceptance_seeds:
        _fail("scenarios[].seed", "must use each reserved acceptance seed exactly once")
    _assert_unique(artifact_paths, "scenarios[].artifact_path")
    _assert_unique(criterion_ids, "scenarios[].acceptance[].id")


def validate_config(config: dict[str, Any]) -> None:
    """Validate structural, semantic, physical, and scheduling constraints."""

    required = {
        "schema_version", "contract_status", "sources", "conventions", "timing",
        "plant_contract", "actuator_contract", "imu_contract", "estimator_contract",
        "controller_contract", "seed_policy", "operating_envelope",
        "acceptance_policy", "scenarios"
    }
    _mapping(config, "$", required, required)
    if config["schema_version"] != SCHEMA_VERSION:
        _fail("schema_version", f"must be {SCHEMA_VERSION!r}")

    status = _mapping(config["contract_status"], "contract_status", {
        "state", "freeze_prohibited", "approval_required"
    })
    if status["state"] != "proposed_pending_maintainer_approval":
        _fail("contract_status.state", "must remain proposed pending maintainer approval")
    if status["freeze_prohibited"] is not True:
        _fail("contract_status.freeze_prohibited", "must be true until approval")
    approvals = _list(status["approval_required"], "contract_status.approval_required")
    if not approvals or any(not isinstance(item, str) or not item for item in approvals):
        _fail("contract_status.approval_required", "must list concrete approval decisions")

    source_ids = _validate_sources(config)
    _validate_conventions(config)
    base_period_s, schedules = _validate_timing(config, source_ids)
    _validate_plant(config, source_ids)
    actuator_limits = _validate_actuator(config, source_ids)
    _validate_imu(config, source_ids, schedules)
    _validate_estimator(config)
    _validate_controller(config, source_ids, actuator_limits)
    acceptance_seeds = _validate_seed_policy(config)
    tolerance = float(config["conventions"]["quaternion"]["unit_norm_tolerance"])
    _validate_scenarios(config, source_ids, acceptance_seeds, base_period_s, tolerance)


    _validate_operating_envelope(config, source_ids)
    _validate_acceptance_policy(config, source_ids, base_period_s)
def _default_config_path() -> Path:
    return Path(__file__).resolve().parent / "configs" / "b0_g0_contract.v1.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the B0 G0 contract configuration.")
    parser.add_argument(
        "--config",
        type=Path,
        default=_default_config_path(),
        help="JSON configuration to validate",
    )
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
        validate_config(config)
    except ContractValidationError as exc:
        parser.error(str(exc))
    print(f"Valid B0 G0 contract configuration: {args.config}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
