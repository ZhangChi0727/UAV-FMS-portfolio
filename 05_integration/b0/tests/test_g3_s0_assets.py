"""Non-algorithmic closure checks for the G3 S0 design assets."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest


TRACK_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TRACK_ROOT.parents[1]
G0_PATH = TRACK_ROOT / "configs" / "b0_g0_contract.v2.json"
SCHEMA_PATH = TRACK_ROOT / "schema" / "b0_g3_integration_evidence.schema.json"
MATRIX_PATH = (
    REPO_ROOT / "systems_engineering/reports/b0/g3_s0_verification_matrix.md"
)
DESIGN_PATH = REPO_ROOT / "systems_engineering/reports/b0/g3_s0_integration_design.md"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _matrix_criterion_rows() -> list[list[str]]:
    matrix = MATRIX_PATH.read_text(encoding="utf-8")
    closure = matrix.split("## Exact 37-criterion closure", maxsplit=1)[1].split(
        "## Criterion record requirements", maxsplit=1
    )[0]
    rows = []
    for line in closure.splitlines():
        if not line.startswith("| `"):
            continue
        fields = [field.strip() for field in line.strip().strip("|").split("|")]
        assert len(fields) == 7
        rows.append(fields)
    return rows


def _matrix_event_rows() -> list[list[str]]:
    matrix = MATRIX_PATH.read_text(encoding="utf-8")
    projection = matrix.split("## Exact 13-event projection", maxsplit=1)[1].split(
        "## Metric-family signal contract", maxsplit=1
    )[0]
    rows = []
    for line in projection.splitlines():
        if not line.startswith("| `"):
            continue
        fields = [field.strip() for field in line.strip().strip("|").split("|")]
        assert len(fields) == 5
        rows.append(fields)
    return rows


def _matrix_scenario_rows() -> list[list[str]]:
    matrix = MATRIX_PATH.read_text(encoding="utf-8")
    catalogue = matrix.split("## Scenario catalogue", maxsplit=1)[1].split(
        "## Exact 13-event projection", maxsplit=1
    )[0]
    rows = []
    for line in catalogue.splitlines():
        if not line.startswith("| `"):
            continue
        fields = [field.strip() for field in line.strip().strip("|").split("|")]
        assert len(fields) == 8
        rows.append(fields)
    return rows


def _atomic_binding(field: str) -> str | None:
    value = field.strip()
    if value == "—":
        return None
    assert re.fullmatch(r"`?[A-Za-z0-9_]+`?", value)
    return value.strip("`")


def _assert_atomic_binding(expected: str | None, field: str) -> None:
    assert _atomic_binding(field) == expected


def test_g3_evidence_schema_has_strict_top_level_envelope() -> None:
    schema = _json(SCHEMA_PATH)
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["properties"]["schema_version"]["const"] == (
        "b0-g3-integration-evidence/v1"
    )
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["properties"]["scenario_runs"]["minItems"] == 8
    assert schema["properties"]["scenario_runs"]["maxItems"] == 8
    assert schema["properties"]["criteria"]["minItems"] == 37
    assert schema["properties"]["criteria"]["maxItems"] == 37
    assert schema["x-b0-validation-role"] == (
        "structural_envelope_requires_semantic_validator"
    )
    semantic_rules = "\n".join(schema["x-b0-semantic-rules"])
    for required_rule in (
        "exact eight G0 scenarios",
        "exact thirteen G0 events",
        "exact thirty-seven G0 criteria",
        "missing or duplicate identifiers",
        "criterion values",
        "acceptance-seed exposure",
    ):
        assert required_rule in semantic_rules
    assert "seed_exposure" in schema["required"]
    assert schema["properties"]["seed_exposure"]["minItems"] == 1


def test_g3_schema_declares_g0_scenario_and_criterion_enums() -> None:
    g0 = _json(G0_PATH)
    schema = _json(SCHEMA_PATH)
    scenario_ids = {item["id"] for item in g0["scenarios"]}
    scenario_classes = {item["class"] for item in g0["scenarios"]}
    criterion_ids = {
        criterion["id"]
        for scenario in g0["scenarios"]
        for criterion in scenario["acceptance"]
    }
    definitions = schema["$defs"]
    assert scenario_ids == set(
        definitions["scenario_run"]["properties"]["scenario_id"]["enum"]
    )
    assert scenario_classes == set(
        definitions["scenario_run"]["properties"]["scenario_class"]["enum"]
    )
    assert criterion_ids == set(
        definitions["criterion"]["properties"]["criterion_id"]["enum"]
    )
    assert scenario_ids == set(
        definitions["seed_exposure"]["properties"]["scenario_id"]["enum"]
    )
    assert len(criterion_ids) == 37


def test_g3_matrix_projects_scenario_identity_and_counts() -> None:
    g0 = _json(G0_PATH)
    rows = _matrix_scenario_rows()
    assert len(rows) == 8
    actual = {row[0].strip("`"): row for row in rows}
    assert set(actual) == {scenario["id"] for scenario in g0["scenarios"]}
    period_s = g0["timing"]["base_period_s"]
    terminal_by_class = {
        "in_envelope_performance": {
            "performance_pass",
            "performance_fail",
        },
        "limitation_characterization": {"limitation_characterized"},
        "invalid_input": {"invalid_input_rejected"},
    }
    for scenario in g0["scenarios"]:
        row = actual[scenario["id"]]
        assert row[1].strip("`") == scenario["class"]
        assert int(row[2]) == scenario["seed"]
        expected_intervals = round(scenario["duration_s"] / period_s)
        assert row[3] == f"{expected_intervals} intervals"
        assert int(row[4]) == len(scenario.get("events", []))
        assert int(row[6]) == len(scenario["acceptance"])
        actual_terminal = set(re.findall(r"`([^ `]+)`", row[7]))
        assert actual_terminal == terminal_by_class[scenario["class"]]


def test_g3_matrix_projects_every_g0_event_exactly_once() -> None:
    g0 = _json(G0_PATH)
    rows = _matrix_event_rows()
    assert len(rows) == 13
    expected_order = [
        event["id"]
        for scenario in g0["scenarios"]
        for event in scenario.get("events", [])
    ]
    assert [row[1].strip("`") for row in rows] == expected_order
    actual = {}
    for scenario, event_id, event_type, interval, payload in rows:
        key = event_id.strip("`")
        assert key not in actual
        actual[key] = {
            "scenario_id": scenario.strip("`"),
            "type": event_type.strip("`"),
            "interval": interval.strip("`"),
            "payload": json.loads(payload.strip("`")),
        }

    expected_ids = {
        event["id"]
        for scenario in g0["scenarios"]
        for event in scenario.get("events", [])
    }
    assert set(actual) == expected_ids
    for scenario in g0["scenarios"]:
        for event in scenario.get("events", []):
            projected = actual[event["id"]]
            assert projected["scenario_id"] == scenario["id"]
            assert projected["type"] == event["type"]
            assert projected["interval"] == (
                f"[{event['start_tick']},{event['end_tick']})"
            )
            payload = {
                key: value
                for key, value in event.items()
                if key not in {"id", "type", "start_tick", "end_tick"}
            }
            assert projected["payload"] == payload


def test_g3_matrix_projects_every_g0_criterion_exactly_once() -> None:
    g0 = _json(G0_PATH)
    rows = _matrix_criterion_rows()
    assert len(rows) == 37
    indexed = {}
    for row in rows:
        scenario_id = row[0].strip("`")
        criterion_id = row[1].strip("`")
        assert criterion_id not in indexed
        indexed[criterion_id] = (scenario_id, row)

    expected_ids = {
        criterion["id"]
        for scenario in g0["scenarios"]
        for criterion in scenario["acceptance"]
    }
    assert set(indexed) == expected_ids

    comparison_pattern = re.compile(
        r"(<=|>=|==)\s+(true|false|[-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?)"
        r"\s+([A-Za-z0-9%/]+)"
    )
    for scenario in g0["scenarios"]:
        for criterion in scenario["acceptance"]:
            actual_scenario, row = indexed[criterion["id"]]
            metric_reducer = row[2].strip("`")
            binding = row[3]
            window = row[4].strip("`")
            comparison = row[5].strip("`")

            assert actual_scenario == scenario["id"]
            assert metric_reducer == (
                f"{criterion['metric']} / {criterion['reducer']}"
            )
            assert window == (
                f"[{criterion['window']['start_tick']},"
                f"{criterion['window']['end_tick']})"
            )
            if "event_id" in criterion:
                expected_binding = criterion["event_id"]
            else:
                expected_binding = criterion.get("axis")
            _assert_atomic_binding(expected_binding, binding)

            match = comparison_pattern.search(comparison)
            assert match is not None, criterion["id"]
            operator, limit_text, unit = match.groups()
            assert operator == criterion["operator"]
            assert unit == criterion["unit"]
            if isinstance(criterion["limit"], bool):
                parsed_limit = limit_text == "true"
            else:
                parsed_limit = float(limit_text)
            assert parsed_limit == criterion["limit"]


def test_g3_atomic_event_binding_rejects_near_match() -> None:
    with pytest.raises(AssertionError):
        _assert_atomic_binding(
            "step_x_positive",
            "`step_x_positive_WRONG_EVENT`",
        )


def test_g3_test_report_envelope_retains_nonpassing_counts() -> None:
    schema = _json(SCHEMA_PATH)
    report_schema = schema["$defs"]["test_report"]
    report = {
        "suite": "structural-negative-fixture",
        "build_type": "Python",
        "junit_path": "artifacts/nonpassing.xml",
        "junit_sha256": "0" * 64,
        "collected": 7,
        "passed": 1,
        "failed": 1,
        "skipped": 2,
        "xfailed": 3,
    }
    assert set(report) == set(report_schema["required"])
    assert sum(report[name] for name in ("passed", "failed", "skipped", "xfailed")) == (
        report["collected"]
    )
    for name in ("collected", "passed", "failed", "skipped", "xfailed"):
        field_schema = report_schema["properties"][name]
        assert field_schema == {"type": "integer", "minimum": 0}
        assert report[name] >= field_schema["minimum"]
    assert "semantic acceptance" in report_schema["x-b0-acceptance-rule"]
    assert report["failed"] and report["skipped"] and report["xfailed"]


def test_g3_saturation_interval_end_weighting_fixture() -> None:
    period_s = 0.0025

    def clipped_weight_s(feedback_tick: int, start: int, end: int) -> float:
        covered_ticks = max(
            0,
            min(feedback_tick, end) - max(feedback_tick - 1, start),
        )
        return covered_ticks * period_s

    assert clipped_weight_s(200, 200, 202) == 0.0
    assert clipped_weight_s(201, 200, 202) == period_s
    assert clipped_weight_s(202, 200, 202) == period_s
    assert clipped_weight_s(203, 200, 202) == 0.0
    assert sum(
        clipped_weight_s(tick, 200, 202) for tick in (200, 201, 202, 203)
    ) == 0.005
    design = DESIGN_PATH.read_text(encoding="utf-8")
    assert "feedback recorded at boundary tick `k` describes the actuator" in design
    assert "interval `[k-1,k)`" in design


def test_g3_bind_smoke_fixture_is_nonzero_and_tuning_only() -> None:
    matrix = MATRIX_PATH.read_text(encoding="utf-8")
    design = DESIGN_PATH.read_text(encoding="utf-8")
    for text in (matrix, design):
        assert "`run_g3_bind_smoke(module_dir, build_type)`" in text
        assert "tuning seed `2026100900`" in text
        assert "`qx(0.1 rad)`" in text
        assert "local `[2,10)`" in text
        assert "ticks 1..12" in text
        assert "2,4,6,8,10,12" in text
        assert "not a ninth G0 scenario" in text


def test_g3_claim_boundary_cannot_encode_release_or_hardware_completion() -> None:
    claim = _json(SCHEMA_PATH)["$defs"]["claim_boundary"]["properties"]
    assert claim["integration_simulation_only"]["const"] is True
    for prohibited in ("g4_complete", "real_time_hil", "board_execution", "flight"):
        assert claim[prohibited]["const"] is False
