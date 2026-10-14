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
    if not isinstance(value, bool):
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


def _strict_bool_vector(value, name):
    if hasattr(value, "tolist"):
        value = value.tolist()
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ControllerConfigurationError(f"{name} must be a length-three bool vector")
    if any(not isinstance(item, bool) for item in value):
        raise ControllerConfigurationError(f"{name} must contain only bool values")
    return list(value)


def _required_attribute(value, name):
    try:
        return getattr(value, name)
    except AttributeError as exc:
        raise ControllerConfigurationError(f"missing frozen message field: {name}") from exc


def _load_g1_contract(repo: Path):
    package_dir = (repo / "01_simulation/b0").resolve()
    package_file = package_dir / "__init__.py"
    package_parent = str(package_dir.parent)
    if package_parent not in sys.path:
        sys.path.insert(0, package_parent)
    try:
        package = importlib.import_module("b0")
        contract = importlib.import_module("b0.contract")
    except (ImportError, OSError) as exc:
        raise ControllerConfigurationError("G1 public package is unavailable") from exc
    package_origin = getattr(package, "__file__", None)
    contract_origin = getattr(contract, "__file__", None)
    if (
        package_origin is None
        or Path(package_origin).resolve() != package_file
        or contract_origin is None
        or Path(contract_origin).resolve() != package_dir / "contract.py"
        or getattr(package, "TorqueCommand", None) is not contract.TorqueCommand
    ):
        raise ControllerConfigurationError(
            "G1 public package identity does not match 01_simulation/b0"
        )
    return contract


def _canonical(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _canonical_file(path: Path, label: str) -> bytes:
    try:
        return _canonical(path.read_bytes())
    except OSError as exc:
        raise ControllerConfigurationError(f"cannot read {label}: {path}") from exc


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
    if design.get("schema_version") != "1.0" or design.get("component") != (
        "b0_g2_cascaded_controller"
    ):
        raise ControllerConfigurationError("unsupported implementation configuration identity")
    if approval.get("schema_version") != "1.0" or approval.get("component") != (
        "b0_g2_cascaded_controller"
    ):
        raise ControllerConfigurationError("unsupported approval overlay identity")
    design_digest = hashlib.sha256(
        _canonical_file(design_path, "implementation configuration")
    ).hexdigest()
    if approval.get("decision") != "DESIGN_ACCEPT" or design_digest != approval.get(
        "approved_config_canonical_lf_sha256"
    ):
        raise ControllerConfigurationError(
            "implementation configuration is not the approved S0 byte identity"
        )
    authority = design.get("authority", {})
    if hashlib.sha256(_canonical_file(g0_path, "G0 contract")).hexdigest() != authority.get(
        "g0_canonical_lf_sha256"
    ):
        raise ControllerConfigurationError("G0 canonical digest mismatch")
    validator_path = repo / authority.get("validator_path", "")
    spec = importlib.util.spec_from_file_location("b0_g2b_g0_validator", validator_path)
    if spec is None or spec.loader is None:
        raise ControllerConfigurationError("authoritative G0 validator unavailable")
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)
    try:
        g0 = validator.load_config(g0_path)
        validator.validate_config(g0)
    except Exception as exc:
        raise ControllerConfigurationError("authoritative G0 validation failed") from exc
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
    try:
        module.CascadedController(p)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ControllerConfigurationError("loaded controller parameters are invalid") from exc
    return p


class ControllerAdapter:
    def __init__(self, module=None):
        self.module = module or importlib.import_module("b0_controller")
        self.parameters = load_controller_parameters(self.module)
        self.core = self.module.CascadedController(self.parameters)
        self.epoch_id = None
        repo = Path(__file__).resolve().parents[3]
        self.g1_contract = _load_g1_contract(repo)

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
        epoch.id = _strict_int64(
            _required_attribute(reset_epoch, "id"), "reset_epoch.id"
        )
        epoch.timestamp_s = _strict_float(
            _required_attribute(reset_epoch, "timestamp_s"),
            "reset_epoch.timestamp_s",
        )
        output = self.core.reset(self.module.ControllerInitialState(), epoch)
        self.epoch_id = epoch.id
        return self._to_g1(output)

    def step(self, attitude_command, state_estimate, actuator_feedback, dt_s):
        if self.epoch_id is None:
            raise ControllerConfigurationError("adapter has no active reset epoch")
        q = self.module.AttitudeCommand()
        q.q_nb = list(_required_attribute(attitude_command, "q_nb_command"))
        q.timestamp_s = _strict_float(
            _required_attribute(attitude_command, "timestamp_s"),
            "attitude_command.timestamp_s",
        )
        q.valid = _strict_bool(
            _required_attribute(attitude_command, "valid"), "attitude_command.valid"
        )
        q.epoch_id = self.epoch_id
        s = self.module.StateEstimate()
        s.q_nb = list(_required_attribute(state_estimate, "q_nb_estimate"))
        s.omega_b_rad_s = list(
            _required_attribute(state_estimate, "omega_b_estimate_rad_s")
        )
        s.timestamp_s = _strict_float(
            _required_attribute(state_estimate, "timestamp_s"),
            "state_estimate.timestamp_s",
        )
        s.valid = _strict_bool(
            _required_attribute(state_estimate, "valid"), "state_estimate.valid"
        )
        s.epoch_id = self.epoch_id
        f = self.module.ActuatorFeedback()
        f.actual_torque_body_Nm = list(
            _required_attribute(actuator_feedback, "actual_torque_body_Nm")
        )
        f.limited_torque_body_Nm = list(
            _required_attribute(actuator_feedback, "limited_torque_body_Nm")
        )
        f.saturated = _strict_bool_vector(
            _required_attribute(actuator_feedback, "saturated"),
            "actuator_feedback.saturated",
        )
        f.timestamp_s = _strict_float(
            _required_attribute(actuator_feedback, "timestamp_s"),
            "actuator_feedback.timestamp_s",
        )
        f.command_timestamp_s = _strict_float(
            _required_attribute(actuator_feedback, "command_timestamp_s"),
            "actuator_feedback.command_timestamp_s",
        )
        f.epoch_id = self.epoch_id
        output = self.core.step(q, s, f, _strict_float(dt_s, "dt_s"))
        return self._to_g1(output)
