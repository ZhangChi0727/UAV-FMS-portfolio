from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

TOOLS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_ROOT))

from g15b_joint_baseline import BaselineValidationError, validate_baseline  # noqa: E402


REPO = Path(__file__).resolve().parents[3]


def load(name: str):
    path = {
        "requirements": "systems_engineering/requirements/b0_requirements.json",
        "registry": "systems_engineering/requirements/b0_id_registry.json",
        "verification": "systems_engineering/verification/b0_verification_specifications.json",
    }[name]
    return json.loads((REPO / path).read_text(encoding="utf-8"))


def validate(req=None, registry=None, verification=None, model_path=None):
    return validate_baseline(
        REPO,
        requirements_data=req,
        registry_data=registry,
        verification_data=verification,
        model_path=model_path,
        check_projections=req is None and verification is None,
    )


def test_candidate_is_complete_and_not_run():
    assert validate() == {"requirements": 30, "model_elements": 26, "verifications": 29}


def test_duplicate_requirement_is_rejected():
    doc = load("requirements")
    doc["requirements"].append(deepcopy(doc["requirements"][0]))
    with pytest.raises(BaselineValidationError, match="duplicate requirement"):
        validate(req=doc)


def test_registry_omission_is_rejected():
    registry = load("registry")
    registry["allocations"].pop()
    with pytest.raises(BaselineValidationError, match="identity sets differ"):
        validate(registry=registry)


def test_registry_reuse_is_rejected():
    registry = load("registry")
    registry["next_ordinal"] = 30
    with pytest.raises(BaselineValidationError, match="reuse"):
        validate(registry=registry)


def test_retired_identity_reuse_is_rejected():
    registry = load("registry")
    registry["retired"] = ["B0-REQ-0001"]
    with pytest.raises(BaselineValidationError, match="retired requirement identity"):
        validate(registry=registry)


@pytest.mark.parametrize("field", ["statement", "source_ids", "acceptance_condition"])
def test_required_requirement_content_is_rejected(field):
    doc = load("requirements")
    doc["requirements"][0][field] = [] if field == "source_ids" else ""
    with pytest.raises(BaselineValidationError, match="schema error"):
        validate(req=doc)


def test_missing_applicability_is_rejected():
    doc = load("requirements")
    del doc["requirements"][0]["applicability"]
    with pytest.raises(BaselineValidationError, match="schema error"):
        validate(req=doc)


def test_unknown_parent_is_rejected():
    doc = load("requirements")
    doc["requirements"][1]["parent_id"] = "B0-REQ-9999"
    with pytest.raises(BaselineValidationError, match="unknown parent"):
        validate(req=doc)


def test_unknown_model_link_is_rejected():
    doc = load("requirements")
    doc["requirements"][0]["model_element_ids"] = ["B0-MODEL-NOT-THERE"]
    with pytest.raises(BaselineValidationError, match="unknown model"):
        validate(req=doc)


def test_unknown_verification_link_is_rejected():
    doc = load("requirements")
    doc["requirements"][0]["verification_ids"] = ["B0-VER-NOT-THERE"]
    with pytest.raises(BaselineValidationError, match="unknown verification"):
        validate(req=doc)


def test_reverse_link_drift_is_rejected():
    verification = load("verification")
    verification["specifications"][0]["requirement_ids"] = ["B0-REQ-0002"]
    with pytest.raises(BaselineValidationError, match="reverse link"):
        validate(verification=verification)


@pytest.mark.parametrize("field", ["oracle", "decision_rule", "responsible"])
def test_incomplete_verification_contract_is_rejected(field):
    verification = load("verification")
    verification["specifications"][0][field] = ""
    with pytest.raises(BaselineValidationError, match="lacks"):
        validate(verification=verification)


def test_fake_pass_is_rejected():
    verification = load("verification")
    verification["specifications"][0]["execution_status"] = "passed"
    verification["specifications"][0]["result"] = "pass"
    with pytest.raises(BaselineValidationError, match="claims execution"):
        validate(verification=verification)


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("flow PlantTruth from plant to evaluator;", "flow PlantTruth from plant to controller;", "truth"),
        ("item requested;", "item raw;", "paired torque field"),
        ("out item actuatorFeedback : ActuatorFeedback;", "in item actuatorFeedback : ActuatorFeedback;", "feedback output"),
        ("expose B0System;", "expose CascadedController;", "exposure"),
    ],
)
def test_critical_model_mutations_are_rejected(tmp_path, old, new, message):
    source = (REPO / "systems_engineering/models/b0_system.sysml").read_text(encoding="utf-8")
    path = tmp_path / "mutated.sysml"
    path.write_text(source.replace(old, new), encoding="utf-8")
    with pytest.raises(BaselineValidationError, match=message):
        validate(model_path=path)


def test_planned_many_to_many_allocation_is_allowed():
    req = load("requirements")
    ver = load("verification")
    req["requirements"][1]["verification_ids"].append(req["requirements"][0]["verification_ids"][0])
    ver["specifications"][0]["requirement_ids"].append(req["requirements"][1]["id"])
    assert validate(req=req, verification=ver)["requirements"] == 30


def test_legal_supersedes_chain_is_traceable():
    req = load("requirements")
    registry = load("registry")
    req["requirements"][1]["supersedes"] = "B0-REQ-0001"
    registry["supersedes"] = [{"new_id": "B0-REQ-0002", "prior_id": "B0-REQ-0001"}]
    assert validate(req=req, registry=registry)["requirements"] == 30
