"""Only invented split metadata; no image, annotation or M1/v2 access."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from leakage import validate_split_metadata  # noqa: E402


ROLES = {"dev": "development", "cal": "calibration", "locked": "heldout"}


def record(image, group, split="dev", level="bridge", exploratory=False, **kwargs):
    return {"image_id": image, "group_id": group, "grouping_level": level,
            "split": split, "exploratory": exploratory, **kwargs}


def check(*records, roles=None):
    return validate_split_metadata({"split_roles": ROLES if roles is None else roles,
                                    "records": list(records)})


def codes(result):
    return {error["code"] for error in result["errors"]}


def test_pass_is_metadata_only_and_not_w1_acceptance():
    result = check(record("a", "bridge-a"), record("b", "bridge-b", "locked"))
    assert result["status"] == "pass"
    assert result["scope"] == "declared_metadata_only"
    assert result["independent_holdout_ready"] is False


@pytest.mark.parametrize("field,value", [("image_id", "unknown"), ("group_id", None),
                                        ("split", ""), ("image_id", " x ")])
def test_missing_or_unknown_ids_fail(field, value):
    item = record("a", "bridge-a")
    item[field] = value
    assert "missing_or_unknown_id" in codes(check(item))


def test_group_and_exact_hash_cross_split_fail():
    same_hash = "a" * 64
    result = check(record("a", "g", sha256=same_hash),
                   record("b", "g", "locked", sha256=same_hash))
    assert {"group_crosses_splits", "exact_hash_crosses_splits"} <= codes(result)


def test_duplicate_image_ids_fail_even_when_group_differs():
    result = check(record("a", "g1"), record("a", "g2", "locked"))
    assert "duplicate_image_id" in codes(result)


def test_unknown_or_exploratory_never_goes_to_heldout():
    result = check(record("a", "provisional-a", "locked", level="unknown", exploratory=True),
                   record("b", "provisional-b", level="unknown", exploratory=False))
    assert {"exploratory_or_unknown_in_heldout", "unknown_group_must_be_exploratory"} <= codes(result)
    assert check(record("a", "provisional-a", level="unknown", exploratory=True))["status"] == "pass"


def test_crops_require_declared_existing_parent_and_same_group():
    missing = check(record("child", "g", is_crop=True))
    assert "crop_missing_parent" in codes(missing)
    mismatch = check(record("parent", "g1"), record("child", "g2", is_crop=True, parent_image_id="parent"))
    assert "parent_group_mismatch" in codes(mismatch)
    absent = check(record("child", "g", is_crop=True, parent_image_id="missing"))
    assert "parent_not_in_manifest" in codes(absent)
    valid = check(record("parent", "g"), record("child", "g", is_crop=True, parent_image_id="parent"))
    assert valid["status"] == "pass"


def test_split_roles_required_and_additional_labels_rejected():
    assert "invalid_or_missing_split_roles" in codes(check(record("a", "g"), roles={"dev": "development"}))
    item = record("a", "g", annotation="must-not-be-read")
    assert "unexpected_fields" in codes(check(item))


def test_malformed_role_and_level_fail_without_exception():
    assert "invalid_or_missing_split_roles" in codes(check(record("a", "g"), roles={"dev": []}))
    assert "invalid_grouping_level" in codes(check(record("a", "g", level=[])))


def test_one_group_cannot_claim_different_grouping_levels():
    result = check(record("a", "g", level="bridge"), record("b", "g", level="source_image"))
    assert "inconsistent_grouping_level" in codes(result)


def test_cli_uses_stdin_and_emits_only_metadata(tmp_path):
    script = Path(__file__).resolve().parents[1] / "leakage.py"
    document = {"split_roles": ROLES, "records": [record("a", "g")]}
    run = subprocess.run([sys.executable, "-B", str(script)], input=json.dumps(document),
                         text=True, capture_output=True, check=False)
    assert run.returncode == 0
    assert json.loads(run.stdout)["status"] == "pass"
    document["records"][0]["group_id"] = "unknown"
    failed = subprocess.run([sys.executable, "-B", str(script)], input=json.dumps(document),
                            text=True, capture_output=True, check=False)
    assert failed.returncode == 1
    assert json.loads(failed.stdout)["status"] == "fail"
    outside = subprocess.run([sys.executable, "-B", str(script), "--output", str(tmp_path / "result.json")],
                             input=json.dumps(document), text=True, capture_output=True, check=False)
    assert outside.returncode != 0
    assert not (tmp_path / "result.json").exists()
