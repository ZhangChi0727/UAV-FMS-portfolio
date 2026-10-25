"""Author-side structural accounting for a G3-A raw record set.

This module is intentionally not the independent evidence oracle described by
``g3a_evidence_spec.md``.  It checks serialization hygiene, stable references,
and the author-declared operation/count ledger so malformed recorder output is
rejected before independent review.  It does not import the DUT, derive due
ticks, apply numerical tolerances, compare builds, or grant G3-A acceptance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence


REPORT_VERSION = "b0-g3a-author-runtime-check/v1"
EVIDENCE_VERSION = "b0-g3a-evidence/v1"
PROFILE_ORDER = ("S", "L1", "L2", "O1", "O2", "E", "T1", "T2")
CLASSIFICATION = "development_integration_not_normal_acceptance"
SEED = 2026100900

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

TOP_LEVEL_KEYS = {
    "schema_version",
    "identity",
    "conventions",
    "completion",
    "termination_reason",
    "parameter_objects",
    "lifecycle_observations",
    "profiles",
    "reported_counts",
}
PROFILE_KEYS = {
    "profile_id",
    "horizon_tick",
    "reset_ticks",
    "initial_inputs",
    "wires",
    "boundaries",
    "probes",
    "snapshots",
    "reported_counts",
}
FLOAT_HEX = re.compile(r"^-?0x(?:[01]\.[0-9a-f]{13}p[+-][0-9]+|0\.0p\+0)$")
SHA256 = re.compile(r"^[0-9A-Fa-f]{64}$")

PARAMETER_OBJECT_KEYS = {
    "parameter_object_id",
    "kind",
    "capture_kind",
    "values_sha256",
    "values",
}
LIFECYCLE_KEYS = {
    "observation_index",
    "call_id",
    "parent_call_id",
    "profile_id",
    "operation_id",
    "owner",
    "method",
    "event",
    "callsite",
    "actor_id",
    "core_use",
    "arguments",
    "result",
    "exception",
}
_CONSTRUCTOR_OWNER_TO_COUNTER = {
    "plant": "plant_constructor",
    "actuator": "actuator_constructor",
    "imu": "imu_constructor",
    "estimator": "estimator_constructor",
    "controller": "controller_adapter_constructor",
    "controller_core": "controller_core_constructor",
}
_RESET_OWNER_TO_COUNTER = {
    "plant": "plant_reset",
    "actuator": "actuator_reset",
    "imu": "imu_reset",
    "estimator": "estimator_reset",
    "controller": "controller_reset",
}

LIFECYCLE_OWNERS = {
    "plant",
    "actuator",
    "imu",
    "estimator",
    "controller",
    "controller_core",
    "g1_parameters",
    "estimator_parameters",
    "controller_parameters",
    "g1_loader",
    "estimator_loader",
    "controller_loader",
    "g0_validator",
    "observer",
    "session",
}
LIFECYCLE_METHODS = {
    "constructor",
    "load_parameters",
    "load_config",
    "validate_config",
    "capture_snapshot",
    "reset",
}
CONSTRUCTOR_ARGUMENT_KEYS = {
    "kind",
    "mode",
    "parameter_object_ref",
    "module_sha256",
}
CONFIG_ARGUMENT_KEYS = {
    "kind",
    "actual_argument_kind",
    "path_argument",
    "source_artifact_ref",
    "source_bytes_sha256",
    "document_sha256",
}
OBSERVER_ARGUMENT_KEYS = {
    "kind",
    "snapshot_id",
    "capture_id",
    "observer_manifest_sha256",
}
LIFECYCLE_RESULT_KEYS = {
    "actor_id",
    "parameter_object_ref",
    "snapshot_ref",
    "capture_id",
    "resolved_config_path",
    "source_bytes_sha256",
    "document_sha256",
}
LIFECYCLE_EXCEPTION_KEYS = {"type", "reason", "message"}


class RuntimeRecordError(ValueError):
    """One author-side recorder/accounting failure."""

    def __init__(self, reason: str, path: str, detail: str = "") -> None:
        self.reason = reason
        self.path = path
        self.detail = detail
        message = f"{reason} at {path}"
        if detail:
            message += f": {detail}"
        super().__init__(message)


def _duplicate_reject(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RuntimeRecordError("duplicate_json_key", "/", key)
        result[key] = value
    return result


def _nonstandard_constant(token: str) -> None:
    raise RuntimeRecordError("nonstandard_json_number", "/", token)


def _decode(payload: bytes, source: str) -> Any:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeRecordError("invalid_utf8", source, str(exc)) from exc
    try:
        return json.loads(
            text,
            object_pairs_hook=_duplicate_reject,
            parse_constant=_nonstandard_constant,
        )
    except RuntimeRecordError:
        raise
    except (
        json.JSONDecodeError,
        TypeError,
        ValueError,
        OverflowError,
        RecursionError,
    ) as exc:
        raise RuntimeRecordError("invalid_json", source, str(exc)) from exc


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeRecordError("expected_object", path)
    return value


def _array(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise RuntimeRecordError("expected_array", path)
    return value


def _integer(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RuntimeRecordError("expected_nonnegative_integer", path)
    return value


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeRecordError("expected_nonempty_string", path)
    return value


def _exact_keys(value: Mapping[str, Any], expected: set[str], path: str) -> None:
    actual = set(value)
    if actual != expected:
        raise RuntimeRecordError(
            "object_keys_mismatch",
            path,
            f"missing={sorted(expected - actual)!r}; extra={sorted(actual - expected)!r}",
        )


def _walk_number_encoding(value: Any, path: str = "") -> None:
    if isinstance(value, float):
        raise RuntimeRecordError("json_float_not_hex_string", path or "/")
    if isinstance(value, str):
        if value in {"nan", "inf", "-inf"}:
            raise RuntimeRecordError("nonfinite_float_token", path or "/")
        if value.startswith(("0x", "-0x")) and not FLOAT_HEX.fullmatch(value):
            raise RuntimeRecordError("noncanonical_float_hex", path or "/", value)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _walk_number_encoding(item, f"{path}/{index}")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _walk_number_encoding(item, f"{path}/{key}")


def _counts(value: Any, path: str) -> dict[str, int]:
    mapping = _mapping(value, path)
    missing = set(COUNT_KEYS) - set(mapping)
    if missing:
        raise RuntimeRecordError(
            "counter_keys_mismatch",
            path,
            f"missing={sorted(missing)!r}",
        )
    result: dict[str, int] = {}
    for key, value_item in mapping.items():
        if not isinstance(key, str) or not key:
            raise RuntimeRecordError("counter_key_invalid", path, repr(key))
        if key not in COUNT_KEYS:
            if key == "operation:actuator:step":
                pass
            elif key.startswith("lifecycle:"):
                suffix = key[len("lifecycle:"):]
                try:
                    site, event = suffix.rsplit(":", 1)
                except ValueError as exc:
                    raise RuntimeRecordError(
                        "counter_key_invalid", f"{path}/{key}"
                    ) from exc
                if not site or event not in {"enter", "return", "exception"}:
                    raise RuntimeRecordError(
                        "counter_key_invalid", f"{path}/{key}"
                    )
            elif key.startswith("guard:"):
                suffix = key[len("guard:"):]
                try:
                    site, event = suffix.rsplit(":", 1)
                except ValueError as exc:
                    raise RuntimeRecordError(
                        "counter_key_invalid", f"{path}/{key}"
                    ) from exc
                if not site or not event:
                    raise RuntimeRecordError(
                        "counter_key_invalid", f"{path}/{key}"
                    )
            else:
                raise RuntimeRecordError(
                    "counter_key_invalid", f"{path}/{key}"
                )
        result[key] = _integer(value_item, f"{path}/{key}")
    return result


def _component_count_delta(value: Any, path: str) -> dict[str, int]:
    mapping = _mapping(value, path)
    expected = set(COMPONENT_COUNT_KEYS)
    if set(mapping) != expected:
        raise RuntimeRecordError(
            "component_counter_keys_mismatch",
            path,
            f"missing={sorted(expected - set(mapping))!r}; "
            f"extra={sorted(set(mapping) - expected)!r}",
        )
    return {
        key: _integer(mapping[key], f"{path}/{key}")
        for key in COMPONENT_COUNT_KEYS
    }


def _unique(identifier: str, seen: set[str], path: str) -> None:
    if identifier in seen:
        raise RuntimeRecordError("duplicate_identifier", path, identifier)
    seen.add(identifier)


def _iter_ref_values(value: Any, path: str) -> Iterable[tuple[str, str]]:
    if value is None:
        return
    mapping = _mapping(value, path)
    for key, item in mapping.items():
        yield _string(item, f"{path}/{key}"), f"{path}/{key}"


def _nullable_string(value: Any, path: str) -> str | None:
    if value is None:
        return None
    return _string(value, path)


def _parameter_objects(value: Any) -> dict[str, dict[str, str]]:
    entries = _array(value, "/parameter_objects")
    identifiers: set[str] = set()
    registry: dict[str, dict[str, str]] = {}
    for index, item in enumerate(entries):
        path = f"/parameter_objects/{index}"
        entry = _mapping(item, path)
        _exact_keys(entry, PARAMETER_OBJECT_KEYS, path)
        identifier = _string(
            entry.get("parameter_object_id"), f"{path}/parameter_object_id"
        )
        _unique(identifier, identifiers, f"{path}/parameter_object_id")
        if entry.get("kind") not in {"g1", "estimator", "controller"}:
            raise RuntimeRecordError(
                "parameter_kind_mismatch", f"{path}/kind", str(entry.get("kind"))
            )
        if entry.get("capture_kind") not in {
            "object_values",
            "constructor_fields",
        }:
            raise RuntimeRecordError(
                "parameter_capture_kind_mismatch",
                f"{path}/capture_kind",
                str(entry.get("capture_kind")),
            )
        values = _mapping(entry.get("values"), f"{path}/values")
        declared = _string(entry.get("values_sha256"), f"{path}/values_sha256")
        if SHA256.fullmatch(declared) is None:
            raise RuntimeRecordError(
                "parameter_digest_invalid", f"{path}/values_sha256", declared
            )
        encoded = json.dumps(
            values,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        actual = hashlib.sha256(encoded).hexdigest()
        if declared.lower() != actual:
            raise RuntimeRecordError(
                "parameter_digest_mismatch",
                f"{path}/values_sha256",
                f"{declared.lower()} != {actual}",
            )
        registry[identifier] = {
            "kind": str(entry["kind"]),
            "capture_kind": str(entry["capture_kind"]),
            "values_sha256": actual,
        }
    return registry


def _walk_parameter_references(
    value: Any,
    parameter_objects: Mapping[str, Mapping[str, str]],
    path: str,
) -> None:
    if isinstance(value, list):
        for index, item in enumerate(value):
            _walk_parameter_references(item, parameter_objects, f"{path}/{index}")
        return
    if not isinstance(value, dict):
        return
    for key, item in value.items():
        item_path = f"{path}/{key}"
        if key in {
            "parameter_object_id",
            "parameter_object_ref",
            "parameter_ref",
        } and item is not None:
            reference = _string(item, item_path)
            if reference not in parameter_objects:
                raise RuntimeRecordError(
                    "unresolved_parameter_reference", item_path, reference
                )
        _walk_parameter_references(item, parameter_objects, item_path)


def _nullable_sha256(value: Any, path: str) -> str | None:
    if value is None:
        return None
    text = _string(value, path)
    if SHA256.fullmatch(text) is None:
        raise RuntimeRecordError("expected_sha256", path, text)
    return text.lower()


def _float64_string(value: Any, path: str) -> str:
    text = _string(value, path)
    if FLOAT_HEX.fullmatch(text) is None:
        raise RuntimeRecordError("expected_float64_hex", path, text)
    return text


def _fixed_vector(value: Any, length: int, path: str) -> list[str]:
    items = _array(value, path)
    if len(items) != length:
        raise RuntimeRecordError(
            "vector_length_mismatch", path, f"{len(items)} != {length}"
        )
    return [
        _float64_string(item, f"{path}/{index}")
        for index, item in enumerate(items)
    ]


def _epoch(value: Any, path: str) -> Mapping[str, Any]:
    epoch = _mapping(value, path)
    _exact_keys(epoch, {"id", "timestamp_s"}, path)
    _integer(epoch.get("id"), f"{path}/id")
    _float64_string(epoch.get("timestamp_s"), f"{path}/timestamp_s")
    return epoch


def _rotation_initial_state(value: Any, path: str) -> Mapping[str, Any]:
    state = _mapping(value, path)
    _exact_keys(state, {"q_nb", "omega_b_rad_s"}, path)
    _fixed_vector(state.get("q_nb"), 4, f"{path}/q_nb")
    _fixed_vector(state.get("omega_b_rad_s"), 3, f"{path}/omega_b_rad_s")
    return state


def _empty_initial_state(value: Any, path: str) -> None:
    state = _mapping(value, path)
    _exact_keys(state, set(), path)


def _reset_arguments(
    observation: Mapping[str, Any],
    arguments: Mapping[str, Any],
    path: str,
) -> None:
    owner = observation["owner"]
    actor = arguments.get("actor")
    if arguments.get("kind") != "reset" or actor != owner:
        raise RuntimeRecordError(
            "lifecycle_reset_actor_mismatch", f"{path}/arguments/actor"
        )
    argument_path = f"{path}/arguments"
    if actor == "controller":
        _exact_keys(arguments, {"kind", "actor", "reset_epoch"}, argument_path)
        _epoch(arguments.get("reset_epoch"), f"{argument_path}/reset_epoch")
    elif actor == "controller_core":
        _exact_keys(
            arguments,
            {"kind", "actor", "initial_state", "reset_epoch"},
            argument_path,
        )
        _empty_initial_state(
            arguments.get("initial_state"), f"{argument_path}/initial_state"
        )
        _epoch(arguments.get("reset_epoch"), f"{argument_path}/reset_epoch")
    elif actor == "plant":
        _exact_keys(
            arguments,
            {"kind", "actor", "initial_state", "reset_epoch_s"},
            argument_path,
        )
        _rotation_initial_state(
            arguments.get("initial_state"), f"{argument_path}/initial_state"
        )
        _float64_string(
            arguments.get("reset_epoch_s"), f"{argument_path}/reset_epoch_s"
        )
    elif actor == "actuator":
        _exact_keys(
            arguments,
            {
                "kind",
                "actor",
                "initial_state",
                "reset_epoch_s",
                "reset_command_ref",
            },
            argument_path,
        )
        state_path = f"{argument_path}/initial_state"
        state = _mapping(arguments.get("initial_state"), state_path)
        _exact_keys(
            state,
            {
                "actual_torque_body_Nm",
                "held_limited_torque_body_Nm",
                "held_requested_torque_body_Nm",
                "held_saturated",
                "held_command_timestamp_s",
            },
            state_path,
        )
        for field in (
            "actual_torque_body_Nm",
            "held_limited_torque_body_Nm",
            "held_requested_torque_body_Nm",
        ):
            _fixed_vector(state.get(field), 3, f"{state_path}/{field}")
        flags = _array(state.get("held_saturated"), f"{state_path}/held_saturated")
        if len(flags) != 3 or any(type(flag) is not bool for flag in flags):
            raise RuntimeRecordError(
                "flags_shape_mismatch", f"{state_path}/held_saturated"
            )
        command_timestamp = state.get("held_command_timestamp_s")
        if command_timestamp is not None:
            _float64_string(
                command_timestamp, f"{state_path}/held_command_timestamp_s"
            )
        _float64_string(
            arguments.get("reset_epoch_s"), f"{argument_path}/reset_epoch_s"
        )
        _string(
            arguments.get("reset_command_ref"),
            f"{argument_path}/reset_command_ref",
        )
    elif actor == "imu":
        _exact_keys(
            arguments,
            {"kind", "actor", "initial_state", "reset_epoch_s", "rng_seed"},
            argument_path,
        )
        _empty_initial_state(
            arguments.get("initial_state"), f"{argument_path}/initial_state"
        )
        _float64_string(
            arguments.get("reset_epoch_s"), f"{argument_path}/reset_epoch_s"
        )
        if _integer(arguments.get("rng_seed"), f"{argument_path}/rng_seed") != SEED:
            raise RuntimeRecordError(
                "reset_seed_mismatch", f"{argument_path}/rng_seed"
            )
    elif actor == "estimator":
        _exact_keys(
            arguments,
            {"kind", "actor", "initial_state", "reset_epoch", "rng_seed"},
            argument_path,
        )
        _rotation_initial_state(
            arguments.get("initial_state"), f"{argument_path}/initial_state"
        )
        _epoch(arguments.get("reset_epoch"), f"{argument_path}/reset_epoch")
        if _integer(arguments.get("rng_seed"), f"{argument_path}/rng_seed") != SEED:
            raise RuntimeRecordError(
                "reset_seed_mismatch", f"{argument_path}/rng_seed"
            )
    else:
        raise RuntimeRecordError(
            "lifecycle_reset_actor_mismatch", f"{argument_path}/actor", str(actor)
        )


def _enter_arguments(
    observation: Mapping[str, Any], path: str
) -> Mapping[str, Any]:
    method = observation["method"]
    owner = observation["owner"]
    allowed_owners = {
        "constructor": {
            "plant",
            "actuator",
            "imu",
            "estimator",
            "controller",
            "controller_core",
            "g1_parameters",
            "estimator_parameters",
            "controller_parameters",
        },
        "load_parameters": {
            "g1_loader",
            "estimator_loader",
            "controller_loader",
        },
        "load_config": {"g0_validator"},
        "validate_config": {"g0_validator"},
        "capture_snapshot": {"observer"},
        "reset": {
            "plant",
            "actuator",
            "imu",
            "estimator",
            "controller",
            "controller_core",
        },
    }
    if owner not in allowed_owners.get(str(method), set()):
        raise RuntimeRecordError(
            "lifecycle_method_owner_mismatch", f"{path}/owner", str(owner)
        )
    core_use = observation.get("core_use")
    if owner == "controller_core":
        expected_core_uses = (
            {"temporary_validation", "production"}
            if method == "constructor"
            else {"production"}
        )
        if core_use not in expected_core_uses:
            raise RuntimeRecordError(
                "lifecycle_core_use_mismatch", f"{path}/core_use", str(core_use)
            )
    elif core_use is not None:
        raise RuntimeRecordError(
            "lifecycle_core_use_mismatch", f"{path}/core_use", str(core_use)
        )
    arguments = _mapping(observation.get("arguments"), f"{path}/arguments")
    kind = arguments.get("kind")
    if method == "constructor":
        _exact_keys(arguments, CONSTRUCTOR_ARGUMENT_KEYS, f"{path}/arguments")
        if kind != "constructor":
            raise RuntimeRecordError(
                "lifecycle_argument_kind_mismatch", f"{path}/arguments/kind"
            )
        if arguments.get("mode") not in {
            "explicit_parameters",
            "parameter_fields",
            "default_loader",
            "controller_module",
            "empty",
        }:
            raise RuntimeRecordError(
                "constructor_mode_mismatch", f"{path}/arguments/mode"
            )
        _nullable_string(
            arguments.get("parameter_object_ref"),
            f"{path}/arguments/parameter_object_ref",
        )
        _nullable_sha256(
            arguments.get("module_sha256"), f"{path}/arguments/module_sha256"
        )
    elif method == "load_parameters":
        if kind != "loader" or "supplied_args" not in arguments:
            raise RuntimeRecordError(
                "lifecycle_argument_kind_mismatch", f"{path}/arguments"
            )
        supplied = _array(arguments["supplied_args"], f"{path}/arguments/supplied_args")
        if any(
            type(item) is not str
            or item not in {"config_path", "module", "track"}
            for item in supplied
        ) or len(set(supplied)) != len(supplied):
            raise RuntimeRecordError(
                "loader_supplied_args_mismatch", f"{path}/arguments/supplied_args"
            )
        allowed = {"kind", "supplied_args", "config_path", "track", "module_sha256"}
        if not set(arguments).issubset(allowed):
            raise RuntimeRecordError(
                "object_keys_mismatch", f"{path}/arguments"
            )
        for supplied_name, value_name in (
            ("config_path", "config_path"),
            ("track", "track"),
            ("module", "module_sha256"),
        ):
            if (supplied_name in supplied) != (value_name in arguments):
                raise RuntimeRecordError(
                    "loader_argument_presence_mismatch",
                    f"{path}/arguments/{value_name}",
                )
        for field in ("config_path", "track"):
            if field in arguments:
                _nullable_string(arguments[field], f"{path}/arguments/{field}")
        if "module_sha256" in arguments:
            _nullable_sha256(
                arguments["module_sha256"], f"{path}/arguments/module_sha256"
            )
    elif method in {"load_config", "validate_config"}:
        _exact_keys(arguments, CONFIG_ARGUMENT_KEYS, f"{path}/arguments")
        if kind != "config":
            raise RuntimeRecordError(
                "lifecycle_argument_kind_mismatch", f"{path}/arguments/kind"
            )
        expected_argument_kind = "path" if method == "load_config" else "document"
        if arguments.get("actual_argument_kind") != expected_argument_kind:
            raise RuntimeRecordError(
                "config_argument_kind_mismatch",
                f"{path}/arguments/actual_argument_kind",
            )
        for field in ("path_argument", "source_artifact_ref"):
            _nullable_string(arguments.get(field), f"{path}/arguments/{field}")
        for field in ("source_bytes_sha256", "document_sha256"):
            _nullable_sha256(arguments.get(field), f"{path}/arguments/{field}")
    elif method == "capture_snapshot":
        _exact_keys(arguments, OBSERVER_ARGUMENT_KEYS, f"{path}/arguments")
        if kind != "observer":
            raise RuntimeRecordError(
                "lifecycle_argument_kind_mismatch", f"{path}/arguments/kind"
            )
        _string(arguments.get("snapshot_id"), f"{path}/arguments/snapshot_id")
        _string(arguments.get("capture_id"), f"{path}/arguments/capture_id")
        observer_sha = _nullable_sha256(
            arguments.get("observer_manifest_sha256"),
            f"{path}/arguments/observer_manifest_sha256",
        )
        if observer_sha is None:
            raise RuntimeRecordError(
                "expected_sha256", f"{path}/arguments/observer_manifest_sha256"
            )
    elif method == "reset":
        _reset_arguments(observation, arguments, path)
    else:
        raise RuntimeRecordError(
            "lifecycle_method_mismatch", f"{path}/method", str(method)
        )
    return arguments


def _lifecycle_result(value: Any, path: str) -> Mapping[str, Any]:
    result = _mapping(value, path)
    _exact_keys(result, LIFECYCLE_RESULT_KEYS, path)
    for field in (
        "actor_id",
        "parameter_object_ref",
        "snapshot_ref",
        "capture_id",
        "resolved_config_path",
    ):
        _nullable_string(result.get(field), f"{path}/{field}")
    for field in ("source_bytes_sha256", "document_sha256"):
        _nullable_sha256(result.get(field), f"{path}/{field}")
    return result


def _result_fields(
    result: Mapping[str, Any],
    *,
    allowed_nonnull: set[str],
    path: str,
) -> None:
    for field in LIFECYCLE_RESULT_KEYS - allowed_nonnull:
        if result.get(field) is not None:
            raise RuntimeRecordError(
                "lifecycle_result_field_mismatch", f"{path}/{field}"
            )


def _parameter_metadata(
    reference: Any,
    parameter_objects: Mapping[str, Mapping[str, str]],
    *,
    path: str,
    kind: str,
    capture_kind: str,
) -> Mapping[str, str]:
    identifier = _string(reference, path)
    metadata = parameter_objects.get(identifier)
    if metadata is None:
        raise RuntimeRecordError("unresolved_parameter_reference", path, identifier)
    if metadata.get("kind") != kind:
        raise RuntimeRecordError(
            "parameter_kind_binding_mismatch",
            path,
            f"{metadata.get('kind')!r} != {kind!r}",
        )
    if metadata.get("capture_kind") != capture_kind:
        raise RuntimeRecordError(
            "parameter_capture_binding_mismatch",
            path,
            f"{metadata.get('capture_kind')!r} != {capture_kind!r}",
        )
    return metadata


def _lifecycle_parameter_binding(
    entered: Mapping[str, Any],
    result: Mapping[str, Any],
    parameter_objects: Mapping[str, Mapping[str, str]],
    path: str,
) -> None:
    owner = str(entered["owner"])
    method = str(entered["method"])
    arguments = _mapping(entered.get("arguments"), f"{path}/entered_arguments")
    result_path = f"{path}/result"
    result_ref = result.get("parameter_object_ref")

    if method == "load_parameters":
        kind_by_owner = {
            "g1_loader": "g1",
            "estimator_loader": "estimator",
            "controller_loader": "controller",
        }
        kind = kind_by_owner.get(owner)
        if kind is None:
            raise RuntimeRecordError(
                "loader_owner_mismatch", f"{path}/owner", owner
            )
        _parameter_metadata(
            result_ref,
            parameter_objects,
            path=f"{result_path}/parameter_object_ref",
            kind=kind,
            capture_kind="object_values",
        )
        _result_fields(
            result,
            allowed_nonnull={"actor_id", "parameter_object_ref"},
            path=result_path,
        )
        return

    if method != "constructor":
        if result_ref is not None:
            raise RuntimeRecordError(
                "unexpected_parameter_result",
                f"{result_path}/parameter_object_ref",
            )
        return

    mode = arguments.get("mode")
    input_ref = arguments.get("parameter_object_ref")
    paired_input: Mapping[str, str] | None = None
    expected_result: tuple[str, str] | None = None
    if owner in {"plant", "actuator", "imu"}:
        if mode != "explicit_parameters":
            raise RuntimeRecordError("constructor_mode_mismatch", f"{path}/mode")
        paired_input = _parameter_metadata(
            input_ref,
            parameter_objects,
            path=f"{path}/arguments/parameter_object_ref",
            kind="g1",
            capture_kind="object_values",
        )
        expected_result = ("g1", "object_values")
    elif owner == "g1_parameters":
        if mode != "parameter_fields":
            raise RuntimeRecordError("constructor_mode_mismatch", f"{path}/mode")
        paired_input = _parameter_metadata(
            input_ref,
            parameter_objects,
            path=f"{path}/arguments/parameter_object_ref",
            kind="g1",
            capture_kind="constructor_fields",
        )
        expected_result = ("g1", "object_values")
    elif owner == "estimator_parameters":
        if mode != "parameter_fields":
            raise RuntimeRecordError("constructor_mode_mismatch", f"{path}/mode")
        paired_input = _parameter_metadata(
            input_ref,
            parameter_objects,
            path=f"{path}/arguments/parameter_object_ref",
            kind="estimator",
            capture_kind="constructor_fields",
        )
        expected_result = ("estimator", "object_values")
    elif owner == "estimator":
        if mode not in {"default_loader", "explicit_parameters"}:
            raise RuntimeRecordError("constructor_mode_mismatch", f"{path}/mode")
        if mode == "default_loader":
            if input_ref is not None:
                raise RuntimeRecordError(
                    "constructor_parameter_presence_mismatch",
                    f"{path}/arguments/parameter_object_ref",
                )
        else:
            paired_input = _parameter_metadata(
                input_ref,
                parameter_objects,
                path=f"{path}/arguments/parameter_object_ref",
                kind="estimator",
                capture_kind="object_values",
            )
        expected_result = ("estimator", "object_values")
    elif owner == "controller":
        if mode != "controller_module" or input_ref is not None:
            raise RuntimeRecordError("constructor_mode_mismatch", f"{path}/mode")
        expected_result = ("controller", "object_values")
    elif owner == "controller_parameters":
        if mode != "empty" or input_ref is not None or result_ref is not None:
            raise RuntimeRecordError("constructor_mode_mismatch", f"{path}/mode")
    elif owner == "controller_core":
        if (
            mode != "explicit_parameters"
            or entered.get("core_use") not in {"temporary_validation", "production"}
        ):
            raise RuntimeRecordError("constructor_mode_mismatch", f"{path}/mode")
        _parameter_metadata(
            input_ref,
            parameter_objects,
            path=f"{path}/arguments/parameter_object_ref",
            kind="controller",
            capture_kind="object_values",
        )
        if result_ref is not None:
            raise RuntimeRecordError(
                "unexpected_parameter_result",
                f"{result_path}/parameter_object_ref",
            )
    else:
        raise RuntimeRecordError(
            "constructor_owner_mismatch", f"{path}/owner", owner
        )

    result_metadata: Mapping[str, str] | None = None
    if expected_result is not None:
        result_metadata = _parameter_metadata(
            result_ref,
            parameter_objects,
            path=f"{result_path}/parameter_object_ref",
            kind=expected_result[0],
            capture_kind=expected_result[1],
        )
    if paired_input is not None and result_metadata is not None:
        if paired_input["values_sha256"] != result_metadata["values_sha256"]:
            raise RuntimeRecordError(
                "constructor_parameter_value_mismatch",
                f"{result_path}/parameter_object_ref",
            )
    allowed = {"actor_id"}
    if expected_result is not None:
        allowed.add("parameter_object_ref")
    _result_fields(result, allowed_nonnull=allowed, path=result_path)


def _lifecycle_exception(value: Any, path: str) -> Mapping[str, Any]:
    exception = _mapping(value, path)
    _exact_keys(exception, LIFECYCLE_EXCEPTION_KEYS, path)
    _string(exception.get("type"), f"{path}/type")
    _nullable_string(exception.get("reason"), f"{path}/reason")
    if not isinstance(exception.get("message"), str):
        raise RuntimeRecordError("expected_string", f"{path}/message")
    return exception


def _lifecycle(
    value: Any,
    parameter_objects: Mapping[str, Mapping[str, str]],
) -> tuple[
    dict[str, dict[str, int]],
    dict[str, int],
    list[dict[str, Any]],
    dict[tuple[str, str, str], Mapping[str, Any]],
]:
    observations = _array(value, "/lifecycle_observations")
    open_calls: dict[str, Mapping[str, Any]] = {}
    completed_calls: set[str] = set()
    stack: list[str] = []
    by_profile = {
        profile_id: {key: 0 for key in COUNT_KEYS}
        for profile_id in PROFILE_ORDER
    }
    event_counts: dict[str, int] = {}
    links: list[dict[str, Any]] = []
    reset_arguments: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    pending_config: dict[tuple[str | None, str | None], Mapping[str, Any]] = {}
    validate_config_sources: dict[str, Mapping[str, Any]] = {}
    parameter_evidence_by_parent: dict[str, list[str]] = {}

    for index, item in enumerate(observations):
        path = f"/lifecycle_observations/{index}"
        observation = _mapping(item, path)
        _exact_keys(observation, LIFECYCLE_KEYS, path)
        if _integer(
            observation.get("observation_index"), f"{path}/observation_index"
        ) != index:
            raise RuntimeRecordError(
                "lifecycle_index_mismatch", f"{path}/observation_index"
            )
        call_id = _string(observation.get("call_id"), f"{path}/call_id")
        parent_call_id = _nullable_string(
            observation.get("parent_call_id"), f"{path}/parent_call_id"
        )
        profile_id = _nullable_string(
            observation.get("profile_id"), f"{path}/profile_id"
        )
        if profile_id is not None and profile_id not in PROFILE_ORDER:
            raise RuntimeRecordError(
                "lifecycle_profile_mismatch", f"{path}/profile_id", profile_id
            )
        _nullable_string(observation.get("operation_id"), f"{path}/operation_id")
        owner = _string(observation.get("owner"), f"{path}/owner")
        method = _string(observation.get("method"), f"{path}/method")
        event = _string(observation.get("event"), f"{path}/event")
        if owner not in LIFECYCLE_OWNERS:
            raise RuntimeRecordError(
                "lifecycle_owner_mismatch", f"{path}/owner", owner
            )
        if method not in LIFECYCLE_METHODS:
            raise RuntimeRecordError(
                "lifecycle_method_mismatch", f"{path}/method", method
            )
        callsite = _string(observation.get("callsite"), f"{path}/callsite")
        actor_id = _nullable_string(
            observation.get("actor_id"), f"{path}/actor_id"
        )
        core_use = _nullable_string(
            observation.get("core_use"), f"{path}/core_use"
        )
        if core_use not in {None, "temporary_validation", "production"}:
            raise RuntimeRecordError(
                "lifecycle_core_use_mismatch", f"{path}/core_use", str(core_use)
            )
        _walk_parameter_references(observation, parameter_objects, path)
        event_key = f"{owner}.{method}.{event}"
        event_counts[event_key] = event_counts.get(event_key, 0) + 1
        charged_profile = "S" if profile_id is None else profile_id
        lifecycle_key = f"lifecycle:{callsite}:{event}"
        by_profile[charged_profile][lifecycle_key] = (
            by_profile[charged_profile].get(lifecycle_key, 0) + 1
        )

        if event == "enter":
            arguments = _enter_arguments(observation, path)
            if call_id in open_calls or call_id in completed_calls:
                raise RuntimeRecordError(
                    "lifecycle_duplicate_call", f"{path}/call_id", call_id
                )
            expected_parent = stack[-1] if stack else None
            if parent_call_id != expected_parent:
                raise RuntimeRecordError(
                    "lifecycle_parent_mismatch",
                    f"{path}/parent_call_id",
                    f"{parent_call_id!r} != {expected_parent!r}",
                )
            if method == "reset" and owner == "controller_core":
                if parent_call_id is None or parent_call_id not in open_calls:
                    raise RuntimeRecordError(
                        "core_reset_parent_missing", f"{path}/parent_call_id"
                    )
                parent_reset = open_calls[parent_call_id]
                parent_arguments = _mapping(
                    parent_reset.get("arguments"),
                    f"{path}/parent_reset_arguments",
                )
                if (
                    parent_reset.get("owner") != "controller"
                    or parent_reset.get("method") != "reset"
                    or parent_reset.get("profile_id") != profile_id
                    or parent_reset.get("operation_id")
                    != observation.get("operation_id")
                    or parent_arguments.get("reset_epoch")
                    != arguments.get("reset_epoch")
                ):
                    raise RuntimeRecordError(
                        "core_reset_parent_mismatch", f"{path}/parent_call_id"
                    )
            if observation.get("result") is not None or observation.get("exception") is not None:
                raise RuntimeRecordError("lifecycle_enter_payload_mismatch", path)
            if method == "validate_config":
                config_key = (parent_call_id, actor_id)
                source = pending_config.pop(config_key, None)
                if source is None:
                    raise RuntimeRecordError(
                        "config_validation_source_missing", f"{path}/arguments"
                    )
                expected_bindings = {
                    "path_argument": None,
                    "source_artifact_ref": source["source_artifact_ref"],
                    "source_bytes_sha256": source["source_bytes_sha256"],
                    "document_sha256": source["document_sha256"],
                }
                for field, expected_value in expected_bindings.items():
                    if arguments.get(field) != expected_value:
                        raise RuntimeRecordError(
                            "config_validation_source_mismatch",
                            f"{path}/arguments/{field}",
                        )
                validate_config_sources[call_id] = source
            open_calls[call_id] = observation
            stack.append(call_id)
            if (
                method == "reset"
                and owner != "controller_core"
                and profile_id is not None
                and observation.get("operation_id") is not None
            ):
                key = (profile_id, str(observation["operation_id"]), owner)
                if key in reset_arguments:
                    raise RuntimeRecordError(
                        "duplicate_lifecycle_reset", path, repr(key)
                    )
                reset_arguments[key] = arguments
            continue

        if event not in {"return", "exception"}:
            raise RuntimeRecordError("lifecycle_event_mismatch", f"{path}/event", event)
        if observation.get("arguments") is not None:
            raise RuntimeRecordError(
                "lifecycle_terminal_arguments_mismatch", f"{path}/arguments"
            )
        if not stack or stack[-1] != call_id or call_id not in open_calls:
            raise RuntimeRecordError(
                "lifecycle_terminal_order_mismatch", f"{path}/call_id", call_id
            )
        entered = open_calls[call_id]
        for field in (
            "parent_call_id",
            "profile_id",
            "operation_id",
            "owner",
            "method",
            "callsite",
            "actor_id",
            "core_use",
        ):
            if observation.get(field) != entered.get(field):
                raise RuntimeRecordError(
                    "lifecycle_terminal_identity_mismatch", f"{path}/{field}"
                )
        if event == "return":
            if observation.get("exception") is not None:
                raise RuntimeRecordError("lifecycle_return_payload_mismatch", path)
            result = _lifecycle_result(
                observation.get("result"), f"{path}/result"
            )
            if result.get("actor_id") != actor_id:
                raise RuntimeRecordError(
                    "lifecycle_actor_result_mismatch", f"{path}/result/actor_id"
                )
            _lifecycle_parameter_binding(
                entered, result, parameter_objects, path
            )
            entered_arguments = _mapping(
                entered.get("arguments"), f"{path}/entered_arguments"
            )
            result_parameter_ref = result.get("parameter_object_ref")
            result_parameter_digest = (
                None
                if result_parameter_ref is None
                else parameter_objects[str(result_parameter_ref)]["values_sha256"]
            )
            if method == "load_parameters":
                if result_parameter_digest not in parameter_evidence_by_parent.get(
                    call_id, []
                ):
                    raise RuntimeRecordError(
                        "loader_parameter_source_mismatch",
                        f"{path}/result/parameter_object_ref",
                    )
            if method == "constructor" and (
                (owner == "estimator" and entered_arguments.get("mode") == "default_loader")
                or (owner == "controller" and entered_arguments.get("mode") == "controller_module")
            ):
                if result_parameter_digest not in parameter_evidence_by_parent.get(
                    call_id, []
                ):
                    raise RuntimeRecordError(
                        "constructor_parameter_source_mismatch",
                        f"{path}/result/parameter_object_ref",
                    )
            if method == "capture_snapshot":
                if (
                    result.get("snapshot_ref")
                    != entered_arguments.get("snapshot_id")
                    or result.get("capture_id")
                    != entered_arguments.get("capture_id")
                ):
                    raise RuntimeRecordError(
                        "observer_result_binding_mismatch", f"{path}/result"
                    )
                _result_fields(
                    result,
                    allowed_nonnull={"actor_id", "snapshot_ref", "capture_id"},
                    path=f"{path}/result",
                )
            elif method == "reset":
                _result_fields(
                    result,
                    allowed_nonnull={"actor_id"},
                    path=f"{path}/result",
                )
            elif method == "load_config":
                _string(
                    entered_arguments.get("source_artifact_ref"),
                    f"{path}/entered_arguments/source_artifact_ref",
                )
                if entered_arguments.get("document_sha256") is not None:
                    raise RuntimeRecordError(
                        "config_load_argument_mismatch",
                        f"{path}/entered_arguments/document_sha256",
                    )
                required_bindings = {
                    "resolved_config_path": entered_arguments.get("path_argument"),
                    "source_bytes_sha256": entered_arguments.get(
                        "source_bytes_sha256"
                    ),
                }
                for field, expected_value in required_bindings.items():
                    if expected_value is None or result.get(field) != expected_value:
                        raise RuntimeRecordError(
                            "config_load_result_mismatch", f"{path}/result/{field}"
                        )
                if result.get("document_sha256") is None:
                    raise RuntimeRecordError(
                        "config_load_result_mismatch",
                        f"{path}/result/document_sha256",
                    )
                _result_fields(
                    result,
                    allowed_nonnull={
                        "actor_id",
                        "resolved_config_path",
                        "source_bytes_sha256",
                        "document_sha256",
                    },
                    path=f"{path}/result",
                )
                config_key = (
                    entered.get("parent_call_id"),
                    entered.get("actor_id"),
                )
                if config_key in pending_config:
                    raise RuntimeRecordError(
                        "config_load_without_validation", path
                    )
                pending_config[config_key] = {
                    "source_artifact_ref": entered_arguments.get(
                        "source_artifact_ref"
                    ),
                    "resolved_config_path": result["resolved_config_path"],
                    "source_bytes_sha256": result["source_bytes_sha256"],
                    "document_sha256": result["document_sha256"],
                }
            elif method == "validate_config":
                source = validate_config_sources.pop(call_id, None)
                if source is None:
                    raise RuntimeRecordError(
                        "config_validation_source_missing", path
                    )
                for field in (
                    "resolved_config_path",
                    "source_bytes_sha256",
                    "document_sha256",
                ):
                    if result.get(field) != source.get(field):
                        raise RuntimeRecordError(
                            "config_validation_result_mismatch",
                            f"{path}/result/{field}",
                        )
                _result_fields(
                    result,
                    allowed_nonnull={
                        "actor_id",
                        "resolved_config_path",
                        "source_bytes_sha256",
                        "document_sha256",
                    },
                    path=f"{path}/result",
                )
            links.append(
                {
                    "path": path,
                    "profile_id": profile_id,
                    "operation_id": observation.get("operation_id"),
                    "method": method,
                    "snapshot_ref": result.get("snapshot_ref"),
                    "capture_id": result.get("capture_id"),
                }
            )
            parent = entered.get("parent_call_id")
            if parent is not None:
                child_digests = parameter_evidence_by_parent.setdefault(
                    str(parent), []
                )
                input_parameter_ref = entered_arguments.get(
                    "parameter_object_ref"
                )
                if input_parameter_ref is not None:
                    child_digests.append(
                        parameter_objects[str(input_parameter_ref)][
                            "values_sha256"
                        ]
                    )
                if result_parameter_digest is not None:
                    child_digests.append(result_parameter_digest)
        else:
            if observation.get("result") is not None:
                raise RuntimeRecordError("lifecycle_exception_payload_mismatch", path)
            _lifecycle_exception(
                observation.get("exception"), f"{path}/exception"
            )
        stack.pop()
        open_calls.pop(call_id)
        completed_calls.add(call_id)

        if event != "return" or profile_id is None:
            continue
        if method == "constructor" and owner in _CONSTRUCTOR_OWNER_TO_COUNTER:
            by_profile[profile_id][_CONSTRUCTOR_OWNER_TO_COUNTER[owner]] += 1
        if method == "reset" and owner in _RESET_OWNER_TO_COUNTER:
            by_profile[profile_id][_RESET_OWNER_TO_COUNTER[owner]] += 1

    if stack or open_calls:
        raise RuntimeRecordError(
            "lifecycle_unmatched_call",
            "/lifecycle_observations",
            ",".join(stack),
        )
    if pending_config or validate_config_sources:
        raise RuntimeRecordError(
            "config_lifecycle_unmatched",
            "/lifecycle_observations",
        )
    return by_profile, event_counts, links, reset_arguments


def _reconstruct_profile(
    profile: Mapping[str, Any],
    path: str,
    lifecycle_counts: Mapping[str, int],
    reset_arguments: Mapping[tuple[str, str, str], Mapping[str, Any]],
    allowed_external_parents: Mapping[str, Mapping[str, Any]],
) -> dict[str, int]:
    result = {key: 0 for key in COUNT_KEYS}
    operations: list[Mapping[str, Any]] = []
    seen_operations: set[str] = set()
    seen_wires: set[str] = set()
    wire_by_id: dict[str, Mapping[str, Any]] = {}
    seen_snapshots: set[str] = set()
    seen_probes: set[str] = set()

    wires = _array(profile["wires"], f"{path}/wires")
    for index, item in enumerate(wires):
        wire_path = f"{path}/wires/{index}"
        wire = _mapping(item, wire_path)
        wire_id = _string(wire.get("wire_id"), f"{wire_path}/wire_id")
        _unique(wire_id, seen_wires, f"{wire_path}/wire_id")
        wire_by_id[wire_id] = wire

    snapshots = _array(profile["snapshots"], f"{path}/snapshots")
    for index, item in enumerate(snapshots):
        snapshot_path = f"{path}/snapshots/{index}"
        snapshot = _mapping(item, snapshot_path)
        snapshot_id = _string(snapshot.get("snapshot_id"), f"{snapshot_path}/snapshot_id")
        _unique(snapshot_id, seen_snapshots, f"{snapshot_path}/snapshot_id")

    boundaries = _array(profile["boundaries"], f"{path}/boundaries")
    previous_tick: int | None = None
    for boundary_index, item in enumerate(boundaries):
        boundary_path = f"{path}/boundaries/{boundary_index}"
        boundary = _mapping(item, boundary_path)
        tick = _integer(boundary.get("global_tick"), f"{boundary_path}/global_tick")
        if previous_tick is not None and tick < previous_tick:
            raise RuntimeRecordError("boundary_order_mismatch", boundary_path)
        previous_tick = tick
        for field in ("held_before_ref", "published_after_ref"):
            ref = boundary.get(field)
            if ref is not None and _string(ref, f"{boundary_path}/{field}") not in seen_wires:
                raise RuntimeRecordError("unresolved_wire_reference", f"{boundary_path}/{field}", str(ref))
        boundary_operations = _array(boundary.get("operations"), f"{boundary_path}/operations")
        previous_phase = -1
        current_operations: list[Mapping[str, Any]] = []
        for operation_index, operation_value in enumerate(boundary_operations):
            operation_path = f"{boundary_path}/operations/{operation_index}"
            operation = _mapping(operation_value, operation_path)
            operation_id = _string(operation.get("operation_id"), f"{operation_path}/operation_id")
            _unique(operation_id, seen_operations, f"{operation_path}/operation_id")
            phase = _integer(operation.get("phase"), f"{operation_path}/phase")
            if phase > 6 or phase < previous_phase:
                raise RuntimeRecordError("operation_phase_order_mismatch", operation_path)
            previous_phase = phase
            operations.append(operation)
            current_operations.append(operation)
        actuator_resets = [
            operation
            for operation in current_operations
            if operation.get("owner") == "actuator"
            and operation.get("method") == "reset"
        ]
        if actuator_resets:
            controller_resets = [
                operation
                for operation in current_operations
                if operation.get("owner") == "controller"
                and operation.get("method") == "reset"
            ]
            if len(actuator_resets) != 1 or len(controller_resets) != 1:
                raise RuntimeRecordError(
                    "actuator_reset_command_source_mismatch", boundary_path
                )
            controller_outputs = _mapping(
                controller_resets[0].get("outputs"),
                f"{boundary_path}/controller-reset/outputs",
            )
            controller_command_ref = _string(
                controller_outputs.get("torque_command"),
                f"{boundary_path}/controller-reset/outputs/torque_command",
            )
            actuator_inputs = _mapping(
                actuator_resets[0].get("reset_inputs"),
                f"{boundary_path}/actuator-reset/reset_inputs",
            )
            actuator_command_ref = _string(
                actuator_inputs.get("reset_command_ref"),
                f"{boundary_path}/actuator-reset/reset_inputs/reset_command_ref",
            )
            if (
                actuator_command_ref != controller_command_ref
                or actuator_command_ref not in seen_wires
            ):
                raise RuntimeRecordError(
                    "actuator_reset_command_source_mismatch",
                    f"{boundary_path}/actuator-reset/reset_inputs/reset_command_ref",
                )
            command_wire = wire_by_id[controller_command_ref]
            if (
                command_wire.get("kind") != "torque_command"
                or command_wire.get("role") != "held_torque"
                or command_wire.get("producer_operation_id")
                != controller_resets[0].get("operation_id")
            ):
                raise RuntimeRecordError(
                    "actuator_reset_command_source_mismatch",
                    f"{boundary_path}/controller-reset/outputs/torque_command",
                )
            command_payload = _mapping(
                command_wire.get("payload"),
                f"{boundary_path}/controller-reset/command-payload",
            )
            initial_state = _mapping(
                actuator_inputs.get("initial_state"),
                f"{boundary_path}/actuator-reset/reset_inputs/initial_state",
            )
            paired_fields = {
                "held_limited_torque_body_Nm": "limited_torque_body_Nm",
                "held_requested_torque_body_Nm": "requested_torque_body_Nm",
                "held_saturated": "saturated",
                "held_command_timestamp_s": "timestamp_s",
            }
            for reset_field, command_field in paired_fields.items():
                if initial_state.get(reset_field) != command_payload.get(command_field):
                    raise RuntimeRecordError(
                        "actuator_reset_pairing_mismatch",
                        f"{boundary_path}/actuator-reset/reset_inputs/initial_state/{reset_field}",
                    )

    for index, wire_value in enumerate(wires):
        wire_path = f"{path}/wires/{index}"
        wire = _mapping(wire_value, wire_path)
        producer = wire.get("producer_operation_id")
        if producer is not None:
            producer = _string(
                producer, f"{wire_path}/producer_operation_id"
            )
            if producer not in seen_operations:
                raise RuntimeRecordError(
                    "unresolved_operation_reference",
                    f"{wire_path}/producer_operation_id",
                    producer,
                )
        parent_values = _array(wire.get("parent_ids"), f"{wire_path}/parent_ids")
        parents = [
            _string(value, f"{wire_path}/parent_ids/{parent_index}")
            for parent_index, value in enumerate(parent_values)
        ]
        if len(set(parents)) != len(parents):
            raise RuntimeRecordError(
                "duplicate_parent_reference", f"{wire_path}/parent_ids"
            )
        wire_id = _string(wire.get("wire_id"), f"{wire_path}/wire_id")
        for parent_index, parent in enumerate(parents):
            parent_path = f"{wire_path}/parent_ids/{parent_index}"
            if parent == wire_id:
                raise RuntimeRecordError("self_parent_reference", parent_path)
            external_parent = allowed_external_parents.get(parent)
            if parent not in seen_wires and external_parent is None:
                raise RuntimeRecordError(
                    "unresolved_parent_reference", parent_path, parent
                )
            if parent not in seen_wires:
                if (
                    profile.get("profile_id") not in {"T1", "T2"}
                    or wire.get("producer")
                    not in {"sealed_replay", "evaluator_truth"}
                    or external_parent.get("kind") != wire.get("kind")
                    or external_parent.get("role") != wire.get("role")
                ):
                    raise RuntimeRecordError(
                        "parent_reference_scope_mismatch", parent_path, parent
                    )

    for operation_index, operation in enumerate(operations):
        operation_path = f"{path}/operations-flat/{operation_index}"
        for field in ("inputs", "outputs"):
            for ref, ref_path in _iter_ref_values(operation.get(field, {}), f"{operation_path}/{field}"):
                if ref not in seen_wires:
                    raise RuntimeRecordError("unresolved_wire_reference", ref_path, ref)
        for field in ("before_snapshot_ref", "after_snapshot_ref"):
            ref = operation.get(field)
            if ref is not None and ref not in seen_snapshots:
                raise RuntimeRecordError("unresolved_snapshot_reference", f"{operation_path}/{field}", str(ref))
        owner = operation.get("owner")
        method = operation.get("method")
        accepted = operation.get("accepted")
        if not isinstance(accepted, bool):
            raise RuntimeRecordError("expected_boolean", f"{operation_path}/accepted")
        if owner == "plant" and method == "step_base":
            result["plant_step_base"] += 1
        elif owner == "actuator" and method == "step_base":
            result["actuator_step_base"] += 1
        elif owner == "imu" and method == "sample":
            result["imu_sample"] += 1
        elif owner == "estimator" and method == "process":
            result["estimator_process"] += 1
            result["estimator_accepted" if accepted else "estimator_rejected"] += 1
        elif owner == "controller" and method == "step":
            result["controller_step"] += 1
            result["controller_accepted" if accepted else "controller_rejected"] += 1
        elif method == "reset" and owner in {"plant", "actuator", "imu", "estimator", "controller"}:
            result[f"{owner}_reset"] += 1
            lifecycle_key = (profile["profile_id"], operation["operation_id"], owner)
            observed_arguments = reset_arguments.get(lifecycle_key)
            if observed_arguments is None:
                raise RuntimeRecordError(
                    "lifecycle_reset_missing", operation_path, repr(lifecycle_key)
                )
            if observed_arguments != operation.get("reset_inputs"):
                raise RuntimeRecordError(
                    "lifecycle_reset_arguments_mismatch",
                    f"{operation_path}/reset_inputs",
                )
        if owner == "actuator" and method == "step":
            key = "operation:actuator:step"
            result[key] = result.get(key, 0) + 1

    probes = _array(profile["probes"], f"{path}/probes")
    for index, item in enumerate(probes):
        probe_path = f"{path}/probes/{index}"
        probe = _mapping(item, probe_path)
        probe_id = _string(probe.get("probe_id"), f"{probe_path}/probe_id")
        _unique(probe_id, seen_probes, f"{probe_path}/probe_id")
        accepted = probe.get("accepted")
        if not isinstance(accepted, bool):
            raise RuntimeRecordError("expected_boolean", f"{probe_path}/accepted")
        for ref, ref_path in _iter_ref_values(
            probe.get("checked_refs", {}), f"{probe_path}/checked_refs"
        ):
            if ref not in seen_wires:
                raise RuntimeRecordError("unresolved_wire_reference", ref_path, ref)
        for field in ("candidate_ref", "original_legal_ref", "source_truth_ref"):
            ref = probe.get(field)
            if ref is not None and ref not in seen_wires:
                raise RuntimeRecordError("unresolved_wire_reference", f"{probe_path}/{field}", str(ref))
        consumer = probe.get("consumer_operation_id")
        if consumer is not None and consumer not in seen_operations:
            raise RuntimeRecordError("unresolved_operation_reference", f"{probe_path}/consumer_operation_id", str(consumer))
        for field in ("before_snapshot_ref", "after_snapshot_ref"):
            ref = probe.get(field)
            if ref is not None and ref not in seen_snapshots:
                raise RuntimeRecordError("unresolved_snapshot_reference", f"{probe_path}/{field}", str(ref))
        component_delta = _component_count_delta(
            probe.get("component_call_delta"),
            f"{probe_path}/component_call_delta",
        )
        guard_site = _string(probe.get("guard_site"), f"{probe_path}/guard_site")
        guard_event = "accepted" if accepted else _string(
            probe.get("reason"), f"{probe_path}/reason"
        )
        guard_key = f"guard:{guard_site}:{guard_event}"
        result[guard_key] = result.get(guard_key, 0) + 1
        if accepted:
            continue
        if any(component_delta.values()):
            raise RuntimeRecordError(
                "rejected_probe_called_component",
                f"{probe_path}/component_call_delta",
            )
        kind = probe.get("kind")
        if kind == "old_epoch":
            result["old_epoch_rejected"] += 1
        elif kind == "needs_reset":
            result["needs_reset_rejected"] += 1
        elif kind == "truth_negative":
            result["truth_negative_rejected"] += 1

    for operation_index, operation in enumerate(operations):
        guard_ref = operation.get("guard_ref")
        if guard_ref is not None and guard_ref not in seen_probes:
            raise RuntimeRecordError(
                "unresolved_probe_reference",
                f"{path}/operations-flat/{operation_index}/guard_ref",
                str(guard_ref),
            )

    # Construction is an actual lifecycle observation, never profile arithmetic
    # or a reported-count echo.  Resets are present in both ledgers and must
    # reconcile exactly before the author-side record can be delivered.
    for key in (
        "plant_constructor",
        "actuator_constructor",
        "imu_constructor",
        "estimator_constructor",
        "controller_adapter_constructor",
        "controller_core_constructor",
    ):
        result[key] = _integer(lifecycle_counts.get(key), f"{path}/lifecycle/{key}")
    for key in (
        "plant_reset",
        "actuator_reset",
        "imu_reset",
        "estimator_reset",
        "controller_reset",
    ):
        observed = _integer(lifecycle_counts.get(key), f"{path}/lifecycle/{key}")
        if observed != result[key]:
            raise RuntimeRecordError(
                "lifecycle_operation_count_mismatch",
                f"{path}/{key}",
                f"lifecycle={observed}; operations={result[key]}",
            )
    for key, value_item in lifecycle_counts.items():
        if key not in COUNT_KEYS:
            result[key] = _integer(value_item, f"{path}/lifecycle/{key}")
    return result


def _record_id_index(
    profiles: Sequence[Mapping[str, Any]],
) -> tuple[
    set[tuple[str, str]],
    dict[tuple[str, str], str],
]:
    operations: set[tuple[str, str]] = set()
    snapshots: dict[tuple[str, str], str] = {}
    for profile_index, profile in enumerate(profiles):
        profile_id = str(profile["profile_id"])
        for boundary_index, boundary_value in enumerate(profile["boundaries"]):
            boundary = _mapping(
                boundary_value,
                f"/profiles/{profile_index}/boundaries/{boundary_index}",
            )
            for operation in _array(
                boundary.get("operations"),
                f"/profiles/{profile_index}/boundaries/{boundary_index}/operations",
            ):
                operation_id = _string(
                    _mapping(operation, "/operation").get("operation_id"),
                    "/operation/operation_id",
                )
                key = (profile_id, operation_id)
                if key in operations:
                    raise RuntimeRecordError(
                        "duplicate_identifier", "/operation/operation_id", operation_id
                    )
                operations.add(key)
        for snapshot_index, snapshot_value in enumerate(profile["snapshots"]):
            snapshot_path = f"/profiles/{profile_index}/snapshots/{snapshot_index}"
            snapshot = _mapping(snapshot_value, snapshot_path)
            snapshot_id = _string(
                snapshot.get("snapshot_id"), f"{snapshot_path}/snapshot_id"
            )
            capture_id = _string(
                snapshot.get("capture_id"), f"{snapshot_path}/capture_id"
            )
            key = (profile_id, snapshot_id)
            if key in snapshots:
                raise RuntimeRecordError(
                    "duplicate_identifier", f"{snapshot_path}/snapshot_id", snapshot_id
                )
            snapshots[key] = capture_id
    return operations, snapshots


def _check_lifecycle_links(
    links: Sequence[Mapping[str, Any]],
    operations: set[tuple[str, str]],
    snapshots: Mapping[tuple[str, str], str],
) -> None:
    for link in links:
        profile_id = link["profile_id"]
        operation_id = link["operation_id"]
        if profile_id is None:
            if operation_id is not None:
                raise RuntimeRecordError(
                    "lifecycle_operation_profile_missing",
                    f"{link['path']}/operation_id",
                )
            continue
        if link["method"] == "capture_snapshot":
            snapshot_ref = link["snapshot_ref"]
            key = (profile_id, snapshot_ref)
            if snapshot_ref is None or key not in snapshots:
                raise RuntimeRecordError(
                    "unresolved_snapshot_reference",
                    f"{link['path']}/result/snapshot_ref",
                    str(snapshot_ref),
                )
            if snapshots[key] != link["capture_id"]:
                raise RuntimeRecordError(
                    "snapshot_capture_id_mismatch",
                    f"{link['path']}/result/capture_id",
                )
            if operation_id != snapshot_ref:
                raise RuntimeRecordError(
                    "observer_operation_binding_mismatch",
                    f"{link['path']}/operation_id",
                )
        elif operation_id is not None and (profile_id, operation_id) not in operations:
            raise RuntimeRecordError(
                "unresolved_operation_reference",
                f"{link['path']}/operation_id",
                str(operation_id),
            )


def _check_bytes(raw_bytes: bytes, source: str) -> dict[str, Any]:
    raw = _mapping(_decode(raw_bytes, source), "/")
    _exact_keys(raw, TOP_LEVEL_KEYS, "/")
    _walk_number_encoding(raw)
    if raw["schema_version"] != EVIDENCE_VERSION:
        raise RuntimeRecordError("schema_version_mismatch", "/schema_version")
    if raw.get("completion") != "complete" or raw.get("termination_reason") is not None:
        raise RuntimeRecordError("record_set_not_complete", "/completion")
    identity = _mapping(raw.get("identity"), "/identity")
    if identity.get("seed") != SEED:
        raise RuntimeRecordError("seed_mismatch", "/identity/seed")
    if identity.get("classification") != CLASSIFICATION:
        raise RuntimeRecordError("classification_mismatch", "/identity/classification")

    parameter_ids = _parameter_objects(raw["parameter_objects"])
    (
        lifecycle_by_profile,
        lifecycle_event_counts,
        lifecycle_links,
        lifecycle_reset_arguments,
    ) = _lifecycle(
        raw["lifecycle_observations"], parameter_ids
    )
    if any(key.endswith(".exception") for key in lifecycle_event_counts):
        raise RuntimeRecordError(
            "lifecycle_exception_in_complete_record", "/lifecycle_observations"
        )

    profiles = _array(raw["profiles"], "/profiles")
    if [item.get("profile_id") if isinstance(item, dict) else None for item in profiles] != list(PROFILE_ORDER):
        raise RuntimeRecordError("profile_order_mismatch", "/profiles")

    wires_by_profile: dict[str, dict[str, Mapping[str, Any]]] = {}
    for index, value in enumerate(profiles):
        profile_path = f"/profiles/{index}"
        profile = _mapping(value, profile_path)
        profile_id = _string(profile.get("profile_id"), f"{profile_path}/profile_id")
        identifiers: set[str] = set()
        indexed_wires: dict[str, Mapping[str, Any]] = {}
        for wire_index, wire_value in enumerate(
            _array(profile.get("wires"), f"{profile_path}/wires")
        ):
            wire_path = f"{profile_path}/wires/{wire_index}"
            wire = _mapping(wire_value, wire_path)
            identifier = _string(wire.get("wire_id"), f"{wire_path}/wire_id")
            _unique(identifier, identifiers, f"{wire_path}/wire_id")
            indexed_wires[identifier] = wire
        wires_by_profile[profile_id] = indexed_wires

    reconstructed_total = {key: 0 for key in COUNT_KEYS}
    profile_results: list[dict[str, Any]] = []
    for index, value in enumerate(profiles):
        path = f"/profiles/{index}"
        profile = _mapping(value, path)
        _exact_keys(profile, PROFILE_KEYS, path)
        profile_id = _string(profile["profile_id"], f"{path}/profile_id")
        reported = _counts(profile["reported_counts"], f"{path}/reported_counts")
        reconstructed = _reconstruct_profile(
            profile,
            path,
            lifecycle_by_profile[profile_id],
            lifecycle_reset_arguments,
            (
                wires_by_profile["L1"]
                if profile_id in {"T1", "T2"}
                else {}
            ),
        )
        # The external E2 plan may require an explicitly serialized zero for a
        # finite auxiliary key that had no actual event.  This author-side
        # checker has no authority input and therefore checks only that such a
        # well-formed reported key reconciles to the actual default of zero;
        # the independent checker owns authorization of the key set and value.
        for key in reported:
            reconstructed.setdefault(key, 0)
        if reconstructed != reported:
            differing = [
                key
                for key in sorted(set(reconstructed) | set(reported))
                if reconstructed.get(key) != reported.get(key)
            ]
            raise RuntimeRecordError(
                "profile_reconstructed_counts_mismatch",
                path,
                ",".join(differing),
            )
        for key, count in reconstructed.items():
            reconstructed_total[key] = reconstructed_total.get(key, 0) + count
        profile_results.append(
            {"profile_id": profile_id, "status": "pass", "reconstructed_counts": reconstructed}
        )

    reported_total = _counts(raw["reported_counts"], "/reported_counts")
    if reconstructed_total != reported_total:
        raise RuntimeRecordError("reconstructed_total_counts_mismatch", "/reported_counts")
    operation_ids, snapshot_ids = _record_id_index(profiles)
    _check_lifecycle_links(lifecycle_links, operation_ids, snapshot_ids)
    return {
        "status": "pass",
        "reason": "author_structure_and_counts_match",
        "profile_results": profile_results,
        "reported_counts": reported_total,
        "reconstructed_counts": reconstructed_total,
        "parameter_object_count": len(parameter_ids),
        "lifecycle_event_counts": lifecycle_event_counts,
    }


def _base_report(raw_source: str) -> dict[str, Any]:
    return {
        "report_version": REPORT_VERSION,
        "raw_path": raw_source,
        "raw_sha256": None,
        "consumer_authority_sha256": None,
        "status": "execution_error_inconclusive",
        "reason": "author_check_not_completed",
        "path": "/",
        "limitations": [
            "author-side checker; not the independent g3a_evidence_spec checker",
            "consumer authority transport binding is checked structurally only; external authority admission remains independent",
            "does not authorize auxiliary counter keys against the external E2 execution plan",
            "does not derive due ticks or apply numerical comparison policies",
            "constructor/reset counters are reconciled from actual lifecycle observations; this remains author-side accounting",
            "does not grant G3-A, G0-scene, performance, SIL, HIL, or flight acceptance",
        ],
    }


def check_runtime_record_bytes(
    raw_bytes: bytes,
    *,
    source: str,
    transport_path: str | Path | None = None,
) -> dict[str, Any]:
    """Check one already-sealed byte string without reopening its raw file.

    A ``pass`` here is only recorder preflight.  Independent authority,
    schema/semantic checking, numerical policies, diagnostic copies and PA
    acceptance remain external predicates.  The byte-oriented entry point
    lets downstream admission pass the exact same retained bytes to both the
    author-side and independent checkers.
    """

    base = _base_report(source)
    try:
        if not isinstance(raw_bytes, bytes):
            raise RuntimeRecordError("expected_bytes", "/")
        raw_sha256 = hashlib.sha256(raw_bytes).hexdigest()
        base["raw_sha256"] = raw_sha256
        if transport_path is not None:
            transport_source = Path(transport_path)
            consumer_bytes = transport_source.read_bytes()
            base["consumer_authority_sha256"] = hashlib.sha256(
                consumer_bytes
            ).hexdigest()
            consumer = _mapping(
                _decode(consumer_bytes, str(transport_source)),
                "/consumer_authority",
            )
            authority_basis_sha256 = consumer.get("authority_basis_sha256")
            if (
                not isinstance(authority_basis_sha256, str)
                or SHA256.fullmatch(authority_basis_sha256) is None
            ):
                raise RuntimeRecordError(
                    "consumer_authority_basis_digest_missing",
                    "/consumer_authority/authority_basis_sha256",
                )
            transport = _mapping(
                consumer.get("transport"), "/consumer_authority/transport"
            )
            transport_keys = set(transport)
            base_transport_keys = {"sha256", "artifact_locator"}
            diagnostic_keys = {"parent_raw_sha256", "diagnostic_id"}
            if (
                transport_keys != base_transport_keys
                and transport_keys != base_transport_keys | diagnostic_keys
            ):
                raise RuntimeRecordError(
                    "consumer_transport_shape_mismatch",
                    "/consumer_authority/transport",
                )
            declared_sha256 = transport.get("sha256")
            if (
                not isinstance(declared_sha256, str)
                or SHA256.fullmatch(declared_sha256) is None
            ):
                raise RuntimeRecordError(
                    "expected_sha256", "/consumer_authority/transport/sha256"
                )
            if declared_sha256.lower() != raw_sha256:
                raise RuntimeRecordError(
                    "transport_sha256_mismatch",
                    "/consumer_authority/transport/sha256",
                )
            _string(
                transport.get("artifact_locator"),
                "/consumer_authority/transport/artifact_locator",
            )
            if diagnostic_keys.issubset(transport_keys):
                parent_sha = transport.get("parent_raw_sha256")
                if not isinstance(parent_sha, str) or SHA256.fullmatch(parent_sha) is None:
                    raise RuntimeRecordError(
                        "expected_sha256",
                        "/consumer_authority/transport/parent_raw_sha256",
                    )
                _string(
                    transport.get("diagnostic_id"),
                    "/consumer_authority/transport/diagnostic_id",
                )
            base["transport_path"] = str(transport_source.resolve())
        outcome = _check_bytes(raw_bytes, source)
        base.update(outcome)
        base["path"] = None
        return base
    except RuntimeRecordError as exc:
        base.update({"status": "reject", "reason": exc.reason, "path": exc.path, "detail": exc.detail})
        return base
    except OSError as exc:
        base.update({"status": "execution_error_inconclusive", "reason": "io_error", "detail": str(exc)})
        return base
    except (
        TypeError,
        KeyError,
        IndexError,
        ValueError,
        OverflowError,
        RecursionError,
        AttributeError,
    ) as exc:
        base.update(
            {
                "status": "reject",
                "reason": "author_checker_structural_error",
                "path": "/",
                "detail": f"{type(exc).__name__}: {exc}",
            }
        )
        return base


def check_runtime_record_set(
    raw_path: str | Path,
    transport_path: str | Path | None = None,
) -> dict[str, Any]:
    """Read a retained record once, then apply the byte-oriented checker."""

    raw_source = Path(raw_path)
    try:
        raw_bytes = raw_source.read_bytes()
        source = str(raw_source.resolve())
    except OSError as exc:
        base = _base_report(str(raw_source))
        base.update(
            {
                "status": "execution_error_inconclusive",
                "reason": "io_error",
                "detail": str(exc),
            }
        )
        return base
    return check_runtime_record_bytes(
        raw_bytes,
        source=source,
        transport_path=transport_path,
    )


def _write_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8") + b"\n"
    with path.open("xb") as stream:
        stream.write(payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", required=True, type=Path)
    parser.add_argument("--transport", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    report = check_runtime_record_set(args.raw, args.transport)
    _write_exclusive(args.output, report)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "RuntimeRecordError",
    "check_runtime_record_bytes",
    "check_runtime_record_set",
    "main",
]
