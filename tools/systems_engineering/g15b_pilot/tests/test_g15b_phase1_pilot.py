"""Positive and negative checks for the G1.5-B phase-one text trial."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[4]
TOOLS_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TOOLS_ROOT))

from check_g15b_phase1_pilot import (  # noqa: E402
    PilotError,
    check_pilot,
    parse_markdown_records,
    parse_sdoc_records,
    validate_equivalence,
    validate_records,
)


SDOC_SOURCE = REPO_ROOT / "tools/systems_engineering/g15b_pilot/strictdoc/b0_phase1_pilot.sdoc"
MARKDOWN_SOURCE = REPO_ROOT / "tools/systems_engineering/g15b_pilot/lightweight/b0_phase1_pilot.md"


def test_actual_phase_one_pilot_passes() -> None:
    check_pilot(REPO_ROOT)


def test_duplicate_temporary_key_fails_closed() -> None:
    source = SDOC_SOURCE.read_text(encoding="utf-8").replace(
        "UID: PILOT-ONLY-G2-05", "UID: PILOT-ONLY-NEED-01"
    )
    with pytest.raises(PilotError, match="duplicate pilot key"):
        validate_records(parse_sdoc_records(source), REPO_ROOT)


def test_unknown_model_reference_fails_closed() -> None:
    source = SDOC_SOURCE.read_text(encoding="utf-8").replace(
        "SE-MODEL-INTERFACE-001", "SE-MODEL-NOT-999", 1
    )
    with pytest.raises(PilotError, match="unknown model reference"):
        validate_records(parse_sdoc_records(source), REPO_ROOT)


def test_missing_json_field_locator_fails_closed() -> None:
    source = SDOC_SOURCE.read_text(encoding="utf-8").replace(
        "/controller_contract/truth_inputs_forbidden", "/missing_controller_contract"
    )
    with pytest.raises(PilotError, match="JSON pointer is missing"):
        validate_records(parse_sdoc_records(source), REPO_ROOT)


def test_malformed_json_locator_fails_closed() -> None:
    source = SDOC_SOURCE.read_text(encoding="utf-8").replace(
        "#/controller_contract/truth_inputs_forbidden", "#controller_contract/truth_inputs_forbidden"
    )
    with pytest.raises(PilotError, match="must use a JSON Pointer"):
        validate_records(parse_sdoc_records(source), REPO_ROOT)


def test_malformed_markdown_locator_fails_closed() -> None:
    source = SDOC_SOURCE.read_text(encoding="utf-8").replace(
        "architecture.md#modular-boundaries", "architecture.md#/modular-boundaries"
    )
    with pytest.raises(PilotError, match="must use a Markdown anchor"):
        validate_records(parse_sdoc_records(source), REPO_ROOT)


def test_missing_required_metadata_fails_closed() -> None:
    source = SDOC_SOURCE.read_text(encoding="utf-8").replace(
        "Evidence status: planned/not_run\n", "", 1
    )
    with pytest.raises(PilotError, match="missing required metadata"):
        parse_sdoc_records(source)


def test_missing_acceptance_condition_fails_closed() -> None:
    source = SDOC_SOURCE.read_text(encoding="utf-8").replace(
        "Acceptance condition: planned inspection confirms the declared experiment boundary and exclusions are present\n",
        "",
        1,
    )
    with pytest.raises(PilotError, match="missing required metadata: acceptance condition"):
        parse_sdoc_records(source)


def test_missing_allocation_for_applicable_record_fails_closed() -> None:
    source = SDOC_SOURCE.read_text(encoding="utf-8").replace(
        "Allocation: integration execution adapter and reader-facing system boundary\n",
        "",
        1,
    )
    with pytest.raises(PilotError, match="missing required metadata: allocation"):
        parse_sdoc_records(source)


def test_not_applicable_record_without_approval_reference_fails_closed() -> None:
    source = SDOC_SOURCE.read_text(encoding="utf-8").replace(
        "Approval ref: systems_engineering/reports/b0/g0_approval_decision.md#决定\n",
        "",
        1,
    )
    with pytest.raises(PilotError, match="lacks approval ref"):
        validate_records(parse_sdoc_records(source), REPO_ROOT)


def test_not_applicable_record_with_invalid_approval_reference_fails_closed() -> None:
    source = SDOC_SOURCE.read_text(encoding="utf-8").replace(
        "Approval ref: systems_engineering/reports/b0/g0_approval_decision.md#决定",
        "Approval ref: systems_engineering/reports/b0/g0_approval_decision.md#missing-decision",
    )
    with pytest.raises(PilotError, match="approval ref.*anchor is missing"):
        validate_records(parse_sdoc_records(source), REPO_ROOT)


def test_not_applicable_record_with_unrelated_approval_reference_fails_closed() -> None:
    source = SDOC_SOURCE.read_text(encoding="utf-8").replace(
        "Approval ref: systems_engineering/reports/b0/g0_approval_decision.md#决定",
        "Approval ref: systems_engineering/project_charter.md#purpose",
    )
    with pytest.raises(PilotError, match="fixed legacy approval decision"):
        validate_records(parse_sdoc_records(source), REPO_ROOT)


def test_not_applicable_record_cannot_claim_applicability() -> None:
    source = SDOC_SOURCE.read_text(encoding="utf-8").replace(
        "Applicability: not_applicable", "Applicability: applicable"
    )
    with pytest.raises(PilotError, match="must state not_applicable applicability"):
        validate_records(parse_sdoc_records(source), REPO_ROOT)


def test_broken_parent_relation_fails_closed() -> None:
    source = SDOC_SOURCE.read_text(encoding="utf-8").replace(
        "VALUE: PILOT-ONLY-INTERFACE-02", "VALUE: PILOT-ONLY-MISSING-99"
    )
    with pytest.raises(PilotError, match="unknown parent relation"):
        validate_records(parse_sdoc_records(source), REPO_ROOT)


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
    source = SDOC_SOURCE.read_text(encoding="utf-8").replace("/scenarios/6/id", replacement)
    with pytest.raises(PilotError, match=message):
        validate_records(parse_sdoc_records(source), REPO_ROOT)


def test_valid_json_array_index_remains_accepted() -> None:
    source = SDOC_SOURCE.read_text(encoding="utf-8").replace("/scenarios/6/id", "/scenarios/0/id")
    validate_records(parse_sdoc_records(source), REPO_ROOT)


def test_cross_format_drift_fails_closed() -> None:
    changed_markdown = MARKDOWN_SOURCE.read_text(encoding="utf-8").replace(
        "Runtime truth isolation", "Changed interface title", 1
    )
    with pytest.raises(PilotError, match="trial source formats drift"):
        validate_equivalence(
            parse_sdoc_records(SDOC_SOURCE.read_text(encoding="utf-8")),
            parse_markdown_records(changed_markdown),
        )


def test_cross_format_rationale_drift_fails_closed() -> None:
    changed_markdown = MARKDOWN_SOURCE.read_text(encoding="utf-8").replace(
        "This trial represents an interface constraint and a child relationship without treating existing component behavior as the sole source of the obligation.",
        "A deliberately different rationale must not be concealed by the text-format comparison.",
        1,
    )
    with pytest.raises(PilotError, match="trial source formats drift"):
        validate_equivalence(
            parse_sdoc_records(SDOC_SOURCE.read_text(encoding="utf-8")),
            parse_markdown_records(changed_markdown),
        )
