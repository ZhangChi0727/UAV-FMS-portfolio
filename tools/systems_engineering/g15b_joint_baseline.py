"""Validation and deterministic projections for the B0 G1.5-B D2 candidate."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from jsonschema import Draft202012Validator


class BaselineValidationError(ValueError):
    """Raised when the joint baseline is ambiguous, incomplete, or untruthful."""


REQ_ID = re.compile(r"B0-REQ-(\d{4})$")
MODEL_ID = re.compile(r"<'(B0-MODEL-[A-Z0-9-]+)'>")
FORBIDDEN_RESULT = {"pass", "passed", "complete", "completed", "satisfied"}


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise BaselineValidationError(message)


def _load(path: Path) -> Any:
    _need(path.is_file(), f"missing required asset: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BaselineValidationError(f"invalid JSON in {path}: {exc}") from exc


def _unique(items: list[Mapping[str, Any]], field: str, label: str) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for item in items:
        identity = item[field]
        _need(identity not in result, f"duplicate {label}: {identity}")
        result[identity] = item
    return result


def _resolve_locator(repo: Path, source: Mapping[str, Any]) -> None:
    path = (repo / source["path"]).resolve()
    try:
        path.relative_to(repo.resolve())
    except ValueError as exc:
        raise BaselineValidationError(f"source escapes repository: {source['id']}") from exc
    _need(path.is_file(), f"source path is missing: {source['id']} -> {source['path']}")
    locator = source["locator"]
    _need(isinstance(locator, str) and locator.strip(), f"source locator is empty: {source['id']}")
    revision = source["revision"]
    _need(re.fullmatch(r"[0-9a-f]{40}", revision) is not None, f"invalid source revision: {source['id']}")


def _validate_parents(requirements: Mapping[str, Mapping[str, Any]]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(identity: str) -> None:
        _need(identity not in visiting, f"requirement parent cycle at {identity}")
        if identity in visited:
            return
        visiting.add(identity)
        parent = requirements[identity]["parent_id"]
        if parent is not None:
            _need(parent in requirements, f"unknown parent for {identity}: {parent}")
            visit(parent)
        visiting.remove(identity)
        visited.add(identity)

    for identity in requirements:
        visit(identity)


def load_sysml(repo: Path, model_path: Path | None = None) -> tuple[str, set[str]]:
    """Parse/analyse using fixed sysmlpy and return source plus declared stable IDs."""

    path = model_path or repo / "systems_engineering/models/b0_system.sysml"
    _need(path.is_file(), f"missing SysML source: {path}")
    try:
        from sysmlpy import analyze, load_grammar, loads
    except ModuleNotFoundError as exc:
        raise BaselineValidationError("sysmlpy==0.33.2 is required") from exc
    source = path.read_text(encoding="utf-8")
    try:
        load_grammar(source)
        issues = analyze(loads(source))
    except Exception as exc:
        raise BaselineValidationError(f"SysML parse/analyse failed: {exc}") from exc
    errors = [issue for issue in issues if str(getattr(issue, "severity", "")).lower() == "error"]
    _need(not errors, f"SysML semantic error: {errors[0] if errors else ''}")
    identities = set(MODEL_ID.findall(source))
    _need(len(identities) == len(MODEL_ID.findall(source)), "duplicate SysML stable identity")
    return source, identities


def validate_baseline(
    repo: Path,
    requirements_data: Mapping[str, Any] | None = None,
    registry_data: Mapping[str, Any] | None = None,
    verification_data: Mapping[str, Any] | None = None,
    model_path: Path | None = None,
    check_manual_review: bool = True,
    check_projections: bool = True,
) -> dict[str, int]:
    req_path = repo / "systems_engineering/requirements/b0_requirements.json"
    registry_path = repo / "systems_engineering/requirements/b0_id_registry.json"
    verification_path = repo / "systems_engineering/verification/b0_verification_specifications.json"
    schema = _load(repo / "systems_engineering/requirements/b0_requirements.schema.json")
    req_doc = requirements_data or _load(req_path)
    registry = registry_data or _load(registry_path)
    ver_doc = verification_data or _load(verification_path)

    errors = sorted(Draft202012Validator(schema).iter_errors(req_doc), key=lambda error: list(error.path))
    if errors:
        where = "/".join(str(part) for part in errors[0].absolute_path) or "<root>"
        raise BaselineValidationError(f"requirement schema error at {where}: {errors[0].message}")

    sources = _unique(req_doc["sources"], "id", "source ID")
    requirements = _unique(req_doc["requirements"], "id", "requirement ID")
    specifications = _unique(ver_doc["specifications"], "id", "verification ID")
    registered = _unique(registry["allocations"], "id", "registry allocation")
    _need(set(requirements) == set(registered), "registry and requirement identity sets differ")
    retired_ids = {
        item if isinstance(item, str) else item["id"]
        for item in registry.get("retired", [])
    }
    _need(not (set(registered) & retired_ids), "retired requirement identity was reused")
    all_ids = set(registered) | retired_ids
    _need(all(REQ_ID.fullmatch(identity) for identity in all_ids), "registry contains an invalid identity")
    ordinals = sorted(int(REQ_ID.fullmatch(identity).group(1)) for identity in all_ids)
    _need(registry["next_ordinal"] > max(ordinals), "registry next_ordinal would reuse an identity")
    _need(len(ordinals) == len(set(ordinals)), "requirement ordinal reused")
    for source in sources.values():
        _resolve_locator(repo, source)
    _validate_parents(requirements)
    supersedes_pairs = {
        (item["new_id"], item["prior_id"])
        for item in registry.get("supersedes", [])
    }
    declared_pairs = {
        (identity, req["supersedes"])
        for identity, req in requirements.items()
        if req["supersedes"] is not None
    }
    _need(declared_pairs == supersedes_pairs, "requirement supersedes chain and registry differ")
    _need(all(new in requirements and old in all_ids and new != old for new, old in supersedes_pairs), "invalid supersedes chain")

    model_source, model_ids = load_sysml(repo, model_path)
    required_model_ids = {value for req in requirements.values() for value in req["model_element_ids"] + req["responsible_components"]}
    _need(required_model_ids <= model_ids, f"unknown model IDs: {sorted(required_model_ids - model_ids)}")
    _need("flow PlantTruth from plant to evaluator;" in model_source, "truth-to-evaluator flow is missing")
    _need("flow PlantTruth from plant to estimator;" not in model_source, "truth leaks into estimator")
    _need("flow PlantTruth from plant to controller;" not in model_source, "truth leaks into controller")
    for token in ("requested", "limitedTarget", "saturationStatus", "timestamp"):
        _need(re.search(rf"\bitem {token};", model_source) is not None, f"paired torque field missing: {token}")
    _need("out item torqueCommand : TorqueCommand;" in model_source, "controller torque output missing")
    _need("in item torqueCommand : TorqueCommand;" in model_source, "actuator torque input missing")
    _need("out item actuatorFeedback : ActuatorFeedback;" in model_source, "actuator feedback output missing")
    _need("in item actuatorFeedback : ActuatorFeedback;" in model_source, "controller feedback input missing")
    _need("expose B0System;" in model_source, "required B0 system view exposure missing")

    _need(ver_doc["baseline_status"] == "candidate_pending_d2", "verification baseline status is not candidate")
    for identity, req in requirements.items():
        _need(req["status"] == "candidate_pending_d2", f"non-candidate requirement status: {identity}")
        _need(all(source_id in sources for source_id in req["source_ids"]), f"unknown source on {identity}")
        _need(req["verification_ids"], f"requirement has no verification: {identity}")
        _need(all(value in specifications for value in req["verification_ids"]), f"unknown verification on {identity}")
    for identity, spec in specifications.items():
        _need(spec["requirement_ids"], f"verification has no requirement: {identity}")
        _need(all(value in requirements for value in spec["requirement_ids"]), f"verification has unknown requirement: {identity}")
        _need(spec["oracle"].strip() and spec["decision_rule"].strip(), f"verification lacks oracle/decision: {identity}")
        _need(spec["responsible"].strip(), f"verification lacks responsible owner: {identity}")
        _need(spec["execution_status"] == "not_run" and spec["result"] is None, f"verification claims execution: {identity}")
        _need(str(spec["execution_status"]).lower() not in FORBIDDEN_RESULT, f"forbidden result claim: {identity}")
        for req_id in spec["requirement_ids"]:
            _need(identity in requirements[req_id]["verification_ids"], f"verification reverse link missing: {identity} -> {req_id}")
    for req_id, req in requirements.items():
        for spec_id in req["verification_ids"]:
            _need(req_id in specifications[spec_id]["requirement_ids"], f"requirement reverse link missing: {req_id} -> {spec_id}")

    if check_manual_review:
        review = _load(repo / "systems_engineering/models/b0_model_manual_review.json")
        digest = hashlib.sha256(model_source.encode("utf-8")).hexdigest()
        _need(review["model_sha256"] == digest, "manual expose review is stale")
        _need(review["tool_version"] == "sysmlpy==0.33.2", "manual review tool version drifted")
        _need(review["exposed_element_id"] == "B0-MODEL-SYSTEM", "manual review exposes wrong element")
        _need(review["decision"] == "candidate_review_pass", "manual expose review is not complete")

    if check_projections:
        generated_root = repo / "systems_engineering/requirements/generated"
        expected_outputs = {
            generated_root / "b0_requirements.md": render_markdown(req_doc, ver_doc),
            generated_root / "b0_requirements.sdoc": render_strictdoc(req_doc),
        }
        for path, content in expected_outputs.items():
            _need(path.is_file(), f"generated projection is missing: {path}")
            _need(path.read_text(encoding="utf-8") == content.rstrip() + "\n", f"generated projection drift: {path}")

    return {"requirements": len(requirements), "model_elements": len(model_ids), "verifications": len(specifications)}


def render_markdown(req_doc: Mapping[str, Any], ver_doc: Mapping[str, Any]) -> str:
    specs = {item["id"]: item for item in ver_doc["specifications"]}
    lines = ["# B0 joint requirement baseline", "", "> Candidate pending D2; no execution result is claimed.", ""]
    for req in req_doc["requirements"]:
        lines += [f"## {req['id']} — {req['title']}", "", req["statement"], "", f"**Acceptance:** {req['acceptance_condition']}", "", "**Verification:** " + ", ".join(req["verification_ids"]), ""]
        for spec_id in req["verification_ids"]:
            lines += [f"- `{spec_id}`: {specs[spec_id]['method']}; status `not_run`."]
        lines.append("")
    return "\n".join(lines)


def render_strictdoc(req_doc: Mapping[str, Any]) -> str:
    lines = [
        "[DOCUMENT]",
        "TITLE: B0 Joint Requirement Baseline",
        "UID: B0-JOINT-REQUIREMENT-BASELINE",
        "",
        "[GRAMMAR]",
        "ELEMENTS:",
        "- TAG: REQUIREMENT",
        "  PROPERTIES:",
        "    IS_COMPOSITE: False",
        "  FIELDS:",
        "  - TITLE: UID",
        "    TYPE: String",
        "    REQUIRED: True",
        "  - TITLE: TITLE",
        "    TYPE: String",
        "    REQUIRED: True",
        "  - TITLE: STATUS",
        "    TYPE: String",
        "    REQUIRED: True",
        "  - TITLE: STATEMENT",
        "    TYPE: String",
        "    REQUIRED: True",
        "  - TITLE: RATIONALE",
        "    TYPE: String",
        "    REQUIRED: True",
        "  - TITLE: ACCEPTANCE",
        "    TYPE: String",
        "    REQUIRED: True",
        "  - TITLE: SOURCE",
        "    TYPE: String",
        "    REQUIRED: True",
        "  - TITLE: MODEL",
        "    TYPE: String",
        "    REQUIRED: True",
        "  - TITLE: VERIFICATION",
        "    TYPE: String",
        "    REQUIRED: True",
        "  RELATIONS:",
        "  - TYPE: Parent",
        "",
    ]
    for req in req_doc["requirements"]:
        lines += [
            "[REQUIREMENT]",
            f"UID: {req['id']}",
            f"TITLE: {req['title']}",
            f"STATUS: {req['status']}",
            "STATEMENT: >>>",
            req["statement"],
            "<<<",
            "RATIONALE: >>>",
            req["rationale"],
            "<<<",
            "ACCEPTANCE: >>>",
            req["acceptance_condition"],
            "<<<",
            "SOURCE: " + ", ".join(req["source_ids"]),
            "MODEL: " + ", ".join(req["model_element_ids"]),
            "VERIFICATION: " + ", ".join(req["verification_ids"]) + " (planned/not_run)",
        ]
        if req["parent_id"] is not None:
            lines += ["RELATIONS:", "- TYPE: Parent", f"  VALUE: {req['parent_id']}"]
        lines.append("")
    return "\n".join(lines)
