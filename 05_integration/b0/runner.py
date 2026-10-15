"""Approved B0 components wired into the first deterministic G3 smoke loop.

This module deliberately exposes only the tuning-seed G3-BIND development check.
It is not an approved-scenario runner and does not calculate acceptance metrics.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.machinery
import importlib.util
import json
import math
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from events import EventSchedule
from scheduler import IntegerScheduler


REPO_ROOT = Path(__file__).resolve().parents[2]
G0_PATH = REPO_ROOT / "05_integration/b0/configs/b0_g0_contract.v2.json"
TUNING_SEED = 2026100900
IDENTITY = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)
RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
ACCEPTANCE_SEED_HISTORY = {
    "seed": 2026100906,
    "previously_exposed": True,
    "exposure_source_commit": "78abbbe27a6e451049d80fbcf9c8e031a5001b0c",
    "exposure_start_sha256": "5cdf8a7a76e683e2d15e79d3716db232897d6f2f47a0a04c66a3e1fa4e399f0c",
    "exposure_result_sha256": "79e691f5b17655935943ad2e4ae1cb784e1cc82d8a122c36cde8a5a385075a0b",
    "exposure_final_sha256": "6a7771ebd67f86cd55822563ee5cb71530d964c19a6a1667f0af4919a7e65dde",
}
BEHAVIOR_CLOSURE_PATHS = (
    ".github/workflows/ci.yml",
    ".github/workflows/g3a.yml",
    "CMakeLists.txt",
    "CMakePresets.json",
    "requirements/b0-dev.txt",
    "05_integration/b0/configs/b0_g0_contract.v2.json",
    "05_integration/b0/configs/b0_g3_rate_kp_x_study.v1.json",
    "05_integration/b0/validate_config.py",
    "05_integration/b0/runner.py",
    "05_integration/b0/scheduler.py",
    "05_integration/b0/events.py",
    "01_simulation/b0/__init__.py",
    "01_simulation/b0/contract.py",
    "01_simulation/b0/quaternion.py",
    "01_simulation/b0/plant.py",
    "01_simulation/b0/actuator.py",
    "01_simulation/b0/imu.py",
    "02_estimation/b0/estimator.py",
    "02_estimation/b0/configs/b0_g2_estimator.v1.json",
    "02_estimation/b0/configs/b0_g2_estimator_approval.v1.json",
    "03_control/b0/CMakeLists.txt",
    "03_control/b0/include/b0_controller/controller.hpp",
    "03_control/b0/src/controller.cpp",
    "03_control/b0/python/controller_bindings.cpp",
    "03_control/b0/python/controller.py",
    "03_control/b0/configs/b0_g2_controller.v1.json",
    "03_control/b0/configs/b0_g2_controller_approval.v1.json",
    "docs/work_orders/B0_PR11_v2_G1_closeout.md",
    "systems_engineering/reports/b0/g0_approval_decision.md",
    "systems_engineering/reports/b0/g2a_validation_record.md",
    "systems_engineering/reports/b0/g2b_validation_record.md",
    "systems_engineering/reports/b0/g3_s0_integration_design.md",
    "systems_engineering/reports/b0/g3_s0_verification_matrix.md",
)
CONTROLLER_BUILD_INPUT_PATHS = (
    "CMakeLists.txt",
    "CMakePresets.json",
    "requirements/b0-dev.txt",
    "03_control/b0/CMakeLists.txt",
    "03_control/b0/include/b0_controller/controller.hpp",
    "03_control/b0/src/controller.cpp",
    "03_control/b0/python/controller_bindings.cpp",
)


class RunnerContractError(ValueError):
    """Raised when the smoke runner cannot preserve an approved contract."""


@dataclass(frozen=True, init=False)
class AttitudeCommand:
    _q_nb_command: np.ndarray
    timestamp_s: float
    valid: bool

    def __init__(self, q_nb_command: Any, timestamp_s: float, valid: bool) -> None:
        q = np.asarray(q_nb_command, dtype=np.float64)
        if q.shape != (4,) or not np.all(np.isfinite(q)):
            raise RunnerContractError("q_nb_command must be a finite length-four vector")
        if abs(float(np.linalg.norm(q)) - 1.0) > 1e-12:
            raise RunnerContractError("q_nb_command must be a unit quaternion")
        if not isinstance(valid, bool):
            raise RunnerContractError("command validity must be boolean")
        object.__setattr__(self, "_q_nb_command", q.copy())
        object.__setattr__(self, "timestamp_s", float(timestamp_s))
        object.__setattr__(self, "valid", valid)

    @property
    def q_nb_command(self) -> np.ndarray:
        return self._q_nb_command.copy()


def _prepend_import_path(path: Path) -> None:
    value = str(path.resolve())
    if value not in sys.path:
        sys.path.insert(0, value)


def _load_simulation_package():
    package_root = (REPO_ROOT / "01_simulation").resolve()
    expected = package_root / "b0/__init__.py"
    loaded = sys.modules.get("b0")
    if loaded is not None and Path(getattr(loaded, "__file__", "")).resolve() != expected:
        for name in tuple(sys.modules):
            if name == "b0" or name.startswith("b0."):
                sys.modules.pop(name, None)
    _prepend_import_path(package_root)
    package = importlib.import_module("b0")
    if Path(getattr(package, "__file__", "")).resolve() != expected:
        raise RunnerContractError("G1 public package identity does not match 01_simulation/b0")
    return package


def _load_python_file(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RunnerContractError(f"cannot load Python module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return module


def _load_controller_module(module_dir: Path):
    if not module_dir.is_absolute():
        raise RunnerContractError("module_dir must be absolute")
    if not module_dir.is_dir():
        raise RunnerContractError(f"controller module directory does not exist: {module_dir}")
    spec = importlib.machinery.PathFinder.find_spec("b0_controller", [str(module_dir)])
    if spec is None or spec.loader is None or spec.origin is None:
        raise RunnerContractError(f"b0_controller is unavailable in {module_dir}")
    origin = Path(spec.origin).resolve()
    if module_dir.resolve() not in origin.parents:
        raise RunnerContractError("resolved controller module escaped module_dir")
    loaded = sys.modules.get("b0_controller")
    if loaded is not None:
        loaded_path = Path(getattr(loaded, "__file__", "")).resolve()
        if loaded_path != origin:
            raise RunnerContractError(
                "a different b0_controller binary is already loaded in this process"
            )
        return loaded, origin
    module = importlib.util.module_from_spec(spec)
    sys.modules["b0_controller"] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop("b0_controller", None)
        raise
    return module, origin


def _validated_contract() -> dict[str, Any]:
    validator = _load_python_file("b0_g3_authoritative_validator", REPO_ROOT / "05_integration/b0/validate_config.py")
    contract = validator.load_config(G0_PATH)
    validator.validate_config(contract)
    return contract


def _qx(angle_rad: float) -> np.ndarray:
    return np.array(
        [math.cos(angle_rad / 2.0), math.sin(angle_rad / 2.0), 0.0, 0.0],
        dtype=np.float64,
    )


def _vector(value: Any) -> list[float]:
    return [float(item) for item in np.asarray(value, dtype=np.float64)]


def _canonical_lf_sha256(path: Path) -> str:
    normalized = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(normalized).hexdigest()


def _source_identity() -> str:
    status = subprocess.run(
        ["git", "status", "--porcelain", "--", *BEHAVIOR_CLOSURE_PATHS],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if status:
        raise RunnerContractError(
            "reachability diagnostic requires committed G3 execution sources"
        )
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _scenario(contract: dict[str, Any], scenario_id: str) -> dict[str, Any]:
    matches = [item for item in contract["scenarios"] if item["id"] == scenario_id]
    if len(matches) != 1:
        raise RunnerContractError(f"scenario identity is not unique: {scenario_id}")
    return matches[0]


def _write_exclusive_json(path: Path, value: dict[str, Any]) -> str:
    rendered = json.dumps(value, indent=2, sort_keys=True) + "\n"
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(rendered)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _git_file_bytes(source_commit: str, relative_path: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"{source_commit}:{relative_path}"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    ).stdout


def _file_identity(path: Path, source_commit: str) -> dict[str, Any]:
    relative_path = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    live_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    source_sha256 = hashlib.sha256(
        _git_file_bytes(source_commit, relative_path)
    ).hexdigest()
    return {
        "path": relative_path,
        "sha256": live_sha256,
        "source_sha256": source_sha256,
        "live_sha256": live_sha256,
        "live_matches_source": live_sha256 == source_sha256,
    }


def _authority_identity(
    source_commit: str, module_path: Path, build_type: str
) -> dict[str, Any]:
    files = [
        _file_identity(REPO_ROOT / relative_path, source_commit)
        for relative_path in BEHAVIOR_CLOSURE_PATHS
    ]
    if not all(item["live_matches_source"] for item in files):
        raise RunnerContractError("behavior closure does not match source commit")
    return {
        "schema_version": "b0-g3-authority-identity/v2",
        "source_commit": source_commit,
        "build_type": build_type,
        "controller_module_path": str(module_path),
        "controller_module_sha256": hashlib.sha256(module_path.read_bytes()).hexdigest(),
        "behavior_closure_complete": True,
        "controller_build_input_paths": list(CONTROLLER_BUILD_INPUT_PATHS),
        "files": files,
    }


def _acceptance_seed_provenance(executed_this_run: bool) -> dict[str, Any]:
    return {
        "acceptance_seed_executed_this_run": executed_this_run,
        "acceptance_seed_previously_exposed": ACCEPTANCE_SEED_HISTORY[
            "previously_exposed"
        ],
        "acceptance_seed_exposure_cumulative": (
            executed_this_run or ACCEPTANCE_SEED_HISTORY["previously_exposed"]
        ),
        "acceptance_seed_exposure_history": dict(ACCEPTANCE_SEED_HISTORY),
    }


def _reset_loop(
    simulation: Any,
    estimator_module: Any,
    plant: Any,
    actuator: Any,
    imu: Any,
    estimator: Any,
    controller: Any,
    plant_q_nb: Any,
    plant_omega_b_rad_s: Any,
    seed: int,
    epoch_id: int = 0,
    epoch_timestamp_s: float = 0.0,
) -> tuple[Any, Any]:
    class ControllerResetEpoch:
        id = epoch_id
        timestamp_s = epoch_timestamp_s

    held_command = controller.reset(ControllerResetEpoch())
    actuator_state = simulation.ActuatorInitialState(
        actual_torque_body_Nm=np.zeros(3),
        held_limited_torque_body_Nm=held_command.limited_torque_body_Nm,
        held_command_timestamp_s=held_command.timestamp_s,
        held_saturated=held_command.saturated,
        held_requested_torque_body_Nm=held_command.requested_torque_body_Nm,
    )
    actuator.reset(actuator_state, epoch_timestamp_s)
    plant.reset(
        simulation.PlantInitialState(plant_q_nb, plant_omega_b_rad_s),
        epoch_timestamp_s,
    )
    imu.reset(simulation.IMUInitialState(), epoch_timestamp_s, seed)
    estimator.reset(
        estimator_module.EstimatorInitialState(IDENTITY, np.zeros(3)),
        estimator_module.ResetEpoch(epoch_id, epoch_timestamp_s),
        seed,
    )
    return held_command, actuator.feedback


_VECTOR_PARAMETER_FIELDS = (
    "attitude_kp",
    "rate_kp",
    "rate_ki",
    "rate_kd",
    "integral_limit_Nm",
    "rate_limit_rad_s",
    "torque_limit_Nm",
    "kaw_limit_per_s",
    "kaw_lag_per_s",
)
_SCALAR_PARAMETER_FIELDS = (
    "derivative_time_constant_s",
    "controller_period_s",
    "timestamp_tolerance_s",
    "quaternion_norm_tolerance",
)


def _sealed_parameters(parameters: Any) -> dict[str, Any]:
    sealed = {
        field: [float(value) for value in getattr(parameters, field)]
        for field in _VECTOR_PARAMETER_FIELDS
    }
    sealed.update(
        {field: float(getattr(parameters, field)) for field in _SCALAR_PARAMETER_FIELDS}
    )
    return sealed


def _study_controller(
    adapter_module: Any, controller_module: Any, rate_kp_x: float
) -> tuple[Any, dict[str, Any]]:
    if not math.isfinite(rate_kp_x) or not 0.0 <= rate_kp_x <= 0.2:
        raise RunnerContractError("study rate_kp[0] must be finite and within [0,0.2]")
    accepted = adapter_module.load_controller_parameters(controller_module)
    parameters = controller_module.ControllerParameters()
    for field in _VECTOR_PARAMETER_FIELDS:
        setattr(parameters, field, list(getattr(accepted, field)))
    for field in _SCALAR_PARAMETER_FIELDS:
        setattr(parameters, field, float(getattr(accepted, field)))
    rate_kp = list(parameters.rate_kp)
    rate_kp[0] = rate_kp_x
    parameters.rate_kp = rate_kp
    sealed = _sealed_parameters(parameters)
    accepted_sealed = _sealed_parameters(accepted)
    changed = []
    for field in (*_VECTOR_PARAMETER_FIELDS, *_SCALAR_PARAMETER_FIELDS):
        if sealed[field] != accepted_sealed[field]:
            changed.append(field)
    if changed not in ([], ["rate_kp"]):
        raise RunnerContractError(f"study parameter whitelist violated: {changed}")
    if sealed["rate_kp"][1:] != accepted_sealed["rate_kp"][1:]:
        raise RunnerContractError("study changed a non-x rate Kp")
    adapter = object.__new__(adapter_module.ControllerAdapter)
    adapter.module = controller_module
    adapter.parameters = parameters
    adapter.core = controller_module.CascadedController(parameters)
    adapter.epoch_id = None
    adapter.g1_contract = adapter_module._load_g1_contract(REPO_ROOT)
    return adapter, sealed


def _run_g3_bind_smoke(module_dir: Path, build_type: str, seed: int) -> dict[str, Any]:
    if seed != TUNING_SEED:
        raise RunnerContractError("G3-BIND accepts only the approved tuning seed")
    if build_type not in {"Debug", "Release"}:
        raise RunnerContractError("build_type must be Debug or Release")
    if not module_dir.is_absolute():
        raise RunnerContractError("module_dir must be absolute")
    if not module_dir.is_dir():
        raise RunnerContractError(
            f"controller module directory does not exist: {module_dir}"
        )

    contract = _validated_contract()
    scheduler = IntegerScheduler.from_contract(contract)
    if scheduler.base_period_s != 0.0025:
        raise RunnerContractError("G3-BIND requires the approved 0.0025 s base period")

    simulation = _load_simulation_package()
    estimator_module = _load_python_file(
        "b0_g3_estimator", REPO_ROOT / "02_estimation/b0/estimator.py"
    )
    adapter_module = _load_python_file(
        "b0_g3_controller_adapter", REPO_ROOT / "03_control/b0/python/controller.py"
    )
    controller_module, module_path = _load_controller_module(module_dir.resolve())

    parameters = simulation.load_g1_parameters(G0_PATH)
    plant = simulation.Plant(parameters)
    actuator = simulation.Actuator(parameters)
    imu = simulation.IMU(parameters)
    estimator = estimator_module.AttitudeEstimator()
    controller = adapter_module.ControllerAdapter(controller_module)

    held_command, feedback = _reset_loop(
        simulation,
        estimator_module,
        plant,
        actuator,
        imu,
        estimator,
        controller,
        IDENTITY,
        np.zeros(3),
        seed,
    )
    call_counts = {name: 0 for name in ("plant", "actuator", "imu", "estimator", "controller")}
    records: list[dict[str, Any]] = []

    for local_tick in range(1, 13):
        due = scheduler.boundary(local_tick)
        previous_actual = feedback.actual_torque_body_Nm
        plant_state = plant.step_base(previous_actual)
        call_counts["plant"] += 1
        feedback = actuator.step_base(held_command)
        call_counts["actuator"] += 1
        record: dict[str, Any] = {
            "local_tick": local_tick,
            "timestamp_s": due.timestamp_s,
            "plant_updated": True,
            "actuator_updated": True,
            "imu_updated": False,
            "estimator_updated": False,
            "controller_updated": False,
            "plant_consumed_actual_torque_body_Nm": _vector(previous_actual),
            "actuator_command_timestamp_s": float(feedback.command_timestamp_s),
            "actual_torque_body_Nm": _vector(feedback.actual_torque_body_Nm),
        }
        if due.imu_due:
            truth = simulation.SensorTruth(
                plant_state.q_nb,
                plant_state.omega_b_rad_s,
                np.zeros(3),
            )
            sample = imu.sample(truth, due.timestamp_s)
            call_counts["imu"] += 1
            estimate = estimator.step(sample)
            call_counts["estimator"] += 1
            command_q = _qx(0.1) if 2 <= local_tick < 10 else IDENTITY
            command = AttitudeCommand(command_q, due.timestamp_s, True)
            held_command = controller.step(
                command,
                estimate,
                feedback,
                scheduler.controller_every_ticks * scheduler.base_period_s,
            )
            call_counts["controller"] += 1
            record.update(
                {
                    "imu_updated": True,
                    "estimator_updated": True,
                    "controller_updated": True,
                    "command_q_nb": _vector(command_q),
                    "estimate_q_nb": _vector(estimate.q_nb_estimate),
                    "estimate_omega_b_rad_s": _vector(estimate.omega_b_estimate_rad_s),
                    "requested_torque_body_Nm": _vector(
                        held_command.requested_torque_body_Nm
                    ),
                    "limited_torque_body_Nm": _vector(
                        held_command.limited_torque_body_Nm
                    ),
                    "saturated": [bool(value) for value in held_command.saturated],
                    "published_command_timestamp_s": float(held_command.timestamp_s),
                }
            )
        records.append(record)

    expected_counts = {
        "plant": 12,
        "actuator": 12,
        "imu": 6,
        "estimator": 6,
        "controller": 6,
    }
    if call_counts != expected_counts:
        raise RunnerContractError(
            f"G3-BIND call counts differ: {call_counts} != {expected_counts}"
        )
    if not any(
        abs(value) > 0.0
        for record in records
        for value in record.get("requested_torque_body_Nm", [])
    ):
        raise RunnerContractError("G3-BIND did not exercise a nonzero controller request")

    return {
        "check_id": "G3-BIND",
        "classification": "development_interface_smoke_not_acceptance",
        "build_type": build_type,
        "seed_kind": "tuning_seed",
        "seed": seed,
        "module_path": str(module_path),
        "module_sha256": hashlib.sha256(module_path.read_bytes()).hexdigest(),
        "call_counts": call_counts,
        "records": records,
    }


def run_g3_bind_smoke(module_dir: str | Path, build_type: str) -> dict[str, Any]:
    """Run the fixed 12-tick real-component fixture with the tuning seed."""

    return _run_g3_bind_smoke(Path(module_dir), build_type, TUNING_SEED)


def _run_saturation_profile(
    module_dir: str | Path,
    build_type: str,
    output_root: str | Path,
    run_id: str,
    *,
    seed: int,
    rate_kp_x: float | None,
    purpose: str,
    acceptance_exposure: bool,
    protocol_identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the frozen saturation template through one explicitly labelled profile."""

    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise RunnerContractError("run_id does not match the approved identity pattern")
    if build_type not in {"Debug", "Release"}:
        raise RunnerContractError("build_type must be Debug or Release")
    module_directory = Path(module_dir)
    if not module_directory.is_absolute() or not module_directory.is_dir():
        raise RunnerContractError("module_dir must be an existing absolute directory")
    root = Path(output_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    run_directory = root / run_id
    run_directory.mkdir(exist_ok=False)

    source_commit = _source_identity()
    contract = _validated_contract()
    scenario = _scenario(contract, "saturation_withdrawal")
    if scenario["seed"] != 2026100906:
        raise RunnerContractError("frozen saturation acceptance seed identity changed")
    if acceptance_exposure:
        if seed != scenario["seed"] or rate_kp_x is not None:
            raise RunnerContractError("acceptance diagnostic must use frozen seed and parameters")
    elif seed != TUNING_SEED or rate_kp_x is None:
        raise RunnerContractError("study profile requires tuning seed and explicit x rate Kp")
    scheduler = IntegerScheduler.from_contract(contract)
    events = EventSchedule(scenario["events"])
    controller_module, module_path = _load_controller_module(module_directory.resolve())
    module_hash = hashlib.sha256(module_path.read_bytes()).hexdigest()
    started_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    authority = _authority_identity(source_commit, module_path, build_type)
    start_record = {
        "schema_version": (
            "b0-g3-seed-exposure/v1"
            if acceptance_exposure
            else "b0-g3-tuning-run/v1"
        ),
        "acceptance_seed_exposed": _acceptance_seed_provenance(
            acceptance_exposure
        )["acceptance_seed_exposure_cumulative"],
        **_acceptance_seed_provenance(acceptance_exposure),
        "scenario_id": scenario["id"],
        "source_scenario_seed": scenario["seed"],
        "seed": seed,
        "seed_override": None if acceptance_exposure else TUNING_SEED,
        "purpose": purpose,
        "source_commit": source_commit,
        "g0_config_path": str(G0_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
        "g0_config_canonical_lf_sha256": _canonical_lf_sha256(G0_PATH),
        "module_path": str(module_path),
        "module_sha256": module_hash,
        "authority": authority,
        "build_type": build_type,
        "run_id": run_id,
        "protocol_identity": protocol_identity,
        "rate_kp_x": rate_kp_x,
        "started_at": started_at,
        "record_state": "started_before_execution",
    }
    start_name = "seed-exposure-start.json" if acceptance_exposure else "run-start.json"
    final_name = "seed-exposure-final.json" if acceptance_exposure else "run-final.json"
    result_name = (
        "reachability-result.json" if acceptance_exposure else "tuning-result.json"
    )
    start_hash = _write_exclusive_json(run_directory / start_name, start_record)

    result_path = run_directory / result_name
    final_path = run_directory / final_name
    try:
        simulation = _load_simulation_package()
        estimator_module = _load_python_file(
            "b0_g3_reachability_estimator",
            REPO_ROOT / "02_estimation/b0/estimator.py",
        )
        adapter_module = _load_python_file(
            "b0_g3_reachability_controller_adapter",
            REPO_ROOT / "03_control/b0/python/controller.py",
        )
        parameters = simulation.load_g1_parameters(G0_PATH)
        plant = simulation.Plant(parameters)
        actuator = simulation.Actuator(parameters)
        imu = simulation.IMU(parameters)
        estimator = estimator_module.AttitudeEstimator()
        if rate_kp_x is None:
            controller = adapter_module.ControllerAdapter(controller_module)
            sealed_parameters = _sealed_parameters(controller.parameters)
        else:
            controller, sealed_parameters = _study_controller(
                adapter_module, controller_module, rate_kp_x
            )
        held_command, feedback = _reset_loop(
            simulation,
            estimator_module,
            plant,
            actuator,
            imu,
            estimator,
            controller,
            scenario["initial_q_nb"],
            scenario["initial_body_rate_rad_s"],
            seed,
        )
        duration_ticks = round(float(scenario["duration_s"]) / scheduler.base_period_s)
        if duration_ticks != 2400:
            raise RunnerContractError("frozen saturation duration must be 2400 ticks")
        request_min = np.full(3, np.inf)
        request_max = np.full(3, -np.inf)
        publications: list[dict[str, Any]] = []
        saturated_publications: list[dict[str, Any]] = []
        saturated_intervals: list[dict[str, Any]] = []
        due_records: list[dict[str, Any]] = []
        limits = parameters.actuator_limits_Nm

        for global_tick in range(1, duration_ticks + 1):
            due = scheduler.boundary(global_tick)
            active = events.active_at(global_tick)
            previous_actual = feedback.actual_torque_body_Nm
            plant_input = previous_actual + active.external_torque_body_Nm
            plant_state = plant.step_base(plant_input)
            consumed = held_command
            feedback = actuator.step_base(consumed)
            recomputed_saturation = (
                np.abs(consumed.requested_torque_body_Nm) > limits
            )
            if not np.array_equal(recomputed_saturation, feedback.saturated):
                raise RunnerContractError("actuator saturation pairing mismatch")
            if np.any(recomputed_saturation):
                clipped_start = max(global_tick - 1, 200)
                clipped_end = min(global_tick, 1000)
                if clipped_end > clipped_start:
                    saturated_intervals.append(
                        {
                            "actuator_tick": global_tick,
                            "interval": [global_tick - 1, global_tick],
                            "clipped_interval": [clipped_start, clipped_end],
                            "axes": [bool(value) for value in recomputed_saturation],
                            "request_Nm": _vector(
                                consumed.requested_torque_body_Nm
                            ),
                            "limited_Nm": _vector(
                                consumed.limited_torque_body_Nm
                            ),
                            "command_timestamp_s": float(consumed.timestamp_s),
                        }
                    )
            if due.imu_due:
                raw_sample = imu.sample(
                    simulation.SensorTruth(
                        plant_state.q_nb,
                        plant_state.omega_b_rad_s,
                        np.zeros(3),
                    ),
                    due.timestamp_s,
                )
                gyro, force = events.adapt_measurement(
                    raw_sample.gyro_b_rad_s,
                    raw_sample.specific_force_b_m_s2,
                    active,
                    parameters.gyro_bias_rad_s,
                    parameters.accelerometer_bias_m_s2,
                )
                adapted_sample = simulation.IMUSample(
                    raw_sample.timestamp_s, gyro, force, raw_sample.valid
                )
                estimate = estimator.step(adapted_sample)
                command = AttitudeCommand(
                    active.command_q_nb, due.timestamp_s, True
                )
                held_command = controller.step(
                    command,
                    estimate,
                    feedback,
                    scheduler.controller_every_ticks * scheduler.base_period_s,
                )
                diagnostics = controller.core.last_diagnostics()
                if rate_kp_x is not None:
                    expected_proportional_x = (
                        rate_kp_x * diagnostics.rate_error_rad_s[0]
                    )
                    if abs(
                        diagnostics.proportional_Nm[0] - expected_proportional_x
                    ) > 1e-12:
                        raise RunnerContractError(
                            "study core did not use the sealed x rate Kp"
                        )
                    expected_request_x = (
                        diagnostics.proportional_Nm[0]
                        + diagnostics.integral_before_Nm[0]
                        + diagnostics.derivative_Nm[0]
                    )
                    if abs(held_command.requested_torque_body_Nm[0] - expected_request_x) > 1e-12:
                        raise RunnerContractError(
                            "study request failed the independent P+I+D invariant"
                        )
                request = held_command.requested_torque_body_Nm
                request_min = np.minimum(request_min, request)
                request_max = np.maximum(request_max, request)
                publication = {
                    "global_tick": global_tick,
                    "timestamp_s": due.timestamp_s,
                    "event_ids": list(active.event_ids),
                    "command_q_nb": _vector(active.command_q_nb),
                    "truth_q_nb": _vector(plant_state.q_nb),
                    "truth_omega_b_rad_s": _vector(plant_state.omega_b_rad_s),
                    "raw_imu_gyro_b_rad_s": _vector(raw_sample.gyro_b_rad_s),
                    "raw_imu_specific_force_b_m_s2": _vector(
                        raw_sample.specific_force_b_m_s2
                    ),
                    "adapted_imu_gyro_b_rad_s": _vector(gyro),
                    "adapted_imu_specific_force_b_m_s2": _vector(force),
                    "estimate_q_nb": _vector(estimate.q_nb_estimate),
                    "estimate_omega_b_rad_s": _vector(
                        estimate.omega_b_estimate_rad_s
                    ),
                    "request_Nm": _vector(request),
                    "limited_Nm": _vector(held_command.limited_torque_body_Nm),
                    "saturated": [bool(value) for value in held_command.saturated],
                    "feedback_actual_Nm": _vector(feedback.actual_torque_body_Nm),
                    "feedback_command_timestamp_s": float(
                        feedback.command_timestamp_s
                    ),
                    "integral_before_Nm": _vector(diagnostics.integral_before_Nm),
                    "integral_after_Nm": _vector(diagnostics.integral_after_Nm),
                    "proportional_Nm": _vector(diagnostics.proportional_Nm),
                    "derivative_Nm": _vector(diagnostics.derivative_Nm),
                    "limit_backcalculation_rate_Nm_s": _vector(
                        diagnostics.limit_backcalculation_rate_Nm_s
                    ),
                    "lag_backcalculation_rate_Nm_s": _vector(
                        diagnostics.lag_backcalculation_rate_Nm_s
                    ),
                }
                publications.append(publication)
                if any(publication["saturated"]):
                    saturated_publications.append(publication)
                due_records.append(publication)

        union_duration_s = sum(
            interval["clipped_interval"][1] - interval["clipped_interval"][0]
            for interval in saturated_intervals
        ) * scheduler.base_period_s
        result = {
            "schema_version": "b0-g3-saturation-reachability/v1",
            "classification": (
                "development_reachability_diagnostic_not_acceptance"
                if acceptance_exposure
                else "tuning_development_profile_not_acceptance"
            ),
            "scenario_id": scenario["id"],
            "source_scenario_seed": scenario["seed"],
            "seed": seed,
            "seed_override": None if acceptance_exposure else TUNING_SEED,
            "acceptance_seed_exposed": _acceptance_seed_provenance(
                acceptance_exposure
            )["acceptance_seed_exposure_cumulative"],
            **_acceptance_seed_provenance(acceptance_exposure),
            "source_commit": source_commit,
            "build_type": build_type,
            "module_path": str(module_path),
            "module_sha256": module_hash,
            "authority": authority,
            "protocol_identity": protocol_identity,
            "controller_parameters": sealed_parameters,
            "window_ticks": [200, 1000],
            "request_min_Nm": _vector(request_min),
            "request_max_Nm": _vector(request_max),
            "negative_limit_headroom_Nm": _vector(request_min + limits),
            "positive_limit_headroom_Nm": _vector(limits - request_max),
            "saturated_publications": saturated_publications,
            "saturated_intervals": saturated_intervals,
            "saturation_union_duration_s": union_duration_s,
            "required_minimum_s": 0.05,
            "reachability_status": (
                "triggered" if union_duration_s >= 0.05 else "valid_shortfall"
            ),
            "publication_count": len(publications),
            "due_records": due_records,
        }
        result_hash = _write_exclusive_json(result_path, result)
        final_record = {
            **start_record,
            "record_state": "finalized_after_execution",
            "seed_exposure_start_sha256": start_hash,
            "execution_status": "structurally_complete",
            "result_path": result_path.name,
            "result_sha256": result_hash,
            "completed_at": datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
        }
        _write_exclusive_json(final_path, final_record)
        return result
    except Exception as exc:
        failure_record = {
            **start_record,
            "record_state": "finalized_after_execution",
            "seed_exposure_start_sha256": start_hash,
            "execution_status": "execution_error_inconclusive",
            "result_path": None,
            "result_sha256": None,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "completed_at": datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
        }
        if not final_path.exists():
            _write_exclusive_json(final_path, failure_record)
        raise


def run_saturation_reachability(
    module_dir: str | Path,
    build_type: str,
    output_root: str | Path,
    run_id: str,
) -> dict[str, Any]:
    """Run the first frozen diagnostic with append-only seed exposure records."""

    return _run_saturation_profile(
        module_dir,
        build_type,
        output_root,
        run_id,
        seed=2026100906,
        rate_kp_x=None,
        purpose="reachability_diagnostic",
        acceptance_exposure=True,
    )


def run_rate_kp_x_study(
    protocol_path: str | Path,
    module_dir: str | Path,
    build_type: str,
    output_root: str | Path,
    study_id: str,
) -> dict[str, Any]:
    """Execute the predeclared tuning-seed-only x-rate-Kp feasibility set once."""

    if not RUN_ID_PATTERN.fullmatch(study_id):
        raise RunnerContractError("study_id does not match the approved identity pattern")
    protocol_file = Path(protocol_path).resolve()
    expected_protocol = (
        REPO_ROOT
        / "05_integration/b0/configs/b0_g3_rate_kp_x_study.v1.json"
    ).resolve()
    if protocol_file != expected_protocol:
        raise RunnerContractError("study requires the repository-controlled protocol")
    protocol = json.loads(protocol_file.read_text(encoding="utf-8"))
    if protocol.get("schema_version") != "b0-g3-rate-kp-x-study/v1":
        raise RunnerContractError("unsupported study protocol identity")
    budget = protocol["execution_budget"]
    candidates = budget["candidates_rate_kp_x"]
    if budget["maximum_runs"] != 8 or not 1 <= len(candidates) <= 8:
        raise RunnerContractError("study candidate budget exceeds PA authorization")
    if len(candidates) != len(set(candidates)) or 0.08 not in candidates:
        raise RunnerContractError("study candidates must be unique and include baseline")
    if protocol["profile"]["seed"] != TUNING_SEED:
        raise RunnerContractError("study protocol must use the tuning seed")
    source_commit = _source_identity()
    protocol_hash = hashlib.sha256(protocol_file.read_bytes()).hexdigest()
    protocol_identity = {
        "path": str(protocol_file.relative_to(REPO_ROOT)).replace("\\", "/"),
        "sha256": protocol_hash,
        "source_commit": source_commit,
    }
    study_root = Path(output_root).resolve() / study_id
    study_root.mkdir(parents=True, exist_ok=False)
    results: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates):
        value = float(candidate)
        candidate_id = f"{index + 1:02d}-kp-x-{value:.3f}".replace(".", "p")
        result = _run_saturation_profile(
            module_dir,
            build_type,
            study_root,
            candidate_id,
            seed=TUNING_SEED,
            rate_kp_x=value,
            purpose="rate_kp_x_feasibility_study",
            acceptance_exposure=False,
            protocol_identity=protocol_identity,
        )
        result_path = study_root / candidate_id / "tuning-result.json"
        results.append(
            {
                "candidate_index": index,
                "candidate_id": candidate_id,
                "rate_kp_x": value,
                "saturation_union_duration_s": result[
                    "saturation_union_duration_s"
                ],
                "feasible": result["saturation_union_duration_s"] >= 0.05,
                "result_sha256": hashlib.sha256(result_path.read_bytes()).hexdigest(),
                "parameter_sha256": hashlib.sha256(
                    json.dumps(
                        result["controller_parameters"],
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest(),
            }
        )
    feasible = [item for item in results if item["feasible"]]
    feasible.sort(key=lambda item: (abs(item["rate_kp_x"] - 0.08), item["rate_kp_x"]))
    summary = {
        "schema_version": "b0-g3-rate-kp-x-study-result/v1",
        "classification": "feasibility_only_not_parameter_acceptance",
        "study_id": study_id,
        "source_commit": source_commit,
        "protocol": protocol_identity,
        "build_type": build_type,
        "module_dir": str(Path(module_dir).resolve()),
        "seed": TUNING_SEED,
        "acceptance_seed_executed": False,
        "acceptance_seed_executed_this_run": False,
        "acceptance_seed_previously_exposed": True,
        "acceptance_seed_exposure_cumulative": True,
        "acceptance_seed_exposure_history": dict(ACCEPTANCE_SEED_HISTORY),
        "candidate_results": results,
        "feasible_candidate_count": len(feasible),
        "ranked_overlay_candidate": feasible[0] if feasible else None,
        "next_action": (
            "return_one_candidate_for_PARAMETER_ACCEPT_review"
            if feasible
            else "stop_and_return_no_feasible_candidate"
        ),
    }
    _write_exclusive_json(study_root / "study-summary.json", summary)
    return summary


def compare_g3_bind_results(
    debug: dict[str, Any], release: dict[str, Any]
) -> None:
    """Compare independently generated Debug and Release smoke results."""

    if debug.get("build_type") != "Debug" or release.get("build_type") != "Release":
        raise RunnerContractError("comparison requires Debug and Release results")
    if debug.get("module_path") == release.get("module_path"):
        raise RunnerContractError("Debug and Release module paths must differ")
    if debug.get("module_sha256") == release.get("module_sha256"):
        raise RunnerContractError("Debug and Release module hashes must differ")

    comparable_keys = (
        "check_id",
        "classification",
        "seed_kind",
        "seed",
        "call_counts",
        "records",
    )

    def compare(left: Any, right: Any, path: str) -> None:
        if isinstance(left, bool) or isinstance(right, bool):
            if not isinstance(left, bool) or not isinstance(right, bool) or left != right:
                raise RunnerContractError(f"boolean mismatch at {path}")
            return
        if isinstance(left, int) or isinstance(right, int):
            if not isinstance(left, int) or not isinstance(right, int) or left != right:
                raise RunnerContractError(f"integer mismatch at {path}")
            return
        if isinstance(left, float) or isinstance(right, float):
            if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
                raise RunnerContractError(f"numeric type mismatch at {path}")
            if not math.isfinite(float(left)) or not math.isfinite(float(right)):
                raise RunnerContractError(f"non-finite comparison value at {path}")
            tolerance = 1e-12 + 1e-12 * abs(float(right))
            if abs(float(left) - float(right)) > tolerance:
                raise RunnerContractError(f"floating mismatch at {path}")
            return
        if isinstance(left, dict) or isinstance(right, dict):
            if not isinstance(left, dict) or not isinstance(right, dict):
                raise RunnerContractError(f"mapping type mismatch at {path}")
            if set(left) != set(right):
                raise RunnerContractError(f"mapping key mismatch at {path}")
            for key in sorted(left):
                compare(left[key], right[key], f"{path}.{key}")
            return
        if isinstance(left, list) or isinstance(right, list):
            if not isinstance(left, list) or not isinstance(right, list):
                raise RunnerContractError(f"sequence type mismatch at {path}")
            if len(left) != len(right):
                raise RunnerContractError(f"sequence length mismatch at {path}")
            for index, (left_item, right_item) in enumerate(zip(left, right)):
                compare(left_item, right_item, f"{path}[{index}]")
            return
        if type(left) is not type(right) or left != right:
            raise RunnerContractError(f"value mismatch at {path}")

    for key in comparable_keys:
        if key not in debug or key not in release:
            raise RunnerContractError(f"missing comparison field: {key}")
        compare(debug[key], release[key], key)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--g3-bind-smoke", action="store_true")
    parser.add_argument("--reachability-diagnostic", action="store_true")
    parser.add_argument("--rate-kp-x-study", action="store_true")
    parser.add_argument("--module-dir", type=Path)
    parser.add_argument("--build-type", choices=("Debug", "Release"))
    parser.add_argument("--seed", type=int, default=TUNING_SEED)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--protocol", type=Path)
    args = parser.parse_args(argv)
    if sum(
        bool(value)
        for value in (
            args.g3_bind_smoke,
            args.reachability_diagnostic,
            args.rate_kp_x_study,
        )
    ) != 1:
        parser.error("select exactly one G3-A execution mode")
    if args.module_dir is None or args.build_type is None:
        parser.error("--module-dir and --build-type are required")
    if args.reachability_diagnostic:
        if args.seed != TUNING_SEED:
            parser.error("--seed is not accepted for the frozen reachability diagnostic")
        if args.output_root is None or args.run_id is None:
            parser.error("--output-root and --run-id are required")
        if args.output is not None:
            parser.error("--output is only valid with --g3-bind-smoke")
        result = run_saturation_reachability(
            args.module_dir,
            args.build_type,
            args.output_root,
            args.run_id,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if args.rate_kp_x_study:
        if args.seed != TUNING_SEED:
            parser.error("the study seed is fixed by its protocol")
        if args.output_root is None or args.run_id is None or args.protocol is None:
            parser.error("--output-root, --run-id and --protocol are required")
        if args.output is not None:
            parser.error("--output is only valid with --g3-bind-smoke")
        result = run_rate_kp_x_study(
            args.protocol,
            args.module_dir,
            args.build_type,
            args.output_root,
            args.run_id,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if args.output_root is not None or args.run_id is not None:
        parser.error("--output-root and --run-id require --reachability-diagnostic")
    result = _run_g3_bind_smoke(args.module_dir, args.build_type, args.seed)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output is None:
        print(rendered)
    else:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "RunnerContractError",
    "compare_g3_bind_results",
    "run_g3_bind_smoke",
    "run_rate_kp_x_study",
    "run_saturation_reachability",
]
