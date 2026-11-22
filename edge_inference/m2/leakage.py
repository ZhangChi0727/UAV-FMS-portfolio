"""Check declared split metadata only; never inspect images or annotations.

Input is a JSON object on stdin with `split_roles` and `records`. Each split
must be assigned one of development, calibration, or heldout explicitly.
Records contain image_id, group_id, grouping_level, split and exploratory;
optional fields are parent_image_id, is_crop and sha256. The caller supplies
the metadata; this check cannot prove that undeclared relations do not exist.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any

PRIVATE_BUILD = Path(__file__).resolve().parents[2] / "build"
ROLES = frozenset({"development", "calibration", "heldout"})
LEVELS = frozenset({"bridge", "source_image", "unknown"})
RECORD_FIELDS = frozenset({"image_id", "group_id", "grouping_level", "split", "exploratory",
                           "parent_image_id", "is_crop", "sha256"})
UNKNOWN_IDS = frozenset({"unknown", "none", "null", "n/a", "na", "?"})


def _valid_id(value: Any) -> bool:
    return (isinstance(value, str) and value == value.strip() and bool(value)
            and value.casefold() not in UNKNOWN_IDS)


def validate_split_metadata(document: Any) -> dict[str, Any]:
    """Return explicit errors; a pass is not W1 acceptance or provenance proof."""
    errors: list[dict[str, Any]] = []

    def error(code: str, **details: Any) -> None:
        errors.append({"code": code, **details})

    if not isinstance(document, dict) or set(document) != {"split_roles", "records"}:
        error("invalid_envelope")
        return _report(errors, 0)
    roles, records = document["split_roles"], document["records"]
    if (not isinstance(roles, dict) or not roles
        or any(not _valid_id(k) or not isinstance(v, str) or v not in ROLES for k, v in roles.items())
        or "heldout" not in roles.values()):
        error("invalid_or_missing_split_roles")
        roles = {}
    if not isinstance(records, list):
        error("records_not_array")
        return _report(errors, 0)
    if not records:
        error("no_records")

    by_id: dict[str, tuple[int, dict[str, Any]]] = {}
    groups: dict[str, tuple[str, int]] = {}
    group_levels: dict[str, tuple[str, int]] = {}
    hashes: dict[str, tuple[str, int]] = {}
    valid_records: list[tuple[int, dict[str, Any]]] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            error("record_not_object", index=index)
            continue
        extra = set(record) - RECORD_FIELDS
        if extra:
            error("unexpected_fields", index=index, fields=sorted(extra))
        image_id, group_id = record.get("image_id"), record.get("group_id")
        split, level = record.get("split"), record.get("grouping_level")
        exploratory = record.get("exploratory")
        invalid = False
        for name, value in (("image_id", image_id), ("group_id", group_id), ("split", split)):
            if not _valid_id(value):
                error("missing_or_unknown_id", index=index, field=name)
                invalid = True
        if not isinstance(level, str) or level not in LEVELS:
            error("invalid_grouping_level", index=index)
            invalid = True
        if type(exploratory) is not bool:
            error("exploratory_not_boolean", index=index)
            invalid = True
        if not invalid and split not in roles:
            error("split_without_role", index=index, split=split)
            invalid = True
        crop = record.get("is_crop", False)
        if type(crop) is not bool:
            error("is_crop_not_boolean", index=index)
        parent = record.get("parent_image_id")
        if parent is not None and not _valid_id(parent):
            error("missing_or_unknown_id", index=index, field="parent_image_id")
        if crop is True and not _valid_id(parent):
            error("crop_missing_parent", index=index)
        digest = record.get("sha256")
        if digest is not None and (not isinstance(digest, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", digest)):
            error("invalid_sha256", index=index)
        if invalid:
            continue
        valid_records.append((index, record))
        if image_id in by_id:
            error("duplicate_image_id", index=index, first_index=by_id[image_id][0])
        else:
            by_id[image_id] = (index, record)
        if level == "unknown" and not exploratory:
            error("unknown_group_must_be_exploratory", index=index)
        if roles[split] == "heldout" and (exploratory or level == "unknown"):
            error("exploratory_or_unknown_in_heldout", index=index)
        if group_id in groups and groups[group_id][0] != split:
            error("group_crosses_splits", index=index, first_index=groups[group_id][1])
        else:
            groups.setdefault(group_id, (split, index))
        if group_id in group_levels and group_levels[group_id][0] != level:
            error("inconsistent_grouping_level", index=index, first_index=group_levels[group_id][1])
        else:
            group_levels.setdefault(group_id, (level, index))
        if isinstance(digest, str) and re.fullmatch(r"[a-fA-F0-9]{64}", digest):
            digest = digest.lower()
            if digest in hashes and hashes[digest][0] != split:
                error("exact_hash_crosses_splits", index=index, first_index=hashes[digest][1])
            else:
                hashes.setdefault(digest, (split, index))

    for index, record in valid_records:
        parent_id = record.get("parent_image_id")
        if parent_id is None or not _valid_id(parent_id):
            continue
        if parent_id not in by_id:
            error("parent_not_in_manifest", index=index)
        elif parent_id == record["image_id"]:
            error("self_parent", index=index)
        elif by_id[parent_id][1]["group_id"] != record["group_id"]:
            error("parent_group_mismatch", index=index, parent_index=by_id[parent_id][0])
        elif by_id[parent_id][1]["split"] != record["split"]:
            error("parent_split_mismatch", index=index, parent_index=by_id[parent_id][0])
    return _report(errors, len(records))


def _report(errors: list[dict[str, Any]], count: int) -> dict[str, Any]:
    return {"status": "fail" if errors else "pass", "errors": errors, "record_count": count,
            "scope": "declared_metadata_only", "independent_holdout_ready": False,
            "limitations": ["No images, labels or hidden data inspected.",
                            "Undeclared crop/parent links and unknown duplicates remain unverified.",
                            "A metadata pass does not establish group provenance or W1 acceptance."]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="new JSON file inside this checkout's private build; default stdout")
    args = parser.parse_args()
    try:
        document = json.load(sys.stdin)
    except json.JSONDecodeError:
        result = _report([{"code": "invalid_json"}], 0)
    else:
        result = validate_split_metadata(document)
    serialized = json.dumps(result, indent=2, ensure_ascii=True) + "\n"
    if args.output is None:
        sys.stdout.write(serialized)
    else:
        output = args.output.resolve(strict=False)
        if not output.is_relative_to(PRIVATE_BUILD.resolve()) or not output.parent.is_dir():
            parser.error("output must be inside this checkout's existing private build directory")
        with output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(serialized)
    sys.exit(0 if result["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
