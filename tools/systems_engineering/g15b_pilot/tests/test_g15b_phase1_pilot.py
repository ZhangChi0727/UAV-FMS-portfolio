"""Positive and negative checks for the G1.5-B structured pilot."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[4]
TOOLS_ROOT = Path(__file__).resolve().parents[2]
PILOT_ROOT = TOOLS_ROOT / "g15b_pilot"
sys.path.insert(0, str(TOOLS_ROOT))

from check_g15b_phase1_pilot import check_pilot  # noqa: E402
from g15b_pilot.build_pilot_views import (  # noqa: E402
    check_outputs,
    render_outputs,
    render_preview_html,
)
from g15b_pilot.pilot_contract import (  # noqa: E402
    MODEL_PATH,
    PilotError,
    load_contract,
    load_sysml_model,
    load_validated_pilot,
    validate_contract,
    validate_schema,
)


MIGRATION_BASELINE_PATH = (
    PILOT_ROOT / "tests" / "fixtures" / "prestructured_semantic_baseline.json"
)


def contract_copy() -> dict:
    return deepcopy(load_contract())


def validate(data: dict) -> None:
    validate_schema(data)
    validate_contract(REPO_ROOT, data, load_sysml_model())


def test_actual_structured_pilot_passes() -> None:
    check_pilot(REPO_ROOT)


def test_five_records_preserve_the_prestructured_semantics() -> None:
    """Compare the one-way migration with its test-only pre-structured oracle."""
    baseline = json.loads(MIGRATION_BASELINE_PATH.read_text(encoding="utf-8"))
    assert baseline["fixture_role"] == "test_only_migration_oracle"
    assert baseline["source_commit"] == "ce350a488ff9b0c50cf32bb4d22c5833b33db597"

    contract = load_contract()
    locator_by_id = {
        source["id"]: source["locator"] for source in contract["source_locators"]
    }
    records_by_key = {record["key"]: record for record in contract["records"]}
    assert list(records_by_key) == [record["key"] for record in baseline["records"]]

    for expected in baseline["records"]:
        actual = records_by_key[expected["key"]]
        for field in ("level", "status", "title", "statement", "rationale", "parent"):
            assert actual[field] == expected[field]
        assert actual["applicability"] == expected["applicability"]
        assert actual["acceptance_condition"].casefold().rstrip(".") == (
            expected["acceptance_condition"].casefold().rstrip(".")
        )
        assert [locator_by_id[source_id] for source_id in actual["source_locator_ids"]] == (
            expected["source_locators"]
        )


def test_actual_parser_records_documented_non_error_warnings() -> None:
    model = load_sysml_model()
    assert model.analysis_warnings
    assert all("severity='warning'" in warning for warning in model.analysis_warnings)


def test_duplicate_temporary_key_fails_closed() -> None:
    data = contract_copy()
    data["records"][-1]["key"] = data["records"][0]["key"]
    with pytest.raises(PilotError, match="duplicate records identity"):
        validate(data)


@pytest.mark.parametrize("field", ("statement", "acceptance_condition"))
def test_required_record_body_or_acceptance_field_fails_closed(field: str) -> None:
    data = contract_copy()
    del data["records"][0][field]
    with pytest.raises(PilotError, match="schema validation failed"):
        validate(data)


def test_illegal_enum_fails_closed() -> None:
    data = contract_copy()
    data["records"][0]["applicability"]["state"] = "unknown"
    with pytest.raises(PilotError, match="schema validation failed"):
        validate(data)


def test_unknown_relation_target_fails_closed() -> None:
    data = contract_copy()
    data["relations"][0]["target_id"] = "PILOT-MODEL-UNKNOWN-01"
    with pytest.raises(PilotError, match="relation target is unknown"):
        validate(data)


def test_wrong_relation_endpoint_type_fails_closed() -> None:
    data = contract_copy()
    data["relations"][0]["target_kind"] = "verification_provision"
    with pytest.raises(PilotError, match="relation endpoint type is invalid"):
        validate(data)


def test_wrong_relation_direction_fails_closed() -> None:
    data = contract_copy()
    data["relations"][0]["direction"] = "reverse"
    with pytest.raises(PilotError, match="schema validation failed"):
        validate(data)


def test_missing_parent_target_fails_closed() -> None:
    data = contract_copy()
    data["records"][1]["parent"] = "PILOT-ONLY-MISSING-99"
    with pytest.raises(PilotError, match="unknown parent relation"):
        validate(data)


def test_parent_hierarchy_cycle_fails_without_rejecting_physical_feedback() -> None:
    data = contract_copy()
    data["records"][0]["parent"] = "PILOT-ONLY-G2-05"
    with pytest.raises(PilotError, match="Parent hierarchy cycle"):
        validate(data)


@pytest.mark.parametrize(
    ("replacement", "message"),
    (
        ("/scenarios/-1/id", "invalid JSON array index"),
        ("/scenarios/06/id", "invalid JSON array index"),
        ("/scenarios/one/id", "invalid JSON array index"),
        ("/scenarios/99/id", "JSON pointer is missing"),
    ),
)
def test_invalid_json_array_index_fails_closed(replacement: str, message: str) -> None:
    data = contract_copy()
    source = next(item for item in data["source_locators"] if item["id"] == "PILOT-SRC-G0-SCENARIO-ID-01")
    source["locator"] = f"05_integration/b0/configs/b0_g0_contract.v2.json#{replacement}"
    with pytest.raises(PilotError, match=message):
        validate(data)


def test_valid_json_array_index_remains_accepted() -> None:
    data = contract_copy()
    source = next(item for item in data["source_locators"] if item["id"] == "PILOT-SRC-G0-SCENARIO-ID-01")
    source["locator"] = "05_integration/b0/configs/b0_g0_contract.v2.json#/scenarios/0/id"
    validate(data)


def test_bad_markdown_anchor_fails_closed() -> None:
    data = contract_copy()
    source = next(item for item in data["source_locators"] if item["id"] == "PILOT-SRC-ARCH-MODULAR-01")
    source["locator"] = "systems_engineering/models/architecture.md#missing-anchor"
    with pytest.raises(PilotError, match="anchor is missing"):
        validate(data)


def test_bad_relation_source_locator_fails_closed() -> None:
    data = contract_copy()
    source = next(item for item in data["source_locators"] if item["id"] == "PILOT-SRC-VER-B0-CHECKS-01")
    source["locator"] = "systems_engineering/verification/verification_plan.md#missing-anchor"
    with pytest.raises(PilotError, match="relation source locator.*anchor is missing"):
        validate(data)


def test_not_applicable_without_approval_fails_closed() -> None:
    data = contract_copy()
    del data["records"][3]["applicability"]["approval_ref"]
    with pytest.raises(PilotError, match="schema validation failed"):
        validate(data)


def test_not_applicable_with_unapproved_reference_fails_closed() -> None:
    data = contract_copy()
    data["records"][3]["applicability"]["approval_ref"] = "PILOT-SRC-CHARTER-PURPOSE-01"
    with pytest.raises(PilotError, match="fixed G0 approval"):
        validate(data)


def test_planned_verification_cannot_claim_pass() -> None:
    data = contract_copy()
    data["verification_provisions"][0]["execution_status"] = "pass"
    with pytest.raises(PilotError, match="schema validation failed"):
        validate(data)


def test_defined_verification_with_pass_and_no_evidence_fails_closed() -> None:
    data = contract_copy()
    data["verification_provisions"][0]["planning_status"] = "defined"
    data["verification_provisions"][0]["execution_status"] = "pass"
    with pytest.raises(PilotError, match="schema validation failed"):
        validate(data)


def test_implemented_development_without_references_fails_closed() -> None:
    data = contract_copy()
    data["development_objects"][0]["lifecycle"] = "implemented"
    with pytest.raises(PilotError, match="schema validation failed"):
        validate(data)


def test_orphan_execution_evidence_fails_closed() -> None:
    data = contract_copy()
    data["execution_evidence"].append(
        {
            "id": "PILOT-EVID-ORPHAN-01",
            "test_case_ref": "fabricated-test",
            "code_version": "fabricated-code",
            "configuration_version": "fabricated-config",
            "command": "not run",
            "environment": "none",
            "result": "pass",
            "locator": "systems_engineering/project_charter.md#purpose",
        }
    )
    with pytest.raises(PilotError, match="execution_evidence must remain empty"):
        validate(data)


def test_planned_verification_cannot_carry_execution_evidence() -> None:
    data = contract_copy()
    data["execution_evidence"].append(
        {
            "id": "PILOT-EVID-UNTRUE-01",
            "test_case_ref": "not-run-test",
            "code_version": "not-run-code",
            "configuration_version": "not-run-config",
            "command": "not run",
            "environment": "none",
            "result": "pass",
            "locator": "systems_engineering/project_charter.md#purpose",
        }
    )
    data["verification_provisions"][0]["evidence_ids"] = ["PILOT-EVID-UNTRUE-01"]
    with pytest.raises(PilotError, match="carries execution evidence"):
        validate(data)


def test_generated_projection_drift_fails_closed(tmp_path: Path) -> None:
    contract, model = load_validated_pilot(REPO_ROOT)
    expected = render_outputs(contract, model)
    generated = tmp_path / "b0_phase1_pilot.md"
    generated.write_text(next(content for path, content in expected.items() if path.name.endswith(".md")), encoding="utf-8")
    generated.write_text(generated.read_text(encoding="utf-8") + "manual drift\n", encoding="utf-8")
    with pytest.raises(PilotError, match="projection drifted"):
        check_outputs({generated: next(content for path, content in expected.items() if path.name.endswith(".md"))})


def test_legal_many_to_many_relation_and_planned_not_applicable_states_pass() -> None:
    data = contract_copy()
    data["relations"].append(
        {
            "id": "PILOT-REL-INTERFACE-MODEL-MANY-01",
            "type": "models",
            "source_id": "PILOT-ONLY-INTERFACE-02",
            "source_kind": "record",
            "target_id": "PILOT-MODEL-IMU-01",
            "target_kind": "model_element",
            "direction": "forward",
            "origin": "project_extension",
            "basis": "A legal additional many-to-many truth-isolation model link for schema coverage.",
            "source_locator_id": "PILOT-SRC-TRUTH-VISIBILITY-01",
        }
    )
    validate(data)


def test_required_model_relation_cannot_be_retargeted_to_existing_element() -> None:
    data = contract_copy()
    relation = next(
        item for item in data["relations"]
        if item["id"] == "PILOT-REL-G2-MODEL-01"
    )
    relation["target_id"] = "PILOT-MODEL-ACTUATOR-01"
    with pytest.raises(PilotError, match="required record-to-model relation"):
        validate(data)


def test_model_type_mismatch_fails_closed() -> None:
    data = contract_copy()
    model = next(item for item in data["model_elements"] if item["id"] == "PILOT-MODEL-CONTROLLER-01")
    model["sysml_kind"] = "interface_definition"
    validate_schema(data)
    with pytest.raises(PilotError, match="SysML model type mismatch"):
        validate_contract(REPO_ROOT, data, load_sysml_model())


def test_dangling_model_identity_fails_closed(tmp_path: Path) -> None:
    source = MODEL_PATH.read_text(encoding="utf-8").replace(
        "'PILOT-MODEL-CONTROLLER-01'", "'PILOT-MODEL-CONTROLLER-99'", 1
    )
    model_path = tmp_path / "dangling.sysml"
    model_path.write_text(source, encoding="utf-8")
    with pytest.raises(PilotError, match="sysmlpy reported semantic error"):
        load_validated_pilot(REPO_ROOT, model_path=model_path)


def test_invalid_sysml_syntax_fails_closed(tmp_path: Path) -> None:
    model_path = tmp_path / "invalid.sysml"
    model_path.write_text(MODEL_PATH.read_text(encoding="utf-8") + "\nthis is not SysML;\n", encoding="utf-8")
    with pytest.raises(PilotError, match="sysmlpy could not parse/analyse"):
        load_sysml_model(model_path)


def test_live_truth_flow_to_controller_fails_closed(tmp_path: Path) -> None:
    source = MODEL_PATH.read_text(encoding="utf-8").replace(
        "flow plant.truth to evaluator.truth;",
        "flow plant.truth to evaluator.truth;\n        flow plant.truth to controller.estimate;",
    )
    model_path = tmp_path / "truth_leak.sysml"
    model_path.write_text(source, encoding="utf-8")
    with pytest.raises(PilotError, match="live truth must not flow"):
        load_validated_pilot(REPO_ROOT, model_path=model_path)


def test_raw_torque_request_only_actuation_fails_closed(tmp_path: Path) -> None:
    source = MODEL_PATH.read_text(encoding="utf-8").replace(
        "paired_command", "torque_request"
    )
    model_path = tmp_path / "raw-request-only.sysml"
    model_path.write_text(source, encoding="utf-8")
    with pytest.raises(PilotError, match="required SysML flow is missing"):
        load_validated_pilot(REPO_ROOT, model_path=model_path)


@pytest.mark.parametrize(
    ("old", "new"),
    (
        (
            "out item paired_command : 'PILOT-MODEL-ITEM-PAIRED-TORQUE-COMMAND-01';",
            "out item paired_command : 'PILOT-MODEL-ITEM-TORQUE-REQUEST-01';",
        ),
        (
            "in item paired_command : 'PILOT-MODEL-ITEM-PAIRED-TORQUE-COMMAND-01';",
            "out item paired_command : 'PILOT-MODEL-ITEM-PAIRED-TORQUE-COMMAND-01';",
        ),
        (
            "item limited_target : 'PILOT-MODEL-ITEM-LIMITED-TARGET-01';",
            "item limited_target : 'PILOT-MODEL-ITEM-TORQUE-REQUEST-01';",
        ),
    ),
)
def test_paired_command_type_members_and_direction_fail_closed(
    tmp_path: Path, old: str, new: str
) -> None:
    source = MODEL_PATH.read_text(encoding="utf-8").replace(old, new, 1)
    assert source != MODEL_PATH.read_text(encoding="utf-8")
    model_path = tmp_path / "wrong-paired-command.sysml"
    model_path.write_text(source, encoding="utf-8")
    with pytest.raises(PilotError, match="SysML feature type or direction mismatch"):
        load_validated_pilot(REPO_ROOT, model_path=model_path)


def test_g2_trace_chain_cannot_be_removed() -> None:
    data = contract_copy()
    data["relations"] = [
        relation
        for relation in data["relations"]
        if relation["id"] != "PILOT-REL-DEV-CONTROLLER-VERIFY-01"
    ]
    with pytest.raises(PilotError, match="planned controller verification relation is missing"):
        validate(data)


def test_generated_sources_are_current_and_use_the_single_json_body_source() -> None:
    contract, model = load_validated_pilot(REPO_ROOT)
    rendered = render_outputs(contract, model)
    check_outputs(rendered)
    assert "Generated review projection; edit pilot_structure.json" in rendered[
        PILOT_ROOT / "strictdoc" / "b0_phase1_pilot.sdoc"
    ]
    assert "do not edit this Markdown file" in rendered[
        PILOT_ROOT / "lightweight" / "b0_phase1_pilot.md"
    ]


def test_local_review_preview_links_records_model_parent_and_planned_objects() -> None:
    contract, model = load_validated_pilot(REPO_ROOT)
    preview = render_preview_html(contract, model)
    assert 'href="#PILOT-ONLY-NEED-01"' in preview
    assert 'href="#PILOT-MODEL-CONTROLLER-01"' in preview
    assert 'id="PILOT-MODEL-CONTROLLER-01"' in preview
    assert 'id="PILOT-DEV-CONTROLLER-CORE-01"' in preview
    assert 'id="PILOT-VER-G2-INTERFACE-01"' in preview
