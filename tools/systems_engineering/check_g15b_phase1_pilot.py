"""Fail-closed checks for the non-authoritative G1.5-B phase-one trial."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import re
from pathlib import Path
from typing import Iterable


class PilotError(ValueError):
    """Raised when a phase-one pilot record cannot support review."""


EXPECTED_KEYS = {
    "PILOT-ONLY-NEED-01",
    "PILOT-ONLY-INTERFACE-02",
    "PILOT-ONLY-ACCEPTANCE-03",
    "PILOT-ONLY-LEGACY-04",
    "PILOT-ONLY-G2-05",
}
REQUIRED_METADATA = (
    "source locators",
    "applicability",
    "scope",
    "allocation",
    "model refs",
    "verification plan",
    "acceptance condition",
    "evidence status",
    "candidate only",
)
PILOT_KEY = re.compile(r"PILOT-ONLY-[A-Z0-9-]+$")
EXPECTED_LEGACY_APPROVAL_REF = "systems_engineering/reports/b0/g0_approval_decision.md#决定"
APPROVED_LEGACY_DISPOSITIONS = {
    "CTL-REQ-001": "not_applicable",
    "CTL-REQ-002": "not_applicable",
}


@dataclass(frozen=True)
class PilotRecord:
    """The shared review fields represented by both trial source formats."""

    key: str
    level: str
    status: str
    title: str
    statement: str
    rationale: str
    parent: str
    source_locators: str
    applicability: str
    scope: str
    allocation: str
    model_refs: str
    verification_plan: str
    acceptance_condition: str
    evidence_status: str
    candidate_only: str
    approval_ref: str


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PilotError(message)


def _normalise(value: str) -> str:
    return " ".join(value.split())


def _scalar(block: str, field: str) -> str:
    match = re.search(rf"^{re.escape(field)}:\s*(.+?)\s*$", block, re.MULTILINE)
    _require(match is not None, f"missing {field} field")
    return _normalise(match.group(1))


def _multiline(block: str, field: str, *, normalise: bool = True) -> str:
    match = re.search(
        rf"^{re.escape(field)}:\s*>>>\s*\n(?P<value>.*?)\n<<<\s*$",
        block,
        re.MULTILINE | re.DOTALL,
    )
    _require(match is not None, f"missing {field} block")
    value = match.group("value")
    return _normalise(value) if normalise else value.strip()


def _metadata(comment: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in comment.splitlines():
        if ":" not in line:
            continue
        label, value = line.split(":", 1)
        values[label.strip().lower()] = _normalise(value)
    for label in REQUIRED_METADATA:
        _require(values.get(label), f"missing required metadata: {label}")
    return values


def _parent_from_sdoc(block: str) -> str:
    match = re.search(
        r"^RELATIONS:\s*\n- TYPE: Parent\s*\n\s+VALUE:\s*(.+?)\s*$",
        block,
        re.MULTILINE,
    )
    return _normalise(match.group(1)) if match else "none"


def parse_sdoc_records(text: str) -> list[PilotRecord]:
    """Parse only the small, fixed phase-one SDoc fixture without StrictDoc APIs."""

    chunks = re.split(r"(?=^\[REQUIREMENT\]\s*$)", text, flags=re.MULTILINE)
    records: list[PilotRecord] = []
    for block in chunks[1:]:
        metadata = _metadata(_multiline(block, "COMMENT", normalise=False))
        records.append(
            PilotRecord(
                key=_scalar(block, "UID"),
                level=_scalar(block, "LEVEL"),
                status=_scalar(block, "STATUS"),
                title=_scalar(block, "TITLE"),
                statement=_multiline(block, "STATEMENT"),
                rationale=_multiline(block, "RATIONALE"),
                parent=_parent_from_sdoc(block),
                source_locators=metadata["source locators"],
                applicability=metadata["applicability"],
                scope=metadata["scope"],
                allocation=metadata["allocation"],
                model_refs=metadata["model refs"],
                verification_plan=metadata["verification plan"],
                acceptance_condition=metadata["acceptance condition"],
                evidence_status=metadata["evidence status"],
                candidate_only=metadata["candidate only"],
                approval_ref=metadata.get("approval ref", ""),
            )
        )
    _require(records, "SDoc trial contains no requirement records")
    return records


def parse_markdown_records(text: str) -> list[PilotRecord]:
    """Parse the fixed lightweight comparison template without Markdown packages."""

    headings = list(re.finditer(r"^## (PILOT-ONLY-[A-Z0-9-]+)\s*$", text, re.MULTILINE))
    records: list[PilotRecord] = []
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        block = text[heading.end() : end]
        values = {
            match.group(1).strip().lower(): _normalise(match.group(2))
            for match in re.finditer(r"^- \*\*(.+?):\*\*\s*(.+?)\s*$", block, re.MULTILINE)
        }
        for field in ("level", "status", "title", "parent", *REQUIRED_METADATA):
            _require(values.get(field), f"{heading.group(1)} is missing required field: {field}")
        statement = re.search(
            r"^### Statement\s*\n\s*(?P<value>.*?)(?=^### Rationale\s*$|\Z)",
            block,
            re.MULTILINE | re.DOTALL,
        )
        rationale = re.search(
            r"^### Rationale\s*\n\s*(?P<value>.*?)\s*\Z",
            block,
            re.MULTILINE | re.DOTALL,
        )
        _require(statement is not None, f"{heading.group(1)} is missing Statement")
        _require(rationale is not None, f"{heading.group(1)} is missing Rationale")
        records.append(
            PilotRecord(
                key=heading.group(1),
                level=values["level"],
                status=values["status"],
                title=values["title"],
                statement=_normalise(statement.group("value")),
                rationale=_normalise(rationale.group("value")),
                parent=values["parent"],
                source_locators=values["source locators"],
                applicability=values["applicability"],
                scope=values["scope"],
                allocation=values["allocation"],
                model_refs=values["model refs"],
                verification_plan=values["verification plan"],
                acceptance_condition=values["acceptance condition"],
                evidence_status=values["evidence status"],
                candidate_only=values["candidate only"],
                approval_ref=values.get("approval ref", ""),
            )
        )
    _require(records, "lightweight trial contains no requirement records")
    return records


def _anchors(text: str) -> set[str]:
    def slug(heading: str) -> str:
        value = re.sub(r"[`*_]", "", heading.strip().lower())
        value = re.sub(r"[^\w\s-]", "", value)
        return re.sub(r"\s+", "-", value)

    return {
        slug(match.group(1))
        for match in re.finditer(r"^#{1,6}\s+(.+?)\s*$", text, re.MULTILINE)
    }


def _check_locator(repo_root: Path, locator: str, label: str) -> None:
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
            value = json.loads(path.read_text(encoding="utf-8"))
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


def _validate_legacy_approval(record: PilotRecord, repo_root: Path) -> None:
    """Bind the fixed trial's legacy disposition to its actual approval record."""

    _check_locator(repo_root, record.approval_ref, f"approval ref for {record.key}")
    _require(
        record.approval_ref == EXPECTED_LEGACY_APPROVAL_REF,
        f"{record.key} must use the fixed legacy approval decision",
    )
    approval_path = repo_root / EXPECTED_LEGACY_APPROVAL_REF.partition("#")[0]
    decision_text = approval_path.read_text(encoding="utf-8")
    for legacy_id, disposition in APPROVED_LEGACY_DISPOSITIONS.items():
        _require(
            re.search(
                rf"`{re.escape(legacy_id)}`[^\n]*`{re.escape(disposition)}`",
                decision_text,
            )
            is not None,
            f"{record.key} approval decision lacks {legacy_id} {disposition} disposition",
        )


def _known_model_elements(repo_root: Path) -> set[str]:
    source = repo_root / "systems_engineering/models/system_views.md"
    _require(source.is_file(), "system views source is missing")
    text = source.read_text(encoding="utf-8")
    sections = list(re.finditer(r"^## (SE-MODEL-[A-Z]+-[0-9]{3})\b.*$", text, re.MULTILINE))
    elements: set[str] = set()
    for index, section in enumerate(sections):
        end = sections[index + 1].start() if index + 1 < len(sections) else len(text)
        model_id = section.group(1)
        body = text[section.end() : end]
        nodes = set(re.findall(r"(?m)^\s*([A-Za-z][A-Za-z0-9_]*)\s*(?:\[|\(\()", body))
        nodes.update(re.findall(r"(?m)^\s*([A-Za-z][A-Za-z0-9_]*)\s*-->", body))
        nodes.update(re.findall(r"-->\s*([A-Za-z][A-Za-z0-9_]*)", body))
        elements.update(f"{model_id}:{node}" for node in nodes)
    _require(elements, "no model elements were found in system views")
    return elements


def validate_records(records: Iterable[PilotRecord], repo_root: Path) -> None:
    """Validate the review schema, relations, references and truthful trial state."""

    records = list(records)
    keys = [record.key for record in records]
    _require(len(keys) == len(set(keys)), "duplicate pilot key")
    _require(set(keys) == EXPECTED_KEYS, "pilot key set is incomplete or unexpected")
    by_key = {record.key: record for record in records}
    model_elements = _known_model_elements(repo_root)
    for record in records:
        _require(PILOT_KEY.fullmatch(record.key) is not None, f"invalid temporary key: {record.key}")
        _require("B0-REQ-" not in record.key, f"formal B0 key is forbidden in phase one: {record.key}")
        _require(record.status == "pilot_only_candidate", f"invalid pilot status for {record.key}")
        _require(record.candidate_only == "true", f"{record.key} must remain candidate_only=true")
        _require("shall" in record.statement.lower(), f"{record.key} lacks a normative trial statement")
        _require(record.evidence_status == "planned/not_run", f"{record.key} must not claim execution evidence")
        if record.parent == "none":
            _require(record.key == "PILOT-ONLY-NEED-01", "only the trial user need may be a root record")
        else:
            _require(record.parent in by_key, f"unknown parent relation for {record.key}: {record.parent}")
        for locator in (item.strip() for item in record.source_locators.split(";")):
            _check_locator(repo_root, locator, f"source locator for {record.key}")
        _check_locator(repo_root, record.verification_plan, f"verification locator for {record.key}")
        _require(
            record.applicability in {"applicable", "not_applicable"},
            f"{record.key} has invalid applicability value: {record.applicability}",
        )
        if record.level == "applicability_record":
            _require(record.applicability == "not_applicable", f"{record.key} must state not_applicable applicability")
            _require(record.approval_ref, f"{record.key} lacks approval ref for not_applicable status")
            _validate_legacy_approval(record, repo_root)
        else:
            _require(record.applicability == "applicable", f"{record.key} must state applicable applicability")
            _require(record.allocation, f"{record.key} lacks allocation")
        for model_ref in (item.strip() for item in record.model_refs.split(",")):
            _require(model_ref in model_elements, f"unknown model reference for {record.key}: {model_ref}")


def validate_equivalence(sdoc_records: Iterable[PilotRecord], markdown_records: Iterable[PilotRecord]) -> None:
    """Ensure the temporary cross-format fixture does not conceal format drift."""

    sdoc = {record.key: record for record in sdoc_records}
    markdown = {record.key: record for record in markdown_records}
    _require(set(sdoc) == set(markdown), "trial formats use different temporary keys")
    for key in sorted(sdoc):
        _require(sdoc[key] == markdown[key], f"trial source formats drift for {key}")


def check_pilot(repo_root: Path) -> None:
    pilot_root = repo_root / "tools/systems_engineering/g15b_pilot"
    sdoc_source = pilot_root / "strictdoc/b0_phase1_pilot.sdoc"
    markdown_source = pilot_root / "lightweight/b0_phase1_pilot.md"
    _require(sdoc_source.is_file(), "StrictDoc pilot source is missing")
    _require(markdown_source.is_file(), "lightweight pilot source is missing")
    sdoc_records = parse_sdoc_records(sdoc_source.read_text(encoding="utf-8"))
    markdown_records = parse_markdown_records(markdown_source.read_text(encoding="utf-8"))
    validate_records(sdoc_records, repo_root)
    validate_records(markdown_records, repo_root)
    validate_equivalence(sdoc_records, markdown_records)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args(argv)
    try:
        check_pilot(args.repo_root.resolve())
    except PilotError as exc:
        parser.error(str(exc))
    print("G1.5-B phase-one pilot check passed (5 non-authoritative records)")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
