"""Independent contract checks for the first G3-A implementation slice."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from runner import (
    ACCEPTANCE_SEED_HISTORY,
    BEHAVIOR_CLOSURE_PATHS,
    CONTROLLER_BUILD_INPUT_PATHS,
    RunnerContractError,
    _acceptance_seed_provenance,
    _live_bytes_match_source,
    _run_g3_bind_smoke,
    compare_g3_bind_results,
    run_saturation_reachability,
)
from scheduler import IntegerScheduler, ScheduleContractError


TRACK_ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads(
    (TRACK_ROOT / "configs/b0_g0_contract.v2.json").read_text(encoding="utf-8")
)


def test_integer_scheduler_has_reset_only_tick_and_exact_due_boundaries() -> None:
    scheduler = IntegerScheduler.from_contract(CONTRACT)
    reset = scheduler.boundary(0, 12.0)
    assert reset.timestamp_s == 12.0
    assert not any(
        (
            reset.plant_due,
            reset.actuator_due,
            reset.imu_due,
            reset.estimator_due,
            reset.controller_due,
        )
    )
    first = scheduler.boundary(1, 12.0)
    assert first.timestamp_s == 12.0025
    assert first.plant_due and first.actuator_due
    assert not first.imu_due and not first.estimator_due and not first.controller_due
    second = scheduler.boundary(2, 12.0)
    assert second.timestamp_s == 12.005
    assert all(
        (
            second.plant_due,
            second.actuator_due,
            second.imu_due,
            second.estimator_due,
            second.controller_due,
        )
    )
    assert scheduler.boundary(1_000_000, 12.0).timestamp_s == 2512.0


def test_integer_scheduler_rejects_phase_or_period_drift() -> None:
    changed = json.loads(json.dumps(CONTRACT))
    changed["timing"]["schedules"]["controller_every_ticks"] = 3
    with pytest.raises(ScheduleContractError, match="periods must be identical"):
        IntegerScheduler.from_contract(changed)
    with pytest.raises(ScheduleContractError, match="non-negative"):
        IntegerScheduler.from_contract(CONTRACT).boundary(-1)


def test_bind_smoke_rejects_acceptance_seed_before_loading_a_module(tmp_path: Path) -> None:
    with pytest.raises(RunnerContractError, match="only the approved tuning seed"):
        _run_g3_bind_smoke(tmp_path.resolve(), "Debug", 2026100901)


def test_bind_smoke_rejects_non_absolute_or_unknown_build_module() -> None:
    with pytest.raises(RunnerContractError, match="module_dir must be absolute"):
        _run_g3_bind_smoke(Path("relative"), "Debug", 2026100900)
    with pytest.raises(RunnerContractError, match="build_type"):
        _run_g3_bind_smoke(Path.cwd(), "Profile", 2026100900)


def test_bind_comparison_uses_exact_discrete_and_declared_float_tolerance() -> None:
    common = {
        "check_id": "G3-BIND",
        "classification": "development_interface_smoke_not_acceptance",
        "seed_kind": "tuning_seed",
        "seed": 2026100900,
        "call_counts": {"plant": 12},
        "records": [{"tick": 1, "updated": True, "value": 0.25}],
    }
    debug = {
        **common,
        "build_type": "Debug",
        "module_path": "/debug/b0_controller.so",
        "module_sha256": "a" * 64,
    }
    release = {
        **common,
        "build_type": "Release",
        "module_path": "/release/b0_controller.so",
        "module_sha256": "b" * 64,
    }
    compare_g3_bind_results(debug, release)
    release["records"] = [{"tick": 1, "updated": True, "value": 0.25 + 2e-12}]
    with pytest.raises(RunnerContractError, match="floating mismatch"):
        compare_g3_bind_results(debug, release)
    release["records"] = [{"tick": 1, "updated": False, "value": 0.25}]
    with pytest.raises(RunnerContractError, match="boolean mismatch"):
        compare_g3_bind_results(debug, release)


def test_reachability_run_identity_is_rejected_before_any_seed_exposure(
    tmp_path: Path,
) -> None:
    with pytest.raises(RunnerContractError, match="run_id"):
        run_saturation_reachability(
            tmp_path.resolve(), "Debug", tmp_path / "output", "bad id"
        )
    assert not (tmp_path / "output").exists()


def test_rate_kp_x_study_protocol_is_finite_tuning_only_and_one_dimensional() -> None:
    protocol = json.loads(
        (
            TRACK_ROOT / "configs/b0_g3_rate_kp_x_study.v1.json"
        ).read_text(encoding="utf-8")
    )
    candidates = protocol["execution_budget"]["candidates_rate_kp_x"]
    assert protocol["profile"]["seed"] == 2026100900
    assert protocol["profile"]["acceptance_seed_must_not_run"] is True
    assert protocol["parameter_whitelist"]["field"] == "controller.rate_pid.kp.x"
    assert 1 <= len(candidates) <= 8
    assert len(candidates) == len(set(candidates))
    assert candidates == [0.08, 0.17, 0.175, 0.176, 0.18, 0.19, 0.2]
    assert all(0.0 <= value <= 0.2 for value in candidates)


def test_acceptance_seed_provenance_separates_run_execution_from_history() -> None:
    tuning = _acceptance_seed_provenance(False)
    assert tuning["acceptance_seed_executed_this_run"] is False
    assert tuning["acceptance_seed_previously_exposed"] is True
    assert tuning["acceptance_seed_exposure_cumulative"] is True
    assert tuning["acceptance_seed_exposure_history"] == ACCEPTANCE_SEED_HISTORY

    diagnostic = _acceptance_seed_provenance(True)
    assert diagnostic["acceptance_seed_executed_this_run"] is True
    assert diagnostic["acceptance_seed_previously_exposed"] is True
    assert diagnostic["acceptance_seed_exposure_cumulative"] is True


def test_behavior_closure_contains_public_runtime_build_and_ci_inputs() -> None:
    required = {
        "01_simulation/b0/__init__.py",
        "01_simulation/b0/quaternion.py",
        "03_control/b0/include/b0_controller/controller.hpp",
        "03_control/b0/src/controller.cpp",
        "03_control/b0/python/controller_bindings.cpp",
        "03_control/b0/CMakeLists.txt",
        "CMakeLists.txt",
        "CMakePresets.json",
        "requirements/b0-dev.txt",
        ".github/workflows/ci.yml",
        ".github/workflows/g3a.yml",
    }
    assert required <= set(BEHAVIOR_CLOSURE_PATHS)
    assert set(CONTROLLER_BUILD_INPUT_PATHS) <= set(BEHAVIOR_CLOSURE_PATHS)
    assert len(BEHAVIOR_CLOSURE_PATHS) == len(set(BEHAVIOR_CLOSURE_PATHS))


def test_source_match_accepts_only_exact_or_line_ending_equivalent_bytes() -> None:
    source = b"gain=0.08\nmode=frozen\n"
    assert _live_bytes_match_source(source, source)
    assert _live_bytes_match_source(source.replace(b"\n", b"\r\n"), source)

    semantic_smudge_filter_output = b"gain=0.20\nmode=frozen\n"
    assert not _live_bytes_match_source(semantic_smudge_filter_output, source)
