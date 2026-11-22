"""Tests for the M1 rule-based parser (EDG-REQ-0001, EDG-REQ-0010).

The rule rules themselves are tested here on targeted sentences. Dataset-level scores are
produced by evaluate.py and are not asserted in these tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rule_parser import parse_instruction  # noqa: E402
from task_schema import validate_task  # noqa: E402


def test_basic_task_fields():
    result = parse_instruction("Check the deck for cracks near span 2 using close-up and overview images.")
    assert result.status == "task"
    assert result.task == {
        "target_element": "deck",
        "location_tag": "span-2",
        "defect_classes": ["crack"],
        "required_views": ["close_up", "overview"],
    }


def test_underside_is_not_side_view():
    result = parse_instruction("Examine the girder of span 1 for cracks; underside view required.")
    assert result.task["required_views"] == ["underside"]


def test_side_view_is_detected_alone():
    result = parse_instruction("Inspect pier 3 for cracks from the side view.")
    assert result.task["required_views"] == ["side_view"]


def test_bearing_takes_priority_over_pier():
    result = parse_instruction("Check bearings on pier 1 for corrosion.")
    assert result.task["target_element"] == "bearing"
    assert result.task["location_tag"] == "pier-1"


def test_default_view_is_overview_and_is_recorded_as_such():
    result = parse_instruction("Check the deck for corrosion.")
    assert result.task["required_views"] == ["overview"]


def test_location_absent_gives_unspecified():
    result = parse_instruction("Check the deck for corrosion.")
    assert result.task["location_tag"] == "unspecified"


@pytest.mark.parametrize("text, expected", [
    ("Look at the north abutment for efflorescence.", "abutment-N"),
    ("Check the south abutment for rust.", "abutment-S"),
])
def test_abutment_location(text, expected):
    assert parse_instruction(text).task["location_tag"] == expected


def test_white_deposit_maps_to_efflorescence():
    assert parse_instruction("Inspect the girder for white deposit.").task["defect_classes"] == ["efflorescence"]


def test_civil_refusal_comes_first():
    result = parse_instruction("Find people near the deck and track the vehicle.")
    assert result.status == "rejected"
    assert result.reason == "non-civil or surveillance content"


def test_missing_target_is_rejected():
    result = parse_instruction("Summarise the bridge history.")
    assert result.status == "rejected"
    assert result.reason == "target element not identified"


def test_missing_defect_is_rejected_rather_than_guessed():
    result = parse_instruction("Check the deck and report back.")
    assert result.status == "rejected"
    assert result.reason == "no defect class identified"


@pytest.mark.parametrize("text", [
    "Check the deck for cracks.",
    "Inspect pier 9 for spalling and corrosion from the side view.",
    "Check the south abutment for rust and cracks with close-up images.",
    "Examine the bearing on span 12 for delamination.",
])
def test_accepted_outputs_always_validate(text):
    result = parse_instruction(text)
    assert result.status == "task"
    assert validate_task(result.task) == []
