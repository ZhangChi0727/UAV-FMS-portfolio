import importlib.util
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

repo = Path(os.environ["B0_CONTROLLER_REPO"]).resolve()
sys.path.insert(0, os.environ["B0_CONTROLLER_MODULE_DIR"])
sys.path.insert(0, str(repo / "01_simulation/b0"))
sys.path.insert(0, str(repo / "02_estimation/b0"))

from actuator import Actuator  # noqa: E402
from contract import ActuatorInitialState, TorqueCommand  # noqa: E402
from estimator import ResetEpoch, StateEstimate  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "g2b_controller_adapter", repo / "03_control/b0/python/controller.py"
)
adapter_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter_module)


@dataclass
class Command:
    q_nb_command: tuple = (1.0, 0.0, 0.0, 0.0)
    timestamp_s: float = 0.005
    valid: object = True


def reset_fixture(epoch_id=0, timestamp=0.0):
    adapter = adapter_module.ControllerAdapter()
    reset_command = adapter.reset(ResetEpoch(epoch_id, timestamp))
    actuator = Actuator()
    actuator.reset(ActuatorInitialState(), timestamp)
    feedback = actuator.step_base(reset_command)
    feedback = actuator.step_base(reset_command)
    return adapter, actuator, reset_command, feedback


def test_real_g2a_g1_adapter_and_actuator_consumption():
    adapter, actuator, reset_command, feedback = reset_fixture()
    assert isinstance(reset_command, TorqueCommand)
    estimate = StateEstimate((1, 0, 0, 0), (0, 0, 0), 0.005, True)
    output = adapter.step(Command(), estimate, feedback, 0.005)
    assert isinstance(output, TorqueCommand)
    consumed = actuator.step_base(output)
    assert consumed.command_timestamp_s == output.timestamp_s


@pytest.mark.parametrize("value", [False, "false", 0, 1, None])
def test_command_validity_is_explicit_bool_and_true(value):
    adapter, _, _, feedback = reset_fixture()
    estimate = StateEstimate((1, 0, 0, 0), (0, 0, 0), 0.005, True)
    with pytest.raises(ValueError):
        adapter.step(Command(valid=value), estimate, feedback, 0.005)


def test_estimate_validity_wrong_type_is_rejected():
    adapter, _, _, feedback = reset_fixture()

    class Estimate:
        q_nb_estimate = (1, 0, 0, 0)
        omega_b_estimate_rad_s = (0, 0, 0)
        timestamp_s = 0.005
        valid = "false"

    with pytest.raises(ValueError):
        adapter.step(Command(), Estimate(), feedback, 0.005)


@pytest.mark.parametrize("value", [1.5, True, -1, 2**63])
def test_reset_epoch_type_and_range_are_not_coerced(value):
    adapter = adapter_module.ControllerAdapter()

    class Epoch:
        id = value
        timestamp_s = 0.0

    with pytest.raises(ValueError):
        adapter.reset(Epoch())
