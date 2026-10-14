import hashlib
import importlib.util
import json
import os
import shutil
from pathlib import Path

import pytest

module_dir = Path(os.environ["B0_CONTROLLER_MODULE_DIR"]).resolve()
track = Path(__file__).resolve().parents[2]
repo = track.parents[1]
spec = importlib.util.spec_from_file_location(
    "g2b_controller_adapter", track / "python/controller.py"
)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


def canonical(data):
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def write_json(path, document, newline="\n"):
    text = json.dumps(document, indent=2) + "\n"
    path.write_bytes(text.replace("\n", newline).encode())


def fixture_repo(tmp_path, *, g0_newline="\n"):
    temporary_repo = tmp_path / "repository"
    temporary_track = temporary_repo / "03_control/b0"
    (temporary_track / "configs").mkdir(parents=True)
    (temporary_repo / "05_integration/b0/configs").mkdir(parents=True)
    (temporary_repo / "systems_engineering/reports/b0").mkdir(parents=True)
    shutil.copy2(track / "configs/b0_g2_controller.v1.json", temporary_track / "configs")
    shutil.copy2(
        track / "configs/b0_g2_controller_approval.v1.json", temporary_track / "configs"
    )
    shutil.copy2(
        repo / "05_integration/b0/validate_config.py",
        temporary_repo / "05_integration/b0/validate_config.py",
    )
    shutil.copy2(
        repo / "systems_engineering/reports/b0/g0_approval_decision.md",
        temporary_repo / "systems_engineering/reports/b0/g0_approval_decision.md",
    )
    source_g0 = repo / "05_integration/b0/configs/b0_g0_contract.v2.json"
    normalized = canonical(source_g0.read_bytes())
    (temporary_repo / "05_integration/b0/configs/b0_g0_contract.v2.json").write_bytes(
        normalized.replace(b"\n", g0_newline.encode())
    )
    return temporary_track


def approve_modified_design(temporary_track):
    design_path = temporary_track / "configs/b0_g2_controller.v1.json"
    approval_path = temporary_track / "configs/b0_g2_controller_approval.v1.json"
    approval = json.loads(approval_path.read_text())
    approval["approved_config_canonical_lf_sha256"] = hashlib.sha256(
        canonical(design_path.read_bytes())
    ).hexdigest()
    write_json(approval_path, approval)


def test_actual_approved_config_and_authoritative_g0_load():
    parameters = adapter.load_controller_parameters()
    assert parameters.controller_period_s == 0.005
    assert parameters.torque_limit_Nm == [0.35, 0.35, 0.2]
    assert parameters.kaw_limit_per_s == [8.0, 8.0, 8.0]


@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
def test_line_endings_and_authoritative_validation(tmp_path, newline):
    temporary_track = fixture_repo(tmp_path, g0_newline=newline)
    parameters = adapter.load_controller_parameters(track=temporary_track)
    assert parameters.controller_period_s == 0.005
    assert parameters.torque_limit_Nm == [0.35, 0.35, 0.2]


@pytest.mark.parametrize("case", ["missing", "changed", "wrong_version", "bad_gain"])
def test_configuration_fail_closed_for_g0(tmp_path, case):
    temporary_track = fixture_repo(tmp_path)
    g0_path = temporary_track.parents[1] / "05_integration/b0/configs/b0_g0_contract.v2.json"
    if case == "missing":
        g0_path.unlink()
    elif case == "changed":
        g0_path.write_bytes(g0_path.read_bytes() + b" ")
    else:
        document = json.loads(g0_path.read_text())
        if case == "wrong_version":
            document["schema_version"] = "b0-g0-contract/v999"
        else:
            document["controller_contract"]["rate_pid"]["kp"]["initial"][0] = -1.0
        write_json(g0_path, document)
        design_path = temporary_track / "configs/b0_g2_controller.v1.json"
        design = json.loads(design_path.read_text())
        design["authority"]["g0_canonical_lf_sha256"] = hashlib.sha256(
            canonical(g0_path.read_bytes())
        ).hexdigest()
        write_json(design_path, design)
        approve_modified_design(temporary_track)
    with pytest.raises(adapter.ControllerConfigurationError):
        adapter.load_controller_parameters(track=temporary_track)


@pytest.mark.parametrize("case", ["missing", "changed", "wrong_version", "bad_tolerance"])
def test_configuration_fail_closed_for_implementation_config(tmp_path, case):
    temporary_track = fixture_repo(tmp_path)
    design_path = temporary_track / "configs/b0_g2_controller.v1.json"
    if case == "missing":
        design_path.unlink()
    elif case == "changed":
        design_path.write_bytes(design_path.read_bytes() + b" ")
    else:
        design = json.loads(design_path.read_text())
        if case == "wrong_version":
            design["schema_version"] = "999"
        else:
            design["numeric_policy"]["timestamp_absolute_tolerance_s"] = -1.0
        write_json(design_path, design)
        approve_modified_design(temporary_track)
    with pytest.raises(adapter.ControllerConfigurationError):
        adapter.load_controller_parameters(track=temporary_track)
