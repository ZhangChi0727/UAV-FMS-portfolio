"""Fail-closed B0 G1.5-C execution-evidence validation and reporting."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import html
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Mapping

from jsonschema import Draft202012Validator


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


def validate_ledger(
    repo: Path,
    ledger_data: Mapping[str, Any] | None = None,
    *,
    check_files: bool = True,
    check_frozen: bool = True,
) -> dict[str, Any]:
    """Validate schema, trace links, evidence truthfulness and controlled drift."""

    ledger_path = repo / "systems_engineering/verification/b0_execution_evidence.json"
    schema = _load(repo / "systems_engineering/verification/b0_execution_evidence.schema.json")
    ledger = ledger_data or _load(ledger_path)
    errors = sorted(Draft202012Validator(schema).iter_errors(ledger), key=lambda error: list(error.absolute_path))
    if errors:
        where = "/".join(str(part) for part in errors[0].absolute_path) or "<root>"
        raise TraceabilityError(f"evidence schema error at {where}: {errors[0].message}")

    req_doc = _load(_inside(repo, ledger["baseline"]["requirements_path"], "requirements path"))
    ver_doc = _load(_inside(repo, ledger["baseline"]["verification_path"], "verification path"))
    requirements = _unique(req_doc["requirements"], "requirement ID")
    specifications = _unique(ver_doc["specifications"], "verification ID")
    records = _unique(ledger["records"], "execution record")
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

    superseded: set[str] = set()
    for record_id, record in records.items():
        if record["supersedes"] is not None:
            _need(record["supersedes"] in records, f"unknown superseded record: {record_id}")
            _need(record["supersedes"] != record_id, f"record supersedes itself: {record_id}")
            superseded.add(record["supersedes"])
        _need(all(value in specifications for value in record["verification_spec_ids"]), f"unknown verification in {record_id}")
        _need(all(value in requirements for value in record["requirement_ids"]), f"unknown requirement in {record_id}")
        _need(all(value in model_ids for value in record["model_ids"]), f"unknown model identity in {record_id}")
        linked_requirements = {req for spec in record["verification_spec_ids"] for req in specifications[spec]["requirement_ids"]}
        _need(set(record["requirement_ids"]) <= linked_requirements, f"record requirement/specification mismatch: {record_id}")

        execution, evidence = record["execution"], record["evidence"]
        applicability, review = record["applicability"], record["review"]
        if execution["result"] == "not_run":
            _need(execution["exit_code"] is None and evidence["availability"] == "none", f"not_run record contains execution evidence: {record_id}")
        if execution["result"] == "pass":
            _need(execution["exit_code"] == 0, f"pass has non-zero/unknown exit code: {record_id}")
            _need(evidence["availability"] in {"local_only", "remote_verified"}, f"pass lacks available raw evidence: {record_id}")
            _need(evidence["sha256"] is not None and evidence["uri"], f"pass lacks evidence hash/URI: {record_id}")
            _need(execution["tests"]["failed"] == 0, f"pass records failed tests: {record_id}")
            _need(execution["tests"]["skipped"] == 0 and execution["tests"]["xfailed"] == 0, f"pass relies on skip/xfail: {record_id}")
        if review["status"] == "accepted":
            _need(review["reviewer"] and review["source"], f"accepted record lacks review provenance: {record_id}")
        if applicability["status"] in {"applicable_exact", "applicable_by_analysis"}:
            _need(applicability["relevant_files"], f"applicable record lacks relevant-file basis: {record_id}")
        if record["coverage"] == "complete":
            locators = " ".join(execution["criterion_locators"])
            _need(all(spec_id in locators for spec_id in record["verification_spec_ids"]), f"complete record lacks a criterion locator for every specification: {record_id}")
        if check_files:
            for value in record["implementation"]["paths"]:
                _need(_inside(repo, value, "implementation path").is_file(), f"missing implementation path: {record_id} -> {value}")
            for item in applicability["relevant_files"]:
                path = _inside(repo, item["path"], "applicability path")
                _need(path.is_file(), f"missing applicability file: {record_id} -> {item['path']}")
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                _need(digest == item["sha256"], f"stale applicability hash: {record_id} -> {item['path']}")

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
    accepted_records = [record for record in production if _counts_as_accepted(record)]
    satisfied_requirements = {
        req_id
        for req_id, req in requirements.items()
        if req["verification_ids"] and all(any(_counts_as_accepted(record) and spec_id in record["verification_spec_ids"] and req_id in record["requirement_ids"] for record in production) for spec_id in req["verification_ids"])
    }
    return {
        "requirements": len(requirements), "model_elements": len(model_ids), "verifications": len(specifications),
        "production_records": len(production), "executed_specifications": len(executed_specs),
        "accepted_evidence_records": len(accepted_records), "satisfied_requirements": len(satisfied_requirements),
        "result_counts": dict(Counter(record["execution"]["result"] for record in production)),
    }


def _counts_as_accepted(record: Mapping[str, Any]) -> bool:
    return bool(record["execution"]["result"] == "pass" and record["evidence"]["availability"] in {"local_only", "remote_verified"} and record["applicability"]["status"] in {"applicable_exact", "applicable_by_analysis"} and record["review"]["status"] == "accepted" and record["coverage"] == "complete")


def render_markdown(repo: Path, ledger_data: Mapping[str, Any] | None = None) -> str:
    ledger = ledger_data or _load(repo / "systems_engineering/verification/b0_execution_evidence.json")
    summary = validate_ledger(repo, ledger)
    rows = []
    for record in ledger["records"]:
        rows.append(f"| `{record['id']}` | {record['execution']['level']} | {record['execution']['result']} | {record['evidence']['availability']} | {record['applicability']['status']} | {record['review']['status']} | {record['coverage']} |")
    return "\n".join([
        "# B0 G1.5-C verification traceability status", "", "> Controlled current view; frozen verification specifications remain planned/not_run and are not rewritten.", "",
        "## First-screen conclusion", "",
        f"- Design traceability: **{summary['requirements']}/30 requirements**, **{summary['model_elements']} model identities**, **{summary['verifications']}/29 planned specifications** are structurally linked.",
        f"- Execution: **{summary['executed_specifications']}/29 specifications** have at least one current production execution record.",
        f"- Accepted evidence: **{summary['accepted_evidence_records']}/{summary['production_records']} production records**.",
        f"- Requirement satisfaction: **{summary['satisfied_requirements']}/30**. A requirement counts only when every required specification has complete, applicable, available and accepted pass evidence.",
        "- Current gap: the retained G1 component artifact is real and hash-bound, but deliberately remains partial and pending independent review; it therefore proves no requirement satisfied.", "",
        "## Execution records", "", "| Record | Level | Result | Evidence | Applicability | Review | Coverage |", "|---|---|---|---|---|---|---|", *rows, "",
        "## Reading and filtering", "", "Use the ledger fields `execution.level`, `execution.result`, `evidence.availability`, `applicability.status`, `review.status`, and `coverage`. Module and integration records are distinct; fixtures are excluded from production totals.", "",
        "## Evidence chain", "", "The current record links the frozen specification IDs to G1 implementation paths, an Actions run artifact, SHA-256 content identity, relevant-file applicability hashes, and an explicit pending review. Artifact expiry changes evidence availability and must not silently preserve an auditable-pass claim.", "",
        "## External research-suite interface", "", "A future external suite may contribute a record only by supplying the same version, criterion, command, raw-evidence hash/URI, applicability, and review fields. This repository does not run or write to an external suite in G1.5-C.", "",
    ])


def render_html(repo: Path) -> str:
    ledger = _load(repo / "systems_engineering/verification/b0_execution_evidence.json")
    summary = validate_ledger(repo, ledger)
    metrics = [
        ("Design traceability", f"{summary['requirements']}/30 requirements; {summary['model_elements']} model identities; {summary['verifications']}/29 planned specifications structurally linked."),
        ("Execution", f"{summary['executed_specifications']}/29 specifications have a current production execution record."),
        ("Accepted evidence", f"{summary['accepted_evidence_records']}/{summary['production_records']} production records."),
        ("Requirement satisfaction", f"{summary['satisfied_requirements']}/30; every required specification needs complete, applicable, available and accepted pass evidence."),
        ("Current gap", "The retained G1 component artifact is real and hash-bound, but remains partial and pending independent review; it proves no requirement satisfied."),
    ]
    metric_html = "".join(f"<section class='card'><h3>{html.escape(label)}</h3><p>{html.escape(value)}</p></section>" for label, value in metrics)
    records = "".join(
        "<article class='record'>"
        f"<h3>{html.escape(record['id'])}</h3>"
        f"<p><span>level</span> {html.escape(record['execution']['level'])} · <span>result</span> {html.escape(record['execution']['result'])} · <span>evidence</span> {html.escape(record['evidence']['availability'])}</p>"
        f"<p><span>applicability</span> {html.escape(record['applicability']['status'])} · <span>review</span> {html.escape(record['review']['status'])} · <span>coverage</span> {html.escape(record['coverage'])}</p>"
        "</article>"
        for record in ledger["records"]
    ) or "<p class='empty'>No production or fixture records.</p>"
    body = f"<h1 id='top'>B0 G1.5-C verification traceability status</h1><p class='boundary'>Controlled current view. Frozen verification specifications remain planned/not_run and are not rewritten.</p><h2 id='conclusion'>First-screen conclusion</h2>{metric_html}<h2 id='records'>Execution records</h2>{records}<h2 id='filtering'>Reading and filtering</h2><p>Filter ledger fields execution.level, execution.result, evidence.availability, applicability.status, review.status and coverage. Module and integration records remain distinct; fixtures are excluded from production totals.</p><h2 id='chain'>Evidence chain</h2><p>The current record links frozen specification IDs to G1 implementation paths, an Actions artifact, SHA-256 identity, relevant-file applicability hashes and explicit pending review. Artifact expiry cannot silently preserve an auditable-pass claim.</p><h2 id='external'>External research-suite interface</h2><p>A future external suite must provide the same version, criterion, command, evidence hash/URI, applicability and review fields. G1.5-C does not run or write to external suites.</p>"
    return f"<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>B0 G1.5-C traceability</title><style>:root{{--bg:#0d1117;--panel:#161b22;--text:#c9d1d9;--muted:#8b949e;--accent:#7ee787}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:16px/1.55 ui-monospace,SFMono-Regular,Consolas,Liberation Mono,monospace}}main{{max-width:1100px;margin:auto;padding:32px}}h1,h2{{color:var(--accent)}}h1{{font-size:clamp(1.5rem,4vw,2.4rem);line-height:1.2}}h2{{border-bottom:1px solid #30363d;padding-bottom:.4rem;margin-top:2rem}}h3{{font-size:1rem;margin:.1rem 0 .35rem;color:var(--accent)}}p{{overflow-wrap:anywhere;margin:.35rem 0}}.boundary{{color:var(--muted);margin-top:1rem}}.card,.record{{background:var(--panel);border-left:3px solid var(--accent);padding:.7rem 1rem;margin:.6rem 0}}.record span{{color:var(--accent)}}.empty{{color:var(--muted)}}a{{color:#58a6ff}}@media(max-width:700px){{main{{padding:18px}}}}</style><main>{body}</main></html>\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--check-report", action="store_true")
    parser.add_argument("--write-report", action="store_true")
    parser.add_argument("--json", action="store_true", dest="machine_json")
    parser.add_argument("--html-output", type=Path)
    args = parser.parse_args()
    try:
        summary = validate_ledger(args.repo)
        report = render_markdown(args.repo).rstrip() + "\n"
        report_path = args.repo / "systems_engineering/reports/b0/g15c_verification_status.md"
        if args.write_report:
            report_path.write_text(report, encoding="utf-8")
        if args.check_report:
            _need(report_path.is_file() and report_path.read_text(encoding="utf-8") == report, "generated G1.5-C report is stale")
        if args.html_output:
            args.html_output.parent.mkdir(parents=True, exist_ok=True)
            args.html_output.write_text(render_html(args.repo), encoding="utf-8")
        print(json.dumps({"ok": True, **summary}, sort_keys=True) if args.machine_json else f"G1.5-C traceability check passed: {summary}")
    except TraceabilityError as exc:
        if args.machine_json:
            print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        else:
            print(f"G1.5-C traceability check failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
