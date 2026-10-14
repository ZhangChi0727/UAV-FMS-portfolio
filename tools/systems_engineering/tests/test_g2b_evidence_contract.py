from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import pytest


REPO = Path(__file__).resolve().parents[3]
MATRIX_PATH = (
    REPO / "systems_engineering/reports/b0/g2b_s0_controller_verification_matrix.md"
)
SPEC = importlib.util.spec_from_file_location(
    "g2b_evidence_contract", REPO / "03_control/b0/evidence.py"
)
assert SPEC is not None and SPEC.loader is not None
evidence_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evidence_module)


def case_traces(digest: str) -> dict:
    ctest_nodes = {}
    pytest_nodes = {}
    rows = []
    mutation_oracles = {
        "b0_controller::mutation::attitude_feedback_sign_reversed": "attitude_error_axes_and_small_angle",
        "b0_controller::mutation::antiwindup_backcalculation_sign_reversed": "antiwindup_backcalculation_terms",
        "b0_controller::mutation::antiwindup_disabled": "antiwindup_backcalculation_terms",
        "b0_controller::mutation::lag_uses_current_limited": "antiwindup_backcalculation_terms",
    }
    for row_id, nodes in evidence_module.S0_CASE_NODES.items():
        executions = []
        for node in nodes:
            output = ""
            if node in mutation_oracles:
                # CTest may truncate wrapper output; the exact mutation/oracle
                # relationship is independently fixed by MUTATION_ORACLES.
                output = "detected subject mutation"
            source_kind = "pytest" if node.startswith("python/") else "ctest"
            collected_name = (
                node if source_kind == "ctest" else node.rsplit("::", 1)[-1]
            )
            record = {
                "status": "pass",
                "invocation_count": 1,
                "duration_s": 0.01,
                "collected_cases": [collected_name],
                "output": output,
            }
            (pytest_nodes if source_kind == "pytest" else ctest_nodes)[node] = record
            executions.append({"node": node, "source_kind": source_kind, **record})
        samples = [
            manifest_sample(row_id, case_id, requirement, executions)
            for case_id, requirement in evidence_module.S0_CASE_MANIFEST[row_id].items()
        ]
        rows.append(
            {
                "row_id": row_id,
                "nodes": list(nodes),
                "node_executions": executions,
                "samples": samples,
                "result": True,
            }
        )
    return {
        "matrix_path": "systems_engineering/reports/b0/g2b_s0_controller_verification_matrix.md",
        "matrix_sha256": digest,
        "execution_sources": [
            {
                "kind": "ctest",
                "path": "ctest-debug.xml",
                "sha256": digest,
                "size_bytes": 4096,
                "collected_testcases": sum(
                    record["invocation_count"] for record in ctest_nodes.values()
                ),
                "nodes": ctest_nodes,
            },
            {
                "kind": "pytest",
                "path": "pytest-debug.xml",
                "sha256": digest,
                "size_bytes": 8192,
                "collected_testcases": sum(
                    record["invocation_count"] for record in pytest_nodes.values()
                ),
                "nodes": pytest_nodes,
            },
        ],
        "rows": sorted(rows, key=lambda row: row["row_id"]),
        "all_rows_pass": True,
    }


def _fixture_input_value(key: str, case_id: str):
    if key == "axis":
        return 0
    if key in {"epoch_id", "active_epoch", "feedback_epoch"}:
        return 1
    if key.endswith("timestamp_s"):
        return 0.005
    if key in {"mutation", "mutation_node"}:
        return case_id
    if key == "authority":
        return "g0" if case_id.startswith("g0-") else "implementation"
    if key == "line_ending":
        return case_id.rsplit("-", 1)[-1]
    return f"fixture-{key}"


def _fixture_exact_value(keys: tuple[str, ...]):
    if not keys:
        return True
    return {key: True for key in keys}


def _zero_command(epoch_id: int = 1, timestamp_s: float = 0.015) -> dict:
    return {
        "epoch_id": epoch_id,
        "requested_torque_body_Nm": [0.0, 0.0, 0.0],
        "limited_torque_body_Nm": [0.0, 0.0, 0.0],
        "saturated": [False, False, False],
        "timestamp_s": timestamp_s,
    }


def _reset_diagnostics() -> dict:
    vector_fields = (
        "rate_error_rad_s",
        "derivative_raw_rad_s2",
        "derivative_filtered_rad_s2",
        "proportional_Nm",
        "integral_before_Nm",
        "derivative_Nm",
        "conditional_integral_rate_Nm_s",
        "limit_backcalculation_rate_Nm_s",
        "lag_backcalculation_rate_Nm_s",
        "integral_after_Nm",
        "requested_Nm",
        "limited_Nm",
    )
    return {
        "accepted": False,
        "reason": "",
        "epoch_id": 0,
        "tick_index": 0,
        "saturated": [False, False, False],
        **{field: [0.0, 0.0, 0.0] for field in vector_fields},
    }


def _reset_snapshot() -> dict:
    return {
        "reset": True,
        "epoch_id": 1,
        "tick_index": 0,
        "epoch_origin_s": 0.015,
        "expected_timestamp_s": 0.020,
        "integral_Nm": [0.0, 0.0, 0.0],
        "derivative_filtered_rad_s2": [0.0, 0.0, 0.0],
        "previous_rate_rad_s": [0.0, 0.0, 0.0],
        "has_previous_rate": False,
        "expected_held_command": _zero_command(),
        "last_diagnostics": _reset_diagnostics(),
    }


def _pre_reset_snapshot() -> dict:
    snapshot = _reset_snapshot()
    snapshot.update(
        reset=False,
        epoch_id=0,
        tick_index=2,
        integral_Nm=[0.01, 0.0, 0.0],
        derivative_filtered_rad_s2=[0.2, 0.0, 0.0],
        previous_rate_rad_s=[0.4, 0.0, 0.0],
        has_previous_rate=True,
    )
    return snapshot


def _configuration_failure(case_id: str) -> dict:
    messages = {
        "g0-missing": "cannot read G0 contract: /fixture/b0_g0_contract.v2.json",
        "g0-changed": "G0 canonical digest mismatch",
        "g0-wrong-version": "authoritative G0 validation failed",
        "g0-bad-gain": "authoritative G0 validation failed",
        "implementation-missing": (
            "cannot load /fixture/b0_g2_controller.v1.json: file missing"
        ),
        "implementation-changed": (
            "implementation configuration is not the approved S0 byte identity"
        ),
        "implementation-wrong-version": (
            "unsupported implementation configuration identity"
        ),
        "implementation-bad-tolerance": "loaded controller parameters are invalid",
    }
    return {
        "exception_type": "ControllerConfigurationError",
        "message": messages[case_id],
    }


def manifest_sample(
    row_id: str,
    case_id: str,
    requirement: dict,
    executions: list[dict],
) -> dict:
    kind = requirement["kind"]
    input_keys = tuple(requirement["input_keys"])
    assert input_keys, f"manifest input contract must be nonempty: {row_id}/{case_id}"
    input_value = {
        key: _fixture_input_value(key, case_id)
        for key in input_keys
    }
    units = list(requirement["units"])
    base = {
        "case_id": case_id,
        "input": input_value,
        "units": units,
        "absolute_tolerance": 0.0 if kind != "numeric" else 1e-12,
        "relative_tolerance": 0.0,
    }
    if kind == "numeric":
        labels = list(requirement["labels"])
        assert len(units) == len(labels)
        values = list(requirement.get("expected_values", (0.0,) * len(labels)))
        assert len(values) == len(labels)
        if row_id == "B-ATT-03" and case_id == "mixed-half-turn-signs-and-values":
            inverse_root_three = 1.0 / (3.0**0.5)
            input_value.update(
                q_nb_command=[
                    0.0,
                    inverse_root_three,
                    -inverse_root_three,
                    inverse_root_three,
                ],
                q_nb_estimate=[1.0, 0.0, 0.0, 0.0],
            )
        if row_id == "B-AW-03":
            match = re.fullmatch(
                r"axis-([0-2])-sign-([+-]1)-saturate-release", case_id
            )
            assert match is not None
            axis = int(match.group(1))
            sign = int(match.group(2))
            input_value.update(
                axis=axis,
                saturation_rate_rad_s=-0.2 * sign,
                release_rate_rad_s=-0.002 * sign,
            )
            values = [
                1.0,
                -0.8 * sign,
                0.1 * sign,
                -0.001 * sign,
                0.0,
                0.2 * sign,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
            ]
        return {
            **base,
            "independent_expected": {"labels": labels, "values": values},
            "actual": {"values": list(values)},
            "comparison": {
                "kind": kind,
                "max_absolute_error": 0.0,
                "result": True,
            },
        }
    if kind == "rejection_atomic":
        snapshot = {"tick_index": 0, "integral_Nm": [0.0, 0.0, 0.0]}
        reason = requirement.get("reason", "fixture_rejection")
        return {
            **base,
            "independent_expected": {"reason": reason, "state_change": "none"},
            "actual": {
                "reason": reason,
                "snapshot_before": snapshot,
                "snapshot_after": deepcopy(snapshot),
            },
            "comparison": {"kind": kind, "result": True},
        }
    if kind == "binding_rejection_atomic":
        snapshot = {"tick_index": 0, "integral_Nm": [0.0, 0.0, 0.0]}
        exception_type = requirement.get("exception_type", "ValueError")
        message = requirement.get("message", "fixture rejection")
        return {
            **base,
            "independent_expected": {
                "exception_type": exception_type,
                "message": message,
                "warning_count": 0,
                "state_change": "none",
            },
            "actual": {
                "exception_type": exception_type,
                "message": message,
                "warning_count": 0,
                "snapshot_before": snapshot,
                "snapshot_after": deepcopy(snapshot),
            },
            "comparison": {"kind": kind, "result": True},
        }
    if kind == "exact":
        expected_keys = tuple(requirement.get("expected_value_keys", ()))
        actual_keys = tuple(requirement.get("actual_value_keys", expected_keys))
        keys = tuple(dict.fromkeys((*expected_keys, *actual_keys)))
        value = _fixture_exact_value(keys)
        if row_id == "B-RESET-01":
            input_value["before_reset"] = _pre_reset_snapshot()
            input_value["new_epoch_id"] = 1
            input_value["reset_timestamp_s"] = 0.015
            value = {"reset_output": _zero_command(), "state": _reset_snapshot()}
        elif (
            row_id == "B-BIND-01"
            and case_id == "approved-diagnostics-status-fields"
        ):
            value = {"accepted": True, "reason": "accepted"}
        elif row_id == "B-CONFIG-02":
            value = _configuration_failure(case_id)
        sample = {
            **base,
            "independent_expected": {"value": deepcopy(value)},
            "actual": {"value": deepcopy(value)},
            "comparison": {"kind": kind, "result": True},
        }
        if row_id in {"B-DETECT-01", "B-DETECT-02"}:
            oracle = {
                "attitude_feedback_sign_reversed": "attitude_error_axes_and_small_angle",
                "antiwindup_backcalculation_sign_reversed": "antiwindup_backcalculation_terms",
                "antiwindup_disabled": "antiwindup_backcalculation_terms",
                "lag_uses_current_limited": "antiwindup_backcalculation_terms",
            }[case_id]
            execution = next(
                record
                for record in executions
                if record["node"].endswith(f"::{case_id}")
            )
            sample["input"].update(
                mutation_node=execution["node"], unchanged_oracle_node=oracle
            )
            sample["actual"]["execution"] = {
                key: deepcopy(value)
                for key, value in execution.items()
                if key != "node"
            }
        return sample
    raise AssertionError(f"unsupported manifest kind {kind!r} for {row_id}/{case_id}")


def artifact() -> dict:
    digest = "a" * 64
    matrix_digest = hashlib.sha256(MATRIX_PATH.read_bytes()).hexdigest()
    command = {
        "requested_torque_body_Nm": [0.48, 0.0, 0.0],
        "limited_torque_body_Nm": [0.35, 0.0, 0.0],
        "saturated": [True, False, False],
        "timestamp_s": 12.005,
    }
    diagnostics = {
        "accepted": True,
        "reason": "accepted",
        "proportional_Nm": [0.48, 0.0, 0.0],
        "integral_before_Nm": [0.0, 0.0, 0.0],
        "derivative_Nm": [0.0, 0.0, 0.0],
        "conditional_integral_rate_Nm_s": [0.0, 0.0, 0.0],
        "limit_backcalculation_rate_Nm_s": [-1.04, 0.0, 0.0],
        "lag_backcalculation_rate_Nm_s": [0.0, 0.0, 0.0],
        "integral_after_Nm": [-0.0052, 0.0, 0.0],
        "requested_Nm": [0.48, 0.0, 0.0],
        "limited_Nm": [0.35, 0.0, 0.0],
    }
    timing_row = {
        "tick_index": 1,
        "current_timestamp_s": 12.005,
        "paired_command_timestamp_s": 12.0,
        "feedback_limited_torque_body_Nm": [0.0, 0.0, 0.0],
        "output": command,
        "diagnostics": deepcopy(diagnostics),
    }
    criteria = {
        "attitude_request_absolute_error_le_1e_12": True,
        "saturation_request_absolute_error_le_1e_12": True,
        "saturation_limit_absolute_error_le_1e_12": True,
        "antiwindup_integral_absolute_error_le_1e_12": True,
        "antiwindup_limit_term_absolute_error_le_1e_12": True,
        "paired_feedback_uses_previous_publication": True,
        "invalid_input_rejection_is_atomic": True,
        "corrected_retry_publishes_due_tick": True,
        "complete_s0_case_traces_pass": True,
    }
    return {
        "schema_version": "b0-g2b-controller-evidence/v2",
        "source_commit": "b" * 40,
        "component": "B0 G2-B cascaded attitude/body-rate controller",
        "execution_identity": {
            "context": "github_actions",
            "checked_out_source_commit": "b" * 40,
            "run_id": "38500000000",
            "run_attempt": "1",
            "event_name": "pull_request",
            "github_sha_metadata": "c" * 40,
            "github_ref_metadata": "refs/pull/22/merge",
            "github_head_ref": "codex/b0-g2b-cascaded-controller",
            "repository": "ZhangChi0727/UAV-FMS-portfolio",
            "workflow_ref": "workflow-ref",
            "identity_note": "distinct source and event metadata",
        },
        "claim_boundary": {
            "level": "module_component",
            "g3_closed_loop_performance": False,
            "sil": False,
            "hil": False,
            "board_execution": False,
            "flight": False,
        },
        "build": {
            "build_type": "Debug",
            "cmake_build_type": "Debug",
            "build_directory": "build/b0-controller/debug",
            "cmake_cache_directory": "build/b0-controller/debug",
            "cmake_home_directory": ".",
            "module_directory": "build/b0-controller/debug/03_control/b0",
            "module_path": "build/b0-controller/debug/03_control/b0/module.so",
            "module_sha256": digest,
            "cmake_cache_sha256": digest,
            "python": "3.11.17",
            "python_executable": "/usr/bin/python3.11",
            "generator_python_executable": "/usr/bin/python3.11",
            "cmake_python_matches_generator": True,
            "python_implementation": "CPython",
            "python_abi": "cpython-311-x86_64-linux-gnu",
            "platform": "Linux",
            "cmake": "cmake version 3.30.5",
            "cxx_compiler": "/usr/bin/c++",
            "cxx": "g++ 9.4.0",
            "pybind11": {
                "version": "2.13.6",
                "cmake_directory": "/venv/pybind11/share/cmake/pybind11",
            },
            "catch2": {
                "mode": "fetched_pinned_revision",
                "version": "3.5.4",
                "source_directory": "build/_deps/catch2-src",
                "git_revision": "b5373dadca40b7edc8570cf9470b9b1cb1934d40",
                "required_git_revision": "b5373dadca40b7edc8570cf9470b9b1cb1934d40",
            },
        },
        "configuration": {
            "implementation_path": "03_control/b0/configs/b0_g2_controller.v1.json",
            "implementation_sha256": digest,
            "approval_path": "03_control/b0/configs/b0_g2_controller_approval.v1.json",
            "approval_sha256": digest,
            "g0_path": "05_integration/b0/configs/b0_g0_contract.v2.json",
            "g0_sha256": digest,
            "validator_path": "05_integration/b0/validate_config.py",
            "validator_sha256": digest,
        },
        "observations": {
            "attitude_sign_and_cascade": {
                "input": {},
                "independent_oracle": {},
                "actual": command,
                "diagnostics": deepcopy(diagnostics),
                "max_request_abs_error_Nm": 0.0,
            },
            "saturation_and_limit_backcalculation": {
                "input": {},
                "independent_oracle": {},
                "actual": command,
                "diagnostics": deepcopy(diagnostics),
                "errors": {},
            },
            "paired_three_tick_timing": {
                "trace": [deepcopy(timing_row) for _ in range(3)],
                "independent_expected_publication_times_s": [
                    12.0,
                    12.005,
                    12.01,
                    12.015,
                ],
                "each_feedback_pairs_previous_publication": True,
            },
            "atomic_invalid_measurement_rejection": {
                "invalid_input": {"estimate_valid": False},
                "stable_reason": "invalid_estimate",
                "snapshot_before": {},
                "snapshot_after": {},
                "snapshot_unchanged": True,
                "corrected_same_tick_retry": command,
            },
        },
        "case_traces": case_traces(matrix_digest),
        "criteria": criteria,
        "all_selected_component_criteria_pass": True,
        "limitations": ["component evidence only"],
    }


def test_required_controller_evidence_fields_are_accepted(tmp_path: Path):
    item = artifact()
    evidence_module.validate_evidence(item, **_validation_kwargs(item, tmp_path))


def _row(item: dict, row_id: str) -> dict:
    return next(row for row in item["case_traces"]["rows"] if row["row_id"] == row_id)


def _sample(item: dict, row_id: str, case_id: str) -> dict:
    return next(
        sample
        for sample in _row(item, row_id)["samples"]
        if sample["case_id"] == case_id
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda item: item["build"]["catch2"].pop("git_revision"),
            "fetched Catch2 revision/source",
        ),
        (
            lambda item: item["build"]["pybind11"].pop("cmake_directory"),
            "actual pybind11 identity",
        ),
        (
            lambda item: item["build"].update(
                cmake_python_matches_generator=False
            ),
            "Python ABI owner",
        ),
        (
            lambda item: item["build"].update(cmake_build_type="Release"),
            "declared/CMake build type mismatch",
        ),
        (
            lambda item: item["build"].update(
                cmake_cache_directory="build/b0-controller/release"
            ),
            "declared/CMake build directory mismatch",
        ),
        (
            lambda item: item["build"].update(
                module_directory="build/b0-controller/release/03_control/b0"
            ),
            "module/build directory mismatch",
        ),
        (
            lambda item: item["build"].update(
                module_path="build/b0-controller/release/03_control/b0/module.so"
            ),
            "module path outside declared module directory",
        ),
        (
            lambda item: item["observations"].pop("paired_three_tick_timing"),
            "observations.paired_three_tick_timing",
        ),
        (
            lambda item: item["configuration"].pop("validator_sha256"),
            "configuration.validator_sha256",
        ),
        (
            lambda item: item["execution_identity"].update(
                checked_out_source_commit="d" * 40
            ),
            "execution/source commit mismatch",
        ),
        (
            lambda item: item["observations"][
                "saturation_and_limit_backcalculation"
            ]["diagnostics"].pop("lag_backcalculation_rate_Nm_s"),
            "anti-windup diagnostics.lag_backcalculation_rate_Nm_s",
        ),
        (
            lambda item: item["observations"][
                "saturation_and_limit_backcalculation"
            ]["diagnostics"].update(accepted=False),
            "anti-windup accepted",
        ),
        (
            lambda item: item["observations"]["paired_three_tick_timing"].update(
                trace=[]
            ),
            "three-tick pairing trace",
        ),
        (
            lambda item: item["criteria"].pop(
                "invalid_input_rejection_is_atomic"
            ),
            "required component criteria",
        ),
        (
            lambda item: item["case_traces"]["rows"].pop(),
            "all 26 S0 rows exactly once",
        ),
        (
            lambda item: _row(item, "B-ATT-01")["samples"].pop(),
            "B-ATT-01 exact required cases",
        ),
        (
            lambda item: _row(item, "B-ATT-02")["samples"][0].update(
                case_id="fabricated-replacement"
            ),
            "B-ATT-02/fabricated-replacement declared case",
        ),
        (
            lambda item: _row(item, "B-ATT-02")["samples"][0][
                "comparison"
            ].update(kind="exact"),
            "B-ATT-02/.+ contracted comparison kind",
        ),
        (
            lambda item: _row(item, "B-ATT-02")["samples"][0][
                "independent_expected"
            ].update(
                labels=["fabricated-label-0", "fabricated-label-1", "fabricated-label-2"]
            ),
            "B-ATT-02/.+ contracted numeric labels",
        ),
        (
            lambda item: _row(item, "B-ATT-02")["samples"][0].update(
                absolute_tolerance=1.000001e-12
            ),
            "B-ATT-02/.+ bounded numeric tolerance",
        ),
        (
            lambda item: _row(item, "B-ATT-02")["samples"][0].update(
                relative_tolerance=1e-15
            ),
            "B-ATT-02/.+ bounded numeric tolerance",
        ),
        (
            lambda item: _row(item, "B-ATT-02")["samples"][0]["input"].pop(
                "q_nb_estimate"
            ),
            "B-ATT-02/.+ exact contracted input fields",
        ),
        (
            lambda item: _row(item, "B-BIND-02")["samples"][0][
                "independent_expected"
            ]["value"].pop("output_is_g1_torque_command"),
            "B-BIND-02/.+ contracted expected value fields",
        ),
        (
            lambda item: item["case_traces"]["execution_sources"][0].update(
                collected_testcases=999999
            ),
            "ctest collected testcase count",
        ),
        (
            lambda item: item["case_traces"]["execution_sources"][0].update(
                path="fabricated.bin"
            ),
            "ctest JUnit path",
        ),
        (
            lambda item: item["case_traces"]["execution_sources"][0].update(
                size_bytes=0
            ),
            "ctest JUnit byte size",
        ),
        (
            lambda item: item["case_traces"]["execution_sources"][0].update(
                sha256="0" * 64
            ),
            "ctest JUnit digest",
        ),
        (
            lambda item: _row(item, "B-AW-02")["samples"][0]["actual"].pop(
                "values"
            ),
            "B-AW-02/.+ numeric dimensions",
        ),
        (
            lambda item: _row(item, "B-ATT-01")["nodes"].append(
                "b0_controller::orphan"
            ),
            "B-ATT-01 exact controlled nodes",
        ),
        (
            lambda item: _row(item, "B-DERIV-01")["node_executions"][0].update(
                status="fail"
            ),
            "B-DERIV-01 node .+ detached from JUnit source",
        ),
        (
            lambda item: (
                _row(item, "B-LIMIT-01")["samples"][0]["actual"][
                    "values"
                ].__setitem__(0, 2.0),
                _row(item, "B-LIMIT-01")["samples"][0]["comparison"].update(
                    max_absolute_error=2.0
                ),
            ),
            "B-LIMIT-01/.+ comparison result",
        ),
        (
            lambda item: next(
                sample
                for sample in _row(item, "B-TIME-01")["samples"]
                if sample["comparison"]["kind"] == "binding_rejection_atomic"
            )["actual"].update(message="wrong boundary message"),
            "B-TIME-01/.+ comparison result",
        ),
    ],
)
def test_missing_review_critical_evidence_field_is_rejected(
    mutation, message, tmp_path: Path
):
    item = deepcopy(artifact())
    kwargs = _validation_kwargs(item, tmp_path)
    mutation(item)
    with pytest.raises(ValueError, match=message):
        evidence_module.validate_evidence(item, **kwargs)


def _source_node(item: dict, node: str) -> dict:
    return next(
        source["nodes"][node]
        for source in item["case_traces"]["execution_sources"]
        if node in source["nodes"]
    )


def test_junit_invocation_count_must_match_collected_cases(tmp_path: Path):
    item = deepcopy(artifact())
    kwargs = _validation_kwargs(item, tmp_path)
    row = _row(item, "B-ATT-01")
    node = row["nodes"][0]
    _source_node(item, node)["invocation_count"] = 2
    row["node_executions"][0]["invocation_count"] = 2
    source = next(
        source
        for source in item["case_traces"]["execution_sources"]
        if node in source["nodes"]
    )
    source["collected_testcases"] += 1
    with pytest.raises(ValueError, match="JUnit node .+ collected cases"):
        evidence_module.validate_evidence(item, **kwargs)


def _mutation_fixture(item: dict, row_id: str = "B-DETECT-01"):
    row = _row(item, row_id)
    sample = row["samples"][0]
    node = row["nodes"][0]
    source_record = _source_node(item, node)
    row_record = row["node_executions"][0]
    return sample, source_record, row_record


def test_mutation_detection_requires_the_detection_marker(tmp_path: Path):
    item = deepcopy(artifact())
    sample, source_record, row_record = _mutation_fixture(item)
    output = "oracle ran but no subject-mutation detection marker was emitted"
    source_record["output"] = output
    row_record["output"] = output
    sample["actual"]["execution"]["output"] = output
    with pytest.raises(ValueError, match="mutation detection marker"):
        evidence_module.validate_evidence(
            item, **_validation_kwargs(item, tmp_path)
        )


def test_mutation_detection_requires_the_declared_unchanged_oracle(tmp_path: Path):
    item = deepcopy(artifact())
    sample, _source_record, _row_record = _mutation_fixture(item)
    sample["input"]["unchanged_oracle_node"] = "wrong_oracle"
    with pytest.raises(ValueError, match="unchanged oracle"):
        evidence_module.validate_evidence(
            item, **_validation_kwargs(item, tmp_path)
        )


def test_mutation_sample_execution_is_bound_to_its_junit_node(tmp_path: Path):
    item = deepcopy(artifact())
    sample, _source_record, _row_record = _mutation_fixture(item)
    sample["actual"]["execution"]["duration_s"] = 999.0
    with pytest.raises(ValueError, match="mutation execution"):
        evidence_module.validate_evidence(
            item, **_validation_kwargs(item, tmp_path)
        )


def test_configuration_rejection_requires_the_expected_message(tmp_path: Path):
    item = deepcopy(artifact())
    sample = _row(item, "B-CONFIG-02")["samples"][0]
    message = "unrelated configuration failure"
    sample["independent_expected"]["value"]["message"] = message
    sample["actual"]["value"]["message"] = message
    with pytest.raises(ValueError, match="exact failure reason"):
        evidence_module.validate_evidence(
            item, **_validation_kwargs(item, tmp_path)
        )


def _attach_junit_bytes(item: dict, tmp_path: Path) -> dict[str, Path]:
    paths = {
        "ctest": tmp_path / "ctest-debug.xml",
        "pytest": tmp_path / "pytest-debug.xml",
    }
    for kind, path in paths.items():
        source = next(
            source
            for source in item["case_traces"]["execution_sources"]
            if source["kind"] == kind
        )
        suite = ET.Element("testsuite")
        for node, record in source["nodes"].items():
            assert record["invocation_count"] == len(record["collected_cases"])
            invocation_time = record["duration_s"] / record["invocation_count"]
            for collected_name in record["collected_cases"]:
                classname = (
                    "ctest"
                    if kind == "ctest"
                    else Path(node.split("::", 1)[0]).stem
                )
                case = ET.SubElement(
                    suite,
                    "testcase",
                    name=collected_name,
                    classname=classname,
                    time=str(invocation_time),
                )
                if record["output"]:
                    ET.SubElement(case, "system-out").text = record["output"]
        ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)
        source["size_bytes"] = path.stat().st_size
        source["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return paths


def _validation_kwargs(item: dict, tmp_path: Path) -> dict:
    return {
        "junit_paths": _attach_junit_bytes(item, tmp_path),
        "matrix_path": MATRIX_PATH,
    }


def test_junit_digest_is_recomputed_from_supplied_bytes(tmp_path: Path):
    item = deepcopy(artifact())
    paths = _attach_junit_bytes(item, tmp_path)
    evidence_module.validate_evidence(
        item, junit_paths=paths, matrix_path=MATRIX_PATH
    )
    original = paths["ctest"].read_bytes()
    replacement = original.replace(b"ctest", b"xunit", 1)
    assert len(replacement) == len(original)
    paths["ctest"].write_bytes(replacement)
    with pytest.raises(ValueError, match="ctest JUnit byte digest match"):
        evidence_module.validate_evidence(
            item, junit_paths=paths, matrix_path=MATRIX_PATH
        )


def test_junit_size_is_recomputed_from_supplied_bytes(tmp_path: Path):
    item = deepcopy(artifact())
    paths = _attach_junit_bytes(item, tmp_path)
    evidence_module.validate_evidence(
        item, junit_paths=paths, matrix_path=MATRIX_PATH
    )
    paths["pytest"].write_bytes(paths["pytest"].read_bytes() + b"x")
    with pytest.raises(ValueError, match="pytest JUnit byte size match"):
        evidence_module.validate_evidence(
            item, junit_paths=paths, matrix_path=MATRIX_PATH
        )


def test_junit_nodes_are_reparsed_from_supplied_xml(tmp_path: Path):
    item = deepcopy(artifact())
    paths = _attach_junit_bytes(item, tmp_path)
    evidence_module.validate_evidence(
        item, junit_paths=paths, matrix_path=MATRIX_PATH
    )
    node = _row(item, "B-ATT-01")["nodes"][0]
    forged_output = "self-described output absent from the supplied JUnit XML"
    _source_node(item, node)["output"] = forged_output
    _row(item, "B-ATT-01")["node_executions"][0]["output"] = forged_output
    with pytest.raises(ValueError, match="ctest JUnit .+ match"):
        evidence_module.validate_evidence(
            item, junit_paths=paths, matrix_path=MATRIX_PATH
        )


def test_non_xml_junit_bytes_are_rejected_even_when_metadata_matches(tmp_path: Path):
    item = deepcopy(artifact())
    paths = _attach_junit_bytes(item, tmp_path)
    paths["ctest"].write_bytes(b"not XML but metadata can still be made self-consistent")
    source = item["case_traces"]["execution_sources"][0]
    source["size_bytes"] = paths["ctest"].stat().st_size
    source["sha256"] = hashlib.sha256(paths["ctest"].read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="ctest JUnit bytes parse"):
        evidence_module.validate_evidence(
            item, junit_paths=paths, matrix_path=MATRIX_PATH
        )


def test_validation_requires_both_junit_and_matrix_paths(tmp_path: Path):
    item = deepcopy(artifact())
    paths = _attach_junit_bytes(item, tmp_path)
    with pytest.raises((TypeError, ValueError)):
        evidence_module.validate_evidence(item, matrix_path=MATRIX_PATH)
    with pytest.raises((TypeError, ValueError)):
        evidence_module.validate_evidence(item, junit_paths=paths)


def test_matrix_digest_is_recomputed_from_supplied_bytes(tmp_path: Path):
    item = deepcopy(artifact())
    kwargs = _validation_kwargs(item, tmp_path)
    item["case_traces"]["matrix_sha256"] = "b" * 64
    with pytest.raises(ValueError, match="matrix .+ digest"):
        evidence_module.validate_evidence(item, **kwargs)


def test_numeric_units_are_contracted_per_case(tmp_path: Path):
    item = deepcopy(artifact())
    sample = _sample(item, "B-ATT-02", "nonidentity-multiaxis")
    sample["units"] = ["kg"] * len(sample["units"])
    with pytest.raises(ValueError, match="contracted units"):
        evidence_module.validate_evidence(
            item, **_validation_kwargs(item, tmp_path)
        )


def test_case_input_keys_reject_fabricated_fields(tmp_path: Path):
    item = deepcopy(artifact())
    sample = _row(item, "B-RATE-01")["samples"][0]
    sample["input"]["fabricated"] = "not in the manifest"
    with pytest.raises(ValueError, match="contracted input fields"):
        evidence_module.validate_evidence(
            item, **_validation_kwargs(item, tmp_path)
        )


def test_mixed_half_turn_magnitude_cannot_be_self_consistently_forged(
    tmp_path: Path,
):
    item = deepcopy(artifact())
    sample = _sample(item, "B-ATT-03", "mixed-half-turn-signs-and-values")
    forged = [99.0, -99.0, 99.0]
    sample["independent_expected"]["values"] = list(forged)
    sample["actual"]["values"] = list(forged)
    sample["comparison"].update(max_absolute_error=0.0, result=True)
    with pytest.raises(ValueError, match="contracted numeric oracle"):
        evidence_module.validate_evidence(
            item, **_validation_kwargs(item, tmp_path)
        )


def test_released_hold_ticks_cannot_be_self_consistently_forged(tmp_path: Path):
    item = deepcopy(artifact())
    sample = _row(item, "B-AW-03")["samples"][0]
    labels = sample["independent_expected"]["labels"]
    for index, label in enumerate(labels):
        if label.startswith(("tick3_", "tick4_")):
            sample["independent_expected"]["values"][index] = 99.0
            sample["actual"]["values"][index] = 99.0
    sample["comparison"].update(max_absolute_error=0.0, result=True)
    with pytest.raises(ValueError, match="approved release oracle"):
        evidence_module.validate_evidence(
            item, **_validation_kwargs(item, tmp_path)
        )


def test_reset_semantics_cannot_be_self_consistently_forged(tmp_path: Path):
    item = deepcopy(artifact())
    sample = _row(item, "B-RESET-01")["samples"][0]
    for side in (sample["independent_expected"]["value"], sample["actual"]["value"]):
        side["state"]["reset"] = False
        side["state"]["epoch_id"] = 999
        side["state"]["expected_held_command"]["epoch_id"] = 999
        side["state"]["last_diagnostics"]["epoch_id"] = 999
        side["reset_output"]["epoch_id"] = 999
    sample["comparison"]["result"] = True
    with pytest.raises(ValueError, match="reset semantics"):
        evidence_module.validate_evidence(
            item, **_validation_kwargs(item, tmp_path)
        )


def _build_layout(tmp_path: Path, *, cache_case: str | None = None):
    repo = (tmp_path / "repo").resolve()
    build = (repo / "build/b0-controller/debug").resolve()
    module = (build / "03_control/b0").resolve()
    module.mkdir(parents=True)
    entries = {
        "CMAKE_BUILD_TYPE": "Debug",
        "CMAKE_CACHEFILE_DIR": build.as_posix(),
        "CMAKE_HOME_DIRECTORY": repo.as_posix(),
    }
    if cache_case == "build_type":
        entries["CMAKE_BUILD_TYPE"] = "Release"
    elif cache_case == "build_directory":
        entries["CMAKE_CACHEFILE_DIR"] = (repo / "other-build").as_posix()
    elif cache_case == "source_directory":
        entries["CMAKE_HOME_DIRECTORY"] = (repo / "other-source").as_posix()
    (build / "CMakeCache.txt").write_text(
        "\n".join(
            (
                f"CMAKE_BUILD_TYPE:STRING={entries['CMAKE_BUILD_TYPE']}",
                f"CMAKE_CACHEFILE_DIR:INTERNAL={entries['CMAKE_CACHEFILE_DIR']}",
                f"CMAKE_HOME_DIRECTORY:INTERNAL={entries['CMAKE_HOME_DIRECTORY']}",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    return repo, build, module


def test_actual_build_layout_accepts_one_consistent_cache(tmp_path):
    repo, build, module = _build_layout(tmp_path)
    entries = evidence_module._validated_build_layout(
        module, build, "Debug", repo, Path("03_control/b0")
    )
    assert entries["CMAKE_BUILD_TYPE"] == "Debug"


def test_actual_build_layout_rejects_wrong_module_directory(tmp_path):
    repo, build, module = _build_layout(tmp_path)
    with pytest.raises(RuntimeError, match="module directory does not belong"):
        evidence_module._validated_build_layout(
            module.parent / "elsewhere",
            build,
            "Debug",
            repo,
            Path("03_control/b0"),
        )


@pytest.mark.parametrize(
    ("cache_case", "message"),
    [
        ("build_type", "build type differs"),
        ("build_directory", "build directory differs"),
        ("source_directory", "source directory differs"),
    ],
)
def test_actual_build_layout_rejects_cross_wired_cache(tmp_path, cache_case, message):
    repo, build, module = _build_layout(tmp_path, cache_case=cache_case)
    with pytest.raises(RuntimeError, match=message):
        evidence_module._validated_build_layout(
            module, build, "Debug", repo, Path("03_control/b0")
        )
