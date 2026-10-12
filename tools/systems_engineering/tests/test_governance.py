"""Positive and negative tests for the independent G1.5-A governance gate."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


TOOLS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_ROOT))

from check_governance import (  # noqa: E402
    GovernanceError,
    check_markdown_links,
    validate_manifest,
)


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def fixture_root(tmp_path: Path) -> Path:
    (tmp_path / "README.md").write_text("# Fixture\n\nNAV-REQ-001\n", encoding="utf-8")
    (tmp_path / "models.md").write_text("# SE-MODEL-TEST-001\n", encoding="utf-8")
    (tmp_path / "source.md").write_text("# source\n", encoding="utf-8")
    (tmp_path / "verification.md").write_text("verification\n", encoding="utf-8")
    return tmp_path


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_valid_manifest_passes(tmp_path: Path) -> None:
    validate_manifest(load_fixture("valid_manifest.json"), fixture_root(tmp_path))


@pytest.mark.parametrize(
    "name,match",
    [
        ("missing_evidence.json", "evidence reference is required"),
        ("unknown_model.json", "unknown model reference"),
        ("bad_migration.json", "migration target"),
    ],
)
def test_negative_fixtures_fail_closed(tmp_path: Path, name: str, match: str) -> None:
    with pytest.raises(GovernanceError, match=match):
        validate_manifest(load_fixture(name), fixture_root(tmp_path))


def test_accepted_evidence_cannot_claim_no_execution(tmp_path: Path) -> None:
    manifest = load_fixture("valid_manifest.json")
    manifest["obligations"][0]["evidence"]["ref"] = "no execution evidence available"
    with pytest.raises(GovernanceError, match="contradicted"):
        validate_manifest(manifest, fixture_root(tmp_path))


def test_markdown_link_check_passes_and_rejects_broken_link(tmp_path: Path) -> None:
    fixture_root(tmp_path)
    (tmp_path / "entry.md").write_text("[source](source.md#source)\n# source\n", encoding="utf-8")
    check_markdown_links(tmp_path, ["entry.md"])
    (tmp_path / "entry.md").write_text("[missing](not-present.md)\n", encoding="utf-8")
    with pytest.raises(GovernanceError, match="broken link"):
        check_markdown_links(tmp_path, ["entry.md"])
