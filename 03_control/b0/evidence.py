"""Emit reviewable G2-B controller component evidence.

The artifact is deliberately a component-level numerical trace.  It records
the module/build identity, approved configuration identities, independent
one-step oracles, paired-command timing, and rejection atomicity.  It does not
claim G3 closed-loop performance, HIL, board execution, or flight evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import platform
import re
import subprocess
import sys
from typing import Any


ABS_TOL = 1e-12


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=repo, text=True, stderr=subprocess.DEVNULL
    ).strip()


def _command_version(command: list[str]) -> str:
    try:
        output = subprocess.check_output(
            command, text=True, stderr=subprocess.STDOUT
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        return f"unavailable: {type(exc).__name__}"
    return output.splitlines()[0] if output else "unavailable: empty output"


def _execution_identity(source_commit: str) -> dict[str, Any]:
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return {
            "context": "github_actions",
            "checked_out_source_commit": source_commit,
            "run_id": os.environ.get("GITHUB_RUN_ID"),
            "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "event_name": os.environ.get("GITHUB_EVENT_NAME"),
            "github_sha_metadata": os.environ.get("GITHUB_SHA"),
            "github_ref_metadata": os.environ.get("GITHUB_REF"),
            "github_head_ref": os.environ.get("GITHUB_HEAD_REF") or None,
            "repository": os.environ.get("GITHUB_REPOSITORY"),
            "workflow_ref": os.environ.get("GITHUB_WORKFLOW_REF"),
            "identity_note": "checked_out_source_commit is authoritative for artifact bytes; github_sha_metadata is retained separately and may name the pull-request merge ref",
        }
    return {
        "context": "local",
        "checked_out_source_commit": source_commit,
        "run_id": None,
        "run_attempt": None,
        "event_name": None,
        "github_sha_metadata": None,
        "github_ref_metadata": None,
        "github_head_ref": None,
        "repository": None,
        "workflow_ref": None,
        "identity_note": "local generation has no GitHub Actions run identity",
    }


def _cmake_cache_entries(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="strict").splitlines():
        if not line or line.startswith(("#", "//")) or "=" not in line:
            continue
        key_and_type, value = line.split("=", 1)
        key = key_and_type.split(":", 1)[0]
        entries[key] = value
    return entries


def _validated_build_layout(
    module_dir: Path,
    build_dir: Path,
    build_type: str,
    repo: Path,
    source_subdirectory: Path,
) -> dict[str, str]:
    """Bind the imported module, cache and declared configuration to one build."""

    module_dir = module_dir.resolve()
    build_dir = build_dir.resolve()
    repo = repo.resolve()
    expected_module_dir = (build_dir / source_subdirectory).resolve()
    if module_dir != expected_module_dir:
        raise RuntimeError(
            "controller module directory does not belong to declared build: "
            f"{module_dir} != {expected_module_dir}"
        )

    cache = build_dir / "CMakeCache.txt"
    if not cache.is_file():
        raise RuntimeError(f"declared build has no CMake cache: {cache}")
    entries = _cmake_cache_entries(cache)
    cached_build_type = entries.get("CMAKE_BUILD_TYPE")
    if cached_build_type != build_type:
        raise RuntimeError(
            "declared build type differs from CMake cache: "
            f"{build_type} != {cached_build_type!r}"
        )

    def exact_cached_path(key: str, expected: Path, label: str) -> None:
        value = entries.get(key)
        if not value:
            raise RuntimeError(f"CMake cache lacks {label}")
        cached = Path(value)
        if not cached.is_absolute() or cached.resolve() != expected.resolve():
            raise RuntimeError(
                f"CMake cache {label} differs from declared path: "
                f"{value!r} != {expected}"
            )

    exact_cached_path("CMAKE_CACHEFILE_DIR", build_dir, "build directory")
    exact_cached_path("CMAKE_HOME_DIRECTORY", repo, "source directory")
    return entries


def _display_path(path: Path, repo: Path) -> str:
    path = path.resolve()
    try:
        return str(path.relative_to(repo.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _catch2_identity(cache_entries: dict[str, str], repo: Path) -> dict[str, Any]:
    pinned_revision = "b5373dadca40b7edc8570cf9470b9b1cb1934d40"
    source_value = cache_entries.get("Catch2_SOURCE_DIR", "")
    source = Path(source_value) if source_value else None
    if source is not None and source.is_dir():
        revision = _git(source, "rev-parse", "HEAD")
        cmake_text = (source / "CMakeLists.txt").read_text(encoding="utf-8")
        match = re.search(
            r"project\(\s*Catch2\b.*?\bVERSION\s+([0-9]+(?:\.[0-9]+)+)",
            cmake_text,
            flags=re.DOTALL,
        )
        if match is None:
            raise RuntimeError("cannot identify fetched Catch2 version")
        identity = {
            "mode": "fetched_pinned_revision",
            "version": match.group(1),
            "source_directory": _display_path(source, repo),
            "git_revision": revision,
            "required_git_revision": pinned_revision,
        }
        if identity["version"] != "3.5.4" or revision != pinned_revision:
            raise RuntimeError(f"unexpected fetched Catch2 identity: {identity}")
        return identity

    cmake_dir_value = cache_entries.get("Catch2_DIR", "")
    if not cmake_dir_value or cmake_dir_value.endswith("-NOTFOUND"):
        raise RuntimeError("CMake cache has no resolved Catch2 source or package")
    cmake_dir = Path(cmake_dir_value)
    version_file = cmake_dir / "Catch2ConfigVersion.cmake"
    text = version_file.read_text(encoding="utf-8")
    match = re.search(r"set\(PACKAGE_VERSION\s+\"([^\"]+)\"\)", text)
    if match is None or match.group(1) != "3.5.4":
        raise RuntimeError("installed Catch2 identity is not exact version 3.5.4")
    return {
        "mode": "installed_exact_package",
        "version": match.group(1),
        "cmake_directory": _display_path(cmake_dir, repo),
        "config_version_sha256": _sha256(version_file),
        "required_git_revision": None,
    }


def _build_identity(
    module_dir: Path,
    module_path: Path,
    build_dir: Path,
    build_type: str,
    repo: Path,
    cache_entries: dict[str, str],
) -> dict[str, Any]:
    cache = build_dir / "CMakeCache.txt"
    entries = cache_entries
    try:
        module_path.resolve().relative_to(module_dir.resolve())
    except ValueError as exc:
        raise RuntimeError(
            f"loaded controller module is outside declared module directory: {module_path}"
        ) from exc
    compiler = entries.get("CMAKE_CXX_COMPILER")
    python_executable = entries.get("_Python3_EXECUTABLE") or entries.get(
        "Python3_EXECUTABLE"
    )
    pybind_dir = entries.get("pybind11_DIR")
    if not compiler or not python_executable or not pybind_dir:
        raise RuntimeError("CMake cache lacks compiler, Python, or pybind11 identity")
    pybind_version = _command_version(
        [python_executable, "-c", "import pybind11; print(pybind11.__version__)"]
    )
    if pybind_version != "2.13.6":
        raise RuntimeError(f"unexpected pybind11 version: {pybind_version}")
    configured_python = Path(python_executable).resolve()
    generator_python = Path(sys.executable).resolve()
    if configured_python != generator_python:
        raise RuntimeError(
            "evidence generator Python differs from CMake Python: "
            f"{generator_python} != {configured_python}"
        )
    return {
        "build_type": build_type,
        "cmake_build_type": entries["CMAKE_BUILD_TYPE"],
        "build_directory": _display_path(build_dir, repo),
        "cmake_cache_directory": _display_path(
            Path(entries["CMAKE_CACHEFILE_DIR"]), repo
        ),
        "cmake_home_directory": _display_path(
            Path(entries["CMAKE_HOME_DIRECTORY"]), repo
        ),
        "module_directory": _display_path(module_dir, repo),
        "module_path": _display_path(module_path, repo),
        "module_sha256": _sha256(module_path),
        "cmake_cache_sha256": _sha256(cache),
        "python": sys.version.split()[0],
        "python_executable": _display_path(configured_python, repo),
        "generator_python_executable": _display_path(generator_python, repo),
        "cmake_python_matches_generator": True,
        "python_implementation": platform.python_implementation(),
        "python_abi": getattr(sys.implementation, "cache_tag", "unknown"),
        "platform": platform.platform(),
        "cmake": _command_version(["cmake", "--version"]),
        "cxx_compiler": _display_path(Path(compiler), repo),
        "cxx": _command_version([compiler, "--version"]),
        "pybind11": {
            "version": pybind_version,
            "cmake_directory": _display_path(Path(pybind_dir), repo),
        },
        "catch2": _catch2_identity(entries, repo),
    }


def _plain(value: Any) -> Any:
    """Copy pybind values into JSON data without retaining live references."""

    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    fields = (
        "reset",
        "accepted",
        "reason",
        "epoch_id",
        "tick_index",
        "epoch_origin_s",
        "expected_timestamp_s",
        "integral_Nm",
        "derivative_filtered_rad_s2",
        "previous_rate_rad_s",
        "has_previous_rate",
        "expected_held_command",
        "last_diagnostics",
        "requested_torque_body_Nm",
        "limited_torque_body_Nm",
        "saturated",
        "timestamp_s",
        "rate_error_rad_s",
        "derivative_raw_rad_s2",
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
    result = {
        name: _plain(getattr(value, name))
        for name in fields
        if hasattr(value, name)
    }
    if result:
        return result
    raise TypeError(f"cannot serialize evidence value of type {type(value).__name__}")


def _parameters(module):
    track = Path(__file__).resolve().parent
    sys.path.insert(0, str(track / "python"))
    from controller import load_controller_parameters

    return load_controller_parameters(module=module, track=track)


def _reset(module, controller, epoch_id: int = 7, timestamp_s: float = 12.0):
    epoch = module.ResetEpoch()
    epoch.id = epoch_id
    epoch.timestamp_s = timestamp_s
    return controller.reset(module.ControllerInitialState(), epoch)


def _inputs(module, timestamp_s: float, held, *, epoch_id: int = 7):
    command = module.AttitudeCommand()
    command.q_nb = [1.0, 0.0, 0.0, 0.0]
    command.timestamp_s = timestamp_s
    command.valid = True
    command.epoch_id = epoch_id

    estimate = module.StateEstimate()
    estimate.q_nb = [1.0, 0.0, 0.0, 0.0]
    estimate.omega_b_rad_s = [0.0, 0.0, 0.0]
    estimate.timestamp_s = timestamp_s
    estimate.valid = True
    estimate.epoch_id = epoch_id

    feedback = module.ActuatorFeedback()
    feedback.actual_torque_body_Nm = [0.0, 0.0, 0.0]
    feedback.limited_torque_body_Nm = list(held.limited_torque_body_Nm)
    feedback.saturated = list(held.saturated)
    feedback.timestamp_s = timestamp_s
    feedback.command_timestamp_s = held.timestamp_s
    feedback.epoch_id = epoch_id
    return command, estimate, feedback


def _max_abs_error(actual, expected) -> float:
    return max(abs(float(a) - float(e)) for a, e in zip(actual, expected))


def _attitude_sign_probe(module, parameters) -> dict[str, Any]:
    controller = module.CascadedController(parameters)
    held = _reset(module, controller)
    command, estimate, feedback = _inputs(module, 12.005, held)
    angle = 0.1
    command.q_nb = [math.cos(angle / 2.0), math.sin(angle / 2.0), 0.0, 0.0]
    output = controller.step(command, estimate, feedback, parameters.controller_period_s)
    diagnostics = controller.last_diagnostics()
    expected_rate = parameters.attitude_kp[0] * 2.0 * math.sin(angle / 2.0)
    expected_request = parameters.rate_kp[0] * expected_rate
    expected = [expected_request, 0.0, 0.0]
    return {
        "input": {
            "q_nb_command": list(command.q_nb),
            "q_nb_estimate": list(estimate.q_nb),
            "omega_b_rad_s": list(estimate.omega_b_rad_s),
            "timestamp_s": command.timestamp_s,
        },
        "independent_oracle": {
            "attitude_error_vector": [2.0 * math.sin(angle / 2.0), 0.0, 0.0],
            "rate_target_rad_s": [expected_rate, 0.0, 0.0],
            "requested_torque_body_Nm": expected,
            "absolute_tolerance": ABS_TOL,
            "relative_tolerance": 0.0,
        },
        "actual": _plain(output),
        "diagnostics": _plain(diagnostics),
        "max_request_abs_error_Nm": _max_abs_error(
            output.requested_torque_body_Nm, expected
        ),
    }


def _antiwindup_probe(module, parameters) -> dict[str, Any]:
    controller = module.CascadedController(parameters)
    held = _reset(module, controller)
    command, estimate, feedback = _inputs(module, 12.005, held)
    # Identity attitude produces a zero outer-loop target.  A negative measured
    # body rate makes positive rate error large enough to saturate the x request.
    estimate.omega_b_rad_s = [-6.0, 0.0, 0.0]
    output = controller.step(command, estimate, feedback, parameters.controller_period_s)
    diagnostics = controller.last_diagnostics()
    rate_error = 6.0
    request = parameters.rate_kp[0] * rate_error
    limited = parameters.torque_limit_Nm[0]
    conditional_ki = 0.0  # positive error would push farther into positive saturation
    limit_backcalc = parameters.kaw_limit_per_s[0] * (limited - request)
    lag_backcalc = 0.0
    integral_after = parameters.controller_period_s * (
        conditional_ki + limit_backcalc + lag_backcalc
    )
    independent = {
        "rate_error_rad_s": [rate_error, 0.0, 0.0],
        "proportional_Nm": [request, 0.0, 0.0],
        "conditional_integral_rate_Nm_s": [conditional_ki, 0.0, 0.0],
        "limit_backcalculation_rate_Nm_s": [limit_backcalc, 0.0, 0.0],
        "lag_backcalculation_rate_Nm_s": [lag_backcalc, 0.0, 0.0],
        "integral_after_Nm": [integral_after, 0.0, 0.0],
        "request_Nm": [request, 0.0, 0.0],
        "limited_Nm": [limited, 0.0, 0.0],
        "saturated": [True, False, False],
        "absolute_tolerance": ABS_TOL,
        "relative_tolerance": 0.0,
    }
    return {
        "input": {
            "omega_b_rad_s": list(estimate.omega_b_rad_s),
            "held_command": _plain(held),
            "actual_torque_body_Nm": list(feedback.actual_torque_body_Nm),
            "dt_s": parameters.controller_period_s,
        },
        "independent_oracle": independent,
        "actual": _plain(output),
        "diagnostics": _plain(diagnostics),
        "errors": {
            "request_Nm": abs(output.requested_torque_body_Nm[0] - request),
            "limited_Nm": abs(output.limited_torque_body_Nm[0] - limited),
            "integral_after_Nm": abs(
                diagnostics.integral_after_Nm[0] - integral_after
            ),
            "limit_backcalculation_rate_Nm_s": abs(
                diagnostics.limit_backcalculation_rate_Nm_s[0] - limit_backcalc
            ),
        },
    }


def _paired_timing_probe(module, parameters) -> dict[str, Any]:
    controller = module.CascadedController(parameters)
    held = _reset(module, controller)
    trace = []
    for tick in range(1, 4):
        timestamp = 12.0 + tick * parameters.controller_period_s
        command, estimate, feedback = _inputs(module, timestamp, held)
        feedback.actual_torque_body_Nm = list(held.limited_torque_body_Nm)
        output = controller.step(
            command, estimate, feedback, parameters.controller_period_s
        )
        trace.append(
            {
                "tick_index": tick,
                "current_timestamp_s": timestamp,
                "paired_command_timestamp_s": feedback.command_timestamp_s,
                "feedback_limited_torque_body_Nm": list(
                    feedback.limited_torque_body_Nm
                ),
                "output": _plain(output),
                "diagnostics": _plain(controller.last_diagnostics()),
            }
        )
        held = output
    expected_times = [12.0 + tick * parameters.controller_period_s for tick in range(4)]
    return {
        "trace": trace,
        "independent_expected_publication_times_s": expected_times,
        "each_feedback_pairs_previous_publication": all(
            abs(row["paired_command_timestamp_s"] - expected_times[index]) <= ABS_TOL
            for index, row in enumerate(trace)
        ),
    }


def _atomic_rejection_probe(module, parameters) -> dict[str, Any]:
    controller = module.CascadedController(parameters)
    held = _reset(module, controller)
    command, estimate, feedback = _inputs(module, 12.005, held)
    before = _plain(controller.snapshot())
    estimate.valid = False
    reason = None
    try:
        controller.step(command, estimate, feedback, parameters.controller_period_s)
    except module.ControllerContractError as exc:
        reason = getattr(exc, "reason", None)
        if callable(reason):
            reason = reason()
        reason = reason or str(exc).split(":", 1)[0]
    else:
        raise RuntimeError("invalid estimate was accepted")
    after = _plain(controller.snapshot())
    estimate.valid = True
    retry = controller.step(command, estimate, feedback, parameters.controller_period_s)
    return {
        "invalid_input": {"estimate_valid": False, "timestamp_s": 12.005},
        "stable_reason": reason,
        "snapshot_before": before,
        "snapshot_after": after,
        "snapshot_unchanged": before == after,
        "corrected_same_tick_retry": _plain(retry),
    }


def build_evidence(module_dir: Path, build_dir: Path, build_type: str) -> dict[str, Any]:
    track = Path(__file__).resolve().parent
    repo = track.parents[1]
    module_dir = module_dir.resolve()
    build_dir = build_dir.resolve()
    cache_entries = _validated_build_layout(
        module_dir,
        build_dir,
        build_type,
        repo,
        track.relative_to(repo),
    )
    sys.path.insert(0, str(module_dir))
    module = importlib.import_module("b0_controller")
    module_path = Path(module.__file__).resolve()
    if module_dir not in module_path.parents:
        raise RuntimeError(f"loaded stale controller module outside build: {module_path}")
    parameters = _parameters(module)

    attitude = _attitude_sign_probe(module, parameters)
    antiwindup = _antiwindup_probe(module, parameters)
    pairing = _paired_timing_probe(module, parameters)
    rejection = _atomic_rejection_probe(module, parameters)

    config = track / "configs/b0_g2_controller.v1.json"
    approval = track / "configs/b0_g2_controller_approval.v1.json"
    g0 = repo / "05_integration/b0/configs/b0_g0_contract.v2.json"
    validator = repo / "05_integration/b0/validate_config.py"
    source_commit = _git(repo, "rev-parse", "HEAD")
    criteria = {
        "attitude_request_absolute_error_le_1e_12": attitude[
            "max_request_abs_error_Nm"
        ]
        <= ABS_TOL,
        "saturation_request_absolute_error_le_1e_12": antiwindup["errors"][
            "request_Nm"
        ]
        <= ABS_TOL,
        "saturation_limit_absolute_error_le_1e_12": antiwindup["errors"][
            "limited_Nm"
        ]
        <= ABS_TOL,
        "antiwindup_integral_absolute_error_le_1e_12": antiwindup["errors"][
            "integral_after_Nm"
        ]
        <= ABS_TOL,
        "antiwindup_limit_term_absolute_error_le_1e_12": antiwindup["errors"][
            "limit_backcalculation_rate_Nm_s"
        ]
        <= ABS_TOL,
        "paired_feedback_uses_previous_publication": pairing[
            "each_feedback_pairs_previous_publication"
        ],
        "invalid_input_rejection_is_atomic": rejection["snapshot_unchanged"],
        "corrected_retry_publishes_due_tick": abs(
            rejection["corrected_same_tick_retry"]["timestamp_s"] - 12.005
        )
        <= ABS_TOL,
    }
    evidence = {
        "schema_version": "b0-g2b-controller-evidence/v1",
        "source_commit": source_commit,
        "component": "B0 G2-B cascaded attitude/body-rate controller",
        "execution_identity": _execution_identity(source_commit),
        "claim_boundary": {
            "level": "module_component",
            "g3_closed_loop_performance": False,
            "sil": False,
            "hil": False,
            "board_execution": False,
            "flight": False,
        },
        "build": _build_identity(
            module_dir,
            module_path,
            build_dir,
            build_type,
            repo,
            cache_entries,
        ),
        "configuration": {
            "implementation_path": str(config.relative_to(repo)).replace("\\", "/"),
            "implementation_sha256": _sha256(config),
            "approval_path": str(approval.relative_to(repo)).replace("\\", "/"),
            "approval_sha256": _sha256(approval),
            "g0_path": str(g0.relative_to(repo)).replace("\\", "/"),
            "g0_sha256": _sha256(g0),
            "validator_path": str(validator.relative_to(repo)).replace("\\", "/"),
            "validator_sha256": _sha256(validator),
        },
        "observations": {
            "attitude_sign_and_cascade": attitude,
            "saturation_and_limit_backcalculation": antiwindup,
            "paired_three_tick_timing": pairing,
            "atomic_invalid_measurement_rejection": rejection,
        },
        "criteria": criteria,
        "all_selected_component_criteria_pass": all(criteria.values()),
        "limitations": [
            "The JSON probes are representative retained traces; the complete S0 row matrix is executed by the adjacent C++ and Python test tracks.",
            "The artifact does not measure G3 recovery time, overshoot, yaw drift, cross-axis performance, or scenario acceptance.",
            "No plant truth is provided to the controller inputs.",
            "A pending PA review is not evidence acceptance.",
        ],
    }
    validate_evidence(evidence)
    return evidence


def validate_evidence(evidence: dict[str, Any]) -> None:
    """Fail closed when an artifact omits a review-critical identity or trace."""

    def need(condition: bool, message: str) -> None:
        if not condition:
            raise ValueError(f"invalid G2-B evidence: {message}")

    need(
        evidence.get("schema_version") == "b0-g2b-controller-evidence/v1",
        "schema version",
    )
    source_commit = evidence.get("source_commit")
    need(
        isinstance(source_commit, str)
        and re.fullmatch(r"[0-9a-f]{40}", source_commit) is not None,
        "source commit",
    )
    need(set(source_commit) != {"0"}, "source commit cannot be all zero")
    execution = evidence.get("execution_identity")
    need(isinstance(execution, dict), "execution identity")
    need(
        execution.get("checked_out_source_commit") == source_commit,
        "execution/source commit mismatch",
    )
    need(
        execution.get("context") in {"local", "github_actions"},
        "execution context",
    )
    if execution["context"] == "github_actions":
        need(
            isinstance(execution.get("run_id"), str)
            and execution["run_id"].isdigit(),
            "Actions run ID",
        )
        need(bool(execution.get("event_name")), "Actions event")
        need(
            isinstance(execution.get("github_sha_metadata"), str)
            and re.fullmatch(
                r"[0-9a-f]{40}", execution["github_sha_metadata"]
            )
            is not None,
            "Actions metadata SHA",
        )
    build = evidence.get("build")
    need(isinstance(build, dict), "build identity")
    for field in (
        "build_type",
        "cmake_build_type",
        "build_directory",
        "cmake_cache_directory",
        "cmake_home_directory",
        "module_directory",
        "module_path",
        "module_sha256",
        "cmake_cache_sha256",
        "python",
        "python_executable",
        "generator_python_executable",
        "python_abi",
        "cmake",
        "cxx_compiler",
        "cxx",
    ):
        need(bool(build.get(field)), f"build.{field}")
    need(build["build_type"] in {"Debug", "Release"}, "build type")
    need(
        build["cmake_build_type"] == build["build_type"],
        "declared/CMake build type mismatch",
    )
    need(
        build["cmake_cache_directory"] == build["build_directory"],
        "declared/CMake build directory mismatch",
    )
    need(build["cmake_home_directory"] == ".", "CMake source directory")
    declared_build = PurePosixPath(str(build["build_directory"]).replace("\\", "/"))
    declared_module = PurePosixPath(
        str(build["module_directory"]).replace("\\", "/")
    )
    declared_module_path = PurePosixPath(
        str(build["module_path"]).replace("\\", "/")
    )
    need(
        declared_module == declared_build / "03_control/b0",
        "module/build directory mismatch",
    )
    try:
        module_relative = declared_module_path.relative_to(declared_module)
    except ValueError:
        module_relative = None
    need(
        module_relative is not None and bool(module_relative.parts),
        "module path outside declared module directory",
    )
    need(build.get("cmake_python_matches_generator") is True, "Python ABI owner")
    need(
        re.fullmatch(r"[0-9a-f]{64}", build["module_sha256"]) is not None,
        "module digest",
    )
    need(
        re.fullmatch(r"[0-9a-f]{64}", build["cmake_cache_sha256"])
        is not None,
        "CMake cache digest",
    )
    pybind = build.get("pybind11")
    need(
        isinstance(pybind, dict)
        and pybind.get("version") == "2.13.6"
        and bool(pybind.get("cmake_directory")),
        "actual pybind11 identity",
    )
    catch2 = build.get("catch2")
    need(
        isinstance(catch2, dict) and catch2.get("version") == "3.5.4",
        "actual Catch2 version",
    )
    if catch2.get("mode") == "fetched_pinned_revision":
        need(
            catch2.get("git_revision")
            == "b5373dadca40b7edc8570cf9470b9b1cb1934d40"
            and bool(catch2.get("source_directory")),
            "fetched Catch2 revision/source",
        )
    elif catch2.get("mode") == "installed_exact_package":
        need(
            bool(catch2.get("cmake_directory"))
            and re.fullmatch(
                r"[0-9a-f]{64}", catch2.get("config_version_sha256", "")
            )
            is not None,
            "installed Catch2 package identity",
        )
    else:
        need(False, "Catch2 resolution mode")

    configuration = evidence.get("configuration")
    need(isinstance(configuration, dict), "configuration identity")
    for field in (
        "implementation_path",
        "implementation_sha256",
        "approval_path",
        "approval_sha256",
        "g0_path",
        "g0_sha256",
        "validator_path",
        "validator_sha256",
    ):
        need(bool(configuration.get(field)), f"configuration.{field}")
    for field in (
        "implementation_sha256",
        "approval_sha256",
        "g0_sha256",
        "validator_sha256",
    ):
        need(
            re.fullmatch(r"[0-9a-f]{64}", configuration[field]) is not None,
            f"configuration.{field} digest",
        )

    observations = evidence.get("observations")
    need(isinstance(observations, dict), "observations")
    for field in (
        "attitude_sign_and_cascade",
        "saturation_and_limit_backcalculation",
        "paired_three_tick_timing",
        "atomic_invalid_measurement_rejection",
    ):
        need(field in observations, f"observations.{field}")

    attitude = observations["attitude_sign_and_cascade"]
    need(isinstance(attitude, dict), "attitude observation")
    for field in (
        "input",
        "independent_oracle",
        "actual",
        "diagnostics",
        "max_request_abs_error_Nm",
    ):
        need(field in attitude, f"attitude observation.{field}")
    need(attitude["diagnostics"].get("accepted") is True, "attitude accepted")
    need(attitude["diagnostics"].get("reason") == "accepted", "attitude reason")

    antiwindup = observations["saturation_and_limit_backcalculation"]
    need(isinstance(antiwindup, dict), "anti-windup observation")
    for field in ("input", "independent_oracle", "actual", "diagnostics", "errors"):
        need(field in antiwindup, f"anti-windup observation.{field}")
    for field in (
        "accepted",
        "reason",
        "proportional_Nm",
        "integral_before_Nm",
        "derivative_Nm",
        "conditional_integral_rate_Nm_s",
        "limit_backcalculation_rate_Nm_s",
        "lag_backcalculation_rate_Nm_s",
        "integral_after_Nm",
        "requested_Nm",
        "limited_Nm",
    ):
        need(field in antiwindup["diagnostics"], f"anti-windup diagnostics.{field}")
    need(antiwindup["diagnostics"]["accepted"] is True, "anti-windup accepted")
    need(antiwindup["diagnostics"]["reason"] == "accepted", "anti-windup reason")
    for field in (
        "requested_torque_body_Nm",
        "limited_torque_body_Nm",
        "saturated",
        "timestamp_s",
    ):
        need(field in antiwindup["actual"], f"anti-windup actual.{field}")

    timing = observations["paired_three_tick_timing"]
    need(isinstance(timing, dict), "paired timing observation")
    trace = timing.get("trace")
    need(isinstance(trace, list) and len(trace) == 3, "three-tick pairing trace")
    for index, row in enumerate(trace, start=1):
        need(isinstance(row, dict), f"pairing trace row {index}")
        for field in (
            "tick_index",
            "current_timestamp_s",
            "paired_command_timestamp_s",
            "feedback_limited_torque_body_Nm",
            "output",
            "diagnostics",
        ):
            need(field in row, f"pairing trace row {index}.{field}")
        need(row["diagnostics"].get("accepted") is True, f"pairing trace row {index} accepted")
        need(row["diagnostics"].get("reason") == "accepted", f"pairing trace row {index} reason")
    need(
        isinstance(timing.get("independent_expected_publication_times_s"), list)
        and len(timing["independent_expected_publication_times_s"]) == 4,
        "paired timing independent publication times",
    )
    need(
        timing.get("each_feedback_pairs_previous_publication") is True,
        "paired timing result",
    )

    rejection = observations["atomic_invalid_measurement_rejection"]
    need(isinstance(rejection, dict), "atomic rejection observation")
    for field in (
        "invalid_input",
        "stable_reason",
        "snapshot_before",
        "snapshot_after",
        "snapshot_unchanged",
        "corrected_same_tick_retry",
    ):
        need(field in rejection, f"atomic rejection.{field}")
    need(bool(rejection["stable_reason"]), "atomic rejection stable reason")
    need(rejection["snapshot_unchanged"] is True, "atomic rejection snapshot equality")

    criteria = evidence.get("criteria")
    need(
        isinstance(criteria, dict)
        and criteria
        and all(isinstance(value, bool) for value in criteria.values()),
        "boolean criteria",
    )
    required_criteria = {
        "attitude_request_absolute_error_le_1e_12",
        "saturation_request_absolute_error_le_1e_12",
        "saturation_limit_absolute_error_le_1e_12",
        "antiwindup_integral_absolute_error_le_1e_12",
        "antiwindup_limit_term_absolute_error_le_1e_12",
        "paired_feedback_uses_previous_publication",
        "invalid_input_rejection_is_atomic",
        "corrected_retry_publishes_due_tick",
    }
    need(required_criteria <= set(criteria), "required component criteria")
    need(all(criteria.values()), "selected component criterion failed")
    need(
        evidence.get("all_selected_component_criteria_pass") is True,
        "aggregate criterion",
    )
    boundary = evidence.get("claim_boundary")
    need(
        isinstance(boundary, dict)
        and boundary.get("level") == "module_component"
        and all(
            boundary.get(field) is False
            for field in (
                "g3_closed_loop_performance",
                "sil",
                "hil",
                "board_execution",
                "flight",
            )
        ),
        "claim boundary",
    )
    need(bool(evidence.get("limitations")), "limitations")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--module-dir", type=Path, required=True)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--build-type", choices=("Debug", "Release"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evidence = build_evidence(args.module_dir, args.build_dir, args.build_type)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if not evidence["all_selected_component_criteria_pass"]:
        raise SystemExit("G2-B evidence criterion failed")


if __name__ == "__main__":
    main()
