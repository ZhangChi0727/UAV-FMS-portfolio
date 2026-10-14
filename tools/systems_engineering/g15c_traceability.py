"""Fail-closed B0 G1.5-C execution-evidence validation and reporting."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker


class TraceabilityError(ValueError):
    """Raised when evidence cannot support the claimed traceability state."""


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise TraceabilityError(message)


def _load(path: Path) -> Any:
    _need(path.is_file(), f"missing required file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TraceabilityError(f"invalid JSON in {path}: {exc}") from exc


def _inside(repo: Path, value: str, label: str) -> Path:
    path = (repo / value).resolve()
    try:
        path.relative_to(repo.resolve())
    except ValueError as exc:
        raise TraceabilityError(f"{label} escapes repository: {value}") from exc
    return path


def _unique(items: list[Mapping[str, Any]], label: str) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for item in items:
        identity = item["id"]
        _need(identity not in result, f"duplicate {label}: {identity}")
        result[identity] = item
    return result


def _git_blob(repo: Path, path: str) -> str:
    try:
        return subprocess.check_output(["git", "hash-object", "--", path], cwd=repo, text=True).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise TraceabilityError(f"cannot hash controlled path: {path}") from exc


def _git_revision_sha256(repo: Path, revision: str, path: str) -> str:
    """Hash bytes from an explicit committed revision, never the worktree."""
    try:
        content = subprocess.check_output(["git", "show", f"{revision}:{path}"], cwd=repo, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise TraceabilityError(f"cannot read committed applicability path: {revision}:{path}") from exc
    return hashlib.sha256(content).hexdigest()


def _parse_time(value: str, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise TraceabilityError(f"invalid {label}: {value!r}") from exc
    _need(parsed.tzinfo is not None, f"{label} must include a timezone")
    return parsed


def validate_ledger(
    repo: Path,
    ledger_data: Mapping[str, Any] | None = None,
    *,
    check_files: bool = True,
    check_frozen: bool = True,
    evidence_cache: Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validate schema, trace links, evidence truthfulness and controlled drift."""

    ledger_path = repo / "systems_engineering/verification/b0_execution_evidence.json"
    schema = _load(repo / "systems_engineering/verification/b0_execution_evidence.schema.json")
    ledger = ledger_data or _load(ledger_path)
    errors = sorted(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(ledger), key=lambda error: list(error.absolute_path))
    if errors:
        where = "/".join(str(part) for part in errors[0].absolute_path) or "<root>"
        raise TraceabilityError(f"evidence schema error at {where}: {errors[0].message}")

    req_doc = _load(_inside(repo, ledger["baseline"]["requirements_path"], "requirements path"))
    ver_doc = _load(_inside(repo, ledger["baseline"]["verification_path"], "verification path"))
    requirements = _unique(req_doc["requirements"], "requirement ID")
    specifications = _unique(ver_doc["specifications"], "verification ID")
    records = _unique(ledger["records"], "execution record")
    required_g1_closure = {"01_simulation/b0/plant.py", "01_simulation/b0/actuator.py", "01_simulation/b0/imu.py", "01_simulation/b0/evidence.py", "01_simulation/b0/tests/test_components.py", "01_simulation/b0/contract.py", "01_simulation/b0/quaternion.py", "05_integration/b0/configs/b0_g0_contract.v2.json"}
    required_g2a_estimator_closure = {
        ".github/workflows/ci.yml",
        "02_estimation/b0/estimator.py",
        "02_estimation/b0/evidence.py",
        "02_estimation/b0/tests/test_estimator.py",
        "02_estimation/b0/tests/test_evidence.py",
        "02_estimation/b0/configs/b0_g2_estimator.v1.json",
        "02_estimation/b0/configs/b0_g2_estimator_approval.v1.json",
        "05_integration/b0/configs/b0_g0_contract.v2.json",
        "05_integration/b0/validate_config.py",
    }
    _need(len(requirements) == 30, f"controlled view must contain 30 requirements, found {len(requirements)}")
    _need(len(specifications) == 29, f"controlled view must contain 29 verification specifications, found {len(specifications)}")

    model_source = (repo / "systems_engineering/models/b0_system.sysml").read_text(encoding="utf-8")
    model_ids = set(re.findall(r"<'(B0-MODEL-[A-Z0-9-]+)'>", model_source))
    _need(len(model_ids) == 26, f"controlled model must contain 26 stable identities, found {len(model_ids)}")
    for req_id, req in requirements.items():
        for spec_id in req["verification_ids"]:
            _need(spec_id in specifications, f"unknown verification on {req_id}: {spec_id}")
            _need(req_id in specifications[spec_id]["requirement_ids"], f"forward/reverse mismatch: {req_id} -> {spec_id}")
    for spec_id, spec in specifications.items():
        for req_id in spec["requirement_ids"]:
            _need(req_id in requirements, f"verification has unknown requirement: {spec_id} -> {req_id}")
            _need(spec_id in requirements[req_id]["verification_ids"], f"reverse/forward mismatch: {spec_id} -> {req_id}")

    superseded: set[str] = {
        record["supersedes"] for record in records.values() if record["supersedes"] is not None
    }
    auditable_records: set[str] = set()
    effective_now = now or datetime.now(timezone.utc)
    for record_id, record in records.items():
        _need(record["record_kind"] == "production_evidence", f"fixture prohibited in production ledger: {record_id}")
        if record["supersedes"] is not None:
            _need(record["supersedes"] in records, f"unknown superseded record: {record_id}")
            _need(record["supersedes"] != record_id, f"record supersedes itself: {record_id}")
            previous = records[record["supersedes"]]
            _need(previous["record_kind"] == "production_evidence", f"cannot supersede fixture: {record_id}")
            _need(set(record["verification_spec_ids"]) == set(previous["verification_spec_ids"]), f"supersession verification scope mismatch: {record_id}")
            _need(set(record["requirement_ids"]) == set(previous["requirement_ids"]), f"supersession requirement scope mismatch: {record_id}")
            superseded.add(record["supersedes"])
        _need(all(value in specifications for value in record["verification_spec_ids"]), f"unknown verification in {record_id}")
        _need(all(value in requirements for value in record["requirement_ids"]), f"unknown requirement in {record_id}")
        _need(all(value in model_ids for value in record["model_ids"]), f"unknown model identity in {record_id}")
        linked_requirements = {req for spec in record["verification_spec_ids"] for req in specifications[spec]["requirement_ids"]}
        _need(set(record["requirement_ids"]) <= linked_requirements, f"record requirement/specification mismatch: {record_id}")

        execution, evidence = record["execution"], record["evidence"]
        applicability, review = record["applicability"], record["review"]
        for label, value in (("implementation commit", record["implementation"]["commit"]), ("evidence source commit", evidence["source_commit"]), ("applicability source commit", applicability["source_commit"]), ("applicability target commit", applicability["target_commit"])):
            if value is not None:
                _need(set(value) != {"0"}, f"{label} cannot be all zero: {record_id}")
        if execution["result"] == "not_run":
            _need(execution["exit_code"] is None and evidence["availability"] == "none", f"not_run record contains execution evidence: {record_id}")
        if execution["started_at"] and execution["completed_at"]:
            _need(_parse_time(execution["started_at"], "started_at") <= _parse_time(execution["completed_at"], "completed_at"), f"execution time order is invalid: {record_id}")
        if execution["result"] == "pass":
            _need(execution["exit_code"] == 0, f"pass has non-zero/unknown exit code: {record_id}")
            _need(evidence["availability"] in {"local_only", "remote_unverified", "remote_verified"}, f"pass lacks available raw evidence: {record_id}")
            _need(evidence["sha256"] is not None and evidence["uri"], f"pass lacks evidence hash/URI: {record_id}")
            _need(execution["tests"]["failed"] == 0, f"pass records failed tests: {record_id}")
            _need(execution["tests"]["skipped"] == 0 and execution["tests"]["xfailed"] == 0, f"pass relies on skip/xfail: {record_id}")
        if evidence["availability"].startswith("remote_"):
            _need(evidence["artifact_id"] and evidence["artifact_file"] and evidence["archive_sha256"] and evidence["source_run"] and evidence["source_commit"] and evidence["expires_at"], f"remote evidence lacks exact artifact identity: {record_id}")
            _need(bool(evidence["uri"]), f"remote evidence lacks URI: {record_id}")
            _need(evidence["uri"].rstrip("/").endswith(f"/{evidence['artifact_id']}"), f"artifact URI/ID mismatch: {record_id}")
        if evidence["availability"] == "local_only":
            _need(bool(evidence["artifact_file"]), f"local evidence lacks artifact file: {record_id}")
        if review["status"] == "accepted":
            _need(review["reviewer"] and review["source"], f"accepted record lacks review provenance: {record_id}")
        if applicability["status"] in {"applicable_exact", "applicable_by_analysis"}:
            _need(applicability["relevant_files"], f"applicable record lacks relevant-file basis: {record_id}")
            _need(applicability["source_commit"] == evidence["source_commit"], f"applicability/evidence source commit mismatch: {record_id}")
        if evidence["availability"] in {"local_only", "remote_verified"}:
            _need(evidence["verified_at"] and evidence["expires_at"], f"verified evidence lacks verification/expiry time: {record_id}")
            verified_at = _parse_time(evidence["verified_at"], "verified_at")
            _need(verified_at <= effective_now, f"evidence verification is in the future: {record_id}")
            if execution["completed_at"]:
                _need(_parse_time(execution["completed_at"], "completed_at") <= verified_at, f"evidence verified before execution completed: {record_id}")
            _need(effective_now <= _parse_time(evidence["expires_at"], "expires_at"), f"evidence expired: {record_id}")
            _need(evidence_cache is not None, f"verified evidence unavailable offline: {record_id}")
            cached = _inside(evidence_cache.resolve(), evidence["artifact_file"], "evidence cache path")
            _need(cached.is_file(), f"missing cached evidence: {record_id} -> {evidence['artifact_file']}")
            _need(hashlib.sha256(cached.read_bytes()).hexdigest() == evidence["sha256"], f"cached evidence hash mismatch: {record_id}")
            auditable_records.add(record_id)
        if record["coverage"] == "complete":
            locators = " ".join(execution["criterion_locators"])
            _need(all(spec_id in locators for spec_id in record["verification_spec_ids"]), f"complete record lacks a criterion locator for every specification: {record_id}")
        if check_files and execution["result"] != "not_run" and record_id not in superseded:
            try:
                subprocess.check_output(["git", "cat-file", "-e", f"{record['implementation']['commit']}^{{commit}}"], cwd=repo, stderr=subprocess.DEVNULL)
            except (OSError, subprocess.CalledProcessError) as exc:
                raise TraceabilityError(f"unknown implementation commit: {record_id}") from exc
            for value in record["implementation"]["paths"]:
                _need(_inside(repo, value, "implementation path").is_file(), f"missing implementation path: {record_id} -> {value}")
                _git_revision_sha256(repo, record["implementation"]["commit"], value)
            g1_specs = {"B0-VER-PLANT-DYNAMICS", "B0-VER-PLANT-QUATERNION", "B0-VER-ACTUATOR-DYNAMICS", "B0-VER-IMU-GYRO", "B0-VER-IMU-SPECIFIC-FORCE"}
            g2a_estimator_specs = {"B0-VER-ESTIMATOR-PROPAGATION", "B0-VER-ESTIMATOR-FUSION", "B0-VER-YAW-LIMITATION", "B0-VER-ACCEL-CONTAMINATION"}
            relevant_paths = {item["path"] for item in applicability["relevant_files"]}
            if set(record["verification_spec_ids"]) & g1_specs:
                _need(required_g1_closure <= relevant_paths, f"incomplete G1 dependency closure: {record_id}")
            if set(record["verification_spec_ids"]) & g2a_estimator_specs:
                _need(required_g2a_estimator_closure <= relevant_paths, f"incomplete G2-A estimator dependency closure: {record_id}")
            _need(set(record["implementation"]["paths"]) <= relevant_paths, f"implementation paths missing from applicability closure: {record_id}")
            for value in record["implementation"]["paths"]:
                implementation_digest = _git_revision_sha256(repo, record["implementation"]["commit"], value)
                source_digest = _git_revision_sha256(repo, evidence["source_commit"], value)
                _need(implementation_digest == source_digest, f"implementation/evidence source mismatch: {record_id} -> {value}")
            for item in applicability["relevant_files"]:
                path = _inside(repo, item["path"], "applicability path")
                _need(path.is_file(), f"missing applicability file: {record_id} -> {item['path']}")
                source_digest = _git_revision_sha256(repo, applicability["source_commit"], item["path"])
                target_digest = _git_revision_sha256(repo, applicability["target_commit"], item["path"])
                head_digest = _git_revision_sha256(repo, "HEAD", item["path"])
                _need(source_digest == item["source_sha256"], f"source applicability hash mismatch: {record_id} -> {item['path']}")
                _need(target_digest == item["target_sha256"], f"target applicability hash mismatch: {record_id} -> {item['path']}")
                _need(source_digest == target_digest, f"applicability dependency changed: {record_id} -> {item['path']}")
                _need(head_digest == target_digest, f"committed HEAD differs from applicability target: {record_id} -> {item['path']}")

    for record_id in records:
        seen: set[str] = set()
        cursor: str | None = record_id
        while cursor is not None:
            _need(cursor not in seen, f"supersedes cycle at {record_id}")
            seen.add(cursor)
            cursor = records[cursor]["supersedes"]

    if check_frozen:
        manifest = _load(repo / "systems_engineering/reports/b0/g15b_joint_baseline_manifest.json")
        _need(manifest["candidate_asset_commit_s"] == ledger["baseline"]["frozen_asset_commit"], "frozen baseline commit mismatch")
        allowed_presentation = {".github/workflows/ci.yml", "docs/roadmap.md", "systems_engineering/README.md"}
        normative_prefixes = ("systems_engineering/models/", "systems_engineering/requirements/", "systems_engineering/verification/")
        for asset in manifest["assets"]:
            path = asset["path"]
            if path in allowed_presentation or not path.startswith(normative_prefixes):
                continue
            _need(_git_blob(repo, path) == asset["blob"], f"prohibited frozen normative drift: {path}")

    production = [record for record in records.values() if record["record_kind"] == "production_evidence" and record["id"] not in superseded]
    executed_specs = {spec for record in production if record["execution"]["result"] != "not_run" for spec in record["verification_spec_ids"]}
    accepted_records = [record for record in production if _counts_as_accepted(record, auditable_records)]
    satisfied_requirements = {
        req_id
        for req_id, req in requirements.items()
        if req["verification_ids"] and all(any(_counts_as_accepted(record, auditable_records) and spec_id in record["verification_spec_ids"] and req_id in record["requirement_ids"] for record in production) for spec_id in req["verification_ids"])
    }
    design_linked = {
        req_id for req_id, req in requirements.items()
        if req["source_ids"] and req["model_element_ids"] and req["verification_ids"]
    }
    return {
        "requirements": len(requirements), "model_elements": len(model_ids), "verifications": len(specifications),
        "design_linked_requirements": len(design_linked),
        "production_records": len(production), "executed_specifications": len(executed_specs),
        "accepted_evidence_records": len(accepted_records), "satisfied_requirements": len(satisfied_requirements),
        "result_counts": dict(Counter(record["execution"]["result"] for record in production)),
    }


def _counts_as_accepted(record: Mapping[str, Any], auditable_records: set[str]) -> bool:
    return bool(record["id"] in auditable_records and record["execution"]["result"] == "pass" and record["applicability"]["status"] in {"applicable_exact", "applicable_by_analysis"} and record["review"]["status"] == "accepted" and record["coverage"] == "complete")


def _report_records(ledger: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    superseded = {record["supersedes"] for record in ledger["records"] if record["supersedes"]}
    return [record for record in ledger["records"] if record["id"] not in superseded and record["record_kind"] == "production_evidence"]


def _requirement_gap(req: Mapping[str, Any], records: list[Mapping[str, Any]]) -> str:
    accepted_specs = {
        spec for record in records
        if record["execution"]["result"] == "pass"
        and record["evidence"]["availability"] in {"local_only", "remote_verified"}
        and record["applicability"]["status"] in {"applicable_exact", "applicable_by_analysis"}
        and record["review"]["status"] == "accepted" and record["coverage"] == "complete"
        and req["id"] in record["requirement_ids"]
        for spec in record["verification_spec_ids"]
    }
    missing = [spec for spec in req["verification_ids"] if spec not in accepted_specs]
    return "Satisfied by accepted complete evidence." if not missing else f"Missing accepted evidence for: {', '.join(missing)}."


def render_markdown(repo: Path, ledger_data: Mapping[str, Any] | None = None, *, evidence_cache: Path | None = None, now: datetime | None = None) -> str:
    ledger = ledger_data or _load(repo / "systems_engineering/verification/b0_execution_evidence.json")
    summary = validate_ledger(repo, ledger, evidence_cache=evidence_cache, now=now)
    req_doc = _load(repo / ledger["baseline"]["requirements_path"])
    ver_doc = _load(repo / ledger["baseline"]["verification_path"])
    sources = _unique(req_doc["sources"], "source ID")
    specs = _unique(ver_doc["specifications"], "verification ID")
    current_records = _report_records(ledger)
    rows = []
    for record in current_records:
        rows.append(f"| `{record['id']}` | {record['execution']['level']} | {record['execution']['result']} | {record['evidence']['availability']} | {record['applicability']['status']} | {record['review']['status']} | {record['coverage']} |")
    gap = "No current production execution record exists." if not current_records else f"{summary['satisfied_requirements']}/30 requirements currently have accepted complete evidence; all remaining gaps are listed per requirement."
    lines = [
        "# B0 G1.5-C verification traceability status", "", "> Controlled current view; frozen verification specifications remain planned/not_run and are not rewritten.", "",
        "## First-screen conclusion", "",
        f"- Design traceability: **{summary['design_linked_requirements']}/30 requirements** have source, model and verification relations; the controlled catalog contains **{summary['model_elements']} model identities** and **{summary['verifications']}/29 planned specifications**.",
        f"- Execution: **{summary['executed_specifications']}/29 specifications** have at least one current production execution record.",
        f"- Accepted evidence: **{summary['accepted_evidence_records']}/{summary['production_records']} production records**.",
        f"- Requirement satisfaction: **{summary['satisfied_requirements']}/30**. A requirement counts only when every required specification has complete, applicable, available and accepted pass evidence.",
        f"- Current gap: {gap}", "",
        "## Version boundary", "", f"- Frozen requirements/model base: `{ledger['baseline']['frozen_asset_commit']}`.", f"- Controlled current applicability target: `{ledger['baseline']['closeout_commit']}`.", "- Evaluated repository revision: committed `HEAD`, resolved by the checker at runtime; uncommitted worktree bytes are excluded.", "",
        "## Execution records", "", "| Record | Level | Result | Evidence | Applicability | Review | Coverage |", "|---|---|---|---|---|---|---|", *rows, "",
        "## Requirement index", "", "Static groups: [stakeholder](#group-stakeholder), [system](#group-system), [component](#group-component), [with execution](#group-with-execution), [without execution](#group-without-execution).", "",
    ]
    requirements = req_doc["requirements"]
    for level in ("stakeholder", "system", "component"):
        members = [req for req in requirements if req["level"] == level]
        lines.extend([f"### Group: {level}", f"<a id=\"group-{level}\"></a>", "", ", ".join(f"[`{req['id']}`](#{req['id'].lower()})" for req in members), ""])
    with_execution = [req for req in requirements if any(req["id"] in record["requirement_ids"] and record["execution"]["result"] != "not_run" for record in current_records)]
    without_execution = [req for req in requirements if req not in with_execution]
    lines.extend(["### Group: with execution", '<a id="group-with-execution"></a>', "", ", ".join(f"[`{req['id']}`](#{req['id'].lower()})" for req in with_execution) or "None.", "", "### Group: without execution", '<a id="group-without-execution"></a>', "", ", ".join(f"[`{req['id']}`](#{req['id'].lower()})" for req in without_execution) or "None.", "", "## Requirement chains", ""])
    for req in requirements:
        linked_records = [record for record in current_records if req["id"] in record["requirement_ids"] and record["execution"]["result"] != "not_run"]
        source_text = "; ".join(f"`{sid}` → [`{sources[sid]['path']}`](../../../{sources[sid]['path']}) ({sources[sid]['locator']})" for sid in req["source_ids"])
        verification_text = "; ".join(f"`{sid}` ({specs[sid]['method']}; {specs[sid]['responsible']}; planned `{specs[sid]['execution_status']}`)" for sid in req["verification_ids"])
        execution_text = "; ".join(f"`{record['id']}`: {record['execution']['result']}, [{record['evidence']['availability']}]({record['evidence']['uri']}), SHA-256 `{record['evidence']['sha256']}`, implementation {', '.join(record['implementation']['paths'])}, review {record['review']['status']} ({record['review']['source'] or 'no decision source'}), coverage {record['coverage']}" for record in linked_records) or "Not executed; evidence and review are pending."
        lines.extend([f"### {req['id']}", "", f"- Title: {req['title']}", f"- Source: {source_text}", f"- Requirement: {req['statement']}", f"- Rationale: {req['rationale']}", f"- Model/responsibility: {', '.join(f'`{value}`' for value in req['model_element_ids'])}; responsible {', '.join(f'`{value}`' for value in req['responsible_components'])}.", f"- Verification: {verification_text}", f"- Execution/evidence/review: {execution_text}", f"- Gap: {_requirement_gap(req, current_records)}", ""])
    lines.extend([
        "## Reading and filtering", "", "Use the ledger fields `execution.level`, `execution.result`, `evidence.availability`, `applicability.status`, `review.status`, and `coverage`. Module and integration records are distinct; fixture records are prohibited from the production ledger.", "",
        "## Evidence chain", "", "The current record links the frozen specification IDs to G1 implementation paths, an Actions run artifact, SHA-256 content identity, relevant-file applicability hashes, and an explicit pending review. Artifact expiry changes evidence availability and must not silently preserve an auditable-pass claim.", "",
        "## External research-suite interface", "", "A future external suite may contribute a record only by supplying the same version, criterion, command, raw-evidence hash/URI, applicability, and review fields. This repository does not run or write to an external suite in G1.5-C.", "",
    ])
    return "\n".join(lines)


def render_html(repo: Path, ledger_data: Mapping[str, Any] | None = None, *, evidence_cache: Path | None = None, now: datetime | None = None) -> str:
    ledger = ledger_data or _load(repo / "systems_engineering/verification/b0_execution_evidence.json")
    summary = validate_ledger(repo, ledger, evidence_cache=evidence_cache, now=now)
    req_doc = _load(repo / ledger["baseline"]["requirements_path"])
    ver_doc = _load(repo / ledger["baseline"]["verification_path"])
    sources = _unique(req_doc["sources"], "source ID")
    specs = _unique(ver_doc["specifications"], "verification ID")
    current_records = _report_records(ledger)
    gap = "No current production execution record exists." if not current_records else f"{summary['satisfied_requirements']}/30 requirements currently have accepted complete evidence; remaining gaps are listed per requirement."
    metrics = [
        ("Design traceability", f"{summary['design_linked_requirements']}/30 requirements have source, model and verification relations; {summary['model_elements']} model identities; {summary['verifications']}/29 planned specifications."),
        ("Execution", f"{summary['executed_specifications']}/29 specifications have a current production execution record."),
        ("Accepted evidence", f"{summary['accepted_evidence_records']}/{summary['production_records']} production records."),
        ("Requirement satisfaction", f"{summary['satisfied_requirements']}/30; every required specification needs complete, applicable, available and accepted pass evidence."),
        ("Current gap", gap),
    ]
    metric_html = "".join(f"<section class='card'><h3>{html.escape(label)}</h3><p>{html.escape(value)}</p></section>" for label, value in metrics)
    records = "".join(
        "<article class='record'>"
        f"<h3>{html.escape(record['id'])}</h3>"
        f"<p><span>level</span> {html.escape(record['execution']['level'])} · <span>result</span> {html.escape(record['execution']['result'])} · <span>evidence</span> {html.escape(record['evidence']['availability'])}</p>"
        f"<p><span>applicability</span> {html.escape(record['applicability']['status'])} · <span>review</span> {html.escape(record['review']['status'])} · <span>coverage</span> {html.escape(record['coverage'])}</p>"
        "</article>"
        for record in current_records
    ) or "<p class='empty'>No production or fixture records.</p>"
    nav = "".join(f"<a href='#group-{level}'>{level}</a> " for level in ("stakeholder", "system", "component", "with-execution", "without-execution"))
    groups = ""
    for level in ("stakeholder", "system", "component"):
        links = " ".join(f"<a href='#{req['id'].lower()}'>{req['id']}</a>" for req in req_doc["requirements"] if req["level"] == level)
        groups += f"<h3 id='group-{level}'>Group: {level}</h3><p>{links}</p>"
    chains = ""
    for req in req_doc["requirements"]:
        linked = [record for record in current_records if req["id"] in record["requirement_ids"] and record["execution"]["result"] != "not_run"]
        source_text = "; ".join(f"<a href='https://github.com/ZhangChi0727/UAV-FMS-portfolio/blob/{sources[sid]['revision']}/{sources[sid]['path']}'>{sid} → {sources[sid]['path']}</a> ({html.escape(sources[sid]['locator'])})" for sid in req["source_ids"])
        model_url = f"https://github.com/ZhangChi0727/UAV-FMS-portfolio/blob/{ledger['baseline']['closeout_commit']}/systems_engineering/models/b0_system.sysml"
        model_text = ", ".join(f"<a href='{model_url}'>{html.escape(value)}</a>" for value in req["model_element_ids"])
        verification_url = f"https://github.com/ZhangChi0727/UAV-FMS-portfolio/blob/{ledger['baseline']['closeout_commit']}/{ledger['baseline']['verification_path']}"
        verification_text = "; ".join(f"<a href='{verification_url}'>{html.escape(sid)}</a> ({html.escape(specs[sid]['method'])}; {html.escape(specs[sid]['responsible'])}; {html.escape(specs[sid]['execution_status'])})" for sid in req["verification_ids"])
        execution_parts = []
        for record in linked:
            implementation = ", ".join(f"<a href='https://github.com/ZhangChi0727/UAV-FMS-portfolio/blob/{record['implementation']['commit']}/{path}'>{html.escape(path)}</a>" for path in record["implementation"]["paths"])
            review = html.escape(record["review"]["status"])
            if record["review"]["source"]:
                review = f"<a href='{html.escape(record['review']['source'], quote=True)}'>{review}</a>"
            execution_parts.append(f"{html.escape(record['id'])}: {html.escape(record['execution']['result'])}, <a href='{html.escape(record['evidence']['uri'], quote=True)}'>{html.escape(record['evidence']['availability'])}</a>, SHA-256 {html.escape(record['evidence']['sha256'])}, implementation {implementation}, review {review}, coverage {html.escape(record['coverage'])}")
        execution_text = "; ".join(execution_parts) or "Not executed; evidence and review are pending."
        chains += f"<article class='requirement' id='{req['id'].lower()}'><h3>{html.escape(req['id'])} — {html.escape(req['title'])}</h3><p><span>Source</span> {source_text}</p><p><span>Requirement</span> {html.escape(req['statement'])}</p><p><span>Rationale</span> {html.escape(req['rationale'])}</p><p><span>Model / responsibility</span> {model_text}; responsible {html.escape(', '.join(req['responsible_components']))}</p><p><span>Verification</span> {verification_text}</p><p><span>Execution / evidence / review</span> {execution_text}</p><p><span>Gap</span> {html.escape(_requirement_gap(req, current_records))}</p></article>"
    with_ids = [req["id"] for req in req_doc["requirements"] if any(req["id"] in record["requirement_ids"] and record["execution"]["result"] != "not_run" for record in current_records)]
    without_ids = [req["id"] for req in req_doc["requirements"] if req["id"] not in with_ids]
    with_links = " ".join(f"<a href='#{value.lower()}'>{value}</a>" for value in with_ids) or "None"
    without_links = " ".join(f"<a href='#{value.lower()}'>{value}</a>" for value in without_ids) or "None"
    groups += f"<h3 id='group-with-execution'>Group: with execution</h3><p>{with_links}</p><h3 id='group-without-execution'>Group: without execution</h3><p>{without_links}</p>"
    current_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    body = f"<h1 id='top'>B0 G1.5-C verification traceability status</h1><p class='boundary'>Controlled current view. Frozen verification specifications remain planned/not_run and are not rewritten.</p><h2 id='conclusion'>First-screen conclusion</h2>{metric_html}<h2 id='versions'>Version boundary</h2><p>Frozen base <code>{ledger['baseline']['frozen_asset_commit']}</code>; controlled target <code>{ledger['baseline']['closeout_commit']}</code>; evaluated committed HEAD <code>{current_head}</code>.</p><h2 id='records'>Execution records</h2>{records}<h2 id='requirements'>Requirement index</h2><nav>{nav}</nav>{groups}<h2 id='chains'>Requirement chains</h2>{chains}<h2 id='filtering'>Reading and filtering</h2><p>Filter ledger fields execution.level, execution.result, evidence.availability, applicability.status, review.status and coverage. Fixtures are prohibited from the production ledger.</p><h2 id='chain'>Evidence chain</h2><p>The current record links frozen specification IDs to G1 implementation paths, an Actions artifact, SHA-256 identity, relevant-file applicability hashes and explicit pending review. Artifact expiry cannot silently preserve an auditable-pass claim.</p><h2 id='external'>External research-suite interface</h2><p>A future external suite must provide the same version, criterion, command, evidence hash/URI, applicability and review fields. G1.5-C does not run or write to external suites.</p>"
    return f"<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>B0 G1.5-C traceability</title><style>:root{{--bg:#0d1117;--panel:#161b22;--text:#c9d1d9;--muted:#8b949e;--accent:#7ee787}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:16px/1.55 ui-monospace,SFMono-Regular,Consolas,Liberation Mono,monospace}}main{{max-width:1100px;margin:auto;padding:32px}}h1,h2{{color:var(--accent)}}h1{{font-size:clamp(1.5rem,4vw,2.4rem);line-height:1.2}}h2{{border-bottom:1px solid #30363d;padding-bottom:.4rem;margin-top:2rem}}h3{{font-size:1rem;margin:.1rem 0 .35rem;color:var(--accent)}}p{{overflow-wrap:anywhere;margin:.35rem 0}}.boundary{{color:var(--muted);margin-top:1rem}}.card,.record,.requirement{{background:var(--panel);border-left:3px solid var(--accent);padding:.7rem 1rem;margin:.6rem 0}}.record span,.requirement span{{color:var(--accent)}}.empty{{color:var(--muted)}}a{{color:#58a6ff}}nav{{display:flex;flex-wrap:wrap;gap:.8rem}}code{{font-family:inherit}}@media(max-width:700px){{main{{padding:18px}}}}</style><main>{body}</main></html>\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--check-report", action="store_true")
    parser.add_argument("--write-report", action="store_true")
    parser.add_argument("--json", action="store_true", dest="machine_json")
    parser.add_argument("--html-output", type=Path)
    parser.add_argument("--evidence-cache", type=Path)
    args = parser.parse_args()
    try:
        summary = validate_ledger(args.repo, evidence_cache=args.evidence_cache)
        report = render_markdown(args.repo, evidence_cache=args.evidence_cache).rstrip() + "\n"
        report_path = args.repo / "systems_engineering/reports/b0/g15c_verification_status.md"
        if args.write_report:
            report_path.write_text(report, encoding="utf-8")
        if args.check_report:
            _need(report_path.is_file() and report_path.read_text(encoding="utf-8") == report, "generated G1.5-C report is stale")
        if args.html_output:
            args.html_output.parent.mkdir(parents=True, exist_ok=True)
            args.html_output.write_text(render_html(args.repo, evidence_cache=args.evidence_cache), encoding="utf-8")
        print(json.dumps({"ok": True, **summary}, sort_keys=True) if args.machine_json else f"G1.5-C traceability check passed: {summary}")
    except TraceabilityError as exc:
        if args.machine_json:
            print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        else:
            print(f"G1.5-C traceability check failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
