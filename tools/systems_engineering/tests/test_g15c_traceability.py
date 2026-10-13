from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys

import pytest

TOOLS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_ROOT))

import g15c_traceability as trace  # noqa: E402
from g15c_traceability import TraceabilityError, render_html, render_markdown, validate_ledger  # noqa: E402


REPO = Path(__file__).resolve().parents[3]


def ledger():
    return json.loads((REPO / "systems_engineering/verification/b0_execution_evidence.json").read_text(encoding="utf-8"))


def validate(document=None, *, files=False, frozen=False, evidence_cache=None, now=None):
    return validate_ledger(REPO, document or ledger(), check_files=files, check_frozen=frozen, evidence_cache=evidence_cache, now=now)


def test_current_ledger_is_valid_and_honest():
    assert validate(files=True, frozen=True) == {
        "requirements": 30,
        "model_elements": 26,
        "verifications": 29,
        "design_linked_requirements": 30,
        "production_records": 1,
        "executed_specifications": 5,
        "accepted_evidence_records": 0,
        "satisfied_requirements": 0,
        "result_counts": {"pass": 1},
    }


def test_partial_pending_pass_does_not_satisfy_requirements():
    assert validate()["satisfied_requirements"] == 0


def test_complete_accepted_evidence_counts_only_linked_requirements(tmp_path):
    doc = ledger()
    record = doc["records"][0]
    artifact = tmp_path / "g1_component_evidence.json"
    artifact.write_bytes(b"controlled evidence bytes")
    now = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)
    record["evidence"].update(
        availability="local_only",
        sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),
        verified_at=now.isoformat(),
        expires_at=(now + timedelta(days=1)).isoformat(),
    )
    record["coverage"] = "complete"
    record["execution"]["criterion_locators"] = [
        f"systems_engineering/verification/b0_verification_specifications.json#{spec_id}"
        for spec_id in record["verification_spec_ids"]
    ]
    record["review"] = {"status": "accepted", "reviewer": "independent-reviewer", "source": "review://decision"}
    summary = validate(doc, evidence_cache=tmp_path, now=now)
    assert summary["accepted_evidence_records"] == 1
    assert summary["satisfied_requirements"] == 5


def test_not_run_is_legal_but_not_satisfied():
    doc = ledger()
    record = doc["records"][0]
    record["execution"].update({"result": "not_run", "started_at": None, "completed_at": None, "exit_code": None})
    record["evidence"].update({"availability": "none", "uri": None, "artifact_id": None, "artifact_file": None, "sha256": None, "archive_sha256": None, "source_run": None, "source_commit": None, "verified_at": None, "expires_at": None})
    record["applicability"].update({"status": "not_assessed", "source_commit": None, "target_commit": None, "relevant_files": []})
    assert validate(doc)["executed_specifications"] == 0


@pytest.mark.parametrize("field", ["execution", "evidence", "applicability", "review"])
def test_missing_required_dimension_is_rejected(field):
    doc = ledger()
    del doc["records"][0][field]
    with pytest.raises(TraceabilityError, match="schema error"):
        validate(doc)


@pytest.mark.parametrize(
    ("field", "value"),
    [("result", "green"), ("level", "flight"), ("method", "guess")],
)
def test_unknown_execution_enum_is_rejected(field, value):
    doc = ledger()
    doc["records"][0]["execution"][field] = value
    with pytest.raises(TraceabilityError, match="schema error"):
        validate(doc)


def test_duplicate_record_is_rejected():
    doc = ledger()
    doc["records"].append(deepcopy(doc["records"][0]))
    with pytest.raises(TraceabilityError, match="duplicate execution"):
        validate(doc)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [("verification_spec_ids", ["B0-VER-UNKNOWN"], "unknown verification"), ("requirement_ids", ["B0-REQ-9999"], "unknown requirement"), ("model_ids", ["B0-MODEL-UNKNOWN"], "unknown model")],
)
def test_dangling_identity_is_rejected(field, value, message):
    doc = ledger()
    doc["records"][0][field] = value
    with pytest.raises(TraceabilityError, match=message):
        validate(doc)


def test_requirement_specification_mismatch_is_rejected():
    doc = ledger()
    doc["records"][0]["requirement_ids"] = ["B0-REQ-0001"]
    with pytest.raises(TraceabilityError, match="mismatch"):
        validate(doc)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda r: r["execution"].update(exit_code=1), "exit code"),
        (lambda r: r["evidence"].update(availability="missing"), "raw evidence"),
        (lambda r: r["evidence"].update(sha256=None), "hash/URI"),
        (lambda r: r["execution"]["tests"].update(skipped=1), "skip/xfail"),
        (lambda r: r["execution"]["tests"].update(xfailed=1), "skip/xfail"),
    ],
)
def test_fake_pass_is_rejected(mutation, message):
    doc = ledger()
    mutation(doc["records"][0])
    with pytest.raises(TraceabilityError, match=message):
        validate(doc)


def test_unreviewed_record_cannot_be_disguised_as_accepted():
    doc = ledger()
    doc["records"][0]["review"]["status"] = "accepted"
    with pytest.raises(TraceabilityError, match="review provenance"):
        validate(doc)


def _claim_verified(doc, tmp_path, now):
    record = doc["records"][0]
    record["evidence"].update(
        availability="remote_verified",
        verified_at=now.isoformat(),
        expires_at=(now + timedelta(days=1)).isoformat(),
    )
    return record


def test_remote_verified_is_rejected_when_offline_bytes_are_unavailable(tmp_path):
    doc = ledger()
    now = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)
    _claim_verified(doc, tmp_path, now)
    with pytest.raises(TraceabilityError, match="missing cached evidence"):
        validate(doc, evidence_cache=tmp_path, now=now)


def test_cached_evidence_hash_mismatch_is_rejected(tmp_path):
    doc = ledger()
    now = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)
    record = _claim_verified(doc, tmp_path, now)
    (tmp_path / record["evidence"]["artifact_file"]).write_bytes(b"tampered")
    with pytest.raises(TraceabilityError, match="hash mismatch"):
        validate(doc, evidence_cache=tmp_path, now=now)


def test_expired_evidence_is_rejected_before_acceptance(tmp_path):
    doc = ledger()
    now = datetime(2027, 1, 12, tzinfo=timezone.utc)
    record = doc["records"][0]
    record["evidence"].update(availability="remote_verified", verified_at="2026-10-13T12:00:00Z")
    with pytest.raises(TraceabilityError, match="evidence expired"):
        validate(doc, evidence_cache=tmp_path, now=now)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("id",), 123),
        (("implementation", "commit"), 42),
    ],
)
def test_wrong_scalar_types_produce_structured_schema_errors(path, value):
    doc = ledger()
    target = doc["records"][0]
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value
    with pytest.raises(TraceabilityError, match="schema error at"):
        validate(doc)


def test_all_zero_source_revision_is_rejected():
    doc = ledger()
    doc["records"][0]["evidence"]["source_commit"] = "0" * 40
    doc["records"][0]["applicability"]["source_commit"] = "0" * 40
    with pytest.raises(TraceabilityError, match="cannot be all zero"):
        validate(doc)


def test_unknown_source_revision_is_rejected_when_applicability_is_checked():
    doc = ledger()
    invalid = "1" * 40
    doc["records"][0]["evidence"]["source_commit"] = invalid
    doc["records"][0]["applicability"]["source_commit"] = invalid
    with pytest.raises(TraceabilityError, match="cannot read committed applicability path"):
        validate(doc, files=True)


def test_dependency_closure_includes_contract_and_quaternion():
    paths = {item["path"] for item in ledger()["records"][0]["applicability"]["relevant_files"]}
    assert {"01_simulation/b0/contract.py", "01_simulation/b0/quaternion.py"} <= paths


def test_source_side_hash_mismatch_is_rejected():
    doc = ledger()
    doc["records"][0]["applicability"]["relevant_files"][0]["source_sha256"] = "0" * 64
    with pytest.raises(TraceabilityError, match="source applicability hash mismatch"):
        validate(doc, files=True)


def test_stale_relevant_file_hash_is_rejected():
    doc = ledger()
    doc["records"][0]["applicability"]["relevant_files"][0]["target_sha256"] = "0" * 64
    with pytest.raises(TraceabilityError, match="target applicability hash mismatch"):
        validate_ledger(REPO, doc, check_files=True, check_frozen=False)


def test_repository_escape_is_rejected():
    doc = ledger()
    doc["records"][0]["implementation"]["paths"] = ["../outside"]
    with pytest.raises(TraceabilityError, match="escapes repository"):
        validate_ledger(REPO, doc, check_files=True, check_frozen=False)


def test_fixture_cannot_enter_the_production_ledger():
    doc = ledger()
    fixture = deepcopy(doc["records"][0])
    fixture["id"] = "B0-EXEC-FIXTURE-NEGATIVE"
    fixture["record_kind"] = "fixture"
    doc["records"].append(fixture)
    with pytest.raises(TraceabilityError, match="fixture prohibited"):
        validate(doc)


def test_superseded_record_is_excluded():
    doc = ledger()
    newer = deepcopy(doc["records"][0])
    newer["id"] = "B0-EXEC-G1-COMPONENT-REPEAT"
    newer["supersedes"] = doc["records"][0]["id"]
    doc["records"].append(newer)
    assert validate(doc)["production_records"] == 1


def test_supersession_cannot_replace_an_unrelated_scope():
    doc = ledger()
    newer = deepcopy(doc["records"][0])
    newer["id"] = "B0-EXEC-G1-COMPONENT-UNRELATED"
    newer["supersedes"] = doc["records"][0]["id"]
    newer["verification_spec_ids"] = ["B0-VER-SCOPE-INSPECTION"]
    newer["requirement_ids"] = ["B0-REQ-0001"]
    with pytest.raises(TraceabilityError, match="supersession verification scope mismatch"):
        validate({**doc, "records": [doc["records"][0], newer]})


def test_unknown_superseded_record_is_rejected():
    doc = ledger()
    doc["records"][0]["supersedes"] = "B0-EXEC-NOT-THERE"
    with pytest.raises(TraceabilityError, match="unknown superseded"):
        validate(doc)


def test_supersedes_cycle_is_rejected():
    doc = ledger()
    newer = deepcopy(doc["records"][0])
    newer["id"] = "B0-EXEC-G1-COMPONENT-REPEAT"
    doc["records"][0]["supersedes"] = newer["id"]
    newer["supersedes"] = doc["records"][0]["id"]
    doc["records"].append(newer)
    with pytest.raises(TraceabilityError, match="supersedes cycle"):
        validate(doc)


def test_complete_coverage_requires_every_criterion_locator():
    doc = ledger()
    doc["records"][0]["coverage"] = "complete"
    with pytest.raises(TraceabilityError, match="criterion locator"):
        validate(doc)


def test_empty_production_ledger_is_legal_and_reports_zero():
    doc = ledger()
    doc["records"] = []
    summary = validate(doc)
    assert summary["production_records"] == 0
    assert summary["executed_specifications"] == 0
    assert summary["satisfied_requirements"] == 0
    rendered = render_markdown(REPO, doc)
    assert "No current production execution record exists" in rendered
    assert "retained G1 component artifact" not in rendered


def test_historical_normative_blob_manifest_is_enforced(monkeypatch):
    original = trace._git_blob

    def changed(repo, path):
        if path == "systems_engineering/requirements/b0_requirements.json":
            return "0" * 40
        return original(repo, path)

    monkeypatch.setattr(trace, "_git_blob", changed)
    with pytest.raises(TraceabilityError, match="prohibited frozen normative drift"):
        validate_ledger(REPO, ledger(), check_files=False, check_frozen=True)


def test_report_is_deterministic_and_exposes_denominators():
    first = render_markdown(REPO)
    second = render_markdown(REPO)
    assert first == second
    assert "5/29 specifications" in first
    assert "0/30" in first
    assert "proves no requirement satisfied" in first


def test_controlled_report_projection_is_current():
    expected = render_markdown(REPO).rstrip() + "\n"
    actual = (REPO / "systems_engineering/reports/b0/g15c_verification_status.md").read_text(encoding="utf-8")
    assert actual == expected


def test_html_reader_has_native_metrics_records_and_anchors():
    rendered = render_html(REPO)
    assert "id='conclusion'" in rendered
    assert "B0-EXEC-G1-COMPONENT-20261013" in rendered
    assert "5/29 specifications" in rendered
    assert rendered.count("class='requirement'") == 30
    assert "id='group-without-execution'" in rendered
    assert "**" not in rendered
