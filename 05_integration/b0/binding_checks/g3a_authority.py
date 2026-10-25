"""External G3-A source/build facts, never subject-generated expectations.

Importing this stdlib-only module defines functions/constants only.  The CLI is
an independently released metadata action, not an authorization to build, load
a binding, run a profile, or grant human F0/implementation acceptance.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import sysconfig
from typing import Any


POLICY_VERSION = "b0-g3a-authority-policy/v1"
AUTHORITY_VERSION = "b0-g3a-authority/v1"
SEED = 2026100900
CLASSIFICATION = "development_integration_not_normal_acceptance"
IDENTITY_KEYS = (
    "work_order_sha256", "source_commit", "source_tree",
    "source_closure_manifest_sha256", "config_approval_manifest_sha256",
    "profile_definition_sha256", "parameter_inputs_manifest_sha256",
    "observer_manifest_sha256", "environment_manifest_sha256",
    "f0_manifest_sha256", "controller_module_path", "controller_module_sha256",
    "controller_module_abi", "build_type", "seed", "classification",
)
G1_FIELDS = {
    "inertia_kg_m2", "actuator_time_constant_s", "actuator_limits_Nm",
    "gravity_n_m_s2", "gyro_noise_std_rad_s", "gyro_bias_rad_s",
    "accelerometer_noise_std_m_s2", "accelerometer_bias_m_s2",
    "base_period_s", "imu_period_ticks", "config_path",
}
ESTIMATOR_FIELDS = {
    "sample_period_s", "gravity_m_s2", "unit_norm_tolerance",
    "correction_gain_per_s", "accelerometer_gate_deviation_m_s2",
    "maximum_correction_step_rad", "timestamp_tolerance_s", "config_path",
    "g0_config_path",
}
CONTROLLER_FIELDS = {
    "attitude_kp", "rate_kp", "rate_ki", "rate_kd", "integral_limit_Nm",
    "rate_limit_rad_s", "torque_limit_Nm", "kaw_limit_per_s", "kaw_lag_per_s",
    "derivative_time_constant_s", "controller_period_s", "timestamp_tolerance_s",
    "quaternion_norm_tolerance",
}
PARAMETER_FIELDS = {
    "g1": G1_FIELDS, "estimator": ESTIMATOR_FIELDS,
    "controller": CONTROLLER_FIELDS,
}
POLICY_KEYS = {
    "policy_version", "work_order", "source_paths", "fixed_files",
    "config_approval_paths", "parameter_bindings", "evidence_files",
    "observer_paths", "comparison_policy", "conventions", "environment",
    "build", "ci", "canonical_lf_checks", "approval_digest_checks",
    "execution_plan",
}
SHA256 = re.compile(r"[0-9a-fA-F]{64}\Z")
SHA1 = re.compile(r"[0-9a-fA-F]{40}\Z")


class AuthorityError(ValueError):
    """A specific fail-closed metadata/preflight refusal."""

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(reason + (": " + detail if detail else ""))


def _require(condition: bool, reason: str, detail: str = "") -> None:
    if not condition:
        raise AuthorityError(reason, detail)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _digest(value: Any, label: str, *, git: bool = False) -> str:
    pattern = SHA1 if git else SHA256
    _require(isinstance(value, str) and pattern.fullmatch(value) is not None,
             "invalid_digest", label)
    return value.lower()


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        _require(key not in value, "duplicate_json_key", key)
        value[key] = item
    return value


def _constant(value: str) -> None:
    raise AuthorityError("nonfinite_json", value)


def _decode(data: bytes, label: str) -> Any:
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=_constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AuthorityError("invalid_json", label) from exc


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _object(value: Any, label: str) -> dict[str, Any]:
    _require(isinstance(value, dict), "object_required", label)
    return value


def _strings(value: Any, label: str, *, nonempty: bool = True) -> list[str]:
    _require(isinstance(value, list) and (bool(value) or not nonempty),
             "string_list_required", label)
    _require(all(isinstance(item, str) and bool(item) for item in value),
             "string_list_required", label)
    _require(len(value) == len(set(value)), "duplicate_list_item", label)
    return value


def _relative(value: Any) -> str:
    _require(isinstance(value, str) and bool(value) and "\\" not in value,
             "invalid_source_path", str(value))
    path = PurePosixPath(value)
    _require(not path.is_absolute() and value == path.as_posix()
             and all(part not in {".", ".."} for part in path.parts),
             "invalid_source_path", value)
    return value


def _source_file(root: Path, relative: str) -> Path:
    candidate = root / _relative(relative)
    resolved = candidate.resolve(strict=True)
    _require(resolved.is_relative_to(root) and candidate.is_file(),
             "source_path_escape_or_not_file", relative)
    return candidate


def _read(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise AuthorityError("input_unavailable", str(path)) from exc


def _pointer(document: Any, pointer: str) -> Any:
    _require(isinstance(pointer, str) and (pointer == "" or pointer.startswith("/")),
             "invalid_json_pointer", str(pointer))
    current = document
    if pointer == "":
        return current
    for raw in pointer[1:].split("/"):
        _require(re.search(r"~(?![01])", raw) is None, "invalid_json_pointer", pointer)
        token = raw.replace("~1", "/").replace("~0", "~")
        try:
            if isinstance(current, list):
                _require(re.fullmatch(r"0|[1-9][0-9]*", token) is not None,
                         "invalid_json_pointer", pointer)
                current = current[int(token)]
            else:
                current = _object(current, pointer)[token]
        except (KeyError, IndexError) as exc:
            raise AuthorityError("missing_json_pointer", pointer) from exc
    return current


def _float_tree(value: Any) -> Any:
    if isinstance(value, list):
        return [_float_tree(item) for item in value]
    _require(type(value) in {int, float}, "float_input_required")
    number = float(value)
    _require(math.isfinite(number), "nonfinite_parameter")
    return number.hex()


def _execution_plan(value: Any) -> dict[str, Any]:
    plan = _object(value, "execution_plan")
    _require(set(plan) == {"plan_version", "lifecycle_callsites", "auxiliary_counts"}
             and plan.get("plan_version") == "b0-g3a-execution-plan/v1", "execution_plan_shape")
    sites = _object(plan["lifecycle_callsites"], "lifecycle_callsites")
    _require(bool(sites), "execution_plan_empty")
    owners = {"plant", "actuator", "imu", "estimator", "controller", "controller_core",
              "g1_parameters", "estimator_parameters", "controller_parameters", "g1_loader",
              "estimator_loader", "controller_loader", "g0_validator", "observer", "session"}
    methods = {"constructor", "load_parameters", "load_config", "validate_config", "capture_snapshot", "reset"}
    for name, rule in sites.items():
        item = _object(rule, "callsite")
        _require(bool(name) and set(item) == {"owner", "method", "parent_site"}
                 and item["owner"] in owners and item["method"] in methods,
                 "callsite_rule_invalid", name)
        parents = item["parent_site"]
        _require(parents is None or (isinstance(parents, list) and bool(parents)
                 and len(parents) == len(set(parents))
                 and all(isinstance(parent, str) and parent in sites for parent in parents)),
                 "callsite_parent_invalid", name)
    counts = _object(plan["auxiliary_counts"], "auxiliary_counts")
    _require(set(counts) == {"S", "L1", "L2", "O1", "O2", "E", "T1", "T2"},
             "auxiliary_profile_set")
    for profile, counters in counts.items():
        items = _object(counters, "auxiliary_counts." + profile)
        _require(bool(items) and all(bool(key) and type(count) is int and count >= 0
                                    for key, count in items.items()),
                 "auxiliary_counter_invalid", profile)
    return plan


def expected_parameters(policy: dict[str, Any], source_bytes: dict[str, bytes],
                        root: Path) -> dict[str, Any]:
    """Pure approved-data mapping; never call production validation/loaders."""
    values: dict[str, dict[str, Any]] = {kind: {} for kind in PARAMETER_FIELDS}
    bindings = policy["parameter_bindings"]
    _require(isinstance(bindings, list) and bool(bindings), "missing_parameter_bindings")
    documents: dict[str, Any] = {}
    for binding in bindings:
        item = _object(binding, "parameter_binding")
        kind, field = item.get("component"), item.get("field")
        _require(kind in PARAMETER_FIELDS and field in PARAMETER_FIELDS[kind],
                 "unknown_parameter_field", f"{kind}.{field}")
        _require(field not in values[kind], "duplicate_parameter_field", f"{kind}.{field}")
        _require(isinstance(item.get("unit"), str) and bool(item["unit"]),
                 "parameter_unit_required", str(field))
        encoding = item.get("encoding")
        has_literal = "literal" in item
        _require(has_literal != ("source_path" in item), "parameter_source_ambiguous", str(field))
        if has_literal:
            _require(isinstance(item.get("source_locator"), str) and bool(item["source_locator"]),
                     "literal_source_locator_required", str(field))
            original = item["literal"]
        else:
            relative = _relative(item["source_path"])
            _require(relative in policy["fixed_files"] and relative in source_bytes,
                     "parameter_source_not_fixed", relative)
            if relative not in documents:
                documents[relative] = _decode(source_bytes[relative], relative)
            original = _pointer(documents[relative], item.get("json_pointer"))
        if encoding == "float64_tree":
            result = _float_tree(original)
        elif encoding == "exact_json":
            result = _decode(_json_bytes(original), "exact_parameter")
        elif encoding == "source_relative_path":
            _require(has_literal and field in {"config_path", "g0_config_path"},
                     "path_binding_not_permitted", str(field))
            relative = _relative(original)
            _require(relative in policy["fixed_files"] and relative in source_bytes,
                     "parameter_path_not_fixed", relative)
            result = str(_source_file(root, relative).resolve(strict=True))
        else:
            raise AuthorityError("unknown_parameter_encoding", str(encoding))
        values[kind][field] = result
    for kind, fields in PARAMETER_FIELDS.items():
        _require(set(values[kind]) == fields, "incomplete_expected_parameters", kind)
    _require(type(values["g1"]["imu_period_ticks"]) is int
             and values["g1"]["imu_period_ticks"] > 0,
             "integer_imu_period_required")
    for kind, fields in PARAMETER_FIELDS.items():
        for field in fields & {"config_path", "g0_config_path"}:
            _require(isinstance(values[kind][field], str)
                     and Path(values[kind][field]).is_absolute(),
                     "absolute_expected_path_required", f"{kind}.{field}")
    vector_fields = {
        "g1": {"actuator_limits_Nm", "gravity_n_m_s2", "gyro_noise_std_rad_s", "gyro_bias_rad_s",
               "accelerometer_noise_std_m_s2", "accelerometer_bias_m_s2"},
        "estimator": set(),
        "controller": {"attitude_kp", "rate_kp", "rate_ki", "rate_kd", "integral_limit_Nm",
                       "rate_limit_rad_s", "torque_limit_Nm", "kaw_limit_per_s", "kaw_lag_per_s"},
    }
    for kind, fields in PARAMETER_FIELDS.items():
        for field in fields - {"config_path", "g0_config_path", "imu_period_ticks"}:
            item = values[kind][field]
            if field == "inertia_kg_m2":
                valid = (isinstance(item, list) and len(item) == 3
                         and all(isinstance(row, list) and len(row) == 3
                                 and all(isinstance(cell, str) for cell in row) for row in item))
            elif field in vector_fields[kind]:
                valid = isinstance(item, list) and len(item) == 3 and all(isinstance(cell, str) for cell in item)
            else:
                valid = isinstance(item, str)
            _require(valid, "expected_parameter_shape", f"{kind}.{field}")
            scalars = (sum(item, []) if field == "inertia_kg_m2"
                       else item if field in vector_fields[kind] else [item])
            for scalar in scalars:
                try:
                    number = float.fromhex(scalar)
                    canonical = math.isfinite(number) and number.hex() == scalar
                except (ValueError, TypeError):
                    canonical = False
                _require(canonical, "expected_parameter_not_canonical_float", f"{kind}.{field}")
    components = {name: values["g1"] for name in ("plant", "actuator", "imu")}
    components.update({"estimator": values["estimator"], "controller": values["controller"]})
    return {
        "manifest_version": "b0-g3a-expected-parameter-inputs/v1",
        "semantics": "approved_expected_inputs_not_runtime_observations",
        "components": components, "bindings": bindings,
        "values_sha256": {kind: _sha(_json_bytes(value)) for kind, value in values.items()},
    }


def _load_policy(path: Path, expected: str, root: Path) -> tuple[dict[str, Any], bytes, str]:
    raw = _read(path)
    _require(_sha(raw) == _digest(expected, "policy"), "policy_digest_mismatch")
    policy = _object(_decode(raw, "policy"), "policy")
    required = POLICY_KEYS - {"canonical_lf_checks", "approval_digest_checks"}
    _require(required <= set(policy) <= POLICY_KEYS, "policy_key_set")
    _require(policy.get("policy_version") == POLICY_VERSION, "policy_version_mismatch")
    relative_policy = path.resolve(strict=True).relative_to(root).as_posix()
    paths = _strings(policy["source_paths"], "source_paths")
    for relative in paths:
        _relative(relative)
    _require(relative_policy in paths, "policy_not_in_source_closure")
    fixed = _object(policy["fixed_files"], "fixed_files")
    _require(relative_policy not in fixed, "circular_policy_hash")
    for relative, digest in fixed.items():
        _require(relative in paths, "fixed_file_not_in_closure", relative)
        _digest(digest, relative)
    work_order = _object(policy["work_order"], "work_order")
    _require(work_order.get("path") in paths, "work_order_not_in_closure")
    _digest(work_order.get("sha256"), "work_order")
    for category in ("config_approval_paths", "observer_paths"):
        _require(set(_strings(policy[category], category)) <= set(paths),
                 "manifest_path_not_in_closure", category)
    evidence = _object(policy["evidence_files"], "evidence_files")
    _require(set(evidence) == {"profile", "spec", "schema", "checker"}, "evidence_file_roles")
    _require(all(value in paths for value in evidence.values()), "evidence_not_in_closure")
    _object(policy["comparison_policy"], "comparison_policy")
    _object(policy["conventions"], "conventions")
    _execution_plan(policy["execution_plan"])
    return policy, raw, relative_policy


def _source_identity(root: Path, paths: list[str], source_bytes: dict[str, bytes],
                     git_executable: Path | None, source_facts: Path | None,
                     expected_source_facts_sha256: str | None) -> tuple[dict[str, Any], bytes | None]:
    _require((git_executable is None) != (source_facts is None), "source_provider_required")
    facts_raw: bytes | None = None
    provider_identity: dict[str, Any] = {}
    if source_facts is not None:
        _require(expected_source_facts_sha256 is not None, "external_source_facts_digest_required")
        facts_raw = _read(source_facts)
        _require(_sha(facts_raw) == _digest(expected_source_facts_sha256, "source_facts"),
                 "source_facts_digest_mismatch")
        facts = _object(_decode(facts_raw, "source_facts"), "source_facts")
        _require(facts.get("schema_version") == "b0-g3a-source-facts/v1", "source_facts_version")
        commit, tree = facts.get("source_commit"), facts.get("source_tree")
        blobs = _object(facts.get("files"), "source_facts.files")
        _require(set(blobs) == set(paths), "source_fact_path_set")
        provider = "externally_digest_bound_git_facts"
        provider_identity = {"facts_sha256": _sha(facts_raw)}
    else:
        _require(git_executable is not None and git_executable.is_absolute()
                 and git_executable.is_file(), "absolute_git_executable_required")
        provider_identity = {"executable": str(git_executable.resolve(strict=True)),
                             "sha256": _sha(_read(git_executable.resolve(strict=True))), "commands": []}
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith("GIT_")}
        environment.update({"GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"})

        def git_read(arguments: list[str]) -> bytes:
            command = [str(git_executable), "--no-optional-locks", "-c", "core.fsmonitor=false",
                       "-C", str(root), *arguments]
            provider_identity["commands"].append(command)
            completed = subprocess.run(command, env=environment, stdin=subprocess.DEVNULL,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       timeout=30, check=False)
            _require(completed.returncode == 0, "git_read_failed", " ".join(arguments[:2]))
            return completed.stdout

        commit = git_read(["rev-parse", "--verify", "HEAD"]).decode("ascii").strip()
        commit = _digest(commit, "source_commit", git=True)
        tree = git_read(["rev-parse", "--verify", commit + "^{tree}"]).decode("ascii").strip()
        listing = git_read(["ls-tree", "-r", "-z", commit, "--", *paths])
        blobs = {}
        for row in listing.split(b"\0"):
            if not row:
                continue
            header, name = row.split(b"\t", 1)
            mode, object_type, blob = header.decode("ascii").split(" ")
            _require(mode in {"100644", "100755"} and object_type == "blob",
                     "source_nonregular_git_entry", name.decode("utf-8"))
            relative = name.decode("utf-8")
            _require(relative not in blobs, "duplicate_git_path", relative)
            blobs[relative] = blob
        _require(set(blobs) == set(paths), "source_git_path_set")
        provider = "three_explicit_read_only_git_builtins"
    commit = _digest(commit, "source_commit", git=True)
    tree = _digest(tree, "source_tree", git=True)
    records = []
    for relative in paths:
        raw = source_bytes[relative]
        actual_blob = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
        _require(actual_blob == _digest(blobs[relative], relative, git=True),
                 "source_bytes_not_git_blob", relative)
        records.append({"path": relative, "bytes": len(raw), "sha256": _sha(raw),
                        "git_blob_sha1": actual_blob, "byte_policy": "exact_raw"})
    return {"manifest_version": "b0-g3a-source-closure/v1", "source_commit": commit,
            "source_tree": tree, "provider": provider, "provider_identity": provider_identity,
            "files": records}, facts_raw


def _expand_path(value: str, roots: dict[str, Path]) -> Path:
    _require(isinstance(value, str) and bool(value), "file_boundary_required")
    for token, root in roots.items():
        if value == token:
            return root.resolve(strict=False)
        if value.startswith(token + "/"):
            suffix = _relative(value[len(token) + 1:])
            return (root / suffix).resolve(strict=False)
    _require("$" not in value and Path(value).is_absolute(), "unknown_or_relative_file_boundary", value)
    return Path(value).resolve(strict=False)


def _fact_files(document: dict[str, Any], section: dict[str, Any], roots: dict[str, Path],
                label: str) -> tuple[list[dict[str, Any]], dict[str, bytes]]:
    required = _strings(section.get("required_file_roles"), label + ".required_file_roles")
    rules = _object(section.get("file_role_rules"), label + ".file_role_rules")
    _require(set(required) == set(rules), "role_rule_set", label)
    records = document.get("files")
    _require(isinstance(records, list) and bool(records), "fact_files_required", label)
    counts = {role: 0 for role in required}
    seen_paths: set[str] = set()
    seen_names: set[tuple[str, str]] = set()
    captured: dict[str, bytes] = {}
    observations = []
    for record in records:
        item = _object(record, label + ".file")
        role = item.get("role")
        _require(role in counts, "unknown_file_role", str(role))
        rule = _object(rules[role], label + ".rule")
        minimum, maximum = rule.get("min_files"), rule.get("max_files")
        _require(type(minimum) is int and type(maximum) is int and 1 <= minimum <= maximum,
                 "invalid_file_count_bounds", role)
        original = Path(item.get("path", ""))
        _require(original.is_absolute(), "fact_path_not_absolute", str(original))
        resolved = original.resolve(strict=True)
        _require(resolved.is_file(), "fact_not_regular_file", str(original))
        boundaries = [_expand_path(value, roots) for value in
                      _strings(rule.get("allowed_roots", []), role, nonempty=False)]
        exact = [_expand_path(value, roots) for value in
                 _strings(rule.get("allowed_paths", []), role, nonempty=False)]
        matching = [base for base in boundaries if resolved.is_relative_to(base)]
        _require(bool(matching) or resolved in exact, "fact_outside_role_boundary", str(original))
        if matching:
            selected = max(matching, key=lambda p: len(p.parts))
            relative_name = f"root[{boundaries.index(selected)}]/" + resolved.relative_to(selected).as_posix()
        else:
            relative_name = f"exact[{exact.index(resolved)}]/" + resolved.name
        _require(str(resolved) not in seen_paths and (role, relative_name) not in seen_names,
                 "duplicate_fact_path_or_name", str(original))
        seen_paths.add(str(resolved))
        seen_names.add((role, relative_name))
        data = _read(resolved)
        _require(_sha(data) == _digest(item.get("sha256"), str(original))
                 and type(item.get("bytes")) is int and len(data) == item["bytes"],
                 "fact_byte_identity_mismatch", str(original))
        counts[role] += 1
        _require(counts[role] <= maximum, "file_role_count_exceeded", role)
        key = f"{label}/{len(observations):06d}"
        captured[key] = data
        observations.append({"role": role, "path": str(original), "resolved_path": str(resolved),
                             "relative_name": relative_name, "bytes": len(data),
                             "sha256": _sha(data), "artifact_key": key})
    for role, count in counts.items():
        _require(rules[role]["min_files"] <= count <= rules[role]["max_files"],
                 "file_role_incomplete", role)
    return observations, captured


def _environment(raw: bytes, policy: dict[str, Any], roots: dict[str, Path]) -> tuple[dict[str, Any], dict[str, bytes]]:
    _require(sys.platform.startswith("linux"), "linux_environment_required")
    _require(sys.flags.isolated == 1 and sys.flags.dont_write_bytecode == 1,
             "isolated_no_bytecode_launch_required")
    document = _object(_decode(raw, "environment_facts"), "environment_facts")
    _require(document.get("schema_version") == "b0-g3a-environment-facts/v1", "environment_facts_version")
    section = _object(policy["environment"], "environment_policy")
    observed = {
        "major": sys.version_info.major, "minor": sys.version_info.minor,
        "soabi": sysconfig.get_config_var("SOABI") or sys.implementation.cache_tag,
        "prefix": sys.prefix, "base_prefix": sys.base_prefix, "executable": sys.executable,
    }
    declared = _object(document.get("python"), "environment.python")
    _require(all(declared.get(key) == value for key, value in observed.items()),
             "actual_interpreter_mismatch")
    _require(observed["major"] == section.get("python_major")
             and observed["minor"] == section.get("python_minor"), "python_policy_mismatch")
    records, captured = _fact_files(document, section, roots, "environment")
    binary = [item for item in records if item["role"] == "python_binary"]
    _require(len(binary) == 1 and Path(binary[0]["resolved_path"]) == Path(sys.executable).resolve(strict=True),
             "python_binary_binding_missing")
    packages = _object(section.get("package_versions"), "environment.package_versions")
    _require(document.get("package_versions") == packages, "declared_package_versions_mismatch")
    # importlib.metadata reads installed distribution metadata, not the packages.
    from importlib import metadata
    actual_packages = {}
    for name, version in packages.items():
        dist = metadata.distribution(name)
        normal_name = lambda value: re.sub(r"[-_.]+", "-", value).lower()
        _require(normal_name(dist.metadata.get("Name", "")) == normal_name(name)
                 and dist.version == version, "installed_package_mismatch", name)
        metadata_paths = [Path(dist.locate_file(item)).resolve(strict=True) for item in (dist.files or ())
                          if item.name == "METADATA" and any(part.endswith(".dist-info") for part in item.parts)]
        package_records = [item for item in records if item["role"] == "package_metadata:" + name]
        _require(len(metadata_paths) == 1 and len(package_records) == 2
                 and {Path(item["resolved_path"]) for item in package_records}
                 == {metadata_paths[0], metadata_paths[0].parent / "RECORD"},
                 "distribution_metadata_binding_missing", name)
        actual_packages[name] = dist.version
    configuration = [item for item in records if item["role"] == "python_configuration"]
    _require(len(configuration) == 1
             and Path(configuration[0]["resolved_path"]) == (Path(sys.prefix) / "pyvenv.cfg").resolve(strict=True)
             and sys.prefix != sys.base_prefix, "venv_configuration_binding_missing")
    for name in ("cmake", "ninja"):
        launcher = shutil.which(name)
        _require(launcher is not None and any(
            Path(item["resolved_path"]) == Path(launcher).resolve(strict=True)
            for item in records if item["role"] == "tool:" + name),
            "actual_tool_launcher_not_captured", name)
    boundary = _strings(section.get("trusted_platform_boundary"), "trusted_platform_boundary")
    return {"manifest_version": "b0-g3a-environment/v1", "python": observed,
            "interpreter_flags": {"isolated": sys.flags.isolated,
                                  "dont_write_bytecode": sys.flags.dont_write_bytecode,
                                  "no_user_site": sys.flags.no_user_site},
            "package_versions": actual_packages, "facts_input_sha256": _sha(raw),
            "files": records, "trusted_platform_boundary": boundary,
            "full_supply_chain_proven": False}, captured


def _one(records: list[dict[str, Any]], role: str) -> dict[str, Any]:
    matches = [item for item in records if item["role"] == role]
    _require(len(matches) == 1, "single_file_role_required", role)
    return matches[0]


def _catch_source_binding(cache: dict[str, str], records: list[dict[str, Any]]) -> dict[str, Any]:
    installed = cache.get("Catch2_DIR")
    _require(installed is None or installed == "Catch2_DIR-NOTFOUND", "installed_catch_branch_not_allowed")
    actual, overlay = cache.get("Catch2_SOURCE_DIR"), cache.get("FETCHCONTENT_SOURCE_DIR_CATCH2")
    _require(isinstance(actual, str) and bool(actual) and Path(actual).is_absolute()
             and isinstance(overlay, str) and bool(overlay) and Path(overlay).is_absolute(),
             "explicit_catch_source_overlay_required")
    root = Path(actual).resolve(strict=True)
    _require(root.is_dir() and root == Path(overlay).resolve(strict=True), "catch_source_overlay_mismatch")
    selected = [item for item in records if item["role"] == "catch_source"]
    _require(bool(selected) and all(Path(item["resolved_path"]).is_relative_to(root) for item in selected),
             "catch_capture_not_consumed_source")
    return {"source_root": str(root), "selection": "explicit_source_not_installed_package",
            "captured_files": len(selected),
            "pin_identity": "requires_retained_E2_commit_version_evidence_not_directory_existence"}


def _absolute_cache_path(cache: dict[str, str], key: str) -> Path:
    """Never turn an absent/relative CMake identity into the process cwd."""
    value = cache.get(key)
    _require(isinstance(value, str) and bool(value) and Path(value).is_absolute(),
             "cache_absolute_path_required", key)
    return Path(value).resolve(strict=True)


def _build(raw: bytes, policy: dict[str, Any], roots: dict[str, Path], source: dict[str, Any],
           environment: dict[str, Any], build_type: str, module: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    document = _object(_decode(raw, "build_facts"), "build_facts")
    _require(document.get("schema_version") == "b0-g3a-build-facts/v1", "build_facts_version")
    _require(document.get("source_commit") == source["source_commit"]
             and document.get("source_tree") == source["source_tree"]
             and document.get("build_type") == build_type, "build_source_or_type_mismatch")
    records, captured = _fact_files(document, policy["build"], roots, "build")
    cache_record = _one(records, "cmake_cache")
    _require(Path(cache_record["resolved_path"]) == (roots["$BUILD_DIR"] / "CMakeCache.txt").resolve(strict=True),
             "cmake_cache_path_mismatch")
    cache = {}
    for line in captured[cache_record["artifact_key"]].decode("utf-8").splitlines():
        if not line or line.startswith(("#", "//")) or "=" not in line or ":" not in line.split("=", 1)[0]:
            continue
        key_type, value = line.split("=", 1)
        key = key_type.split(":", 1)[0]
        _require(key not in cache, "duplicate_cmake_cache_key", key)
        cache[key] = value
    home_directory = _absolute_cache_path(cache, "CMAKE_HOME_DIRECTORY")
    _require(cache.get("CMAKE_BUILD_TYPE") == build_type
             and home_directory == roots["$SOURCE_ROOT"],
             "cmake_source_or_type_mismatch")
    for key, value in _object(policy["build"].get("required_cache_values"), "required_cache_values").items():
        _require(cache.get(key) == value, "cmake_policy_mismatch", key)
    for role, key in (("tool:cmake", "CMAKE_COMMAND"), ("tool:compiler", "CMAKE_CXX_COMPILER"),
                      ("tool:ninja", "CMAKE_MAKE_PROGRAM")):
        actual_tool = _absolute_cache_path(cache, key)
        matches = [item for item in environment["files"] if item["role"] == role
                   and actual_tool == Path(item["resolved_path"])]
        _require(len(matches) == 1,
                 "build_tool_binding_mismatch", role)
    catch = _catch_source_binding(cache, environment["files"])
    commands_record = _one(records, "compile_commands")
    ninja_record = _one(records, "build_ninja")
    rules_record = _one(records, "ninja_rules")
    for record, basename in ((commands_record, "compile_commands.json"), (ninja_record, "build.ninja")):
        _require(Path(record["resolved_path"]) == (roots["$BUILD_DIR"] / basename).resolve(strict=True),
                 "build_metadata_path_mismatch", basename)
    _require(Path(rules_record["resolved_path"])
             == (roots["$BUILD_DIR"] / "CMakeFiles/rules.ninja").resolve(strict=True),
             "ninja_rules_path_mismatch")
    commands = _decode(captured[commands_record["artifact_key"]], "compile_commands")
    _require(isinstance(commands, list) and bool(commands), "compile_commands_required")
    _require(any(item["role"] == "execution_log" for item in records), "build_execution_log_required")
    execution = _object(document.get("execution_evidence"), "execution_evidence")
    _require(execution.get("configure_exit_code") == 0 and type(execution.get("configure_exit_code")) is int
             and execution.get("build_exit_code") == 0 and type(execution.get("build_exit_code")) is int
             and execution.get("status") == "completed", "build_execution_not_completed")
    module_record = _one(records, "controller_module")
    resolved_module = module.resolve(strict=True)
    _require(resolved_module.is_relative_to(roots["$BUILD_DIR"])
             and Path(module_record["resolved_path"]) == resolved_module,
             "controller_module_path_mismatch")
    suffix = sysconfig.get_config_var("EXT_SUFFIX")
    _require(isinstance(suffix, str) and resolved_module.name == "b0_controller" + suffix,
             "controller_module_suffix_mismatch")
    _require(captured[module_record["artifact_key"]].startswith(b"\x7fELF"), "module_not_elf")
    return {"manifest_version": "b0-g3a-f0-candidate/v1", "source_commit": source["source_commit"],
            "source_tree": source["source_tree"], "build_type": build_type,
            "facts_input_sha256": _sha(raw), "files": records,
            "cache": cache, "execution_evidence": execution, "catch2_source_binding": catch,
            "module": {"path": str(resolved_module), "sha256": module_record["sha256"],
                       "bytes": module_record["bytes"], "abi": environment["python"]["soabi"]},
            "human_f0_accept": False,
            "limitations": ["declared finite build/log evidence, not malicious-builder attestation",
                            "no extension import or constructor performed"]}, captured


def _ci_context(event_raw: bytes | None, name: str | None, repository: str | None,
                github_sha: str | None, run_id: str | None, attempt: str | None,
                policy: dict[str, Any], commit: str) -> dict[str, Any] | None:
    if event_raw is None:
        _require(all(item is None for item in (name, repository, github_sha, run_id, attempt)),
                 "partial_ci_context")
        return None
    event = _object(_decode(event_raw, "github_event"), "github_event")
    ci = _object(policy["ci"], "ci_policy")
    _require(name in _strings(ci.get("allowed_events"), "ci.allowed_events")
             and name in {"pull_request", "push"}, "ci_event_not_allowed")
    _require(repository == ci.get("repository") and event.get("repository", {}).get("full_name") == repository,
             "ci_repository_mismatch")
    _require(isinstance(run_id, str) and run_id.isdigit() and int(run_id) > 0
             and isinstance(attempt, str) and attempt.isdigit() and int(attempt) > 0,
             "ci_run_identity_required")
    if name == "pull_request":
        expected_head = event.get("pull_request", {}).get("head", {}).get("sha")
        # GITHUB_SHA can be the synthetic merge SHA; it is retained, not selected.
        _digest(github_sha, "github_sha", git=True)
    else:
        expected_head = event.get("after")
        _require(_digest(github_sha, "github_sha", git=True) == commit, "ci_push_sha_mismatch")
    _require(_digest(expected_head, "event_head", git=True) == commit, "ci_event_head_mismatch")
    return {"event_sha256": _sha(event_raw), "event_name": name, "repository": repository,
            "event_head": commit, "github_sha": github_sha, "run_id": run_id,
            "run_attempt": attempt, "trust_boundary": "PA-reviewed exact policy/workflow/helper candidate; not malicious-workflow defense"}


def collect(*, policy_path: Path, expected_policy_sha256: str, source_root: Path,
            build_type: str, phase: str, environment_facts: Path, out_dir: Path,
            build_facts: Path | None = None, module: Path | None = None,
            build_dir: Path | None = None, git_executable: Path | None = None,
            source_facts: Path | None = None, expected_source_facts_sha256: str | None = None,
            github_event: Path | None = None, github_event_name: str | None = None,
            github_repository: str | None = None, github_sha: str | None = None,
            github_run_id: str | None = None, github_run_attempt: str | None = None) -> dict[str, Any]:
    """Collect external candidate facts, without importing or constructing DUT."""
    _require(phase in {"prebuild", "preflight"} and build_type in {"Debug", "Release"}, "collection_mode")
    root = source_root.resolve(strict=True)
    _require(root.is_dir() and not out_dir.exists(), "source_root_or_output_invalid")
    policy, policy_raw, relative_policy = _load_policy(policy_path, expected_policy_sha256, root)
    source_bytes = {relative: _read(_source_file(root, relative)) for relative in policy["source_paths"]}
    _require(source_bytes[relative_policy] == policy_raw, "policy_changed_during_collection")
    for relative, digest in policy["fixed_files"].items():
        _require(_sha(source_bytes[relative]) == _digest(digest, relative), "fixed_file_mismatch", relative)
    work_order = policy["work_order"]
    _require(_sha(source_bytes[work_order["path"]]) == _digest(work_order["sha256"], "work_order"),
             "work_order_digest_mismatch")
    for check in policy.get("canonical_lf_checks", []):
        relative = check["path"]
        canonical = source_bytes[relative].replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        _require(_sha(canonical) == _digest(check["sha256"], relative), "canonical_lf_mismatch", relative)
    for check in policy.get("approval_digest_checks", []):
        relative = check["document_path"]
        approval = _decode(source_bytes[check["approval_path"]], check["approval_path"])
        expected = _pointer(approval, check["approval_pointer"])
        if check["kind"] == "canonical_lf_sha256":
            data = source_bytes[relative].replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        elif check["kind"] == "canonical_json_sha256":
            data = _json_bytes(_decode(source_bytes[relative], relative))
        else:
            raise AuthorityError("unknown_approval_digest_kind")
        _require(_sha(data) == _digest(expected, relative), "approval_digest_mismatch", relative)
    source, git_raw = _source_identity(root, policy["source_paths"], source_bytes, git_executable,
                                       source_facts, expected_source_facts_sha256)
    # Tool/provider provenance is retained, but does not change the source-only
    # closure digest merely because Debug/Release used different Git binaries.
    source_provider = source.pop("provider_identity", {})
    event_raw = _read(github_event) if github_event is not None else None
    ci = _ci_context(event_raw, github_event_name, github_repository, github_sha,
                     github_run_id, github_run_attempt, policy, source["source_commit"])
    roots = {"$SOURCE_ROOT": root, "$PYTHON_PREFIX": Path(sys.prefix),
             "$PYTHON_BASE_PREFIX": Path(sys.base_prefix), "$PYTHON_EXECUTABLE": Path(sys.executable),
             "$PYTHON_INCLUDE": Path(sysconfig.get_path("include"))}
    if build_dir is not None:
        roots["$BUILD_DIR"] = build_dir.resolve(strict=True)
    environment_raw = _read(environment_facts)
    environment, external = _environment(environment_raw, policy, roots)
    parameters = expected_parameters(policy, source_bytes, root)
    config_approval = {"manifest_version": "b0-g3a-config-approval/v1", "files": [
        {"path": path, "raw_sha256": _sha(source_bytes[path]),
         "canonical_lf_sha256": _sha(source_bytes[path].replace(b"\r\n", b"\n").replace(b"\r", b"\n")),
         "parsed_document_sha256": _sha(_json_bytes(_decode(source_bytes[path], path)))}
        for path in policy["config_approval_paths"]]}
    observer = {"manifest_version": "b0-g3a-observer/v1", "files": [
        {"path": path, "sha256": _sha(source_bytes[path])} for path in policy["observer_paths"]],
        "evidence_files": {role: {"path": path, "sha256": _sha(source_bytes[path])}
                           for role, path in policy["evidence_files"].items()}}
    artifacts = dict(source_bytes)
    retained_external = dict(external)
    artifacts["external/environment-facts.json"] = environment_raw
    if git_raw is not None:
        artifacts["external/source-facts.json"] = git_raw
    if event_raw is not None:
        artifacts["external/github-event.json"] = event_raw
    manifests = {"source-closure.json": source, "config-approval.json": config_approval,
                 "expected-parameter-inputs.json": parameters, "observer.json": observer,
                 "environment.json": environment,
                 "source-provider.json": {"manifest_version": "b0-g3a-source-provider/v1",
                                          "source_commit": source["source_commit"],
                                          "provider": source_provider}}
    state: dict[str, Any] = {"status": "PREBUILD_ONLY", "human_f0_accept": False,
                             "policy_sha256": _sha(policy_raw), "source_commit": source["source_commit"],
                             "source_tree": source["source_tree"], "phase": phase, "ci": ci}
    if phase == "prebuild":
        _require(build_facts is None and module is None, "prebuild_cannot_claim_binary")
    else:
        _require(build_facts is not None and module is not None and build_dir is not None,
                 "postbuild_inputs_required")
        build_raw = _read(build_facts)
        f0, build_external = _build(build_raw, policy, roots, source, environment, build_type, module)
        retained_external.update(build_external)
        artifacts["external/build-facts.json"] = build_raw
        manifests["f0-candidate.json"] = f0
        state["status"] = "CI_POLICY_PREFLIGHT_PASS" if ci is not None else "CANDIDATE_FACTS_READY_FOR_PA_F0_REVIEW"
    for locator, value in manifests.items():
        _require(locator not in artifacts, "artifact_locator_collision", locator)
        artifacts[locator] = _json_bytes(value) + b"\n"
    basis = None
    if phase == "preflight":
        f0 = manifests["f0-candidate.json"]
        identity = {
            "work_order_sha256": work_order["sha256"].lower(), "source_commit": source["source_commit"],
            "source_tree": source["source_tree"], "source_closure_manifest_sha256": _sha(artifacts["source-closure.json"]),
            "config_approval_manifest_sha256": _sha(artifacts["config-approval.json"]),
            "profile_definition_sha256": _sha(source_bytes[policy["evidence_files"]["profile"]]),
            "parameter_inputs_manifest_sha256": _sha(artifacts["expected-parameter-inputs.json"]),
            "observer_manifest_sha256": _sha(artifacts["observer.json"]),
            "environment_manifest_sha256": _sha(artifacts["environment.json"]),
            "f0_manifest_sha256": _sha(artifacts["f0-candidate.json"]),
            "controller_module_path": f0["module"]["path"], "controller_module_sha256": f0["module"]["sha256"],
            "controller_module_abi": f0["module"]["abi"], "build_type": build_type,
            "seed": SEED, "classification": CLASSIFICATION,
        }
        _require(set(identity) == set(IDENTITY_KEYS), "internal_identity_key_set")
        basis = {"authority_version": AUTHORITY_VERSION, "identity": identity,
                 "parameter_inputs": parameters, "conventions": policy["conventions"],
                 "comparison_policy": policy["comparison_policy"], "collection": state,
                 "execution_plan": policy["execution_plan"],
                 "policy_sha256": _sha(policy_raw),
                 "artifact_sha256": {key: _sha(value) for key, value in artifacts.items()},
                 "input_artifact_base64": {key: base64.b64encode(value).decode("ascii")
                                           for key, value in artifacts.items()}}
    # Nothing is repaired or overwritten.  All verification precedes output creation.
    out_dir.mkdir(parents=False, exist_ok=False)
    snapshots = dict(artifacts)
    _require(not (set(snapshots) & set(retained_external)), "snapshot_locator_collision")
    snapshots.update(retained_external)
    snapshot_index = []
    for index, (locator, raw) in enumerate(sorted(snapshots.items())):
        destination = out_dir / "snapshots" / f"{index:06d}.bin"
        destination.parent.mkdir(exist_ok=True)
        with destination.open("xb") as handle:
            handle.write(raw)
        snapshot_index.append({"artifact_locator": locator, "path": destination.relative_to(out_dir).as_posix(),
                               "bytes": len(raw), "sha256": _sha(raw)})
    with (out_dir / "snapshot-index.json").open("xb") as handle:
        handle.write(_json_bytes({"manifest_version": "b0-g3a-snapshots/v1", "files": snapshot_index}) + b"\n")
    for locator, value in manifests.items():
        with (out_dir / locator).open("xb") as handle:
            handle.write(_json_bytes(value) + b"\n")
    if basis is not None:
        with (out_dir / "authority-basis.json").open("xb") as handle:
            handle.write(_json_bytes(basis) + b"\n")
    with (out_dir / "collection-state.json").open("xb") as handle:
        handle.write(_json_bytes(state) + b"\n")
    return state


def _admit_basis(raw: bytes, expected_sha256: str) -> dict[str, Any]:
    _require(_sha(raw) == _digest(expected_sha256, "authority_basis"), "authority_basis_digest_mismatch")
    basis = _object(_decode(raw, "authority_basis"), "authority_basis")
    _require(_json_bytes(basis) + b"\n" == raw, "basis_not_canonical_collector_bytes")
    _require(basis.get("authority_version") == AUTHORITY_VERSION
             and set(_object(basis.get("identity"), "identity")) == set(IDENTITY_KEYS),
             "authority_basis_shape")
    identity = basis["identity"]
    for key, value in identity.items():
        if key.endswith("sha256"):
            _digest(value, key)
    _digest(identity["source_commit"], "source_commit", git=True)
    _digest(identity["source_tree"], "source_tree", git=True)
    _require(identity["build_type"] in {"Debug", "Release"}
             and type(identity["seed"]) is int and identity["seed"] == SEED
             and identity["classification"] == CLASSIFICATION,
             "authority_identity_mode")
    _require("transport" not in basis and "authority_basis_sha256" not in basis,
             "basis_already_has_transport")
    expected = _object(basis.get("artifact_sha256"), "artifact_sha256")
    encoded = _object(basis.get("input_artifact_base64"), "input_artifact_base64")
    _require(set(expected) == set(encoded) and bool(expected), "artifact_registry_set")
    for locator, value in encoded.items():
        _require(isinstance(value, str), "base64_artifact_required", locator)
        try:
            data = base64.b64decode(value, validate=True)
        except (ValueError, TypeError) as exc:
            raise AuthorityError("invalid_base64_artifact", locator) from exc
        _require(_sha(data) == _digest(expected[locator], locator), "artifact_digest_mismatch", locator)
    return basis


def bind_transport(*, basis_path: Path, expected_basis_sha256: str, raw_path: Path,
                   locator: str, output: Path, parent_raw_sha256: str | None = None,
                   diagnostic_id: str | None = None) -> dict[str, Any]:
    """New external envelope; no raw identity is copied into expected identity."""
    basis = _admit_basis(_read(basis_path), expected_basis_sha256)
    _require(isinstance(locator, str) and bool(locator), "artifact_locator_required")
    _require(not output.exists() and output.resolve() not in {basis_path.resolve(), raw_path.resolve()},
             "transport_output_not_new")
    _require((parent_raw_sha256 is None) == (diagnostic_id is None), "partial_diagnostic_parent")
    if diagnostic_id is not None:
        _require(isinstance(diagnostic_id, str) and bool(diagnostic_id), "diagnostic_id_required")
    transport = {"sha256": _sha(_read(raw_path)), "artifact_locator": locator}
    if parent_raw_sha256 is not None:
        transport.update({"parent_raw_sha256": _digest(parent_raw_sha256, "parent_raw"),
                          "diagnostic_id": diagnostic_id})
    consumer = dict(basis)
    consumer["authority_basis_sha256"] = _digest(expected_basis_sha256, "basis")
    consumer["transport"] = transport
    with output.open("xb") as handle:
        handle.write(_json_bytes(consumer) + b"\n")
    return {"status": "TRANSPORT_BOUND_NOT_SEMANTICALLY_ACCEPTED", "transport": transport,
            "consumer_authority_sha256": _sha(_json_bytes(consumer) + b"\n")}


def load_consumer_authority(path: Path, expected_sha256: str) -> dict[str, Any]:
    """Decode JSON wire bytes for the independent checker; no DUT or IO repair."""
    raw = _read(path)
    _require(_sha(raw) == _digest(expected_sha256, "consumer_authority"), "consumer_authority_digest_mismatch")
    consumer = _object(_decode(raw, "consumer_authority"), "consumer_authority")
    parent_digest = _digest(consumer.get("authority_basis_sha256"), "basis")
    transport = _object(consumer.get("transport"), "transport")
    _digest(transport.get("sha256"), "transport")
    basis = {key: value for key, value in consumer.items() if key not in {"transport", "authority_basis_sha256"}}
    _admit_basis(_json_bytes(basis) + b"\n", parent_digest)
    consumer["input_artifact_bytes"] = {
        key: base64.b64decode(value, validate=True) for key, value in consumer["input_artifact_base64"].items()
    }
    return consumer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    collect_parser = commands.add_parser("collect")
    for name in ("policy", "source-root", "environment-facts", "out-dir"):
        collect_parser.add_argument("--" + name, type=Path, required=True)
    collect_parser.add_argument("--expected-policy-sha256", required=True)
    collect_parser.add_argument("--phase", choices=("prebuild", "preflight"), required=True)
    collect_parser.add_argument("--build-type", choices=("Debug", "Release"), required=True)
    provider = collect_parser.add_mutually_exclusive_group(required=True)
    provider.add_argument("--git-executable", type=Path)
    provider.add_argument("--source-facts", type=Path)
    collect_parser.add_argument("--expected-source-facts-sha256")
    for name in ("build-facts", "module", "build-dir", "github-event"):
        collect_parser.add_argument("--" + name, type=Path)
    for name in ("github-event-name", "github-repository", "github-sha", "github-run-id", "github-run-attempt"):
        collect_parser.add_argument("--" + name)
    transport_parser = commands.add_parser("bind-transport")
    for name in ("basis", "raw", "output"):
        transport_parser.add_argument("--" + name, type=Path, required=True)
    transport_parser.add_argument("--expected-basis-sha256", required=True)
    transport_parser.add_argument("--locator", required=True)
    transport_parser.add_argument("--parent-raw-sha256")
    transport_parser.add_argument("--diagnostic-id")
    arguments = vars(parser.parse_args(argv))
    command = arguments.pop("command")
    try:
        if command == "collect":
            arguments["policy_path"] = arguments.pop("policy")
            result = collect(**arguments)
        else:
            arguments["basis_path"] = arguments.pop("basis")
            arguments["raw_path"] = arguments.pop("raw")
            result = bind_transport(**arguments)
        print(_json_bytes(result).decode("ascii"))
        return 0
    except (AuthorityError, OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as exc:
        result = {"status": "REFUSED_OR_INCONCLUSIVE", "reason": getattr(exc, "reason", type(exc).__name__),
                  "detail": str(exc), "human_f0_accept": False}
        print(_json_bytes(result).decode("ascii"), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
