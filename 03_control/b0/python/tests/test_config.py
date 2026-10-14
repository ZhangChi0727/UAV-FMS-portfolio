import importlib.util
import os
from pathlib import Path

module_dir = Path(os.environ["B0_CONTROLLER_MODULE_DIR"]).resolve()
spec = importlib.util.spec_from_file_location(
    "g2b_controller_adapter", Path(__file__).parents[1] / "controller.py"
)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


def test_actual_approved_config_and_authoritative_g0_load():
    parameters = adapter.load_controller_parameters()
    assert parameters.controller_period_s == 0.005
    assert parameters.torque_limit_Nm == [0.35, 0.35, 0.2]
    assert parameters.kaw_limit_per_s == [8, 8, 8]
