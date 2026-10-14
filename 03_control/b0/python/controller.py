"""Validated configuration loader and frozen-message adapters for G2-B."""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import math
import numbers
import os
import sys
from pathlib import Path


class ControllerConfigurationError(ValueError):
    pass


def _strict_bool(value, name):
    if type(value) is not bool:
        raise ControllerConfigurationError(f"{name} must be bool")
    return value


def _strict_int64(value, name):
    if isinstance(value, bool) or not isinstance(value, numbers.Integral):
        raise ControllerConfigurationError(f"{name} must be an integer")
    value = int(value)
    if value < 0 or value > 2**63 - 1:
        raise ControllerConfigurationError(f"{name} outside signed int64 range")
    return value


def _strict_float(value, name):
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise ControllerConfigurationError(f"{name} must be a real scalar")
    value = float(value)
    if not math.isfinite(value):
        raise ControllerConfigurationError(f"{name} must be finite")
    return value


def _canonical(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ControllerConfigurationError(f"cannot load {path}: {exc}") from exc


def load_controller_parameters(module=None, track: Path | None = None):
    track = (track or Path(__file__).resolve().parents[1]).resolve()
    repo = track.parents[1]
    design_path = track / "configs/b0_g2_controller.v1.json"
    approval_path = track / "configs/b0_g2_controller_approval.v1.json"
    g0_path = repo / "05_integration/b0/configs/b0_g0_contract.v2.json"
    design, approval = _json(design_path), _json(approval_path)
    design_digest = hashlib.sha256(_canonical(design_path.read_bytes())).hexdigest()
    if approval.get("decision") != "DESIGN_ACCEPT" or design_digest != approval.get(
        "approved_config_canonical_lf_sha256"
    ):
        raise ControllerConfigurationError(
            "implementation configuration is not the approved S0 byte identity"
        )
    authority = design.get("authority", {})
    if hashlib.sha256(_canonical(g0_path.read_bytes())).hexdigest() != authority.get(
        "g0_canonical_lf_sha256"
    ):
        raise ControllerConfigurationError("G0 canonical digest mismatch")
    validator_path = repo / authority.get("validator_path", "")
    spec = importlib.util.spec_from_file_location("b0_g2b_g0_validator", validator_path)
    if spec is None or spec.loader is None:
        raise ControllerConfigurationError("authoritative G0 validator unavailable")
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)
    g0 = validator.load_config(g0_path)
    validator.validate_config(g0)
    if module is None:
        module_dir = os.environ.get("B0_CONTROLLER_MODULE_DIR")
        if module_dir:
            import sys

            sys.path.insert(0, module_dir)
        module = importlib.import_module("b0_controller")
    p = module.ControllerParameters()
    control, actuator, timing = (
        g0["controller_contract"],
        g0["actuator_contract"],
        g0["timing"],
    )
    p.attitude_kp = control["attitude_kp"]["initial"]
    p.rate_kp = control["rate_pid"]["kp"]["initial"]
    p.rate_ki = control["rate_pid"]["ki"]["initial"]
    p.rate_kd = control["rate_pid"]["kd"]["initial"]
    p.integral_limit_Nm = control["rate_pid"]["integrator_limit_Nm"]
    p.rate_limit_rad_s = control["body_rate_target_limit_rad_s"]
    p.torque_limit_Nm = actuator["limits_Nm"]
    p.kaw_limit_per_s = actuator["antiwindup"]["limit_feedback"]["gain_per_s"]
    p.kaw_lag_per_s = actuator["antiwindup"]["actuator_lag_feedback"]["gain_per_s"]
    p.derivative_time_constant_s = control["rate_pid"]["derivative_filter"][
        "time_constant_s"
    ]
    p.controller_period_s = (
        timing["base_period_s"] * timing["schedules"]["controller_every_ticks"]
    )
    p.timestamp_tolerance_s = design["numeric_policy"]["timestamp_absolute_tolerance_s"]
    p.quaternion_norm_tolerance = g0["conventions"]["quaternion"]["unit_norm_tolerance"]
    return p


class ControllerAdapter:
    def __init__(self, module=None):
        self.module = module or importlib.import_module("b0_controller")
        self.parameters = load_controller_parameters(self.module)
        self.core = self.module.CascadedController(self.parameters)
        self.epoch_id = None
        repo = Path(__file__).resolve().parents[3]
        if "contract" in sys.modules:
            self.g1_contract = sys.modules["contract"]
        else:
            spec = importlib.util.spec_from_file_location(
                "contract", repo / "01_simulation/b0/contract.py"
            )
            if spec is None or spec.loader is None:
                raise ControllerConfigurationError("G1 contract module unavailable")
            self.g1_contract = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = self.g1_contract
            spec.loader.exec_module(self.g1_contract)

    def _to_g1(self, output):
        return self.g1_contract.TorqueCommand(
            output.requested_torque_body_Nm,
            output.limited_torque_body_Nm,
            output.timestamp_s,
            output.saturated,
            limits_Nm=self.parameters.torque_limit_Nm,
        )

    def reset(self, reset_epoch):
        epoch = self.module.ResetEpoch()
        epoch.id = _strict_int64(reset_epoch.id, "reset_epoch.id")
        epoch.timestamp_s = _strict_float(
            reset_epoch.timestamp_s, "reset_epoch.timestamp_s"
        )
        output = self.core.reset(self.module.ControllerInitialState(), epoch)
        self.epoch_id = epoch.id
        return self._to_g1(output)

    def step(self, attitude_command, state_estimate, actuator_feedback, dt_s):
        if self.epoch_id is None:
            raise ControllerConfigurationError("adapter has no active reset epoch")
        q = self.module.AttitudeCommand()
        q.q_nb = list(attitude_command.q_nb_command)
        q.timestamp_s = _strict_float(
            attitude_command.timestamp_s, "attitude_command.timestamp_s"
        )
        q.valid = _strict_bool(attitude_command.valid, "attitude_command.valid")
        q.epoch_id = self.epoch_id
        s = self.module.StateEstimate()
        s.q_nb = list(state_estimate.q_nb_estimate)
        s.omega_b_rad_s = list(state_estimate.omega_b_estimate_rad_s)
        s.timestamp_s = _strict_float(
            state_estimate.timestamp_s, "state_estimate.timestamp_s"
        )
        s.valid = _strict_bool(state_estimate.valid, "state_estimate.valid")
        s.epoch_id = self.epoch_id
        f = self.module.ActuatorFeedback()
        f.actual_torque_body_Nm = list(actuator_feedback.actual_torque_body_Nm)
        f.limited_torque_body_Nm = list(actuator_feedback.limited_torque_body_Nm)
        f.saturated = list(actuator_feedback.saturated)
        f.timestamp_s = _strict_float(
            actuator_feedback.timestamp_s, "actuator_feedback.timestamp_s"
        )
        f.command_timestamp_s = _strict_float(
            actuator_feedback.command_timestamp_s,
            "actuator_feedback.command_timestamp_s",
        )
        f.epoch_id = self.epoch_id
        output = self.core.step(q, s, f, _strict_float(dt_s, "dt_s"))
        return self._to_g1(output)
