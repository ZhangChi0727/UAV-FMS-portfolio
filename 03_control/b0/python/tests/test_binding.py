import importlib
import os
import sys
from pathlib import Path

import pytest

module_dir = Path(os.environ["B0_CONTROLLER_MODULE_DIR"]).resolve()
sys.path.insert(0, str(module_dir))
c = importlib.import_module("b0_controller")
assert module_dir in Path(c.__file__).resolve().parents


def parameters():
    p = c.ControllerParameters()
    p.attitude_kp = [4, 4, 2.5]
    p.rate_kp = [0.08, 0.08, 0.06]
    p.rate_ki = [0.02, 0.02, 0.015]
    p.rate_kd = [0.004, 0.004, 0.003]
    p.integral_limit_Nm = [0.15, 0.15, 0.1]
    p.rate_limit_rad_s = [2, 2, 1.5]
    p.torque_limit_Nm = [0.35, 0.35, 0.2]
    p.kaw_limit_per_s = [8, 8, 8]
    p.kaw_lag_per_s = [2, 2, 2]
    p.derivative_time_constant_s = 0.02
    p.controller_period_s = 0.005
    p.timestamp_tolerance_s = 1e-12
    p.quaternion_norm_tolerance = 1e-6
    return p


def reset(controller, epoch=0, time=0.0):
    e = c.ResetEpoch()
    e.id = epoch
    e.timestamp_s = time
    return controller.reset(c.ControllerInitialState(), e)


def inputs(time, held, epoch=0):
    q = c.AttitudeCommand()
    q.q_nb = [1, 0, 0, 0]
    q.timestamp_s = time
    q.valid = True
    q.epoch_id = epoch
    s = c.StateEstimate()
    s.q_nb = [1, 0, 0, 0]
    s.omega_b_rad_s = [0, 0, 0]
    s.timestamp_s = time
    s.valid = True
    s.epoch_id = epoch
    f = c.ActuatorFeedback()
    f.actual_torque_body_Nm = [0, 0, 0]
    f.limited_torque_body_Nm = held.limited_torque_body_Nm
    f.saturated = held.saturated
    f.timestamp_s = time
    f.command_timestamp_s = held.timestamp_s
    f.epoch_id = epoch
    return q, s, f


def test_module_identity_and_g0_step_shape():
    controller = c.CascadedController(parameters())
    held = reset(controller)
    q, s, f = inputs(0.005, held)
    out = controller.step(q, s, f, 0.005)
    assert out.timestamp_s == 0.005 and out.requested_torque_body_Nm == [0, 0, 0]


def test_invalid_is_atomic_and_retry_uses_expected_held():
    controller = c.CascadedController(parameters())
    held = reset(controller)
    q, s, f = inputs(0.005, held)
    f.actual_torque_body_Nm = [0.36, 0, 0]
    with pytest.raises(ValueError):
        controller.step(q, s, f, 0.005)
    f.actual_torque_body_Nm = [0, 0, 0]
    assert controller.step(q, s, f, 0.005).timestamp_s == 0.005


def test_int64_overflow_rejected_by_binding():
    e = c.ResetEpoch()
    with pytest.raises(TypeError):
        e.id = 2**80
