"""Shared validation for the non-authoritative G1.5-B structured pilot.

The module deliberately consumes the AST returned by the fixed ``sysmlpy``
parser.  It never uses a regular expression to parse the SysML source.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

from jsonschema import Draft202012Validator


class PilotError(ValueError):
    """Raised when the bounded phase-one pilot cannot support review."""


PILOT_ROOT = Path(__file__).resolve().parent
CONTRACT_PATH = PILOT_ROOT / "contract" / "pilot_structure.json"
SCHEMA_PATH = PILOT_ROOT / "contract" / "pilot_structure.schema.json"
MODEL_PATH = PILOT_ROOT / "model" / "b0_truth_control_slice.sysml"

EXPECTED_KEYS = {
    "PILOT-ONLY-NEED-01",
    "PILOT-ONLY-INTERFACE-02",
    "PILOT-ONLY-ACCEPTANCE-03",
    "PILOT-ONLY-LEGACY-04",
    "PILOT-ONLY-G2-05",
}
EXPECTED_PARENTS = {
    "PILOT-ONLY-INTERFACE-02": "PILOT-ONLY-NEED-01",
    "PILOT-ONLY-ACCEPTANCE-03": "PILOT-ONLY-NEED-01",
    "PILOT-ONLY-LEGACY-04": "PILOT-ONLY-NEED-01",
    "PILOT-ONLY-G2-05": "PILOT-ONLY-INTERFACE-02",
}
EXPECTED_LEGACY_APPROVAL_LOCATOR = "systems_engineering/reports/b0/g0_approval_decision.md#决定"
APPROVED_LEGACY_DISPOSITIONS = {
    "CTL-REQ-001": "not_applicable",
    "CTL-REQ-002": "not_applicable",
}
PILOT_KEY = re.compile(r"PILOT-ONLY-[A-Z0-9-]+$")

SYSML_NODE_KINDS = {
    "ItemDefinition": "item_definition",
    "PartDefinition": "part_definition",
    "InterfaceDefinition": "interface_definition",
    "RequirementDefinition": "requirement_definition",
    "VerificationDefinition": "verification_definition",
    "VerificationCaseDefinition": "verification_definition",
}

EXPECTED_FLOWS = {
    (
        "PILOT-MODEL-COMMAND-SOURCE-01",
        "command",
        "PILOT-MODEL-CONTROLLER-01",
        "command",
    ),
    (
        "PILOT-MODEL-PLANT-01",
        "truth",
        "PILOT-MODEL-IMU-01",
        "truth",
    ),
    (
        "PILOT-MODEL-IMU-01",
        "sample",
        "PILOT-MODEL-ESTIMATOR-01",
        "sample",
    ),
    (
        "PILOT-MODEL-ESTIMATOR-01",
        "estimate",
        "PILOT-MODEL-CONTROLLER-01",
        "estimate",
    ),
    (
        "PILOT-MODEL-CONTROLLER-01",
        "paired_command",
        "PILOT-MODEL-ACTUATOR-01",
        "paired_command",
    ),
    (
        "PILOT-MODEL-ACTUATOR-01",
        "feedback",
        "PILOT-MODEL-CONTROLLER-01",
        "feedback",
    ),
    (
        "PILOT-MODEL-PLANT-01",
        "truth",
        "PILOT-MODEL-EVALUATOR-01",
        "truth",
    ),
}

REQUIRED_MODEL_LINKS = {
    ("PILOT-ONLY-NEED-01", "PILOT-MODEL-B0-BOUNDARY-01"),
    ("PILOT-ONLY-INTERFACE-02", "PILOT-MODEL-IF-TRUTH-EVALUATOR-01"),
    ("PILOT-ONLY-INTERFACE-02", "PILOT-MODEL-CONTROLLER-01"),
    ("PILOT-ONLY-ACCEPTANCE-03", "PILOT-MODEL-VER-BOUNDARY-01"),
    ("PILOT-ONLY-LEGACY-04", "PILOT-MODEL-B0-BOUNDARY-01"),
    ("PILOT-ONLY-G2-05", "PILOT-MODEL-CONTROLLER-01"),
    ("PILOT-ONLY-G2-05", "PILOT-MODEL-REQ-PROXY-G2-05"),
    ("PILOT-ONLY-G2-05", "PILOT-MODEL-IF-CONTROLLER-ACTUATOR-01"),
}

RELATION_ENDPOINTS = {
    "models": ("record", "model_element"),
    "allocated_to": ("record", "development_object"),
    "specified_by": ("record", "verification_provision"),
    "development_checked_by": ("development_object", "verification_provision"),
    "evidenced_by": ("verification_provision", "execution_evidence"),
}


@dataclass(frozen=True)
class ModelIndex:
    """Declared model identities and resolved flow endpoints from a real AST."""

    definitions: dict[str, str]
    flows: frozenset[tuple[str, str, str, str]]
    analysis_warnings: tuple[str, ...]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PilotError(message)


def _canonical_name(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().strip("'")


def _walk(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _walk_strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _walk_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_strings(child)


def _first_model_identity(value: Any) -> str:
    for candidate in _walk_strings(value):
        identity = _canonical_name(candidate)
        if identity.startswith("PILOT-MODEL-"):
            return identity
    return ""


def _declaration_name(value: Mapping[str, Any]) -> str:
    try:
        return _canonical_name(
            value["usage"]["declaration"]["declaration"]["identification"]["declaredName"]
        )
    except (KeyError, TypeError):
        return ""


def _definition(value: Mapping[str, Any]) -> tuple[str, str] | None:
    kind = SYSML_NODE_KINDS.get(value.get("name"))
    if not kind:
        return None
    try:
        definition = value.get("definition", value)
        name = _canonical_name(definition["declaration"]["identification"]["declaredName"])
    except (KeyError, TypeError):
        return None
    return (name, kind) if name else None


def _role_types(definition: Mapping[str, Any]) -> dict[str, str]:
    """Map local flow roles to stable part identities from parser AST nodes."""

    roles: dict[str, str] = {}
    for node in _walk(definition):
        if node.get("name") == "DefaultInterfaceEnd":
            role = _declaration_name(node)
        elif node.get("name") == "PartUsage":
            role = _declaration_name(node)
        else:
            continue
        model_identity = _first_model_identity(node)
        if role and model_identity:
            roles[role] = model_identity
    return roles


def _flow_end(relationship: Mapping[str, Any]) -> tuple[str, str]:
    try:
        flow_end = relationship["ownedRelatedElement"][0]
        role = _canonical_name(flow_end["fes"][0]["referencedFeature"]["names"][-1])
        feature = _canonical_name(
            flow_end["ffm"][0]["ownedRelatedElement"][0]["ownedRelationship"][0]
            ["redefinedFeature"]["names"][-1]
        )
    except (IndexError, KeyError, TypeError):
        return ("", "")
    return role, feature


def _flow(value: Mapping[str, Any]) -> tuple[str, str, str, str] | None:
    try:
        declaration = value["declaration"]
        source_role, source_feature = _flow_end(declaration["ownedRelationship_from"])
        target_role, target_feature = _flow_end(declaration["ownedRelationship_to"])
    except (KeyError, TypeError):
        return None
    if not all((source_role, source_feature, target_role, target_feature)):
        return None
    return source_role, source_feature, target_role, target_feature


def _collect_model_ast(ast: Mapping[str, Any]) -> tuple[dict[str, str], set[tuple[str, str, str, str]]]:
    definitions: dict[str, str] = {}
    flows: set[tuple[str, str, str, str]] = set()

    def visit(value: Any, scope: str | None = None, roles: Mapping[str, str] | None = None) -> None:
        if isinstance(value, dict):
            definition = _definition(value)
            if definition is not None:
                identity, kind = definition
                _require(identity not in definitions, f"duplicate SysML model identity: {identity}")
                definitions[identity] = kind
                scope = identity
                roles = _role_types(value)
            if value.get("name") == "FlowConnectionUsage":
                parsed_flow = _flow(value)
                _require(parsed_flow is not None, "unable to read a SysML flow endpoint from parser AST")
                _require(scope is not None and roles is not None, "SysML flow has no enclosing definition context")
                source_role, source_feature, target_role, target_feature = parsed_flow
                source = roles.get(source_role, source_role)
                target = roles.get(target_role, target_role)
                _require(
                    source.startswith("PILOT-MODEL-") and target.startswith("PILOT-MODEL-"),
                    f"SysML flow endpoint does not resolve to a stable model identity: {source_role} -> {target_role}",
                )
                flows.add((source, source_feature, target, target_feature))
            for child in value.values():
                visit(child, scope, roles)
        elif isinstance(value, list):
            for child in value:
                visit(child, scope, roles)

    visit(ast)
    return definitions, flows


def load_sysml_model(model_path: Path = MODEL_PATH) -> ModelIndex:
    """Run the fixed parser/analyser and extract the adopted subset from its AST."""

    _require(model_path.is_file(), f"SysML model source is missing: {model_path}")
    try:
        from sysmlpy import analyze, load_grammar, loads
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised in setup failures
        raise PilotError("sysmlpy==0.33.2 must be installed in the isolated pilot environment") from exc

    source = model_path.read_text(encoding="utf-8")
    try:
        ast = load_grammar(source)
        analysis = analyze(loads(source))
    except Exception as exc:  # parser exceptions have implementation-specific types
        raise PilotError(f"sysmlpy could not parse/analyse {model_path.name}: {exc}") from exc

    errors = [issue for issue in analysis if str(getattr(issue, "severity", "")).lower() == "error"]
    if errors:
        raise PilotError(f"sysmlpy reported semantic error: {errors[0]}")
    warnings = tuple(str(issue) for issue in analysis if str(getattr(issue, "severity", "")).lower() == "warning")
    definitions, flows = _collect_model_ast(ast)
    return ModelIndex(definitions=definitions, flows=frozenset(flows), analysis_warnings=warnings)


def _anchors(text: str) -> set[str]:
    def slug(heading: str) -> str:
        value = re.sub(r"[`*_]", "", heading.strip().lower())
        value = re.sub(r"[^\w\s-]", "", value)
        return re.sub(r"\s+", "-", value)

    return {
        slug(match.group(1))
        for match in re.finditer(r"^#{1,6}\s+(.+?)\s*$", text, re.MULTILINE)
    }


def check_locator(repo_root: Path, locator: str, label: str) -> None:
    """Resolve a repository-relative Markdown anchor or JSON Pointer safely."""

    path_text, separator, fragment = locator.partition("#")
    path = (repo_root / path_text).resolve()
    try:
        path.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise PilotError(f"{label} escapes the repository: {locator}") from exc
    _require(path.is_file(), f"{label} file is missing: {locator}")
    if not separator:
        return
    _require(fragment, f"{label} fragment is empty: {locator}")
    if path.suffix == ".json":
        _require(fragment.startswith("/"), f"{label} must use a JSON Pointer: {locator}")
        try:
            value: Any = json.loads(path.read_text(encoding="utf-8"))
            for segment in fragment[1:].split("/"):
                segment = segment.replace("~1", "/").replace("~0", "~")
                if isinstance(value, list):
                    _require(
                        re.fullmatch(r"(?:0|[1-9][0-9]*)", segment) is not None,
                        f"{label} uses an invalid JSON array index: {locator}",
                    )
                    value = value[int(segment)]
                else:
                    value = value[segment]
        except PilotError:
            raise
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise PilotError(f"{label} JSON pointer is missing: {locator}") from exc
    elif path.suffix == ".md":
        _require(not fragment.startswith("/"), f"{label} must use a Markdown anchor: {locator}")
        _require(fragment in _anchors(path.read_text(encoding="utf-8")), f"{label} anchor is missing: {locator}")
    else:
        raise PilotError(f"{label} uses an unsupported fragment format: {locator}")


def load_contract(contract_path: Path = CONTRACT_PATH) -> dict[str, Any]:
    _require(contract_path.is_file(), f"structured pilot contract is missing: {contract_path}")
    try:
        return json.loads(contract_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PilotError(f"structured pilot contract is invalid JSON: {exc}") from exc


def validate_schema(contract: Mapping[str, Any], schema_path: Path = SCHEMA_PATH) -> None:
    _require(schema_path.is_file(), f"structured pilot schema is missing: {schema_path}")
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PilotError(f"structured pilot schema is invalid JSON: {exc}") from exc
    errors = sorted(Draft202012Validator(schema).iter_errors(contract), key=lambda error: list(error.path))
    if errors:
        error = errors[0]
        location = "/".join(str(part) for part in error.absolute_path) or "<root>"
        raise PilotError(f"schema validation failed at {location}: {error.message}")


def _index_unique(contract: Mapping[str, Any], key: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for item in contract[key]:
        identity = item["id"] if key != "records" else item["key"]
        _require(identity not in indexed, f"duplicate {key} identity: {identity}")
        indexed[identity] = item
    return indexed


def _validate_parent_hierarchy(records: Mapping[str, Mapping[str, Any]]) -> None:
    parents = {key: record["parent"] for key, record in records.items()}
    for child, parent in parents.items():
        if parent is None:
            _require(child == "PILOT-ONLY-NEED-01", "only the trial user need may be a root record")
        else:
            _require(parent in parents, f"unknown parent relation for {child}: {parent}")

    visited: set[str] = set()
    visiting: set[str] = set()

    def visit(key: str) -> None:
        _require(key not in visiting, f"Parent hierarchy cycle detected at {key}")
        if key in visited:
            return
        visiting.add(key)
        parent = parents[key]
        if parent is not None:
            visit(parent)
        visiting.remove(key)
        visited.add(key)

    for key in parents:
        visit(key)
    _require({key: parent for key, parent in parents.items() if parent is not None} == EXPECTED_PARENTS, "pilot Parent hierarchy drifted")


def _validate_legacy_approval(record: Mapping[str, Any], locators: Mapping[str, Mapping[str, Any]], repo_root: Path) -> None:
    approval_id = record["applicability"]["approval_ref"]
    _require(approval_id == "PILOT-SRC-G0-APPROVAL-01", "not_applicable record must use the fixed G0 approval reference")
    locator = locators[approval_id]["locator"]
    _require(locator == EXPECTED_LEGACY_APPROVAL_LOCATOR, "not_applicable record must use the approved legacy decision locator")
    check_locator(repo_root, locator, "legacy approval locator")
    approval_path = repo_root / locator.partition("#")[0]
    decision_text = approval_path.read_text(encoding="utf-8")
    for legacy_id, disposition in APPROVED_LEGACY_DISPOSITIONS.items():
        _require(
            re.search(rf"`{re.escape(legacy_id)}`[^\n]*`{re.escape(disposition)}`", decision_text) is not None,
            f"legacy approval decision lacks {legacy_id} {disposition} disposition",
        )


def _validate_record_semantics(
    records: Mapping[str, Mapping[str, Any]], locators: Mapping[str, Mapping[str, Any]], repo_root: Path
) -> None:
    _require(set(records) == EXPECTED_KEYS, "pilot key set is incomplete or unexpected")
    _validate_parent_hierarchy(records)
    for key, record in records.items():
        _require(PILOT_KEY.fullmatch(key) is not None, f"invalid temporary key: {key}")
        _require("B0-REQ-" not in key, f"formal B0 key is forbidden in phase one: {key}")
        _require(record["status"] == "pilot_only_candidate", f"invalid pilot status for {key}")
        _require(record["candidate_only"] is True, f"{key} must remain candidate_only=true")
        _require("shall" in record["statement"].lower(), f"{key} lacks a normative trial statement")
        _require(record["evidence_status"] == "planned/not_run", f"{key} must not claim execution evidence")
        for locator_id in record["source_locator_ids"]:
            _require(locator_id in locators, f"unknown source locator for {key}: {locator_id}")
            check_locator(repo_root, locators[locator_id]["locator"], f"source locator {locator_id} for {key}")
        applicability = record["applicability"]
        if record["level"] == "applicability_record":
            _require(applicability["state"] == "not_applicable", f"{key} must state not_applicable applicability")
            _validate_legacy_approval(record, locators, repo_root)
        else:
            _require(applicability["state"] == "applicable", f"{key} must state applicable applicability")


def _validate_execution_truthfulness(
    development: Mapping[str, Mapping[str, Any]],
    verification: Mapping[str, Mapping[str, Any]],
    evidence: Mapping[str, Mapping[str, Any]],
) -> None:
    for identity, object_ in development.items():
        _require(object_["lifecycle"] == "planned", f"phase-one development object must remain planned: {identity}")
        _require(
            all(object_.get(field) is None for field in ("implementation_path", "symbol", "version_ref")),
            f"planned development object claims implementation: {identity}",
        )
    for identity, provision in verification.items():
        status = provision["execution_status"]
        evidence_ids = provision["evidence_ids"]
        for evidence_id in evidence_ids:
            _require(evidence_id in evidence, f"verification provision references unknown evidence: {evidence_id}")
        _require(provision["planning_status"] == "planned", f"phase-one verification must remain planned: {identity}")
        _require(status == "not_run", f"planned verification provision falsely claims {status}: {identity}")
        _require(not evidence_ids, f"planned verification provision carries execution evidence: {identity}")
    _require(not evidence, "phase-one execution_evidence must remain empty")


def _validate_relations(
    relations: list[Mapping[str, Any]],
    indexes: Mapping[str, Mapping[str, Mapping[str, Any]]],
    locators: Mapping[str, Mapping[str, Any]],
    repo_root: Path,
) -> None:
    relation_ids: set[str] = set()
    for relation in relations:
        identity = relation["id"]
        _require(identity not in relation_ids, f"duplicate relation identity: {identity}")
        relation_ids.add(identity)
        expected_kinds = RELATION_ENDPOINTS[relation["type"]]
        _require(
            (relation["source_kind"], relation["target_kind"]) == expected_kinds,
            f"relation endpoint type is invalid for {identity}",
        )
        _require(relation["direction"] == "forward", f"relation direction is invalid for {identity}")
        _require(relation["origin"] == "project_extension", f"cross-domain relation must be a project_extension: {identity}")
        source_index = indexes[relation["source_kind"]]
        target_index = indexes[relation["target_kind"]]
        _require(relation["source_id"] in source_index, f"relation source target is unknown: {relation['source_id']}")
        _require(relation["target_id"] in target_index, f"relation target is unknown: {relation['target_id']}")
        _require(relation["source_locator_id"] in locators, f"relation source locator is unknown: {relation['source_locator_id']}")
        locator_id = relation["source_locator_id"]
        check_locator(repo_root, locators[locator_id]["locator"], f"relation source locator {locator_id} for {identity}")

    for record_id in EXPECTED_KEYS:
        _require(
            any(relation["type"] == "models" and relation["source_id"] == record_id for relation in relations),
            f"record lacks model relation: {record_id}",
        )
        _require(
            any(relation["type"] == "specified_by" and relation["source_id"] == record_id for relation in relations),
            f"record lacks verification relation: {record_id}",
        )
    actual_model_links = {
        (relation["source_id"], relation["target_id"])
        for relation in relations
        if relation["type"] == "models"
    }
    _require(
        REQUIRED_MODEL_LINKS <= actual_model_links,
        "required record-to-model relation is missing or retargeted",
    )
    _require(
        any(
            relation["type"] == "allocated_to"
            and relation["source_id"] == "PILOT-ONLY-G2-05"
            and relation["target_id"] == "PILOT-DEV-CONTROLLER-CORE-01"
            for relation in relations
        ),
        "planned controller allocation is missing",
    )
    _require(
        any(
            relation["type"] == "development_checked_by"
            and relation["source_id"] == "PILOT-DEV-CONTROLLER-CORE-01"
            and relation["target_id"] == "PILOT-VER-G2-INTERFACE-01"
            for relation in relations
        ),
        "planned controller verification relation is missing",
    )


def _validate_model(
    model: ModelIndex,
    model_elements: Mapping[str, Mapping[str, Any]],
) -> None:
    actual = {identity: kind for identity, kind in model.definitions.items() if identity.startswith("PILOT-MODEL-")}
    _require(set(actual) == set(model_elements), "SysML model identity set is incomplete or contains an uncontracted identity")
    for identity, element in model_elements.items():
        _require(actual[identity] == element["sysml_kind"], f"SysML model type mismatch for {identity}")
    missing = EXPECTED_FLOWS - set(model.flows)
    if missing:
        raise PilotError(f"required SysML flow is missing: {sorted(missing)[0]}")
    truth_consumers = {
        target
        for source, source_feature, target, _ in model.flows
        if source == "PILOT-MODEL-PLANT-01" and source_feature == "truth"
    }
    _require(
        "PILOT-MODEL-ESTIMATOR-01" not in truth_consumers
        and "PILOT-MODEL-CONTROLLER-01" not in truth_consumers,
        "live truth must not flow to estimator or controller",
    )


def validate_contract(repo_root: Path, contract: Mapping[str, Any], model: ModelIndex) -> None:
    """Validate cross-object project semantics after JSON-schema validation."""

    records = _index_unique(contract, "records")
    locators = _index_unique(contract, "source_locators")
    model_elements = _index_unique(contract, "model_elements")
    development = _index_unique(contract, "development_objects")
    verification = _index_unique(contract, "verification_provisions")
    evidence = _index_unique(contract, "execution_evidence")
    _validate_record_semantics(records, locators, repo_root)
    _validate_execution_truthfulness(development, verification, evidence)
    _validate_relations(
        contract["relations"],
        {
            "record": records,
            "model_element": model_elements,
            "development_object": development,
            "verification_provision": verification,
            "execution_evidence": evidence,
        },
        locators,
        repo_root,
    )
    _validate_model(model, model_elements)


def load_validated_pilot(
    repo_root: Path,
    *,
    contract_path: Path = CONTRACT_PATH,
    model_path: Path = MODEL_PATH,
) -> tuple[dict[str, Any], ModelIndex]:
    """Load the JSON source, validate it, then validate real SysML AST links."""

    contract = load_contract(contract_path)
    validate_schema(contract)
    model = load_sysml_model(model_path)
    validate_contract(repo_root, contract, model)
    return contract, model
