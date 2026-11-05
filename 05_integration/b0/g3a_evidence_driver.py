"""Fixed G3-A development evidence batch driver.

The runner lazy-loads this module.  This module never imports ``runner`` and has
no import-time DUT, NumPy, extension, filesystem-write, or execution side
effect.  The public entry point fixes the eight-profile order and seed; callers
cannot select a profile or seed.

The raw output is an author-owned observation record.  It is not an independent
oracle and does not make a performance, normal-scene, SIL, HIL, or flight claim.
Independent authority and checker policy remain external inputs.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.machinery
import importlib.util
import io
import json
import math
from contextlib import contextmanager
from pathlib import Path
import re
import sys
import sysconfig
from typing import Any, Callable, Iterator, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
G0_PATH = REPO_ROOT / "05_integration/b0/configs/b0_g0_contract.v2.json"
PROFILE_PATH = REPO_ROOT / "05_integration/b0/configs/g3a_evidence_profiles.v1.json"
SESSION_PATH = REPO_ROOT / "05_integration/b0/integration_session.py"
PROFILE_ORDER = ("S", "L1", "L2", "O1", "O2", "E", "T1", "T2")
SEED = 2026100900
EVIDENCE_VERSION = "b0-g3a-evidence/v1"
PROFILE_VERSION = "b0-g3a-profile-definition/v1"
AUTHORITY_VERSION = "b0-g3a-authority/v1"
CLASSIFICATION = "development_integration_not_normal_acceptance"
RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
SHA256_PATTERN = re.compile(r"[0-9A-Fa-f]{64}")
GIT_SHA1_PATTERN = re.compile(r"[0-9A-Fa-f]{40}")

COUNT_KEYS = (
    "plant_step_base",
    "actuator_step_base",
    "imu_sample",
    "estimator_process",
    "estimator_accepted",
    "estimator_rejected",
    "controller_step",
    "controller_accepted",
    "controller_rejected",
    "plant_reset",
    "actuator_reset",
    "imu_reset",
    "estimator_reset",
    "controller_reset",
    "plant_constructor",
    "actuator_constructor",
    "imu_constructor",
    "estimator_constructor",
    "controller_adapter_constructor",
    "controller_core_constructor",
    "old_epoch_rejected",
    "needs_reset_rejected",
    "truth_negative_rejected",
)
COMPONENT_COUNT_KEYS = COUNT_KEYS[:20]

_SESSION_COUNTER_TO_EVIDENCE = {
    "plant_reset_attempts": "plant_reset",
    "actuator_reset_attempts": "actuator_reset",
    "imu_reset_attempts": "imu_reset",
    "estimator_reset_attempts": "estimator_reset",
    "controller_reset_attempts": "controller_reset",
    "plant_step_attempts": "plant_step_base",
    "actuator_step_attempts": "actuator_step_base",
    "imu_sample_attempts": "imu_sample",
    "estimator_process_attempts": "estimator_process",
    "estimator_process_accepted": "estimator_accepted",
    "estimator_process_rejected": "estimator_rejected",
    "controller_step_attempts": "controller_step",
    "controller_step_accepted": "controller_accepted",
    "controller_step_rejected": "controller_rejected",
}

_CONSTRUCTOR_OWNER_TO_EVIDENCE = {
    "plant": "plant_constructor",
    "actuator": "actuator_constructor",
    "imu": "imu_constructor",
    "estimator": "estimator_constructor",
    "controller": "controller_adapter_constructor",
    "controller_core": "controller_core_constructor",
}

CONVENTIONS = {
    "navigation_frame": "NED",
    "body_frame": "FRD",
    "quaternion": "scalar_first_Hamilton_q_nb_body_to_NED",
    "time": "s",
    "angular_rate": "rad/s",
    "angular_acceleration": "rad/s2",
    "torque": "Nm",
    "torque_rate": "Nm/s",
    "specific_force": "m/s2",
    "inertia": "kg*m2",
}

_IDENTITY_KEYS = (
    "work_order_sha256",
    "source_commit",
    "source_tree",
    "source_closure_manifest_sha256",
    "config_approval_manifest_sha256",
    "profile_definition_sha256",
    "parameter_inputs_manifest_sha256",
    "observer_manifest_sha256",
    "environment_manifest_sha256",
    "f0_manifest_sha256",
    "controller_module_path",
    "controller_module_sha256",
    "controller_module_abi",
    "build_type",
    "seed",
    "classification",
)


class EvidenceDriverError(RuntimeError):
    """Fail-closed batch preparation, execution, or recording failure."""

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        message = reason if not detail else f"{reason}: {detail}"
        super().__init__(message)


def _duplicate_reject(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceDriverError("duplicate_json_key", key)
        result[key] = value
    return result


def _nonstandard_constant(token: str) -> None:
    raise EvidenceDriverError("nonstandard_json_number", token)


def _json_bytes(payload: bytes, source: Path) -> Any:
    try:
        return json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_duplicate_reject,
            parse_constant=_nonstandard_constant,
        )
    except EvidenceDriverError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise EvidenceDriverError("invalid_json", f"{source}: {exc}") from exc


def _json(path: Path) -> Any:
    try:
        return _json_bytes(path.read_bytes(), path)
    except OSError as exc:
        raise EvidenceDriverError("input_unavailable", f"{path}: {exc}") from exc


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8") + b"\n"


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256(path: Path) -> str:
    try:
        return _sha256_bytes(path.read_bytes())
    except OSError as exc:
        raise EvidenceDriverError("input_unavailable", f"{path}: {exc}") from exc


def _write_bytes_exclusive(path: Path, payload: bytes) -> str:
    try:
        with path.open("xb") as stream:
            stream.write(payload)
    except OSError as exc:
        raise EvidenceDriverError("artifact_write_failed", f"{path}: {exc}") from exc
    return _sha256_bytes(payload)


def _write_json_exclusive(path: Path, value: Any) -> str:
    return _write_bytes_exclusive(path, _canonical_json_bytes(value))


def _require_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise EvidenceDriverError("field_type_mismatch", f"{name} must be an object")
    return value


def _require_internal_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise EvidenceDriverError("field_type_mismatch", f"{name} must be a mapping")
    return value


def _require_sha256(value: Any, name: str) -> str:
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        raise EvidenceDriverError("authority_invalid", f"{name} must be SHA-256")
    return value.lower()


def _require_git_sha1(value: Any, name: str) -> str:
    if not isinstance(value, str) or GIT_SHA1_PATTERN.fullmatch(value) is None:
        raise EvidenceDriverError("authority_invalid", f"{name} must be Git SHA-1")
    return value.lower()


def _hex(value: Any) -> str:
    if isinstance(value, bool):
        raise EvidenceDriverError("float_encoding_invalid", "boolean supplied as float")
    try:
        converted = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise EvidenceDriverError("float_encoding_invalid", str(value)) from exc
    if not math.isfinite(converted):
        raise EvidenceDriverError("float_encoding_invalid", "non-finite signal")
    # Python's binary64 float.hex() already emits the schema's fixed 13 digits.
    return converted.hex()


def _sequence(value: Any, length: int, name: str) -> list[Any]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, (tuple, list)) or len(value) != length:
        raise EvidenceDriverError("field_type_mismatch", f"{name} must have length {length}")
    return list(value)


def _vec(value: Any, length: int, name: str) -> list[str]:
    return [_hex(item) for item in _sequence(value, length, name)]


def _flags(value: Any, name: str) -> list[bool]:
    result = _sequence(value, 3, name)
    if any(not isinstance(item, bool) for item in result):
        # np.bool_ is intentionally normalized by bool only after exact 0/1 test.
        normalized = [bool(item) for item in result]
        if any(item not in (0, 1, False, True) for item in result):
            raise EvidenceDriverError("field_type_mismatch", f"{name} must be booleans")
        return normalized
    return result


def _load_python_file(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise EvidenceDriverError("module_unavailable", str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return module


def _prepend_import_path(path: Path) -> None:
    value = str(path.resolve())
    if value not in sys.path:
        sys.path.insert(0, value)


def _load_simulation_package() -> Any:
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
        raise EvidenceDriverError("module_identity_mismatch", "01_simulation/b0")
    return package


def _load_controller_module(module_dir: Path) -> tuple[Any, Path]:
    spec = importlib.machinery.PathFinder.find_spec("b0_controller", [str(module_dir)])
    if spec is None or spec.loader is None or spec.origin is None:
        raise EvidenceDriverError("module_unavailable", f"b0_controller in {module_dir}")
    origin = Path(spec.origin).resolve()
    if module_dir not in origin.parents:
        raise EvidenceDriverError("module_identity_mismatch", "controller escaped module_dir")
    loaded = sys.modules.get("b0_controller")
    if loaded is not None:
        if Path(getattr(loaded, "__file__", "")).resolve() != origin:
            raise EvidenceDriverError("module_identity_mismatch", "different controller already loaded")
        return loaded, origin
    module = importlib.util.module_from_spec(spec)
    sys.modules["b0_controller"] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop("b0_controller", None)
        raise
    return module, origin


def _find_controller_module_path(module_dir: Path) -> Path:
    spec = importlib.machinery.PathFinder.find_spec("b0_controller", [str(module_dir)])
    if spec is None or spec.loader is None or spec.origin is None:
        raise EvidenceDriverError("module_unavailable", f"b0_controller in {module_dir}")
    origin = Path(spec.origin).resolve()
    if module_dir not in origin.parents:
        raise EvidenceDriverError("module_identity_mismatch", "controller escaped module_dir")
    return origin


def _load_dependencies(
    module_dir: Path,
    *,
    session_module: Any,
    support: _LifecycleSupport,
) -> dict[str, Any]:
    """Load concrete dependencies without importing the legacy runner."""

    # G0 is the first observed dependency transaction.  The caller already
    # owns ``support``; completing this ledger before later imports means any
    # subsequent import failure can retain the one authoritative G0 read and
    # validation without rerunning either call.
    validator = _load_python_file(
        "b0_g3a_validator", REPO_ROOT / "05_integration/b0/validate_config.py"
    )
    _wrap_validator_module(
        validator,
        REPO_ROOT / "05_integration/b0/validate_config.py",
        support,
        load_callsite="g3a_evidence_driver.g0.load_config",
        validate_callsite="g3a_evidence_driver.g0.validate_config",
    )
    contract = validator.load_config(G0_PATH)
    validator.validate_config(contract)
    scheduler_module = _load_python_file(
        "b0_g3a_scheduler", REPO_ROOT / "05_integration/b0/scheduler.py"
    )
    events_module = _load_python_file(
        "b0_g3a_events", REPO_ROOT / "05_integration/b0/events.py"
    )
    simulation = _load_simulation_package()
    estimator = _load_python_file(
        "b0_g3a_estimator", REPO_ROOT / "02_estimation/b0/estimator.py"
    )
    adapter = _load_python_file(
        "b0_g3a_controller_adapter", REPO_ROOT / "03_control/b0/python/controller.py"
    )
    controller, module_path = _load_controller_module(module_dir)
    return {
        "scheduler_module": scheduler_module,
        "events_module": events_module,
        "session_module": session_module,
        "contract": contract,
        "simulation": simulation,
        "estimator_module": estimator,
        "adapter_module": adapter,
        "controller_module": controller,
        "controller_module_path": module_path,
        "lifecycle_support": support,
    }


def _validate_definition(value: Any) -> Mapping[str, Any]:
    definition = _require_mapping(value, "profile definition")
    if definition.get("schema_version") != PROFILE_VERSION:
        raise EvidenceDriverError("profile_identity_mismatch", "schema_version")
    if definition.get("evidence_schema_version") != EVIDENCE_VERSION:
        raise EvidenceDriverError("profile_identity_mismatch", "evidence_schema_version")
    if definition.get("seed") != SEED or definition.get("profile_order") != list(PROFILE_ORDER):
        raise EvidenceDriverError("profile_identity_mismatch", "fixed seed/profile order")
    profiles = definition.get("profiles")
    if not isinstance(profiles, list) or [item.get("profile_id") for item in profiles if isinstance(item, dict)] != list(PROFILE_ORDER):
        raise EvidenceDriverError("profile_identity_mismatch", "profile catalogue")
    return definition


def _validate_authority(
    value: Any,
    *,
    profile_sha256: str,
    module_path: Path,
    build_type: str,
) -> Mapping[str, Any]:
    authority = _require_mapping(value, "authority")
    if authority.get("authority_version") != AUTHORITY_VERSION:
        raise EvidenceDriverError("authority_invalid", "authority_version")
    identity = _require_mapping(authority.get("identity"), "authority.identity")
    if set(identity) != set(_IDENTITY_KEYS):
        raise EvidenceDriverError("authority_invalid", "identity key set")
    for field in (
        "work_order_sha256",
        "source_closure_manifest_sha256",
        "config_approval_manifest_sha256",
        "profile_definition_sha256",
        "parameter_inputs_manifest_sha256",
        "observer_manifest_sha256",
        "environment_manifest_sha256",
        "f0_manifest_sha256",
        "controller_module_sha256",
    ):
        _require_sha256(identity.get(field), f"authority.identity.{field}")
    _require_git_sha1(identity.get("source_commit"), "authority.identity.source_commit")
    _require_git_sha1(identity.get("source_tree"), "authority.identity.source_tree")
    actual_abi = sysconfig.get_config_var("SOABI") or sys.implementation.cache_tag
    actual_module_sha256 = _sha256(module_path)
    expected = {
        "profile_definition_sha256": profile_sha256,
        "controller_module_path": str(module_path),
        "controller_module_sha256": actual_module_sha256,
        "controller_module_abi": actual_abi,
        "build_type": build_type,
        "seed": SEED,
        "classification": CLASSIFICATION,
    }
    for field, actual in expected.items():
        declared = identity.get(field)
        if field.endswith("sha256") and isinstance(declared, str):
            declared = declared.lower()
        if declared != actual:
            raise EvidenceDriverError(
                "authority_identity_mismatch", f"{field}: {declared!r} != {actual!r}"
            )
    _authority_auxiliary_keys(authority)
    return authority


def _authority_auxiliary_keys(
    authority: Mapping[str, Any],
) -> dict[str, tuple[str, ...]]:
    """Return only the PA-plan counter key set, never its expected values.

    Planned values are independent-checker expectations and must not be used to
    manufacture author observations.  The key set is nevertheless required so
    a genuinely unobserved, planned zero counter is serialized explicitly.
    """

    plan = _require_mapping(authority.get("execution_plan"), "execution_plan")
    if plan.get("plan_version") != "b0-g3a-execution-plan/v1":
        raise EvidenceDriverError("authority_invalid", "execution_plan.plan_version")
    auxiliary = _require_mapping(
        plan.get("auxiliary_counts"), "execution_plan.auxiliary_counts"
    )
    if set(auxiliary) != set(PROFILE_ORDER):
        raise EvidenceDriverError(
            "authority_invalid", "execution_plan auxiliary profile set"
        )
    result: dict[str, tuple[str, ...]] = {}
    for profile_id in PROFILE_ORDER:
        counters = _require_mapping(
            auxiliary[profile_id],
            f"execution_plan.auxiliary_counts.{profile_id}",
        )
        keys: list[str] = []
        for key, expected_value in counters.items():
            if (
                not isinstance(key, str)
                or not key
                or isinstance(expected_value, bool)
                or not isinstance(expected_value, int)
                or expected_value < 0
            ):
                raise EvidenceDriverError(
                    "authority_invalid",
                    f"execution_plan auxiliary counter {profile_id}:{key!r}",
                )
            if key == "operation:actuator:step":
                pass
            elif key.startswith("lifecycle:"):
                suffix = key[len("lifecycle:") :]
                site, separator, event = suffix.rpartition(":")
                if not separator or not site or event not in {
                    "enter", "return", "exception"
                }:
                    raise EvidenceDriverError(
                        "authority_invalid", f"auxiliary lifecycle key {key}"
                    )
            elif key.startswith("guard:"):
                suffix = key[len("guard:") :]
                if ":" not in suffix or not all(suffix.rsplit(":", 1)):
                    raise EvidenceDriverError(
                        "authority_invalid", f"auxiliary guard key {key}"
                    )
            else:
                raise EvidenceDriverError(
                    "authority_invalid", f"auxiliary counter key {key}"
                )
            keys.append(key)
        result[profile_id] = tuple(sorted(keys))
    return result


def _profile(definition: Mapping[str, Any], profile_id: str) -> Mapping[str, Any]:
    matches = [item for item in definition["profiles"] if item["profile_id"] == profile_id]
    if len(matches) != 1:
        raise EvidenceDriverError("profile_identity_mismatch", profile_id)
    return matches[0]


def _events_for_profile(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for declared in profile.get("events", []):
        event = {
            key: value
            for key, value in declared.items()
            if key not in {"event_id", "source_locator"}
        }
        event["id"] = declared["event_id"]
        if event["type"] == "command_step":
            event["post_event_action"] = "return_axis_to_zero"
        events.append(event)
    for fault in profile.get("faults", []):
        if fault["kind"] == "controller_negative_dt":
            events.append(
                {
                    "id": f"{profile['profile_id']}_invalid_negative_dt",
                    "type": "invalid_input",
                    "invalid_kind": "negative_dt",
                    "start_tick": fault["global_tick"],
                    "end_tick": fault["global_tick"] + 1,
                }
            )
        elif fault["kind"] == "estimator_stale_timestamp":
            events.append(
                {
                    "id": f"{profile['profile_id']}_invalid_stale_timestamp",
                    "type": "invalid_input",
                    "invalid_kind": "stale_timestamp",
                    "start_tick": fault["global_tick"],
                    "end_tick": fault["global_tick"] + 1,
                }
            )
    for reset_tick in profile.get("reset_ticks", [])[1:]:
        events.append(
            {
                "id": f"{profile['profile_id']}_reset_{reset_tick}",
                "type": "reset",
                "target": "all_components",
                "start_tick": reset_tick,
                "end_tick": reset_tick + 1,
            }
        )
    events.sort(key=lambda item: (item["start_tick"], item["id"]))
    return events


def _hamilton(left: Any, right: Any, np: Any) -> Any:
    lw, lx, ly, lz = left
    rw, rx, ry, rz = right
    return np.array(
        [
            lw * rw - lx * rx - ly * ry - lz * rz,
            lw * rx + lx * rw + ly * rz - lz * ry,
            lw * ry - lx * rz + ly * rw + lz * rx,
            lw * rz + lx * ry - ly * rx + lz * rw,
        ],
        dtype=np.float64,
    )


def _axis_quaternion(axis: str, angle: float, np: Any) -> Any:
    half = 0.5 * angle
    vector = {
        "x": [math.cos(half), math.sin(half), 0.0, 0.0],
        "y": [math.cos(half), 0.0, math.sin(half), 0.0],
        "z": [math.cos(half), 0.0, 0.0, math.sin(half)],
    }[axis]
    return np.array(vector, dtype=np.float64)


def _offset_quaternion(angles_rad: Sequence[Any], np: Any) -> Any:
    roll, pitch, yaw = _sequence(angles_rad, 3, "attitude_offset_rad")
    result = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)
    for axis, angle in zip(("x", "y", "z"), (roll, pitch, yaw), strict=True):
        result = _hamilton(result, _axis_quaternion(axis, float(angle), np), np)
    return result


def _plant_offset_q(definition: Mapping[str, Any], np: Any) -> Any:
    return _offset_quaternion(
        definition["initial_inputs"]["plant_only_attitude_offset_rad"], np
    )


def _plant_profile_initial_q(
    profile_id: str, definition: Mapping[str, Any], np: Any
) -> Any:
    """Return the literal profile initialization, not observed plant truth.

    The approved plant-only offset belongs to E.  S/L/O and the two sealed
    E/C replays retain the identity plant input; T2 applies the same offset
    only to its separate evaluator-owned truth copy.
    """

    if profile_id == "E":
        return _plant_offset_q(definition, np)
    return np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)


def _command_factory(np: Any) -> Callable[[Any, float, bool], Any]:
    class AttitudeCommand:
        def __init__(self, q_nb_command: Any, timestamp_s: float, valid: bool) -> None:
            self._q_nb_command = np.asarray(q_nb_command, dtype=np.float64).copy()
            self.timestamp_s = float(timestamp_s)
            self.valid = bool(valid)

        @property
        def q_nb_command(self) -> Any:
            return self._q_nb_command.copy()

    return AttitudeCommand


def _matrix3(value: Any, name: str) -> list[list[str]]:
    rows = _sequence(value, 3, name)
    return [_vec(row, 3, f"{name}[{index}]") for index, row in enumerate(rows)]


def _json_value_digest(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _sha256_bytes(payload)


def _relative_artifact(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _lifecycle_result(
    *,
    actor_id: str | None = None,
    parameter_object_ref: str | None = None,
    snapshot_ref: str | None = None,
    capture_id: str | None = None,
    resolved_config_path: str | None = None,
    source_bytes_sha256: str | None = None,
    document_sha256: str | None = None,
) -> dict[str, Any]:
    """Build the schema's fixed seven-field lifecycle return value."""

    return {
        "actor_id": actor_id,
        "parameter_object_ref": parameter_object_ref,
        "snapshot_ref": snapshot_ref,
        "capture_id": capture_id,
        "resolved_config_path": resolved_config_path,
        "source_bytes_sha256": source_bytes_sha256,
        "document_sha256": document_sha256,
    }


class _ActorRegistry:
    """Allocate stable audit identities without exposing object addresses."""

    def __init__(self) -> None:
        self._sequence = 0

    def new(self, profile_id: str | None, role: str) -> str:
        self._sequence += 1
        prefix = "setup" if profile_id is None else profile_id
        return f"{prefix}/actor/{role}/{self._sequence}"


class _ParameterRegistry:
    """Detach actual parameter values at each real consuming boundary."""

    _CONTROLLER_VECTOR_FIELDS = (
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
    _CONTROLLER_SCALAR_FIELDS = (
        "derivative_time_constant_s",
        "controller_period_s",
        "timestamp_tolerance_s",
        "quaternion_norm_tolerance",
    )

    def __init__(self) -> None:
        self._sequence = 0
        self._entries: list[dict[str, Any]] = []

    @staticmethod
    def values(kind: str, value: Any) -> dict[str, Any]:
        if kind == "g1":
            return {
                "inertia_kg_m2": _matrix3(value.inertia_kg_m2, "inertia_kg_m2"),
                "actuator_time_constant_s": _hex(value.actuator_time_constant_s),
                "actuator_limits_Nm": _vec(value.actuator_limits_Nm, 3, "actuator_limits_Nm"),
                "gravity_n_m_s2": _vec(value.gravity_n_m_s2, 3, "gravity_n_m_s2"),
                "gyro_noise_std_rad_s": _vec(value.gyro_noise_std_rad_s, 3, "gyro_noise_std_rad_s"),
                "gyro_bias_rad_s": _vec(value.gyro_bias_rad_s, 3, "gyro_bias_rad_s"),
                "accelerometer_noise_std_m_s2": _vec(
                    value.accelerometer_noise_std_m_s2,
                    3,
                    "accelerometer_noise_std_m_s2",
                ),
                "accelerometer_bias_m_s2": _vec(
                    value.accelerometer_bias_m_s2,
                    3,
                    "accelerometer_bias_m_s2",
                ),
                "base_period_s": _hex(value.base_period_s),
                "imu_period_ticks": int(value.imu_period_ticks),
                "config_path": str(value.config_path),
            }
        if kind == "estimator":
            return {
                "sample_period_s": _hex(value.sample_period_s),
                "gravity_m_s2": _hex(value.gravity_m_s2),
                "unit_norm_tolerance": _hex(value.unit_norm_tolerance),
                "correction_gain_per_s": _hex(value.correction_gain_per_s),
                "accelerometer_gate_deviation_m_s2": _hex(
                    value.accelerometer_gate_deviation_m_s2
                ),
                "maximum_correction_step_rad": _hex(value.maximum_correction_step_rad),
                "timestamp_tolerance_s": _hex(value.timestamp_tolerance_s),
                "config_path": str(value.config_path),
                "g0_config_path": str(value.g0_config_path),
            }
        if kind == "controller":
            result = {
                field: _vec(getattr(value, field), 3, field)
                for field in _ParameterRegistry._CONTROLLER_VECTOR_FIELDS
            }
            result.update(
                {
                    field: _hex(getattr(value, field))
                    for field in _ParameterRegistry._CONTROLLER_SCALAR_FIELDS
                }
            )
            return result
        raise EvidenceDriverError("unknown_parameter_kind", kind)

    def capture(
        self,
        kind: str,
        value: Any,
        *,
        capture_kind: str = "object_values",
    ) -> tuple[str, str]:
        if capture_kind not in {"object_values", "constructor_fields"}:
            raise EvidenceDriverError("invalid_parameter_capture_kind", capture_kind)
        values = self.values(kind, value)
        return self.capture_values(kind, values, capture_kind=capture_kind)

    def capture_values(
        self,
        kind: str,
        values: Mapping[str, Any],
        *,
        capture_kind: str,
    ) -> tuple[str, str]:
        if kind not in {"g1", "estimator", "controller"}:
            raise EvidenceDriverError("unknown_parameter_kind", kind)
        if capture_kind not in {"object_values", "constructor_fields"}:
            raise EvidenceDriverError("invalid_parameter_capture_kind", capture_kind)
        detached = json.loads(
            json.dumps(
                dict(values),
                ensure_ascii=True,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        self._sequence += 1
        identifier = f"parameter/{kind}/{self._sequence}"
        digest = _json_value_digest(detached)
        self._entries.append(
            {
                "parameter_object_id": identifier,
                "kind": kind,
                "capture_kind": capture_kind,
                "values_sha256": digest,
                "values": detached,
            }
        )
        return identifier, digest

    @property
    def entries(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(json.loads(json.dumps(item)) for item in self._entries)


class _LifecycleSupport:
    """Shared lifecycle, actor and actual-parameter observation support."""

    def __init__(self, recorder: Any) -> None:
        self.recorder = recorder
        self.actors = _ActorRegistry()
        self.parameters = _ParameterRegistry()
        self.document_sources: dict[int, tuple[str, str, str, str]] = {}

    @staticmethod
    def constructor_arguments(
        mode: str,
        *,
        parameter_object_ref: str | None,
        module_sha256: str | None,
    ) -> dict[str, Any]:
        return {
            "kind": "constructor",
            "mode": mode,
            "parameter_object_ref": parameter_object_ref,
            "module_sha256": module_sha256,
        }

    def observe_constructor(
        self,
        *,
        profile_id: str | None,
        owner: str,
        role: str,
        callsite: str,
        mode: str,
        parameter_object_ref: str | None,
        module_sha256: str | None,
        core_use: str | None,
        call: Callable[[], Any],
        result_parameter_ref: Callable[[Any], str | None] | None = None,
    ) -> tuple[Any, str]:
        actor_id = self.actors.new(profile_id, role)
        token = self.recorder.begin(
            profile_id=profile_id,
            operation_id=None,
            owner=owner,
            method="constructor",
            callsite=callsite,
            actor_id=actor_id,
            core_use=core_use,
            arguments=self.constructor_arguments(
                mode,
                parameter_object_ref=parameter_object_ref,
                module_sha256=module_sha256,
            ),
        )
        try:
            result = call()
        except Exception as exc:
            self.recorder.raised(token, exc)
            raise
        returned_parameter = (
            None if result_parameter_ref is None else result_parameter_ref(result)
        )
        self.recorder.returned(
            token,
            result=_lifecycle_result(
                actor_id=actor_id,
                parameter_object_ref=returned_parameter,
            ),
        )
        return result, actor_id


class _ValidatorLoaderProxy:
    """Wrap each freshly loaded authoritative validator before first use."""

    def __init__(
        self,
        delegate: Any,
        support: _LifecycleSupport,
        validator_path: Path,
    ) -> None:
        self._delegate = delegate
        self._support = support
        self._validator_path = validator_path.resolve()

    def create_module(self, spec: Any) -> Any:
        creator = getattr(self._delegate, "create_module", None)
        return None if creator is None else creator(spec)

    def exec_module(self, module: Any) -> None:
        self._delegate.exec_module(module)
        _wrap_validator_module(module, self._validator_path, self._support)


@contextmanager
def _captured_config_read(
    path: Path, payload: bytes
) -> Iterator[dict[str, int]]:
    """Make the authoritative loader consume the one captured byte image.

    ``validate_config.load_config`` owns JSON decoding and duplicate/nonfinite
    rejection.  This narrowly scoped adapter changes neither of those paths: it
    replaces only the successful text open of the exact captured path with a
    text view over the bytes already hashed for the lifecycle record.  Thus the
    digest and parsed document describe one filesystem read, not a provenance
    pre-read followed by a second, potentially different, loader read.
    """

    resolved = path.resolve()
    path_type = type(resolved)
    inherited_open = path_type.open
    had_direct_open = "open" in path_type.__dict__
    state = {"open_count": 0}

    def captured_open(
        candidate: Any,
        mode: str = "r",
        buffering: int = -1,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> Any:
        candidate_path = Path(candidate).resolve()
        if candidate_path != resolved:
            return inherited_open(
                candidate, mode, buffering, encoding, errors, newline
            )
        if mode not in {"r", "rt"} or state["open_count"] != 0:
            raise EvidenceDriverError(
                "config_source_consumption_mismatch",
                f"{resolved}: mode={mode!r}, opens={state['open_count']}",
            )
        state["open_count"] += 1
        codec = "utf-8" if encoding is None else encoding
        error_policy = "strict" if errors is None else errors
        text = payload.decode(codec, errors=error_policy)
        return io.StringIO(text, newline=newline)

    def restore_open() -> None:
        if had_direct_open:
            setattr(path_type, "open", inherited_open)
        else:
            delattr(path_type, "open")

    setattr(path_type, "open", captured_open)
    try:
        yield state
    except BaseException as primary:
        try:
            restore_open()
        except Exception as restoration:
            primary.add_note(
                "failed to restore Path.open after authoritative config read: "
                f"{type(restoration).__name__}: {restoration}"
            )
        raise
    else:
        restore_open()


def _wrap_validator_module(
    module: Any,
    validator_path: Path,
    support: _LifecycleSupport,
    *,
    load_callsite: str = "validate_config.load_config",
    validate_callsite: str = "validate_config.validate_config",
) -> None:
    original_load = module.load_config
    original_validate = module.validate_config
    actor_id = support.actors.new(None, "g0-validator")

    def observed_load(config_path: Any) -> Any:
        path = Path(config_path).resolve()
        try:
            payload = path.read_bytes()
        except OSError:
            token = support.recorder.begin(
                profile_id=None,
                operation_id=None,
                owner="g0_validator",
                method="load_config",
                callsite=load_callsite,
                actor_id=actor_id,
                core_use=None,
                arguments={
                    "kind": "config",
                    "actual_argument_kind": "path",
                    "path_argument": str(path),
                    "source_artifact_ref": _relative_artifact(path),
                    "source_bytes_sha256": None,
                    "document_sha256": None,
                },
            )
            try:
                original_load(config_path)
            except Exception as exc:
                support.recorder.raised(token, exc)
                raise
            support.recorder.returned(
                token,
                result=_lifecycle_result(
                    actor_id=actor_id,
                    resolved_config_path=str(path),
                ),
            )
            raise EvidenceDriverError(
                "config_source_observation_unavailable",
                f"{path}: initial authoritative capture failed but loader returned",
            )
        source_sha = _sha256_bytes(payload)
        source_ref = _relative_artifact(path)
        token = support.recorder.begin(
            profile_id=None,
            operation_id=None,
            owner="g0_validator",
            method="load_config",
            callsite=load_callsite,
            actor_id=actor_id,
            core_use=None,
            arguments={
                "kind": "config",
                "actual_argument_kind": "path",
                "path_argument": str(path),
                "source_artifact_ref": source_ref,
                "source_bytes_sha256": source_sha,
                "document_sha256": None,
            },
        )
        try:
            with _captured_config_read(path, payload) as consumption:
                document = original_load(config_path)
            if consumption["open_count"] != 1:
                raise EvidenceDriverError(
                    "config_source_consumption_mismatch",
                    f"{path}: authoritative opens={consumption['open_count']}",
                )
        except Exception as exc:
            support.recorder.raised(token, exc)
            raise
        document_sha = _json_value_digest(document)
        support.document_sources[id(document)] = (
            source_ref,
            str(path),
            source_sha,
            document_sha,
        )
        support.recorder.returned(
            token,
            result=_lifecycle_result(
                actor_id=actor_id,
                resolved_config_path=str(path),
                source_bytes_sha256=source_sha,
                document_sha256=document_sha,
            ),
        )
        return document

    def observed_validate(document: Any) -> Any:
        document_sha = _json_value_digest(document)
        source = support.document_sources.get(id(document))
        source_ref = None if source is None else source[0]
        resolved_path = None if source is None else source[1]
        source_sha = None if source is None else source[2]
        token = support.recorder.begin(
            profile_id=None,
            operation_id=None,
            owner="g0_validator",
            method="validate_config",
            callsite=validate_callsite,
            actor_id=actor_id,
            core_use=None,
            arguments={
                "kind": "config",
                "actual_argument_kind": "document",
                "path_argument": None,
                "source_artifact_ref": source_ref,
                "source_bytes_sha256": source_sha,
                "document_sha256": document_sha,
            },
        )
        try:
            result = original_validate(document)
        except Exception as exc:
            support.recorder.raised(token, exc)
            raise
        support.recorder.returned(
            token,
            result=_lifecycle_result(
                actor_id=actor_id,
                resolved_config_path=resolved_path,
                source_bytes_sha256=source_sha,
                document_sha256=document_sha,
            ),
        )
        return result

    module.load_config = observed_load
    module.validate_config = observed_validate


@contextmanager
def _observe_dynamic_validators(
    support: _LifecycleSupport,
) -> Iterator[None]:
    original = importlib.util.spec_from_file_location
    validator_path = (REPO_ROOT / "05_integration/b0/validate_config.py").resolve()

    def observed_spec(name: str, location: Any, *args: Any, **kwargs: Any) -> Any:
        spec = original(name, location, *args, **kwargs)
        try:
            resolved = Path(location).resolve()
        except (TypeError, ValueError, OSError):
            return spec
        if (
            resolved == validator_path
            and spec is not None
            and spec.loader is not None
            and not isinstance(spec.loader, _ValidatorLoaderProxy)
        ):
            spec.loader = _ValidatorLoaderProxy(spec.loader, support, resolved)
        return spec

    importlib.util.spec_from_file_location = observed_spec
    try:
        yield
    finally:
        importlib.util.spec_from_file_location = original


def _python_module_sha256(value: Any) -> str | None:
    module_name = getattr(value, "__module__", None)
    module = None if module_name is None else sys.modules.get(module_name)
    filename = None if module is None else getattr(module, "__file__", None)
    if filename is None:
        return None
    path = Path(filename)
    try:
        return _sha256(path.resolve())
    except OSError:
        return None


def _parameter_field_values(kind: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
    """Encode actual keyword fields before a parameter-data constructor call."""

    if kind == "g1":
        return {
            "inertia_kg_m2": _matrix3(arguments["inertia_kg_m2"], "inertia_kg_m2"),
            "actuator_time_constant_s": _hex(arguments["actuator_time_constant_s"]),
            "actuator_limits_Nm": _vec(arguments["actuator_limits_Nm"], 3, "actuator_limits_Nm"),
            "gravity_n_m_s2": _vec(arguments["gravity_n_m_s2"], 3, "gravity_n_m_s2"),
            "gyro_noise_std_rad_s": _vec(arguments["gyro_noise_std_rad_s"], 3, "gyro_noise_std_rad_s"),
            "gyro_bias_rad_s": _vec(arguments["gyro_bias_rad_s"], 3, "gyro_bias_rad_s"),
            "accelerometer_noise_std_m_s2": _vec(
                arguments["accelerometer_noise_std_m_s2"],
                3,
                "accelerometer_noise_std_m_s2",
            ),
            "accelerometer_bias_m_s2": _vec(
                arguments["accelerometer_bias_m_s2"],
                3,
                "accelerometer_bias_m_s2",
            ),
            "base_period_s": _hex(arguments["base_period_s"]),
            "imu_period_ticks": int(arguments["imu_period_ticks"]),
            "config_path": str(arguments.get("config_path", "<explicit>")),
        }
    if kind == "estimator":
        return {
            "sample_period_s": _hex(arguments["sample_period_s"]),
            "gravity_m_s2": _hex(arguments["gravity_m_s2"]),
            "unit_norm_tolerance": _hex(arguments["unit_norm_tolerance"]),
            "correction_gain_per_s": _hex(arguments["correction_gain_per_s"]),
            "accelerometer_gate_deviation_m_s2": _hex(
                arguments["accelerometer_gate_deviation_m_s2"]
            ),
            "maximum_correction_step_rad": _hex(arguments["maximum_correction_step_rad"]),
            "timestamp_tolerance_s": _hex(arguments["timestamp_tolerance_s"]),
            "config_path": str(arguments["config_path"]),
            "g0_config_path": str(arguments["g0_config_path"]),
        }
    raise EvidenceDriverError("unsupported_parameter_constructor", kind)


@contextmanager
def _observe_parameter_class(
    module: Any,
    attribute: str,
    *,
    kind: str,
    owner: str,
    callsite: str,
    support: _LifecycleSupport,
) -> Iterator[None]:
    original = getattr(module, attribute)
    module_sha = _python_module_sha256(original)

    def observed(*args: Any, **kwargs: Any) -> Any:
        if args:
            raise EvidenceDriverError(
                "parameter_constructor_shape_changed",
                f"{callsite} received positional fields",
            )
        field_values = _parameter_field_values(kind, kwargs)
        field_ref, _ = support.parameters.capture_values(
            kind,
            field_values,
            capture_kind="constructor_fields",
        )
        actor_id = support.actors.new(None, owner)
        token = support.recorder.begin(
            profile_id=None,
            operation_id=None,
            owner=owner,
            method="constructor",
            callsite=callsite,
            actor_id=actor_id,
            core_use=None,
            arguments=support.constructor_arguments(
                "parameter_fields",
                parameter_object_ref=field_ref,
                module_sha256=module_sha,
            ),
        )
        try:
            result = original(**kwargs)
        except Exception as exc:
            support.recorder.raised(token, exc)
            raise
        object_ref, _ = support.parameters.capture(kind, result)
        support.recorder.returned(
            token,
            result=_lifecycle_result(
                actor_id=actor_id,
                parameter_object_ref=object_ref,
            ),
        )
        return result

    setattr(module, attribute, observed)
    try:
        yield
    finally:
        setattr(module, attribute, original)


def _loader_arguments(
    *,
    supplied_args: Sequence[str],
    config_path: Any = None,
    track: Any = None,
    module_sha256: str | None = None,
) -> dict[str, Any]:
    if isinstance(supplied_args, (str, bytes)):
        raise EvidenceDriverError(
            "loader_arguments_invalid", "supplied_args must be a sequence of names"
        )
    supplied = list(supplied_args)
    allowed = {"config_path", "track", "module"}
    if (
        any(type(item) is not str or item not in allowed for item in supplied)
        or len(set(supplied)) != len(supplied)
    ):
        raise EvidenceDriverError(
            "loader_arguments_invalid", repr(supplied)
        )
    arguments: dict[str, Any] = {
        "kind": "loader",
        "supplied_args": supplied,
    }
    # The distinction between an omitted optional argument and an explicitly
    # supplied null is part of the lifecycle record.  Add only fields named by
    # supplied_args (module is represented by its immutable byte digest).
    if "config_path" in supplied:
        arguments["config_path"] = (
            None if config_path is None else str(Path(config_path).resolve())
        )
    if "track" in supplied:
        arguments["track"] = (
            None if track is None else str(Path(track).resolve())
        )
    if "module" in supplied:
        arguments["module_sha256"] = module_sha256
    return arguments


def _load_g1_parameters_observed(
    simulation: Any,
    support: _LifecycleSupport,
) -> tuple[Any, str, str]:
    loader = simulation.load_g1_parameters
    contract_module = sys.modules[loader.__module__]
    actor_id = support.actors.new(None, "g1-loader")
    token = support.recorder.begin(
        profile_id=None,
        operation_id=None,
        owner="g1_loader",
        method="load_parameters",
        callsite="b0.contract.load_g1_parameters",
        actor_id=actor_id,
        core_use=None,
        arguments=_loader_arguments(
            supplied_args=("config_path",),
            config_path=G0_PATH,
        ),
    )
    try:
        with _observe_parameter_class(
            contract_module,
            "G1Parameters",
            kind="g1",
            owner="g1_parameters",
            callsite="b0.contract.G1Parameters",
            support=support,
        ), _observe_dynamic_validators(support):
            result = loader(G0_PATH)
    except Exception as exc:
        support.recorder.raised(token, exc)
        raise
    parameter_ref, parameter_sha = support.parameters.capture("g1", result)
    support.recorder.returned(
        token,
        result=_lifecycle_result(
            actor_id=actor_id,
            parameter_object_ref=parameter_ref,
        ),
    )
    return result, parameter_ref, parameter_sha


class _ControllerCoreProxy:
    """Transparent production-core proxy which observes the real nested reset."""

    def __init__(
        self,
        core: Any,
        *,
        actor_id: str,
        support: _LifecycleSupport,
    ) -> None:
        self._core = core
        self._actor_id = actor_id
        self._support = support

    def reset(self, initial_state: Any, reset_epoch: Any) -> Any:
        reset_inputs = {
            "kind": "reset",
            "actor": "controller_core",
            "initial_state": {},
            "reset_epoch": {
                "id": int(reset_epoch.id),
                "timestamp_s": _hex(reset_epoch.timestamp_s),
            },
        }
        token = self._support.recorder.begin(
            profile_id=None,
            operation_id=None,
            owner="controller_core",
            method="reset",
            callsite="ControllerAdapter.reset.core.reset",
            actor_id=self._actor_id,
            core_use="production",
            arguments=reset_inputs,
        )
        try:
            result = self._core.reset(initial_state, reset_epoch)
        except Exception as exc:
            self._support.recorder.raised(token, exc)
            raise
        self._support.recorder.returned(
            token,
            result=_lifecycle_result(actor_id=self._actor_id),
        )
        return result

    def step(self, *args: Any, **kwargs: Any) -> Any:
        return self._core.step(*args, **kwargs)

    def snapshot(self) -> Any:
        return self._core.snapshot()

    def last_diagnostics(self) -> Any:
        return self._core.last_diagnostics()


class _ControllerModuleProxy:
    """Observe actual parameter/core constructors without changing their calls."""

    def __init__(
        self,
        module: Any,
        *,
        profile_id: str,
        module_sha256: str,
        support: _LifecycleSupport,
    ) -> None:
        self._module = module
        self._profile_id = profile_id
        self._module_sha256 = module_sha256
        self._support = support
        self._core_use = "production"

    def __getattr__(self, name: str) -> Any:
        return getattr(self._module, name)

    def ControllerParameters(self) -> Any:  # noqa: N802 - mirrors pybind API
        actor_id = self._support.actors.new(self._profile_id, "controller-parameters")
        token = self._support.recorder.begin(
            profile_id=self._profile_id,
            operation_id=None,
            owner="controller_parameters",
            method="constructor",
            callsite="b0_controller.ControllerParameters",
            actor_id=actor_id,
            core_use=None,
            arguments=self._support.constructor_arguments(
                "empty",
                parameter_object_ref=None,
                module_sha256=self._module_sha256,
            ),
        )
        try:
            result = self._module.ControllerParameters()
        except Exception as exc:
            self._support.recorder.raised(token, exc)
            raise
        self._support.recorder.returned(
            token,
            result=_lifecycle_result(actor_id=actor_id),
        )
        return result

    def CascadedController(self, parameters: Any) -> Any:  # noqa: N802
        parameter_ref, _ = self._support.parameters.capture("controller", parameters)
        actor_id = self._support.actors.new(self._profile_id, "controller-core")
        token = self._support.recorder.begin(
            profile_id=self._profile_id,
            operation_id=None,
            owner="controller_core",
            method="constructor",
            callsite="b0_controller.CascadedController",
            actor_id=actor_id,
            core_use=self._core_use,
            arguments=self._support.constructor_arguments(
                "explicit_parameters",
                parameter_object_ref=parameter_ref,
                module_sha256=self._module_sha256,
            ),
        )
        try:
            core = self._module.CascadedController(parameters)
        except Exception as exc:
            self._support.recorder.raised(token, exc)
            raise
        self._support.recorder.returned(
            token,
            result=_lifecycle_result(actor_id=actor_id),
        )
        if self._core_use == "production":
            return _ControllerCoreProxy(
                core,
                actor_id=actor_id,
                support=self._support,
            )
        return core


def _construct_estimator(
    profile_id: str,
    estimator_module: Any,
    support: _LifecycleSupport,
    *,
    shared_parameters: Any | None,
) -> tuple[Any, str, Any, str, str]:
    """Construct one real estimator, observing its sole default loader call."""

    original_loader = estimator_module.load_estimator_parameters
    loaded: dict[str, Any] = {}

    def observed_loader(*args: Any, **kwargs: Any) -> Any:
        if len(args) > 1 or any(key != "config_path" for key in kwargs):
            raise EvidenceDriverError("estimator_loader_shape_changed")
        supplied = []
        config_path = None
        if args:
            supplied.append("config_path")
            config_path = args[0]
        elif "config_path" in kwargs:
            supplied.append("config_path")
            config_path = kwargs["config_path"]
        actor_id = support.actors.new(profile_id, "estimator-loader")
        token = support.recorder.begin(
            profile_id=profile_id,
            operation_id=None,
            owner="estimator_loader",
            method="load_parameters",
            callsite="estimator.load_estimator_parameters",
            actor_id=actor_id,
            core_use=None,
            arguments=_loader_arguments(
                supplied_args=supplied,
                config_path=config_path,
            ),
        )
        try:
            with _observe_parameter_class(
                estimator_module,
                "EstimatorParameters",
                kind="estimator",
                owner="estimator_parameters",
                callsite="estimator.EstimatorParameters",
                support=support,
            ), _observe_dynamic_validators(support):
                result = original_loader(*args, **kwargs)
        except Exception as exc:
            support.recorder.raised(token, exc)
            raise
        parameter_ref, parameter_sha = support.parameters.capture(
            "estimator", result
        )
        loaded.update(
            {
                "parameters": result,
                "parameter_ref": parameter_ref,
                "parameter_sha": parameter_sha,
            }
        )
        support.recorder.returned(
            token,
            result=_lifecycle_result(
                actor_id=actor_id,
                parameter_object_ref=parameter_ref,
            ),
        )
        return result

    if shared_parameters is None:
        mode = "default_loader"
        input_ref = None
    else:
        mode = "explicit_parameters"
        input_ref, _ = support.parameters.capture("estimator", shared_parameters)
    actor_id = support.actors.new(profile_id, "estimator")
    token = support.recorder.begin(
        profile_id=profile_id,
        operation_id=None,
        owner="estimator",
        method="constructor",
        callsite="estimator.AttitudeEstimator",
        actor_id=actor_id,
        core_use=None,
        arguments=support.constructor_arguments(
            mode,
            parameter_object_ref=input_ref,
            module_sha256=_python_module_sha256(estimator_module.AttitudeEstimator),
        ),
    )
    estimator_module.load_estimator_parameters = observed_loader
    try:
        estimator = (
            estimator_module.AttitudeEstimator()
            if shared_parameters is None
            else estimator_module.AttitudeEstimator(shared_parameters)
        )
    except Exception as exc:
        support.recorder.raised(token, exc)
        raise
    finally:
        estimator_module.load_estimator_parameters = original_loader
    actual_parameters = estimator._parameters
    output_ref, output_sha = support.parameters.capture(
        "estimator", actual_parameters
    )
    support.recorder.returned(
        token,
        result=_lifecycle_result(
            actor_id=actor_id,
            parameter_object_ref=output_ref,
        ),
    )
    if shared_parameters is None:
        if loaded.get("parameters") is not actual_parameters:
            raise EvidenceDriverError("estimator_loader_binding_mismatch", profile_id)
        output_sha = str(loaded["parameter_sha"])
    return estimator, actor_id, actual_parameters, output_ref, output_sha


def _construct_controller(
    profile_id: str,
    adapter_module: Any,
    controller_module: Any,
    controller_module_sha256: str,
    support: _LifecycleSupport,
) -> tuple[Any, str, str, str]:
    """Construct one adapter through its unmodified loader/core call graph."""

    proxy = _ControllerModuleProxy(
        controller_module,
        profile_id=profile_id,
        module_sha256=controller_module_sha256,
        support=support,
    )
    original_loader = adapter_module.load_controller_parameters
    loaded: dict[str, Any] = {}

    def observed_loader(*args: Any, **kwargs: Any) -> Any:
        if len(args) > 2 or any(key not in {"module", "track"} for key in kwargs):
            raise EvidenceDriverError("controller_loader_shape_changed")
        supplied: list[str] = []
        module_arg = None
        track_arg = None
        if args:
            supplied.append("module")
            module_arg = args[0]
        elif "module" in kwargs:
            supplied.append("module")
            module_arg = kwargs["module"]
        if len(args) == 2:
            supplied.append("track")
            track_arg = args[1]
        elif "track" in kwargs:
            supplied.append("track")
            track_arg = kwargs["track"]
        if module_arg is not proxy:
            raise EvidenceDriverError("controller_loader_module_mismatch", profile_id)
        actor_id = support.actors.new(profile_id, "controller-loader")
        token = support.recorder.begin(
            profile_id=profile_id,
            operation_id=None,
            owner="controller_loader",
            method="load_parameters",
            callsite="controller.load_controller_parameters",
            actor_id=actor_id,
            core_use=None,
            arguments=_loader_arguments(
                supplied_args=supplied,
                track=track_arg,
                module_sha256=controller_module_sha256,
            ),
        )
        proxy._core_use = "temporary_validation"
        try:
            with _observe_dynamic_validators(support):
                parameters = original_loader(*args, **kwargs)
        except Exception as exc:
            support.recorder.raised(token, exc)
            raise
        finally:
            proxy._core_use = "production"
        parameter_ref, parameter_sha = support.parameters.capture(
            "controller", parameters
        )
        loaded.update(
            {
                "parameters": parameters,
                "parameter_ref": parameter_ref,
                "parameter_sha": parameter_sha,
            }
        )
        support.recorder.returned(
            token,
            result=_lifecycle_result(
                actor_id=actor_id,
                parameter_object_ref=parameter_ref,
            ),
        )
        return parameters

    actor_id = support.actors.new(profile_id, "controller")
    token = support.recorder.begin(
        profile_id=profile_id,
        operation_id=None,
        owner="controller",
        method="constructor",
        callsite="controller.ControllerAdapter",
        actor_id=actor_id,
        core_use=None,
        arguments=support.constructor_arguments(
            "controller_module",
            parameter_object_ref=None,
            module_sha256=controller_module_sha256,
        ),
    )
    adapter_module.load_controller_parameters = observed_loader
    try:
        adapter = adapter_module.ControllerAdapter(proxy)
    except Exception as exc:
        support.recorder.raised(token, exc)
        raise
    finally:
        adapter_module.load_controller_parameters = original_loader
    parameters = loaded.get("parameters")
    if parameters is None or adapter.parameters is not parameters:
        raise EvidenceDriverError("controller_loader_binding_mismatch", profile_id)
    output_ref, output_sha = support.parameters.capture("controller", parameters)
    support.recorder.returned(
        token,
        result=_lifecycle_result(
            actor_id=actor_id,
            parameter_object_ref=output_ref,
        ),
    )
    return adapter, actor_id, output_ref, output_sha


def _construct_g1_component(
    profile_id: str,
    owner: str,
    component_type: Any,
    parameters: Any,
    support: _LifecycleSupport,
) -> tuple[Any, str, str]:
    parameter_ref, parameter_sha = support.parameters.capture("g1", parameters)
    component, actor_id = support.observe_constructor(
        profile_id=profile_id,
        owner=owner,
        role=owner,
        callsite=f"b0.{component_type.__name__}",
        mode="explicit_parameters",
        parameter_object_ref=parameter_ref,
        module_sha256=_python_module_sha256(component_type),
        core_use=None,
        call=lambda: component_type(parameters),
        result_parameter_ref=lambda _result: parameter_ref,
    )
    return component, actor_id, parameter_sha


def _diagnostics_estimator(value: Any) -> dict[str, Any]:
    return {
        "accepted": bool(value.accepted),
        "reason": str(value.reason),
        "correction_eligible": bool(value.correction_eligible),
        "correction_applied": bool(value.correction_applied),
        "correction_capped": bool(value.correction_capped),
        "elapsed_periods": int(value.elapsed_periods),
        "missing_periods": int(value.missing_periods),
        "gap_approximated": bool(value.gap_approximated),
    }


def _diagnostics_controller(value: Any) -> dict[str, Any]:
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
    result = {
        field: _vec(getattr(value, field), 3, field) for field in vector_fields
    }
    result.update(
        {
            "accepted": bool(value.accepted),
            "reason": str(value.reason),
            "saturated": _flags(value.saturated, "saturated"),
            "epoch_id": int(value.epoch_id),
            "tick_index": int(value.tick_index),
        }
    )
    return result


def _plant_state(value: Any) -> dict[str, Any]:
    return {
        "q_nb": _vec(value.q_nb, 4, "plant.q_nb"),
        "omega_b_rad_s": _vec(value.omega_b_rad_s, 3, "plant.omega_b_rad_s"),
        "timestamp_s": _hex(value.timestamp_s),
    }


def _sensor_truth(value: Any) -> dict[str, Any]:
    return {
        "q_nb": _vec(value.q_nb, 4, "truth.q_nb"),
        "omega_b_rad_s": _vec(value.omega_b_rad_s, 3, "truth.omega_b_rad_s"),
        "translational_acceleration_n_m_s2": _vec(
            value.acceleration_n_m_s2,
            3,
            "truth.acceleration_n_m_s2",
        ),
    }


def _torque_command(value: Any) -> dict[str, Any]:
    return {
        "requested_torque_body_Nm": _vec(
            value.requested_torque_body_Nm, 3, "requested_torque_body_Nm"
        ),
        "limited_torque_body_Nm": _vec(
            value.limited_torque_body_Nm, 3, "limited_torque_body_Nm"
        ),
        "saturated": _flags(value.saturated, "saturated"),
        "timestamp_s": _hex(value.timestamp_s),
    }


def _feedback(value: Any) -> dict[str, Any]:
    return {
        "actual_torque_body_Nm": _vec(
            value.actual_torque_body_Nm, 3, "actual_torque_body_Nm"
        ),
        "limited_torque_body_Nm": _vec(
            value.limited_torque_body_Nm, 3, "limited_torque_body_Nm"
        ),
        "saturated": _flags(value.saturated, "saturated"),
        "timestamp_s": _hex(value.timestamp_s),
        "command_timestamp_s": _hex(value.command_timestamp_s),
    }


def _imu_sample(value: Any) -> dict[str, Any]:
    return {
        "gyro_rad_s": _vec(value.gyro_b_rad_s, 3, "gyro_b_rad_s"),
        "specific_force_m_s2": _vec(
            value.specific_force_b_m_s2, 3, "specific_force_b_m_s2"
        ),
        "timestamp_s": _hex(value.timestamp_s),
        "valid": bool(value.valid),
    }


def _estimate(value: Any) -> dict[str, Any]:
    return {
        "q_nb": _vec(value.q_nb_estimate, 4, "estimate.q_nb"),
        "omega_b_rad_s": _vec(
            value.omega_b_estimate_rad_s, 3, "estimate.omega_b_rad_s"
        ),
        "timestamp_s": _hex(value.timestamp_s),
        "valid": bool(value.valid),
    }


def _attitude_command(value: Any) -> dict[str, Any]:
    return {
        "q_nb": _vec(value.q_nb_command, 4, "command.q_nb"),
        "timestamp_s": _hex(value.timestamp_s),
        "valid": bool(value.valid),
    }


def _epoch(value: Any) -> dict[str, Any]:
    return {"id": int(value.id), "timestamp_s": _hex(value.timestamp_s)}


def _core_torque_command(value: Any) -> dict[str, Any]:
    return {
        "epoch_id": int(value.epoch_id),
        "requested_torque_body_Nm": _vec(
            value.requested_torque_body_Nm,
            3,
            "core.expected_held_command.requested_torque_body_Nm",
        ),
        "limited_torque_body_Nm": _vec(
            value.limited_torque_body_Nm,
            3,
            "core.expected_held_command.limited_torque_body_Nm",
        ),
        "saturated": _flags(
            value.saturated, "core.expected_held_command.saturated"
        ),
        "timestamp_s": _hex(value.timestamp_s),
    }


def _core_snapshot(value: Any) -> dict[str, Any]:
    return {
        "reset": bool(value.reset),
        "epoch_id": int(value.epoch_id),
        "tick_index": int(value.tick_index),
        "epoch_origin_s": _hex(value.epoch_origin_s),
        "expected_timestamp_s": _hex(value.expected_timestamp_s),
        "integral_Nm": _vec(value.integral_Nm, 3, "controller.integral_Nm"),
        "derivative_filtered_rad_s2": _vec(
            value.derivative_filtered_rad_s2,
            3,
            "controller.derivative_filtered_rad_s2",
        ),
        "previous_rate_rad_s": _vec(
            value.previous_rate_rad_s, 3, "controller.previous_rate_rad_s"
        ),
        "has_previous_rate": bool(value.has_previous_rate),
        "expected_held_command": _core_torque_command(
            value.expected_held_command
        ),
        "last_diagnostics": _diagnostics_controller(value.last_diagnostics),
    }


def _controller_snapshot(controller: Any) -> dict[str, Any]:
    parameters = _ParameterRegistry.values("controller", controller.parameters)
    return {
        "adapter_epoch_id": (
            None if controller.epoch_id is None else int(controller.epoch_id)
        ),
        "parameter_binding_sha256": _json_value_digest(parameters),
        "adapter_parameter_values": parameters,
        "snapshot": _core_snapshot(controller.core.snapshot()),
    }


def _snapshot_observer(session: Any) -> Mapping[str, Any]:
    """Read the version-bound complete functional state without mutation."""

    plant = session.plant
    actuator = session.actuator
    imu = session.imu
    estimator = session.estimator
    plant_values = _ParameterRegistry.values("g1", plant.parameters)
    actuator_values = _ParameterRegistry.values("g1", actuator.parameters)
    imu_values = _ParameterRegistry.values("g1", imu.parameters)
    estimator_values = _ParameterRegistry.values(
        "estimator", estimator._parameters
    )
    return {
        "session": session.functional_state(),
        "plant": {
            "_state": None if plant._state is None else _plant_state(plant._state),
            "_last_reset_epoch": (
                None
                if plant._last_reset_epoch is None
                else _hex(plant._last_reset_epoch)
            ),
            "_epoch_origin_s": (
                None if plant._epoch_origin_s is None else _hex(plant._epoch_origin_s)
            ),
            "_local_tick": int(plant._local_tick),
            "_mode": plant._mode,
            "_inertia": _matrix3(plant._inertia, "plant._inertia"),
            "_inertia_inverse": _matrix3(
                plant._inertia_inverse, "plant._inertia_inverse"
            ),
            "parameter_binding_sha256": _json_value_digest(plant_values),
        },
        "actuator": {
            "_actual": _vec(actuator._actual, 3, "actuator._actual"),
            "_target": _vec(actuator._target, 3, "actuator._target"),
            "_requested": _vec(actuator._requested, 3, "actuator._requested"),
            "_saturated": _flags(actuator._saturated, "actuator._saturated"),
            "_command_timestamp": _hex(actuator._command_timestamp),
            "_timestamp": _hex(actuator._timestamp),
            "_last_reset_epoch": (
                None
                if actuator._last_reset_epoch is None
                else _hex(actuator._last_reset_epoch)
            ),
            "_epoch_origin_s": (
                None
                if actuator._epoch_origin_s is None
                else _hex(actuator._epoch_origin_s)
            ),
            "_local_tick": int(actuator._local_tick),
            "_mode": actuator._mode,
            "_reset": bool(actuator._reset),
            "_limits": _vec(actuator._limits, 3, "actuator._limits"),
            "_time_constant": _hex(actuator._time_constant),
            "parameter_binding_sha256": _json_value_digest(actuator_values),
        },
        "imu": {
            "_reset_epoch": _hex(imu._reset_epoch),
            "_last_sample_timestamp": (
                None
                if imu._last_sample_timestamp is None
                else _hex(imu._last_sample_timestamp)
            ),
            "_samples_emitted": int(imu._samples_emitted),
            "_rng_seed": int(imu._rng_seed),
            "_last_reset_epoch": (
                None
                if imu._last_reset_epoch is None
                else _hex(imu._last_reset_epoch)
            ),
            "_epoch_origin_s": (
                None if imu._epoch_origin_s is None else _hex(imu._epoch_origin_s)
            ),
            "_local_tick": int(imu._local_tick),
            "_next_sample_tick": int(imu._next_sample_tick),
            "_reset": bool(imu._reset),
            "_rng_state": (
                None if imu._rng is None else imu._rng.bit_generator.state
            ),
            "parameter_binding_sha256": _json_value_digest(imu_values),
        },
        "estimator": {
            "_estimate": (
                None
                if estimator._estimate is None
                else _estimate(estimator._estimate)
            ),
            "_reset_epoch": (
                None
                if estimator._reset_epoch is None
                else _epoch(estimator._reset_epoch)
            ),
            "_last_tick": int(estimator._last_tick),
            "_rng_seed": int(estimator._rng_seed),
            "parameter_binding_sha256": _json_value_digest(estimator_values),
        },
        "controller": _controller_snapshot(session.controller),
    }


def _wire_payload(envelope: Any) -> tuple[str, str, dict[str, Any]]:
    role = envelope.role
    if role == "plant_state":
        return "plant_state", "plant_state", _plant_state(envelope.payload)
    if role == "sensor_truth":
        return "sensor_truth", "sensor_truth", _sensor_truth(envelope.payload)
    if role == "held_torque":
        return "torque_command", "torque_command", _torque_command(envelope.payload)
    if role == "feedback":
        return "feedback", "feedback", _feedback(envelope.payload)
    if role == "imu":
        field = "raw_imu" if envelope.producer == "imu" else "adapted_imu"
        return "imu", field, _imu_sample(envelope.payload)
    if role == "estimate":
        return "estimate", "estimate", _estimate(envelope.payload)
    if role == "attitude_command":
        return (
            "attitude_command",
            "attitude_command",
            _attitude_command(envelope.payload),
        )
    if role == "estimator_diagnostics":
        return (
            "estimator_diagnostics",
            "estimator_diagnostics",
            _diagnostics_estimator(envelope.payload),
        )
    if role == "controller_diagnostics":
        return (
            "controller_diagnostics",
            "controller_diagnostics",
            _diagnostics_controller(envelope.payload),
        )
    raise EvidenceDriverError("unknown_wire_role", str(role))


def _wire(envelope: Any) -> dict[str, Any]:
    kind, producer_field, payload = _wire_payload(envelope)
    return {
        "wire_id": envelope.envelope_id,
        "kind": kind,
        "role": envelope.role,
        "producer": envelope.producer,
        "parent_ids": list(envelope.parent_ids),
        "epoch_id": int(envelope.epoch_id),
        "global_tick": int(envelope.global_tick),
        "local_tick": int(envelope.local_tick),
        "phase": int(envelope.phase),
        "producer_operation_id": envelope.producer_operation_id,
        "producer_field": producer_field,
        "payload": payload,
    }


def _configuration_bindings(
    scheduler: Any,
    events: Sequence[Mapping[str, Any]],
    g1_parameters: Any,
    estimator_parameters: Any,
    controller_parameters: Any,
) -> dict[str, str]:
    scheduler_values = {
        "base_period_s": _hex(scheduler.base_period_s),
        "plant_every_ticks": int(scheduler.plant_every_ticks),
        "actuator_every_ticks": int(scheduler.actuator_every_ticks),
        "imu_every_ticks": int(scheduler.imu_every_ticks),
        "estimator_every_ticks": int(scheduler.estimator_every_ticks),
        "controller_every_ticks": int(scheduler.controller_every_ticks),
    }
    parameter_values = {
        "g1": _ParameterRegistry.values("g1", g1_parameters),
        "estimator": _ParameterRegistry.values("estimator", estimator_parameters),
        "controller": _ParameterRegistry.values("controller", controller_parameters),
    }
    return {
        "scheduler_definition_sha256": _json_value_digest(scheduler_values),
        "event_definition_sha256": _json_value_digest(list(events)),
        "parameter_binding_sha256": _json_value_digest(parameter_values),
    }


def _initial_inputs(
    profile_id: str, definition: Mapping[str, Any], np: Any
) -> dict[str, Any]:
    inputs = definition["initial_inputs"]
    return {
        "plant_q_nb": _vec(
            _plant_profile_initial_q(profile_id, definition, np),
            4,
            "plant_q_nb",
        ),
        "plant_omega_b_rad_s": _vec(
            inputs["plant_omega_b_rad_s"], 3, "plant_omega_b_rad_s"
        ),
        "estimator_q_nb": _vec(
            inputs["estimator_q_nb"], 4, "estimator_q_nb"
        ),
        "estimator_omega_b_rad_s": _vec(
            inputs["estimator_omega_b_rad_s"],
            3,
            "estimator_omega_b_rad_s",
        ),
        "actuator_actual_torque_body_Nm": _vec(
            inputs["actuator_actual_torque_body_Nm"],
            3,
            "actuator_actual_torque_body_Nm",
        ),
        "attitude_command_q_nb": _vec(
            _axis_quaternion("x", 0.0, np), 4, "attitude_command_q_nb"
        ),
        "reset_local_command_q_nb": _vec(
            _axis_quaternion(
                "x", float(inputs["controller_reset_local_command_axes_rad"][0]), np
            ),
            4,
            "reset_local_command_q_nb",
        ),
        "epoch_id": 0,
        "epoch_origin_tick": 0,
        "epoch_origin_s": _hex(0.0),
        "source_refs": [
            inputs["source_locators"]["plant_only_attitude_offset_rad"],
            inputs["source_locators"]["controller_reset_local_command_axes_rad"],
        ],
    }


def _event_inputs(
    events: Sequence[Mapping[str, Any]], event_ids: Sequence[str]
) -> dict[str, Any]:
    active_ids = tuple(event_ids)
    active = {event["id"]: event for event in events if event["id"] in active_ids}
    axes = {"x": 0.0, "y": 0.0, "z": 0.0}
    external = [0.0, 0.0, 0.0]
    gyro_bias = None
    accelerometer_bias = None
    force = [0.0, 0.0, 0.0]
    for event_id in active_ids:
        event = active[event_id]
        if event["type"] == "command_step":
            axes[event["axis"]] = float(event["value_rad"])
        elif event["type"] == "external_torque":
            external = event["vector_Nm"]
        elif event["type"] == "imu_bias":
            gyro_bias = event["gyro_bias_rad_s"]
            accelerometer_bias = event["accelerometer_bias_m_s2"]
        elif event["type"] == "specific_force_disturbance":
            force = event["vector_m_s2"]
    return {
        "active_event_ids": list(active_ids),
        "command_axes_rad": [_hex(axes[axis]) for axis in ("x", "y", "z")],
        "external_torque_body_Nm": _vec(external, 3, "external_torque_body_Nm"),
        "replacement_gyro_bias_rad_s": (
            None if gyro_bias is None else _vec(gyro_bias, 3, "gyro_bias_rad_s")
        ),
        "replacement_accelerometer_bias_m_s2": (
            None
            if accelerometer_bias is None
            else _vec(accelerometer_bias, 3, "accelerometer_bias_m_s2")
        ),
        "additive_specific_force_body_m_s2": _vec(
            force, 3, "additive_specific_force_body_m_s2"
        ),
    }


class _SnapshotStore:
    def __init__(self) -> None:
        self._snapshots: list[dict[str, Any]] = []
        self._ids: set[str] = set()

    def add(
        self,
        snapshot_id: str,
        capture_id: str,
        global_tick: int,
        phase: int,
        functional_state: Mapping[str, Any],
    ) -> str:
        if snapshot_id in self._ids:
            raise EvidenceDriverError("duplicate_snapshot_id", snapshot_id)
        self._ids.add(snapshot_id)
        snapshot = {
            "snapshot_id": snapshot_id,
            "capture_id": capture_id,
            "global_tick": int(global_tick),
            "phase": int(phase),
            **dict(functional_state),
        }
        self._snapshots.append(snapshot)
        return snapshot_id

    @property
    def values(self) -> list[dict[str, Any]]:
        return list(self._snapshots)


def _empty_count_delta() -> dict[str, int]:
    # Guard probes precede consumption.  Their delta is limited to the twenty
    # component step/outcome/reset/construction counters; the three probe
    # rejection counters are recorder bookkeeping, not component calls.
    return {key: 0 for key in COMPONENT_COUNT_KEYS}


def _confirm_zero_delta(value: Mapping[str, Any], probe_id: str) -> dict[str, int]:
    expected = set(COMPONENT_COUNT_KEYS)
    if set(value) != expected:
        raise EvidenceDriverError(
            "component_counter_keys_mismatch",
            f"{probe_id}: missing={sorted(expected - set(value))!r}; "
            f"extra={sorted(set(value) - expected)!r}",
        )
    if any(type(value[key]) is not int or value[key] != 0 for key in expected):
        raise EvidenceDriverError("probe_called_component", probe_id)
    return {key: int(value[key]) for key in COMPONENT_COUNT_KEYS}


def _component_count_snapshot(
    session: Any,
    *,
    profile_id: str,
    lifecycle: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    """Read the actual twenty component counters used by rejection probes."""

    raw = _require_internal_mapping(session.call_counts, "session.call_counts")
    expected_session = set(_SESSION_COUNTER_TO_EVIDENCE)
    if set(raw) != expected_session:
        raise EvidenceDriverError(
            "session_counter_keys_mismatch",
            f"missing={sorted(expected_session - set(raw))!r}; "
            f"extra={sorted(set(raw) - expected_session)!r}",
        )
    counts = _empty_count_delta()
    for session_key, evidence_key in _SESSION_COUNTER_TO_EVIDENCE.items():
        value = raw[session_key]
        if type(value) is not int or value < 0:
            raise EvidenceDriverError("session_counter_value_invalid", session_key)
        counts[evidence_key] = value
    for observation in lifecycle:
        if (
            observation["profile_id"] == profile_id
            and observation["event"] == "return"
            and observation["method"] == "constructor"
            and observation["owner"] in _CONSTRUCTOR_OWNER_TO_EVIDENCE
        ):
            counts[_CONSTRUCTOR_OWNER_TO_EVIDENCE[observation["owner"]]] += 1
    return counts


def _component_count_difference(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    probe_id: str,
) -> dict[str, int]:
    expected = set(COMPONENT_COUNT_KEYS)
    if set(before) != expected or set(after) != expected:
        raise EvidenceDriverError("component_counter_keys_mismatch", probe_id)
    delta: dict[str, int] = {}
    for key in COMPONENT_COUNT_KEYS:
        before_value = before[key]
        after_value = after[key]
        if (
            type(before_value) is not int
            or type(after_value) is not int
            or before_value < 0
            or after_value < before_value
        ):
            raise EvidenceDriverError("component_counter_value_invalid", key)
        delta[key] = after_value - before_value
    return delta


def _materialize_session_probe_delta(
    value: Mapping[str, Any],
    *,
    profile_id: str,
    lifecycle: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    """Bind a session's 14 counters plus observed constructor activity to 20."""

    raw = _require_mapping(value["component_call_delta"], "component_call_delta")
    expected_session = set(_SESSION_COUNTER_TO_EVIDENCE)
    if set(raw) != expected_session:
        raise EvidenceDriverError(
            "session_counter_keys_mismatch",
            str(value["probe_id"]),
        )
    delta = _empty_count_delta()
    for session_key, evidence_key in _SESSION_COUNTER_TO_EVIDENCE.items():
        item = raw[session_key]
        if type(item) is not int or item < 0:
            raise EvidenceDriverError("session_counter_value_invalid", session_key)
        delta[evidence_key] = item

    capture_terminals: dict[str, list[int]] = {
        str(value["before_capture_id"]): [],
        str(value["after_capture_id"]): [],
    }
    for observation in lifecycle:
        if (
            observation["profile_id"] == profile_id
            and observation["owner"] == "observer"
            and observation["method"] == "capture_snapshot"
            and observation["event"] == "return"
        ):
            result = _require_mapping(
                observation["result"], "observer lifecycle result"
            )
            capture_id = result.get("capture_id")
            if capture_id in capture_terminals:
                capture_terminals[str(capture_id)].append(
                    int(observation["observation_index"])
                )
    before_matches = capture_terminals[str(value["before_capture_id"])]
    after_matches = capture_terminals[str(value["after_capture_id"])]
    if len(before_matches) != 1 or len(after_matches) != 1:
        raise EvidenceDriverError(
            "probe_capture_lifecycle_mismatch", str(value["probe_id"])
        )
    before_index = before_matches[0]
    after_index = after_matches[0]
    if after_index <= before_index:
        raise EvidenceDriverError(
            "probe_capture_order_mismatch", str(value["probe_id"])
        )
    for observation in lifecycle:
        index = int(observation["observation_index"])
        if (
            before_index < index <= after_index
            and observation["profile_id"] == profile_id
            and observation["event"] == "return"
            and observation["method"] == "constructor"
            and observation["owner"] in _CONSTRUCTOR_OWNER_TO_EVIDENCE
        ):
            delta[_CONSTRUCTOR_OWNER_TO_EVIDENCE[observation["owner"]]] += 1
    return _confirm_zero_delta(delta, str(value["probe_id"]))


def _held_after_reference(
    *,
    boundary_kind: str,
    held_before_id: str | None,
    published_after_id: str | None,
) -> str | None:
    """Return the command actually held when a boundary finishes.

    ``published_after_id`` on the session result records a new phase-6
    publication, so it is null on an ordinary boundary that merely continues
    holding the previous command.  The raw evidence field instead carries the
    actual held-after reference on every completed ordinary boundary.  Keeping
    this conversion here preserves the absence of a publish operation while
    avoiding a fictitious null held state on odd ticks and rejected O6 calls.
    """

    if published_after_id is not None:
        return published_after_id
    if boundary_kind == "ordinary":
        return held_before_id
    return None


def _exception_observation(exc: BaseException) -> dict[str, Any]:
    return {
        "type": type(exc).__name__,
        "reason": getattr(exc, "reason", None),
        "detail": getattr(exc, "detail", str(exc)),
        "message": str(exc),
    }


def _first_exception_observation(exc: BaseException) -> dict[str, Any]:
    """Prefer the session-retained first cause over a transport wrapper."""

    frontier = getattr(exc, "failure_frontier", None)
    original = (
        frontier.get("original_exception")
        if isinstance(frontier, Mapping)
        else None
    )
    if isinstance(original, Mapping):
        return {
            "type": original.get("type"),
            "reason": original.get("reason"),
            "detail": original.get("detail"),
            "message": original.get("message"),
        }
    return _exception_observation(exc)


def _exception_reason(exc: BaseException) -> str:
    reason = getattr(exc, "reason", None)
    if isinstance(reason, str) and reason:
        return reason
    message = str(exc)
    return message.split(":", 1)[0] if message else type(exc).__name__


def _ref_key(role: str, wire_by_id: Mapping[str, Mapping[str, Any]], ref: str) -> str:
    if role == "held_torque":
        return "torque_command"
    if role != "imu":
        return role
    wire = wire_by_id.get(ref)
    if wire is None:
        raise EvidenceDriverError("producer_ref_missing", ref)
    return "raw_imu" if wire["producer"] == "imu" else "adapted_imu"


def _refs(
    value: Mapping[str, str], wire_by_id: Mapping[str, Mapping[str, Any]]
) -> dict[str, str]:
    return {
        _ref_key(role, wire_by_id, ref): ref for role, ref in value.items()
    }


def _materialize_snapshot_pair(
    value: Mapping[str, Any],
    *,
    global_tick: int,
    phase: int,
    snapshots: _SnapshotStore,
) -> tuple[str | None, str | None]:
    before_ref = None
    after_ref = None
    if "before_snapshot" in value:
        before_ref = snapshots.add(
            str(value["before_snapshot_id"]),
            str(value["before_capture_id"]),
            global_tick,
            phase,
            _require_mapping(value["before_snapshot"], "before_snapshot"),
        )
    if "after_snapshot" in value:
        after_ref = snapshots.add(
            str(value["after_snapshot_id"]),
            str(value["after_capture_id"]),
            global_tick,
            phase,
            _require_mapping(value["after_snapshot"], "after_snapshot"),
        )
    return before_ref, after_ref


def _materialize_operation(
    value: Mapping[str, Any],
    *,
    global_tick: int,
    snapshots: _SnapshotStore,
    canonicalize: Callable[[Any], Any],
) -> dict[str, Any]:
    phase = int(value["phase"])
    before_ref, after_ref = _materialize_snapshot_pair(
        value,
        global_tick=global_tick,
        phase=phase,
        snapshots=snapshots,
    )
    operation = {
        "operation_id": value["operation_id"],
        "owner": value["owner"],
        "method": value["method"],
        "phase": phase,
        "attempt_kind": value["attempt_kind"],
        "inputs": dict(value["inputs"]),
        "outputs": dict(value["outputs"]),
        "scalar_inputs": dict(value["scalar_inputs"]),
        "reset_inputs": value["reset_inputs"],
        "accepted": bool(value["accepted"]),
        "reason": str(value["reason"]),
        "before_snapshot_ref": before_ref,
        "after_snapshot_ref": after_ref,
        "guard_ref": value["guard_ref"],
    }
    return canonicalize(operation)


def _materialize_guard_probe(
    guard: Mapping[str, Any],
    *,
    wire_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "probe_id": guard["guard_id"],
        "kind": "normal_guard",
        "global_tick": int(guard["global_tick"]),
        "phase": int(guard["phase"]),
        "consumer_operation_id": guard["consumer_operation_id"],
        "role": guard["role"],
        "checked_refs": _refs(guard["checked_refs"], wire_by_id),
        "candidate_ref": guard["candidate_id"],
        "original_legal_ref": None,
        "source_truth_ref": None,
        "source_field": None,
        "target_field": None,
        "derivation_site": None,
        "guard_site": guard["site"],
        "accepted": bool(guard["accepted"]),
        "reason": str(guard["reason"]),
        "before_snapshot_ref": None,
        "after_snapshot_ref": None,
        "component_call_delta": _empty_count_delta(),
    }


def _materialize_rejection_probe(
    value: Mapping[str, Any],
    *,
    profile_id: str,
    lifecycle: Sequence[Mapping[str, Any]],
    wire_by_id: Mapping[str, Mapping[str, Any]],
    snapshots: _SnapshotStore,
) -> dict[str, Any]:
    before_ref, after_ref = _materialize_snapshot_pair(
        value,
        global_tick=int(value["global_tick"]),
        phase=int(value["phase"]),
        snapshots=snapshots,
    )
    return {
        "probe_id": value["probe_id"],
        "kind": value["kind"],
        "global_tick": int(value["global_tick"]),
        "phase": int(value["phase"]),
        "consumer_operation_id": value["consumer_operation_id"],
        "role": value["role"],
        "checked_refs": _refs(value["checked_refs"], wire_by_id),
        "candidate_ref": value["candidate_id"],
        "original_legal_ref": value["original_legal_id"],
        "source_truth_ref": value["source_truth_id"],
        "source_field": value["source_field"],
        "target_field": value["target_field"],
        "derivation_site": value["derivation_site"],
        "guard_site": value["guard_site"],
        "accepted": bool(value["accepted"]),
        "reason": str(value["reason"]),
        "before_snapshot_ref": before_ref,
        "after_snapshot_ref": after_ref,
        "component_call_delta": _materialize_session_probe_delta(
            value,
            profile_id=profile_id,
            lifecycle=lifecycle,
        ),
    }


class _ProfileRecord:
    """Materialize one profile from actual session values and call records."""

    def __init__(
        self,
        profile: Mapping[str, Any],
        definition: Mapping[str, Any],
        np: Any,
        canonicalize: Callable[[Any], Any],
    ) -> None:
        self.profile = profile
        self.events = _events_for_profile(profile)
        self.canonicalize = canonicalize
        self.snapshots = _SnapshotStore()
        self.wires: list[dict[str, Any]] = []
        self.wire_by_id: dict[str, dict[str, Any]] = {}
        self.boundaries: list[dict[str, Any]] = []
        self.probes: list[dict[str, Any]] = []
        self.failure_frontiers: list[dict[str, Any]] = []
        self.retention_failures: list[dict[str, Any]] = []
        self.initial_inputs = _initial_inputs(
            str(profile["profile_id"]), definition, np
        )

    def retain_failure_frontier(
        self,
        exc: Exception,
        *,
        lifecycle: Sequence[Mapping[str, Any]],
        capture_site: str,
        boundary_result: Any | None = None,
        component_call_counts: Mapping[str, Any] | None = None,
        observed_frontier: Mapping[str, Any] | None = None,
    ) -> None:
        """Retain only already-observed facts for one failed transaction.

        This method never calls the observer or a component.  Session-owned
        frontiers take precedence.  ``boundary_result`` is used only when the
        boundary already returned and a subsequent required observer capture
        failed in the driver.
        """

        if self.failure_frontiers or self.retention_failures:
            return
        supplied = getattr(exc, "failure_frontier", None)
        frontier = (
            supplied
            if isinstance(supplied, Mapping)
            else observed_frontier
            if isinstance(observed_frontier, Mapping)
            else None
        )
        if frontier is None and boundary_result is None:
            operations: Sequence[Mapping[str, Any]] = ()
            guards: Sequence[Mapping[str, Any]] = ()
            probes: Sequence[Mapping[str, Any]] = ()
            envelopes: Sequence[Any] = ()
            profile_id = str(self.profile["profile_id"])
            global_tick = None
            epoch_id = None
            epoch_origin_tick = None
            local_tick = None
            epoch_origin_s = None
            timestamp_s = None
            boundary_kind = None
            event_ids: Sequence[str] = ()
            held_before_id = None
            published_after_id = None
            counts = {} if component_call_counts is None else component_call_counts
            lifecycle_state = None
            phase_cursor = None
            termination_status = "driver_inconclusive"
            original_exception: Mapping[str, Any] = _exception_observation(exc)
            required_after_imu_capture = None
            retention_status = "complete"
            missing_observations: list[str] = []
            retention_exception = None
        else:
            source = frontier
            if source is None:
                source = {
                    "profile_id": str(self.profile["profile_id"]),
                    "global_tick": boundary_result.global_tick,
                    "epoch_id": boundary_result.epoch_id,
                    "epoch_origin_tick": boundary_result.epoch_origin_tick,
                    "local_tick": boundary_result.local_tick,
                    "epoch_origin_s": boundary_result.epoch_origin_s,
                    "timestamp_s": boundary_result.timestamp_s,
                    "boundary_kind": boundary_result.boundary_kind,
                    "event_ids": boundary_result.event_ids,
                    "held_before_id": boundary_result.held_before_id,
                    "published_after_id": boundary_result.published_after_id,
                    "operations": boundary_result.operations,
                    "guards": boundary_result.guards,
                    "probes": boundary_result.probes,
                    "wires": boundary_result.wires,
                    "component_call_counts": (
                        {} if component_call_counts is None else component_call_counts
                    ),
                    "original_exception": _exception_observation(exc),
                    "lifecycle_state": None,
                    "phase_cursor": None,
                    "termination_status": "driver_observer_inconclusive",
                }
            profile_id = str(source["profile_id"])
            global_tick = int(source["global_tick"])
            epoch_id = int(source["epoch_id"])
            epoch_origin_tick = int(source["epoch_origin_tick"])
            local_tick = int(source["local_tick"])
            epoch_origin_s = _hex(source["epoch_origin_s"])
            timestamp_s = _hex(source["timestamp_s"])
            boundary_kind = str(source["boundary_kind"])
            event_ids = tuple(str(item) for item in source["event_ids"])
            held_before_id = source["held_before_id"]
            published_after_id = _held_after_reference(
                boundary_kind=boundary_kind,
                held_before_id=source["held_before_id"],
                published_after_id=source["published_after_id"],
            )
            operations = tuple(source["operations"])
            guards = tuple(source["guards"])
            probes = tuple(source["probes"])
            envelopes = tuple(source["wires"])
            counts = _require_internal_mapping(
                source["component_call_counts"], "failure component counts"
            )
            lifecycle_state = source["lifecycle_state"]
            phase_value = source["phase_cursor"]
            phase_cursor = None if phase_value is None else int(phase_value)
            termination_status = source["termination_status"]
            original_exception = _require_internal_mapping(
                source["original_exception"], "failure original exception"
            )
            required_after_imu_capture = source.get(
                "required_after_imu_capture"
            )
            retention_status = str(source.get("retention_status", "complete"))
            missing_observations = [
                str(item) for item in source.get("missing_observations", ())
            ]
            retained_secondary = source.get("retention_exception")
            retention_exception = (
                None
                if retained_secondary is None
                else self.canonicalize(
                    dict(
                        _require_internal_mapping(
                            retained_secondary,
                            "failure retention exception",
                        )
                    )
                )
            )
            if retention_status not in {"complete", "incomplete"}:
                raise EvidenceDriverError(
                    "failure_frontier_retention_status_invalid",
                    retention_status,
                )
            if retention_status == "complete" and (
                missing_observations or retention_exception is not None
            ):
                raise EvidenceDriverError(
                    "failure_frontier_retention_status_invalid",
                    "complete frontier declares missing observations",
                )
            if retention_status == "incomplete" and (
                not missing_observations or retention_exception is None
            ):
                raise EvidenceDriverError(
                    "failure_frontier_retention_status_invalid",
                    "incomplete frontier lacks its secondary failure",
                )

        required_after_ref = None
        if required_after_imu_capture is not None:
            capture_snapshot_id = getattr(
                required_after_imu_capture, "snapshot_id", None
            )
            capture_id = getattr(required_after_imu_capture, "capture_id", None)
            capture_phase = getattr(required_after_imu_capture, "phase", None)
            capture_state = getattr(
                required_after_imu_capture, "functional_state", None
            )
            if (
                not isinstance(capture_snapshot_id, str)
                or not capture_snapshot_id
                or not isinstance(capture_id, str)
                or not capture_id
                or type(capture_phase) is not int
                or capture_phase != 3
                or global_tick is None
            ):
                raise EvidenceDriverError(
                    "required_snapshot_binding_mismatch",
                    f"failure frontier {self.profile['profile_id']}",
                )
            required_after_ref = self.add_snapshot(
                capture_snapshot_id,
                capture_id,
                global_tick,
                capture_phase,
                self.canonicalize(
                    _require_internal_mapping(
                        capture_state,
                        "failure required after-IMU snapshot",
                    )
                ),
            )

        materialized_wires: list[dict[str, Any]] = []
        for envelope in envelopes:
            self.add_envelope(envelope)
            materialized_wires.append(self.wire_by_id[envelope.envelope_id])
        materialized_guards = [
            self.canonicalize(
                dict(_require_internal_mapping(item, "failure guard"))
            )
            for item in guards
        ]
        materialized_probes = [
            _materialize_rejection_probe(
                self.canonicalize(
                    _require_internal_mapping(item, "failure probe")
                ),
                profile_id=str(self.profile["profile_id"]),
                lifecycle=lifecycle,
                wire_by_id=self.wire_by_id,
                snapshots=self.snapshots,
            )
            for item in probes
        ]
        materialized_operations = [
            _materialize_operation(
                self.canonicalize(
                    _require_internal_mapping(item, "failure operation")
                ),
                global_tick=(0 if global_tick is None else global_tick),
                snapshots=self.snapshots,
                canonicalize=self.canonicalize,
            )
            for item in operations
        ]
        if required_after_ref is not None:
            samples = [
                operation
                for operation in materialized_operations
                if operation["owner"] == "imu"
                and operation["method"] == "sample"
                and operation["accepted"]
            ]
            if len(samples) == 1:
                samples[0]["after_snapshot_ref"] = required_after_ref
            elif retention_status == "complete":
                raise EvidenceDriverError(
                    "required_snapshot_binding_mismatch",
                    f"failure frontier {self.profile['profile_id']}",
                )
            else:
                missing_observations.append(
                    "required_after_imu_operation_binding"
                )
        lifecycle_owner = None
        for observation in reversed(lifecycle):
            if (
                observation.get("profile_id") == str(self.profile["profile_id"])
                and observation.get("event") == "exception"
            ):
                lifecycle_owner = observation.get("owner")
                break
        self.failure_frontiers.append(
            {
                "capture_site": capture_site,
                "failure_origin": (
                    "observer"
                    if lifecycle_owner == "observer"
                    else (
                        "dut_or_session"
                        if capture_site.startswith("integration_session.")
                        or capture_site.endswith(
                            (
                                ".reset",
                                ".process",
                                ".step",
                                ".guard",
                                ".diagnostics",
                            )
                        )
                        else "driver_materialization"
                    )
                ),
                "lifecycle_exception_owner": lifecycle_owner,
                "profile_id": profile_id,
                "global_tick": global_tick,
                "epoch_id": epoch_id,
                "epoch_origin_tick": epoch_origin_tick,
                "local_tick": local_tick,
                "epoch_origin_s": epoch_origin_s,
                "timestamp_s": timestamp_s,
                "boundary_kind": boundary_kind,
                "event_ids": list(event_ids),
                "held_before_ref": held_before_id,
                "published_after_ref": published_after_id,
                "operations": materialized_operations,
                "guards": materialized_guards,
                "probes": materialized_probes,
                "wires": materialized_wires,
                "component_call_counts": {
                    str(key): int(value) for key, value in counts.items()
                },
                "original_exception": self.canonicalize(
                    dict(original_exception)
                ),
                "lifecycle_state": lifecycle_state,
                "phase_cursor": phase_cursor,
                "termination_status": termination_status,
                "required_after_imu_snapshot_ref": required_after_ref,
                "retention_status": retention_status,
                "missing_observations": missing_observations,
                "retention_exception": retention_exception,
            }
        )

    def mark_retention_incomplete(
        self,
        primary_exception: Exception,
        retention_exception: Exception,
        *,
        capture_site: str,
    ) -> None:
        """Retain a bounded secondary-failure marker without hiding cause one."""

        if self.failure_frontiers or self.retention_failures:
            return
        self.retention_failures.append(
            {
                "capture_site": capture_site,
                "retention_status": "incomplete",
                "missing_observations": ["failure_frontier_materialization"],
                "primary_exception": _first_exception_observation(
                    primary_exception
                ),
                "retention_exception": _exception_observation(
                    retention_exception
                ),
            }
        )

    def add_envelope(self, envelope: Any) -> None:
        if envelope.envelope_id in self.wire_by_id:
            return
        materialized = _wire(envelope)
        self.wire_by_id[envelope.envelope_id] = materialized
        self.wires.append(materialized)

    def add_snapshot(
        self,
        snapshot_id: str,
        capture_id: str,
        global_tick: int,
        phase: int,
        functional_state: Mapping[str, Any],
    ) -> str:
        return self.snapshots.add(
            snapshot_id,
            capture_id,
            global_tick,
            phase,
            functional_state,
        )

    def add_boundary(
        self,
        result: Any,
        *,
        lifecycle: Sequence[Mapping[str, Any]],
        reset_before_ref: str | None = None,
        reset_after_ref: str | None = None,
        required_after_ref: str | None = None,
    ) -> None:
        for envelope in result.wires:
            self.add_envelope(envelope)
        represented_guards = {
            probe["guard_ref"] for probe in result.probes
        }
        for guard in result.guards:
            if guard["guard_id"] not in represented_guards:
                self.probes.append(
                    _materialize_guard_probe(
                        guard,
                        wire_by_id=self.wire_by_id,
                    )
                )
        for probe in result.probes:
            self.probes.append(
                _materialize_rejection_probe(
                    probe,
                    profile_id=str(self.profile["profile_id"]),
                    lifecycle=lifecycle,
                    wire_by_id=self.wire_by_id,
                    snapshots=self.snapshots,
                )
            )
        operations = [
            _materialize_operation(
                operation,
                global_tick=int(result.global_tick),
                snapshots=self.snapshots,
                canonicalize=self.canonicalize,
            )
            for operation in result.operations
        ]
        if reset_before_ref is not None or reset_after_ref is not None:
            controller_resets = [
                operation
                for operation in operations
                if operation["owner"] == "controller"
                and operation["method"] == "reset"
            ]
            estimator_resets = [
                operation
                for operation in operations
                if operation["owner"] == "estimator"
                and operation["method"] == "reset"
            ]
            if (
                reset_before_ref is None
                or reset_after_ref is None
                or len(controller_resets) != 1
                or len(estimator_resets) != 1
            ):
                raise EvidenceDriverError(
                    "reset_snapshot_binding_mismatch",
                    str(self.profile["profile_id"]),
                )
            controller_resets[0]["before_snapshot_ref"] = reset_before_ref
            estimator_resets[0]["after_snapshot_ref"] = reset_after_ref
        if required_after_ref is not None:
            samples = [
                operation
                for operation in operations
                if operation["owner"] == "imu"
                and operation["method"] == "sample"
                and operation["accepted"]
            ]
            if len(samples) != 1:
                raise EvidenceDriverError(
                    "required_snapshot_binding_mismatch",
                    f"{self.profile['profile_id']}:{result.global_tick}",
                )
            samples[0]["after_snapshot_ref"] = required_after_ref
        self.boundaries.append(
            {
                "global_tick": int(result.global_tick),
                "epoch_id": int(result.epoch_id),
                "epoch_origin_tick": int(result.epoch_origin_tick),
                "local_tick": int(result.local_tick),
                "epoch_origin_s": _hex(result.epoch_origin_s),
                "timestamp_s": _hex(result.timestamp_s),
                "boundary_kind": result.boundary_kind,
                "event_inputs": _event_inputs(self.events, result.event_ids),
                "held_before_ref": result.held_before_id,
                "published_after_ref": _held_after_reference(
                    boundary_kind=result.boundary_kind,
                    held_before_id=result.held_before_id,
                    published_after_id=result.published_after_id,
                ),
                "operations": operations,
            }
        )

    def add_needs_reset_probe(
        self,
        *,
        probe_id: str,
        global_tick: int,
        before_ref: str,
        after_ref: str,
        component_call_delta: Mapping[str, Any],
    ) -> None:
        self.probes.append(
            {
                "probe_id": probe_id,
                "kind": "needs_reset",
                "global_tick": global_tick,
                "phase": 0,
                "consumer_operation_id": None,
                "role": "ordinary_boundary",
                "checked_refs": {},
                "candidate_ref": None,
                "original_legal_ref": None,
                "source_truth_ref": None,
                "source_field": None,
                "target_field": None,
                "derivation_site": None,
                "guard_site": "integration_session.advance.lifecycle_preflight",
                "accepted": False,
                "reason": "needs_reset",
                "before_snapshot_ref": before_ref,
                "after_snapshot_ref": after_ref,
                "component_call_delta": _confirm_zero_delta(
                    component_call_delta, probe_id
                ),
            }
        )

    def materialize(self, counts: Mapping[str, int]) -> dict[str, Any]:
        return {
            "profile_id": self.profile["profile_id"],
            "horizon_tick": int(self.profile["horizon_tick"]),
            "reset_ticks": [int(tick) for tick in self.profile["reset_ticks"]],
            "initial_inputs": self.initial_inputs,
            "wires": self.wires,
            "boundaries": self.boundaries,
            "probes": self.probes,
            "snapshots": self.snapshots.values,
            "reported_counts": dict(counts),
        }


def _retain_failure_without_masking(
    record: _ProfileRecord,
    exc: Exception,
    *,
    lifecycle: Sequence[Mapping[str, Any]],
    capture_site: str,
    boundary_result: Any | None = None,
    component_call_counts: Mapping[str, Any] | None = None,
    observed_frontier: Mapping[str, Any] | None = None,
) -> None:
    try:
        record.retain_failure_frontier(
            exc,
            lifecycle=lifecycle,
            capture_site=capture_site,
            boundary_result=boundary_result,
            component_call_counts=component_call_counts,
            observed_frontier=observed_frontier,
        )
    except Exception as retention_exc:
        try:
            record.mark_retention_incomplete(
                exc,
                retention_exc,
                capture_site=capture_site,
            )
        except Exception as marker_exc:
            exc.add_note(
                "secondary incomplete-retention marker failure retained: "
                f"{type(marker_exc).__name__}: {marker_exc}"
            )
        exc.add_note(
            "secondary failure-frontier materialization failure retained: "
            f"{type(retention_exc).__name__}: {retention_exc}"
        )


def _profile_counts(
    record: _ProfileRecord,
    lifecycle: Sequence[Mapping[str, Any]],
    planned_auxiliary_keys: Sequence[str] = (),
    *,
    enforce_auxiliary_plan: bool = True,
) -> dict[str, int]:
    counts = {key: 0 for key in COUNT_KEYS}
    planned = set(planned_auxiliary_keys)
    for key in planned_auxiliary_keys:
        if key in counts:
            raise EvidenceDriverError("auxiliary_counter_collision", key)
        counts[key] = 0

    def increment_auxiliary(key: str) -> None:
        if key not in planned:
            if enforce_auxiliary_plan:
                raise EvidenceDriverError("unplanned_auxiliary_counter", key)
            counts.setdefault(key, 0)
        counts[key] += 1

    for boundary in record.boundaries:
        for operation in boundary["operations"]:
            owner = operation["owner"]
            method = operation["method"]
            accepted = bool(operation["accepted"])
            if owner == "plant" and method == "step_base":
                counts["plant_step_base"] += 1
            elif owner == "actuator" and method == "step_base":
                counts["actuator_step_base"] += 1
            elif owner == "imu" and method == "sample":
                counts["imu_sample"] += 1
            elif owner == "estimator" and method == "process":
                counts["estimator_process"] += 1
                counts[
                    "estimator_accepted" if accepted else "estimator_rejected"
                ] += 1
            elif owner == "controller" and method == "step":
                counts["controller_step"] += 1
                counts[
                    "controller_accepted" if accepted else "controller_rejected"
                ] += 1
            elif method == "reset" and owner in {
                "plant",
                "actuator",
                "imu",
                "estimator",
                "controller",
            }:
                counts[f"{owner}_reset"] += 1
            if owner == "actuator" and method == "step":
                key = "operation:actuator:step"
                increment_auxiliary(key)
    constructor_keys = {
        "plant": "plant_constructor",
        "actuator": "actuator_constructor",
        "imu": "imu_constructor",
        "estimator": "estimator_constructor",
        "controller": "controller_adapter_constructor",
        "controller_core": "controller_core_constructor",
    }
    profile_id = str(record.profile["profile_id"])
    for observation in lifecycle:
        charged_profile = (
            "S"
            if observation["profile_id"] is None
            else str(observation["profile_id"])
        )
        if charged_profile == profile_id:
            lifecycle_key = (
                f"lifecycle:{observation['callsite']}:"
                f"{observation['event']}"
            )
            increment_auxiliary(lifecycle_key)
        if (
            observation["profile_id"] == profile_id
            and observation["event"] == "return"
            and observation["method"] == "constructor"
            and observation["owner"] in constructor_keys
        ):
            counts[constructor_keys[observation["owner"]]] += 1
    for probe in record.probes:
        guard_event = "accepted" if probe["accepted"] else str(probe["reason"])
        guard_key = f"guard:{probe['guard_site']}:{guard_event}"
        increment_auxiliary(guard_key)
        if probe["accepted"]:
            continue
        if probe["kind"] == "old_epoch":
            counts["old_epoch_rejected"] += 1
        elif probe["kind"] == "needs_reset":
            counts["needs_reset_rejected"] += 1
        elif probe["kind"] == "truth_negative":
            counts["truth_negative_rejected"] += 1
    return counts


def _capture_profile_snapshot(
    session: Any,
    record: _ProfileRecord,
    *,
    snapshot_id: str,
    global_tick: int,
    phase: int,
) -> str:
    capture_id = f"{snapshot_id}/capture"
    state = session.capture_state(snapshot_id, capture_id)
    return record.add_snapshot(
        snapshot_id,
        capture_id,
        global_tick,
        phase,
        _require_mapping(state, "captured snapshot"),
    )


def _old_epoch_directive(
    profile_id: str,
    tick: int,
    old: Mapping[str, Any],
    session_module: Any,
) -> Any:
    if profile_id != "L1":
        return session_module.TickDirective()
    if tick == 1001:
        return session_module.TickDirective(
            preflight_probes=(
                session_module.GuardProbe(
                    probe_id="L1_old_epoch_held_torque_1001",
                    kind="old_epoch",
                    envelope=old["held_torque"],
                    expected_role="held_torque",
                    consumer="actuator",
                    expected_reason="stale_epoch",
                ),
            )
        )
    if tick == 1002:
        return session_module.TickDirective(
            pre_estimator_probes=(
                session_module.GuardProbe(
                    probe_id="L1_old_epoch_imu_1002",
                    kind="old_epoch",
                    envelope=old["imu"],
                    expected_role="imu",
                    consumer="estimator",
                    expected_reason="stale_epoch",
                ),
            ),
            pre_controller_probes=tuple(
                session_module.GuardProbe(
                    probe_id=probe_id,
                    kind="old_epoch",
                    envelope=old[role],
                    expected_role=role,
                    consumer="controller",
                    expected_reason="stale_epoch",
                )
                for role, probe_id in (
                    ("feedback", "L1_old_epoch_feedback_1002"),
                    ("estimate", "L1_old_epoch_estimate_1002"),
                    (
                        "attitude_command",
                        "L1_old_epoch_attitude_command_1002",
                    ),
                )
            ),
            truth_estimator_probe_id="N_E_truth_to_imu_1002",
            truth_controller_probe_id="N_C_truth_to_estimate_1002",
        )
    return session_module.TickDirective()


def _directive_for_tick(
    profile_id: str,
    tick: int,
    old: Mapping[str, Any],
    session_module: Any,
) -> Any:
    directive = _old_epoch_directive(
        profile_id, tick, old, session_module
    )
    if profile_id in {"L1", "L2"} and tick == 400:
        return session_module.TickDirective(
            fault=session_module.FAULT_CONTROLLER_NEGATIVE_DT
        )
    if profile_id in {"L1", "L2"} and tick == 800:
        return session_module.TickDirective(
            fault=session_module.FAULT_ESTIMATOR_STALE_TIMESTAMP
        )
    if profile_id in {"O1", "O2"} and tick == 6:
        return session_module.TickDirective(
            fault=session_module.FAULT_CONTROLLER_UNEXPECTED_TICK
        )
    return directive


def _live_profiles(
    definition: Mapping[str, Any],
    dependencies: Mapping[str, Any],
    authority_identity: Mapping[str, Any],
    record_sink: list[_ProfileRecord] | None = None,
) -> tuple[list[_ProfileRecord], Any, Any, dict[int, dict[str, Any]]]:
    session_module = dependencies["session_module"]
    np = session_module.np
    simulation = dependencies["simulation"]
    estimator_module = dependencies["estimator_module"]
    adapter_module = dependencies["adapter_module"]
    controller_module = dependencies["controller_module"]
    support = dependencies["lifecycle_support"]
    g1_parameters, _g1_ref, _g1_sha = _load_g1_parameters_observed(
        simulation, support
    )
    shared_estimator_parameters = None
    records: list[_ProfileRecord] = []
    replay_sources: dict[int, dict[str, Any]] = {}

    for profile_id in PROFILE_ORDER[:6]:
        profile = _profile(definition, profile_id)
        record = _ProfileRecord(
            profile,
            definition,
            np,
            session_module.canonical_snapshot_value,
        )
        if record_sink is not None:
            record_sink.append(record)
        events = record.events
        scheduler = dependencies["scheduler_module"].IntegerScheduler.from_contract(
            dependencies["contract"]
        )
        event_schedule = dependencies["events_module"].EventSchedule(events)
        plant, plant_actor, _ = _construct_g1_component(
            profile_id,
            "plant",
            simulation.Plant,
            g1_parameters,
            support,
        )
        actuator, actuator_actor, _ = _construct_g1_component(
            profile_id,
            "actuator",
            simulation.Actuator,
            g1_parameters,
            support,
        )
        imu, imu_actor, _ = _construct_g1_component(
            profile_id,
            "imu",
            simulation.IMU,
            g1_parameters,
            support,
        )
        estimator, estimator_actor, actual_estimator_parameters, _, _ = (
            _construct_estimator(
                profile_id,
                estimator_module,
                support,
                shared_parameters=shared_estimator_parameters,
            )
        )
        if shared_estimator_parameters is None:
            shared_estimator_parameters = actual_estimator_parameters
        controller, controller_actor, _, _ = _construct_controller(
            profile_id,
            adapter_module,
            controller_module,
            authority_identity["controller_module_sha256"],
            support,
        )
        observer_actor = support.actors.new(profile_id, "observer")
        actor_ids = {
            "plant": plant_actor,
            "actuator": actuator_actor,
            "imu": imu_actor,
            "estimator": estimator_actor,
            "controller": controller_actor,
            "observer": observer_actor,
        }
        bindings = _configuration_bindings(
            scheduler,
            events,
            g1_parameters,
            actual_estimator_parameters,
            controller.parameters,
        )
        initial = definition["initial_inputs"]
        session = session_module.IntegrationSession(
            profile_id=profile_id,
            scheduler=scheduler,
            event_schedule=event_schedule,
            simulation=simulation,
            estimator_types=estimator_module,
            g1_parameters=g1_parameters,
            plant=plant,
            actuator=actuator,
            imu=imu,
            estimator=estimator,
            controller=controller,
            command_factory=_command_factory(np),
            actor_ids=actor_ids,
            observer_manifest_sha256=authority_identity[
                "observer_manifest_sha256"
            ],
            configuration_bindings=bindings,
            lifecycle_recorder=support.recorder,
            seed=SEED,
            plant_q_nb=_plant_profile_initial_q(profile_id, definition, np),
            plant_omega_b_rad_s=initial["plant_omega_b_rad_s"],
            estimator_q_nb=initial["estimator_q_nb"],
            estimator_omega_b_rad_s=initial["estimator_omega_b_rad_s"],
            actuator_actual_torque_body_Nm=initial[
                "actuator_actual_torque_body_Nm"
            ],
            initial_epoch_id=0,
            scenario_origin_s=0.0,
            snapshotter=_snapshot_observer,
        )
        old: dict[str, Any] = {}
        reset_ticks = set(int(tick) for tick in profile["reset_ticks"])
        required_snapshot_ticks = {
            tick + offset
            for tick in reset_ticks
            for offset in (0, 2, 4)
            if tick + offset <= int(profile["horizon_tick"])
        }
        for tick in range(0, int(profile["horizon_tick"]) + 1):
            if tick in reset_ticks:
                if tick > 0 and profile_id.startswith("O"):
                    probe_id = f"{profile_id}_needs_reset_ordinary_{tick}"
                    before_id = f"{profile_id}/g{tick}/needs-reset/before"
                    before_capture = f"{before_id}/capture"
                    try:
                        before = session.capture_state(before_id, before_capture)
                    except Exception as exc:
                        _retain_failure_without_masking(
                            record,
                            exc,
                            lifecycle=support.recorder.observations,
                            capture_site="driver.needs_reset.before_observer",
                            component_call_counts=session.call_counts,
                        )
                        raise
                    record.add_snapshot(
                        before_id,
                        before_capture,
                        tick,
                        0,
                        _require_mapping(before, "needs-reset before"),
                    )
                    before_counts = _component_count_snapshot(
                        session,
                        profile_id=profile_id,
                        lifecycle=support.recorder.observations,
                    )
                    try:
                        session.advance(tick)
                    except session_module.SessionContractError as exc:
                        if exc.reason != "needs_reset":
                            _retain_failure_without_masking(
                                record,
                                exc,
                                lifecycle=support.recorder.observations,
                                capture_site="integration_session.advance",
                                component_call_counts=session.call_counts,
                            )
                            raise
                    else:
                        raise EvidenceDriverError(
                            "needs_reset_probe_not_rejected", profile_id
                        )
                    after_counts = _component_count_snapshot(
                        session,
                        profile_id=profile_id,
                        lifecycle=support.recorder.observations,
                    )
                    component_call_delta = _component_count_difference(
                        before_counts, after_counts, probe_id
                    )
                    after_id = f"{profile_id}/g{tick}/needs-reset/after"
                    after_capture = f"{after_id}/capture"
                    try:
                        after = session.capture_state(after_id, after_capture)
                    except Exception as exc:
                        _retain_failure_without_masking(
                            record,
                            exc,
                            lifecycle=support.recorder.observations,
                            capture_site="driver.needs_reset.after_observer",
                            component_call_counts=session.call_counts,
                        )
                        raise
                    if session_module.canonical_snapshot_bytes(before) != (
                        session_module.canonical_snapshot_bytes(after)
                    ):
                        raise EvidenceDriverError(
                            "rejection_mutated_state", after_id
                        )
                    record.add_snapshot(
                        after_id,
                        after_capture,
                        tick,
                        0,
                        _require_mapping(after, "needs-reset after"),
                    )
                    record.add_needs_reset_probe(
                        probe_id=probe_id,
                        global_tick=tick,
                        before_ref=before_id,
                        after_ref=after_id,
                        component_call_delta=component_call_delta,
                    )
                reset_reason = (
                    "initial"
                    if tick == 0
                    else (
                        "needs_reset_recovery"
                        if profile_id.startswith("O")
                        else "scheduled_reset"
                    )
                )
                reset_before_id = f"{profile_id}/g{tick}/reset/before"
                reset_before_capture = f"{reset_before_id}/capture"
                try:
                    reset_before = session.capture_state(
                        reset_before_id, reset_before_capture
                    )
                except Exception as exc:
                    _retain_failure_without_masking(
                        record,
                        exc,
                        lifecycle=support.recorder.observations,
                        capture_site="driver.reset.before_observer",
                        component_call_counts=session.call_counts,
                    )
                    raise
                record.add_snapshot(
                    reset_before_id,
                    reset_before_capture,
                    tick,
                    0,
                    _require_mapping(reset_before, "reset before"),
                )
                try:
                    result = session.reset(tick, reason=reset_reason)
                except Exception as exc:
                    _retain_failure_without_masking(
                        record,
                        exc,
                        lifecycle=support.recorder.observations,
                        capture_site="integration_session.reset",
                        component_call_counts=session.call_counts,
                    )
                    raise
                reset_after_id = f"{profile_id}/g{tick}/reset/after"
                reset_after_capture = f"{reset_after_id}/capture"
                try:
                    reset_after = session.capture_state(
                        reset_after_id, reset_after_capture
                    )
                except Exception as exc:
                    _retain_failure_without_masking(
                        record,
                        exc,
                        lifecycle=support.recorder.observations,
                        capture_site="driver.reset.after_observer",
                        boundary_result=result,
                        component_call_counts=session.call_counts,
                    )
                    raise
                record.add_snapshot(
                    reset_after_id,
                    reset_after_capture,
                    tick,
                    0,
                    _require_mapping(reset_after, "reset after"),
                )
                try:
                    record.add_boundary(
                        result,
                        lifecycle=support.recorder.observations,
                        reset_before_ref=reset_before_id,
                        reset_after_ref=reset_after_id,
                    )
                except Exception as exc:
                    _retain_failure_without_masking(
                        record,
                        exc,
                        lifecycle=support.recorder.observations,
                        capture_site="driver.reset.materialize",
                        boundary_result=result,
                        component_call_counts=session.call_counts,
                    )
                    raise
            else:
                directive = _directive_for_tick(
                    profile_id, tick, old, session_module
                )
                requested_snapshot_id = None
                if tick in required_snapshot_ticks:
                    requested_snapshot_id = f"{profile_id}/g{tick}/required"
                    directive = session_module.TickDirective(
                        fault=directive.fault,
                        preflight_probes=directive.preflight_probes,
                        pre_estimator_probes=directive.pre_estimator_probes,
                        pre_controller_probes=directive.pre_controller_probes,
                        truth_estimator_probe_id=directive.truth_estimator_probe_id,
                        truth_controller_probe_id=directive.truth_controller_probe_id,
                        required_after_imu_snapshot_id=requested_snapshot_id,
                    )
                try:
                    result = session.advance(tick, directive=directive)
                except Exception as exc:
                    _retain_failure_without_masking(
                        record,
                        exc,
                        lifecycle=support.recorder.observations,
                        capture_site="integration_session.advance",
                        component_call_counts=session.call_counts,
                    )
                    raise
                required_after_ref = None
                required_capture = result.required_after_imu_capture
                try:
                    if requested_snapshot_id is not None:
                        if (
                            required_capture is None
                            or required_capture.snapshot_id != requested_snapshot_id
                            or required_capture.phase != 3
                        ):
                            raise EvidenceDriverError(
                                "required_snapshot_binding_mismatch",
                                f"{profile_id}:{tick}",
                            )
                        required_after_ref = record.add_snapshot(
                            required_capture.snapshot_id,
                            required_capture.capture_id,
                            tick,
                            required_capture.phase,
                            session_module.canonical_snapshot_value(
                                _require_internal_mapping(
                                    required_capture.functional_state,
                                    "required after-IMU snapshot",
                                )
                            ),
                        )
                    elif required_capture is not None:
                        raise EvidenceDriverError(
                            "unexpected_required_snapshot",
                            f"{profile_id}:{tick}",
                        )
                except Exception as exc:
                    _retain_failure_without_masking(
                        record,
                        exc,
                        lifecycle=support.recorder.observations,
                        capture_site="driver.required_materialize",
                        boundary_result=result,
                        component_call_counts=session.call_counts,
                    )
                    raise
                try:
                    record.add_boundary(
                        result,
                        lifecycle=support.recorder.observations,
                        required_after_ref=required_after_ref,
                    )
                except Exception as exc:
                    _retain_failure_without_masking(
                        record,
                        exc,
                        lifecycle=support.recorder.observations,
                        capture_site="driver.advance.materialize",
                        boundary_result=result,
                        component_call_counts=session.call_counts,
                    )
                    raise
                if profile_id == "L1" and tick == 998:
                    old = {
                        "held_torque": session.held_envelope,
                        "feedback": session.feedback_envelope,
                        "imu": session.last_sample_envelope,
                        "estimate": session.last_estimate_envelope,
                        "attitude_command": session.last_command_envelope,
                    }
                    if any(value is None for value in old.values()):
                        raise EvidenceDriverError("old_epoch_fixture_unavailable")
                if profile_id == "L1" and tick in {1002, 1004}:
                    by_role = {
                        "imu": next(
                            envelope
                            for envelope in result.wires
                            if envelope.role == "imu"
                            and envelope.producer == "measurement_adapter"
                        ),
                        "attitude_command": next(
                            envelope
                            for envelope in result.wires
                            if envelope.role == "attitude_command"
                            and envelope.producer == "command_sampler"
                        ),
                        "feedback": next(
                            envelope
                            for envelope in result.wires
                            if envelope.role == "feedback"
                            and envelope.producer == "actuator"
                        ),
                        "sensor_truth": next(
                            envelope
                            for envelope in result.wires
                            if envelope.role == "sensor_truth"
                        ),
                    }
                    replay_sources[tick] = by_role
        records.append(record)

    if shared_estimator_parameters is None or set(replay_sources) != {1002, 1004}:
        raise EvidenceDriverError("sealed_replay_fixture_unavailable")
    return records, g1_parameters, shared_estimator_parameters, replay_sources


def _estimator_snapshot(estimator: Any) -> dict[str, Any]:
    values = _ParameterRegistry.values("estimator", estimator._parameters)
    return {
        "_estimate": (
            None if estimator._estimate is None else _estimate(estimator._estimate)
        ),
        "_reset_epoch": (
            None
            if estimator._reset_epoch is None
            else _epoch(estimator._reset_epoch)
        ),
        "_last_tick": int(estimator._last_tick),
        "_rng_seed": int(estimator._rng_seed),
        "parameter_binding_sha256": _json_value_digest(values),
    }


def _observe_replay_snapshot(
    *,
    profile_id: str,
    snapshot_id: str,
    capture_id: str,
    observer_actor: str,
    observer_manifest_sha256: str,
    support: _LifecycleSupport,
    session_state: Mapping[str, Any],
    estimator: Any,
    controller: Any,
    canonicalize: Callable[[Any], Any],
) -> Mapping[str, Any]:
    token = support.recorder.begin(
        profile_id=profile_id,
        operation_id=snapshot_id,
        owner="observer",
        method="capture_snapshot",
        callsite="g3a_evidence_driver.capture_replay_snapshot",
        actor_id=observer_actor,
        core_use=None,
        arguments={
            "kind": "observer",
            "snapshot_id": snapshot_id,
            "capture_id": capture_id,
            "observer_manifest_sha256": observer_manifest_sha256,
        },
    )
    try:
        captured = canonicalize(
            {
                "session": dict(session_state),
                "plant": None,
                "actuator": None,
                "imu": None,
                "estimator": _estimator_snapshot(estimator),
                "controller": _controller_snapshot(controller),
            }
        )
    except Exception as exc:
        support.recorder.raised(token, exc)
        raise
    support.recorder.returned(
        token,
        result=_lifecycle_result(
            actor_id=observer_actor,
            snapshot_ref=snapshot_id,
            capture_id=capture_id,
        ),
    )
    return captured


def _observe_reset_call(
    *,
    profile_id: str,
    operation_id: str,
    owner: str,
    actor_id: str,
    callsite: str,
    reset_inputs: Mapping[str, Any],
    support: _LifecycleSupport,
    call: Callable[[], Any],
) -> Any:
    token = support.recorder.begin(
        profile_id=profile_id,
        operation_id=operation_id,
        owner=owner,
        method="reset",
        callsite=callsite,
        actor_id=actor_id,
        core_use=None,
        arguments=reset_inputs,
    )
    try:
        result = call()
    except Exception as exc:
        support.recorder.raised(token, exc)
        raise
    support.recorder.returned(
        token, result=_lifecycle_result(actor_id=actor_id)
    )
    return result


def _normal_guard_probe(
    *,
    probe_id: str,
    tick: int,
    phase: int,
    operation_id: str,
    checked_refs: Mapping[str, str],
    guard_site: str,
) -> dict[str, Any]:
    return {
        "probe_id": probe_id,
        "kind": "normal_guard",
        "global_tick": tick,
        "phase": phase,
        "consumer_operation_id": operation_id,
        "role": "input_bundle",
        "checked_refs": dict(checked_refs),
        "candidate_ref": None,
        "original_legal_ref": None,
        "source_truth_ref": None,
        "source_field": None,
        "target_field": None,
        "derivation_site": None,
        "guard_site": guard_site,
        "accepted": True,
        "reason": "accepted",
        "before_snapshot_ref": None,
        "after_snapshot_ref": None,
        "component_call_delta": _empty_count_delta(),
    }


def _replay_profiles(
    definition: Mapping[str, Any],
    dependencies: Mapping[str, Any],
    authority_identity: Mapping[str, Any],
    g1_parameters: Any,
    estimator_parameters: Any,
    replay_sources: Mapping[int, Mapping[str, Any]],
    record_sink: list[_ProfileRecord] | None = None,
) -> list[_ProfileRecord]:
    session_module = dependencies["session_module"]
    np = session_module.np
    simulation = dependencies["simulation"]
    estimator_module = dependencies["estimator_module"]
    adapter_module = dependencies["adapter_module"]
    controller_module = dependencies["controller_module"]
    support = dependencies["lifecycle_support"]
    scheduler = dependencies["scheduler_module"].IntegerScheduler.from_contract(
        dependencies["contract"]
    )
    records: list[_ProfileRecord] = []
    initial = definition["initial_inputs"]
    epoch_id = 1
    reset_tick = 1000
    reset_time = reset_tick * scheduler.base_period_s

    for profile_id in PROFILE_ORDER[6:]:
        profile = _profile(definition, profile_id)
        record = _ProfileRecord(
            profile,
            definition,
            np,
            session_module.canonical_snapshot_value,
        )
        if record_sink is not None:
            record_sink.append(record)
        record.initial_inputs.update(
            {
                "epoch_id": epoch_id,
                "epoch_origin_tick": reset_tick,
                "epoch_origin_s": _hex(reset_time),
            }
        )
        estimator, estimator_actor, actual_estimator_parameters, _, _ = (
            _construct_estimator(
                profile_id,
                estimator_module,
                support,
                shared_parameters=estimator_parameters,
            )
        )
        controller, controller_actor, _, _ = _construct_controller(
            profile_id,
            adapter_module,
            controller_module,
            authority_identity["controller_module_sha256"],
            support,
        )
        observer_actor = support.actors.new(profile_id, "observer")
        bindings = _configuration_bindings(
            scheduler,
            (),
            g1_parameters,
            actual_estimator_parameters,
            controller.parameters,
        )
        replay_counts = {
            "controller_reset_attempts": 0,
            "estimator_reset_attempts": 0,
            "estimator_process_attempts": 0,
            "estimator_process_accepted": 0,
            "estimator_process_rejected": 0,
            "controller_step_attempts": 0,
            "controller_step_accepted": 0,
            "controller_step_rejected": 0,
        }
        envelope_sequence = 0
        configuration_values = {
            "seed": SEED,
            "initial_epoch_id": epoch_id,
            "scenario_origin_s": _hex(reset_time),
            "plant_q_nb": record.initial_inputs["plant_q_nb"],
            "plant_omega_b_rad_s": record.initial_inputs[
                "plant_omega_b_rad_s"
            ],
            "estimator_q_nb": record.initial_inputs["estimator_q_nb"],
            "estimator_omega_b_rad_s": record.initial_inputs[
                "estimator_omega_b_rad_s"
            ],
            "actuator_actual_torque_body_Nm": record.initial_inputs[
                "actuator_actual_torque_body_Nm"
            ],
            **bindings,
        }
        replay_reset_before_id = f"{profile_id}/g{reset_tick}/reset/before"
        replay_reset_before_capture = f"{replay_reset_before_id}/capture"
        session_state: dict[str, Any] = {
            "lifecycle": "new",
            "needs_reset": False,
            "epoch_id": None,
            "epoch_origin_tick": None,
            "epoch_origin_s": None,
            "next_global_tick": reset_tick,
            "last_completed_global_tick": None,
            "phase_cursor": 0,
            "envelope_sequence": 0,
            "held": None,
            "feedback": None,
            "last_raw_sample": None,
            "last_sample": None,
            "last_estimate": None,
            "last_command": None,
            "last_plant_state": None,
            "last_truth": None,
            "last_event_ids": [],
            "last_event_state": None,
            "pending_publication": None,
            "pending_inputs": [],
            "pending_event_state": None,
            "configuration_values": configuration_values,
        }

        def replay_frontier(
            exc: Exception,
            *,
            tick: int,
            phase: int,
            boundary_kind: str,
            held_before_id: str | None,
            published_after_id: str | None,
            operations: Sequence[Mapping[str, Any]],
            guards: Sequence[Mapping[str, Any]],
            wires: Sequence[Any],
        ) -> dict[str, Any]:
            session_state["envelope_sequence"] = envelope_sequence
            return {
                "profile_id": profile_id,
                "global_tick": tick,
                "epoch_id": epoch_id,
                "epoch_origin_tick": reset_tick,
                "local_tick": tick - reset_tick,
                "epoch_origin_s": reset_time,
                "timestamp_s": (
                    reset_time
                    + (tick - reset_tick) * scheduler.base_period_s
                ),
                "boundary_kind": boundary_kind,
                "event_ids": (),
                "held_before_id": held_before_id,
                "published_after_id": published_after_id,
                "operations": tuple(operations),
                "guards": tuple(guards),
                "probes": (),
                "wires": tuple(wires),
                "component_call_counts": dict(replay_counts),
                "original_exception": _exception_observation(exc),
                "lifecycle_state": session_state["lifecycle"],
                "phase_cursor": phase,
                "termination_status": "driver_inconclusive",
            }

        def retain_replay_failure(
            exc: Exception,
            *,
            capture_site: str,
            tick: int,
            phase: int,
            boundary_kind: str,
            held_before_id: str | None,
            published_after_id: str | None,
            operations: Sequence[Mapping[str, Any]],
            guards: Sequence[Mapping[str, Any]],
            wires: Sequence[Any],
        ) -> None:
            _retain_failure_without_masking(
                record,
                exc,
                lifecycle=support.recorder.observations,
                capture_site=capture_site,
                component_call_counts=replay_counts,
                observed_frontier=replay_frontier(
                    exc,
                    tick=tick,
                    phase=phase,
                    boundary_kind=boundary_kind,
                    held_before_id=held_before_id,
                    published_after_id=published_after_id,
                    operations=operations,
                    guards=guards,
                    wires=wires,
                ),
            )

        reset_operations: list[dict[str, Any]] = []
        reset_wires: list[Any] = []
        try:
            replay_reset_before = _observe_replay_snapshot(
                profile_id=profile_id,
                snapshot_id=replay_reset_before_id,
                capture_id=replay_reset_before_capture,
                observer_actor=observer_actor,
                observer_manifest_sha256=authority_identity[
                    "observer_manifest_sha256"
                ],
                support=support,
                session_state=session_state,
                estimator=estimator,
                controller=controller,
                canonicalize=session_module.canonical_snapshot_value,
            )
        except Exception as exc:
            retain_replay_failure(
                exc,
                capture_site="driver.replay.reset.before_observer",
                tick=reset_tick,
                phase=0,
                boundary_kind="reset",
                held_before_id=None,
                published_after_id=None,
                operations=reset_operations,
                guards=(),
                wires=reset_wires,
            )
            raise
        record.add_snapshot(
            replay_reset_before_id,
            replay_reset_before_capture,
            reset_tick,
            0,
            _require_mapping(replay_reset_before, "replay reset before"),
        )

        def new_envelope(
            *,
            role: str,
            payload: Any,
            tick: int,
            phase: int,
            producer: str,
            operation_id: str | None,
            parents: Sequence[str] = (),
        ) -> Any:
            nonlocal envelope_sequence
            envelope_sequence += 1
            return session_module.EpochEnvelope(
                envelope_id=(
                    f"{profile_id}/e{epoch_id}/g{tick}/p{phase}/"
                    f"{role}/{envelope_sequence}"
                ),
                role=role,
                epoch_id=epoch_id,
                global_tick=tick,
                local_tick=tick - reset_tick,
                phase=phase,
                producer=producer,
                producer_operation_id=operation_id,
                parent_ids=tuple(parents),
                payload=payload,
            )

        controller_op = f"{profile_id}/g{reset_tick}/p0/controller-reset"
        controller_reset_inputs = {
            "kind": "reset",
            "actor": "controller",
            "reset_epoch": {"id": epoch_id, "timestamp_s": _hex(reset_time)},
        }
        controller_reset_operation = {
            "operation_id": controller_op,
            "owner": "controller",
            "method": "reset",
            "phase": 0,
            "attempt_kind": "reset",
            "inputs": {},
            "outputs": {},
            "scalar_inputs": {},
            "reset_inputs": controller_reset_inputs,
            "accepted": False,
            "reason": "component_call_incomplete",
            "before_snapshot_ref": None,
            "after_snapshot_ref": None,
            "guard_ref": None,
        }
        reset_operations.append(controller_reset_operation)
        replay_counts["controller_reset_attempts"] += 1
        try:
            reset_command = _observe_reset_call(
                profile_id=profile_id,
                operation_id=controller_op,
                owner="controller",
                actor_id=controller_actor,
                callsite="g3a_evidence_driver.replay.controller.reset",
                reset_inputs=controller_reset_inputs,
                support=support,
                call=lambda: controller.reset(
                    session_module.ResetEpochView(epoch_id, reset_time)
                ),
            )
        except Exception as exc:
            controller_reset_operation["reason"] = _exception_reason(exc)
            retain_replay_failure(
                exc,
                capture_site="driver.replay.controller.reset",
                tick=reset_tick,
                phase=0,
                boundary_kind="reset",
                held_before_id=None,
                published_after_id=None,
                operations=reset_operations,
                guards=(),
                wires=reset_wires,
            )
            raise
        held = new_envelope(
            role="held_torque",
            payload=reset_command,
            tick=reset_tick,
            phase=0,
            producer="controller_reset",
            operation_id=controller_op,
        )
        reset_wires.append(held)
        record.add_envelope(held)
        controller_reset_operation["outputs"] = {
            "torque_command": held.envelope_id
        }
        controller_reset_operation["accepted"] = True
        controller_reset_operation["reason"] = "accepted"
        estimator_op = f"{profile_id}/g{reset_tick}/p0/estimator-reset"
        estimator_initial = estimator_module.EstimatorInitialState(
            initial["estimator_q_nb"], initial["estimator_omega_b_rad_s"]
        )
        estimator_epoch = estimator_module.ResetEpoch(epoch_id, reset_time)
        estimator_reset_inputs = {
            "kind": "reset",
            "actor": "estimator",
            "initial_state": {
                "q_nb": _vec(estimator_initial.q_nb, 4, "estimator.reset.q_nb"),
                "omega_b_rad_s": _vec(
                    estimator_initial.omega_b_rad_s,
                    3,
                    "estimator.reset.omega_b_rad_s",
                ),
            },
            "reset_epoch": _epoch(estimator_epoch),
            "rng_seed": SEED,
        }
        estimator_reset_operation = {
            "operation_id": estimator_op,
            "owner": "estimator",
            "method": "reset",
            "phase": 0,
            "attempt_kind": "reset",
            "inputs": {},
            "outputs": {},
            "scalar_inputs": {},
            "reset_inputs": estimator_reset_inputs,
            "accepted": False,
            "reason": "component_call_incomplete",
            "before_snapshot_ref": None,
            "after_snapshot_ref": None,
            "guard_ref": None,
        }
        reset_operations.append(estimator_reset_operation)
        replay_counts["estimator_reset_attempts"] += 1
        try:
            reset_estimate = _observe_reset_call(
                profile_id=profile_id,
                operation_id=estimator_op,
                owner="estimator",
                actor_id=estimator_actor,
                callsite="g3a_evidence_driver.replay.estimator.reset",
                reset_inputs=estimator_reset_inputs,
                support=support,
                call=lambda: estimator.reset(
                    estimator_initial, estimator_epoch, SEED
                ),
            )
        except Exception as exc:
            estimator_reset_operation["reason"] = _exception_reason(exc)
            retain_replay_failure(
                exc,
                capture_site="driver.replay.estimator.reset",
                tick=reset_tick,
                phase=0,
                boundary_kind="reset",
                held_before_id=None,
                published_after_id=None,
                operations=reset_operations,
                guards=(),
                wires=reset_wires,
            )
            raise
        estimate_envelope = new_envelope(
            role="estimate",
            payload=reset_estimate,
            tick=reset_tick,
            phase=0,
            producer="estimator_reset",
            operation_id=estimator_op,
        )
        reset_wires.append(estimate_envelope)
        record.add_envelope(estimate_envelope)
        estimator_reset_operation["outputs"] = {
            "estimate": estimate_envelope.envelope_id
        }
        estimator_reset_operation["accepted"] = True
        estimator_reset_operation["reason"] = "accepted"
        session_state.update(
            {
                "lifecycle": "active",
                "epoch_id": epoch_id,
                "epoch_origin_tick": reset_tick,
                "epoch_origin_s": _hex(reset_time),
                # T is a restricted replay stream: the next retained boundary
                # is local tick 2, not an implied ordinary local tick 1.
                "next_global_tick": 1002,
                "last_completed_global_tick": reset_tick,
                "phase_cursor": 0,
                "envelope_sequence": envelope_sequence,
                "held": record.wire_by_id[held.envelope_id],
                "last_estimate": record.wire_by_id[estimate_envelope.envelope_id],
            }
        )

        def capture(
            snapshot_id: str,
            tick: int,
            phase: int,
            *,
            boundary_kind: str,
            held_before_id: str | None,
            published_after_id: str | None,
            operations: Sequence[Mapping[str, Any]],
            guards: Sequence[Mapping[str, Any]],
            wires: Sequence[Any],
        ) -> str:
            capture_id = f"{snapshot_id}/capture"
            session_state["envelope_sequence"] = envelope_sequence
            try:
                captured = _observe_replay_snapshot(
                    profile_id=profile_id,
                    snapshot_id=snapshot_id,
                    capture_id=capture_id,
                    observer_actor=observer_actor,
                    observer_manifest_sha256=authority_identity[
                        "observer_manifest_sha256"
                    ],
                    support=support,
                    session_state=session_state,
                    estimator=estimator,
                    controller=controller,
                    canonicalize=session_module.canonical_snapshot_value,
                )
                return record.add_snapshot(
                    snapshot_id,
                    capture_id,
                    tick,
                    phase,
                    _require_mapping(captured, "replay snapshot"),
                )
            except Exception as exc:
                retain_replay_failure(
                    exc,
                    capture_site="driver.replay.observer",
                    tick=tick,
                    phase=phase,
                    boundary_kind=boundary_kind,
                    held_before_id=held_before_id,
                    published_after_id=published_after_id,
                    operations=operations,
                    guards=guards,
                    wires=wires,
                )
                raise

        replay_reset_after_id = f"{profile_id}/g{reset_tick}/reset/after"
        capture(
            replay_reset_after_id,
            reset_tick,
            0,
            boundary_kind="reset",
            held_before_id=None,
            published_after_id=held.envelope_id,
            operations=reset_operations,
            guards=(),
            wires=reset_wires,
        )
        reset_operations[0]["before_snapshot_ref"] = replay_reset_before_id
        reset_operations[1]["after_snapshot_ref"] = replay_reset_after_id
        record.boundaries.append(
            {
                "global_tick": reset_tick,
                "epoch_id": epoch_id,
                "epoch_origin_tick": reset_tick,
                "local_tick": 0,
                "epoch_origin_s": _hex(reset_time),
                "timestamp_s": _hex(reset_time),
                "boundary_kind": "reset",
                "event_inputs": _event_inputs((), ()),
                "held_before_ref": None,
                "published_after_ref": held.envelope_id,
                "operations": reset_operations,
            }
        )

        def publish_replay_output(
            *,
            tick: int,
            output: Any,
            feedback: Any,
            sample: Any,
            estimate: Any,
            command: Any,
            truth: Any,
        ) -> dict[str, Any]:
            """Perform T's real session-local phase-6 held-state transition."""

            if session_state["phase_cursor"] != 5:
                raise EvidenceDriverError(
                    "replay_phase_cursor_mismatch",
                    f"{profile_id}:{tick}:{session_state['phase_cursor']}",
                )
            published_wire = record.wire_by_id[output.envelope_id]
            session_state["phase_cursor"] = 6
            session_state["pending_publication"] = published_wire
            session_state.update(
                {
                    "next_global_tick": {1002: 1004, 1004: 1005}[tick],
                    "last_completed_global_tick": tick,
                    "envelope_sequence": envelope_sequence,
                    "held": published_wire,
                    "feedback": record.wire_by_id[feedback.envelope_id],
                    "last_sample": record.wire_by_id[sample.envelope_id],
                    "last_estimate": record.wire_by_id[estimate.envelope_id],
                    "last_command": record.wire_by_id[command.envelope_id],
                    "last_truth": record.wire_by_id[truth.envelope_id],
                    "last_event_ids": [],
                    "last_event_state": None,
                    "pending_inputs": [],
                    "pending_event_state": None,
                    "pending_publication": None,
                }
            )
            publish_operation = f"{profile_id}/g{tick}/p6/publish"
            return {
                "operation_id": publish_operation,
                "owner": "session",
                "method": "publish",
                "phase": 6,
                "attempt_kind": "publication",
                "inputs": {"torque_command": output.envelope_id},
                "outputs": {"torque_command": output.envelope_id},
                "scalar_inputs": {},
                "reset_inputs": None,
                "accepted": True,
                "reason": "accepted",
                "before_snapshot_ref": None,
                "after_snapshot_ref": None,
                "guard_ref": None,
            }

        for tick in (1002, 1004):
            source = replay_sources[tick]
            local_tick = tick - reset_tick
            timestamp = reset_time + local_tick * scheduler.base_period_s
            sample = new_envelope(
                role="imu",
                payload=source["imu"].payload,
                tick=tick,
                phase=4,
                producer="sealed_replay",
                operation_id=None,
                parents=(source["imu"].envelope_id,),
            )
            command = new_envelope(
                role="attitude_command",
                payload=source["attitude_command"].payload,
                tick=tick,
                phase=5,
                producer="sealed_replay",
                operation_id=None,
                parents=(source["attitude_command"].envelope_id,),
            )
            feedback = new_envelope(
                role="feedback",
                payload=source["feedback"].payload,
                tick=tick,
                phase=5,
                producer="sealed_replay",
                operation_id=None,
                parents=(source["feedback"].envelope_id,),
            )
            source_truth = source["sensor_truth"].payload
            truth_q = source_truth.q_nb
            if profile_id == "T2":
                truth_q = _hamilton(
                    truth_q,
                    _offset_quaternion(
                        profile["evaluator_truth_copy"]["attitude_offset_rad"],
                        np,
                    ),
                    np,
                )
            truth_payload = simulation.SensorTruth(
                truth_q,
                source_truth.omega_b_rad_s,
                source_truth.acceleration_n_m_s2,
            )
            truth = new_envelope(
                role="sensor_truth",
                payload=truth_payload,
                tick=tick,
                phase=3,
                producer="evaluator_truth",
                operation_id=None,
                parents=(source["sensor_truth"].envelope_id,),
            )
            for envelope in (sample, command, feedback, truth):
                record.add_envelope(envelope)
            record.wire_by_id[truth.envelope_id]["producer_field"] = (
                str(profile["evaluator_truth_copy"]["source_locator"])
            )
            held_before = held
            boundary_operations: list[dict[str, Any]] = []
            boundary_guards: list[dict[str, Any]] = []
            boundary_wires: list[Any] = [sample, command, feedback, truth]
            session_state.update(
                {
                    "phase_cursor": 4,
                    "pending_inputs": [
                        record.wire_by_id[sample.envelope_id],
                        record.wire_by_id[command.envelope_id],
                        record.wire_by_id[feedback.envelope_id],
                    ],
                    "pending_event_state": None,
                }
            )

            def retain_tick_failure(
                exc: Exception,
                *,
                capture_site: str,
                phase: int,
                published_after_id: str | None = None,
            ) -> None:
                retain_replay_failure(
                    exc,
                    capture_site=capture_site,
                    tick=tick,
                    phase=phase,
                    boundary_kind="ordinary",
                    held_before_id=held_before.envelope_id,
                    published_after_id=published_after_id,
                    operations=boundary_operations,
                    guards=boundary_guards,
                    wires=boundary_wires,
                )

            estimator_operation = f"{profile_id}/g{tick}/p4/estimator-process"
            estimator_guard = f"{estimator_operation}/guard/1"
            estimator_guard_record = {
                "guard_id": estimator_guard,
                "global_tick": tick,
                "phase": 4,
                "consumer_operation_id": estimator_operation,
                "role": "input_bundle",
                "checked_refs": {"imu": sample.envelope_id},
                "candidate_id": None,
                "site": "estimator.consume.input_bundle",
                "accepted": False,
                "reason": "guard_incomplete",
            }
            boundary_guards.append(estimator_guard_record)
            try:
                session_module.guard_input_bundle(
                    (session_module.GuardedInput("imu", sample),),
                    active_epoch_id=epoch_id,
                    consumer="estimator",
                )
            except Exception as exc:
                estimator_guard_record["reason"] = _exception_reason(exc)
                retain_tick_failure(
                    exc,
                    capture_site="driver.replay.estimator.guard",
                    phase=4,
                )
                raise
            estimator_guard_record["accepted"] = True
            estimator_guard_record["reason"] = "accepted"
            record.probes.append(
                _normal_guard_probe(
                    probe_id=estimator_guard,
                    tick=tick,
                    phase=4,
                    operation_id=estimator_operation,
                    checked_refs={"adapted_imu": sample.envelope_id},
                    guard_site="estimator.consume.input_bundle",
                )
            )
            estimator_operation_record = {
                "operation_id": estimator_operation,
                "owner": "estimator",
                "method": "process",
                "phase": 4,
                "attempt_kind": "normal",
                "inputs": {"adapted_imu": sample.envelope_id},
                "outputs": {},
                "scalar_inputs": {},
                "reset_inputs": None,
                "accepted": False,
                "reason": "component_call_incomplete",
                "before_snapshot_ref": None,
                "after_snapshot_ref": None,
                "guard_ref": estimator_guard,
            }
            boundary_operations.append(estimator_operation_record)
            replay_counts["estimator_process_attempts"] += 1
            try:
                estimator_result = estimator.process(sample.payload)
            except Exception as exc:
                estimator_operation_record["reason"] = _exception_reason(exc)
                retain_tick_failure(
                    exc,
                    capture_site="driver.replay.estimator.process",
                    phase=4,
                )
                raise
            if not estimator_result.diagnostics.accepted:
                replay_counts["estimator_process_rejected"] += 1
                estimator_operation_record["reason"] = str(
                    estimator_result.diagnostics.reason
                )
                error = EvidenceDriverError(
                    "sealed_replay_estimator_rejected",
                    str(estimator_result.diagnostics.reason),
                )
                retain_tick_failure(
                    error,
                    capture_site="driver.replay.estimator.process",
                    phase=4,
                )
                raise error
            replay_counts["estimator_process_accepted"] += 1
            estimate_envelope = new_envelope(
                role="estimate",
                payload=estimator_result.estimate,
                tick=tick,
                phase=4,
                producer="estimator",
                operation_id=estimator_operation,
                parents=(sample.envelope_id,),
            )
            estimator_diagnostics = new_envelope(
                role="estimator_diagnostics",
                payload=estimator_result.diagnostics,
                tick=tick,
                phase=4,
                producer="estimator",
                operation_id=estimator_operation,
                parents=(sample.envelope_id,),
            )
            boundary_wires.extend((estimate_envelope, estimator_diagnostics))
            record.add_envelope(estimate_envelope)
            record.add_envelope(estimator_diagnostics)
            estimator_operation_record["outputs"] = {
                "estimate": estimate_envelope.envelope_id,
                "estimator_diagnostics": estimator_diagnostics.envelope_id,
            }
            estimator_operation_record["accepted"] = True
            estimator_operation_record["reason"] = "accepted"
            controller_operation = f"{profile_id}/g{tick}/p5/controller-step"
            controller_guard = f"{controller_operation}/guard/1"
            session_state["phase_cursor"] = 5
            controller_guard_record = {
                "guard_id": controller_guard,
                "global_tick": tick,
                "phase": 5,
                "consumer_operation_id": controller_operation,
                "role": "input_bundle",
                "checked_refs": {
                    "attitude_command": command.envelope_id,
                    "estimate": estimate_envelope.envelope_id,
                    "feedback": feedback.envelope_id,
                },
                "candidate_id": None,
                "site": "controller.consume.input_bundle",
                "accepted": False,
                "reason": "guard_incomplete",
            }
            boundary_guards.append(controller_guard_record)
            try:
                session_module.guard_input_bundle(
                    (
                        session_module.GuardedInput("attitude_command", command),
                        session_module.GuardedInput("estimate", estimate_envelope),
                        session_module.GuardedInput("feedback", feedback),
                    ),
                    active_epoch_id=epoch_id,
                    consumer="controller",
                )
            except Exception as exc:
                controller_guard_record["reason"] = _exception_reason(exc)
                retain_tick_failure(
                    exc,
                    capture_site="driver.replay.controller.guard",
                    phase=5,
                )
                raise
            controller_guard_record["accepted"] = True
            controller_guard_record["reason"] = "accepted"
            record.probes.append(
                _normal_guard_probe(
                    probe_id=controller_guard,
                    tick=tick,
                    phase=5,
                    operation_id=controller_operation,
                    checked_refs={
                        "attitude_command": command.envelope_id,
                        "estimate": estimate_envelope.envelope_id,
                        "feedback": feedback.envelope_id,
                    },
                    guard_site="controller.consume.input_bundle",
                )
            )
            controller_operation_record = {
                "operation_id": controller_operation,
                "owner": "controller",
                "method": "step",
                "phase": 5,
                "attempt_kind": "normal",
                "inputs": {
                    "attitude_command": command.envelope_id,
                    "estimate": estimate_envelope.envelope_id,
                    "feedback": feedback.envelope_id,
                },
                "outputs": {},
                "scalar_inputs": {
                    "dt_s": _hex(
                        scheduler.controller_every_ticks
                        * scheduler.base_period_s
                    )
                },
                "reset_inputs": None,
                "accepted": False,
                "reason": "component_call_incomplete",
                "before_snapshot_ref": None,
                "after_snapshot_ref": None,
                "guard_ref": controller_guard,
            }
            boundary_operations.append(controller_operation_record)
            replay_counts["controller_step_attempts"] += 1
            try:
                output_payload = controller.step(
                    command.payload,
                    estimate_envelope.payload,
                    feedback.payload,
                    scheduler.controller_every_ticks * scheduler.base_period_s,
                )
            except Exception as exc:
                controller_operation_record["reason"] = _exception_reason(exc)
                retain_tick_failure(
                    exc,
                    capture_site="driver.replay.controller.step",
                    phase=5,
                )
                raise
            replay_counts["controller_step_accepted"] += 1
            output = new_envelope(
                role="held_torque",
                payload=output_payload,
                tick=tick,
                phase=5,
                producer="controller",
                operation_id=controller_operation,
                parents=(
                    command.envelope_id,
                    estimate_envelope.envelope_id,
                    feedback.envelope_id,
                ),
            )
            boundary_wires.append(output)
            record.add_envelope(output)
            controller_operation_record["outputs"] = {
                "torque_command": output.envelope_id
            }
            controller_operation_record["accepted"] = True
            controller_operation_record["reason"] = "accepted"
            try:
                actual_controller_diagnostics = controller.core.last_diagnostics()
            except Exception as exc:
                retain_tick_failure(
                    exc,
                    capture_site="driver.replay.controller.diagnostics",
                    phase=5,
                )
                raise
            controller_diagnostics = new_envelope(
                role="controller_diagnostics",
                payload=actual_controller_diagnostics,
                tick=tick,
                phase=5,
                producer="controller",
                operation_id=controller_operation,
                parents=(output.envelope_id,),
            )
            boundary_wires.append(controller_diagnostics)
            record.add_envelope(controller_diagnostics)
            controller_operation_record["outputs"][
                "controller_diagnostics"
            ] = controller_diagnostics.envelope_id
            try:
                publish_operation = publish_replay_output(
                    tick=tick,
                    output=output,
                    feedback=feedback,
                    sample=sample,
                    estimate=estimate_envelope,
                    command=command,
                    truth=truth,
                )
            except Exception as exc:
                retain_tick_failure(
                    exc,
                    capture_site="driver.replay.publish",
                    phase=6,
                )
                raise
            boundary_operations.append(publish_operation)
            required_ref = capture(
                f"{profile_id}/g{tick}/required",
                tick,
                6,
                boundary_kind="ordinary",
                held_before_id=held_before.envelope_id,
                published_after_id=output.envelope_id,
                operations=boundary_operations,
                guards=boundary_guards,
                wires=boundary_wires,
            )
            publish_operation["after_snapshot_ref"] = required_ref
            record.boundaries.append(
                {
                    "global_tick": tick,
                    "epoch_id": epoch_id,
                    "epoch_origin_tick": reset_tick,
                    "local_tick": local_tick,
                    "epoch_origin_s": _hex(reset_time),
                    "timestamp_s": _hex(timestamp),
                    "boundary_kind": "ordinary",
                    "event_inputs": _event_inputs((), ()),
                    "held_before_ref": held_before.envelope_id,
                    "published_after_ref": output.envelope_id,
                    "operations": boundary_operations,
                }
            )
            held = output
        records.append(record)
    return records


def _total_counts(profiles: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    auxiliary_keys = sorted(
        {
            key
            for profile in profiles
            for key in profile["reported_counts"]
            if key not in COUNT_KEYS
        }
    )
    keys = (*COUNT_KEYS, *auxiliary_keys)
    return {
        key: sum(int(profile["reported_counts"].get(key, 0)) for profile in profiles)
        for key in keys
    }


def _raw_document(
    *,
    identity: Mapping[str, Any],
    support: _LifecycleSupport | None,
    profiles: Sequence[Mapping[str, Any]],
    completion: str,
    termination_reason: str | None,
) -> dict[str, Any]:
    normalized_identity = dict(identity)
    for key, value in tuple(normalized_identity.items()):
        if key.endswith("sha256") and isinstance(value, str):
            normalized_identity[key] = value.lower()
    return {
        "schema_version": EVIDENCE_VERSION,
        "identity": normalized_identity,
        "conventions": dict(CONVENTIONS),
        "completion": completion,
        "termination_reason": termination_reason,
        "parameter_objects": (
            [] if support is None else list(support.parameters.entries)
        ),
        "lifecycle_observations": (
            [] if support is None else list(support.recorder.observations)
        ),
        "profiles": list(profiles),
        "reported_counts": _total_counts(profiles),
    }


def _failure_sidecar_document(
    *,
    identity: Mapping[str, Any],
    support: _LifecycleSupport | None,
    records: Sequence[_ProfileRecord],
    primary_exception: Exception,
) -> dict[str, Any]:
    retention_incomplete = any(
        record.retention_failures
        or any(
            frontier.get("retention_status") == "incomplete"
            for frontier in record.failure_frontiers
        )
        for record in records
    )
    return {
        "sidecar_version": "b0-g3a-failure-frontier/v1",
        "completion": "partial",
        "retention_status": (
            "incomplete" if retention_incomplete else "complete"
        ),
        "identity": dict(identity),
        "primary_exception": _first_exception_observation(primary_exception),
        "lifecycle_observations": (
            [] if support is None else list(support.recorder.observations)
        ),
        "profiles": [
            {
                "profile_id": str(record.profile["profile_id"]),
                "failure_frontiers": list(record.failure_frontiers),
                "retention_failures": list(record.retention_failures),
            }
            for record in records
            if record.failure_frontiers or record.retention_failures
        ],
        "not_complete_evidence": True,
    }


def run_g3a_evidence_batch(
    module_dir: Path,
    build_type: str,
    output_root: Path,
    run_id: str,
    authority_path: Path,
) -> dict[str, Any]:
    """Run the fixed eight-profile batch and retain one immutable raw record."""

    if not isinstance(run_id, str) or RUN_ID_PATTERN.fullmatch(run_id) is None:
        raise EvidenceDriverError("invalid_run_id")
    if build_type not in {"Debug", "Release"}:
        raise EvidenceDriverError("invalid_build_type", str(build_type))
    module_directory = Path(module_dir)
    output_parent = Path(output_root)
    authority_file = Path(authority_path)
    if not module_directory.is_absolute() or not module_directory.is_dir():
        raise EvidenceDriverError("module_directory_invalid", str(module_directory))
    if not output_parent.is_absolute() or not output_parent.is_dir():
        raise EvidenceDriverError("output_root_invalid", str(output_parent))
    if not authority_file.is_absolute() or not authority_file.is_file():
        raise EvidenceDriverError("authority_unavailable", str(authority_file))

    try:
        profile_bytes = PROFILE_PATH.read_bytes()
    except OSError as exc:
        raise EvidenceDriverError(
            "input_unavailable", f"{PROFILE_PATH}: {exc}"
        ) from exc
    definition = _validate_definition(_json_bytes(profile_bytes, PROFILE_PATH))
    profile_sha256 = _sha256_bytes(profile_bytes)
    module_path = _find_controller_module_path(module_directory.resolve())
    authority = _validate_authority(
        _json(authority_file),
        profile_sha256=profile_sha256,
        module_path=module_path,
        build_type=build_type,
    )
    identity = _require_mapping(authority["identity"], "authority.identity")
    planned_auxiliary_keys = _authority_auxiliary_keys(authority)
    run_directory = output_parent / run_id
    try:
        run_directory.mkdir(exist_ok=False)
    except OSError as exc:
        raise EvidenceDriverError(
            "output_directory_creation_failed", f"{run_directory}: {exc}"
        ) from exc
    raw_directory = run_directory / "raw"
    try:
        raw_directory.mkdir(exist_ok=False)
    except OSError as exc:
        raise EvidenceDriverError(
            "output_directory_creation_failed", f"{raw_directory}: {exc}"
        ) from exc
    raw_path = raw_directory / "g3a-evidence.json"
    failure_sidecar_path = raw_directory / "g3a-failure-frontier.json"
    support: _LifecycleSupport | None = None
    record_objects: list[_ProfileRecord] = []
    materialized_profiles: list[dict[str, Any]] = []
    try:
        session_module = _load_python_file(
            "b0_g3a_integration_session", SESSION_PATH
        )
        support = _LifecycleSupport(
            session_module.LifecycleRecorder(id_prefix="g3a")
        )
        dependencies = _load_dependencies(
            module_directory.resolve(),
            session_module=session_module,
            support=support,
        )
        live, g1_parameters, estimator_parameters, replay_sources = _live_profiles(
            definition,
            dependencies,
            identity,
            record_objects,
        )
        replay = _replay_profiles(
            definition,
            dependencies,
            identity,
            g1_parameters,
            estimator_parameters,
            replay_sources,
            record_objects,
        )
        records = [*live, *replay]
        lifecycle = support.recorder.observations
        for record in records:
            profile_id = str(record.profile["profile_id"])
            counts = _profile_counts(
                record,
                lifecycle,
                planned_auxiliary_keys[profile_id],
            )
            materialized_profiles.append(record.materialize(counts))
        if [profile["profile_id"] for profile in materialized_profiles] != list(
            PROFILE_ORDER
        ):
            raise EvidenceDriverError("profile_order_mismatch")
        raw = _raw_document(
            identity=identity,
            support=support,
            profiles=materialized_profiles,
            completion="complete",
            termination_reason=None,
        )
        raw_sha256 = _write_json_exclusive(raw_path, raw)
    except Exception as exc:
        try:
            if support is not None:
                lifecycle = support.recorder.observations
                materialized_profiles = [
                    record.materialize(
                        _profile_counts(
                            record,
                            lifecycle,
                            planned_auxiliary_keys[
                                str(record.profile["profile_id"])
                            ],
                            enforce_auxiliary_plan=False,
                        )
                    )
                    for record in record_objects
                ]
        except Exception as retention_exc:
            exc.add_note(
                "secondary partial materialization failure retained: "
                f"{type(retention_exc).__name__}: {retention_exc}"
            )
        partial_reason = f"{type(exc).__name__}: {exc}"
        partial = _raw_document(
            identity=identity,
            support=support,
            profiles=materialized_profiles,
            completion="partial",
            termination_reason=partial_reason,
        )
        try:
            if not failure_sidecar_path.exists():
                _write_json_exclusive(
                    failure_sidecar_path,
                    _failure_sidecar_document(
                        identity=identity,
                        support=support,
                        records=record_objects,
                        primary_exception=exc,
                    ),
                )
        except Exception as retention_exc:
            exc.add_note(
                "secondary failure-sidecar write failure retained: "
                f"{type(retention_exc).__name__}: {retention_exc}"
            )
        try:
            if not raw_path.exists():
                _write_json_exclusive(raw_path, partial)
        except Exception as retention_exc:
            exc.add_note(
                "secondary partial artifact failure retained: "
                f"{type(retention_exc).__name__}: {retention_exc}"
            )
        raise
    return {
        "status": "complete",
        "classification": CLASSIFICATION,
        "run_id": run_id,
        "build_type": build_type,
        "seed": SEED,
        "raw_path": str(raw_path),
        "raw_sha256": raw_sha256,
        "profile_order": list(PROFILE_ORDER),
        "reported_counts": raw["reported_counts"],
        "transport_binding_required": True,
    }


__all__ = ["EvidenceDriverError", "run_g3a_evidence_batch"]
