"""Tests for the M1 task schema (EDG-REQ-0001, EDG-REQ-0010)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from task_schema import DEFECT_CLASSES, REQUIRED_VIEWS, TARGET_ELEMENTS, validate_task  # noqa: E402


def _valid():
    return {
        "target_element": "girder",
        "location_tag": "span-3",
        "defect_classes": ["crack", "spalling"],
        "required_views": ["close_up"],
    }


def test_valid_task_has_no_errors():
    assert validate_task(_valid()) == []


def test_non_mapping_is_rejected():
    assert validate_task(["girder"]) == ["task must be a mapping"]


@pytest.mark.parametrize("field", ["target_element", "location_tag", "defect_classes", "required_views"])
def test_missing_field_is_reported(field):
    task = _valid()
    del task[field]
    assert f"missing field: {field}" in validate_task(task)


def test_unknown_field_is_reported():
    task = _valid()
    task["severity"] = "high"
    assert "unknown field: severity" in validate_task(task)


def test_unknown_target_is_reported():
    task = _valid()
    task["target_element"] = "tower"
    assert any("target_element" in e for e in validate_task(task))


@pytest.mark.parametrize("location", ["span-0", "span-100", "pier-", "abutment-E", "Span-1", 3])
def test_bad_location_is_reported(location):
    task = _valid()
    task["location_tag"] = location
    assert any("location_tag" in e for e in validate_task(task))


@pytest.mark.parametrize("location", ["unspecified", "span-1", "span-99", "pier-12", "abutment-N", "abutment-S"])
def test_good_location_is_accepted(location):
    task = _valid()
    task["location_tag"] = location
    assert validate_task(task) == []


def test_empty_defect_list_is_rejected():
    task = _valid()
    task["defect_classes"] = []
    assert any("defect_classes must be a non-empty list" in e for e in validate_task(task))


def test_duplicate_values_are_reported():
    task = _valid()
    task["defect_classes"] = ["crack", "crack"]
    assert any("duplicates" in e for e in validate_task(task))


def test_non_civil_class_cannot_be_represented():
    task = _valid()
    task["defect_classes"] = ["person"]
    errors = validate_task(task)
    assert any("outside the schema" in e for e in errors)


def test_list_with_non_string_is_reported_without_crashing():
    task = _valid()
    task["required_views"] = [["overview"]]
    assert any("only strings" in e for e in validate_task(task))


def test_vocabularies_are_as_documented():
    assert TARGET_ELEMENTS == ("deck", "girder", "pier", "abutment", "bearing")
    assert DEFECT_CLASSES == ("crack", "spalling", "corrosion", "efflorescence", "delamination")
    assert REQUIRED_VIEWS == ("overview", "close_up", "side_view", "underside")
