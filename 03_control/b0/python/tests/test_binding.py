import importlib
import math
import os
import sys
import warnings
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

module_dir = Path(os.environ["B0_CONTROLLER_MODULE_DIR"]).resolve()
sys.path.insert(0, str(module_dir))
c = importlib.import_module("b0_controller")
assert module_dir in Path(c.__file__).resolve().parents


def parameters():
    p = c.ControllerParameters()
    p.attitude_kp = [4.0, 4.0, 2.5]
    p.rate_kp = [0.08, 0.08, 0.06]
    p.rate_ki = [0.02, 0.02, 0.015]
    p.rate_kd = [0.004, 0.004, 0.003]
    p.integral_limit_Nm = [0.15, 0.15, 0.1]
    p.rate_limit_rad_s = [2.0, 2.0, 1.5]
    p.torque_limit_Nm = [0.35, 0.35, 0.2]
    p.kaw_limit_per_s = [8.0, 8.0, 8.0]
    p.kaw_lag_per_s = [2.0, 2.0, 2.0]
    p.derivative_time_constant_s = 0.02
    p.controller_period_s = 0.005
    p.timestamp_tolerance_s = 1e-12
    p.quaternion_norm_tolerance = 1e-6
    return p


def reset(controller, epoch=0, time=0.0):
    value = c.ResetEpoch()
    value.id = epoch
    value.timestamp_s = time
    return controller.reset(c.ControllerInitialState(), value)


def inputs(time, held, epoch=0, *, q=None, rate=None, actual=None):
    command = c.AttitudeCommand()
    command.q_nb = q or [1.0, 0.0, 0.0, 0.0]
    command.timestamp_s = time
    command.valid = True
    command.epoch_id = epoch
    estimate = c.StateEstimate()
    estimate.q_nb = [1.0, 0.0, 0.0, 0.0]
    estimate.omega_b_rad_s = rate or [0.0, 0.0, 0.0]
    estimate.timestamp_s = time
    estimate.valid = True
    estimate.epoch_id = epoch
    feedback = c.ActuatorFeedback()
    feedback.actual_torque_body_Nm = actual or [0.0, 0.0, 0.0]
    feedback.limited_torque_body_Nm = held.limited_torque_body_Nm
    feedback.saturated = held.saturated
    feedback.timestamp_s = time
    feedback.command_timestamp_s = held.timestamp_s
    feedback.epoch_id = epoch
    return command, estimate, feedback


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
        tuple(diagnostics.rate_error_rad_s),
        tuple(diagnostics.derivative_raw_rad_s2),
        tuple(diagnostics.derivative_filtered_rad_s2),
        tuple(diagnostics.proportional_Nm),
        tuple(diagnostics.integral_before_Nm),
        tuple(diagnostics.derivative_Nm),
        tuple(diagnostics.conditional_integral_rate_Nm_s),
        tuple(diagnostics.limit_backcalculation_rate_Nm_s),
        tuple(diagnostics.lag_backcalculation_rate_Nm_s),
        tuple(diagnostics.integral_after_Nm),
        tuple(diagnostics.requested_Nm),
        tuple(diagnostics.limited_Nm),
        tuple(diagnostics.saturated),
        diagnostics.epoch_id,
        diagnostics.tick_index,
    )


def test_cpp_python_parity_and_module_identity():
    controller = c.CascadedController(parameters())
    held = reset(controller, epoch=7, time=10.0)
    angle = 0.1
    q = [math.cos(angle / 2.0), math.sin(angle / 2.0), 0.0, 0.0]
    command, estimate, feedback = inputs(10.005, held, 7, q=q)
    output = controller.step(command, estimate, feedback, 0.005)
    expected = 0.08 * 4.0 * 2.0 * math.sin(angle / 2.0)
    assert output.requested_torque_body_Nm[0] == pytest.approx(expected, rel=0.0, abs=1e-12)
    assert output.timestamp_s == 10.005
    assert output.epoch_id == 7
    assert Path(c.__file__).resolve().parent == module_dir


def test_complete_diagnostics_and_snapshot_are_read_only_copies():
    controller = c.CascadedController(parameters())
    held = reset(controller)
    command, estimate, feedback = inputs(
        0.005,
        held,
        q=[math.cos(0.05), math.sin(0.05), 0.0, 0.0],
        rate=[0.1, 0.0, 0.0],
        actual=[0.005, 0.0, 0.0],
    )
    output = controller.step(command, estimate, feedback, 0.005)
    diagnostics = controller.last_diagnostics()
    expected_fields = {
        "accepted",
        "reason",
        "rate_error_rad_s",
        "derivative_raw_rad_s2",
        "derivative_filtered_rad_s2",
        "proportional_Nm",
        "integral_before_Nm",
        "derivative_Nm",
        "conditional_integral_rate_Nm_s",
        "limit_backcalculation_rate_Nm_s",
        "lag_backcalculation_rate_Nm_s",
        "integral_after_Nm",
        "requested_Nm",
        "limited_Nm",
        "saturated",
        "epoch_id",
        "tick_index",
    }
    assert expected_fields <= set(dir(diagnostics))
    assert diagnostics.accepted is True
    assert diagnostics.reason == "accepted"
    assert diagnostics.requested_Nm == output.requested_torque_body_Nm
    before = snapshot_value(controller.snapshot())
    copied_integral = controller.snapshot().integral_Nm
    copied_integral[0] = 999.0
    copied_output = output.limited_torque_body_Nm
    copied_output[0] = 999.0
    assert snapshot_value(controller.snapshot()) == before
    with pytest.raises(AttributeError):
        controller.snapshot().tick_index = 99


def test_contract_error_exposes_stable_reason_and_atomic_retry():
    controller = c.CascadedController(parameters())
    held = reset(controller)
    command, estimate, feedback = inputs(0.005, held)
    estimate.valid = False
    before = snapshot_value(controller.snapshot())
    with pytest.raises(c.ControllerContractError) as caught:
        controller.step(command, estimate, feedback, 0.005)
    assert caught.value.reason == "invalid_estimate"
    assert str(caught.value).startswith("invalid_estimate:")
    assert snapshot_value(controller.snapshot()) == before
    estimate.valid = True
    assert controller.step(command, estimate, feedback, 0.005).timestamp_s == 0.005
    accepted = snapshot_value(controller.snapshot())
    next_command, next_estimate, next_feedback = inputs(0.010, controller.snapshot().expected_held_command)
    next_estimate.valid = False
    with pytest.raises(c.ControllerContractError) as second:
        controller.step(next_command, next_estimate, next_feedback, 0.005)
    assert second.value.reason == "invalid_estimate"
    assert snapshot_value(controller.snapshot()) == accepted
    assert controller.last_diagnostics().accepted is True
    assert controller.last_diagnostics().reason == "accepted"


@pytest.mark.parametrize(
    ("factory", "attribute", "value"),
    [
        (c.AttitudeCommand, "q_nb", [1.0, 0.0, 0.0]),
        (c.AttitudeCommand, "q_nb", [1.0, 0.0, 0.0, True]),
        (c.AttitudeCommand, "q_nb", [[1.0], [0.0], [0.0], [0.0]]),
        (c.AttitudeCommand, "q_nb", np.array([[1.0], [0.0], [0.0], [0.0]])),
        (c.AttitudeCommand, "q_nb", "1000"),
        (c.AttitudeCommand, "timestamp_s", "0.005"),
        (c.AttitudeCommand, "timestamp_s", float("inf")),
        (c.AttitudeCommand, "valid", 1),
        (c.AttitudeCommand, "epoch_id", True),
        (c.AttitudeCommand, "epoch_id", 1.5),
        (c.StateEstimate, "omega_b_rad_s", [0.0, 0.0]),
        (c.StateEstimate, "omega_b_rad_s", [[0.0], [0.0], [0.0]]),
        (c.StateEstimate, "omega_b_rad_s", np.zeros((3, 1))),
        (c.StateEstimate, "omega_b_rad_s", [0.0, float("nan"), 0.0]),
        (c.ActuatorFeedback, "saturated", [False, 0, False]),
        (c.ActuatorFeedback, "saturated", [False, False]),
        (c.ActuatorFeedback, "actual_torque_body_Nm", [0.0, False, 0.0]),
    ],
)
def test_binding_rejects_wrong_shape_type_and_nonfinite(factory, attribute, value):
    instance = factory()
    with pytest.raises((TypeError, ValueError, OverflowError)):
        setattr(instance, attribute, value)


@pytest.mark.parametrize(
    "value",
    [
        True,
        np.bool_(True),
        0.005 + 123.0j,
        np.complex64(0.005 + 123.0j),
        np.complex128(0.005 + 123.0j),
        Fraction(1, 3),
        2**53 + 1,
        np.int64(2**53 + 1),
    ],
)
def test_scalar_binding_rejects_nonreal_bool_and_lossy_coercion_atomically(value):
    epoch = c.ResetEpoch()
    epoch.timestamp_s = 0.125
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises((TypeError, ValueError, OverflowError)):
            epoch.timestamp_s = value
    assert caught == []
    assert epoch.timestamp_s == 0.125


@pytest.mark.parametrize(
    "value",
    [
        [np.bool_(True), 0.0, 0.0, 0.0],
        [np.complex128(1.0 + 2.0j), 0.0, 0.0, 0.0],
        [Fraction(1, 3), 0.0, 0.0, 0.0],
        [np.int64(2**53 + 1), 0.0, 0.0, 0.0],
    ],
)
def test_vector_binding_rejects_nonreal_bool_and_lossy_elements_atomically(value):
    command = c.AttitudeCommand()
    command.q_nb = [1.0, 0.0, 0.0, 0.0]
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises((TypeError, ValueError, OverflowError)):
            command.q_nb = value
    assert caught == []
    assert command.q_nb == [1.0, 0.0, 0.0, 0.0]


@pytest.mark.parametrize(
    "value",
    [
        0,
        1,
        -1,
        0.125,
        np.int64(7),
        np.float32(0.125),
        np.float64(0.125),
        Fraction(1, 2),
    ],
)
def test_scalar_binding_accepts_losslessly_representable_real_scalars(value):
    epoch = c.ResetEpoch()
    epoch.timestamp_s = value
    assert epoch.timestamp_s == float(value)


@pytest.mark.parametrize(
    "invalid_dt",
    [
        True,
        np.bool_(True),
        0.005 + 123.0j,
        np.complex128(0.005 + 123.0j),
        Fraction(1, 3),
        2**53 + 1,
        np.int64(2**53 + 1),
    ],
)
def test_step_rejects_nonreal_bool_and_lossy_dt_atomically_then_retries(
    invalid_dt,
):
    controller = c.CascadedController(parameters())
    clean_twin = c.CascadedController(parameters())
    held = reset(controller)
    clean_held = reset(clean_twin)
    command, estimate, feedback = inputs(0.005, held)
    clean_command, clean_estimate, clean_feedback = inputs(0.005, clean_held)
    before = snapshot_value(controller.snapshot())

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises((TypeError, ValueError, OverflowError)) as rejected:
            controller.step(command, estimate, feedback, invalid_dt)
    assert not isinstance(rejected.value, c.ControllerContractError)
    assert caught == []
    assert snapshot_value(controller.snapshot()) == before

    retried = controller.step(command, estimate, feedback, 0.005)
    clean = clean_twin.step(
        clean_command, clean_estimate, clean_feedback, 0.005
    )
    assert retried.requested_torque_body_Nm == clean.requested_torque_body_Nm
    assert retried.limited_torque_body_Nm == clean.limited_torque_body_Nm
    assert retried.saturated == clean.saturated
    assert retried.timestamp_s == clean.timestamp_s
    assert retried.epoch_id == clean.epoch_id
    assert snapshot_value(controller.snapshot()) == snapshot_value(
        clean_twin.snapshot()
    )


def test_integer_bounds_and_input_copy():
    epoch = c.ResetEpoch()
    epoch.id = 2**63 - 1
    assert epoch.id == 2**63 - 1
    epoch.id = -(2**63)
    assert epoch.id == -(2**63)
    for value in (2**63, -(2**63) - 1):
        with pytest.raises((TypeError, OverflowError)):
            epoch.id = value

    command = c.AttitudeCommand()
    source = [1.0, 0.0, 0.0, 0.0]
    command.q_nb = source
    source[0] = 0.0
    assert command.q_nb == [1.0, 0.0, 0.0, 0.0]
    returned = command.q_nb
    returned[0] = 0.0
    assert command.q_nb == [1.0, 0.0, 0.0, 0.0]


def test_invalid_output_feedback_is_atomic():
    controller = c.CascadedController(parameters())
    held = reset(controller)
    command, estimate, feedback = inputs(0.005, held)
    feedback.actual_torque_body_Nm = [0.36, 0.0, 0.0]
    before = snapshot_value(controller.snapshot())
    with pytest.raises(c.ControllerContractError) as caught:
        controller.step(command, estimate, feedback, 0.005)
    assert caught.value.reason == "invalid_feedback"
    assert snapshot_value(controller.snapshot()) == before
