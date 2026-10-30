"""Synthetic metadata-only tests; source written but not executed in static phase.

No production loader, component, binding import, simulation or seed is needed.
These tests do not qualify the actual G3-A environment or real lifecycle.
"""

from __future__ import annotations

import base64
import builtins
import hashlib
import json
import os
import re
import subprocess
import sys
import zlib

import pytest

from binding_checks import g3a_authority as authority


def test_workflow_exact_startup_fixture_mode(tmp_path):
    """Invoke the exact workflow payload; do not maintain a second startup parser."""
    repository = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    workflow_path = os.path.join(repository, ".github", "workflows", "g3a.yml")
    with open(workflow_path, encoding="utf-8", newline="") as source:
        workflow = source.read()
    production_blob = re.findall(
        r'^  G3A_STARTUP_PRODUCTION_ZLIB_BASE64: "([A-Za-z0-9+/=]+)"$',
        workflow,
        flags=re.MULTILINE,
    )
    assert len(production_blob) == 1
    payload = zlib.decompress(base64.b64decode(production_blob[0], validate=True))
    assert len(payload) == 39456
    assert hashlib.sha256(payload).hexdigest() == (
        "0c15f02d71f4ca86372c6211cfdf8c1084beba25ae41ced97b65b53f132dd218"
    )
    fixture_blob = re.findall(
        r'^  G3A_STARTUP_FIXTURES_ZLIB_BASE64: "([A-Za-z0-9+/=]+)"$',
        workflow,
        flags=re.MULTILINE,
    )
    assert len(fixture_blob) == 1
    seal = tmp_path / "startup-fixture-seal.json"
    environment = dict(os.environ)
    environment["G3A_STARTUP_FIXTURES_ZLIB_BASE64"] = fixture_blob[0]
    completed = subprocess.run(
        [sys.executable, "-I", "-B", "-S", "-", "--fixture-mode", str(seal)],
        input=payload,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env=environment,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")
    result = json.loads(completed.stdout)
    assert result == {"fixture_atoms": 79, "passed": 7, "rejected": 72}
    sealed = json.loads(seal.read_bytes())
    assert sealed["schema_version"] == "b0-g3a-startup-fixture-seal/v1"
    assert sealed["fixture_atoms"] == 79
    assert sealed["materialization_failures"] == 0


def _startup_production_namespace():
    repository = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    workflow_path = os.path.join(repository, ".github", "workflows", "g3a.yml")
    with open(workflow_path, encoding="utf-8", newline="") as source:
        workflow = source.read()
    production_blob = re.findall(
        r'^  G3A_STARTUP_PRODUCTION_ZLIB_BASE64: "([A-Za-z0-9+/=]+)"$',
        workflow,
        flags=re.MULTILINE,
    )
    assert len(production_blob) == 1
    payload = zlib.decompress(base64.b64decode(production_blob[0], validate=True))
    assert len(payload) == 39456
    assert hashlib.sha256(payload).hexdigest() == (
        "0c15f02d71f4ca86372c6211cfdf8c1084beba25ae41ced97b65b53f132dd218"
    )
    namespace = {"__name__": "g3a_startup_scan_test", "__file__": "<workflow-production>"}
    exec(compile(payload, "<workflow-production>", "exec"), namespace)
    return namespace


class _ScanJournal:
    def __init__(self):
        self.records = []

    def add(self, value):
        self.records.append(value)


def test_startup_live_scan_accepts_53_ordinary_cache_entries(tmp_path):
    production = _startup_production_namespace()
    root = tmp_path / "stdlib"
    cache = root / "__pycache__"
    cache.mkdir(parents=True)
    for index in range(53):
        (cache / f"module_{index:04d}.cpython-311.pyc").write_bytes(b"")
    journal = _ScanJournal()

    production["scan_customization_root"](root, 0, journal)

    assert journal.records == [{
        "label": "customization.0.pycache",
        "status": "enumerated",
        "entries": 53,
        "entry_limit": 4096,
    }]


def test_startup_live_scan_rejects_late_sitecustomize_cache_entry(tmp_path):
    production = _startup_production_namespace()
    root = tmp_path / "stdlib"
    cache = root / "__pycache__"
    cache.mkdir(parents=True)
    for index in range(52):
        (cache / f"module_{index:04d}.cpython-311.pyc").write_bytes(b"")
    dangerous = cache / "sitecustomize.cpython-311.pyc"
    dangerous.write_bytes(b"synthetic-not-executed")
    journal = _ScanJournal()

    with pytest.raises(production["Reject"]) as caught:
        production["scan_customization_root"](root, 0, journal)

    assert caught.value.code == "CUSTOMIZATION_PRESENT_OR_REFUSED"
    assert caught.value.locator == "customization.entry"
    assert journal.records[-1] == {
        "label": "customization.0.sitecustomize.cpython-311.pyc",
        "status": "refused",
        "kind": "regular",
    }


def test_startup_live_scan_rejects_directory_cap_plus_one(tmp_path):
    production = _startup_production_namespace()
    root = tmp_path / "stdlib"
    cache = root / "__pycache__"
    cache.mkdir(parents=True)
    for index in range(4097):
        (cache / f"module_{index:04d}.cpython-311.pyc").write_bytes(b"")
    journal = _ScanJournal()

    with pytest.raises(production["Reject"]) as caught:
        production["scan_customization_root"](root, 0, journal)

    assert caught.value.code == "ACQ_LIMIT_EXCEEDED"
    assert caught.value.locator == "acquisition.entry_count"
    assert journal.records[-1] == {
        "label": "customization.0.pycache",
        "status": "count_exceeded",
        "entries": 4097,
    }


def test_startup_live_scan_rejects_unsafe_cache(tmp_path):
    production = _startup_production_namespace()
    root = tmp_path / "stdlib"
    root.mkdir()
    (root / "__pycache__").write_bytes(b"synthetic-nondirectory")
    journal = _ScanJournal()

    with pytest.raises(production["Reject"]) as caught:
        production["scan_customization_root"](root, 0, journal)

    assert caught.value.code == "CUSTOMIZATION_PRESENT_OR_REFUSED"
    assert caught.value.locator == "customization.entry"
    assert journal.records == [{
        "label": "customization.0.__pycache__",
        "status": "refused",
        "reason": "unsafe_cache",
    }]


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _parameter_fixture(tmp_path):
    raw = b'{"synthetic_metadata_fixture":true,"x":-0.0}\n'
    (tmp_path / "fixed.json").write_bytes(raw)
    bindings = []
    vectors = {
        "actuator_limits_Nm", "gravity_n_m_s2", "gyro_noise_std_rad_s", "gyro_bias_rad_s",
        "accelerometer_noise_std_m_s2", "accelerometer_bias_m_s2",
        "attitude_kp", "rate_kp", "rate_ki", "rate_kd", "integral_limit_Nm",
        "rate_limit_rad_s", "torque_limit_Nm", "kaw_limit_per_s", "kaw_lag_per_s",
    }
    for kind, fields in authority.PARAMETER_FIELDS.items():
        for field in sorted(fields):
            if field in {"config_path", "g0_config_path"}:
                value, encoding = "fixed.json", "source_relative_path"
            elif field == "imu_period_ticks":
                value, encoding = 2, "exact_json"
            elif field == "inertia_kg_m2":
                value, encoding = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]], "float64_tree"
            elif field in vectors:
                value, encoding = [0.0, 0.0, 1.0], "float64_tree"
            else:
                value, encoding = 1.0, "float64_tree"
            bindings.append({"component": kind, "field": field, "literal": value,
                             "encoding": encoding, "unit": "synthetic_unit",
                             "source_locator": "synthetic unit fixture, not project parameters"})
    return {"parameter_bindings": bindings, "fixed_files": {"fixed.json": _sha(raw)}}, {"fixed.json": raw}


def _basis_fixture():
    identity = {key: "1" * 64 for key in authority.IDENTITY_KEYS}
    identity.update({"source_commit": "2" * 40, "source_tree": "3" * 40,
                     "controller_module_path": "/synthetic/b0_controller.so",
                     "controller_module_abi": "synthetic-test-only",
                     "build_type": "Debug", "seed": authority.SEED,
                     "classification": authority.CLASSIFICATION})
    artifact = b'{"synthetic_fixture":true}\n'
    return {"authority_version": authority.AUTHORITY_VERSION, "identity": identity,
            "parameter_inputs": {"semantics": "synthetic_test_fixture"},
            "artifact_sha256": {"fixed.json": _sha(artifact)},
            "input_artifact_base64": {"fixed.json": base64.b64encode(artifact).decode("ascii")}}


def test_strict_json_refuses_duplicate_keys_and_nonfinite_constants():
    with pytest.raises(authority.AuthorityError, match="duplicate_json_key"):
        authority._decode(b'{"a":1,"a":2}', "fixture")
    with pytest.raises(authority.AuthorityError, match="nonfinite_json"):
        authority._decode(b'{"a":NaN}', "fixture")


def test_policy_expected_digest_is_checked_before_parsing(tmp_path):
    path = tmp_path / "policy.json"
    path.write_bytes(b"deliberately not JSON")
    with pytest.raises(authority.AuthorityError, match="policy_digest_mismatch"):
        authority._load_policy(path, "0" * 64, tmp_path.resolve())


def test_expected_full_parameter_mapping_preserves_types_and_runtime_root(tmp_path):
    policy, source = _parameter_fixture(tmp_path)
    result = authority.expected_parameters(policy, source, tmp_path.resolve())
    assert result["components"]["plant"] == result["components"]["actuator"]
    assert result["components"]["plant"] == result["components"]["imu"]
    assert result["components"]["plant"]["imu_period_ticks"] == 2
    assert type(result["components"]["plant"]["imu_period_ticks"]) is int
    assert result["components"]["plant"]["config_path"] == str((tmp_path / "fixed.json").resolve())
    assert set(result["components"]["estimator"]) == authority.ESTIMATOR_FIELDS
    assert set(result["components"]["controller"]) == authority.CONTROLLER_FIELDS


def test_expected_parameter_pointer_uses_source_bytes_and_signed_zero(tmp_path):
    policy, source = _parameter_fixture(tmp_path)
    item = next(item for item in policy["parameter_bindings"]
                if item["component"] == "estimator" and item["field"] == "sample_period_s")
    item.pop("literal")
    item.update({"source_path": "fixed.json", "json_pointer": "/x"})
    result = authority.expected_parameters(policy, source, tmp_path.resolve())
    assert result["components"]["estimator"]["sample_period_s"] == "-0x0.0p+0"
    unfixed_raw = b'{"synthetic_unfixed_fixture":true,"x":-0.0}\n'
    source["unfixed.json"] = unfixed_raw
    item["source_path"] = "unfixed.json"
    with pytest.raises(authority.AuthorityError, match="parameter_source_not_fixed"):
        authority.expected_parameters(policy, source, tmp_path.resolve())


def test_missing_or_duplicate_parameter_binding_is_not_ready(tmp_path):
    policy, source = _parameter_fixture(tmp_path)
    first = policy["parameter_bindings"].pop()
    with pytest.raises(authority.AuthorityError, match="incomplete_expected_parameters"):
        authority.expected_parameters(policy, source, tmp_path.resolve())
    policy["parameter_bindings"].extend([first, first])
    with pytest.raises(authority.AuthorityError, match="duplicate_parameter_field"):
        authority.expected_parameters(policy, source, tmp_path.resolve())


def test_wrong_parameter_shape_and_path_escape_are_refused(tmp_path):
    policy, source = _parameter_fixture(tmp_path)
    vector = next(item for item in policy["parameter_bindings"] if item["field"] == "attitude_kp")
    vector["literal"] = 1.0
    with pytest.raises(authority.AuthorityError, match="expected_parameter_shape"):
        authority.expected_parameters(policy, source, tmp_path.resolve())
    with pytest.raises(authority.AuthorityError, match="invalid_source_path"):
        authority._relative("../outside.json")


def test_external_source_fact_digest_and_blob_identity_are_both_needed(tmp_path):
    content = b"synthetic source\n"
    facts = {"schema_version": "b0-g3a-source-facts/v1", "source_commit": "1" * 40,
             "source_tree": "2" * 40,
             "files": {"file.py": hashlib.sha1(b"blob 17\0" + content).hexdigest()}}
    path = tmp_path / "source-facts.json"
    raw = _json(facts)
    path.write_bytes(raw)
    with pytest.raises(authority.AuthorityError, match="external_source_facts_digest_required"):
        authority._source_identity(tmp_path, ["file.py"], {"file.py": content}, None, path, None)
    with pytest.raises(authority.AuthorityError, match="source_facts_digest_mismatch"):
        authority._source_identity(tmp_path, ["file.py"], {"file.py": content}, None, path, "0" * 64)
    with pytest.raises(authority.AuthorityError, match="source_bytes_not_git_blob"):
        authority._source_identity(tmp_path, ["file.py"], {"file.py": content + b"changed"}, None, path, _sha(raw))


def test_role_boundary_duplicate_and_empty_coverage_refused(tmp_path):
    inside = tmp_path / "inside"
    inside.mkdir()
    path = inside / "a.bin"
    path.write_bytes(b"abc")
    record = {"role": "fixture", "path": str(path.resolve()), "bytes": 3, "sha256": _sha(b"abc")}
    section = {"required_file_roles": ["fixture"], "file_role_rules": {"fixture": {
        "allowed_roots": [str(inside.resolve())], "allowed_paths": [], "min_files": 1, "max_files": 2}}}
    observations, captured = authority._fact_files({"files": [record]}, section, {}, "environment")
    assert len(observations) == 1 and tuple(captured.values()) == (b"abc",)
    with pytest.raises(authority.AuthorityError, match="duplicate_fact_path_or_name"):
        authority._fact_files({"files": [record, record]}, section, {}, "environment")
    section["file_role_rules"]["fixture"]["allowed_roots"] = [str((tmp_path / "other").resolve())]
    with pytest.raises(authority.AuthorityError, match="fact_outside_role_boundary"):
        authority._fact_files({"files": [record]}, section, {}, "environment")
    with pytest.raises(authority.AuthorityError, match="fact_files_required"):
        authority._fact_files({"files": []}, section, {}, "environment")


def test_two_distinct_role_roots_can_have_same_basename(tmp_path):
    records = []
    roots = []
    for name in ("launcher", "binary"):
        directory = tmp_path / name
        directory.mkdir()
        path = directory / "cmake"
        path.write_bytes(name.encode("ascii"))
        roots.append(str(directory.resolve()))
        records.append({"role": "tool:cmake", "path": str(path.resolve()),
                        "bytes": len(name), "sha256": _sha(name.encode("ascii"))})
    section = {"required_file_roles": ["tool:cmake"], "file_role_rules": {"tool:cmake": {
        "allowed_roots": roots, "allowed_paths": [], "min_files": 2, "max_files": 2}}}
    observed, _ = authority._fact_files({"files": records}, section, {}, "environment")
    assert len({item["relative_name"] for item in observed}) == 2


def test_ci_pr_uses_event_head_not_synthetic_merge():
    head, merge = "1" * 40, "2" * 40
    event = _json({"repository": {"full_name": "owner/repo"}, "pull_request": {"head": {"sha": head}}})
    policy = {"ci": {"repository": "owner/repo", "allowed_events": ["pull_request", "push"]}}
    result = authority._ci_context(event, "pull_request", "owner/repo", merge, "1", "1", policy, head)
    assert result["event_head"] == head
    with pytest.raises(authority.AuthorityError, match="ci_event_head_mismatch"):
        authority._ci_context(event, "pull_request", "owner/repo", merge, "1", "1", policy, merge)


def test_catch_captured_root_must_equal_explicit_cmake_source(tmp_path):
    root = tmp_path / "catch-source"
    root.mkdir()
    source = root / "CMakeLists.txt"
    source.write_bytes(b"synthetic path-binding fixture, not Catch source")
    records = [{"role": "catch_source", "resolved_path": str(source.resolve())}]
    cache = {"Catch2_DIR": "Catch2_DIR-NOTFOUND", "Catch2_SOURCE_DIR": str(root.resolve()),
             "FETCHCONTENT_SOURCE_DIR_CATCH2": str(root.resolve())}
    result = authority._catch_source_binding(cache, records)
    assert result["source_root"] == str(root.resolve())
    cache["Catch2_DIR"] = str(root.resolve())
    with pytest.raises(authority.AuthorityError, match="installed_catch_branch_not_allowed"):
        authority._catch_source_binding(cache, records)
    cache["Catch2_DIR"] = "Catch2_DIR-NOTFOUND"
    cache["FETCHCONTENT_SOURCE_DIR_CATCH2"] = ""
    with pytest.raises(authority.AuthorityError, match="explicit_catch_source_overlay_required"):
        authority._catch_source_binding(cache, records)
    cache["FETCHCONTENT_SOURCE_DIR_CATCH2"] = str(root.resolve())
    records[0]["resolved_path"] = str((tmp_path / "outside.txt").resolve())
    with pytest.raises(authority.AuthorityError, match="catch_capture_not_consumed_source"):
        authority._catch_source_binding(cache, records)


@pytest.mark.parametrize("key", ["CMAKE_HOME_DIRECTORY", "CMAKE_COMMAND",
                                 "CMAKE_CXX_COMPILER", "CMAKE_MAKE_PROGRAM"])
@pytest.mark.parametrize("invalid_kind", ["missing", "relative", "empty"])
def test_all_four_cache_identity_paths_refuse_missing_relative_or_empty(tmp_path, monkeypatch, key, invalid_kind):
    # Reproduce the vulnerable cwd condition without a configure/build or DUT.
    monkeypatch.chdir(tmp_path)
    cache = {}
    if invalid_kind == "relative":
        cache[key] = "."
    elif invalid_kind == "empty":
        cache[key] = ""
    with pytest.raises(authority.AuthorityError, match="cache_absolute_path_required") as caught:
        authority._absolute_cache_path(cache, key)
    assert caught.value.detail == key


def test_empty_execution_plan_and_boolean_auxiliary_counts_are_refused():
    plan = {"plan_version": "b0-g3a-execution-plan/v1", "lifecycle_callsites": {}, "auxiliary_counts": {}}
    with pytest.raises(authority.AuthorityError, match="execution_plan_empty"):
        authority._execution_plan(plan)
    plan["lifecycle_callsites"] = {"fixture": {"owner": "observer", "method": "capture_snapshot", "parent_site": None}}
    plan["auxiliary_counts"] = {profile: {"fixture": 0} for profile in ("S", "L1", "L2", "O1", "O2", "E", "T1", "T2")}
    plan["auxiliary_counts"]["S"]["fixture"] = True
    with pytest.raises(authority.AuthorityError, match="auxiliary_counter_invalid"):
        authority._execution_plan(plan)


def test_collect_prebuild_needs_no_raw_and_cannot_emit_basis(tmp_path, monkeypatch):
    """Control-flow unit fixture, deliberately not actual environment evidence."""
    source_file = tmp_path / "source.txt"
    source_file.write_bytes(b"synthetic source")
    env_path = tmp_path / "environment-facts.json"
    env_path.write_bytes(b"{}")
    policy_raw = b"synthetic mocked policy"
    policy = {"source_paths": ["source.txt"], "fixed_files": {},
              "work_order": {"path": "source.txt", "sha256": _sha(b"synthetic source")},
              "config_approval_paths": [], "observer_paths": [], "evidence_files": {}}
    monkeypatch.setattr(authority, "_load_policy", lambda *args: (policy, policy_raw, "source.txt"))
    monkeypatch.setattr(authority, "_source_identity", lambda *args: ({"source_commit": "1" * 40,
                                                                     "source_tree": "2" * 40}, None))
    monkeypatch.setattr(authority, "_environment", lambda *args: ({"synthetic": True}, {}))
    monkeypatch.setattr(authority, "expected_parameters", lambda *args: {"synthetic": True})
    original_import = builtins.__import__

    def reject_dut_import(name, *args, **kwargs):
        assert name.split(".")[0] not in {"numpy", "b0_controller", "runner", "plant", "imu", "estimator"}
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", reject_dut_import)
    # Match the mocked policy byte identity check, without supplying any raw.
    source_file.write_bytes(policy_raw)
    policy["work_order"]["sha256"] = _sha(policy_raw)
    output = tmp_path / "new-prebuild"
    state = authority.collect(policy_path=source_file, expected_policy_sha256=_sha(policy_raw),
                              source_root=tmp_path, build_type="Debug", phase="prebuild",
                              environment_facts=env_path, out_dir=output)
    assert state["status"] == "PREBUILD_ONLY" and state["human_f0_accept"] is False
    assert not (output / "authority-basis.json").exists()
    assert (output / "snapshot-index.json").is_file()


def test_transport_does_not_copy_raw_identity_or_modify_basis(tmp_path):
    basis = _basis_fixture()
    basis_path = tmp_path / "basis.json"
    basis_raw = _json(basis) + b"\n"
    basis_path.write_bytes(basis_raw)
    raw_path = tmp_path / "raw.json"
    raw_bytes = b'{"identity":{"source_commit":"untrusted raw claim"}}\n'
    raw_path.write_bytes(raw_bytes)
    output = tmp_path / "consumer.json"
    result = authority.bind_transport(basis_path=basis_path, expected_basis_sha256=_sha(basis_raw),
                                      raw_path=raw_path, locator="synthetic/artifact", output=output)
    consumer = authority.load_consumer_authority(output, result["consumer_authority_sha256"])
    assert consumer["identity"] == basis["identity"]
    assert consumer["transport"]["sha256"] == _sha(raw_bytes)
    assert consumer["input_artifact_bytes"]["fixed.json"] == b'{"synthetic_fixture":true}\n'
    assert basis_path.read_bytes() == basis_raw and raw_path.read_bytes() == raw_bytes
    with pytest.raises(authority.AuthorityError, match="transport_output_not_new"):
        authority.bind_transport(basis_path=basis_path, expected_basis_sha256=_sha(basis_raw),
                                 raw_path=raw_path, locator="same", output=output)


def test_transport_rejects_corrupt_registry_even_when_outer_digest_is_supplied(tmp_path):
    basis = _basis_fixture()
    basis["input_artifact_base64"]["fixed.json"] = base64.b64encode(b"wrong bytes").decode("ascii")
    raw = _json(basis) + b"\n"
    with pytest.raises(authority.AuthorityError, match="artifact_digest_mismatch"):
        authority._admit_basis(raw, _sha(raw))
