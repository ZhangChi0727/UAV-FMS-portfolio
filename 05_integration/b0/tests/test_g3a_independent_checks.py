"""Synthetic unit fixtures only; statically authored, not executed here.

These cases exercise offline admission, selectors and comparison precedence.
They are not real raw traces, a complete valid record fixture, a second plant /
controller model, or evidence that the real thirteen diagnostic records pass.
The real legal-control / twelve owning-rejection campaign must use sealed raw.
No DUT, production loader, scheduler, runner or component helper is imported.
"""

from __future__ import annotations

import copy
import hashlib
import json

import pytest

from binding_checks import g3a_independent_checks as checks


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def test_synthetic_unit_fixture_duplicate_json_key_has_own_reason():
    with pytest.raises(checks._Reject) as failure:
        checks._decode(b'{"synthetic_unit_fixture":true,"x":1,"x":2}', "$")
    assert failure.value.reason == "json_duplicate_key"


def test_synthetic_unit_fixture_missing_required_field_has_precise_path():
    schema = {"type": "object", "required": ["timestamp_s"],
              "properties": {"timestamp_s": {"type": "string"}}}
    with pytest.raises(checks._Reject) as failure:
        checks._shape({}, schema, schema, "$/synthetic_unit_fixture/imu")
    assert failure.value.reason == "missing_required_field"
    assert failure.value.path == "$/synthetic_unit_fixture/imu/timestamp_s"


@pytest.mark.parametrize(("token", "reason"), [
    ("nan", "nonfinite_nan"), ("inf", "nonfinite_inf"),
    ("-inf", "nonfinite_inf"), ("0x0p+0", "float_encoding_invalid"),
])
def test_synthetic_unit_fixture_finite_preflight_reason(token, reason):
    with pytest.raises(checks._Reject) as failure:
        checks._finite([("$/synthetic_unit_fixture/gyro_rad_s/0", token)])
    assert failure.value.reason == reason


def test_synthetic_unit_fixture_canonical_signed_zero_remains_distinct():
    checks._finite([("positive", "0x0.0p+0"), ("negative", "-0x0.0p+0")])
    assert not checks._equal("0x0.0p+0", "-0x0.0p+0")


@pytest.mark.parametrize("mode", ["twin", "dr"])
def test_synthetic_unit_fixture_quaternion_absolute_rule_precedes_copy_and_twin(mode):
    policy = checks._comparison_policy(
        ("synthetic_unit_fixture", "initial_inputs", "q_nb", 0), None, mode)
    assert policy == (1e-12, 0.0, "1", "quaternion_component_absolute_1e-12")


def test_synthetic_unit_fixture_q_comparison_has_no_relative_allowance():
    # Deliberately not a valid physical quaternion: this isolates the field
    # comparison policy and cannot stand in for a real-record/schema pass.
    reference = [1024.0.hex()]
    changed = [(1024.0 + 1e-10).hex()]
    with pytest.raises(checks._Reject) as failure:
        checks._compare_values(changed, reference,
                               ("synthetic_unit_fixture", "q_nb"), {}, mode="dr")
    assert failure.value.reason == "float_comparison_failed"
    assert failure.value.expected["policy"] == "quaternion_component_absolute_1e-12"


def test_synthetic_unit_fixture_unknown_float_path_is_inconclusive():
    with pytest.raises(checks._Reject) as failure:
        checks._compare_values("0x0.0p+0", "0x0.0p+0",
                               ("synthetic_unit_fixture", "unknown_signal"), {}, mode="dr")
    assert failure.value.reason == "comparison_policy_missing"
    assert failure.value.incomplete


def test_synthetic_unit_fixture_non_q_reset_argument_remains_exact():
    left = {"kind": "reset", "actor": "plant", "initial_state": {
        "omega_b_rad_s": [(1.0 + 1e-13).hex(), "0x0.0p+0", "0x0.0p+0"]}}
    right = copy.deepcopy(left)
    right["initial_state"]["omega_b_rad_s"][0] = 1.0.hex()
    with pytest.raises(checks._Reject) as failure:
        checks._compare_values(left, right, ("synthetic_unit_fixture", "arguments"), {}, mode="dr")
    assert failure.value.reason == "float_comparison_failed"
    assert failure.value.expected["policy"] == "canonical_exact"


def test_synthetic_unit_fixture_protected_copy_is_exact_even_for_q():
    # Only _preserved's six protected sections are supplied.  This is not a
    # schema-complete observation or proof of an actual observer capture.
    before = {"capture_id": "synthetic_unit_fixture/before", "session": {},
              "plant": {"q_nb": [1.0.hex(), "0x0.0p+0", "0x0.0p+0", "0x0.0p+0"]},
              "actuator": {}, "imu": {}, "estimator": {}, "controller": {}}
    after = copy.deepcopy(before)
    after["capture_id"] = "synthetic_unit_fixture/after"
    after["plant"]["q_nb"][1] = (1e-13).hex()
    context = {"path": "$/synthetic_unit_fixture", "snapshots": {"before": before, "after": after}}
    with pytest.raises(checks._Reject) as failure:
        checks._preserved(context, "before", "after")
    assert failure.value.reason == "snapshot_changed"


def test_synthetic_unit_fixture_missing_authority_never_passes():
    result = checks.check_record_set(b'{"synthetic_unit_fixture":true}', {})
    assert result["status"] == "execution_error_inconclusive"
    assert result["reason"] == "authority_invalid"
    assert result["profiles"] == result["groups"] == {}


@pytest.mark.parametrize(("field", "reason"), [
    ("source_commit", "source_mismatch"),
    ("controller_module_sha256", "module_identity_mismatch"),
])
def test_synthetic_unit_fixture_raw_cannot_replace_external_identity(monkeypatch, field, reason):
    # Isolate the identity selector after authority admission, without forging
    # a complete authority / valid raw.  _authority is explicitly stubbed; the
    # actual registry, source closure and transport campaign remain untested.
    expected = {name: "approved_synthetic_unit_fixture" for name in checks._IDENTITY_KEYS}
    altered = dict(expected)
    altered[field] = "raw_self_claim_must_not_become_authority"
    raw_bytes = _json({"identity": altered})
    schema = {"type": "object", "required": ["identity"], "properties": {"identity": {"type": "object"}}}
    monkeypatch.setattr(checks, "_authority", lambda authority: (schema, {}, {}))
    authority = {"identity": expected, "transport": {"sha256": hashlib.sha256(raw_bytes).hexdigest()}}
    with pytest.raises(checks._Reject) as failure:
        checks._preflight(raw_bytes, authority)
    assert failure.value.reason == reason
    assert authority["identity"] == expected


def test_synthetic_unit_fixture_reset_only_and_correction_selector():
    # Integer signature expectations only; no schedule/component is executed.
    reset = checks._expected_operations("T1", 1000, True, 0)
    assert [(item[0], item[1], item[2]) for item in reset] == [
        ("controller", "reset", 0), ("estimator", "reset", 0)]
    correction = checks._expected_operations("L1", 400, False, 400)
    controller = [item for item in correction if item[0] == "controller"]
    assert controller == [
        ("controller", "step", 5, "injected_invalid", False, "invalid_dt"),
        ("controller", "step", 5, "same_tick_correction", True, "accepted")]


def test_synthetic_unit_fixture_o6_has_no_hidden_correction_or_publication():
    signatures = checks._expected_operations("O1", 6, False, 6)
    assert signatures[-1] == ("controller", "step", 5, "injected_invalid", False, "unexpected_tick")
    assert sum(item[0] == "controller" for item in signatures) == 1
    assert not any(item[1] == "publish" for item in signatures)


def test_synthetic_unit_fixture_auxiliary_names_cannot_grow_from_actual():
    actual = checks.Counter({"lifecycle:declared:enter": 1, "lifecycle:undeclared:enter": 1})
    with pytest.raises(checks._Reject) as failure:
        checks._closed_auxiliary_counts(actual, {"lifecycle:declared:enter": 1}, "synthetic_unit_fixture/aux")
    assert failure.value.reason == "counter_set_mismatch"
    assert failure.value.incomplete
    assert failure.value.actual["undeclared_actual_auxiliary"] == {"lifecycle:undeclared:enter": 1}


def test_synthetic_unit_fixture_auxiliary_explicit_zero_is_retained():
    actual = checks.Counter({"lifecycle:declared:enter": 1})
    planned = {"lifecycle:declared:enter": 1, "lifecycle:declared:exception": 0}
    result = checks._closed_auxiliary_counts(actual, planned, "synthetic_unit_fixture/aux")
    assert result == planned
    assert "lifecycle:declared:exception" in result


def test_synthetic_unit_fixture_auxiliary_missing_positive_observation_rejects():
    with pytest.raises(checks._Reject) as failure:
        checks._closed_auxiliary_counts(checks.Counter(), {"guard:declared:accepted": 1},
                                        "synthetic_unit_fixture/aux")
    assert failure.value.reason == "count_mismatch"


def _synthetic_pcg64_value_map():
    # A typed value-map fixture, not a generated seed state or RNG result.
    return {"bit_generator": "PCG64", "state": {"state": 0, "inc": 1}, "has_uint32": 0, "uinteger": 0}


@pytest.mark.parametrize("alteration", [
    "empty", "missing_cache", "extra_key", "wrong_generator", "state_bool",
    "state_negative", "state_overflow", "inc_even", "inc_zero", "inc_overflow",
    "cache_flag_bool", "cache_flag_two", "cache_negative", "cache_overflow",
])
def test_synthetic_unit_fixture_pcg64_rejects_wrong_key_type_and_domain(alteration):
    value = _synthetic_pcg64_value_map()
    if alteration == "empty":
        value = {}
    elif alteration == "missing_cache":
        del value["uinteger"]
    elif alteration == "extra_key":
        value["unexpected"] = 0
    elif alteration == "wrong_generator":
        value["bit_generator"] = "PCG64DXSM"
    elif alteration == "state_bool":
        value["state"]["state"] = False
    elif alteration == "state_negative":
        value["state"]["state"] = -1
    elif alteration == "state_overflow":
        value["state"]["state"] = 1 << 128
    elif alteration == "inc_even":
        value["state"]["inc"] = 2
    elif alteration == "inc_zero":
        value["state"]["inc"] = 0
    elif alteration == "inc_overflow":
        value["state"]["inc"] = (1 << 128) + 1
    elif alteration == "cache_flag_bool":
        value["has_uint32"] = False
    elif alteration == "cache_flag_two":
        value["has_uint32"] = 2
    elif alteration == "cache_negative":
        value["uinteger"] = -1
    else:
        value["uinteger"] = 1 << 32
    with pytest.raises(checks._Reject) as failure:
        checks._pcg64_state(value, "synthetic_unit_fixture/rng_state", allow_uninitialized=True)
    assert failure.value.reason == "snapshot_incomplete"
    assert failure.value.incomplete


def test_synthetic_unit_fixture_pcg64_none_is_only_uninitialized():
    checks._pcg64_state(None, "synthetic_unit_fixture/uninitialized", allow_uninitialized=True)
    checks._pcg64_state(_synthetic_pcg64_value_map(), "synthetic_unit_fixture/value_map", allow_uninitialized=False)
    with pytest.raises(checks._Reject) as failure:
        checks._pcg64_state(None, "synthetic_unit_fixture/reset_state", allow_uninitialized=False)
    assert failure.value.reason == "snapshot_incomplete"


def test_synthetic_unit_fixture_recomputed_estimate_q_is_not_copied_q():
    expected = {"epoch_id": 1, "payload": {
        "q_nb": [1.0.hex(), "0x0.0p+0", "0x0.0p+0", "0x0.0p+0"],
        "omega_b_rad_s": ["0x0.0p+0"] * 3, "timestamp_s": 2.505.hex(), "valid": True}}
    actual = copy.deepcopy(expected)
    actual["payload"]["q_nb"][1] = (1e-13).hex()
    checks._replay_input_payload(actual, expected, "controller", "estimate",
                                  ("synthetic_unit_fixture", "recomputed_estimate"), {})
    # The identical q perturbation is still forbidden for a frozen copied
    # attitude-command payload; no global quaternion tolerance repairs copies.
    with pytest.raises(checks._Reject) as failure:
        checks._replay_input_payload(actual, expected, "controller", "attitude_command",
                                      ("synthetic_unit_fixture", "fixed_copied_command"), {})
    assert failure.value.reason == "replay_mismatch"


def test_synthetic_unit_fixture_recomputed_estimate_non_q_keeps_twin_policy():
    expected = {"epoch_id": 1, "payload": {"omega_b_rad_s": ["0x0.0p+0"] * 3}}
    actual = copy.deepcopy(expected)
    actual["payload"]["omega_b_rad_s"][0] = (1e-13).hex()
    with pytest.raises(checks._Reject) as failure:
        checks._replay_input_payload(actual, expected, "controller", "estimate",
                                      ("synthetic_unit_fixture", "recomputed_estimate"), {})
    assert failure.value.reason == "float_comparison_failed"
    assert failure.value.expected["policy"] == "same_build_exact_non_quaternion"


def test_synthetic_unit_fixture_latest_old_role_uses_real_producer_and_cap():
    def record(identifier, tick, producer="actuator", epoch=0):
        return {"wire_id": identifier, "role": "feedback", "kind": "feedback", "producer": producer,
                "epoch_id": epoch, "global_tick": tick}

    old = record("synthetic_unit_fixture/996", 996)
    latest = record("synthetic_unit_fixture/998", 998)
    after_cap = record("synthetic_unit_fixture/999", 999)
    wrong_producer = record("synthetic_unit_fixture/truth", 998, "evaluator_truth")
    new_epoch = record("synthetic_unit_fixture/new", 1002, epoch=1)
    selected = checks._latest_old_role_value(
        [after_cap, old, wrong_producer, latest, new_epoch], "feedback", "synthetic_unit_fixture")
    assert selected is latest
    assert selected is not old


@pytest.mark.parametrize("profile_id", ["T1", "T2"])
@pytest.mark.parametrize(("completed_tick", "next_tick"), [(1000, 1002), (1002, 1004), (1004, 1005)])
def test_synthetic_unit_fixture_sparse_t_next_is_actual_replay_point(profile_id, completed_tick, next_tick):
    # Pure integer definition, not a replay invocation or proof of actual raw.
    assert checks._expected_session_next_tick(profile_id, completed_tick) == next_tick


@pytest.mark.parametrize(("profile_id", "completed_tick", "next_tick"), [
    ("S", 0, 1), ("L1", 1000, 1001), ("L2", 1000, 1001),
    ("O1", 7, 8), ("O2", 7, 8), ("E", 0, 1),
])
def test_synthetic_unit_fixture_normal_session_next_stays_base_tick(profile_id, completed_tick, next_tick):
    assert checks._expected_session_next_tick(profile_id, completed_tick) == next_tick


def _synthetic_default_loader_fixture():
    """A finite lifecycle fragment, not a schema-complete or real raw record."""
    values = {
        "sample_period_s": 1.0.hex(), "gravity_m_s2": 1.0.hex(),
        "unit_norm_tolerance": 1.0.hex(), "correction_gain_per_s": 1.0.hex(),
        "accelerometer_gate_deviation_m_s2": 1.0.hex(),
        "maximum_correction_step_rad": 1.0.hex(), "timestamp_tolerance_s": 1.0.hex(),
        "config_path": "/synthetic/estimator.json", "g0_config_path": "/synthetic/g0.json",
    }
    value_digest = hashlib.sha256(_json(values)).hexdigest()
    parameter_ids = {name: "synthetic/parameter/" + name
                     for name in ("fields", "constructed", "loader", "estimator")}
    parameter_records = [
        {"parameter_object_id": identifier, "kind": "estimator",
         "capture_kind": "constructor_fields" if name == "fields" else "object_values",
         "values": copy.deepcopy(values), "values_sha256": value_digest}
        for name, identifier in parameter_ids.items()
    ]
    estimator_source = b"synthetic source binding only; never imported\n"
    config_document = {"synthetic_metadata_fixture": True}
    config_bytes = _json(config_document) + b"\n"
    source_digest = hashlib.sha256(estimator_source).hexdigest()
    config_digest = hashlib.sha256(config_bytes).hexdigest()
    document_digest = hashlib.sha256(_json(config_document)).hexdigest()
    source_locator = "02_estimation/b0/estimator.py"
    config_locator = "05_integration/b0/configs/b0_g0_contract.v2.json"
    sites = {
        "estimator.AttitudeEstimator": {"owner": "estimator", "method": "constructor", "parent_site": None},
        "estimator.load_estimator_parameters": {
            "owner": "estimator_loader", "method": "load_parameters",
            "parent_site": ["estimator.AttitudeEstimator"]},
        "estimator.EstimatorParameters": {
            "owner": "estimator_parameters", "method": "constructor",
            "parent_site": ["estimator.load_estimator_parameters"]},
        "validate_config.load_config": {
            "owner": "g0_validator", "method": "load_config",
            "parent_site": ["estimator.load_estimator_parameters"]},
        "validate_config.validate_config": {
            "owner": "g0_validator", "method": "validate_config",
            "parent_site": ["estimator.load_estimator_parameters"]},
    }
    g1_values = {"config_path": "/synthetic/g0.json"}
    authority = {
        "parameter_inputs": {
            "manifest_version": "b0-g3a-expected-parameter-inputs/v1",
            "semantics": "approved_expected_inputs_not_runtime_observations",
            "components": {"plant": g1_values, "actuator": copy.deepcopy(g1_values),
                           "imu": copy.deepcopy(g1_values), "estimator": copy.deepcopy(values),
                           "controller": {}}},
        "input_artifact_bytes": {source_locator: estimator_source, config_locator: config_bytes},
        "execution_plan": {"lifecycle_callsites": sites},
        "identity": {"controller_module_sha256": "a" * 64},
    }

    def entered(name, site, parent, actor, arguments):
        return {"observation_index": -1, "event": "enter", "call_id": "synthetic/" + name,
                "parent_call_id": None if parent is None else "synthetic/" + parent,
                "profile_id": "S", "operation_id": None, "owner": sites[site]["owner"],
                "method": sites[site]["method"], "callsite": site, "actor_id": actor,
                "core_use": None, "arguments": arguments, "result": None, "exception": None}

    def returned(entry, parameter_ref=None, *, config=False):
        event = copy.deepcopy(entry)
        event.update(event="return", arguments=None,
                     result={"actor_id": entry["actor_id"], "parameter_object_ref": parameter_ref,
                             "snapshot_ref": None, "capture_id": None,
                             "resolved_config_path": "/synthetic/g0.json" if config else None,
                             "source_bytes_sha256": config_digest if config else None,
                             "document_sha256": document_digest if config else None})
        return event

    estimator = entered("estimator", "estimator.AttitudeEstimator", None, "synthetic/estimator-actor",
                        {"kind": "constructor", "mode": "default_loader",
                         "parameter_object_ref": None, "module_sha256": source_digest})
    loader = entered("loader", "estimator.load_estimator_parameters", "estimator", "synthetic/loader-actor",
                     {"kind": "loader", "supplied_args": []})
    load = entered("load-config", "validate_config.load_config", "loader", "synthetic/validator-actor",
                   {"kind": "config", "actual_argument_kind": "path",
                    "path_argument": "/synthetic/g0.json", "source_artifact_ref": config_locator,
                    "source_bytes_sha256": config_digest, "document_sha256": None})
    validate = entered("validate-config", "validate_config.validate_config", "loader", "synthetic/validator-actor",
                       {"kind": "config", "actual_argument_kind": "document", "path_argument": None,
                        "source_artifact_ref": config_locator, "source_bytes_sha256": config_digest,
                        "document_sha256": document_digest})
    parameters = entered("parameters", "estimator.EstimatorParameters", "loader", "synthetic/parameters-actor",
                         {"kind": "constructor", "mode": "parameter_fields", "module_sha256": source_digest,
                          "parameter_object_ref": parameter_ids["fields"]})
    events = [estimator, loader, load, returned(load, config=True), validate,
              returned(validate, config=True), parameters, returned(parameters, parameter_ids["constructed"]),
              returned(loader, parameter_ids["loader"]), returned(estimator, parameter_ids["estimator"])]
    for index, event in enumerate(events):
        event["observation_index"] = index
    raw = {"parameter_objects": parameter_records, "lifecycle_observations": events}
    contexts = {pid: {"path": "$/synthetic/" + pid, "snapshots": {}, "ops": {}} for pid in checks._ORDER}
    return raw, authority, contexts


def _synthetic_default_loader_inputs(raw, authority):
    # Use the real approved-value registry, not a stub that bypasses the binding.
    parameters = checks._parameter_objects(raw, authority)
    calls = {event["call_id"]: event for event in raw["lifecycle_observations"] if event["event"] == "enter"}
    terminals = {event["call_id"]: event for event in raw["lifecycle_observations"] if event["event"] == "return"}
    return calls["synthetic/estimator"], terminals["synthetic/estimator"]["result"], calls, terminals, parameters


@pytest.mark.parametrize("same_capture", [False, True])
def test_synthetic_default_loader_parameter_capture_id_is_not_object_identity(same_capture):
    raw, authority, _ = _synthetic_default_loader_fixture()
    if same_capture:
        raw["lifecycle_observations"][-1]["result"]["parameter_object_ref"] = "synthetic/parameter/loader"
    arguments = _synthetic_default_loader_inputs(raw, authority)
    # This checks the value-binding rule only; sharing a reference does not
    # establish an actual repeated capture or Python object-identity observation.
    checks._default_loader_parameter_binding(*arguments, "$/synthetic/constructor")


def test_synthetic_distinct_default_loader_captures_reach_existing_lifecycle_count_gate():
    raw, authority, contexts = _synthetic_default_loader_fixture()
    parameters = checks._parameter_objects(raw, authority)
    # The fragment has a valid local binding, but deliberately lacks the other
    # seven profiles/components. The unchanged global count gate must still fail.
    with pytest.raises(checks._Reject) as failure:
        checks._lifecycle(raw, authority, contexts, parameters)
    assert failure.value.reason == "lifecycle_observation_missing"
    assert failure.value.path == "$/lifecycle/plant:constructor"
    assert failure.value.incomplete


@pytest.mark.parametrize(("alteration", "suffix"), [
    ("missing_loader", ""), ("duplicate_loader", ""), ("wrong_parent", ""),
    ("wrong_profile", "/loader"), ("wrong_operation", "/loader"),
    ("wrong_callsite", "/loader"), ("wrong_owner", "/loader"),
    ("missing_terminal", "/loader_return"), ("exception_terminal", "/loader_return"),
    ("terminal_actor", "/loader_return"),
    ("loader_missing_ref", "/loader_parameter_object_ref"),
    ("loader_unknown_ref", "/loader_parameter_object_ref"),
    ("constructor_missing_ref", "/constructor_parameter_object_ref"),
    ("constructor_unknown_ref", "/constructor_parameter_object_ref"),
    ("loader_wrong_kind", "/loader_capture"), ("constructor_wrong_kind", "/constructor_capture"),
    ("loader_wrong_capture_kind", "/loader_capture"), ("constructor_wrong_capture_kind", "/constructor_capture"),
    ("loader_bad_digest", "/loader_capture"), ("constructor_bad_digest", "/constructor_capture"),
    ("changed_values", "/values"),
])
def test_synthetic_default_loader_binding_rejects_single_fault(alteration, suffix):
    raw, authority, _ = _synthetic_default_loader_fixture()
    enter, result, calls, terminals, parameters = _synthetic_default_loader_inputs(raw, authority)
    loader = calls["synthetic/loader"]
    loader_return = terminals["synthetic/loader"]
    if alteration == "missing_loader":
        del calls["synthetic/loader"]
    elif alteration == "duplicate_loader":
        duplicate = copy.deepcopy(loader)
        duplicate["call_id"] = "synthetic/duplicate-loader"
        calls[duplicate["call_id"]] = duplicate
    elif alteration == "wrong_parent":
        loader["parent_call_id"] = "synthetic/other-constructor"
    elif alteration == "wrong_profile":
        loader["profile_id"] = "L1"
    elif alteration == "wrong_operation":
        loader["operation_id"] = "synthetic/other-operation"
    elif alteration == "wrong_callsite":
        loader["callsite"] = "synthetic/other-loader"
    elif alteration == "wrong_owner":
        loader["owner"] = "controller_loader"
    elif alteration == "missing_terminal":
        del terminals["synthetic/loader"]
    elif alteration == "exception_terminal":
        loader_return["event"] = "exception"
    elif alteration == "terminal_actor":
        loader_return["actor_id"] = "synthetic/other-actor"
    elif alteration in {"loader_missing_ref", "loader_unknown_ref"}:
        loader_return["result"]["parameter_object_ref"] = None if alteration.endswith("missing_ref") else "unknown"
    elif alteration in {"constructor_missing_ref", "constructor_unknown_ref"}:
        result["parameter_object_ref"] = None if alteration.endswith("missing_ref") else "unknown"
    elif alteration.endswith("wrong_kind"):
        label = alteration.split("_", 1)[0]
        identifier = "synthetic/parameter/" + ("estimator" if label == "constructor" else "loader")
        parameters[identifier]["kind"] = "controller"
    elif alteration.endswith("wrong_capture_kind"):
        label = alteration.split("_", 1)[0]
        identifier = "synthetic/parameter/" + ("estimator" if label == "constructor" else "loader")
        parameters[identifier]["capture_kind"] = "constructor_fields"
    elif alteration.endswith("bad_digest"):
        label = alteration.split("_", 1)[0]
        identifier = "synthetic/parameter/" + ("estimator" if label == "constructor" else "loader")
        parameters[identifier]["values_sha256"] = "0" * 64
    else:
        # Isolate local exact-value comparison after registry admission. The
        # separate test below proves changed approved values also fail upstream.
        capture = parameters["synthetic/parameter/estimator"]
        capture["values"]["sample_period_s"] = 2.0.hex()
        capture["values_sha256"] = hashlib.sha256(_json(capture["values"])).hexdigest()
    with pytest.raises(checks._Reject) as failure:
        checks._default_loader_parameter_binding(enter, result, calls, terminals, parameters,
                                                  "$/synthetic/constructor")
    assert failure.value.reason == "constructor_binding_mismatch"
    assert failure.value.path == "$/synthetic/constructor/default_loader" + suffix


@pytest.mark.parametrize(("alteration", "field"), [("changed_value", "values"), ("bad_digest", "values_sha256")])
def test_synthetic_default_loader_registry_keeps_external_approved_value_gate(alteration, field):
    raw, authority, _ = _synthetic_default_loader_fixture()
    capture = raw["parameter_objects"][-1]
    if alteration == "changed_value":
        capture["values"]["sample_period_s"] = 2.0.hex()
        capture["values_sha256"] = hashlib.sha256(_json(capture["values"])).hexdigest()
    else:
        capture["values_sha256"] = "0" * 64
    with pytest.raises(checks._Reject) as failure:
        checks._parameter_objects(raw, authority)
    assert failure.value.reason == "constructor_binding_mismatch"
    assert failure.value.path == "$/parameter_objects/synthetic/parameter/estimator/" + field


@pytest.mark.parametrize(("alteration", "reason", "path"), [
    ("module_source", "constructor_binding_mismatch", "0/arguments/module_sha256"),
    ("loader_parent", "lifecycle_pairing_mismatch", "1/parent_call_id"),
    ("loader_callsite", "lifecycle_observation_missing", "1/callsite"),
    ("loader_profile", "lifecycle_pairing_mismatch", "8/profile_id"),
    ("loader_operation", "lifecycle_pairing_mismatch", "8/operation_id"),
    ("config_bytes", "constructor_binding_mismatch", "2"),
    ("config_path", "constructor_binding_mismatch", "2/arguments/path_argument"),
    ("config_document", "constructor_binding_mismatch", "4/arguments/document_sha256"),
    ("config_locator", "authority_missing", "2"),
])
def test_synthetic_default_loader_lifecycle_keeps_parent_and_source_guards(alteration, reason, path):
    raw, authority, contexts = _synthetic_default_loader_fixture()
    events = raw["lifecycle_observations"]
    if alteration == "module_source":
        events[0]["arguments"]["module_sha256"] = "0" * 64
    elif alteration == "loader_parent":
        events[1]["parent_call_id"] = "synthetic/other-constructor"
    elif alteration == "loader_callsite":
        events[1]["callsite"] = "synthetic/other-loader"
    elif alteration == "loader_profile":
        events[1]["profile_id"] = "L1"
    elif alteration == "loader_operation":
        events[1]["operation_id"] = "synthetic/other-operation"
    elif alteration == "config_bytes":
        events[2]["arguments"]["source_bytes_sha256"] = "0" * 64
    elif alteration == "config_path":
        events[2]["arguments"]["path_argument"] = "/synthetic/unapproved.json"
    elif alteration == "config_document":
        events[4]["arguments"]["document_sha256"] = "0" * 64
    else:
        events[2]["arguments"]["source_artifact_ref"] = "synthetic/missing-source.json"
    parameters = checks._parameter_objects(raw, authority)
    with pytest.raises(checks._Reject) as failure:
        checks._lifecycle(raw, authority, contexts, parameters)
    assert failure.value.reason == reason
    assert failure.value.path == "$/lifecycle_observations/" + path
