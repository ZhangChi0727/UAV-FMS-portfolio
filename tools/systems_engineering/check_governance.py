"""Small, dependency-free G1.5-A structure and traceability gate."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable


class GovernanceError(ValueError):
    """Raised when a governance manifest cannot support a truthful pass."""


REQUIRED_MANIFEST_KEYS = {
    "schema_version",
    "required_files",
    "model_views",
    "obligations",
    "migration",
    "preserved_identifiers",
}
MATURITIES = {"accepted", "approved/planned", "not active"}
EVIDENCE_STATUSES = {"accepted", "planned", "not_active", "pass", "not_run"}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise GovernanceError(message)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GovernanceError(f"cannot load JSON manifest {path}: {exc}") from exc
    _require(isinstance(value, dict), "manifest root must be an object")
    return value


def _repo_file(repo_root: Path, relative: str) -> Path:
    path = (repo_root / relative).resolve()
    try:
        path.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise GovernanceError(f"path escapes repository: {relative}") from exc
    return path


def _check_file(repo_root: Path, relative: str, label: str) -> Path:
    _require(isinstance(relative, str) and relative.strip(), f"{label} must be a path")
    path = _repo_file(repo_root, relative)
    _require(path.is_file(), f"{label} is missing: {relative}")
    return path


def validate_manifest(manifest: dict[str, Any], repo_root: Path) -> None:
    """Validate manifest structure, sources, allocations and evidence references."""

    _require(set(manifest) == REQUIRED_MANIFEST_KEYS, "manifest keys are incomplete or unexpected")
    _require(manifest["schema_version"] == "g1.5-a-governance/v1", "unsupported governance schema")

    required_files = manifest["required_files"]
    _require(isinstance(required_files, list) and required_files, "required_files must be non-empty")
    _require(len(required_files) == len(set(required_files)), "required_files contains duplicates")
    for relative in required_files:
        _check_file(repo_root, relative, "required file")

    views = manifest["model_views"]
    _require(isinstance(views, list) and views, "model_views must be non-empty")
    view_ids: set[str] = set()
    for view in views:
        _require(isinstance(view, dict), "each model view must be an object")
        _require(set(view) == {"id", "file", "anchor", "maturity"}, "model view fields are incomplete")
        model_id = view["id"]
        _require(isinstance(model_id, str) and model_id.startswith("SE-MODEL-"), f"invalid model id: {model_id}")
        _require(model_id not in view_ids, f"duplicate model id: {model_id}")
        view_ids.add(model_id)
        _require(view["maturity"] in MATURITIES, f"invalid maturity for {model_id}")
        model_file = _check_file(repo_root, view["file"], f"model file for {model_id}")
        text = model_file.read_text(encoding="utf-8")
        _require(view["anchor"] in text, f"model anchor missing: {model_id}")

    obligations = manifest["obligations"]
    _require(isinstance(obligations, list) and obligations, "obligations must be non-empty")
    obligation_keys: set[str] = set()
    for obligation in obligations:
        _require(isinstance(obligation, dict), "each obligation must be an object")
        expected = {"key", "source", "model_ref", "allocation", "verification", "applicability", "evidence"}
        _require(set(obligation) == expected, f"obligation fields are incomplete: {obligation.get('key')}")
        key = obligation["key"]
        _require(isinstance(key, str) and key.strip(), "obligation key must be non-empty")
        _require(key not in obligation_keys, f"duplicate obligation key: {key}")
        obligation_keys.add(key)
        _check_file(repo_root, obligation["source"], f"source for {key}")
        _require(obligation["model_ref"] in view_ids, f"unknown model reference for {key}")
        for field in ("allocation", "verification", "applicability"):
            _require(isinstance(obligation[field], str) and obligation[field].strip(), f"{key}.{field} is required")
        _check_file(repo_root, obligation["verification"], f"verification plan for {key}")
        evidence = obligation["evidence"]
        _require(isinstance(evidence, dict) and set(evidence) == {"status", "ref"}, f"evidence fields are incomplete: {key}")
        _require(evidence["status"] in EVIDENCE_STATUSES, f"invalid evidence status for {key}")
        _require(isinstance(evidence["ref"], str) and evidence["ref"].strip(), f"evidence reference is required for {key}")
        if evidence["status"] in {"accepted", "pass"}:
            _require("no execution evidence" not in evidence["ref"].lower(), f"accepted evidence is contradicted for {key}")

    migration = manifest["migration"]
    _require(isinstance(migration, list) and migration, "migration must be non-empty")
    migration_sources: set[str] = set()
    migration_targets: set[str] = set()
    for item in migration:
        _require(isinstance(item, dict) and set(item) == {"source", "target"}, "migration entries require source and target")
        source = item["source"]
        target = item["target"]
        _require(source not in migration_sources, f"duplicate migration source: {source}")
        _require(target not in migration_targets, f"duplicate migration target: {target}")
        migration_sources.add(source)
        migration_targets.add(target)
        _require(isinstance(source, str) and source.startswith("07_docs/"), f"migration source is not historical 07_docs: {source}")
        if not source.endswith("/*"):
            _check_file(repo_root, target, f"migration target for {source}")
        else:
            target_root = _repo_file(repo_root, target.removesuffix("/*"))
            _require(target_root.is_dir(), f"migration target directory is missing: {target}")

    identifiers = manifest["preserved_identifiers"]
    _require(isinstance(identifiers, list) and identifiers, "preserved_identifiers must be non-empty")
    requirements_path = repo_root / "systems_engineering/requirements/legacy_requirements.md"
    if requirements_path.is_file():
        requirements_text = requirements_path.read_text(encoding="utf-8")
    else:
        requirements_text = "\n".join(
            _check_file(repo_root, relative, "required file").read_text(encoding="utf-8")
            for relative in required_files
        )
    for identifier in identifiers:
        _require(isinstance(identifier, str) and re.fullmatch(r"(?:NAV|CTL|FDI)-REQ-[0-9]{3}", identifier), f"invalid preserved identifier: {identifier}")
        _require(identifier in requirements_text, f"preserved identifier is absent from legacy requirements: {identifier}")


_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def _slug(heading: str) -> str:
    value = re.sub(r"[`*_]", "", heading.strip().lower())
    value = re.sub(r"[^\w\s-]", "", value)
    return re.sub(r"\s+", "-", value)


def _anchors(text: str) -> set[str]:
    return {_slug(match.group(1)) for match in re.finditer(r"^#{1,6}\s+(.+?)\s*$", text, re.MULTILINE)}


def check_markdown_links(repo_root: Path, paths: Iterable[str] | None = None) -> None:
    """Check active entry-point Markdown links; historical prose is not a link."""

    paths = paths or (
        "README.md",
        "AGENTS.md",
        "RESULTS.md",
        "systems_engineering",
        "docs",
        "01_simulation/README.md",
        "02_estimation/README.md",
        "03_control/README.md",
        "04_fault_detection/README.md",
        "05_integration/README.md",
        "06_safety/README.md",
    )
    files: list[Path] = []
    for relative in paths:
        path = _repo_file(repo_root, relative)
        if path.is_dir():
            files.extend(sorted(path.rglob("*.md")))
        elif path.is_file():
            files.append(path)
    for source in files:
        source_text = source.read_text(encoding="utf-8")
        for raw_target in _LINK_RE.findall(source_text):
            target = raw_target.strip().split()[0]
            if target.startswith(("http://", "https://", "mailto:", "#")):
                if target.startswith("#") and target[1:] not in _anchors(source_text):
                    raise GovernanceError(f"missing local anchor {raw_target} in {source.relative_to(repo_root)}")
                continue
            path_part, _, fragment = target.partition("#")
            target_path = (source.parent / path_part).resolve()
            try:
                target_path.relative_to(repo_root.resolve())
            except ValueError as exc:
                raise GovernanceError(f"link escapes repository: {source} -> {target}") from exc
            _require(target_path.exists(), f"broken link: {source.relative_to(repo_root)} -> {target}")
            if fragment and target_path.is_file():
                target_text = target_path.read_text(encoding="utf-8")
                _require(fragment in _anchors(target_text), f"missing anchor: {source.relative_to(repo_root)} -> {target}")


def check_repository(repo_root: Path, manifest_path: Path | None = None) -> None:
    manifest_path = manifest_path or repo_root / "tools/systems_engineering/governance_manifest.json"
    validate_manifest(_load_json(manifest_path), repo_root)
    check_markdown_links(repo_root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    manifest = args.manifest.resolve() if args.manifest else None
    try:
        check_repository(repo_root, manifest)
    except GovernanceError as exc:
        parser.error(str(exc))
    print("G1.5-A systems-engineering governance check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
