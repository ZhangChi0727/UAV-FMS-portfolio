from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "g2b_evidence_contract", REPO / "03_control/b0/evidence.py"
)
assert SPEC is not None and SPEC.loader is not None
evidence_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evidence_module)


def artifact() -> dict:
    digest = "a" * 64
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
    }
    return {
        "schema_version": "b0-g2b-controller-evidence/v1",
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
        "criteria": criteria,
        "all_selected_component_criteria_pass": True,
        "limitations": ["component evidence only"],
    }


def test_required_controller_evidence_fields_are_accepted():
    evidence_module.validate_evidence(artifact())


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
    ],
)
def test_missing_review_critical_evidence_field_is_rejected(mutation, message):
    item = deepcopy(artifact())
    mutation(item)
    with pytest.raises(ValueError, match=message):
        evidence_module.validate_evidence(item)


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
