from __future__ import annotations

import json

from evidence import build_evidence


def test_evidence_is_deterministic_and_all_component_criteria_hold():
    first = build_evidence()
    second = build_evidence()
    assert first == second
    assert all(first["criteria"].values())
    assert first["observations"]["gap_recovery"]["diagnostics"]["gap_approximated"]
    assert "closed-loop performance" in first["limitations"][-1]
    json.dumps(first)
