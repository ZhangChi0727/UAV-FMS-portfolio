"""Strict validation for the proposed B0 G0 configuration contract.

The module validates declarative G0 inputs only. It neither models the vehicle
nor evaluates estimator, controller, or closed-loop performance.
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

ROOT_REQUIRED = {
    "schema_version",
    "contract_status",
    "sources",
    "conventions",
    "timing",
    "interface_contract",
    "initialization_contract",
    "plant_contract",
    "actuator_contract",
    "imu_contract",
    "estimator_contract",
    "controller_contract",
    "seed_policy",
    "operating_envelope",
    "acceptance_policy",
    "scenarios",
}

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

METRIC_SPECS: dict[str, dict[str, Any]] = {
    "attitude_error_rad": {
        "reducers": {"max_abs", "peak"},
        "unit": "rad",
        "value_kind": "number",
        "observations": {"q_nb_truth", "q_nb_command"},
        "event_types": {"command_step", "external_torque"},
    },
    "attitude_settling_time_s": {
        "reducers": {"max"},
        "unit": "s",
        "value_kind": "number",
        "observations": {"q_nb_truth", "q_nb_command"},
        "event_types": {"command_step", "external_torque"},
    },
    "body_rate_error_rad_s": {
        "reducers": {"max_abs", "rms"},
        "unit": "rad/s",
        "value_kind": "number",
        "observations": {"omega_b_truth_rad_s", "omega_b_estimate_rad_s"},
        "event_types": set(),
    },
    "quaternion_norm_error": {
        "reducers": {"max_abs"},
        "unit": "1",
        "value_kind": "number",
        "observations": {"q_nb_estimate"},
        "event_types": set(),
    },
    "tracking_settling_time_s": {
        "reducers": {"max"},
        "unit": "s",
        "value_kind": "number",
        "observations": {"q_nb_truth", "q_nb_command"},
        "event_types": {"command_step"},
    },
    "tracking_overshoot_percent": {
        "reducers": {"max"},
        "unit": "%",
        "value_kind": "number",
        "observations": {"q_nb_truth", "q_nb_command"},
        "event_types": {"command_step"},
    },
    "cross_axis_attitude_error_rad": {
        "reducers": {"max_abs"},
        "unit": "rad",
        "value_kind": "number",
        "observations": {"q_nb_truth", "q_nb_command"},
        "event_types": {"command_step"},
    },
    "actuator_saturation_time_s": {
        "reducers": {"total_time"},
        "unit": "s",
        "value_kind": "number",
        "observations": {"requested_torque_Nm", "limited_torque_Nm"},
        "event_types": {"command_step", "external_torque"},
    },
    "roll_pitch_estimation_error_rad": {
        "reducers": {"rms"},
        "unit": "rad",
        "value_kind": "number",
        "observations": {"q_nb_truth", "q_nb_estimate"},
        "event_types": set(),
    },
    "yaw_drift_rad_s": {
        "reducers": {"max_abs"},
        "unit": "rad/s",
        "value_kind": "number",
        "observations": {"q_nb_truth", "q_nb_estimate"},
        "event_types": set(),
    },
    "controller_integral_Nm": {
        "reducers": {"max_abs"},
        "unit": "Nm",
        "value_kind": "number",
        "observations": {"controller_integral_Nm"},
        "event_types": set(),
    },
    "limitation_event_recorded": {
        "reducers": {"all"},
        "unit": "bool",
        "value_kind": "bool",
        "observations": {
            "imu_specific_force_m_s2",
            "limitation_status",
            "q_nb_truth",
            "q_nb_estimate",
        },
        "event_types": {"specific_force_disturbance"},
    },
    "invalid_input_rejection_count": {
        "reducers": {"min"},
        "unit": "count",
        "value_kind": "number",
        "observations": {"sample_validity", "rejection_reason"},
        "event_types": set(),
    },
    "reset_replay_match": {
        "reducers": {"all"},
        "unit": "bool",
        "value_kind": "bool",
        "observations": {"reset_epoch", "q_nb_estimate"},
        "event_types": {"reset"},
    },
}

EVENT_COMMON_FIELDS = {"id", "type", "start_tick", "end_tick"}
EVENT_FIELDS: dict[str, set[str]] = {
    "command_step": {"axis", "value_rad", "post_event_action"},
    "external_torque": {"vector_Nm"},
    "imu_bias": {
        "gyro_bias_rad_s",
        "accelerometer_bias_m_s2",
        "application",
    },
    "specific_force_disturbance": {"vector_m_s2", "application"},
    "invalid_input": {"invalid_kind"},
    "reset": {"target"},
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

REQUIRED_SCENARIO_METRICS: dict[str, set[str]] = {
    "stationary_zero_command": {
        "attitude_error_rad",
        "body_rate_error_rad_s",
        "quaternion_norm_error",
    },
    "initial_attitude_offset": {"attitude_settling_time_s", "attitude_error_rad"},
    "tri_axis_signed_steps": set(),
    "external_torque_disturbance": {
        "attitude_error_rad",
        "attitude_settling_time_s",
        "actuator_saturation_time_s",
    },
    "imu_noise_and_bias": {
        "roll_pitch_estimation_error_rad",
        "yaw_drift_rad_s",
    },
    "saturation_withdrawal": {
        "controller_integral_Nm",
        "attitude_settling_time_s",
        "actuator_saturation_time_s",
    },
    "acceleration_contamination": {"limitation_event_recorded"},
    "invalid_input_and_reset": {
        "invalid_input_rejection_count",
        "reset_replay_match",
    },
}

REQUIRED_EVENT_METRICS: dict[str, dict[str, set[str]]] = {
    "tri_axis_signed_steps": {
        "command_step": {
            "tracking_settling_time_s",
            "tracking_overshoot_percent",
            "cross_axis_attitude_error_rad",
        }
    },
    "external_torque_disturbance": {
        "external_torque": {"attitude_error_rad", "attitude_settling_time_s"}
    },
    "saturation_withdrawal": {
        "command_step": {
            "attitude_settling_time_s",
            "actuator_saturation_time_s",
        }
    },
    "acceleration_contamination": {
        "specific_force_disturbance": {"limitation_event_recorded"}
    },
    "invalid_input_and_reset": {"reset": {"reset_replay_match"}},
}

METRICS_REQUIRING_EVENT = {
    "tracking_settling_time_s",
    "tracking_overshoot_percent",
    "cross_axis_attitude_error_rad",
    "limitation_event_recorded",
    "reset_replay_match",
}


class ContractValidationError(ValueError):
    """A configuration contract is structurally or semantically invalid."""


def _fail(path: str, message: str) -> None:
    raise ContractValidationError(f"{path}: {message}")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _number(
    value: Any,
    path: str,
    *,
    positive: bool = False,
    nonnegative: bool = False,
) -> float:
    if not _is_number(value) or not math.isfinite(float(value)):
        _fail(path, "must be a finite number")
    numeric = float(value)
    if positive and numeric <= 0.0:
        _fail(path, "must be positive")
    if nonnegative and numeric < 0.0:
        _fail(path, "must be non-negative")
    return numeric


def _integer(
    value: Any,
    path: str,
    *,
    positive: bool = False,
    nonnegative: bool = False,
) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        _fail(path, "must be an integer")
    if positive and value <= 0:
        _fail(path, "must be positive")
    if nonnegative and value < 0:
        _fail(path, "must be non-negative")
    return value


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(path, "must be a non-empty string")
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


def _assert_unique(values: list[Any], path: str) -> None:
    if len(values) != len(set(values)):
        _fail(path, "must contain unique values")


def _source_reference(value: Any, path: str, source_ids: set[str]) -> str:
    source_id = _string(value, path)
    if source_id not in source_ids:
        _fail(path, "must reference a declared source id")
    return source_id


def _strict_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant is forbidden: {value}")


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key is forbidden: {key!r}")
        result[key] = value
    return result


def load_config(path: Path) -> dict[str, Any]:
    """Load JSON while rejecting duplicate keys and non-finite constants."""

    try:
        with path.open(encoding="utf-8") as handle:
            loaded = json.load(
                handle,
                object_pairs_hook=_reject_duplicate_json_keys,
                parse_constant=_strict_json_constant,
            )
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
        _mapping(record, path, {"id", "kind", "status", "locator", "use"})
        source_id = _string(record["id"], f"{path}.id")
        if not isinstance(record["kind"], str) or record["kind"] not in allowed_kinds:
            _fail(f"{path}.kind", "must be a supported source kind")
        for field in ("status", "locator", "use"):
            _string(record[field], f"{path}.{field}")
        source_ids.append(source_id)

    _assert_unique(source_ids, "sources[].id")
    source_map = {record["id"]: record for record in records}
    historical = source_map.get("LIT-STATUS-001")
    if historical is None or historical["kind"] != "historical_literature_record":
        _fail("sources", "must retain the historical-literature audit record")
    if historical["status"] != "no_source_located_numeric_parameter_reused":
        _fail("sources.LIT-STATUS-001.status", "must not imply unverified numeric reuse")
    return set(source_ids)


def _validate_conventions(config: dict[str, Any]) -> float:
    value = _mapping(
        config["conventions"],
        "conventions",
        {"world_frame", "body_frame", "units", "quaternion", "body_angular_rate"},
    )
    if value["world_frame"] != "NED":
        _fail("conventions.world_frame", "must be NED")
    if value["body_frame"] != "FRD":
        _fail("conventions.body_frame", "must be FRD")
    if value["units"] != "SI":
        _fail("conventions.units", "must be SI")

    quaternion = _mapping(
        value["quaternion"],
        "conventions.quaternion",
        {
            "name",
            "representation",
            "rotation",
            "normalization_required",
            "sign_policy",
            "unit_norm_tolerance",
        },
    )
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
    tolerance = _number(
        quaternion["unit_norm_tolerance"],
        "conventions.quaternion.unit_norm_tolerance",
        positive=True,
    )

    angular_rate = _mapping(
        value["body_angular_rate"],
        "conventions.body_angular_rate",
        {"name", "frame", "unit"},
    )
    if angular_rate != {"name": "omega_b", "frame": "body_frd", "unit": "rad/s"}:
        _fail("conventions.body_angular_rate", "must declare body-FRD omega_b in rad/s")
    return tolerance


def _validate_timing(
    config: dict[str, Any],
    source_ids: set[str],
) -> tuple[float, dict[str, int], set[str]]:
    timing = _mapping(
        config["timing"],
        "timing",
        {
            "source_ref",
            "base_period_s",
            "schedules",
            "sequence",
            "timestamp_policy",
            "sample_consumption_policy",
            "event_tick_semantics",
        },
    )
    _source_reference(timing["source_ref"], "timing.source_ref", source_ids)
    base_period_s = _number(timing["base_period_s"], "timing.base_period_s", positive=True)

    schedules = _mapping(
        timing["schedules"],
        "timing.schedules",
        {
            "plant_every_ticks",
            "actuator_every_ticks",
            "imu_every_ticks",
            "estimator_every_ticks",
            "controller_every_ticks",
        },
    )
    normalized = {
        name: _integer(value, f"timing.schedules.{name}", positive=True)
        for name, value in schedules.items()
    }
    if normalized["plant_every_ticks"] != 1 or normalized["actuator_every_ticks"] != 1:
        _fail("timing.schedules", "plant and actuator must run at every base tick")
    if normalized["estimator_every_ticks"] != normalized["imu_every_ticks"]:
        _fail(
            "timing.schedules.estimator_every_ticks",
            "must equal imu_every_ticks when no-new-IMU action is not_scheduled",
        )
    if normalized["controller_every_ticks"] != normalized["estimator_every_ticks"]:
        _fail(
            "timing.schedules.controller_every_ticks",
            "must equal estimator_every_ticks so a controller consumes a current estimate",
        )

    sequence = _list(timing["sequence"], "timing.sequence", length=len(REQUIRED_SEQUENCE))
    if sequence != REQUIRED_SEQUENCE:
        _fail("timing.sequence", "must use the declared deterministic publication order")

    timestamp_policy = _mapping(
        timing["timestamp_policy"],
        "timing.timestamp_policy",
        {
            "strictly_increasing",
            "nonpositive_dt_action",
            "stale_timestamp_action",
            "reset_action",
        },
    )
    expected_timestamp_policy = {
        "strictly_increasing": True,
        "nonpositive_dt_action": "reject_sample",
        "stale_timestamp_action": "reject_sample_preserve_last_valid_state",
        "reset_action": "clear_internal_state_then_require_explicit_initialization",
    }
    if timestamp_policy != expected_timestamp_policy:
        _fail("timing.timestamp_policy", "must define the required reject and reset behavior")

    consumption = _mapping(
        timing["sample_consumption_policy"],
        "timing.sample_consumption_policy",
        {
            "estimator_period_relation",
            "estimator_no_new_imu_action",
            "controller_estimate_requirement",
            "controller_estimate_age_max_ticks",
        },
    )
    expected_consumption = {
        "estimator_period_relation": "estimator_every_ticks_must_equal_imu_every_ticks",
        "estimator_no_new_imu_action": "not_scheduled",
        "controller_estimate_requirement": "consume_estimate_from_current_due_imu_sample",
        "controller_estimate_age_max_ticks": 0,
    }
    if consumption != expected_consumption:
        _fail(
            "timing.sample_consumption_policy",
            "must define current-sample consumption without repeated IMU use",
        )

    event_semantics = _mapping(
        timing["event_tick_semantics"],
        "timing.event_tick_semantics",
        {
            "start_tick",
            "end_tick",
            "event_order",
            "same_signal_overlap",
            "allowed_cross_type_overlap_pairs",
            "command_after_event",
        },
    )
    expected_event_semantics = {
        "start_tick": "inclusive",
        "end_tick": "exclusive",
        "event_order": "nondecreasing_start_tick_then_declaration_order",
        "same_signal_overlap": "reject",
        "command_after_event": "return_affected_axis_to_zero",
    }
    for field, expected in expected_event_semantics.items():
        if event_semantics[field] != expected:
            _fail(f"timing.event_tick_semantics.{field}", f"must be {expected!r}")
    pairs = _list(
        event_semantics["allowed_cross_type_overlap_pairs"],
        "timing.event_tick_semantics.allowed_cross_type_overlap_pairs",
    )
    normalized_pairs: list[str] = []
    for index, pair in enumerate(pairs):
        path = f"timing.event_tick_semantics.allowed_cross_type_overlap_pairs[{index}]"
        if not isinstance(pair, str) or pair.count("|") != 1:
            _fail(path, "must be '<event_type>|<event_type>'")
        left, right = pair.split("|")
        if left not in EVENT_FIELDS or right not in EVENT_FIELDS or left == right:
            _fail(path, "must name two distinct supported event types")
        canonical = "|".join(sorted((left, right)))
        if pair != canonical:
            _fail(path, "must be alphabetically canonical")
        normalized_pairs.append(pair)
    _assert_unique(
        normalized_pairs,
        "timing.event_tick_semantics.allowed_cross_type_overlap_pairs",
    )
    return base_period_s, normalized, set(normalized_pairs)


def _validate_interface_contract(config: dict[str, Any], source_ids: set[str]) -> None:
    contract = _mapping(
        config["interface_contract"],
        "interface_contract",
        {
            "source_ref",
            "numeric_type",
            "timestamp_unit",
            "validity_encoding",
            "messages",
            "component_calls",
        },
    )
    _source_reference(contract["source_ref"], "interface_contract.source_ref", source_ids)
    if contract["numeric_type"] != "float64":
        _fail("interface_contract.numeric_type", "must be float64")
    if contract["timestamp_unit"] != "s":
        _fail("interface_contract.timestamp_unit", "must be s")
    if contract["validity_encoding"] != "explicit_boolean_no_implicit_default":
        _fail(
            "interface_contract.validity_encoding",
            "must require an explicit validity value",
        )

    expected_fields = {
        "attitude_command": {
            "timestamp_s": ("float64", "scalar", "s", "scenario_clock"),
            "q_nb_command": ("float64", "length_4", "1", "body_to_ned"),
            "valid": ("bool", "scalar", "bool", "not_applicable"),
        },
        "imu_sample": {
            "timestamp_s": ("float64", "scalar", "s", "scenario_clock"),
            "gyro_b_rad_s": ("float64", "length_3", "rad/s", "body_frd"),
            "specific_force_b_m_s2": ("float64", "length_3", "m/s2", "body_frd"),
            "valid": ("bool", "scalar", "bool", "not_applicable"),
        },
        "state_estimate": {
            "timestamp_s": ("float64", "scalar", "s", "scenario_clock"),
            "q_nb_estimate": ("float64", "length_4", "1", "body_to_ned"),
            "omega_b_estimate_rad_s": ("float64", "length_3", "rad/s", "body_frd"),
            "valid": ("bool", "scalar", "bool", "not_applicable"),
        },
        "torque_request": {
            "timestamp_s": ("float64", "scalar", "s", "scenario_clock"),
            "requested_torque_body_Nm": ("float64", "length_3", "Nm", "body_frd"),
        },
        "actuator_feedback": {
            "timestamp_s": ("float64", "scalar", "s", "scenario_clock"),
            "limited_torque_body_Nm": ("float64", "length_3", "Nm", "body_frd"),
            "actual_torque_body_Nm": ("float64", "length_3", "Nm", "body_frd"),
            "saturated": ("bool", "length_3", "bool", "body_frd"),
        },
    }
    messages = _mapping(
        contract["messages"],
        "interface_contract.messages",
        set(expected_fields),
    )
    for message_name, field_spec in expected_fields.items():
        path = f"interface_contract.messages.{message_name}"
        fields = _list(messages[message_name], path)
        field_map: dict[str, dict[str, Any]] = {}
        for index, field in enumerate(fields):
            field_path = f"{path}[{index}]"
            record = _mapping(
                field,
                field_path,
                {"name", "type", "shape", "unit", "frame", "validity"},
            )
            name = _string(record["name"], f"{field_path}.name")
            if name in field_map:
                _fail(path, f"must not repeat field {name!r}")
            field_map[name] = record
        if set(field_map) != set(field_spec):
            _fail(path, "must declare the complete named field set")
        for field_name, expected in field_spec.items():
            record = field_map[field_name]
            if (
                record["type"],
                record["shape"],
                record["unit"],
                record["frame"],
            ) != expected:
                _fail(f"{path}.{field_name}", "has an incompatible type, shape, unit, or frame")
            _string(record["validity"], f"{path}.{field_name}.validity")

    calls = _mapping(
        contract["component_calls"],
        "interface_contract.component_calls",
        {"plant", "actuator", "estimator", "controller"},
    )
    for component, record in calls.items():
        path = f"interface_contract.component_calls.{component}"
        call = _mapping(record, path, {"reset", "step"})
        _string(call["reset"], f"{path}.reset")
        _string(call["step"], f"{path}.step")


def _validate_quaternion(value: Any, path: str, tolerance: float) -> list[float]:
    quaternion = _vector(value, path, length=4)
    norm = math.sqrt(sum(component * component for component in quaternion))
    if not math.isclose(norm, 1.0, abs_tol=tolerance):
        _fail(path, "must be a unit quaternion within configured tolerance")
    return quaternion


def _validate_initialization_contract(
    config: dict[str, Any],
    source_ids: set[str],
    tolerance: float,
) -> None:
    contract = _mapping(
        config["initialization_contract"],
        "initialization_contract",
        {
            "source_ref",
            "tick_zero",
            "default_component_state",
            "scenario_field_ownership",
            "initial_attitude_offset",
        },
    )
    _source_reference(contract["source_ref"], "initialization_contract.source_ref", source_ids)

    tick_zero = _mapping(
        contract["tick_zero"],
        "initialization_contract.tick_zero",
        {
            "timestamp_s",
            "integration_before_tick_zero",
            "first_interval",
            "reset_epoch_initial",
            "rng_rule",
        },
    )
    if _number(tick_zero["timestamp_s"], "initialization_contract.tick_zero.timestamp_s") != 0.0:
        _fail("initialization_contract.tick_zero.timestamp_s", "must be zero")
    if tick_zero["integration_before_tick_zero"] is not False:
        _fail(
            "initialization_contract.tick_zero.integration_before_tick_zero",
            "must be false",
        )
    if tick_zero["first_interval"] != "[0, base_period_s)":
        _fail(
            "initialization_contract.tick_zero.first_interval",
            "must define the first half-open interval",
        )
    if _integer(
        tick_zero["reset_epoch_initial"],
        "initialization_contract.tick_zero.reset_epoch_initial",
        nonnegative=True,
    ) != 0:
        _fail("initialization_contract.tick_zero.reset_epoch_initial", "must be zero")
    if tick_zero["rng_rule"] != "seed_from_scenario_seed_before_any_noise_draw":
        _fail("initialization_contract.tick_zero.rng_rule", "must seed before noise draw")

    state = _mapping(
        contract["default_component_state"],
        "initialization_contract.default_component_state",
        {
            "plant_q_nb",
            "plant_omega_b_rad_s",
            "estimator_q_nb",
            "estimator_omega_b_rad_s",
            "command_q_nb",
            "actuator_limited_torque_Nm",
            "actuator_actual_torque_Nm",
            "controller_integral_Nm",
            "controller_derivative_filter_rad_s2",
        },
    )
    for name in ("plant_q_nb", "estimator_q_nb", "command_q_nb"):
        _validate_quaternion(
            state[name],
            f"initialization_contract.default_component_state.{name}",
            tolerance,
        )
    for name in (
        "plant_omega_b_rad_s",
        "estimator_omega_b_rad_s",
        "actuator_limited_torque_Nm",
        "actuator_actual_torque_Nm",
        "controller_integral_Nm",
        "controller_derivative_filter_rad_s2",
    ):
        values = _vector(
            state[name],
            f"initialization_contract.default_component_state.{name}",
            length=3,
        )
        if any(value != 0.0 for value in values):
            _fail(
                f"initialization_contract.default_component_state.{name}",
                "must explicitly reset to zero",
            )

    ownership = _mapping(
        contract["scenario_field_ownership"],
        "initialization_contract.scenario_field_ownership",
        {
            "initial_q_nb",
            "initial_body_rate_rad_s",
            "initial_attitude_offset_rad",
            "estimator_initial_state",
            "command_initial_state",
            "actuator_and_controller_initial_state",
        },
    )
    expected_ownership = {
        "initial_q_nb": "plant_truth_q_nb_only",
        "initial_body_rate_rad_s": "plant_truth_omega_b_only",
        "initial_attitude_offset_rad": "plant_truth_only_right_multiplicative_body_xyz",
        "estimator_initial_state": (
            "default_component_state_unless_future_version_adds_explicit_scenario_override"
        ),
        "command_initial_state": "default_component_state",
        "actuator_and_controller_initial_state": "default_component_state",
    }
    if ownership != expected_ownership:
        _fail(
            "initialization_contract.scenario_field_ownership",
            "must distinguish plant, estimator, command, actuator, and controller state",
        )

    offset = _mapping(
        contract["initial_attitude_offset"],
        "initialization_contract.initial_attitude_offset",
        {"owner", "composition", "rotation_sequence", "estimator_truth_rule"},
    )
    expected_offset = {
        "owner": "plant_truth_only",
        "composition": (
            "q_nb_initial = q_nb_base hamilton_product qx(roll) hamilton_product "
            "qy(pitch) hamilton_product qz(yaw)"
        ),
        "rotation_sequence": "body_frd_intrinsic_x_then_y_then_z",
        "estimator_truth_rule": (
            "estimator_reset_uses_explicit_estimator_q_nb_and_never_receives_live_truth"
        ),
    }
    if offset != expected_offset:
        _fail(
            "initialization_contract.initial_attitude_offset",
            "must define owner, composition, sequence, and estimator truth isolation",
        )


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
    plant = _mapping(
        config["plant_contract"],
        "plant_contract",
        {
            "source_ref",
            "implementation_status",
            "state",
            "inertia_kg_m2",
            "inertia_reference_frame",
            "integrator_contract",
            "truth_visibility",
            "parameter_rationale",
        },
    )
    _source_reference(plant["source_ref"], "plant_contract.source_ref", source_ids)
    if plant["implementation_status"] != "future_g1_contract_only":
        _fail("plant_contract.implementation_status", "must stay a future G1 contract")
    if plant["state"] != ["q_nb", "omega_b_rad_s"]:
        _fail("plant_contract.state", "must use q_nb and body angular rate")
    if plant["inertia_reference_frame"] != "body_frd":
        _fail("plant_contract.inertia_reference_frame", "must be body_frd")
    _string(plant["parameter_rationale"], "plant_contract.parameter_rationale")
    _validate_spd(plant["inertia_kg_m2"], "plant_contract.inertia_kg_m2")

    integrator = _mapping(
        plant["integrator_contract"],
        "plant_contract.integrator_contract",
        {"method", "step_halving_check_required"},
    )
    if integrator != {"method": "rk4", "step_halving_check_required": True}:
        _fail("plant_contract.integrator_contract", "must retain the proposed G1 check")

    visibility = _mapping(
        plant["truth_visibility"],
        "plant_contract.truth_visibility",
        {"allowed_consumers", "forbidden_consumers"},
    )
    allowed = _list(
        visibility["allowed_consumers"],
        "plant_contract.truth_visibility.allowed_consumers",
    )
    forbidden = _list(
        visibility["forbidden_consumers"],
        "plant_contract.truth_visibility.forbidden_consumers",
    )
    if set(forbidden) != {"estimator", "controller"}:
        _fail(
            "plant_contract.truth_visibility.forbidden_consumers",
            "must forbid estimator and controller",
        )
    if {"estimator", "controller"} & set(allowed):
        _fail(
            "plant_contract.truth_visibility.allowed_consumers",
            "must not expose truth to estimator/controller",
        )


def _validate_actuator(config: dict[str, Any], source_ids: set[str]) -> list[float]:
    actuator = _mapping(
        config["actuator_contract"],
        "actuator_contract",
        {
            "source_ref",
            "implementation_status",
            "requested_torque",
            "limited_target_torque",
            "actual_torque",
            "model",
            "time_constant_s",
            "limits_Nm",
            "antiwindup",
            "parameter_rationale",
        },
    )
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
    _string(actuator["parameter_rationale"], "actuator_contract.parameter_rationale")
    limits = _vector(
        actuator["limits_Nm"],
        "actuator_contract.limits_Nm",
        length=3,
        nonnegative=True,
    )
    if any(limit == 0.0 for limit in limits):
        _fail("actuator_contract.limits_Nm", "must contain meaningful positive limits")

    antiwindup = _mapping(
        actuator["antiwindup"],
        "actuator_contract.antiwindup",
        {
            "strategy",
            "integrator_state",
            "discrete_update",
            "conditional_integration",
            "limit_feedback",
            "actuator_lag_feedback",
            "reset_value_Nm",
        },
    )
    if antiwindup["strategy"] != "conditional_integration_plus_back_calculation":
        _fail("actuator_contract.antiwindup.strategy", "must select complete anti-windup")
    if antiwindup["integrator_state"] != "integral_torque_contribution_body_Nm":
        _fail(
            "actuator_contract.antiwindup.integrator_state",
            "must use the declared torque-contribution state",
        )
    if antiwindup["discrete_update"] != (
        "I_next=clamp(I+dt*(conditional_ki_rate_error+"
        "kaw_limit*(limited_target-requested)+"
        "kaw_lag*(actual-limited_target)),-I_limit,I_limit)"
    ):
        _fail(
            "actuator_contract.antiwindup.discrete_update",
            "must include conditional, limit, and lag feedback terms",
        )

    conditional = _mapping(
        antiwindup["conditional_integration"],
        "actuator_contract.antiwindup.conditional_integration",
        {"block_when", "allow_when"},
    )
    if conditional != {
        "block_when": "requested_minus_limited_has_same_sign_as_rate_error",
        "allow_when": "not_limited_or_rate_error_reduces_saturation",
    }:
        _fail(
            "actuator_contract.antiwindup.conditional_integration",
            "must define the saturation-direction conditional rule",
        )

    limit_feedback = _mapping(
        antiwindup["limit_feedback"],
        "actuator_contract.antiwindup.limit_feedback",
        {"signal", "availability", "gain_per_s"},
    )
    if limit_feedback["signal"] != "limited_target_minus_requested_torque_body_Nm":
        _fail(
            "actuator_contract.antiwindup.limit_feedback.signal",
            "must feed back the pre-limit request error",
        )
    if limit_feedback["availability"] != "same_controller_tick_after_componentwise_limit":
        _fail(
            "actuator_contract.antiwindup.limit_feedback.availability",
            "must be available in the same controller tick",
        )
    _vector(
        limit_feedback["gain_per_s"],
        "actuator_contract.antiwindup.limit_feedback.gain_per_s",
        length=3,
        nonnegative=True,
    )
    if any(value == 0.0 for value in limit_feedback["gain_per_s"]):
        _fail(
            "actuator_contract.antiwindup.limit_feedback.gain_per_s",
            "must be positive on each axis",
        )

    lag_feedback = _mapping(
        antiwindup["actuator_lag_feedback"],
        "actuator_contract.antiwindup.actuator_lag_feedback",
        {"signal", "availability", "delay_ticks", "gain_per_s"},
    )
    if lag_feedback["signal"] != "actual_minus_limited_target_torque_body_Nm":
        _fail(
            "actuator_contract.antiwindup.actuator_lag_feedback.signal",
            "must distinguish actuator lag from limit feedback",
        )
    if (
        lag_feedback["availability"]
        != "actuator_state_after_current_tick_advance_from_previous_limited_target"
    ):
        _fail(
            "actuator_contract.antiwindup.actuator_lag_feedback.availability",
            "must declare the actuator-state timing",
        )
    if _integer(
        lag_feedback["delay_ticks"],
        "actuator_contract.antiwindup.actuator_lag_feedback.delay_ticks",
        positive=True,
    ) != 1:
        _fail(
            "actuator_contract.antiwindup.actuator_lag_feedback.delay_ticks",
            "must be one publication delay",
        )
    _vector(
        lag_feedback["gain_per_s"],
        "actuator_contract.antiwindup.actuator_lag_feedback.gain_per_s",
        length=3,
        nonnegative=True,
    )
    reset = _vector(
        antiwindup["reset_value_Nm"],
        "actuator_contract.antiwindup.reset_value_Nm",
        length=3,
    )
    if any(value != 0.0 for value in reset):
        _fail("actuator_contract.antiwindup.reset_value_Nm", "must reset to zero")
    return limits


def _validate_imu(
    config: dict[str, Any],
    source_ids: set[str],
    schedules: dict[str, int],
) -> None:
    imu = _mapping(
        config["imu_contract"],
        "imu_contract",
        {
            "source_ref",
            "implementation_status",
            "sample_period_ticks",
            "sample_location",
            "timestamp",
            "gravity_ned_m_s2",
            "specific_force_definition",
            "gyro",
            "accelerometer",
            "parameter_rationale",
        },
    )
    _source_reference(imu["source_ref"], "imu_contract.source_ref", source_ids)
    if imu["implementation_status"] != "future_g1_contract_only":
        _fail("imu_contract.implementation_status", "must stay a future G1 contract")
    if (
        _integer(imu["sample_period_ticks"], "imu_contract.sample_period_ticks", positive=True)
        != schedules["imu_every_ticks"]
    ):
        _fail("imu_contract.sample_period_ticks", "must match timing.schedules.imu_every_ticks")
    expected_imu = {
        "sample_location": "center_of_gravity",
        "timestamp": "end_of_interval",
        "specific_force_definition": "f_b = a_b - R_nb_transpose_times_g_n",
    }
    for field, expected in expected_imu.items():
        if imu[field] != expected:
            _fail(f"imu_contract.{field}", f"must be {expected!r}")
    _string(imu["parameter_rationale"], "imu_contract.parameter_rationale")
    gravity = _vector(imu["gravity_ned_m_s2"], "imu_contract.gravity_ned_m_s2", length=3)
    if gravity[2] <= 0.0:
        _fail("imu_contract.gravity_ned_m_s2", "must use positive Down gravity in NED")

    for sensor_name, noise_field, bias_field in (
        ("gyro", "noise_std_rad_s", "bias_rad_s"),
        ("accelerometer", "noise_std_m_s2", "bias_m_s2"),
    ):
        path = f"imu_contract.{sensor_name}"
        sensor = _mapping(
            imu[sensor_name],
            path,
            {noise_field, bias_field, "noise_representation"},
        )
        if sensor["noise_representation"] != (
            "per_sample_independent_gaussian_standard_deviation"
        ):
            _fail(f"{path}.noise_representation", "must declare per-sample standard deviation")
        _vector(sensor[noise_field], f"{path}.{noise_field}", length=3, nonnegative=True)
        _vector(sensor[bias_field], f"{path}.{bias_field}", length=3)


def _validate_estimator(config: dict[str, Any]) -> None:
    estimator = _mapping(
        config["estimator_contract"],
        "estimator_contract",
        {
            "implementation_status",
            "input",
            "output",
            "truth_inputs_allowed_only_for",
            "truth_inputs_forbidden_after_reset",
            "normalize_after",
            "absolute_yaw_observation",
            "invalid_sample_action",
            "input_message",
            "output_message",
            "reset_contract",
            "step_contract",
            "no_new_imu_action",
        },
    )
    expected = {
        "implementation_status": "future_g2_contract_only",
        "input": "imu_sample_with_timestamp_and_validity",
        "output": "estimated_q_nb_and_estimated_omega_b_rad_s",
        "truth_inputs_allowed_only_for": "explicit_reset_initialization",
        "truth_inputs_forbidden_after_reset": True,
        "absolute_yaw_observation": "not_available_from_six_axis_imu",
        "invalid_sample_action": "reject_sample_preserve_last_valid_state",
        "input_message": "imu_sample",
        "output_message": "state_estimate",
        "reset_contract": (
            "reset_uses_initialization_contract.default_component_state.estimator_values_"
            "and_never_accepts_live_truth"
        ),
        "step_contract": (
            "one_new_valid_imu_sample_per_due_estimator_tick_or_reject_without_state_change"
        ),
        "no_new_imu_action": "not_scheduled",
    }
    for field, expected_value in expected.items():
        if estimator[field] != expected_value:
            _fail(f"estimator_contract.{field}", f"must be {expected_value!r}")
    if set(_list(estimator["normalize_after"], "estimator_contract.normalize_after")) != {
        "propagation",
        "correction",
    }:
        _fail("estimator_contract.normalize_after", "must normalize after propagation and correction")


def _validate_gain(value: Any, path: str) -> dict[str, Any]:
    gain = _mapping(value, path, {"initial", "minimum", "maximum", "unit"})
    initial = _vector(gain["initial"], f"{path}.initial", length=3, nonnegative=True)
    minimum = _vector(gain["minimum"], f"{path}.minimum", length=3, nonnegative=True)
    maximum = _vector(gain["maximum"], f"{path}.maximum", length=3, nonnegative=True)
    _string(gain["unit"], f"{path}.unit")
    for index, (low, candidate, high) in enumerate(zip(minimum, initial, maximum)):
        if low > candidate or candidate > high:
            _fail(path, f"axis {index} must satisfy minimum <= initial <= maximum")
        if high <= 0.0:
            _fail(path, f"axis {index} maximum must be meaningful and positive")
    return gain


def _validate_controller(
    config: dict[str, Any],
    source_ids: set[str],
    limits: list[float],
) -> None:
    controller = _mapping(
        config["controller_contract"],
        "controller_contract",
        {
            "source_ref",
            "implementation_status",
            "input",
            "output",
            "truth_inputs_forbidden",
            "attitude_error",
            "attitude_kp",
            "rate_pid",
            "input_messages",
            "output_message",
            "body_rate_target_limit_rad_s",
            "parameter_rationale",
        },
    )
    _source_reference(controller["source_ref"], "controller_contract.source_ref", source_ids)
    expected = {
        "implementation_status": "future_g2_contract_only",
        "input": "attitude_command_state_estimate_and_actuator_feedback_only",
        "output": "requested_torque_body_Nm",
        "truth_inputs_forbidden": True,
        "output_message": "torque_request",
    }
    for field, expected_value in expected.items():
        if controller[field] != expected_value:
            _fail(f"controller_contract.{field}", f"must be {expected_value!r}")
    if controller["input_messages"] != [
        "attitude_command",
        "state_estimate",
        "actuator_feedback",
    ]:
        _fail(
            "controller_contract.input_messages",
            "must declare command, estimate, and actuator feedback only",
        )
    _vector(
        controller["body_rate_target_limit_rad_s"],
        "controller_contract.body_rate_target_limit_rad_s",
        length=3,
        nonnegative=True,
    )
    if any(value == 0.0 for value in controller["body_rate_target_limit_rad_s"]):
        _fail(
            "controller_contract.body_rate_target_limit_rad_s",
            "must be meaningful and positive on each axis",
        )
    _string(controller["parameter_rationale"], "controller_contract.parameter_rationale")

    attitude_error = _mapping(
        controller["attitude_error"],
        "controller_contract.attitude_error",
        {"equation", "shortest_path", "half_turn_tie_break"},
    )
    expected_error = {
        "equation": "conjugate_q_nb_est_hamilton_product_q_nb_command",
        "shortest_path": "negate_error_quaternion_when_scalar_part_is_negative",
        "half_turn_tie_break": "at_zero_scalar_choose_first_nonzero_vector_component_positive",
    }
    if attitude_error != expected_error:
        _fail(
            "controller_contract.attitude_error",
            "must define deterministic sign and half-turn behavior",
        )

    attitude_gain = _validate_gain(
        controller["attitude_kp"],
        "controller_contract.attitude_kp",
    )
    if attitude_gain["unit"] != "1/s":
        _fail("controller_contract.attitude_kp.unit", "must be '1/s'")

    rate_pid = _mapping(
        controller["rate_pid"],
        "controller_contract.rate_pid",
        {
            "kp",
            "ki",
            "kd",
            "integrator_limit_Nm",
            "integrator_state",
            "integrator_reset_value_Nm",
            "integration_rule",
            "derivative_rule",
            "derivative_filter",
            "output_limit_source",
        },
    )
    expected_units = {"kp": "Nm*s/rad", "ki": "Nm/rad", "kd": "Nm*s2/rad"}
    for term, expected_unit in expected_units.items():
        gain = _validate_gain(rate_pid[term], f"controller_contract.rate_pid.{term}")
        if gain["unit"] != expected_unit:
            _fail(f"controller_contract.rate_pid.{term}.unit", f"must be {expected_unit!r}")
    integrator_limits = _vector(
        rate_pid["integrator_limit_Nm"],
        "controller_contract.rate_pid.integrator_limit_Nm",
        length=3,
        nonnegative=True,
    )
    for index, (integrator_limit, actuator_limit) in enumerate(
        zip(integrator_limits, limits)
    ):
        if integrator_limit <= 0.0 or integrator_limit > actuator_limit:
            _fail(
                "controller_contract.rate_pid.integrator_limit_Nm",
                f"axis {index} must be positive and no greater than actuator limit",
            )
    if rate_pid["integrator_state"] != "integral_torque_contribution_body_Nm":
        _fail(
            "controller_contract.rate_pid.integrator_state",
            "must use the declared torque contribution state",
        )
    reset = _vector(
        rate_pid["integrator_reset_value_Nm"],
        "controller_contract.rate_pid.integrator_reset_value_Nm",
        length=3,
    )
    if any(value != 0.0 for value in reset):
        _fail(
            "controller_contract.rate_pid.integrator_reset_value_Nm",
            "must reset to zero",
        )
    if rate_pid["integration_rule"] != (
        "forward_euler_conditional_integration_plus_back_calculation_using_current_rate_error"
    ):
        _fail(
            "controller_contract.rate_pid.integration_rule",
            "must define the discrete anti-windup integration rule",
        )
    if rate_pid["derivative_rule"] != (
        "differentiate_measured_omega_b_then_apply_first_order_low_pass"
    ):
        _fail(
            "controller_contract.rate_pid.derivative_rule",
            "must define measured-rate differentiation",
        )
    derivative_filter = _mapping(
        rate_pid["derivative_filter"],
        "controller_contract.rate_pid.derivative_filter",
        {"model", "time_constant_s", "reset_value_rad_s2"},
    )
    if derivative_filter["model"] != "first_order_low_pass_on_measured_rate_derivative":
        _fail(
            "controller_contract.rate_pid.derivative_filter.model",
            "must define the first-order derivative filter",
        )
    _number(
        derivative_filter["time_constant_s"],
        "controller_contract.rate_pid.derivative_filter.time_constant_s",
        positive=True,
    )
    derivative_reset = _vector(
        derivative_filter["reset_value_rad_s2"],
        "controller_contract.rate_pid.derivative_filter.reset_value_rad_s2",
        length=3,
    )
    if any(value != 0.0 for value in derivative_reset):
        _fail(
            "controller_contract.rate_pid.derivative_filter.reset_value_rad_s2",
            "must reset to zero",
        )
    if rate_pid["output_limit_source"] != "actuator_contract.limits_Nm":
        _fail(
            "controller_contract.rate_pid.output_limit_source",
            "must use the actuator componentwise limits",
        )


def _validate_seed_policy(config: dict[str, Any]) -> set[int]:
    seeds = _mapping(config["seed_policy"], "seed_policy", {"tuning_seed", "acceptance_seeds", "rule"})
    tuning_seed = _integer(seeds["tuning_seed"], "seed_policy.tuning_seed", nonnegative=True)
    acceptance = [
        _integer(value, f"seed_policy.acceptance_seeds[{index}]", nonnegative=True)
        for index, value in enumerate(
            _list(seeds["acceptance_seeds"], "seed_policy.acceptance_seeds", length=8)
        )
    ]
    _assert_unique(acceptance, "seed_policy.acceptance_seeds")
    if tuning_seed in acceptance:
        _fail("seed_policy", "tuning seed must not be an acceptance seed")
    if seeds["rule"] != "acceptance_seeds_are_reserved_and_must_not_be_reused_for_tuning":
        _fail("seed_policy.rule", "must reserve acceptance seeds from tuning")
    return set(acceptance)


def _validate_acceptance_policy(
    config: dict[str, Any],
    source_ids: set[str],
    base_period_s: float,
) -> int:
    policy = _mapping(
        config["acceptance_policy"],
        "acceptance_policy",
        {
            "source_ref",
            "status",
            "attitude_error",
            "settling",
            "overshoot",
            "saturation",
            "metric_definitions",
            "outcome_classes",
        },
    )
    _source_reference(policy["source_ref"], "acceptance_policy.source_ref", source_ids)
    if policy["status"] != "proposed_pending_maintainer_approval":
        _fail("acceptance_policy.status", "must remain proposed pending maintainer approval")

    attitude_error = _mapping(
        policy["attitude_error"],
        "acceptance_policy.attitude_error",
        {"sign_equivalent_angle_formula", "unit"},
    )
    if attitude_error != {
        "sign_equivalent_angle_formula": (
            "2*acos(clamp(abs(dot(q_reference,q_candidate)),0,1))"
        ),
        "unit": "rad",
    }:
        _fail("acceptance_policy.attitude_error", "must define sign-equivalent quaternion error")

    settling = _mapping(
        policy["settling"],
        "acceptance_policy.settling",
        {
            "band_rad",
            "dwell_s",
            "command_step_time_origin",
            "disturbance_recovery_time_origin",
            "initial_offset_time_origin",
            "entry_rule",
            "deadline_rule",
            "unfinished_action",
            "missing_data_action",
        },
    )
    _number(settling["band_rad"], "acceptance_policy.settling.band_rad", positive=True)
    dwell = _number(settling["dwell_s"], "acceptance_policy.settling.dwell_s", positive=True)
    dwell_ticks = round(dwell / base_period_s)
    if not math.isclose(dwell / base_period_s, dwell_ticks, abs_tol=1e-9):
        _fail("acceptance_policy.settling.dwell_s", "must be an integer number of base ticks")
    expected_settling = {
        "command_step_time_origin": "event_start_tick",
        "disturbance_recovery_time_origin": "event_end_tick",
        "initial_offset_time_origin": "scenario_tick_zero",
        "entry_rule": "first sample inside band that remains inside for the full dwell interval",
        "deadline_rule": (
            "window_must_include_limit_plus_dwell_after_the_applicable_origin"
        ),
        "unfinished_action": "performance_fail",
        "missing_data_action": "execution_error_inconclusive",
    }
    for field, expected in expected_settling.items():
        if settling[field] != expected:
            _fail(f"acceptance_policy.settling.{field}", f"must be {expected!r}")

    overshoot = _mapping(
        policy["overshoot"],
        "acceptance_policy.overshoot",
        {
            "reference",
            "denominator",
            "direction",
            "zero_command_action",
            "missing_data_action",
            "unit",
        },
    )
    expected_overshoot = {
        "reference": "signed_command_delta_from_pre_event_command_to_event_target",
        "denominator": "absolute_value_of_signed_command_delta",
        "direction": "project_tracking_error_along_signed_command_delta",
        "zero_command_action": "not_applicable",
        "missing_data_action": "execution_error_inconclusive",
        "unit": "percent",
    }
    if overshoot != expected_overshoot:
        _fail("acceptance_policy.overshoot", "must define signed step overshoot semantics")

    saturation = _mapping(
        policy["saturation"],
        "acceptance_policy.saturation",
        {"trigger_definition", "trigger_coverage_rule", "missing_data_action"},
    )
    expected_saturation = {
        "trigger_definition": (
            "any_axis_abs_requested_torque_exceeds_limit_and_limited_torque_"
            "equals_componentwise_clamp"
        ),
        "trigger_coverage_rule": (
            "saturation_withdrawal_requires_positive_duration_during_its_command_event"
        ),
        "missing_data_action": "execution_error_inconclusive",
    }
    if saturation != expected_saturation:
        _fail("acceptance_policy.saturation", "must define trigger and coverage semantics")

    definitions = _mapping(
        policy["metric_definitions"],
        "acceptance_policy.metric_definitions",
        set(METRIC_SPECS),
    )
    for metric, spec in METRIC_SPECS.items():
        path = f"acceptance_policy.metric_definitions.{metric}"
        definition = _mapping(
            definitions[metric],
            path,
            {"source_signals", "formula", "axis_aggregation", "invalid_data_action"},
        )
        signals = _list(definition["source_signals"], f"{path}.source_signals")
        if any(not isinstance(signal, str) for signal in signals):
            _fail(f"{path}.source_signals", "must contain signal names")
        if set(signals) != spec["observations"] or len(signals) != len(set(signals)):
            _fail(f"{path}.source_signals", "must match the metric signal dependency set")
        _string(definition["formula"], f"{path}.formula")
        _string(definition["axis_aggregation"], f"{path}.axis_aggregation")
        if definition["invalid_data_action"] != "execution_error_inconclusive":
            _fail(
                f"{path}.invalid_data_action",
                "must classify missing data as execution_error_inconclusive",
            )

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
    return dwell_ticks


def _validate_event(event: Any, path: str, total_ticks: int) -> dict[str, Any]:
    all_specific = set().union(*EVENT_FIELDS.values())
    record = _mapping(event, path, EVENT_COMMON_FIELDS, EVENT_COMMON_FIELDS | all_specific)
    event_type = record["type"]
    if not isinstance(event_type, str) or event_type not in EVENT_FIELDS:
        _fail(f"{path}.type", "must be a supported event type")
    record = _mapping(
        record,
        path,
        EVENT_COMMON_FIELDS | EVENT_FIELDS[event_type],
        EVENT_COMMON_FIELDS | EVENT_FIELDS[event_type],
    )
    _string(record["id"], f"{path}.id")
    start = _integer(record["start_tick"], f"{path}.start_tick", nonnegative=True)
    end = _integer(record["end_tick"], f"{path}.end_tick", positive=True)
    if start >= end or end > total_ticks:
        _fail(path, "must satisfy 0 <= start_tick < end_tick <= scenario ticks")

    if event_type == "command_step":
        if not isinstance(record["axis"], str) or record["axis"] not in {"x", "y", "z"}:
            _fail(f"{path}.axis", "must be x, y, or z")
        _number(record["value_rad"], f"{path}.value_rad")
        if record["post_event_action"] != "return_axis_to_zero":
            _fail(f"{path}.post_event_action", "must be return_axis_to_zero")
    elif event_type == "external_torque":
        values = _vector(record["vector_Nm"], f"{path}.vector_Nm", length=3)
        if not any(value != 0.0 for value in values):
            _fail(f"{path}.vector_Nm", "must excite at least one axis")
    elif event_type == "imu_bias":
        _vector(record["gyro_bias_rad_s"], f"{path}.gyro_bias_rad_s", length=3)
        _vector(
            record["accelerometer_bias_m_s2"],
            f"{path}.accelerometer_bias_m_s2",
            length=3,
        )
        if record["application"] != "replace_nominal_bias":
            _fail(f"{path}.application", "must be replace_nominal_bias")
    elif event_type == "specific_force_disturbance":
        values = _vector(record["vector_m_s2"], f"{path}.vector_m_s2", length=3)
        if not any(value != 0.0 for value in values):
            _fail(f"{path}.vector_m_s2", "must excite at least one axis")
        if record["application"] != "additive_to_nominal_specific_force":
            _fail(f"{path}.application", "must be additive_to_nominal_specific_force")
    elif event_type == "invalid_input":
        if (
            not isinstance(record["invalid_kind"], str)
            or record["invalid_kind"] not in {"negative_dt", "stale_timestamp"}
        ):
            _fail(f"{path}.invalid_kind", "must be negative_dt or stale_timestamp")
    elif event_type == "reset" and record["target"] != "all_components":
        _fail(f"{path}.target", "must be all_components")
    return record


def _event_domain(event: dict[str, Any]) -> str:
    event_type = event["type"]
    if event_type == "command_step":
        return f"command_axis:{event['axis']}"
    return event_type


def _event_pair(event: dict[str, Any], other: dict[str, Any]) -> str:
    return "|".join(sorted((event["type"], other["type"])))


def _validate_event_schedule(
    events: list[dict[str, Any]],
    path: str,
    allowed_cross_type_pairs: set[str],
) -> None:
    prior_start = -1
    for index, event in enumerate(events):
        start = event["start_tick"]
        if start < prior_start:
            _fail(f"{path}[{index}].start_tick", "must be nondecreasing")
        prior_start = start
        for earlier_index, earlier in enumerate(events[:index]):
            overlaps = (
                earlier["start_tick"] < event["end_tick"]
                and event["start_tick"] < earlier["end_tick"]
            )
            if not overlaps:
                continue
            if _event_domain(earlier) == _event_domain(event):
                _fail(
                    f"{path}[{index}]",
                    f"overlaps same signal with {path}[{earlier_index}]",
                )
            if _event_pair(earlier, event) not in allowed_cross_type_pairs:
                _fail(
                    f"{path}[{index}]",
                    f"overlaps undeclared cross-type event {path}[{earlier_index}]",
                )


def _validate_criterion(
    criterion: Any,
    path: str,
    total_ticks: int,
    observations: set[str],
    events_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    required = {
        "id",
        "metric",
        "reducer",
        "operator",
        "limit",
        "unit",
        "window",
        "evidence_status",
    }
    record = _mapping(criterion, path, required, required | {"event_id"})
    _string(record["id"], f"{path}.id")
    metric = record["metric"]
    if not isinstance(metric, str) or metric not in METRIC_SPECS:
        _fail(f"{path}.metric", "must be a supported metric")
    spec = METRIC_SPECS[metric]
    if not isinstance(record["reducer"], str) or record["reducer"] not in spec["reducers"]:
        _fail(f"{path}.reducer", f"is incompatible with metric {metric}")
    if not isinstance(record["unit"], str) or record["unit"] != spec["unit"]:
        _fail(f"{path}.unit", f"must be {spec['unit']!r} for metric {metric}")
    if record["evidence_status"] != "proposed_not_executed":
        _fail(f"{path}.evidence_status", "must not claim unexecuted performance")
    missing_observations = spec["observations"] - observations
    if missing_observations:
        _fail(
            f"{path}.metric",
            "requires observations: " + ", ".join(sorted(missing_observations)),
        )

    if spec["value_kind"] == "bool":
        if not isinstance(record["limit"], bool) or record["operator"] != "==":
            _fail(path, "boolean metrics require == and a boolean limit")
    else:
        _number(record["limit"], f"{path}.limit", nonnegative=True)
        if not isinstance(record["operator"], str) or record["operator"] not in {"<=", ">="}:
            _fail(f"{path}.operator", "numeric metrics require <= or >=")

    window = _mapping(record["window"], f"{path}.window", {"start_tick", "end_tick"})
    start = _integer(window["start_tick"], f"{path}.window.start_tick", nonnegative=True)
    end = _integer(window["end_tick"], f"{path}.window.end_tick", positive=True)
    if start >= end or end > total_ticks:
        _fail(f"{path}.window", "must fit inside the scenario tick range")

    if "event_id" in record:
        event_id = _string(record["event_id"], f"{path}.event_id")
        if event_id not in events_by_id:
            _fail(f"{path}.event_id", "must reference an event in the same scenario")
        allowed_types = spec["event_types"]
        if allowed_types and events_by_id[event_id]["type"] not in allowed_types:
            _fail(f"{path}.event_id", "references an incompatible event type")
        if not allowed_types:
            _fail(f"{path}.event_id", "must not be attached to an event")
    elif metric in METRICS_REQUIRING_EVENT:
        _fail(f"{path}.event_id", f"must bind {metric} to a specific event")
    return record


def _validate_settling_window(
    criterion: dict[str, Any],
    path: str,
    base_period_s: float,
    dwell_ticks: int,
) -> None:
    minimum_ticks = math.ceil(float(criterion["limit"]) / base_period_s) + dwell_ticks
    window = criterion["window"]
    if window["end_tick"] - window["start_tick"] < minimum_ticks:
        _fail(
            f"{path}.window",
            "must contain the settling limit plus the required dwell interval",
        )


def _validate_event_criterion_timing(
    criterion: dict[str, Any],
    path: str,
    event: dict[str, Any],
    base_period_s: float,
    dwell_ticks: int,
) -> None:
    metric = criterion["metric"]
    window = criterion["window"]
    event_type = event["type"]
    if metric in {
        "tracking_settling_time_s",
        "tracking_overshoot_percent",
        "cross_axis_attitude_error_rad",
    }:
        if window["start_tick"] != event["start_tick"] or window["end_tick"] > event["end_tick"]:
            _fail(f"{path}.window", "must be independently bounded by its command event")
        if metric == "tracking_settling_time_s":
            _validate_settling_window(criterion, path, base_period_s, dwell_ticks)
    elif metric == "attitude_settling_time_s":
        if event_type not in {"command_step", "external_torque"}:
            _fail(f"{path}.event_id", "must bind settling only to a command or disturbance")
        if window["start_tick"] != event["end_tick"]:
            _fail(f"{path}.window.start_tick", "must start at the event end for recovery")
        _validate_settling_window(criterion, path, base_period_s, dwell_ticks)
    elif metric == "actuator_saturation_time_s":
        if (
            window["start_tick"] < event["start_tick"]
            or window["end_tick"] > event["end_tick"]
        ):
            _fail(f"{path}.window", "must be bounded by its saturation command event")
    elif metric == "limitation_event_recorded":
        if window != {"start_tick": event["start_tick"], "end_tick": event["end_tick"]}:
            _fail(f"{path}.window", "must exactly cover its contamination event")
    elif metric == "reset_replay_match":
        if window["start_tick"] != event["start_tick"]:
            _fail(f"{path}.window.start_tick", "must start at the reset event")


def _validate_tri_axis_steps(events: list[dict[str, Any]], path: str) -> None:
    if len(events) != 6:
        _fail(path, "must provide signed steps for all three body axes")
    by_axis: dict[str, list[float]] = {"x": [], "y": [], "z": []}
    for event in events:
        if event["type"] != "command_step":
            _fail(path, "must only contain command steps")
        value = float(event["value_rad"])
        if value == 0.0:
            _fail(path, "must not contain a zero command step")
        by_axis[event["axis"]].append(value)
    for axis, values in by_axis.items():
        if (
            len(values) != 2
            or not any(value > 0.0 for value in values)
            or not any(value < 0.0 for value in values)
        ):
            _fail(path, f"must provide one positive and one negative {axis}-axis step")


def _validate_required_acceptance(
    scenario_id: str,
    criteria: list[tuple[dict[str, Any], str]],
    events: list[dict[str, Any]],
) -> None:
    metric_set = {criterion["metric"] for criterion, _ in criteria}
    missing_metrics = REQUIRED_SCENARIO_METRICS[scenario_id] - metric_set
    if missing_metrics:
        _fail(
            "scenarios",
            f"{scenario_id} is missing mandatory metric(s): {', '.join(sorted(missing_metrics))}",
        )

    criteria_by_event: dict[str, set[str]] = {}
    for criterion, _ in criteria:
        event_id = criterion.get("event_id")
        if isinstance(event_id, str):
            criteria_by_event.setdefault(event_id, set()).add(criterion["metric"])

    if scenario_id == "saturation_withdrawal":
        command_event = events[0]
        if float(command_event["value_rad"]) == 0.0:
            _fail(
                "scenarios",
                "saturation_withdrawal must use a non-zero command excitation",
            )
        trigger_criteria = [
            criterion
            for criterion, _ in criteria
            if criterion.get("event_id") == command_event["id"]
            and criterion["metric"] == "actuator_saturation_time_s"
            and criterion["operator"] == ">="
            and float(criterion["limit"]) > 0.0
        ]
        if not trigger_criteria:
            _fail(
                "scenarios",
                "saturation_withdrawal requires a positive saturation trigger criterion",
            )

    for event in events:
        required_metrics = REQUIRED_EVENT_METRICS.get(scenario_id, {}).get(
            event["type"],
            set(),
        )
        if not required_metrics:
            continue
        present = criteria_by_event.get(event["id"], set())
        missing = required_metrics - present
        if missing:
            _fail(
                "scenarios",
                f"{scenario_id} event {event['id']!r} is missing mandatory metric(s): "
                + ", ".join(sorted(missing)),
            )

def _validate_scenarios(
    config: dict[str, Any],
    source_ids: set[str],
    acceptance_seeds: set[int],
    base_period_s: float,
    quaternion_tolerance: float,
    dwell_ticks: int,
    allowed_cross_type_pairs: set[str],
) -> None:
    scenarios = _list(config["scenarios"], "scenarios", length=len(EXPECTED_SCENARIOS))
    scenario_ids: list[str] = []
    used_seeds: list[int] = []
    artifact_paths: list[str] = []
    criterion_ids: list[str] = []

    required = {
        "id",
        "class",
        "source_ref",
        "seed",
        "duration_s",
        "initial_q_nb",
        "initial_body_rate_rad_s",
        "events",
        "observations",
        "artifact_path",
        "acceptance",
    }
    allowed = required | {"initial_attitude_offset_rad", "initial_attitude_offset_owner"}

    for index, scenario in enumerate(scenarios):
        path = f"scenarios[{index}]"
        record = _mapping(scenario, path, required, allowed)
        scenario_id = record["id"]
        if not isinstance(scenario_id, str) or scenario_id not in EXPECTED_SCENARIOS:
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
            _vector(
                record.get("initial_attitude_offset_rad"),
                f"{path}.initial_attitude_offset_rad",
                length=3,
            )
            if record.get("initial_attitude_offset_owner") != "plant_truth_only":
                _fail(
                    f"{path}.initial_attitude_offset_owner",
                    "must be plant_truth_only",
                )
        elif (
            "initial_attitude_offset_rad" in record
            or "initial_attitude_offset_owner" in record
        ):
            _fail(
                f"{path}.initial_attitude_offset_rad",
                "is reserved for initial_attitude_offset",
            )

        raw_events = _list(record["events"], f"{path}.events")
        events = [
            _validate_event(event, f"{path}.events[{event_index}]", total_ticks)
            for event_index, event in enumerate(raw_events)
        ]
        event_ids = [event["id"] for event in events]
        _assert_unique(event_ids, f"{path}.events[].id")
        _validate_event_schedule(events, f"{path}.events", allowed_cross_type_pairs)
        event_types = {event["type"] for event in events}
        if event_types != EXPECTED_EVENT_TYPES[scenario_id]:
            _fail(f"{path}.events", "does not provide the required event class(es)")
        if scenario_id == "tri_axis_signed_steps":
            _validate_tri_axis_steps(events, f"{path}.events")

        observations = _list(record["observations"], f"{path}.observations")
        if not observations or any(
            not isinstance(item, str) or item not in OBSERVATIONS
            for item in observations
        ):
            _fail(f"{path}.observations", "must contain known observation field names")
        _assert_unique(observations, f"{path}.observations")
        observation_set = set(observations)

        artifact_path = record["artifact_path"]
        expected_artifact_path = f"artifacts/b0/{scenario_id}/"
        if artifact_path != expected_artifact_path:
            _fail(f"{path}.artifact_path", f"must be {expected_artifact_path!r}")

        raw_acceptance = _list(record["acceptance"], f"{path}.acceptance")
        if not raw_acceptance:
            _fail(f"{path}.acceptance", "must not be empty")
        events_by_id = {event["id"]: event for event in events}
        criteria: list[tuple[dict[str, Any], str]] = []
        for criterion_index, criterion in enumerate(raw_acceptance):
            criterion_path = f"{path}.acceptance[{criterion_index}]"
            validated = _validate_criterion(
                criterion,
                criterion_path,
                total_ticks,
                observation_set,
                events_by_id,
            )
            if "event_id" in validated:
                _validate_event_criterion_timing(
                    validated,
                    criterion_path,
                    events_by_id[validated["event_id"]],
                    base_period_s,
                    dwell_ticks,
                )
            elif validated["metric"] == "attitude_settling_time_s":
                if scenario_id != "initial_attitude_offset":
                    _fail(
                        f"{criterion_path}.event_id",
                        "must bind non-initial settling to a command or disturbance event",
                    )
                if validated["window"]["start_tick"] != 0:
                    _fail(
                        f"{criterion_path}.window.start_tick",
                        "must start at scenario tick zero for initial-offset settling",
                    )
                _validate_settling_window(
                    validated,
                    criterion_path,
                    base_period_s,
                    dwell_ticks,
                )
            criteria.append((validated, criterion_path))
            criterion_ids.append(validated["id"])

        _validate_required_acceptance(scenario_id, criteria, events)

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


def _validate_operating_envelope(config: dict[str, Any], source_ids: set[str]) -> None:
    envelope = _mapping(
        config["operating_envelope"],
        "operating_envelope",
        {
            "source_ref",
            "status",
            "statement",
            "max_command_attitude_rad",
            "max_initial_attitude_offset_rad",
            "max_body_rate_rad_s",
            "validity_excludes",
            "parameter_rationale",
        },
    )
    _source_reference(envelope["source_ref"], "operating_envelope.source_ref", source_ids)
    if envelope["status"] != "proposed_pending_maintainer_approval":
        _fail("operating_envelope.status", "must remain proposed pending maintainer approval")
    if not isinstance(envelope["statement"], str) or "synthetic" not in envelope["statement"].lower():
        _fail("operating_envelope.statement", "must identify this as a synthetic envelope")
    _string(envelope["parameter_rationale"], "operating_envelope.parameter_rationale")

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

    controller_rate_limit = _vector(
        config["controller_contract"]["body_rate_target_limit_rad_s"],
        "controller_contract.body_rate_target_limit_rad_s",
        length=3,
        nonnegative=True,
    )
    if any(value > limit for value, limit in zip(controller_rate_limit, rate_limit)):
        _fail(
            "controller_contract.body_rate_target_limit_rad_s",
            "must not exceed operating_envelope.max_body_rate_rad_s",
        )

    exclusions = _list(envelope["validity_excludes"], "operating_envelope.validity_excludes")
    expected_exclusions = {"translation", "aerodynamics", "navigation", "hardware"}
    if set(exclusions) != expected_exclusions:
        _fail("operating_envelope.validity_excludes", "must state the B0 scope exclusions")

    for scenario_index, scenario in enumerate(config["scenarios"]):
        path = f"scenarios[{scenario_index}]"
        initial_rate = _vector(
            scenario["initial_body_rate_rad_s"],
            f"{path}.initial_body_rate_rad_s",
            length=3,
        )
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


def validate_config(config: dict[str, Any]) -> None:
    """Validate structural, semantic, physical, and scheduling constraints."""

    _mapping(config, "$", ROOT_REQUIRED, ROOT_REQUIRED)
    if config["schema_version"] != SCHEMA_VERSION:
        _fail("schema_version", f"must be {SCHEMA_VERSION!r}")

    status = _mapping(
        config["contract_status"],
        "contract_status",
        {"state", "freeze_prohibited", "approval_required", "approval_transition"},
    )
    if status["state"] != "proposed_pending_maintainer_approval":
        _fail("contract_status.state", "must remain proposed pending maintainer approval")
    if status["freeze_prohibited"] is not True:
        _fail("contract_status.freeze_prohibited", "must be true until approval")
    approvals = _list(status["approval_required"], "contract_status.approval_required")
    if not approvals or any(not isinstance(item, str) or not item for item in approvals):
        _fail("contract_status.approval_required", "must list concrete approval decisions")
    transition = _mapping(
        status["approval_transition"],
        "contract_status.approval_transition",
        {
            "current_version_action",
            "approved_successor_schema_version",
            "migration_rule",
            "approval_record",
        },
    )
    expected_transition = {
        "current_version_action": (
            "remain_proposed_until_maintainer_approval_record_is_committed"
        ),
        "approved_successor_schema_version": "b0-g0-contract/v2",
        "migration_rule": (
            "create_new_versioned_configuration_and_validator_contract_"
            "do_not_mutate_approved_v1_in_place"
        ),
        "approval_record": (
            "record_maintainer_decision_with_parameter_envelope_metric_and_"
            "CTL_applicability_rationale"
        ),
    }
    if transition != expected_transition:
        _fail(
            "contract_status.approval_transition",
            "must define the approved v2 migration and maintainer record policy",
        )

    source_ids = _validate_sources(config)
    tolerance = _validate_conventions(config)
    base_period_s, schedules, allowed_cross_type_pairs = _validate_timing(config, source_ids)
    _validate_interface_contract(config, source_ids)
    _validate_initialization_contract(config, source_ids, tolerance)
    _validate_plant(config, source_ids)
    actuator_limits = _validate_actuator(config, source_ids)
    _validate_imu(config, source_ids, schedules)
    _validate_estimator(config)
    _validate_controller(config, source_ids, actuator_limits)
    acceptance_seeds = _validate_seed_policy(config)
    dwell_ticks = _validate_acceptance_policy(config, source_ids, base_period_s)
    _validate_scenarios(
        config,
        source_ids,
        acceptance_seeds,
        base_period_s,
        tolerance,
        dwell_ticks,
        allowed_cross_type_pairs,
    )
    _validate_operating_envelope(config, source_ids)


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
