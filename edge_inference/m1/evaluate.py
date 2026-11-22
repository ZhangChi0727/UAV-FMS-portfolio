"""M1: field-level evaluation of an instruction parser over a fixed, versioned dataset.

Requirements covered:
- EDG-REQ-0001: accuracy per field over a fixed, versioned instruction set; schema
  violations counted and raw outputs retained.
- EDG-REQ-0015 / 0028: dataset file hashes are recorded in MANIFEST.json and verified
  before scoring.

Scoring rules:
- status accuracy: predicted status equals gold status.
- field accuracy: for gold task items, each of the four fields is compared. A rejected
  prediction scores every field as wrong. Lists are compared as sets.
- schema violations: count of validation errors in predicted tasks (expected 0 for the
  rule baseline, which validates its own output).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from task_schema import validate_task

FIELDS = ("target_element", "location_tag", "defect_classes", "required_views")
DATA_DIR = Path(__file__).resolve().parent / "data"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_manifest(data_dir: Path = DATA_DIR) -> dict[str, str]:
    """Check every dataset file against MANIFEST.json. Raises ValueError on mismatch."""
    manifest = json.loads((data_dir / "MANIFEST.json").read_text(encoding="utf-8"))
    actual: dict[str, str] = {}
    for name, expected in manifest["files"].items():
        digest = sha256_file(data_dir / name)
        actual[name] = digest
        if digest != expected:
            raise ValueError(f"dataset file changed: {name}")
    return actual


def load_items(path: Path) -> list[dict[str, Any]]:
    items = json.loads(path.read_text(encoding="utf-8"))
    ids = [item["id"] for item in items]
    if len(set(ids)) != len(ids):
        raise ValueError(f"duplicate ids in {path.name}")
    return items


def _field_matches(name: str, predicted: dict[str, Any], gold: dict[str, Any]) -> bool:
    if name in ("defect_classes", "required_views"):
        return set(predicted.get(name, [])) == set(gold[name])
    return predicted.get(name) == gold[name]


def score(items: list[dict[str, Any]], parse: Callable[[str], Any]) -> dict[str, Any]:
    """Run parse on every item and return metrics plus retained raw outputs."""
    raw_outputs: list[dict[str, Any]] = []
    status_correct = 0
    schema_violations = 0
    gold_task_items = 0
    field_correct = {name: 0 for name in FIELDS}
    all_fields_correct = 0

    for item in items:
        result = parse(item["text"])
        gold = item["gold"]
        errors = validate_task(result.task) if result.task is not None else []
        schema_violations += len(errors)

        if result.status == gold["status"]:
            status_correct += 1

        if gold["status"] == "task":
            gold_task_items += 1
            predicted_task = result.task if (result.status == "task" and result.task) else {}
            matches = {
                name: _field_matches(name, predicted_task, gold["task"]) for name in FIELDS
            }
            for name, ok in matches.items():
                if ok:
                    field_correct[name] += 1
            if all(matches.values()):
                all_fields_correct += 1

        raw_outputs.append({
            "id": item["id"],
            "status": result.status,
            "task": result.task,
            "reason": result.reason,
            "schema_errors": errors,
        })

    def ratio(n: int, d: int) -> float | None:
        return round(n / d, 4) if d else None

    return {
        "n_items": len(items),
        "status_accuracy": ratio(status_correct, len(items)),
        "n_gold_task_items": gold_task_items,
        "field_accuracy": {name: ratio(field_correct[name], gold_task_items) for name in FIELDS},
        "all_fields_accuracy": ratio(all_fields_correct, gold_task_items),
        "schema_violations": schema_violations,
        "raw_outputs": raw_outputs,
    }
