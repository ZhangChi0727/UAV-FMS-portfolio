"""Positive and adversarial tests for the B0 G0 configuration validator."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

import pytest


TRACK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRACK_ROOT))

from validate_config import (  # noqa: E402
    ROOT_REQUIRED,
    ContractValidationError,
    load_config,
    main,
    validate_config,
)


CONFIG_PATH = TRACK_ROOT / "configs" / "b0_g0_contract.v1.json"
SCHEMA_PATH = TRACK_ROOT / "schema" / "b0_g0_contract.schema.json"


def default_config() -> dict:
    return load_config(CONFIG_PATH)


def scenario(config: dict, scenario_id: str) -> dict:
    return next(item for item in config["scenarios"] if item["id"] == scenario_id)


def event(config: dict, scenario_id: str, event_id: str) -> dict:
    return next(
        item
        for item in scenario(config, scenario_id)["events"]
        if item["id"] == event_id
    )


def criterion(config: dict, scenario_id: str, criterion_id: str) -> dict:
    return next(
        item
        for item in scenario(config, scenario_id)["acceptance"]
        if item["id"] == criterion_id
    )


def remove_criterion(config: dict, scenario_id: str, criterion_id: str) -> None:
    acceptance = scenario(config, scenario_id)["acceptance"]
    acceptance.remove(
        next(item for item in acceptance if item["id"] == criterion_id)
    )


def assert_invalid(mutator, match: str) -> None:
    config = copy.deepcopy(default_config())
    mutator(config)
    with pytest.raises(ContractValidationError, match=match):
        validate_config(config)


def test_default_contract_is_valid() -> None:
    validate_config(default_config())


def test_command_line_entrypoint_accepts_default_contract(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--config", str(CONFIG_PATH)]) == 0
    assert "Valid B0 G0 contract configuration" in capsys.readouterr().out


def test_schema_is_explicitly_a_top_level_documentation_index() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["properties"]["schema_version"]["const"] == "b0-g0-contract/v1"
    assert schema["x-b0-validation-role"] == "top_level_documentation_index_only"
    assert "not an executable validation entry" in schema["description"]
    assert set(schema["required"]) == ROOT_REQUIRED


@pytest.mark.parametrize(
    ("contents", "match"),
    [
        ('{"value": NaN}', "non-finite JSON constant"),
        ('{"schema_version": "one", "schema_version": "two"}', "duplicate JSON key"),
    ],
)
def test_loader_rejects_nonfinite_and_duplicate_json(
    tmp_path: Path,
    contents: str,
    match: str,
) -> None:
    invalid = tmp_path / "invalid.json"
    invalid.write_text(contents, encoding="utf-8")
    with pytest.raises(ContractValidationError, match=match):
        load_config(invalid)


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (lambda config: config.__setitem__("unexpected", True), "unknown key"),
        (
            lambda config: config["timing"].__setitem__("silent_fallback", "never"),
            "unknown key",
        ),
        (lambda config: config.pop("interface_contract"), "missing required key"),
        (
            lambda config: config["contract_status"].pop("approval_transition"),
            "missing required key",
        ),
    ],
)
def test_rejects_root_missing_and_unknown_keys(mutator, match: str) -> None:
    assert_invalid(mutator, match)


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (
            lambda config: config["plant_contract"].__setitem__(
                "inertia_kg_m2",
                [[0.022, 0, 0], [0, 0, 0], [0, 0, 0.041]],
            ),
            "positive definite",
        ),
        (
            lambda config: config["sources"][0].__setitem__("kind", []),
            "supported source kind",
        ),
        (
            lambda config: config["timing"].__setitem__("source_ref", "UNKNOWN-001"),
            "declared source id",
        ),
    ],
)
def test_rejects_physical_and_source_contract_violations(mutator, match: str) -> None:
    assert_invalid(mutator, match)


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (
            lambda config: config["timing"]["schedules"].__setitem__(
                "estimator_every_ticks",
                1,
            ),
            "must equal imu_every_ticks",
        ),
        (
            lambda config: config["timing"]["schedules"].__setitem__(
                "controller_every_ticks",
                1,
            ),
            "must equal estimator_every_ticks",
        ),
        (
            lambda config: config["timing"]["sample_consumption_policy"].__setitem__(
                "estimator_no_new_imu_action",
                "reuse_last_sample",
            ),
            "current-sample consumption",
        ),
    ],
)
def test_rejects_incompatible_sampling_and_consumption(mutator, match: str) -> None:
    assert_invalid(mutator, match)


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (
            lambda config: config["interface_contract"]["messages"].pop("imu_sample"),
            "missing required key",
        ),
        (
            lambda config: config["interface_contract"]["messages"]["imu_sample"][1].__setitem__(
                "frame",
                "NED",
            ),
            "incompatible type, shape, unit, or frame",
        ),
        (
            lambda config: config["initialization_contract"]["scenario_field_ownership"].__setitem__(
                "initial_q_nb",
                "shared_truth",
            ),
            "must distinguish plant, estimator, command, actuator, and controller state",
        ),
        (
            lambda config: scenario(
                config,
                "initial_attitude_offset",
            ).__setitem__("initial_attitude_offset_owner", "estimator"),
            "plant_truth_only",
        ),
    ],
)
def test_rejects_incomplete_interfaces_and_initialization(mutator, match: str) -> None:
    assert_invalid(mutator, match)


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (
            lambda config: config["actuator_contract"]["antiwindup"].pop(
                "limit_feedback",
            ),
            "missing required key",
        ),
        (
            lambda config: config["actuator_contract"]["antiwindup"][
                "limit_feedback"
            ].__setitem__(
                "signal",
                "actual_minus_limited_target_torque_body_Nm",
            ),
            "pre-limit request error",
        ),
        (
            lambda config: config["actuator_contract"]["antiwindup"].__setitem__(
                "discrete_update",
                "I_next=I",
            ),
            "conditional, limit, and lag feedback terms",
        ),
        (
            lambda config: config["controller_contract"]["rate_pid"].__setitem__(
                "derivative_rule",
                "future_implementation_must_decide",
            ),
            "measured-rate differentiation",
        ),
    ],
)
def test_rejects_incomplete_or_contradictory_antiwindup_contract(
    mutator,
    match: str,
) -> None:
    assert_invalid(mutator, match)


@pytest.mark.parametrize(
    ("scenario_id", "event_id", "field"),
    [
        ("tri_axis_signed_steps", "step_x_positive", "axis"),
        ("external_torque_disturbance", "bounded_external_torque", "vector_Nm"),
        ("imu_noise_and_bias", "replace_nominal_imu_bias", "application"),
        (
            "acceleration_contamination",
            "additive_specific_force_contamination",
            "application",
        ),
        ("invalid_input_and_reset", "negative_dt_rejection", "invalid_kind"),
        ("invalid_input_and_reset", "deterministic_all_component_reset", "target"),
    ],
)
def test_every_event_type_rejects_missing_required_field(
    scenario_id: str,
    event_id: str,
    field: str,
) -> None:
    assert_invalid(
        lambda config: event(config, scenario_id, event_id).pop(field),
        "missing required key",
    )


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (
            lambda config: event(
                config,
                "tri_axis_signed_steps",
                "step_x_positive",
            ).__setitem__("unexpected", True),
            "unknown key",
        ),
        (
            lambda config: event(
                config,
                "tri_axis_signed_steps",
                "step_x_positive",
            ).__setitem__("axis", []),
            "must be x, y, or z",
        ),
        (
            lambda config: event(
                config,
                "invalid_input_and_reset",
                "negative_dt_rejection",
            ).__setitem__("invalid_kind", []),
            "negative_dt or stale_timestamp",
        ),
        (
            lambda config: event(
                config,
                "tri_axis_signed_steps",
                "step_x_positive",
            ).__setitem__("type", []),
            "supported event type",
        ),
    ],
)
def test_event_unknown_and_wrong_type_errors_are_contract_errors(mutator, match: str) -> None:
    assert_invalid(mutator, match)


@pytest.mark.parametrize(
    ("scenario_id", "event_id"),
    [
        ("tri_axis_signed_steps", "step_x_positive"),
        ("external_torque_disturbance", "bounded_external_torque"),
        ("imu_noise_and_bias", "replace_nominal_imu_bias"),
        (
            "acceleration_contamination",
            "additive_specific_force_contamination",
        ),
        ("invalid_input_and_reset", "negative_dt_rejection"),
        ("invalid_input_and_reset", "deterministic_all_component_reset"),
    ],
)
def test_every_event_type_rejects_unknown_fields(
    scenario_id: str,
    event_id: str,
) -> None:
    assert_invalid(
        lambda config: event(config, scenario_id, event_id).__setitem__(
            "unexpected",
            True,
        ),
        "unknown key",
    )


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (
            lambda config: event(
                config,
                "tri_axis_signed_steps",
                "step_x_positive",
            ).__setitem__("axis", []),
            "must be x, y, or z",
        ),
        (
            lambda config: event(
                config,
                "external_torque_disturbance",
                "bounded_external_torque",
            ).__setitem__("vector_Nm", "not-a-vector"),
            "must be an array",
        ),
        (
            lambda config: event(
                config,
                "imu_noise_and_bias",
                "replace_nominal_imu_bias",
            ).__setitem__("gyro_bias_rad_s", "not-a-vector"),
            "must be an array",
        ),
        (
            lambda config: event(
                config,
                "acceleration_contamination",
                "additive_specific_force_contamination",
            ).__setitem__("vector_m_s2", "not-a-vector"),
            "must be an array",
        ),
        (
            lambda config: event(
                config,
                "invalid_input_and_reset",
                "negative_dt_rejection",
            ).__setitem__("invalid_kind", []),
            "negative_dt or stale_timestamp",
        ),
        (
            lambda config: event(
                config,
                "invalid_input_and_reset",
                "deterministic_all_component_reset",
            ).__setitem__("target", []),
            "must be all_components",
        ),
    ],
)
def test_every_event_type_rejects_wrong_field_type(mutator, match: str) -> None:
    assert_invalid(mutator, match)


@pytest.mark.parametrize(
    ("scenario_id", "event_id"),
    [
        ("tri_axis_signed_steps", "step_x_positive"),
        ("external_torque_disturbance", "bounded_external_torque"),
        ("imu_noise_and_bias", "replace_nominal_imu_bias"),
        (
            "acceleration_contamination",
            "additive_specific_force_contamination",
        ),
        ("invalid_input_and_reset", "negative_dt_rejection"),
        ("invalid_input_and_reset", "deterministic_all_component_reset"),
    ],
)
def test_every_event_type_rejects_empty_or_reversed_interval(
    scenario_id: str,
    event_id: str,
) -> None:
    def make_empty_interval(config: dict) -> None:
        item = event(config, scenario_id, event_id)
        item["start_tick"] = item["end_tick"]

    assert_invalid(make_empty_interval, "must satisfy 0 <= start_tick < end_tick")


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (
            lambda config: event(
                config,
                "tri_axis_signed_steps",
                "step_x_negative",
            ).__setitem__("start_tick", 200),
            "overlaps same signal",
        ),
        (
            lambda config: event(
                config,
                "tri_axis_signed_steps",
                "step_x_negative",
            ).__setitem__("start_tick", 100),
            "must be nondecreasing",
        ),
        (
            lambda config: config["acceptance_policy"]["settling"].__setitem__(
                "dwell_s",
                100,
            ),
            "must contain the settling limit plus the required dwell interval",
        ),
        (
            lambda config: criterion(
                config,
                "tri_axis_signed_steps",
                "step_x_positive_settling_time",
            )["window"].__setitem__("end_tick", 700),
            "must contain the settling limit plus the required dwell interval",
        ),
    ],
)
def test_rejects_event_order_overlap_and_unobservable_settling_windows(
    mutator,
    match: str,
) -> None:
    assert_invalid(mutator, match)


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (
            lambda config: remove_criterion(
                config,
                "tri_axis_signed_steps",
                "step_x_positive_overshoot",
            ),
            "missing mandatory metric",
        ),
        (
            lambda config: scenario(
                config,
                "tri_axis_signed_steps",
            ).__setitem__("observations", ["sample_validity"]),
            "requires observations",
        ),
        (
            lambda config: criterion(
                config,
                "tri_axis_signed_steps",
                "step_x_positive_cross_axis",
            ).pop("event_id"),
            "must bind cross_axis_attitude_error_rad",
        ),
        (
            lambda config: criterion(
                config,
                "tri_axis_signed_steps",
                "step_x_positive_settling_time",
            ).__setitem__("event_id", "step_y_positive"),
            "must be independently bounded by its command event",
        ),
    ],
)
def test_rejects_silent_weakening_of_step_acceptance(
    mutator,
    match: str,
) -> None:
    assert_invalid(mutator, match)


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (
            lambda config: event(
                config,
                "saturation_withdrawal",
                "saturation_command",
            ).__setitem__("value_rad", 0),
            "non-zero command excitation",
        ),
        (
            lambda config: remove_criterion(
                config,
                "saturation_withdrawal",
                "saturation_triggered_duration",
            ),
            "positive saturation trigger criterion",
        ),
        (
            lambda config: criterion(
                config,
                "saturation_withdrawal",
                "saturation_triggered_duration",
            ).__setitem__("limit", 0),
            "positive saturation trigger criterion",
        ),
    ],
)
def test_saturation_case_requires_excitation_and_positive_trigger(
    mutator,
    match: str,
) -> None:
    assert_invalid(mutator, match)


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (
            lambda config: config["acceptance_policy"]["metric_definitions"][
                "tracking_overshoot_percent"
            ].__setitem__("source_signals", ["sample_validity"]),
            "must match the metric signal dependency set",
        ),
        (
            lambda config: config["acceptance_policy"]["metric_definitions"][
                "tracking_overshoot_percent"
            ].__setitem__("formula", "any_formula_is_not_acceptable"),
            "must use the declared metric formula",
        ),
        (
            lambda config: criterion(
                config,
                "tri_axis_signed_steps",
                "step_x_positive_overshoot",
            ).__setitem__("operator", ">="),
            "incompatible with metric tracking_overshoot_percent",
        ),
        (
            lambda config: criterion(
                config,
                "invalid_input_and_reset",
                "invalid_input_rejected",
            ).__setitem__("operator", "<="),
            "incompatible with metric invalid_input_rejection_count",
        ),
        (
            lambda config: criterion(
                config,
                "acceleration_contamination",
                "acceleration_limitation_recorded",
            )["window"].__setitem__("end_tick", 1199),
            "must exactly cover its contamination event",
        ),
        (
            lambda config: criterion(
                config,
                "external_torque_disturbance",
                "disturbance_recovery",
            )["window"].__setitem__("start_tick", 799),
            "must start at the event end for recovery",
        ),
    ],
)
def test_metric_dependencies_and_event_time_origins_are_enforced(
    mutator,
    match: str,
) -> None:
    assert_invalid(mutator, match)


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (
            lambda config: config["scenarios"][0].__setitem__(
                "initial_q_nb",
                [0.9, 0.0, 0.0, 0.0],
            ),
            "unit quaternion",
        ),
        (
            lambda config: config["scenarios"][0].__setitem__("duration_s", 5.001),
            "integer number of base ticks",
        ),
        (
            lambda config: config["scenarios"][0]["events"].append(
                {
                    "id": "unexpected_reset",
                    "type": "reset",
                    "target": "all_components",
                    "start_tick": 1900,
                    "end_tick": 1901,
                },
            ),
            "required event class",
        ),
        (
            lambda config: config["scenarios"][0].__setitem__("seed", 2026100999),
            "reserved acceptance seed",
        ),
    ],
)
def test_rejects_existing_state_tick_and_seed_contract_violations(mutator, match: str) -> None:
    assert_invalid(mutator, match)


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (
            lambda config: config["actuator_contract"].__setitem__("time_constant_s", 0.0),
            "must be positive",
        ),
        (
            lambda config: config["imu_contract"]["gyro"]["noise_std_rad_s"].__setitem__(
                0,
                -0.1,
            ),
            "non-negative",
        ),
        (
            lambda config: config["controller_contract"]["rate_pid"]["kp"]["initial"].__setitem__(
                0,
                0.25,
            ),
            "minimum <= initial <= maximum",
        ),
        (
            lambda config: config["controller_contract"]["rate_pid"].__setitem__(
                "integrator_limit_Nm",
                [0.36, 0.15, 0.1],
            ),
            "no greater than actuator limit",
        ),
    ],
)
def test_rejects_component_boundary_violations(mutator, match: str) -> None:
    assert_invalid(mutator, match)


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (
            lambda config: criterion(
                config,
                "stationary_zero_command",
                "stationary_attitude_peak",
            ).__setitem__("unit", "s"),
            "must be 'rad'",
        ),
        (
            lambda config: criterion(
                config,
                "invalid_input_and_reset",
                "invalid_input_rejected",
            ).__setitem__("reducer", []),
            "incompatible",
        ),
        (
            lambda config: criterion(
                config,
                "acceleration_contamination",
                "acceleration_limitation_recorded",
            ).__setitem__("limit", 1),
            "boolean metrics",
        ),
    ],
)
def test_metric_type_errors_remain_locatable_contract_errors(mutator, match: str) -> None:
    assert_invalid(mutator, match)
