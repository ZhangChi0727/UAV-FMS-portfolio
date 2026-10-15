"""Real-module G3-BIND check, explicitly collected by each controller CI build."""

from __future__ import annotations

import os
import sys
from pathlib import Path

TRACK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRACK_ROOT))

from runner import run_g3_bind_smoke  # noqa: E402


def test_real_components_complete_fixed_twelve_tick_loop() -> None:
    module_dir = Path(os.environ["B0_CONTROLLER_MODULE_DIR"]).resolve()
    build_type = os.environ["B0_CONTROLLER_BUILD_TYPE"]
    result = run_g3_bind_smoke(module_dir, build_type)
    assert result["classification"] == "development_interface_smoke_not_acceptance"
    assert result["seed_kind"] == "tuning_seed"
    assert result["seed"] == 2026100900
    assert result["call_counts"] == {
        "plant": 12,
        "actuator": 12,
        "imu": 6,
        "estimator": 6,
        "controller": 6,
    }
    due = [record for record in result["records"] if record["controller_updated"]]
    assert [record["local_tick"] for record in due] == [2, 4, 6, 8, 10, 12]
    assert due[0]["command_q_nb"][1] > 0.0
    assert due[3]["command_q_nb"][1] > 0.0
    assert due[4]["command_q_nb"] == [1.0, 0.0, 0.0, 0.0]
    assert [record["actuator_command_timestamp_s"] for record in result["records"][:3]] == [
        0.0,
        0.0,
        0.005,
    ]
    assert any(
        abs(value) > 0.0
        for record in due
        for value in record["requested_torque_body_Nm"]
    )
