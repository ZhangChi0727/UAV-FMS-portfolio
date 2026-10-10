"""Focused positive and negative tests for the B0 G0 contract validator."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

import pytest

TRACK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRACK_ROOT))

from validate_config import (  # noqa: E402
    ContractValidationError,
    load_config,
    main,
    validate_config,
)


CONFIG_PATH = TRACK_ROOT / "configs" / "b0_g0_contract.v1.json"
SCHEMA_PATH = TRACK_ROOT / "schema" / "b0_g0_contract.schema.json"


def default_config() -> dict:
    return load_config(CONFIG_PATH)


def assert_invalid(mutator, match: str) -> None:
    config = copy.deepcopy(default_config())
    mutator(config)
    with pytest.raises(ContractValidationError, match=match):
        validate_config(config)


def test_default_contract_is_valid() -> None:
    validate_config(default_config())


def test_command_line_entrypoint_accepts_default_contract(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--config", str(CONFIG_PATH)]) == 0
    assert "Valid B0 G0 contract configuration" in capsys.readouterr().out


def test_structural_schema_declares_the_versioned_contract() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["properties"]["schema_version"]["const"] == "b0-g0-contract/v1"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) >= {"sources", "timing", "scenarios"}


def test_rejects_nonfinite_json_constants(tmp_path: Path) -> None:
    invalid = tmp_path / "nonfinite.json"
    invalid.write_text('{"value": NaN}', encoding="utf-8")
    with pytest.raises(ContractValidationError, match="non-finite JSON constant"):
        load_config(invalid)


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (lambda config: config.__setitem__("unexpected", True), "unknown key"),
        (lambda config: config["timing"].__setitem__("silent_fallback", "never"), "unknown key"),
        (lambda config: config.pop("scenarios"), "missing required key"),
    ],
)
def test_rejects_missing_and_unknown_keys(mutator, match: str) -> None:
    assert_invalid(mutator, match)


def test_rejects_non_positive_definite_inertia() -> None:
    assert_invalid(
        lambda config: config["plant_contract"].__setitem__(
            "inertia_kg_m2", [[0.022, 0, 0], [0, 0, 0], [0, 0, 0.041]]
        ),
        "positive definite",
    )


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (
            lambda config: config["scenarios"][0].__setitem__(
                "initial_q_nb", [0.9, 0.0, 0.0, 0.0]
            ),
            "unit quaternion",
        ),
        (
            lambda config: config["scenarios"][0].__setitem__("duration_s", 5.001),
            "integer number of base ticks",
        ),
        (
            lambda config: config["scenarios"][0]["events"].append(
                {"type": "reset", "start_tick": 1900, "end_tick": 1901}
            ),
            "required event class",
        ),
    ],
)
def test_rejects_state_and_tick_contract_violations(mutator, match: str) -> None:
    assert_invalid(mutator, match)


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (
            lambda config: config["actuator_contract"].__setitem__("time_constant_s", 0.0),
            "must be positive",
        ),
        (
            lambda config: config["imu_contract"]["gyro"]["noise_std_rad_s"].__setitem__(0, -0.1),
            "non-negative",
        ),
        (
            lambda config: config["imu_contract"].__setitem__("sample_period_ticks", 3),
            "must match",
        ),
    ],
)
def test_rejects_actuator_and_imu_boundary_violations(mutator, match: str) -> None:
    assert_invalid(mutator, match)


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (
            lambda config: config["controller_contract"].__setitem__(
                "truth_inputs_forbidden", False
            ),
            "must be True",
        ),
        (
            lambda config: config["controller_contract"]["rate_pid"]["kp"]["initial"].__setitem__(
                0, 0.25
            ),
            "minimum <= initial <= maximum",
        ),
        (
            lambda config: config["controller_contract"]["rate_pid"].__setitem__(
                "integrator_limit_Nm", [0.36, 0.15, 0.1]
            ),
            "no greater than actuator limit",
        ),
    ],
)
def test_rejects_truth_and_gain_contract_violations(mutator, match: str) -> None:
    assert_invalid(mutator, match)


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (
            lambda config: config["scenarios"][0].__setitem__("seed", 2026100999),
            "reserved acceptance seed",
        ),
        (
            lambda config: config["scenarios"][1].__setitem__("seed", 2026100901),
            "unique values",
        ),
        (
            lambda config: config["timing"].__setitem__("source_ref", "UNKNOWN-001"),
            "declared source id",
        ),
    ],
)
def test_rejects_seed_and_source_reference_violations(mutator, match: str) -> None:
    assert_invalid(mutator, match)


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (
            lambda config: config["scenarios"][2]["events"][0].__setitem__(
                "end_tick", 4000
            ),
            "scenario ticks",
        ),
        (
            lambda config: config["scenarios"][2]["events"].pop(),
            "signed steps",
        ),
        (
            lambda config: config["scenarios"][7]["events"][0].__setitem__(
                "invalid_kind", "ignored"
            ),
            "negative_dt or stale_timestamp",
        ),
    ],
)
def test_rejects_event_semantic_violations(mutator, match: str) -> None:
    assert_invalid(mutator, match)


@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (
            lambda config: config["scenarios"][0]["acceptance"][0].__setitem__(
                "unit", "s"
            ),
            "must be 'rad'",
        ),
        (
            lambda config: config["scenarios"][6]["acceptance"][0].__setitem__(
                "limit", 1
            ),
            "boolean metrics",
        ),
        (
            lambda config: config["scenarios"][7]["acceptance"][0].__setitem__(
                "reducer", "max"
            ),
            "incompatible",
        ),
    ],
)
def test_rejects_metric_type_and_window_violations(mutator, match: str) -> None:
    assert_invalid(mutator, match)
@pytest.mark.parametrize(
    ("mutator", "match"),
    [
        (
            lambda config: config["acceptance_policy"]["settling"].__setitem__(
                "dwell_s", 0.251
            ),
            "integer number of base ticks",
        ),
        (
            lambda config: config["acceptance_policy"].__setitem__(
                "outcome_classes", ["performance_pass"] * 5
            ),
            "must distinguish",
        ),
        (
            lambda config: config["scenarios"][5]["events"][0].__setitem__(
                "value_rad", 0.8
            ),
            "exceeds operating envelope",
        ),
        (
            lambda config: config["operating_envelope"].__setitem__(
                "source_ref", "UNKNOWN-001"
            ),
            "declared source id",
        ),
    ],
)
def test_rejects_envelope_and_acceptance_policy_violations(mutator, match: str) -> None:
    assert_invalid(mutator, match)
