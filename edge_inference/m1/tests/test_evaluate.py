"""Tests for M1 evaluation mechanics (EDG-REQ-0001, EDG-REQ-0015, EDG-REQ-0028).

These tests check the scoring arithmetic on tiny synthetic inputs and verify the dataset
manifest. They do not assert any parser score on the real datasets.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluate import FIELDS, load_items, score, verify_manifest  # noqa: E402
from rule_parser import ParseResult  # noqa: E402

TASK = {
    "target_element": "deck",
    "location_tag": "span-1",
    "defect_classes": ["crack", "corrosion"],
    "required_views": ["overview"],
}


def _item(item_id, gold):
    return {"id": item_id, "text": item_id, "gold": gold}


def test_manifest_matches_dataset_files():
    actual = verify_manifest()
    assert set(actual) == {"dev_instructions_v1.json", "heldout_instructions_v1.json", "heldout_instructions_v2.json"}


def test_manifest_detects_changed_file(tmp_path):
    (tmp_path / "synthetic.json").write_text("changed", encoding="utf-8")
    (tmp_path / "MANIFEST.json").write_text(
        json.dumps({"files": {"synthetic.json": "0" * 64}}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="changed"):
        verify_manifest(tmp_path)


def test_duplicate_ids_are_rejected(tmp_path):
    path = tmp_path / "dup.json"
    path.write_text('[{"id":"a","text":"x","gold":{"status":"rejected"}},'
                    '{"id":"a","text":"y","gold":{"status":"rejected"}}]', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        load_items(path)


def test_perfect_parser_scores_one():
    items = [_item("t1", {"status": "task", "task": TASK})]
    result = score(items, lambda text: ParseResult("task", dict(TASK), None))
    assert result["status_accuracy"] == 1.0
    assert result["all_fields_accuracy"] == 1.0
    assert all(v == 1.0 for v in result["field_accuracy"].values())


def test_defect_list_compared_as_set():
    reordered = dict(TASK, defect_classes=["corrosion", "crack"])
    items = [_item("t1", {"status": "task", "task": TASK})]
    result = score(items, lambda text: ParseResult("task", reordered, None))
    assert result["field_accuracy"]["defect_classes"] == 1.0


def test_rejected_prediction_scores_fields_wrong():
    items = [_item("t1", {"status": "task", "task": TASK})]
    result = score(items, lambda text: ParseResult("rejected", None, "x"))
    assert result["status_accuracy"] == 0.0
    assert all(v == 0.0 for v in result["field_accuracy"].values())
    assert result["n_gold_task_items"] == 1


def test_correct_rejection_counts_as_status_correct_without_field_score():
    items = [_item("r1", {"status": "rejected"})]
    result = score(items, lambda text: ParseResult("rejected", None, "x"))
    assert result["status_accuracy"] == 1.0
    assert result["n_gold_task_items"] == 0
    assert result["field_accuracy"] == {name: None for name in FIELDS}


def test_schema_violations_are_counted_and_retained():
    bad = dict(TASK, target_element="tower")
    items = [_item("t1", {"status": "task", "task": TASK})]
    result = score(items, lambda text: ParseResult("task", bad, None))
    assert result["schema_violations"] == 1
    assert result["raw_outputs"][0]["schema_errors"]
    assert result["raw_outputs"][0]["task"] == bad


def test_partial_field_accuracy_is_per_field():
    wrong_location = dict(TASK, location_tag="span-9")
    items = [_item("t1", {"status": "task", "task": TASK}),
             _item("t2", {"status": "task", "task": TASK})]
    outputs = iter([TASK, wrong_location])
    result = score(items, lambda text: ParseResult("task", next(outputs), None))
    assert result["field_accuracy"]["location_tag"] == 0.5
    assert result["field_accuracy"]["target_element"] == 1.0
    assert result["all_fields_accuracy"] == 0.5
