"""M1: task record schema and validation.

Requirements covered:
- EDG-REQ-0001: a natural-language instruction becomes a task record with target element,
  location tag, defect classes and required views; output not conforming to the schema is
  rejected.
- EDG-REQ-0010: only civil bridge-inspection vocabularies exist in the schema, so non-civil
  classes cannot be represented.

The vocabularies below are project-owned. They must be mapped to a named dataset version
before any image evaluation (EDG-REQ-0018).

Interface:
    validate_task(task) -> list[str]     # empty list means valid
    SCHEMA_VERSION, TARGET_ELEMENTS, DEFECT_CLASSES, REQUIRED_VIEWS, LOCATION_PATTERN
"""

from __future__ import annotations

import re
from typing import Any, Mapping

SCHEMA_VERSION = "task-schema/v1"

TARGET_ELEMENTS = ("deck", "girder", "pier", "abutment", "bearing")
DEFECT_CLASSES = ("crack", "spalling", "corrosion", "efflorescence", "delamination")
REQUIRED_VIEWS = ("overview", "close_up", "side_view", "underside")

# "unspecified", span-N, pier-N with N in 1..99, or abutment-N / abutment-S.
LOCATION_PATTERN = re.compile(r"^(unspecified|span-[1-9][0-9]?|pier-[1-9][0-9]?|abutment-[NS])$")

TASK_KEYS = frozenset({"target_element", "location_tag", "defect_classes", "required_views"})


def _check_list(name: str, value: Any, allowed: tuple[str, ...], errors: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errors.append(f"{name} must be a non-empty list")
        return
    if not all(isinstance(item, str) for item in value):
        errors.append(f"{name} must contain only strings")
        return
    if len(set(value)) != len(value):
        errors.append(f"{name} contains duplicates")
    unknown = sorted({item for item in value if item not in allowed})
    if unknown:
        errors.append(f"{name} has values outside the schema: {', '.join(unknown)}")


def validate_task(task: Any) -> list[str]:
    """Return every schema violation found. An empty list means the task is valid."""
    if not isinstance(task, Mapping):
        return ["task must be a mapping"]

    errors: list[str] = []
    keys = set(task)
    for key in sorted(TASK_KEYS - keys):
        errors.append(f"missing field: {key}")
    for key in sorted(keys - TASK_KEYS):
        errors.append(f"unknown field: {key}")

    if "target_element" in task and task["target_element"] not in TARGET_ELEMENTS:
        errors.append(f"target_element {task['target_element']!r} is not in the schema")

    if "location_tag" in task:
        location = task["location_tag"]
        if not isinstance(location, str) or not LOCATION_PATTERN.match(location):
            errors.append(f"location_tag {location!r} does not match the schema pattern")

    if "defect_classes" in task:
        _check_list("defect_classes", task["defect_classes"], DEFECT_CLASSES, errors)
    if "required_views" in task:
        _check_list("required_views", task["required_views"], REQUIRED_VIEWS, errors)

    return errors
