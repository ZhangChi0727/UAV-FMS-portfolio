import importlib.util
import os
import sys
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

repo = Path(os.environ["B0_CONTROLLER_REPO"]).resolve()
sys.path.insert(0, os.environ["B0_CONTROLLER_MODULE_DIR"])
sys.path.insert(0, str(repo / "01_simulation"))
sys.path.insert(0, str(repo / "02_estimation/b0"))

from b0 import Actuator, ActuatorInitialState, TorqueCommand  # noqa: E402
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


def snapshot_value(snapshot):
    diagnostics = snapshot.last_diagnostics
    held = snapshot.expected_held_command
    return (
        snapshot.reset,
        snapshot.epoch_id,
        snapshot.tick_index,
        snapshot.epoch_origin_s,
        snapshot.expected_timestamp_s,
        tuple(snapshot.integral_Nm),
        tuple(snapshot.derivative_filtered_rad_s2),
        tuple(snapshot.previous_rate_rad_s),
        snapshot.has_previous_rate,
        tuple(held.requested_torque_body_Nm),
        tuple(held.limited_torque_body_Nm),
        tuple(held.saturated),
        held.timestamp_s,
        held.epoch_id,
        diagnostics.accepted,
        diagnostics.reason,
        diagnostics.epoch_id,
        diagnostics.tick_index,
    )


def test_real_g2a_g1_adapter_and_actuator_consumption():
    adapter, actuator, reset_command, feedback = reset_fixture()
    assert isinstance(reset_command, TorqueCommand)
    assert type(reset_command).__module__ == "b0.contract"
    estimate = StateEstimate((1, 0, 0, 0), (0, 0, 0), 0.005, True)
    output = adapter.step(Command(), estimate, feedback, 0.005)
    assert isinstance(output, TorqueCommand)
    assert type(output).__module__ == "b0.contract"
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


def test_missing_frozen_field_is_atomic_and_valid_retry_succeeds():
    adapter, _, _, feedback = reset_fixture()
    estimate = StateEstimate((1, 0, 0, 0), (0, 0, 0), 0.005, True)

    class MissingQuaternionCommand:
        timestamp_s = 0.005
        valid = True

    before = adapter.core.snapshot()
    with pytest.raises(adapter_module.ControllerConfigurationError):
        adapter.step(MissingQuaternionCommand(), estimate, feedback, 0.005)
    after = adapter.core.snapshot()
    assert after.tick_index == before.tick_index
    assert after.expected_timestamp_s == before.expected_timestamp_s
    assert adapter.step(Command(), estimate, feedback, 0.005).timestamp_s == 0.005


@pytest.mark.parametrize("value", [1.5, True, -1, 2**63])
def test_reset_epoch_type_and_range_are_not_coerced(value):
    adapter = adapter_module.ControllerAdapter()

    class Epoch:
        id = value
        timestamp_s = 0.0

    with pytest.raises(ValueError):
        adapter.reset(Epoch())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("command_timestamp", np.complex128(0.005 + 123.0j)),
        ("estimate_timestamp", np.bool_(True)),
        ("dt", Fraction(1, 3)),
        ("command_quaternion", np.complex128(1.0 + 2.0j)),
        ("estimate_rate", np.bool_(True)),
        ("feedback_torque", np.int64(2**53 + 1)),
    ],
)
def test_adapter_rejects_nonreal_bool_and_lossy_scalars_without_state_change(
    field, value
):
    adapter, _, _, feedback = reset_fixture()

    class MutableCommand:
        q_nb_command = [1.0, 0.0, 0.0, 0.0]
        timestamp_s = 0.005
        valid = True

    class MutableEstimate:
        q_nb_estimate = [1.0, 0.0, 0.0, 0.0]
        omega_b_estimate_rad_s = [0.0, 0.0, 0.0]
        timestamp_s = 0.005
        valid = True

    class MutableFeedback:
        actual_torque_body_Nm = feedback.actual_torque_body_Nm.tolist()
        limited_torque_body_Nm = feedback.limited_torque_body_Nm.tolist()
        saturated = feedback.saturated.tolist()
        timestamp_s = feedback.timestamp_s
        command_timestamp_s = feedback.command_timestamp_s

    command = MutableCommand()
    estimate = MutableEstimate()
    feedback_input = MutableFeedback()
    dt_s = 0.005
    if field == "command_timestamp":
        command.timestamp_s = value
    elif field == "estimate_timestamp":
        estimate.timestamp_s = value
    elif field == "dt":
        dt_s = value
    elif field == "command_quaternion":
        command.q_nb_command[0] = value
    elif field == "estimate_rate":
        estimate.omega_b_estimate_rad_s[0] = value
    elif field == "feedback_torque":
        feedback_input.actual_torque_body_Nm[0] = value

    before = snapshot_value(adapter.core.snapshot())
    with pytest.raises((TypeError, ValueError, OverflowError)):
        adapter.step(command, estimate, feedback_input, dt_s)
    assert snapshot_value(adapter.core.snapshot()) == before
