"""M1: deterministic rule-based baseline from instruction text to task record.

This is the reference baseline for EDG-REQ-0001 and EDG-REQ-0016. It is not a language
model. Its errors are measured by evaluate.py, and later model-based parsers are compared
against it on the same held-out instructions.

Rule order is fixed: civil-scope refusal first, then target element, defect classes,
location and views. A missing target or defect class rejects the instruction rather than
guessing. A missing view defaults to ["overview"], recorded as a rule, not an inference.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

from task_schema import validate_task

NON_CIVIL_TERMS = ("person", "people", "vehicle", "military", "surveil", "weapon")

# Priority matters: "bearing" is tested before "pier" so "bearings on pier 1" is a bearing task.
TARGET_RULES = (
    ("abutment", re.compile(r"\babutment")),
    ("bearing", re.compile(r"\bbearing")),
    ("girder", re.compile(r"\bgirder|\bbeam")),
    ("pier", re.compile(r"\bpier|\bcolumn")),
    ("deck", re.compile(r"\bdeck|\broad surface")),
)

DEFECT_RULES = (
    ("crack", re.compile(r"\bcrack")),
    ("spalling", re.compile(r"\bspall")),
    ("corrosion", re.compile(r"\bcorros|\brust")),
    ("efflorescence", re.compile(r"\befflorescence|\bwhite deposit")),
    ("delamination", re.compile(r"\bdelamin")),
)

VIEW_RULES = (
    ("close_up", re.compile(r"\bclose[- ]?up\b|\bclose\b")),
    ("overview", re.compile(r"\boverview\b")),
    # "side view" must not match inside "underside view".
    ("side_view", re.compile(r"(?<!under)\bside view\b")),
    ("underside", re.compile(r"\bunderside\b")),
)

ABUTMENT_LOCATION = re.compile(r"\b(north|south) abutment")
PIER_LOCATION = re.compile(r"\bpier (\d{1,2})\b")
SPAN_LOCATION = re.compile(r"\bspan (\d{1,2})\b")


@dataclass(frozen=True)
class ParseResult:
    status: str  # "task" or "rejected"
    task: Optional[dict[str, Any]]
    reason: Optional[str]


def _first_match(rules, text: str) -> Optional[str]:
    for label, pattern in rules:
        if pattern.search(text):
            return label
    return None


def _all_matches(rules, text: str) -> list[str]:
    return [label for label, pattern in rules if pattern.search(text)]


def _location(text: str) -> str:
    abutment = ABUTMENT_LOCATION.search(text)
    if abutment:
        return f"abutment-{'N' if abutment.group(1) == 'north' else 'S'}"
    pier = PIER_LOCATION.search(text)
    if pier:
        return f"pier-{int(pier.group(1))}"
    span = SPAN_LOCATION.search(text)
    if span:
        return f"span-{int(span.group(1))}"
    return "unspecified"


def parse_instruction(text: str) -> ParseResult:
    """Map one instruction to a validated task, or reject it with a stated reason."""
    lowered = text.lower()

    if any(term in lowered for term in NON_CIVIL_TERMS):
        return ParseResult("rejected", None, "non-civil or surveillance content")

    target = _first_match(TARGET_RULES, lowered)
    if target is None:
        return ParseResult("rejected", None, "target element not identified")

    defects = _all_matches(DEFECT_RULES, lowered)
    if not defects:
        return ParseResult("rejected", None, "no defect class identified")

    views = _all_matches(VIEW_RULES, lowered) or ["overview"]

    task = {
        "target_element": target,
        "location_tag": _location(lowered),
        "defect_classes": defects,
        "required_views": views,
    }

    # The parser must never emit a record the schema would reject.
    errors = validate_task(task)
    if errors:
        return ParseResult("rejected", None, "internal: " + "; ".join(errors))
    return ParseResult("task", task, None)
