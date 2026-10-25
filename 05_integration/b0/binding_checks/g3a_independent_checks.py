"""Offline G3-A raw checks; static implementation, not an executed acceptance.

Only the three public functions below consume inputs.  Import performs no IO,
component construction, random sampling, subprocess work or check execution.
Expected schedule/event arithmetic is local to this module, never DUT-derived.
The sealed v1 schema is interpreted only for its finite used keyword subset.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import math
import re
from collections import Counter
from typing import Any


__all__ = ["check_record_set", "compare_builds", "make_data_diagnostics"]

_VERSION = "b0-g3a-independent-report/v1"
_SCHEMA_PATH = "05_integration/b0/binding_checks/g3a_evidence_schema.v1.json"
_SCHEMA_SHA = "4c98bdabdf41241952a43d12cec4f96d06c1961095c3b1de9d7ddb73330d0004"
_SPEC_PATH = "05_integration/b0/binding_checks/g3a_evidence_spec.md"
_SPEC_SHA = "a1c12f84764d0b7ec0964d677e8aa7cd5b7f4a8a6dc262a4fd8ab0392ecbc0a3"
_PROFILE_PATH = "05_integration/b0/configs/g3a_evidence_profiles.v1.json"
_ORDER = ("S", "L1", "L2", "O1", "O2", "E", "T1", "T2")
_SEED = 2026100900
_BASE = 0.0025
_PERIOD = 0.005
_TOL = 1e-12
_ZERO3 = (0.0, 0.0, 0.0)
_IDENTITY_Q = (1.0, 0.0, 0.0, 0.0)
_IDENTITY_KEYS = (
    "work_order_sha256", "source_commit", "source_tree",
    "source_closure_manifest_sha256", "config_approval_manifest_sha256",
    "profile_definition_sha256", "parameter_inputs_manifest_sha256",
    "observer_manifest_sha256", "environment_manifest_sha256",
    "f0_manifest_sha256", "controller_module_path", "controller_module_sha256",
    "controller_module_abi", "build_type", "seed", "classification",
)
_CONVENTIONS = {
    "navigation_frame": "NED", "body_frame": "FRD",
    "quaternion": "scalar_first_Hamilton_q_nb_body_to_NED", "time": "s",
    "angular_rate": "rad/s", "angular_acceleration": "rad/s2", "torque": "Nm",
    "torque_rate": "Nm/s", "specific_force": "m/s2", "inertia": "kg*m2",
}
_COUNTERS = (
    "plant_step_base", "actuator_step_base", "imu_sample", "estimator_process",
    "estimator_accepted", "estimator_rejected", "controller_step",
    "controller_accepted", "controller_rejected", "plant_reset", "actuator_reset",
    "imu_reset", "estimator_reset", "controller_reset", "plant_constructor",
    "actuator_constructor", "imu_constructor", "estimator_constructor",
    "controller_adapter_constructor", "controller_core_constructor",
    "old_epoch_rejected", "needs_reset_rejected", "truth_negative_rejected",
)
_COMPONENT_COUNTERS = _COUNTERS[:20]
_GROUPS = (
    "G3-TIME", "G3-INIT", "G3-HOLD", "G3-EVENT", "G3-RESET", "G3-INVALID",
    "G3-TRUTH", "G3-TRUTH-NEGATIVE", "G3-BIND", "G3-REPLAY",
    "G3-DATA-A", "G3-EVIDENCE-A",
)
_LIMITATIONS = (
    "G3-A development integration only; no normal 8-scene/37-criterion or 50ms acceptance",
    "No parameter, physical-accuracy, flight, HIL or overall G3 acceptance",
    "Raw checks do not replace non-author source/observer/guard review or PA F0 acceptance",
    "Core parameter evidence is actual constructor input plus static copy path, not private readback",
    "Long/nonzero-origin scheduler regression and process/JUnit/CI acceptance are external obligations",
)


class _Reject(Exception):
    def __init__(self, reason: str, path: str, expected: Any = None,
                 actual: Any = None, *, incomplete: bool = False) -> None:
        self.reason, self.path = reason, path
        self.expected, self.actual, self.incomplete = expected, actual, incomplete
        super().__init__(f"{reason}: {path}")


def _need(ok: bool, reason: str, path: str, expected: Any = None,
          actual: Any = None, *, incomplete: bool = False) -> None:
    if not ok:
        raise _Reject(reason, path, expected, actual, incomplete=incomplete)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _encoded(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _equal(a: Any, b: Any) -> bool:
    return _encoded(a) == _encoded(b)


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _need(key not in result, "json_duplicate_key", "$", actual=key)
        result[key] = value
    return result


def _constant(token: str) -> None:
    raise _Reject("json_invalid", "$", "standard JSON numbers", token)


def _decode(data: bytes, path: str) -> Any:
    _need(type(data) is bytes, "field_type_mismatch", path, "bytes", type(data).__name__)
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=_constant)
    except (UnicodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise _Reject("json_invalid", path, actual=str(exc)) from exc


def _pointer(path: str, key: Any) -> str:
    return path + "/" + str(key).replace("~", "~0").replace("/", "~1")


def _resolve(schema: dict[str, Any], root: dict[str, Any]) -> dict[str, Any]:
    if "$ref" not in schema:
        return schema
    ref = schema["$ref"]
    _need(type(ref) is str and ref.startswith("#/$defs/"), "authority_invalid", "schema/$ref")
    name = ref[len("#/$defs/"):]
    _need(name in root["$defs"], "authority_invalid", "schema/$defs/" + name)
    return root["$defs"][name]


def _is_type(value: Any, name: str) -> bool:
    if name == "object":
        return type(value) is dict
    if name == "array":
        return type(value) is list
    if name == "integer":
        return type(value) is int
    if name == "number":
        return type(value) in (int, float) and math.isfinite(value)
    return ((name == "string" and type(value) is str) or
            (name == "boolean" and type(value) is bool) or
            (name == "null" and value is None))


def _shape(value: Any, schema: dict[str, Any], root: dict[str, Any],
           path: str = "$") -> list[tuple[str, str]]:
    """Finite sealed-schema subset; no external schema/code loading."""
    if schema.get("$ref") == "#/$defs/float64":
        _need(type(value) is str, "field_type_mismatch", path, "hex string", value)
        _need(re.fullmatch(root["$defs"]["float64"]["pattern"], value) is not None,
              "float_encoding_invalid", path, actual=value)
        return [(path, value)]
    schema = _resolve(schema, root)
    result: list[tuple[str, str]] = []
    for variant_name in ("anyOf", "oneOf"):
        if variant_name in schema:
            successes: list[list[tuple[str, str]]] = []
            errors: list[_Reject] = []
            for item in schema[variant_name]:
                try:
                    successes.append(_shape(value, item, root, path))
                except _Reject as exc:
                    errors.append(exc)
            if not successes:
                precise = [error for error in errors if error.reason == "missing_required_field"]
                raise (max(precise, key=lambda error: len(error.path)) if precise
                       else errors[0] if errors else _Reject("field_type_mismatch", path))
            _need(variant_name != "oneOf" or len(successes) == 1,
                  "field_type_mismatch", path, "one typed alternative")
            result.extend(successes[0])
    if "type" in schema:
        kinds = schema["type"] if type(schema["type"]) is list else [schema["type"]]
        _need(any(_is_type(value, kind) for kind in kinds), "field_type_mismatch", path,
              kinds, type(value).__name__)
    if "const" in schema:
        _need(_equal(value, schema["const"]), "field_type_mismatch", path,
              schema["const"], value)
    if "enum" in schema:
        _need(any(_equal(value, choice) for choice in schema["enum"]),
              "field_type_mismatch", path, schema["enum"], value)
    if type(value) is dict:
        for key in schema.get("required", []):
            _need(key in value, "missing_required_field", _pointer(path, key))
        _need(len(value) <= schema.get("maxProperties", len(value)),
              "unexpected_field", path)
        properties = schema.get("properties", {})
        for key, child in value.items():
            if key in properties:
                result.extend(_shape(child, properties[key], root, _pointer(path, key)))
            elif schema.get("additionalProperties") is False:
                raise _Reject("unexpected_field", _pointer(path, key))
            elif type(schema.get("additionalProperties")) is dict:
                result.extend(_shape(child, schema["additionalProperties"], root,
                                     _pointer(path, key)))
    if type(value) is list:
        _need(len(value) >= schema.get("minItems", 0) and
              len(value) <= schema.get("maxItems", len(value)), "field_type_mismatch", path)
        if schema.get("uniqueItems"):
            _need(len({_encoded(item) for item in value}) == len(value),
                  "field_type_mismatch", path, "unique entries")
        if "items" in schema:
            for index, child in enumerate(value):
                result.extend(_shape(child, schema["items"], root, _pointer(path, index)))
    if type(value) is str:
        _need(len(value) >= schema.get("minLength", 0), "field_type_mismatch", path)
        if "pattern" in schema:
            _need(re.search(schema["pattern"], value) is not None, "field_type_mismatch", path)
    if type(value) in (int, float) and type(value) is not bool:
        _need(value >= schema.get("minimum", value) and value <= schema.get("maximum", value),
              "field_type_mismatch", path)
    for part in schema.get("allOf", []):
        if "if" in part:
            try:
                _shape(value, part["if"], root, path)
                condition = True
            except _Reject:
                condition = False
            if condition and "then" in part:
                result.extend(_shape(value, part["then"], root, path))
        else:
            result.extend(_shape(value, part, root, path))
    return result


def _number(value: str) -> float:
    return float.fromhex(value)


def _hex_tree(value: Any) -> Any:
    if type(value) is list:
        return [_hex_tree(item) for item in value]
    _need(type(value) in (int, float) and type(value) is not bool and math.isfinite(value),
          "authority_invalid", "expected_float", actual=value)
    return float(value).hex()


def _finite(floats: list[tuple[str, str]]) -> None:
    for path, value in floats:
        if value == "nan":
            raise _Reject("nonfinite_nan", path)
        if value in ("inf", "-inf"):
            raise _Reject("nonfinite_inf", path)
        try:
            number = float.fromhex(value)
        except (ValueError, OverflowError) as exc:
            raise _Reject("float_encoding_invalid", path, actual=value) from exc
        _need(math.isfinite(number) and number.hex() == value,
              "float_encoding_invalid", path, "canonical finite float.hex", value)


def _authority(authority: Any) -> tuple[dict[str, Any], dict[str, Any], dict[str, bytes]]:
    _need(type(authority) is dict, "authority_missing", "authority", incomplete=True)
    _need(authority.get("authority_version") == "b0-g3a-authority/v1",
          "authority_invalid", "authority/authority_version", incomplete=True)
    for key in ("identity", "artifact_sha256", "input_artifact_bytes", "input_artifact_base64",
                "parameter_inputs", "comparison_policy", "collection", "transport"):
        _need(type(authority.get(key)) is dict, "authority_missing", "authority/" + key,
              incomplete=True)
    identity = authority["identity"]
    _need(set(identity) == set(_IDENTITY_KEYS), "authority_invalid", "authority/identity",
          incomplete=True)
    registry, digests, encoded = (authority["input_artifact_bytes"],
                                   authority["artifact_sha256"], authority["input_artifact_base64"])
    _need(set(registry) == set(digests) == set(encoded) and bool(registry),
          "authority_invalid", "authority/artifacts", incomplete=True)
    for locator, data in registry.items():
        _need(type(data) is bytes and type(digests[locator]) is str and
              _sha(data) == digests[locator].lower(), "authority_invalid",
              "authority/artifacts/" + locator, incomplete=True)
        try:
            decoded = base64.b64decode(encoded[locator], validate=True)
        except (ValueError, TypeError) as exc:
            raise _Reject("authority_invalid", "authority/base64/" + locator,
                          incomplete=True) from exc
        _need(decoded == data, "authority_invalid", "authority/base64/" + locator,
              incomplete=True)
    basis = {key: value for key, value in authority.items()
             if key not in {"transport", "authority_basis_sha256", "input_artifact_bytes"}}
    _need(_sha(_encoded(basis) + b"\n") == authority.get("authority_basis_sha256"),
          "authority_invalid", "authority/authority_basis_sha256", incomplete=True)
    for locator, digest in ((_SCHEMA_PATH, _SCHEMA_SHA), (_SPEC_PATH, _SPEC_SHA)):
        _need(locator in registry and _sha(registry[locator]) == digest,
              "authority_invalid", "authority/artifacts/" + locator, incomplete=True)
    schema = _decode(registry[_SCHEMA_PATH], "authority/schema")
    _need(_PROFILE_PATH in registry and _sha(registry[_PROFILE_PATH]) == identity["profile_definition_sha256"].lower(),
          "authority_invalid", "authority/profile", incomplete=True)
    definition = _decode(registry[_PROFILE_PATH], "authority/profile")
    for locator, identity_key in (
        ("source-closure.json", "source_closure_manifest_sha256"),
        ("config-approval.json", "config_approval_manifest_sha256"),
        ("expected-parameter-inputs.json", "parameter_inputs_manifest_sha256"),
        ("observer.json", "observer_manifest_sha256"),
        ("environment.json", "environment_manifest_sha256"),
        ("f0-candidate.json", "f0_manifest_sha256"),
    ):
        _need(locator in registry and _sha(registry[locator]) == identity[identity_key].lower(),
              "authority_invalid", "authority/artifacts/" + locator, incomplete=True)
    _need(_equal(_decode(registry["expected-parameter-inputs.json"], "authority/parameters"),
                 authority["parameter_inputs"]), "authority_invalid", "authority/parameter_inputs",
          incomplete=True)
    policy_path = "05_integration/b0/configs/g3a_authority_policy.v1.json"
    _need(policy_path in registry and _sha(registry[policy_path]) == authority.get("policy_sha256"),
          "authority_invalid", "authority/policy", incomplete=True)
    policy = _decode(registry[policy_path], "authority/policy")
    plan = authority.get("execution_plan")
    _need(type(plan) is dict and _equal(plan, policy.get("execution_plan")) and
          plan.get("plan_version") == "b0-g3a-execution-plan/v1",
          "authority_missing", "authority/execution_plan", incomplete=True)
    sites, auxiliary = plan.get("lifecycle_callsites"), plan.get("auxiliary_counts")
    _need(type(sites) is dict and bool(sites) and type(auxiliary) is dict and
          set(auxiliary) == set(_ORDER), "authority_missing", "authority/execution_plan",
          incomplete=True)
    for site, entry in sites.items():
        _need(type(site) is str and bool(site) and type(entry) is dict and
              set(entry) == {"owner", "method", "parent_site"}, "authority_invalid",
              "authority/execution_plan/lifecycle_callsites", incomplete=True)
        parents = entry["parent_site"]
        _need(parents is None or (type(parents) is list and bool(parents) and
              all(type(parent) is str and parent in sites for parent in parents)),
              "authority_invalid", "authority/execution_plan/" + site, incomplete=True)
    for profile, counts in auxiliary.items():
        _need(type(counts) is dict and all(type(key) is str and type(value) is int and value >= 0
              for key, value in counts.items()), "authority_invalid",
              "authority/execution_plan/auxiliary_counts/" + profile, incomplete=True)
    return schema, definition, registry


def _preflight(raw_bytes: bytes, authority: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    schema, definition, registry = _authority(authority)
    _need(type(raw_bytes) is bytes and _sha(raw_bytes) == authority["transport"].get("sha256"),
          "transport_hash_mismatch", "transport/sha256")
    raw = _decode(raw_bytes, "$")
    floats = _shape(raw, schema, schema)
    for key in _IDENTITY_KEYS:
        if not _equal(raw["identity"][key], authority["identity"][key]):
            reason = ("source_mismatch" if key in {"source_commit", "source_tree", "source_closure_manifest_sha256"}
                      else "module_identity_mismatch" if key.startswith("controller_module") or key == "build_type"
                      else "environment_identity_mismatch" if key == "environment_manifest_sha256"
                      else "f0_identity_mismatch" if key == "f0_manifest_sha256"
                      else "parameter_identity_mismatch" if key == "parameter_inputs_manifest_sha256"
                      else "observer_identity_mismatch" if key == "observer_manifest_sha256"
                      else "profile_identity_mismatch" if key == "profile_definition_sha256"
                      else "config_identity_mismatch")
            raise _Reject(reason, "$/identity/" + key, authority["identity"][key], raw["identity"][key])
    for key, expected in _CONVENTIONS.items():
        _need(raw["conventions"][key] == expected,
              "frame_mismatch" if key in {"navigation_frame", "body_frame", "quaternion"} else "unit_mismatch",
              "$/conventions/" + key, expected, raw["conventions"][key])
    _finite(floats)
    _need(raw["completion"] == "complete" and raw["termination_reason"] is None,
          "partial_record", "$/completion", incomplete=True)
    _need(raw["identity"]["seed"] == _SEED and raw["identity"]["classification"] ==
          "development_integration_not_normal_acceptance", "config_identity_mismatch", "$/identity")
    _need(definition.get("profile_order") == list(_ORDER) and definition.get("seed") == _SEED
          and definition.get("base_period_s") == _BASE, "authority_invalid", "authority/profile")
    return raw, definition


def _profile_shape(profile_id: str) -> tuple[int, tuple[int, ...]]:
    if profile_id == "S":
        return 12, (0,)
    if profile_id in ("L1", "L2"):
        return 1200, (0, 1000)
    if profile_id in ("O1", "O2"):
        return 13, (0, 7)
    if profile_id == "E":
        return 38, (0,)
    return 1004, (1000,)


def _expected_operations(profile_id: str, tick: int, reset: bool, local: int) -> list[tuple[Any, ...]]:
    def signature(owner: str, method: str, phase: int, attempt: str = "normal",
                  accepted: bool = True, reason: str = "accepted") -> tuple[Any, ...]:
        return owner, method, phase, attempt, accepted, reason

    if reset:
        actors = ("controller", "estimator") if profile_id in ("T1", "T2") else (
            "controller", "actuator", "plant", "imu", "estimator")
        return [signature(actor, "reset", 0, "reset") for actor in actors]
    replay = profile_id in ("T1", "T2")
    expected = [] if replay else [signature("plant", "step_base", 1),
                                 signature("actuator", "step_base", 2)]
    if local % 2 or local < 2:
        return expected
    if not replay:
        expected += [signature("imu", "sample", 3),
                     signature("measurement_adapter", "adapt_measurement", 3)]
    if profile_id in ("L1", "L2") and tick == 800:
        expected += [signature("estimator", "process", 4, "injected_invalid", False,
                               "imu sample timestamp is duplicate or stale"),
                     signature("estimator", "process", 4, "same_tick_correction")]
    else:
        expected += [signature("estimator", "process", 4)]
    if profile_id in ("L1", "L2") and tick == 400:
        expected += [signature("controller", "step", 5, "injected_invalid", False, "invalid_dt"),
                     signature("controller", "step", 5, "same_tick_correction")]
    elif profile_id in ("O1", "O2") and tick == 6:
        return expected + [signature("controller", "step", 5, "injected_invalid", False,
                                     "unexpected_tick")]
    else:
        expected += [signature("controller", "step", 5)]
    return expected + [signature("session", "publish", 6, "publication")]


def _delegate(operation: dict[str, Any]) -> bool:
    return operation["owner"] == "actuator" and operation["method"] == "step"


def _signature(operation: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(operation[key] for key in ("owner", "method", "phase", "attempt_kind", "accepted", "reason"))


def _schedule(raw: dict[str, Any]) -> None:
    ids = [profile["profile_id"] for profile in raw["profiles"]]
    _need(len(set(ids)) == len(ids), "duplicate_profile", "$/profiles")
    _need(set(ids) == set(_ORDER), "missing_profile", "$/profiles", list(_ORDER), ids)
    _need(ids == list(_ORDER), "profile_order", "$/profiles", list(_ORDER), ids)
    for index, profile in enumerate(raw["profiles"]):
        pid, path = profile["profile_id"], f"$/profiles/{index}"
        horizon, resets = _profile_shape(pid)
        _need(profile["horizon_tick"] == horizon and profile["reset_ticks"] == list(resets),
              "profile_identity_mismatch", path)
        expected_ticks = [1000, 1002, 1004] if pid in ("T1", "T2") else list(range(horizon + 1))
        actual_ticks = [boundary["global_tick"] for boundary in profile["boundaries"]]
        missing, extra = Counter(expected_ticks) - Counter(actual_ticks), Counter(actual_ticks) - Counter(expected_ticks)
        _need(not missing, "missing_due", path + "/boundaries", dict(missing), actual_ticks)
        _need(not extra, "duplicate_due", path + "/boundaries", expected_ticks, dict(extra))
        _need(actual_ticks == expected_ticks, "phase_order", path + "/boundaries")
        for boundary_index, boundary in enumerate(profile["boundaries"]):
            bpath = path + f"/boundaries/{boundary_index}"
            tick = boundary["global_tick"]
            reset = tick in resets
            origin_tick = max(origin for origin in resets if origin <= tick)
            local = tick - origin_tick
            expected = _expected_operations(pid, tick, reset, local)
            operations = [operation for operation in boundary["operations"] if not _delegate(operation)]
            actual = [_signature(operation) for operation in operations]
            missing = Counter(expected) - Counter(actual)
            extra = Counter(actual) - Counter(expected)
            _need(not missing, "missing_due", bpath + "/operations", list(missing.elements()), actual)
            _need(not extra, "duplicate_due", bpath + "/operations", expected, list(extra.elements()))
            _need(actual == expected, "phase_order", bpath + "/operations", expected, actual)
            _need(boundary["boundary_kind"] == ("reset" if reset else "ordinary"),
                  "reset_only_violation", bpath + "/boundary_kind")
            epoch_id = resets.index(origin_tick) if pid not in ("T1", "T2") else 1
            _need((boundary["local_tick"], boundary["epoch_origin_tick"], boundary["epoch_id"]) ==
                  (local, origin_tick, epoch_id), "clock_mismatch", bpath)
            expected_origin = origin_tick * _BASE
            _close_time(boundary["epoch_origin_s"], expected_origin, bpath + "/epoch_origin_s")
            _close_time(boundary["timestamp_s"], expected_origin + local * _BASE, bpath + "/timestamp_s")
            for operation in boundary["operations"]:
                if _delegate(operation):
                    _need(not reset and operation["phase"] == 2 and operation["attempt_kind"] == "normal"
                          and operation["accepted"] and operation["reason"] == "accepted",
                          "phase_order", bpath + "/operations/delegated")


def _close_time(actual: str, expected: float, path: str) -> None:
    _need(abs(_number(actual) - expected) <= _TOL, "clock_mismatch", path,
          expected.hex(), actual)


def _map_unique(items: list[dict[str, Any]], key: str, path: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        identifier = item[key]
        _need(identifier not in result, "producer_mismatch", path + "/" + identifier, "unique ID")
        result[identifier] = item
    return result


def _contexts(raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {}
    for index, profile in enumerate(raw["profiles"]):
        pid = profile["profile_id"]
        all_operations = [operation for boundary in profile["boundaries"] for operation in boundary["operations"]]
        result[pid] = {
            "profile": profile, "path": f"$/profiles/{index}",
            "wires": _map_unique(profile["wires"], "wire_id", f"$/profiles/{index}/wires"),
            "ops": _map_unique(all_operations, "operation_id", f"$/profiles/{index}/operations"),
            "snapshots": _map_unique(profile["snapshots"], "snapshot_id", f"$/profiles/{index}/snapshots"),
            "probes": _map_unique(profile["probes"], "probe_id", f"$/profiles/{index}/probes"),
            "boundaries": {boundary["global_tick"]: boundary for boundary in profile["boundaries"]},
        }
    return result


def _wire(context: dict[str, Any], ref: Any, kind: str | None = None) -> dict[str, Any]:
    _need(type(ref) is str and ref in context["wires"], "producer_ref_missing",
          context["path"] + "/wires", actual=ref)
    wire = context["wires"][ref]
    _need(kind is None or wire["kind"] == kind, "producer_mismatch",
          context["path"] + "/wires/" + ref, kind, wire["kind"])
    return wire


def _snapshot(context: dict[str, Any], ref: Any) -> dict[str, Any]:
    _need(type(ref) is str and ref in context["snapshots"], "snapshot_incomplete",
          context["path"] + "/snapshots", actual=ref, incomplete=True)
    return context["snapshots"][ref]


def _protected_state(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {key: snapshot[key] for key in ("session", "plant", "actuator", "imu", "estimator", "controller")}


def _preserved(context: dict[str, Any], before_ref: Any, after_ref: Any,
               *, needs_reset: bool = False) -> None:
    before, after = _snapshot(context, before_ref), _snapshot(context, after_ref)
    _need(before_ref != after_ref and before["capture_id"] != after["capture_id"],
          "snapshot_incomplete", context["path"] + "/snapshots", "two actual captures", incomplete=True)
    a, b = copy.deepcopy(_protected_state(before)), copy.deepcopy(_protected_state(after))
    if needs_reset:
        _need(a["session"]["lifecycle"] == "active" and b["session"]["lifecycle"] == "needs_reset"
              and a["session"]["needs_reset"] is False and b["session"]["needs_reset"] is True,
              "invalid_recovery_mismatch", context["path"] + "/O6_transition")
        b["session"]["lifecycle"] = "active"
        b["session"]["needs_reset"] = False
    _need(_equal(a, b), "snapshot_changed", context["path"] + "/snapshots/" + str(after_ref))


def _pcg64_state(state: Any, path: str, *, allow_uninitialized: bool) -> None:
    """Validate the fixed NumPy 1.26.4 PCG64 value map without creating an RNG.

    Domain basis: numpy/random/_pcg64.pyx v1.26.4 state getter/setter (175--199)
    and its documented two unsigned 128-bit values, with odd increment.  The
    uint32 cache is retained even when unused; bool is not an integer here.
    """
    if state is None:
        _need(allow_uninitialized, "snapshot_incomplete", path,
              "actual PCG64 state after reset", incomplete=True)
        return
    _need(type(state) is dict and set(state) == {"bit_generator", "state", "has_uint32", "uinteger"}
          and state.get("bit_generator") == "PCG64", "snapshot_incomplete", path,
          "fixed NumPy 1.26.4 PCG64 key map", incomplete=True)
    nested = state["state"]
    _need(type(nested) is dict and set(nested) == {"state", "inc"},
          "snapshot_incomplete", path + "/state", incomplete=True)
    _need(type(nested["state"]) is int and 0 <= nested["state"] < (1 << 128) and
          type(nested["inc"]) is int and 0 < nested["inc"] < (1 << 128) and nested["inc"] % 2 == 1 and
          type(state["has_uint32"]) is int and state["has_uint32"] in (0, 1) and
          type(state["uinteger"]) is int and 0 <= state["uinteger"] < (1 << 32),
          "snapshot_incomplete", path, "uint128 state/odd inc, 0|1 cache flag, uint32 cache", incomplete=True)


def _parameter_objects(raw: dict[str, Any], authority: dict[str, Any]) -> dict[str, dict[str, Any]]:
    manifest = authority["parameter_inputs"]
    _need(manifest.get("manifest_version") == "b0-g3a-expected-parameter-inputs/v1" and
          manifest.get("semantics") == "approved_expected_inputs_not_runtime_observations",
          "authority_invalid", "authority/parameter_inputs", incomplete=True)
    expected = manifest.get("components")
    _need(type(expected) is dict and set(expected) == {"plant", "actuator", "imu", "estimator", "controller"},
          "authority_invalid", "authority/parameter_inputs/components", incomplete=True)
    _need(_equal(expected["plant"], expected["actuator"]) and _equal(expected["plant"], expected["imu"]),
          "authority_invalid", "authority/parameter_inputs/g1", incomplete=True)
    parameters = _map_unique(raw["parameter_objects"], "parameter_object_id", "$/parameter_objects")
    for identifier, record in parameters.items():
        target = expected["plant" if record["kind"] == "g1" else record["kind"]]
        _need(_sha(_encoded(record["values"])) == record["values_sha256"].lower(),
              "constructor_binding_mismatch", "$/parameter_objects/" + identifier + "/values_sha256")
        _need(_equal(record["values"], target), "constructor_binding_mismatch",
              "$/parameter_objects/" + identifier + "/values", target, record["values"])
    _need(bool(parameters), "lifecycle_observation_missing", "$/parameter_objects", incomplete=True)
    return parameters


def _lifecycle(raw: dict[str, Any], authority: dict[str, Any],
               contexts: dict[str, dict[str, Any]], parameters: dict[str, dict[str, Any]]) -> dict[str, Any]:
    plan = authority["execution_plan"]
    sites = plan["lifecycle_callsites"]
    active: list[str] = []
    calls: dict[str, dict[str, Any]] = {}
    terminal: dict[str, dict[str, Any]] = {}
    component = {pid: Counter() for pid in _ORDER}
    auxiliary = {pid: Counter() for pid in _ORDER}
    observed_snapshots: Counter = Counter()
    reset_links: Counter = Counter()
    actors: dict[str, tuple[str, str, Any]] = {}
    setup_events = []
    returned: Counter = Counter()
    core_purposes: Counter = Counter()
    constructor_counter = {"plant": "plant_constructor", "actuator": "actuator_constructor",
                           "imu": "imu_constructor", "estimator": "estimator_constructor",
                           "controller": "controller_adapter_constructor",
                           "controller_core": "controller_core_constructor"}
    constructor_sources = {
        "plant": "01_simulation/b0/plant.py", "actuator": "01_simulation/b0/actuator.py",
        "imu": "01_simulation/b0/imu.py", "g1_parameters": "01_simulation/b0/contract.py",
        "estimator": "02_estimation/b0/estimator.py",
        "estimator_parameters": "02_estimation/b0/estimator.py",
    }
    for index, event in enumerate(raw["lifecycle_observations"]):
        path = f"$/lifecycle_observations/{index}"
        _need(event["observation_index"] == index, "lifecycle_pairing_mismatch", path + "/observation_index")
        site, call_id = event["callsite"], event["call_id"]
        _need(site in sites, "lifecycle_observation_missing", path + "/callsite", incomplete=True)
        expected_site = sites[site]
        _need((event["owner"], event["method"]) == (expected_site["owner"], expected_site["method"]),
              "lifecycle_pairing_mismatch", path)
        pid = event["profile_id"]
        charged = pid if pid is not None else "S"
        if pid is None:
            setup_events.append({"observation_index": index, "call_id": call_id,
                                 "callsite": site, "event": event["event"], "charged_group": "S"})
        auxiliary[charged][f"lifecycle:{site}:{event['event']}"] += 1
        if event["event"] == "enter":
            _need(call_id not in calls and event["result"] is None and event["exception"] is None
                  and type(event["arguments"]) is dict, "lifecycle_pairing_mismatch", path)
            parent = active[-1] if active else None
            _need(event["parent_call_id"] == parent, "lifecycle_pairing_mismatch", path + "/parent_call_id")
            allowed = expected_site["parent_site"]
            parent_site = calls[parent]["callsite"] if parent is not None else None
            _need((allowed is None and parent_site is None) or
                  (type(allowed) is list and parent_site in allowed),
                  "lifecycle_pairing_mismatch", path + "/parent_call_id", allowed, parent_site)
            calls[call_id] = event
            active.append(call_id)
            args, owner, method = event["arguments"], event["owner"], event["method"]
            if method == "constructor":
                _need(args.get("kind") == "constructor", "constructor_binding_mismatch", path)
                expected_mode = ("explicit_parameters" if owner in {"plant", "actuator", "imu", "controller_core"}
                                 else "default_loader" if owner == "estimator" and pid == "S"
                                 else "explicit_parameters" if owner == "estimator"
                                 else "parameter_fields" if owner in {"g1_parameters", "estimator_parameters"}
                                 else "controller_module" if owner == "controller"
                                 else "empty" if owner == "controller_parameters" else None)
                _need(expected_mode is not None and args["mode"] == expected_mode,
                      "constructor_binding_mismatch", path + "/arguments/mode", expected_mode, args["mode"])
                if owner in constructor_sources:
                    locator = constructor_sources[owner]
                    _need(locator in authority["input_artifact_bytes"], "authority_missing", path,
                          incomplete=True)
                    module_digest = _sha(authority["input_artifact_bytes"][locator])
                else:
                    module_digest = authority["identity"]["controller_module_sha256"]
                _need(args["module_sha256"] == module_digest, "constructor_binding_mismatch",
                      path + "/arguments/module_sha256", module_digest, args["module_sha256"])
                reference = args["parameter_object_ref"]
                if args["mode"] in ("explicit_parameters", "parameter_fields"):
                    _need(reference in parameters, "constructor_binding_mismatch", path + "/arguments")
                    expected_kind = ("g1" if owner in {"plant", "actuator", "imu", "g1_parameters"}
                                     else "estimator" if owner in {"estimator", "estimator_parameters"}
                                     else "controller")
                    _need(parameters[reference]["kind"] == expected_kind,
                          "constructor_binding_mismatch", path + "/arguments/parameter_object_ref")
                else:
                    _need(reference is None, "constructor_binding_mismatch", path + "/arguments")
                if owner == "controller_core":
                    _need(args["mode"] == "explicit_parameters" and event["core_use"] in
                          ("temporary_validation", "production"), "constructor_binding_mismatch", path)
                    _need(parent is not None and
                          ((event["core_use"] == "temporary_validation" and calls[parent]["owner"] == "controller_loader")
                           or (event["core_use"] == "production" and calls[parent]["owner"] == "controller")),
                          "constructor_binding_mismatch", path + "/parent_call_id")
                elif owner == "controller":
                    _need(args["mode"] == "controller_module" and args["module_sha256"] ==
                          authority["identity"]["controller_module_sha256"], "constructor_binding_mismatch", path)
            elif method in ("load_config", "validate_config"):
                _need(args.get("kind") == "config" and args["actual_argument_kind"] ==
                      ("path" if method == "load_config" else "document"),
                      "constructor_binding_mismatch", path + "/arguments")
                locator = args["source_artifact_ref"]
                _need(locator in authority["input_artifact_bytes"], "authority_missing", path,
                      incomplete=True)
                data = authority["input_artifact_bytes"][locator]
                _need(args["source_bytes_sha256"] == _sha(data), "constructor_binding_mismatch", path)
                if method == "load_config":
                    _need(args["path_argument"] == authority["parameter_inputs"]["components"]["plant"]["config_path"],
                          "constructor_binding_mismatch", path + "/arguments/path_argument")
                if method == "validate_config":
                    _need(args["path_argument"] is None and args["document_sha256"] ==
                          _sha(_encoded(_decode(data, path + "/document"))),
                          "constructor_binding_mismatch", path + "/arguments/document_sha256")
            elif method == "capture_snapshot":
                _need(args.get("kind") == "observer" and args["observer_manifest_sha256"] ==
                      authority["identity"]["observer_manifest_sha256"], "snapshot_incomplete", path,
                      incomplete=True)
            elif method == "load_parameters":
                _need(args.get("kind") == "loader", "constructor_binding_mismatch", path)
                expected_args = ({"kind": "loader", "supplied_args": ["config_path"],
                                  "config_path": authority["parameter_inputs"]["components"]["plant"]["config_path"]}
                                 if owner == "g1_loader" else
                                 {"kind": "loader", "supplied_args": []} if owner == "estimator_loader" else
                                 {"kind": "loader", "supplied_args": ["module"],
                                  "module_sha256": authority["identity"]["controller_module_sha256"]}
                                 if owner == "controller_loader" else None)
                _need(expected_args is not None and _equal(args, expected_args),
                      "constructor_binding_mismatch", path + "/arguments", expected_args, args)
            elif method == "reset":
                _need(args.get("kind") == "reset" and args["actor"] == owner,
                      "reset_mismatch", path)
                if owner == "controller_core":
                    _need(parent is not None and calls[parent]["owner"] == "controller" and
                          calls[parent]["method"] == "reset" and event["core_use"] == "production" and
                          calls[parent]["profile_id"] == pid and
                          calls[parent]["operation_id"] == event["operation_id"] and
                          args["initial_state"] == {} and
                          _equal(args["reset_epoch"], calls[parent]["arguments"]["reset_epoch"]),
                          "reset_mismatch", path + "/nested_core_reset")
        else:
            _need(bool(active) and active[-1] == call_id and call_id in calls and call_id not in terminal,
                  "lifecycle_pairing_mismatch", path)
            enter = calls[call_id]
            for key in ("parent_call_id", "profile_id", "operation_id", "owner", "method", "callsite", "actor_id", "core_use"):
                _need(event[key] == enter[key], "lifecycle_pairing_mismatch", path + "/" + key)
            _need(event["arguments"] is None, "lifecycle_pairing_mismatch", path + "/arguments")
            active.pop()
            terminal[call_id] = event
            if event["event"] == "exception":
                _need(event["exception"] is not None and event["result"] is None,
                      "lifecycle_pairing_mismatch", path)
                raise _Reject("partial_record", path, actual=event["exception"], incomplete=True)
            _need(event["event"] == "return" and event["exception"] is None and
                  type(event["result"]) is dict, "lifecycle_pairing_mismatch", path)
            owner, method, result = event["owner"], event["method"], event["result"]
            returned[(owner, method)] += 1
            reference = result["parameter_object_ref"]
            if reference is not None:
                _need(reference in parameters, "constructor_binding_mismatch", path + "/result")
            if method == "constructor":
                actor = result["actor_id"]
                _need(type(actor) is str and actor == enter["actor_id"] and actor not in actors,
                      "constructor_binding_mismatch", path + "/result/actor_id")
                actors[actor] = (owner, charged, event["core_use"])
                if owner in constructor_counter:
                    component[charged][constructor_counter[owner]] += 1
                if owner == "controller_core":
                    core_purposes[(charged, event["core_use"])] += 1
                if reference is not None:
                    expected_kind = ("g1" if owner in {"plant", "actuator", "imu", "g1_parameters"}
                                     else "estimator" if owner in {"estimator", "estimator_parameters"}
                                     else "controller")
                    _need(parameters[reference]["kind"] == expected_kind,
                          "constructor_binding_mismatch", path + "/result/parameter_object_ref")
                    if enter["arguments"]["parameter_object_ref"] is not None:
                        supplied = parameters[enter["arguments"]["parameter_object_ref"]]
                        _need(_equal(supplied["values"], parameters[reference]["values"]),
                              "constructor_binding_mismatch", path + "/result/parameter_values")
                if enter["arguments"]["mode"] == "default_loader":
                    nested = [calls[cid] for cid in calls if calls[cid]["parent_call_id"] == call_id
                              and calls[cid]["method"] == "load_parameters"]
                    _need(len(nested) == 1 and reference in parameters and
                          terminal[nested[0]["call_id"]]["result"]["parameter_object_ref"] == reference,
                          "constructor_binding_mismatch", path + "/default_loader")
            elif method == "load_parameters":
                kind = {"g1_loader": "g1", "estimator_loader": "estimator", "controller_loader": "controller"}.get(owner)
                _need(reference in parameters and parameters[reference]["kind"] == kind,
                      "constructor_binding_mismatch", path + "/result")
            elif method == "capture_snapshot":
                _need(pid in contexts and result["snapshot_ref"] == enter["arguments"]["snapshot_id"]
                      and result["capture_id"] == enter["arguments"]["capture_id"],
                      "snapshot_incomplete", path, incomplete=True)
                snap = _snapshot(contexts[pid], result["snapshot_ref"])
                _need(snap["capture_id"] == result["capture_id"], "snapshot_incomplete", path, incomplete=True)
                observed_snapshots[(pid, result["snapshot_ref"])] += 1
            elif method == "reset":
                _need(pid in contexts and event["operation_id"] in contexts[pid]["ops"], "reset_mismatch", path)
                operation = contexts[pid]["ops"][event["operation_id"]]
                if owner != "controller_core":
                    _need(operation["owner"] == owner and operation["method"] == "reset" and
                          _equal(operation["reset_inputs"], enter["arguments"]), "reset_mismatch", path)
                    reset_links[(pid, event["operation_id"])] += 1
                _need(enter["actor_id"] in actors and
                      actors[enter["actor_id"]] == (owner, charged, event["core_use"]),
                      "reset_mismatch", path + "/actor_id")
    _need(not active and len(terminal) == len(calls), "lifecycle_observation_missing",
          "$/lifecycle_observations", incomplete=True)
    required = {("plant", "constructor"): 6, ("actuator", "constructor"): 6,
                ("imu", "constructor"): 6, ("estimator", "constructor"): 8,
                ("controller", "constructor"): 8, ("controller_core", "constructor"): 16,
                ("g1_loader", "load_parameters"): 1, ("estimator_loader", "load_parameters"): 1,
                ("controller_loader", "load_parameters"): 8,
                ("g0_validator", "load_config"): 11, ("g0_validator", "validate_config"): 11}
    for key, count in required.items():
        _need(returned[key] == count, "lifecycle_observation_missing", "$/lifecycle/" + ":".join(key),
              count, returned[key], incomplete=True)
    for pid in _ORDER:
        for purpose in ("temporary_validation", "production"):
            _need(core_purposes[(pid, purpose)] == 1, "constructor_binding_mismatch",
                  "$/lifecycle/" + pid + "/" + purpose, 1, core_purposes[(pid, purpose)])
        for ref in contexts[pid]["snapshots"]:
            _need(observed_snapshots[(pid, ref)] == 1, "snapshot_incomplete",
                  contexts[pid]["path"] + "/snapshots/" + ref, 1, observed_snapshots[(pid, ref)], incomplete=True)
        for operation in contexts[pid]["ops"].values():
            if operation["method"] == "reset":
                _need(reset_links[(pid, operation["operation_id"])] == 1,
                      "lifecycle_observation_missing", contexts[pid]["path"] + "/reset", incomplete=True)
    return {"component_counts": component, "auxiliary_counts": auxiliary,
            "setup_observations": setup_events, "returned": returned}


def _qmul(a: list[float] | tuple[float, ...], b: list[float] | tuple[float, ...]) -> list[float]:
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return [aw*bw-ax*bx-ay*by-az*bz, aw*bx+ax*bw+ay*bz-az*by,
            aw*by-ax*bz+ay*bw+az*bx, aw*bz+ax*by-ay*bx+az*bw]


def _axes_quaternion(angles: list[float] | tuple[float, ...]) -> list[float]:
    q = list(_IDENTITY_Q)
    for axis, angle in enumerate(angles):
        part = [math.cos(angle/2.0), 0.0, 0.0, 0.0]
        part[axis+1] = math.sin(angle/2.0)
        q = _qmul(q, part)
    return q


def _qclose(actual: list[str], expected: list[float] | tuple[float, ...], path: str) -> None:
    _need(len(actual) == 4 and len(expected) == 4 and
          all(abs(_number(a)-b) <= _TOL for a, b in zip(actual, expected)),
          "float_comparison_failed", path, [float(x).hex() for x in expected], actual)


def _source_config(authority: dict[str, Any]) -> dict[str, Any]:
    path = "05_integration/b0/configs/b0_g0_contract.v2.json"
    data = authority["input_artifact_bytes"].get(path)
    _need(type(data) is bytes and _sha(data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")) ==
          "5b95531a6f96cb67ce25f624d6921bd313696f3c0b9868ec1de13c24c34cd98c",
          "authority_invalid", "authority/G0", incomplete=True)
    return _decode(data, "authority/G0")


def _event_expectation(pid: str, tick: int, config: dict[str, Any]) -> tuple[dict[str, Any], list[float]]:
    axes, torque, force = [0.0]*3, [0.0]*3, [0.0]*3
    gyro_bias = accel_bias = None
    active = []
    scenarios = {item["id"]: item for item in config["scenarios"]}
    if pid == "S" and 2 <= tick < 10:
        axes[0], active = 0.1, ["S_qx_positive"]
    elif pid in ("O1", "O2"):
        if 2 <= tick < 7:
            axes[0], active = 0.1, [pid + "_pre_qx_positive"]
        elif 9 <= tick < 14:
            axes[0], active = 0.1, [pid + "_post_qx_positive"]
        if tick == 7:
            active = [pid + "_reset_7"]
    elif pid in ("L1", "L2"):
        if tick == 400:
            active = [pid + "_invalid_negative_dt"]
        elif tick == 800:
            active = [pid + "_invalid_stale_timestamp"]
        elif tick == 1000:
            active = [pid + "_reset_1000"]
    elif pid == "E":
        names = ("x_positive", "x_negative", "y_positive", "y_negative", "z_positive", "z_negative")
        for index, start in enumerate((2, 6, 10, 14, 18, 22)):
            if start <= tick < start+2:
                axes[index//2] = scenarios["tri_axis_signed_steps"]["events"][index]["value_rad"]
                active = ["E_command_" + names[index]]
        if 26 <= tick < 28:
            torque = list(scenarios["external_torque_disturbance"]["events"][0]["vector_Nm"])
            active = ["E_external_torque"]
        elif 30 <= tick < 32:
            event = scenarios["imu_noise_and_bias"]["events"][0]
            gyro_bias, accel_bias = list(event["gyro_bias_rad_s"]), list(event["accelerometer_bias_m_s2"])
            active = ["E_replacement_bias"]
        elif 34 <= tick < 36:
            force = list(scenarios["acceleration_contamination"]["events"][0]["vector_m_s2"])
            active = ["E_additive_force"]
    expected = {"active_event_ids": active, "command_axes_rad": _hex_tree(axes),
                "external_torque_body_Nm": _hex_tree(torque),
                "replacement_gyro_bias_rad_s": None if gyro_bias is None else _hex_tree(gyro_bias),
                "replacement_accelerometer_bias_m_s2": None if accel_bias is None else _hex_tree(accel_bias),
                "additive_specific_force_body_m_s2": _hex_tree(force)}
    return expected, _axes_quaternion(axes)


def _boundary_operation(context: dict[str, Any], tick: int, owner: str,
                        method: str | None = None, *, accepted: bool = True) -> dict[str, Any]:
    matches = [op for op in context["boundaries"][tick]["operations"] if op["owner"] == owner
               and (method is None or op["method"] == method) and op["accepted"] is accepted]
    _need(len(matches) == 1, "producer_mismatch", context["path"] + f"/k{tick}/{owner}",
          "exactly one matching operation", len(matches))
    return matches[0]


def _input_epoch_and_pairing(contexts: dict[str, dict[str, Any]], authority: dict[str, Any]) -> None:
    limits = [_number(value) for value in authority["parameter_inputs"]["components"]["controller"]["torque_limit_Nm"]]
    for pid, context in contexts.items():
        for boundary in context["profile"]["boundaries"]:
            tick = boundary["global_tick"]
            for operation in boundary["operations"]:
                if operation["method"] in ("reset", "publish"):
                    continue
                for key, reference in operation["inputs"].items():
                    wire = _wire(context, reference)
                    _need(wire["epoch_id"] == boundary["epoch_id"], "stale_epoch",
                          context["path"] + "/wires/" + reference + "/epoch_id",
                          boundary["epoch_id"], wire["epoch_id"])
                    if operation["owner"] in ("estimator", "controller"):
                        _need(wire["producer"] != "evaluator_truth", "forbidden_truth_consumed",
                              context["path"] + "/wires/" + reference)
                if operation["owner"] == "actuator" and operation["method"] == "step_base":
                    command = _wire(context, operation["inputs"].get("torque_command"), "torque_command")
                    feedback = _wire(context, operation["outputs"].get("feedback"), "feedback")
                    a, b = command["payload"], feedback["payload"]
                    _need(b["command_timestamp_s"] == a["timestamp_s"] and
                          b["limited_torque_body_Nm"] == a["limited_torque_body_Nm"] and
                          b["saturated"] == a["saturated"], "feedback_pair_mismatch",
                          context["path"] + "/wires/" + feedback["wire_id"])
                    _need(command["global_tick"] < tick and command["wire_id"] == boundary["held_before_ref"],
                          "held_command_mismatch", context["path"] + f"/k{tick}/held")
        for wire in context["profile"]["wires"]:
            if wire["kind"] != "torque_command":
                continue
            payload = wire["payload"]
            requested = [_number(value) for value in payload["requested_torque_body_Nm"]]
            saturated = [abs(value) > limit for value, limit in zip(requested, limits)]
            limited = [value if not flag else math.copysign(limit, value)
                       for value, flag, limit in zip(requested, saturated, limits)]
            _need(payload["saturated"] == saturated and
                  payload["limited_torque_body_Nm"] == _hex_tree(limited),
                  "feedback_pair_mismatch", context["path"] + "/wires/" + wire["wire_id"])


def _guarded(context: dict[str, Any], boundary: dict[str, Any], operation: dict[str, Any]) -> None:
    if operation["method"] in ("reset", "publish") or _delegate(operation):
        return
    probe_ref = operation["guard_ref"]
    _need(probe_ref in context["probes"], "guard_missing",
          context["path"] + "/operations/" + operation["operation_id"], incomplete=True)
    probe = context["probes"][probe_ref]
    _need(probe["kind"] == "normal_guard" and probe["accepted"] is True and
          probe["reason"] == "accepted" and probe["consumer_operation_id"] == operation["operation_id"]
          and probe["global_tick"] == boundary["global_tick"] and probe["phase"] == operation["phase"]
          and _equal(probe["checked_refs"], operation["inputs"]),
          "guard_rejection_mismatch", context["path"] + "/probes/" + str(probe_ref))
    allowed = {
        ("plant", "feedback"): {"actuator_reset", "actuator"},
        ("actuator", "torque_command"): {"controller_reset", "controller"},
        ("imu", "sensor_truth"): {"plant_truth_boundary"},
        ("measurement_adapter", "raw_imu"): {"imu"},
        ("estimator", "adapted_imu"): {"measurement_adapter", "sealed_replay", "fault_injector"},
        ("controller", "estimate"): {"estimator", "sealed_replay", "fault_injector"},
        ("controller", "attitude_command"): {"command_sampler", "sealed_replay", "fault_injector"},
        ("controller", "feedback"): {"actuator_reset", "actuator", "sealed_replay"},
    }
    for key, reference in operation["inputs"].items():
        wire = _wire(context, reference)
        _need((operation["owner"], key) in allowed and wire["producer"] in allowed[(operation["owner"], key)],
              "producer_mismatch", context["path"] + "/inputs/" + reference)
        _need(wire["producer"] != "fault_injector" or operation["attempt_kind"] == "injected_invalid",
              "producer_mismatch", context["path"] + "/inputs/" + reference)


def _wire_links(context: dict[str, Any], contexts: dict[str, dict[str, Any]]) -> None:
    for wire in context["wires"].values():
        reference = wire["producer_operation_id"]
        if reference is not None:
            _need(reference in context["ops"], "producer_ref_missing",
                  context["path"] + "/wires/" + wire["wire_id"] + "/producer_operation_id")
            operation = context["ops"][reference]
            is_input_derivation = (
                wire["producer"] == "plant_truth_boundary" and operation["owner"] == "imu" and
                operation["inputs"].get("sensor_truth") == wire["wire_id"]
            ) or (
                wire["producer"] == "command_sampler" and operation["owner"] == "controller" and
                operation["inputs"].get("attitude_command") == wire["wire_id"]
            ) or (
                wire["producer"] == "fault_injector" and operation["attempt_kind"] == "injected_invalid" and
                wire["wire_id"] in operation["inputs"].values()
            )
            _need(wire["wire_id"] in operation["outputs"].values() or is_input_derivation,
                  "producer_mismatch", context["path"] + "/wires/" + wire["wire_id"] + "/producer_operation_id")
        else:
            _need(wire["producer"] in {"explicit_initialization", "command_sampler", "sealed_replay",
                                      "evaluator_truth", "fault_injector", "plant_truth_boundary"},
                  "producer_mismatch", context["path"] + "/wires/" + wire["wire_id"])
        for parent in wire["parent_ids"]:
            sealed_parent = context["profile"]["profile_id"] in ("T1", "T2") and parent in contexts["L1"]["wires"]
            _need(parent in context["wires"] or sealed_parent, "producer_ref_missing", context["path"] + "/wires/" + parent)


def _flow(contexts: dict[str, dict[str, Any]], authority: dict[str, Any]) -> None:
    config = _source_config(authority)
    offset = next(item["initial_attitude_offset_rad"] for item in config["scenarios"]
                  if item["id"] == "initial_attitude_offset")
    nominal = authority["parameter_inputs"]["components"]["plant"]
    for pid, context in contexts.items():
        _wire_links(context, contexts)
        initial = context["profile"]["initial_inputs"]
        _qclose(initial["plant_q_nb"], _axes_quaternion(offset) if pid == "E" else _IDENTITY_Q,
                context["path"] + "/initial_inputs/plant_q_nb")
        _qclose(initial["estimator_q_nb"], _IDENTITY_Q, context["path"] + "/initial_inputs/estimator_q_nb")
        _qclose(initial["attitude_command_q_nb"], _IDENTITY_Q,
                context["path"] + "/initial_inputs/attitude_command_q_nb")
        _qclose(initial["reset_local_command_q_nb"], _axes_quaternion([0.1, 0.0, 0.0]),
                context["path"] + "/initial_inputs/reset_local_command_q_nb")
        replay = pid in ("T1", "T2")
        _need((initial["epoch_id"], initial["epoch_origin_tick"], initial["epoch_origin_s"]) ==
              ((1, 1000, (1000*_BASE).hex()) if replay else (0, 0, 0.0.hex())),
              "initialization_mismatch", context["path"] + "/initial_inputs/epoch")
        expected_refs = ["b0_g0_contract:scenario=initial_attitude_offset/initial_attitude_offset_rad",
                         "g3a_evidence_spec:fixed qx(0.1) reset-local command"]
        _need(initial["source_refs"] == expected_refs, "initialization_mismatch",
              context["path"] + "/initial_inputs/source_refs")
        for key in ("plant_omega_b_rad_s", "estimator_omega_b_rad_s", "actuator_actual_torque_body_Nm"):
            _need(initial[key] == _hex_tree(list(_ZERO3)), "initialization_mismatch", context["path"] + "/initial_inputs/" + key)
        previous_feedback = None
        previous_held = None
        for boundary in context["profile"]["boundaries"]:
            tick, path = boundary["global_tick"], context["path"] + "/k" + str(boundary["global_tick"])
            expected_events, expected_q = _event_expectation(pid, tick, config)
            _need(_equal(boundary["event_inputs"], expected_events), "event_mismatch", path + "/event_inputs",
                  expected_events, boundary["event_inputs"])
            if boundary["boundary_kind"] == "reset":
                _reset_state(context, boundary, initial, authority)
                previous_held = boundary["published_after_ref"]
                if pid not in ("T1", "T2"):
                    reset_a = _boundary_operation(context, tick, "actuator", "reset")
                    previous_feedback = reset_a["outputs"].get("feedback")
                continue
            if pid not in ("T1", "T2"):
                _need(boundary["held_before_ref"] == previous_held, "held_command_mismatch", path)
            for operation in boundary["operations"]:
                _guarded(context, boundary, operation)
                owner, method = operation["owner"], operation["method"]
                if method == "publish":
                    result = _boundary_operation(context, tick, "controller", "step")
                    command_ref = result["outputs"].get("torque_command")
                    _need(operation["inputs"].get("torque_command") == command_ref and
                          boundary["published_after_ref"] == command_ref,
                          "held_command_mismatch", path + "/publish")
                elif owner in ("plant", "actuator") and method == "step_base":
                    scalars = operation["scalar_inputs"]
                    _need(scalars.get("dt_s") == _BASE.hex() and
                          (scalars.get("interval_start_tick"), scalars.get("interval_end_tick")) == (tick-1, tick),
                          "clock_mismatch", path + "/" + owner)
                    if owner == "plant":
                        feedback = _wire(context, operation["inputs"].get("feedback"), "feedback")
                        _need(feedback["wire_id"] == previous_feedback, "feedback_pair_mismatch", path + "/plant/input")
                        actual = feedback["payload"]["actual_torque_body_Nm"]
                        external = expected_events["external_torque_body_Nm"]
                        total = [(_number(a)+_number(b)).hex() for a, b in zip(actual, external)]
                        _need(scalars.get("external_torque_body_Nm") == external and
                              scalars.get("total_plant_torque_body_Nm") == total,
                              "event_mismatch", path + "/plant/scalar_inputs")
                elif owner == "imu":
                    truth = _wire(context, operation["inputs"].get("sensor_truth"), "sensor_truth")
                    plant = _boundary_operation(context, tick, "plant", "step_base")
                    state = _wire(context, plant["outputs"].get("plant_state"), "plant_state")
                    _need(truth["payload"]["q_nb"] == state["payload"]["q_nb"] and
                          truth["payload"]["omega_b_rad_s"] == state["payload"]["omega_b_rad_s"] and
                          truth["payload"]["translational_acceleration_n_m_s2"] == _hex_tree(list(_ZERO3)),
                          "producer_mismatch", path + "/sensor_boundary")
                    if boundary["local_tick"] in (2, 4):
                        capture = _snapshot(context, operation["after_snapshot_ref"])
                        count = boundary["local_tick"]//2
                        imu = capture["imu"]
                        _need((capture["global_tick"], capture["phase"]) == (tick, 3) and
                              imu is not None and imu["_samples_emitted"] == count and
                              imu["_local_tick"] == boundary["local_tick"] and
                              imu["_next_sample_tick"] == boundary["local_tick"]+2 and imu["_rng_seed"] == _SEED,
                              "rng_replay_mismatch", path + "/imu/public_sample_state")
                elif owner == "measurement_adapter":
                    source = _wire(context, operation["inputs"].get("raw_imu"), "imu")["payload"]
                    output = _wire(context, operation["outputs"].get("adapted_imu"), "imu")["payload"]
                    expected = copy.deepcopy(source)
                    for signal, bias_key, replacement_key in (
                        ("gyro_rad_s", "gyro_bias_rad_s", "replacement_gyro_bias_rad_s"),
                        ("specific_force_m_s2", "accelerometer_bias_m_s2", "replacement_accelerometer_bias_m_s2"),
                    ):
                        replacement = expected_events[replacement_key]
                        if replacement is not None:
                            expected[signal] = [((_number(a)-_number(b))+_number(c)).hex()
                                                for a, b, c in zip(source[signal], nominal[bias_key], replacement)]
                    expected["specific_force_m_s2"] = [(_number(a)+_number(b)).hex() for a, b in
                        zip(expected["specific_force_m_s2"], expected_events["additive_specific_force_body_m_s2"])]
                    _need(_equal(output, expected), "event_mismatch", path + "/adapt_measurement")
                elif owner == "controller":
                    command = _wire(context, operation["inputs"].get("attitude_command"), "attitude_command")
                    _qclose(command["payload"]["q_nb"], expected_q, path + "/attitude_command/q_nb")
                    _need(command["payload"]["valid"] is True, "event_mismatch", path + "/attitude_command/valid")
                    if operation["accepted"]:
                        _need(operation["scalar_inputs"].get("dt_s") == _PERIOD.hex(), "clock_mismatch", path + "/controller/dt")
                if not operation["accepted"]:
                    _invalid_call(context, boundary, operation)
            if pid not in ("T1", "T2"):
                actuator = _boundary_operation(context, tick, "actuator", "step_base")
                previous_feedback = actuator["outputs"].get("feedback")
            accepted_c = [op for op in boundary["operations"] if op["owner"] == "controller" and op["accepted"]]
            if not accepted_c:
                _need(boundary["published_after_ref"] == previous_held, "held_command_mismatch", path + "/no_publication")
            previous_held = boundary["published_after_ref"]


def _expected_session_next_tick(profile_id: str, completed_tick: int) -> int:
    """Fixed sparse T actual-next semantics; ordinary sessions stay base-next."""
    if profile_id in ("T1", "T2"):
        sparse_next = {1000: 1002, 1002: 1004, 1004: 1005}
        _need(completed_tick in sparse_next, "clock_mismatch", profile_id + "/next_global_tick",
              "retained T reset/replay boundary", completed_tick)
        return sparse_next[completed_tick]
    return completed_tick + 1


def _reset_state(context: dict[str, Any], boundary: dict[str, Any], initial: dict[str, Any],
                 authority: dict[str, Any]) -> None:
    tick, epoch = boundary["global_tick"], boundary["epoch_id"]
    path = context["path"] + "/reset/" + str(tick)
    controller = _boundary_operation(context, tick, "controller", "reset")
    estimator = _boundary_operation(context, tick, "estimator", "reset")
    origin = boundary["timestamp_s"]
    _need(controller["reset_inputs"] == {"kind": "reset", "actor": "controller",
          "reset_epoch": {"id": epoch, "timestamp_s": origin}}, "reset_mismatch", path + "/controller")
    estimate_input = {"kind": "reset", "actor": "estimator",
                      "initial_state": {"q_nb": initial["estimator_q_nb"],
                                        "omega_b_rad_s": initial["estimator_omega_b_rad_s"]},
                      "reset_epoch": {"id": epoch, "timestamp_s": origin}, "rng_seed": _SEED}
    _need(_equal(estimator["reset_inputs"], estimate_input), "reset_mismatch", path + "/estimator")
    command = _wire(context, controller["outputs"].get("torque_command"), "torque_command")
    zero = _hex_tree([0.0, 0.0, 0.0])
    expected_command = {"requested_torque_body_Nm": zero, "limited_torque_body_Nm": zero,
                        "saturated": [False]*3, "timestamp_s": origin}
    _need(_equal(command["payload"], expected_command) and command["epoch_id"] == epoch and
          boundary["published_after_ref"] == command["wire_id"], "reset_mismatch", path + "/command")
    replay = context["profile"]["profile_id"] in ("T1", "T2")
    if not replay:
        actuator = _boundary_operation(context, tick, "actuator", "reset")
        expected_a = {"kind": "reset", "actor": "actuator", "reset_epoch_s": origin,
                      "reset_command_ref": command["wire_id"], "initial_state": {
                          "actual_torque_body_Nm": initial["actuator_actual_torque_body_Nm"],
                          "held_limited_torque_body_Nm": zero, "held_requested_torque_body_Nm": zero,
                          "held_saturated": [False]*3, "held_command_timestamp_s": origin}}
        _need(_equal(actuator["reset_inputs"], expected_a), "reset_mismatch", path + "/actuator")
        plant = _boundary_operation(context, tick, "plant", "reset")
        _need(_equal(plant["reset_inputs"], {"kind": "reset", "actor": "plant",
              "initial_state": {"q_nb": initial["plant_q_nb"], "omega_b_rad_s": initial["plant_omega_b_rad_s"]},
              "reset_epoch_s": origin}), "reset_mismatch", path + "/plant")
        imu = _boundary_operation(context, tick, "imu", "reset")
        _need(_equal(imu["reset_inputs"], {"kind": "reset", "actor": "imu", "initial_state": {},
              "reset_epoch_s": origin, "rng_seed": _SEED}), "reset_mismatch", path + "/imu")
    before = _snapshot(context, controller["before_snapshot_ref"])
    after = _snapshot(context, estimator["after_snapshot_ref"])
    _need(before["capture_id"] != after["capture_id"], "snapshot_incomplete", path, incomplete=True)
    for snapshot in (before, after):
        _need((snapshot["global_tick"], snapshot["phase"]) == (tick, 0),
              "snapshot_incomplete", path + "/capture_point", incomplete=True)
    session = after["session"]
    _need(session["lifecycle"] == "active" and session["needs_reset"] is False and
          session["epoch_id"] == epoch and session["epoch_origin_tick"] == tick and
          session["epoch_origin_s"] == origin and session["next_global_tick"] ==
          _expected_session_next_tick(context["profile"]["profile_id"], tick) and
          session["phase_cursor"] == 0 and session["pending_inputs"] == [] and
          session["pending_publication"] is None and session["pending_event_state"] is None and
          session["last_raw_sample"] is None and session["last_sample"] is None,
          "reset_mismatch", path + "/session")
    core = after["controller"]["snapshot"]
    _need(core["reset"] and core["epoch_id"] == epoch and core["tick_index"] == 0 and
          core["epoch_origin_s"] == origin and core["has_previous_rate"] is False and
          core["integral_Nm"] == zero and core["derivative_filtered_rad_s2"] == zero and
          core["previous_rate_rad_s"] == zero, "reset_mismatch", path + "/controller_state")
    held = dict(core["expected_held_command"])
    _need(held.pop("epoch_id") == epoch and _equal(held, expected_command), "reset_mismatch", path + "/core_held")
    estimated = after["estimator"]
    _need(estimated["_last_tick"] == 0 and estimated["_rng_seed"] == _SEED and
          estimated["_reset_epoch"] == {"id": epoch, "timestamp_s": origin}, "reset_mismatch", path + "/estimator_state")
    _qclose(estimated["_estimate"]["q_nb"], _IDENTITY_Q, path + "/estimator_state/q_nb")
    _need(estimated["_estimate"]["omega_b_rad_s"] == zero and estimated["_estimate"]["timestamp_s"] == origin
          and estimated["_estimate"]["valid"] is True, "reset_mismatch", path + "/estimator_state")
    if replay:
        _need(after["plant"] is None and after["actuator"] is None and after["imu"] is None,
              "reset_mismatch", path + "/no_live_components")
    else:
        observed_imu = after["imu"]
        _need(observed_imu is not None and observed_imu["_samples_emitted"] == 0 and
              observed_imu["_last_sample_timestamp"] is None and observed_imu["_next_sample_tick"] == 2
              and observed_imu["_local_tick"] == 0 and observed_imu["_rng_seed"] == _SEED and
              observed_imu["_rng_state"] is not None and observed_imu["_reset"] is True,
              "reset_mismatch", path + "/imu_state")
        for name in ("plant", "actuator", "imu"):
            _need(after[name]["_local_tick"] == 0 and after[name]["_epoch_origin_s"] == origin,
                  "reset_mismatch", path + "/" + name)
        _qclose(after["plant"]["_state"]["q_nb"], [_number(x) for x in initial["plant_q_nb"]], path + "/plant_state/q")
        _need(after["actuator"]["_actual"] == zero and after["actuator"]["_target"] == zero and
              after["actuator"]["_requested"] == zero and after["actuator"]["_saturated"] == [False]*3
              and after["actuator"]["_command_timestamp"] == origin,
              "reset_mismatch", path + "/actuator_state")
    if context["profile"]["profile_id"] in ("O1", "O2") and tick == 7:
        observed = before["controller"]["snapshot"]
        _need(observed["has_previous_rate"] and observed["tick_index"] >= 2 and
              any(_number(value) != 0.0 for key in ("integral_Nm", "derivative_filtered_rad_s2", "previous_rate_rad_s")
                  for value in observed[key]) and
              any(_number(value) != 0.0 for value in before["actuator"]["_actual"]),
              "reset_mismatch", path + "/nonzero_activation")


def _invalid_call(context: dict[str, Any], boundary: dict[str, Any], operation: dict[str, Any]) -> None:
    pid, tick, owner = context["profile"]["profile_id"], boundary["global_tick"], operation["owner"]
    needs_reset = pid in ("O1", "O2") and tick == 6
    _preserved(context, operation["before_snapshot_ref"], operation["after_snapshot_ref"], needs_reset=needs_reset)
    for reference in (operation["before_snapshot_ref"], operation["after_snapshot_ref"]):
        snapshot = _snapshot(context, reference)
        _need((snapshot["global_tick"], snapshot["phase"]) == (tick, operation["phase"]),
              "snapshot_incomplete", context["path"] + "/invalid/capture_point", incomplete=True)
    if needs_reset:
        _need(owner == "controller" and operation["reason"] == "unexpected_tick" and
              operation["scalar_inputs"].get("dt_s") == _PERIOD.hex(),
              "invalid_recovery_mismatch", context["path"] + "/O6")
        command = _wire(context, operation["inputs"].get("attitude_command"), "attitude_command")
        _close_time(command["payload"]["timestamp_s"], _number(boundary["timestamp_s"])+_PERIOD,
                    context["path"] + "/O6/future_timestamp")
        return
    correction = [op for op in boundary["operations"] if op["owner"] == owner and
                  op["attempt_kind"] == "same_tick_correction"]
    _need(len(correction) == 1 and correction[0]["accepted"], "invalid_recovery_mismatch",
          context["path"] + f"/k{tick}/correction")
    if owner == "controller":
        _need(operation["scalar_inputs"].get("dt_s") == (-_PERIOD).hex() and
              correction[0]["scalar_inputs"].get("dt_s") == _PERIOD.hex() and
              _equal(operation["inputs"], correction[0]["inputs"]),
              "invalid_recovery_mismatch", context["path"] + "/negative_dt")
    else:
        bad = _wire(context, operation["inputs"].get("adapted_imu"), "imu")
        good = _wire(context, correction[0]["inputs"].get("adapted_imu"), "imu")
        altered = dict(bad["payload"])
        stale = altered["timestamp_s"]
        altered["timestamp_s"] = good["payload"]["timestamp_s"]
        previous = _boundary_operation(context, tick-2, "estimator", "process")
        prior = _wire(context, previous["outputs"].get("estimate"), "estimate")
        _need(stale == prior["payload"]["timestamp_s"] and _equal(altered, good["payload"])
              and stale != good["payload"]["timestamp_s"], "invalid_recovery_mismatch",
              context["path"] + "/stale_timestamp")


def _consumptions(contexts: dict[str, dict[str, Any]], authority: dict[str, Any]) -> None:
    for pid, context in contexts.items():
        for boundary in context["profile"]["boundaries"]:
            if boundary["boundary_kind"] == "reset":
                continue
            tick, time = boundary["global_tick"], _number(boundary["timestamp_s"])
            operations = boundary["operations"]
            if pid not in ("T1", "T2"):
                delegated = [operation for operation in operations if _delegate(operation)]
                _need(len(delegated) == 1, "lifecycle_observation_missing",
                      context["path"] + f"/k{tick}/actuator/step", 1, len(delegated), incomplete=True)
            for operation in operations:
                owner = operation["owner"]
                if _delegate(operation):
                    outer = _boundary_operation(context, tick, "actuator", "step_base")
                    _need(_equal(operation["inputs"], outer["inputs"]) and
                          _equal(operation["outputs"], outer["outputs"]), "feedback_pair_mismatch",
                          context["path"] + f"/k{tick}/delegated_actuator")
                    continue
                for reference in operation["outputs"].values():
                    wire = _wire(context, reference)
                    if operation["accepted"]:
                        _need(wire["epoch_id"] == boundary["epoch_id"] and wire["global_tick"] == tick and
                              wire["local_tick"] == boundary["local_tick"], "producer_mismatch",
                              context["path"] + "/wires/" + reference)
                    if "timestamp_s" in wire["payload"] and operation["accepted"]:
                        _close_time(wire["payload"]["timestamp_s"], time,
                                    context["path"] + "/wires/" + reference + "/timestamp_s")
                if owner == "estimator" and operation["accepted"]:
                    sample = _wire(context, operation["inputs"].get("adapted_imu"), "imu")
                    _close_time(sample["payload"]["timestamp_s"], time, context["path"] + "/estimator/input_time")
                    if pid not in ("T1", "T2"):
                        adapter = _boundary_operation(context, tick, "measurement_adapter", "adapt_measurement")
                        _need(sample["wire_id"] == adapter["outputs"].get("adapted_imu"),
                              "producer_mismatch", context["path"] + "/estimator/input")
                    estimate = _wire(context, operation["outputs"].get("estimate"), "estimate")
                    diagnostics = _wire(context, operation["outputs"].get("estimator_diagnostics"), "estimator_diagnostics")
                    _need(estimate["payload"]["valid"] is True and diagnostics["payload"]["accepted"] is True and
                          diagnostics["payload"]["reason"] == "accepted" and
                          diagnostics["payload"]["elapsed_periods"] == 1 and
                          diagnostics["payload"]["missing_periods"] == 0 and
                          diagnostics["payload"]["gap_approximated"] is False,
                          "producer_mismatch", context["path"] + "/estimator/output")
                elif owner == "controller":
                    e = _boundary_operation(context, tick, "estimator", "process")
                    _need(operation["inputs"].get("estimate") == e["outputs"].get("estimate"),
                          "producer_mismatch", context["path"] + "/controller/estimate")
                    if pid not in ("T1", "T2"):
                        a = _boundary_operation(context, tick, "actuator", "step_base")
                        _need(operation["inputs"].get("feedback") == a["outputs"].get("feedback"),
                              "feedback_pair_mismatch", context["path"] + "/controller/feedback")
                    if operation["accepted"]:
                        q = _wire(context, operation["inputs"].get("attitude_command"), "attitude_command")
                        _close_time(q["payload"]["timestamp_s"], time, context["path"] + "/controller/command_time")
                        torque = _wire(context, operation["outputs"].get("torque_command"), "torque_command")
                        diagnostic = _wire(context, operation["outputs"].get("controller_diagnostics"), "controller_diagnostics")["payload"]
                        _need(diagnostic["accepted"] is True and diagnostic["reason"] == "accepted" and
                              diagnostic["epoch_id"] == boundary["epoch_id"] and
                              diagnostic["tick_index"] == boundary["local_tick"]//2 and
                              diagnostic["requested_Nm"] == torque["payload"]["requested_torque_body_Nm"] and
                              diagnostic["limited_Nm"] == torque["payload"]["limited_torque_body_Nm"] and
                              diagnostic["saturated"] == torque["payload"]["saturated"],
                              "feedback_pair_mismatch", context["path"] + "/controller/diagnostics")


def _probes(contexts: dict[str, dict[str, Any]], lifecycle: dict[str, Any]) -> None:
    wanted = {
        ("L1", "old_epoch", 1001, 2, "held_torque"),
        ("L1", "old_epoch", 1002, 4, "imu"),
        ("L1", "old_epoch", 1002, 5, "feedback"),
        ("L1", "old_epoch", 1002, 5, "estimate"),
        ("L1", "old_epoch", 1002, 5, "attitude_command"),
        ("L1", "truth_negative", 1002, 4, "imu"),
        ("L1", "truth_negative", 1002, 5, "estimate"),
        ("O1", "needs_reset", 7, 0, "ordinary_boundary"),
        ("O2", "needs_reset", 7, 0, "ordinary_boundary"),
    }
    seen: Counter = Counter()
    role_keys = {"held_torque": "torque_command", "feedback": "feedback", "imu": "adapted_imu",
                 "estimate": "estimate", "attitude_command": "attitude_command"}
    for pid, context in contexts.items():
        for probe in context["profile"]["probes"]:
            path = context["path"] + "/probes/" + probe["probe_id"]
            event = "accepted" if probe["accepted"] else probe["reason"]
            lifecycle["auxiliary_counts"][pid][f"guard:{probe['guard_site']}:{event}"] += 1
            if probe["kind"] == "normal_guard":
                _need(probe["consumer_operation_id"] in context["ops"], "guard_missing", path, incomplete=True)
                continue
            key = (pid, probe["kind"], probe["global_tick"], probe["phase"], probe["role"])
            _need(key in wanted, "probe_coverage_missing", path, actual=key)
            seen[key] += 1
            reason = {"old_epoch": "stale_epoch", "truth_negative": "truth_dependency_forbidden",
                      "needs_reset": "needs_reset"}[probe["kind"]]
            _need(probe["accepted"] is False and probe["reason"] == reason,
                  "guard_rejection_mismatch", path, reason, probe["reason"])
            delta = probe["component_call_delta"]
            _need(set(delta) == set(_COMPONENT_COUNTERS) and all(value == 0 for value in delta.values()),
                  "guard_rejection_mismatch", path + "/component_call_delta")
            _preserved(context, probe["before_snapshot_ref"], probe["after_snapshot_ref"])
            for reference in (probe["before_snapshot_ref"], probe["after_snapshot_ref"]):
                capture = _snapshot(context, reference)
                _need((capture["global_tick"], capture["phase"]) == (probe["global_tick"], probe["phase"]),
                      "snapshot_incomplete", path + "/capture_location", incomplete=True)
            if probe["kind"] == "needs_reset":
                _need(_snapshot(context, probe["before_snapshot_ref"])["session"]["lifecycle"] == "needs_reset",
                      "invalid_recovery_mismatch", path)
                continue
            operation = context["ops"].get(probe["consumer_operation_id"])
            _need(operation is not None, "guard_missing", path, incomplete=True)
            candidate = _wire(context, probe["candidate_ref"])
            original = _wire(context, probe["original_legal_ref"])
            role_key = role_keys[probe["role"]]
            _need(operation["inputs"].get(role_key) == original["wire_id"] and
                  probe["checked_refs"].get(role_key) == candidate["wire_id"] and
                  candidate["role"] == original["role"], "guard_rejection_mismatch", path)
            expected_bundle = dict(operation["inputs"])
            expected_bundle[role_key] = candidate["wire_id"]
            _need(_equal(probe["checked_refs"], expected_bundle), "guard_rejection_mismatch", path + "/checked_refs")
            if probe["kind"] == "old_epoch":
                latest = _latest_old_role_value(context["wires"].values(), probe["role"], path)
                _need(candidate["epoch_id"] == 0 and original["epoch_id"] == 1 and
                      candidate["wire_id"] == latest["wire_id"],
                      "guard_rejection_mismatch", path + "/old_envelope")
            else:
                truth = _wire(context, probe["source_truth_ref"], "sensor_truth")
                _need(candidate["producer"] == "evaluator_truth" and candidate["epoch_id"] == original["epoch_id"]
                      and candidate["global_tick"] == 1002 and truth["global_tick"] == 1002 and
                      candidate["parent_ids"] == [truth["wire_id"], original["wire_id"]] and
                      type(probe["derivation_site"]) is str and bool(probe["derivation_site"]),
                      "truth_derivation_mismatch", path)
                source, target = (("omega_b_rad_s", "gyro_rad_s") if probe["role"] == "imu" else ("q_nb", "q_nb"))
                _need(probe["source_field"] == "sensor_truth." + source and
                      probe["target_field"] == ("imu." if probe["role"] == "imu" else "estimate.") + target,
                      "truth_derivation_mismatch", path + "/fields")
                expected = copy.deepcopy(original["payload"])
                expected[target] = truth["payload"][source]
                _need(_equal(candidate["payload"], expected), "truth_derivation_mismatch", path + "/candidate_payload")
            normal = context["probes"].get(operation["guard_ref"])
            _need(normal is not None and normal["guard_site"] == probe["guard_site"],
                  "guard_rejection_mismatch", path + "/shared_guard_site")
    _need(set(seen) == wanted and all(value == 1 for value in seen.values()),
          "probe_coverage_missing", "$/profiles/probes", sorted(wanted), sorted(seen))


def _latest_old_role_value(wires: Any, role: str, path: str) -> dict[str, Any]:
    """Select the actual last producer value at/before 998, never from 999.

    The producer/kind set is fixed by the five approved role probes; it is not
    inferred from the candidate's own claim.  Wire/operation links are checked
    separately against the retained actual operations.
    """
    origins = {"held_torque": ("torque_command", "controller"),
               "imu": ("imu", "measurement_adapter"), "feedback": ("feedback", "actuator"),
               "estimate": ("estimate", "estimator"), "attitude_command": ("attitude_command", "command_sampler")}
    _need(role in origins, "probe_coverage_missing", path + "/role")
    kind, producer = origins[role]
    eligible = [wire for wire in wires if wire["role"] == role and wire["kind"] == kind and
                wire["producer"] == producer and wire["epoch_id"] == 0 and wire["global_tick"] <= 998]
    _need(bool(eligible), "probe_coverage_missing", path + "/latest_old_role", incomplete=True)
    tick = max(wire["global_tick"] for wire in eligible)
    latest = [wire for wire in eligible if wire["global_tick"] == tick]
    _need(len(latest) == 1, "producer_mismatch", path + "/latest_old_role", "one actual latest producer value")
    return latest[0]


def _snapshot_bindings(contexts: dict[str, dict[str, Any]], authority: dict[str, Any]) -> None:
    expected = authority["parameter_inputs"]["components"]
    digests = {kind: _sha(_encoded(expected[kind])) for kind in ("plant", "estimator", "controller")}
    for pid, context in contexts.items():
        for snapshot in context["profile"]["snapshots"]:
            path = context["path"] + "/snapshots/" + snapshot["snapshot_id"]
            for role, target in (("plant", "plant"), ("actuator", "plant"), ("imu", "plant"),
                                 ("estimator", "estimator"), ("controller", "controller")):
                observed = snapshot[role]
                if observed is None:
                    _need(pid in ("T1", "T2") and role in ("plant", "actuator", "imu"),
                          "snapshot_incomplete", path + "/" + role, incomplete=True)
                    continue
                _need(observed["parameter_binding_sha256"].lower() == digests[target],
                      "constructor_binding_mismatch", path + "/" + role + "/parameter_binding_sha256")
            _need(_equal(snapshot["controller"]["adapter_parameter_values"], expected["controller"]),
                  "constructor_binding_mismatch", path + "/controller/adapter_parameter_values")
            if snapshot["plant"] is not None:
                _need(snapshot["plant"]["_inertia"] == expected["plant"]["inertia_kg_m2"] and
                      snapshot["actuator"]["_limits"] == expected["plant"]["actuator_limits_Nm"] and
                      snapshot["actuator"]["_time_constant"] == expected["plant"]["actuator_time_constant_s"],
                      "constructor_binding_mismatch", path + "/G1_cached_values")
            session = snapshot["session"]
            _need(session["needs_reset"] == (session["lifecycle"] == "needs_reset"),
                  "snapshot_incomplete", path + "/session/lifecycle", incomplete=True)
            inputs = session["configuration_values"]
            for name in ("plant_q_nb", "plant_omega_b_rad_s", "estimator_q_nb", "estimator_omega_b_rad_s", "actuator_actual_torque_body_Nm"):
                _need(_equal(inputs[name], context["profile"]["initial_inputs"][name]),
                      "snapshot_changed", path + "/session/configuration_values/" + name)
            imu = snapshot["imu"]
            if imu is not None:
                uninitialized = (session["lifecycle"] == "new" and imu["_reset"] is False and
                                 imu["_samples_emitted"] == imu["_local_tick"] == imu["_next_sample_tick"] == 0 and
                                 imu["_last_reset_epoch"] is None and imu["_epoch_origin_s"] is None and
                                 imu["_last_sample_timestamp"] is None)
                _pcg64_state(imu["_rng_state"], path + "/imu/_rng_state", allow_uninitialized=uninitialized)


def _closed_auxiliary_counts(actual: Counter, planned: dict[str, int], path: str) -> dict[str, int]:
    """All observed names are predeclared; preserve explicit planned zeros.

    This implementation chooses the fully enumerated accepted-plan option; it
    does not silently derive a new coverage-name family from the actual raw.
    Unknown actuals remain in the diagnostic but prevent complete acceptance.
    """
    unknown = set(actual) - set(planned)
    _need(not unknown, "counter_set_mismatch", path,
          {"accepted_auxiliary_keys": sorted(planned)},
          {"undeclared_actual_auxiliary": {key: actual[key] for key in sorted(unknown)}}, incomplete=True)
    for key, expected in planned.items():
        _need(actual[key] == expected, "count_mismatch", path + "/" + key, expected, actual[key])
    return {key: actual[key] for key in planned}


def _actual_counts(contexts: dict[str, dict[str, Any]], lifecycle: dict[str, Any],
                   authority: dict[str, Any]) -> dict[str, dict[str, int]]:
    counts = {}
    for pid, context in contexts.items():
        observed = Counter({key: 0 for key in _COUNTERS})
        observed.update(lifecycle["component_counts"][pid])
        for operation in context["ops"].values():
            owner, method = operation["owner"], operation["method"]
            if method == "reset":
                observed[owner + "_reset"] += 1
            elif owner in ("plant", "actuator") and method == "step_base":
                observed[owner + "_step_base"] += 1
            elif owner == "imu" and method == "sample":
                observed["imu_sample"] += 1
            elif owner in ("estimator", "controller") and method in ("process", "step"):
                observed[owner + ("_process" if owner == "estimator" else "_step")] += 1
                observed[owner + ("_accepted" if operation["accepted"] else "_rejected")] += 1
            if _delegate(operation):
                lifecycle["auxiliary_counts"][pid]["operation:actuator:step"] += 1
        for probe in context["profile"]["probes"]:
            if probe["kind"] in ("old_epoch", "needs_reset", "truth_negative"):
                observed[probe["kind"] + "_rejected"] += 1
        horizon, reset_ticks = _profile_shape(pid)
        expected = Counter({key: 0 for key in _COUNTERS})
        if pid in ("T1", "T2"):
            expected.update({"estimator_process": 2, "estimator_accepted": 2, "controller_step": 2,
                             "controller_accepted": 2, "estimator_reset": 1, "controller_reset": 1})
        else:
            for tick in range(horizon+1):
                reset = tick in reset_ticks
                origin = max(value for value in reset_ticks if value <= tick)
                for owner, method, _, _, accepted, _ in _expected_operations(pid, tick, reset, tick-origin):
                    if method == "reset":
                        expected[owner + "_reset"] += 1
                    elif method == "step_base":
                        expected[owner + "_step_base"] += 1
                    elif owner == "imu":
                        expected["imu_sample"] += 1
                    elif owner in ("estimator", "controller"):
                        expected[owner + ("_process" if owner == "estimator" else "_step")] += 1
                        expected[owner + ("_accepted" if accepted else "_rejected")] += 1
            for owner in ("plant", "actuator", "imu"):
                expected[owner + "_constructor"] = 1
        expected.update({"estimator_constructor": 1, "controller_adapter_constructor": 1,
                         "controller_core_constructor": 2})
        if pid == "L1":
            expected.update({"old_epoch_rejected": 5, "truth_negative_rejected": 2})
        if pid in ("O1", "O2"):
            expected["needs_reset_rejected"] = 1
        _need(all(observed[key] == expected[key] for key in _COUNTERS), "count_mismatch",
              context["path"] + "/actual_counts", dict(expected), dict(observed))
        auxiliary = lifecycle["auxiliary_counts"][pid]
        planned = authority["execution_plan"]["auxiliary_counts"][pid]
        for key in planned:
            _need(key.startswith(("lifecycle:", "guard:", "operation:")), "counter_set_mismatch",
                  "authority/execution_plan/auxiliary_counts/" + pid + "/" + key, incomplete=True)
            if key.startswith("lifecycle:"):
                site, event = key[len("lifecycle:"):].rsplit(":", 1)
                _need(site in authority["execution_plan"]["lifecycle_callsites"] and
                      event in {"enter", "return", "exception"}, "counter_set_mismatch",
                      "authority/execution_plan/auxiliary_counts/" + key, incomplete=True)
            elif key.startswith("operation:"):
                _need(key == "operation:actuator:step", "counter_set_mismatch",
                      "authority/execution_plan/auxiliary_counts/" + key, incomplete=True)
            elif key.startswith("guard:"):
                site, _ = key[len("guard:"):].rsplit(":", 1)
                _need(any(probe["guard_site"] == site for item in contexts.values()
                          for probe in item["profile"]["probes"]), "counter_set_mismatch",
                      "authority/execution_plan/auxiliary_counts/" + key, incomplete=True)
        reconciled_auxiliary = _closed_auxiliary_counts(auxiliary, planned, context["path"] + "/auxiliary")
        reported = context["profile"]["reported_counts"]
        _need(set(reported) == set(_COUNTERS) | set(planned), "counter_set_mismatch",
              context["path"] + "/reported_counts", actual=list(reported))
        for key, value in reported.items():
            actual = observed[key] if key in observed else auxiliary[key]
            _need(value == actual, "count_mismatch", context["path"] + "/reported_counts/" + key, actual, value)
        counts[pid] = dict(observed)
        counts[pid].update(reconciled_auxiliary)
    return counts


_QUAT_FIELDS = {"q_nb", "plant_q_nb", "estimator_q_nb", "attitude_command_q_nb",
                "reset_local_command_q_nb", "command_q_nb"}
_TIME_FIELDS = {"timestamp_s", "command_timestamp_s", "epoch_origin_s", "expected_timestamp_s",
                "reset_epoch_s", "_last_reset_epoch", "_epoch_origin_s", "_command_timestamp",
                "_timestamp", "_reset_epoch", "_last_sample_timestamp", "held_command_timestamp_s"}
_PAYLOAD_UNITS = {
    "plant_state": {"omega_b_rad_s": "rad/s"},
    "sensor_truth": {"omega_b_rad_s": "rad/s", "translational_acceleration_n_m_s2": "m/s2"},
    "estimate": {"omega_b_rad_s": "rad/s"},
    "imu": {"gyro_rad_s": "rad/s", "specific_force_m_s2": "m/s2"},
    "torque_command": {"requested_torque_body_Nm": "Nm", "limited_torque_body_Nm": "Nm"},
    "feedback": {"actual_torque_body_Nm": "Nm", "limited_torque_body_Nm": "Nm"},
    "controller_diagnostics": {
        "rate_error_rad_s": "rad/s", "derivative_raw_rad_s2": "rad/s2",
        "derivative_filtered_rad_s2": "rad/s2", "proportional_Nm": "Nm",
        "integral_before_Nm": "Nm", "derivative_Nm": "Nm", "integral_after_Nm": "Nm",
        "requested_Nm": "Nm", "limited_Nm": "Nm",
        "conditional_integral_rate_Nm_s": "Nm/s", "limit_backcalculation_rate_Nm_s": "Nm/s",
        "lag_backcalculation_rate_Nm_s": "Nm/s",
    },
}


def _comparison_policy(path: tuple[Any, ...], kind: str | None, mode: str) -> tuple[float, float, str, str]:
    names = [item for item in path if type(item) is str]
    field = names[-1] if names else ""
    if field in _QUAT_FIELDS:
        return _TOL, 0.0, "1", "quaternion_component_absolute_1e-12"
    if mode == "twin":
        return 0.0, 0.0, "same_value", "same_build_exact_non_quaternion"
    copied = any(item in {"parameter_objects", "adapter_parameter_values", "configuration_values",
                          "initial_inputs", "reset_inputs", "event_inputs", "last_event_state",
                          "pending_event_state"} for item in names)
    if copied or kind == "reset_arguments":
        return 0.0, 0.0, "copied_input", "canonical_exact"
    if field in _TIME_FIELDS:
        return _TOL, 0.0, "s", "timestamp_absolute_1e-12"
    if kind in _PAYLOAD_UNITS and field in _PAYLOAD_UNITS[kind]:
        return _TOL, _TOL, _PAYLOAD_UNITS[kind][field], "non_q_finite_path_consistency"
    if field == "total_plant_torque_body_Nm" and "scalar_inputs" in names:
        return _TOL, _TOL, "Nm", "non_q_finite_path_consistency"
    if field in {"dt_s", "external_torque_body_Nm", "translational_acceleration_n_m_s2"} and "scalar_inputs" in names:
        return 0.0, 0.0, "copied_input", "canonical_exact"
    if "actuator" in names and field in {"_actual", "_target", "_requested"}:
        return _TOL, _TOL, "Nm", "non_q_finite_path_consistency"
    if "controller" in names and "snapshot" in names:
        if field == "integral_Nm":
            return _TOL, _TOL, "Nm", "non_q_finite_path_consistency"
        if field == "derivative_filtered_rad_s2":
            return _TOL, _TOL, "rad/s2", "non_q_finite_path_consistency"
        if field == "previous_rate_rad_s":
            return _TOL, _TOL, "rad/s", "non_q_finite_path_consistency"
    if "plant" in names and field == "_inertia_inverse":
        return _TOL, _TOL, "1/(kg*m2)", "non_q_finite_path_consistency"
    if (("plant" in names and field == "_inertia") or
            ("actuator" in names and field in {"_limits", "_time_constant"})):
        return 0.0, 0.0, "copied_input", "canonical_exact"
    raise _Reject("comparison_policy_missing", "/".join(map(str, path)), actual={"field": field, "kind": kind},
                  incomplete=True)


def _compare_values(a: Any, b: Any, path: tuple[Any, ...], stats: dict[str, Any],
                    *, mode: str, kind: str | None = None) -> None:
    _need(type(a) is type(b), "replay_mismatch" if mode == "twin" else "float_comparison_failed",
          "/".join(map(str, path)), type(b).__name__, type(a).__name__)
    if type(a) is dict:
        _need(set(a) == set(b), "replay_mismatch", "/".join(map(str, path)), list(b), list(a))
        wire_kind = a.get("kind") if a.get("kind") in _PAYLOAD_UNITS or a.get("kind") in ("attitude_command", "estimator_diagnostics") else None
        for key in a:
            child_kind = wire_kind if key == "payload" and wire_kind else kind
            if a.get("kind") == "reset":
                child_kind = "reset_arguments"
            if key == "_state":
                child_kind = "plant_state"
            elif key == "_estimate":
                child_kind = "estimate"
            elif key == "last_diagnostics":
                child_kind = "controller_diagnostics"
            elif key == "expected_held_command":
                child_kind = "torque_command"
            _compare_values(a[key], b[key], path+(key,), stats, mode=mode, kind=child_kind)
    elif type(a) is list:
        _need(len(a) == len(b), "replay_mismatch", "/".join(map(str, path)), len(b), len(a))
        for index, (left, right) in enumerate(zip(a, b)):
            _compare_values(left, right, path+(index,), stats, mode=mode, kind=kind)
    elif type(a) is str and (a.startswith(("0x", "-0x")) or b.startswith(("0x", "-0x"))):
        absolute, relative, unit, policy = _comparison_policy(path, kind, mode)
        left, right = _number(a), _number(b)
        difference, bound = abs(left-right), absolute+relative*abs(right)
        _need((a == b if absolute == relative == 0.0 else difference <= bound),
              "float_comparison_failed", "/".join(map(str, path)),
              {"reference": b, "allowed_absolute_plus_relative": bound.hex(), "policy": policy, "unit": unit},
              {"value": a, "absolute_difference": difference.hex()})
        entry = stats.get(policy)
        if entry is None or difference > float.fromhex(entry["max_absolute_difference"]):
            stats[policy] = {"max_absolute_difference": difference.hex(), "path": list(path),
                             "unit": unit, "reference": b, "value": a, "bound": bound.hex()}
    else:
        _need(_equal(a, b), "replay_mismatch", "/".join(map(str, path)), b, a)


def _streams(context: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for boundary in context["profile"]["boundaries"]:
        for operation in boundary["operations"]:
            if _delegate(operation) or operation["owner"] in ("session", "measurement_adapter"):
                continue
            record = {key: operation[key] for key in ("owner", "method", "phase", "attempt_kind", "accepted", "reason")}
            record.update({key: boundary[key] for key in ("global_tick", "local_tick", "epoch_id")})
            record["scalar_inputs"] = operation["scalar_inputs"]
            record["inputs"] = {key: {"kind": _wire(context, reference)["kind"],
                                       "payload": _wire(context, reference)["payload"]}
                                for key, reference in operation["inputs"].items()}
            record["outputs"] = {key: {"kind": _wire(context, reference)["kind"],
                                        "payload": _wire(context, reference)["payload"]}
                                 for key, reference in operation["outputs"].items()}
            if operation["reset_inputs"] is not None:
                record["reset_inputs"] = {key: value for key, value in operation["reset_inputs"].items()
                                           if key != "reset_command_ref"}
            result.append(record)
    return result


def _replay_input_payload(actual: dict[str, Any], expected: dict[str, Any], owner: str,
                          key: str, path: tuple[Any, ...], stats: dict[str, Any]) -> None:
    _need(actual["epoch_id"] == expected["epoch_id"], "replay_mismatch", "/".join(map(str, path)) + "/epoch_id")
    if owner == "controller" and key == "estimate":
        # T's actual E recomputes this value.  Its exact within-T E -> C wire
        # pairing is checked by _consumptions; cross-L1 q is recomputed, not a
        # frozen copied input.  Same-build non-q policy remains exact.
        _compare_values(actual["payload"], expected["payload"], path, stats, mode="twin", kind="estimate")
    else:
        _need(_equal(actual["payload"], expected["payload"]), "replay_mismatch",
              "/".join(map(str, path)), "exact fixed copied input", actual["payload"])


def _replay(contexts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    stats: dict[str, Any] = {}
    for first, second in (("L1", "L2"), ("O1", "O2")):
        _compare_values(_streams(contexts[first]), _streams(contexts[second]),
                        (first+"~"+second,), stats, mode="twin")
    seed_state = None
    for pid, context in contexts.items():
        if pid in ("T1", "T2"):
            continue
        for reset_tick in context["profile"]["reset_ticks"]:
            operation = _boundary_operation(context, reset_tick, "estimator", "reset")
            state = _snapshot(context, operation["after_snapshot_ref"])["imu"]["_rng_state"]
            if seed_state is None:
                seed_state = state
            _need(_equal(state, seed_state), "rng_replay_mismatch", context["path"] + "/reset_rng_state")
        if pid in ("O1", "O2"):
            for before, after in ((2, 9), (4, 11)):
                a = _boundary_operation(context, before, "imu", "sample")
                b = _boundary_operation(context, after, "imu", "sample")
                left = dict(_wire(context, a["outputs"].get("raw_imu"), "imu")["payload"])
                right = dict(_wire(context, b["outputs"].get("raw_imu"), "imu")["payload"])
                left.pop("timestamp_s")
                right.pop("timestamp_s")
                _need(_equal(left, right), "rng_replay_mismatch", context["path"] + "/post_reset_IMU")
    for pid in ("T1", "T2"):
        for tick in (1002, 1004):
            for owner, method in (("estimator", "process"), ("controller", "step")):
                original = _boundary_operation(contexts["L1"], tick, owner, method)
                replay = _boundary_operation(contexts[pid], tick, owner, method)
                for key, reference in original["inputs"].items():
                    actual = _wire(contexts[pid], replay["inputs"].get(key))
                    expected = _wire(contexts["L1"], reference)
                    _replay_input_payload(actual, expected, owner, key,
                                          (pid, tick, owner, "inputs", key), stats)
                for key, reference in original["outputs"].items():
                    actual = _wire(contexts[pid], replay["outputs"].get(key))
                    expected = _wire(contexts["L1"], reference)
                    _compare_values(actual["payload"], expected["payload"],
                                    (pid, tick, owner, "outputs", key), stats, mode="twin", kind=actual["kind"])
    # The finite metamorphic perturbation itself must be retained, not merely a label.
    for tick in (1002, 1004):
        def truth(context: dict[str, Any]) -> dict[str, Any]:
            candidates = [wire for wire in context["wires"].values() if wire["kind"] == "sensor_truth"
                          and wire["global_tick"] == tick and wire["producer"] == "evaluator_truth"]
            _need(len(candidates) == 1, "truth_derivation_mismatch", context["path"] + "/evaluator_truth", incomplete=True)
            return candidates[0]["payload"]
        source_candidates = [wire for wire in contexts["L1"]["wires"].values() if wire["kind"] == "sensor_truth"
                             and wire["global_tick"] == tick and wire["producer"] == "plant_truth_boundary"]
        _need(len(source_candidates) == 1, "truth_derivation_mismatch", "L1/truth", incomplete=True)
        original = source_candidates[0]["payload"]
        first, second = truth(contexts["T1"]), truth(contexts["T2"])
        _need(_equal(first, original), "truth_derivation_mismatch", "T1/truth_copy")
        offset = [0.174533, -0.139626, 0.0]
        _qclose(second["q_nb"], _qmul([_number(x) for x in original["q_nb"]], _axes_quaternion(offset)), "T2/truth_copy/q")
        _need(second["omega_b_rad_s"] == original["omega_b_rad_s"] and
              second["translational_acceleration_n_m_s2"] == original["translational_acceleration_n_m_s2"] and
              any(abs(_number(a)-_number(b)) > _TOL for a, b in zip(first["q_nb"], second["q_nb"])),
              "truth_derivation_mismatch", "T1~T2/distinct_evaluator_copy")
    return stats


def _normalized_view(raw: dict[str, Any], contexts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    references: dict[str, Any] = {}
    for pid, context in contexts.items():
        seen: Counter = Counter()
        for boundary in context["profile"]["boundaries"]:
            for op in boundary["operations"]:
                base = (pid, boundary["global_tick"], op["owner"], op["method"], op["attempt_kind"])
                seen[base] += 1
                references[op["operation_id"]] = [*base, seen[base]]
        seen.clear()
        for wire in context["profile"]["wires"]:
            base = (pid, wire["kind"], wire["role"], wire["global_tick"], wire["phase"], wire["producer"])
            seen[base] += 1
            references[wire["wire_id"]] = [*base, seen[base]]
        seen.clear()
        for snap in context["profile"]["snapshots"]:
            base = (pid, "capture", snap["global_tick"], snap["phase"])
            seen[base] += 1
            references[snap["snapshot_id"]] = [*base, seen[base]]
            references[snap["capture_id"]] = [*base, seen[base]]
        seen.clear()
        for probe in context["profile"]["probes"]:
            base = (pid, "guard", probe["kind"], probe["global_tick"], probe["phase"], probe["role"])
            seen[base] += 1
            references[probe["probe_id"]] = [*base, seen[base]]
    for record in raw["parameter_objects"]:
        references[record["parameter_object_id"]] = ["parameter", record["kind"], record["values_sha256"]]
    seen = Counter()
    for event in raw["lifecycle_observations"]:
        if event["event"] == "enter":
            base = (event["profile_id"], event["callsite"], event["owner"], event["method"], event["core_use"])
            seen[base] += 1
            references[event["call_id"]] = [*base, seen[base]]
        elif event["event"] == "return" and event["method"] == "constructor":
            references[event["result"]["actor_id"]] = ["actor", *references[event["call_id"]]]

    def normalize(value: Any, key: str = "") -> Any:
        if type(value) is dict:
            return {field: normalize(child, field) for field, child in value.items()}
        if type(value) is list:
            return [normalize(child, key) for child in value]
        if type(value) is str and key == "module_sha256":
            return "accepted_corresponding_build_module"
        if type(value) is str and value in references:
            return references[value]
        return value

    return {"profiles": normalize(raw["profiles"]),
            "parameter_objects": sorted((normalize(item) for item in raw["parameter_objects"]), key=lambda item: _encoded(item)),
            "lifecycle_observations": normalize(raw["lifecycle_observations"]),
            "reported_counts": raw["reported_counts"]}


def _report(raw_bytes: bytes, authority: Any) -> dict[str, Any]:
    return {"report_version": _VERSION, "raw_sha256": _sha(raw_bytes) if type(raw_bytes) is bytes else None,
            "authority_basis_sha256": authority.get("authority_basis_sha256") if type(authority) is dict else None,
            "status": "execution_error_inconclusive", "reason": "partial_record", "path": "$",
            "profiles": {}, "groups": {}, "actual_counts": {}, "comparison_maxima": {},
            "limitations": list(_LIMITATIONS)}


def _failed(report: dict[str, Any], error: _Reject) -> dict[str, Any]:
    report.update(status="execution_error_inconclusive" if error.incomplete else "reject",
                  reason=error.reason, path=error.path, expected=error.expected, actual=error.actual)
    return report


def _semantic(raw: dict[str, Any], definition: dict[str, Any], authority: dict[str, Any]) -> dict[str, Any]:
    _schedule(raw)
    contexts = _contexts(raw)
    # Owning epoch/pair errors precede consequential guard/ref/count disagreement.
    _input_epoch_and_pairing(contexts, authority)
    parameters = _parameter_objects(raw, authority)
    lifecycle = _lifecycle(raw, authority, contexts, parameters)
    _snapshot_bindings(contexts, authority)
    _flow(contexts, authority)
    _consumptions(contexts, authority)
    _probes(contexts, lifecycle)
    actual = _actual_counts(contexts, lifecycle, authority)
    total = Counter()
    for counts in actual.values():
        total.update(counts)
    reported = raw["reported_counts"]
    _need(set(reported) == set(total),
          "counter_set_mismatch", "$/reported_counts")
    for key, value in reported.items():
        _need(value == total[key], "count_mismatch", "$/reported_counts/" + key, total[key], value)
    replay = _replay(contexts)
    return {"actual_counts": {"profiles": actual, "total": dict(total)},
            "setup_observations": lifecycle["setup_observations"],
            "comparison_maxima": replay, "contexts": contexts}


def check_record_set(raw_bytes: bytes, authority: dict) -> dict:
    """Check one sealed complete raw; no DUT, file, helper or subprocess calls."""
    report = _report(raw_bytes, authority)
    try:
        raw, definition = _preflight(raw_bytes, authority)
        checked = _semantic(raw, definition, authority)
        report.update({key: value for key, value in checked.items() if key != "contexts"})
        report.update(status="pass", reason="accepted", path="$")
        report["profiles"] = {pid: {"status": "pass_for_development_raw_subscope"} for pid in _ORDER}
        report["groups"] = {group: {"status": "pass_for_development_raw_subscope"} for group in _GROUPS}
        return report
    except _Reject as error:
        return _failed(report, error)
    except (KeyError, IndexError, TypeError, ValueError, OverflowError, RecursionError) as error:
        return _failed(report, _Reject("unclassified_contract_violation", "$", actual=str(error), incomplete=True))


def compare_builds(debug_raw: bytes, release_raw: bytes,
                   debug_authority: dict, release_authority: dict) -> dict:
    """Independent admission of both records, then finite declared field policies."""
    report = {"report_version": _VERSION, "status": "execution_error_inconclusive",
              "reason": "partial_record", "path": "$", "comparison_maxima": {},
              "limitations": list(_LIMITATIONS)}
    try:
        debug, ddef = _preflight(debug_raw, debug_authority)
        release, rdef = _preflight(release_raw, release_authority)
        dchecks = _semantic(debug, ddef, debug_authority)
        rchecks = _semantic(release, rdef, release_authority)
        _need(debug["identity"]["build_type"] == "Debug" and release["identity"]["build_type"] == "Release" and
              debug["identity"]["controller_module_path"] != release["identity"]["controller_module_path"] and
              debug["identity"]["controller_module_sha256"] != release["identity"]["controller_module_sha256"],
              "build_identity_not_distinct", "$/identity")
        for key in ("work_order_sha256", "source_commit", "source_tree", "source_closure_manifest_sha256",
                    "config_approval_manifest_sha256", "profile_definition_sha256", "parameter_inputs_manifest_sha256",
                    "observer_manifest_sha256", "seed", "classification"):
            _need(debug["identity"][key] == release["identity"][key], "cross_build_identity_mismatch", "$/identity/" + key)
        policy = debug_authority["comparison_policy"]
        _need(_equal(policy, release_authority["comparison_policy"]) and
              policy.get("recomputed_quaternion") == {"absolute": _TOL, "relative": 0,
                                                       "priority": "before_other_float_rules"} and
              policy.get("recomputed_non_quaternion", {}).get("absolute") == _TOL and
              policy.get("recomputed_non_quaternion", {}).get("relative") == _TOL and
              policy.get("unknown_path") == "comparison_policy_missing",
              "comparison_policy_missing", "authority/comparison_policy", incomplete=True)
        stats: dict[str, Any] = {}
        _compare_values(_normalized_view(debug, dchecks["contexts"]),
                        _normalized_view(release, rchecks["contexts"]), ("Debug~Release",), stats, mode="dr")
        report.update(status="pass", reason="accepted", path="$", comparison_maxima=stats,
                      debug_raw_sha256=_sha(debug_raw), release_raw_sha256=_sha(release_raw),
                      debug_actual_counts=dchecks["actual_counts"], release_actual_counts=rchecks["actual_counts"])
        return report
    except _Reject as error:
        return _failed(report, error)
    except (KeyError, IndexError, TypeError, ValueError, OverflowError, RecursionError) as error:
        return _failed(report, _Reject("unclassified_contract_violation", "$", actual=str(error), incomplete=True))


def make_data_diagnostics(raw_bytes: bytes, authority: dict) -> tuple[dict, ...]:
    """Make 13 isolated bytes/envelopes; deliberately does not run the checker."""
    raw, _ = _preflight(raw_bytes, authority)
    contexts = _contexts(raw)
    s, l = contexts["S"], contexts["L1"]
    e = _boundary_operation(s, 2, "estimator", "process")
    imu = _boundary_operation(s, 2, "imu", "sample")
    a = _boundary_operation(s, 2, "actuator", "step_base")
    le = _boundary_operation(l, 1002, "estimator", "process")
    profile_indices = {item["profile_id"]: index for index, item in enumerate(raw["profiles"])}

    def wire_index(context: dict[str, Any], reference: str) -> int:
        return next(index for index, wire in enumerate(context["profile"]["wires"]) if wire["wire_id"] == reference)

    def boundary_index(context: dict[str, Any], tick: int) -> int:
        return next(index for index, boundary in enumerate(context["profile"]["boundaries"]) if boundary["global_tick"] == tick)

    si, li = profile_indices["S"], profile_indices["L1"]
    bi = boundary_index(s, 2)
    ei = next(index for index, op in enumerate(s["boundaries"][2]["operations"]) if op["operation_id"] == e["operation_id"])
    mi = wire_index(s, imu["outputs"]["raw_imu"])
    ai = wire_index(s, a["outputs"]["feedback"])
    oldi = wire_index(l, le["inputs"]["adapted_imu"])
    specifications = (
        ("missing_due", "missing_due"), ("duplicate_due", "duplicate_due"),
        ("phase_order", "phase_order"), ("old_epoch", "stale_epoch"),
        ("feedback_pair", "feedback_pair_mismatch"), ("wrong_source", "source_mismatch"),
        ("wrong_module", "module_identity_mismatch"), ("missing_field", "missing_required_field"),
        ("nan", "nonfinite_nan"), ("inf", "nonfinite_inf"),
        ("frame", "frame_mismatch"), ("unit", "unit_mismatch"),
    )
    parent = _sha(raw_bytes)

    def entry(identifier: str, payload: bytes, mutation: Any, reason: str) -> dict[str, Any]:
        digest = _sha(payload)
        transport = {"sha256": digest, "artifact_locator": authority["transport"]["artifact_locator"] + "#" + identifier,
                     "parent_raw_sha256": parent, "diagnostic_id": identifier}
        return {"diagnostic_id": identifier, "parent_raw_sha256": parent, "raw_bytes": payload,
                "raw_sha256": digest, "transport": transport, "mutation": mutation, "expected_reason": reason}

    result = [entry("legal_control", raw_bytes, None, "accepted")]
    for identifier, reason in specifications:
        altered = copy.deepcopy(raw)
        mutation: dict[str, Any]
        operations = altered["profiles"][si]["boundaries"][bi]["operations"]
        if identifier in ("missing_due", "duplicate_due"):
            before = copy.deepcopy(operations[ei])
            path = f"/profiles/{si}/boundaries/{bi}/operations/{ei}"
            if identifier == "missing_due":
                operations.pop(ei)
                mutation = {"path": path, "operation": "remove", "before": before, "after": None}
            else:
                operations.insert(ei+1, copy.deepcopy(before))
                mutation = {"path": path, "operation": "insert_adjacent_duplicate", "before": before, "after": before}
        elif identifier == "phase_order":
            b1 = boundary_index(s, 1)
            ops = altered["profiles"][si]["boundaries"][b1]["operations"]
            pi = next(index for index, op in enumerate(ops) if op["owner"] == "plant")
            aj = next(index for index, op in enumerate(ops) if op["owner"] == "actuator" and op["method"] == "step_base")
            before = [copy.deepcopy(ops[pi]), copy.deepcopy(ops[aj])]
            ops[pi], ops[aj] = ops[aj], ops[pi]
            mutation = {"path": f"/profiles/{si}/boundaries/{b1}/operations", "operation": "swap_pair",
                        "indices": [pi, aj], "before": before, "after": list(reversed(before))}
        else:
            if identifier == "old_epoch":
                target, key, path = altered["profiles"][li]["wires"][oldi], "epoch_id", f"/profiles/{li}/wires/{oldi}/epoch_id"
                value = target[key]-1
            elif identifier == "feedback_pair":
                target, key, path = altered["profiles"][si]["wires"][ai]["payload"], "command_timestamp_s", f"/profiles/{si}/wires/{ai}/payload/command_timestamp_s"
                value = s["boundaries"][2]["timestamp_s"]
            elif identifier in ("wrong_source", "wrong_module"):
                key = "source_commit" if identifier == "wrong_source" else "controller_module_sha256"
                target, path = altered["identity"], "/identity/" + key
                value = ("0" if target[key][0] != "0" else "1") + target[key][1:]
            elif identifier == "missing_field":
                target, key, path = altered["profiles"][si]["wires"][mi]["payload"], "timestamp_s", f"/profiles/{si}/wires/{mi}/payload/timestamp_s"
                value = None
            elif identifier in ("nan", "inf"):
                target, key, path = altered["profiles"][si]["wires"][mi]["payload"]["gyro_rad_s"], 0, f"/profiles/{si}/wires/{mi}/payload/gyro_rad_s/0"
                value = identifier
            else:
                target = altered["conventions"]
                key = "body_frame" if identifier == "frame" else "angular_rate"
                path, value = "/conventions/" + key, "FLU" if identifier == "frame" else "deg/s"
            before = copy.deepcopy(target[key])
            _need(not _equal(before, value), "unclassified_contract_violation", path, "real mutation", incomplete=True)
            if identifier == "missing_field":
                del target[key]
                operation_name = "remove"
            else:
                target[key] = value
                operation_name = "replace"
            mutation = {"path": path, "operation": operation_name, "before": before, "after": value}
        payload = _encoded(altered) + b"\n"
        result.append(entry(identifier, payload, mutation, reason))
    return tuple(result)
