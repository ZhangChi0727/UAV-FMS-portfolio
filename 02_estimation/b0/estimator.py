"""B0 G2-A deterministic six-axis attitude estimator.

Only explicit reset state and IMU samples enter this component.  Plant truth,
scenario event labels and true sensor errors are intentionally absent.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from typing import Any

import numpy as np


class EstimatorContractError(ValueError):
    """Configuration, reset or sample violates the accepted G2-A contract."""

    def __init__(self, message: str, diagnostics: "EstimatorDiagnostics | None" = None) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics


def _scalar(value: Any, name: str) -> float:
    if isinstance(value, (bool, np.bool_)):
        raise EstimatorContractError(f"{name} must be a finite scalar")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise EstimatorContractError(f"{name} must be a finite scalar") from exc
    if not math.isfinite(result):
        raise EstimatorContractError(f"{name} must be a finite scalar")
    return result


def _integer(value: Any, name: str) -> int:
    if isinstance(value, (bool, np.bool_)):
        raise EstimatorContractError(f"{name} must be a non-negative integer")
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise EstimatorContractError(f"{name} must be a non-negative integer") from exc
    if result < 0 or result != value:
        raise EstimatorContractError(f"{name} must be a non-negative integer")
    return result


def _vector(value: Any, length: int, name: str) -> np.ndarray:
    try:
        result = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise EstimatorContractError(f"{name} must be a finite length-{length} vector") from exc
    if result.shape != (length,) or not np.all(np.isfinite(result)):
        raise EstimatorContractError(f"{name} must be a finite length-{length} vector")
    return result.copy()


def _canonical_lf_digest(path: Path) -> str:
    content = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(content).hexdigest()


def _canonicalize(q: np.ndarray) -> np.ndarray:
    result = np.asarray(q, dtype=np.float64).copy()
    if result[0] < 0.0:
        result *= -1.0
    elif result[0] == 0.0:
        for component in result[1:]:
            if component != 0.0:
                if component < 0.0:
                    result *= -1.0
                break
    return result


def _normalize(q: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(q))
    if not math.isfinite(norm) or norm == 0.0:
        raise EstimatorContractError("quaternion must have finite non-zero norm")
    return _canonicalize(q / norm)


def _multiply(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    lw, lx, ly, lz = left
    rw, rx, ry, rz = right
    return np.array(
        [
            lw * rw - lx * rx - ly * ry - lz * rz,
            lw * rx + lx * rw + ly * rz - lz * ry,
            lw * ry - lx * rz + ly * rw + lz * rx,
            lw * rz + lx * ry - ly * rx + lz * rw,
        ],
        dtype=np.float64,
    )


def _rotation_quaternion(rotation_vector: np.ndarray) -> np.ndarray:
    angle = float(np.linalg.norm(rotation_vector))
    half = 0.5 * angle
    if angle < 1e-8:
        scale = 0.5 - angle * angle / 48.0 + angle**4 / 3840.0
    else:
        scale = math.sin(half) / angle
    return np.array([math.cos(half), *(scale * rotation_vector)], dtype=np.float64)


def _rotate_ned_to_body(q_nb: np.ndarray, vector_n: np.ndarray) -> np.ndarray:
    vector_q = np.array([0.0, *vector_n], dtype=np.float64)
    conjugate = q_nb * np.array([1.0, -1.0, -1.0, -1.0])
    return _multiply(_multiply(conjugate, vector_q), q_nb)[1:]


def _magnitude_clamp(vector: np.ndarray, limit: float) -> tuple[np.ndarray, bool]:
    norm = float(np.linalg.norm(vector))
    if norm <= limit:
        return vector.copy(), False
    return vector * (limit / norm), True


@dataclass(frozen=True, init=False)
class EstimatorInitialState:
    _q_nb: np.ndarray
    _omega_b_rad_s: np.ndarray

    def __init__(self, q_nb: Any, omega_b_rad_s: Any) -> None:
        object.__setattr__(self, "_q_nb", _vector(q_nb, 4, "q_nb"))
        object.__setattr__(self, "_omega_b_rad_s", _vector(omega_b_rad_s, 3, "omega_b_rad_s"))

    @property
    def q_nb(self) -> np.ndarray:
        return self._q_nb.copy()

    @property
    def omega_b_rad_s(self) -> np.ndarray:
        return self._omega_b_rad_s.copy()


@dataclass(frozen=True)
class ResetEpoch:
    id: int
    timestamp_s: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _integer(self.id, "reset_epoch.id"))
        object.__setattr__(self, "timestamp_s", _scalar(self.timestamp_s, "reset_epoch.timestamp_s"))


@dataclass(frozen=True, init=False)
class StateEstimate:
    _q_nb_estimate: np.ndarray
    _omega_b_estimate_rad_s: np.ndarray
    timestamp_s: float
    valid: bool

    def __init__(self, q_nb_estimate: Any, omega_b_estimate_rad_s: Any, timestamp_s: Any, valid: bool = True) -> None:
        object.__setattr__(self, "_q_nb_estimate", _vector(q_nb_estimate, 4, "q_nb_estimate"))
        object.__setattr__(self, "_omega_b_estimate_rad_s", _vector(omega_b_estimate_rad_s, 3, "omega_b_estimate_rad_s"))
        object.__setattr__(self, "timestamp_s", _scalar(timestamp_s, "timestamp_s"))
        if not isinstance(valid, (bool, np.bool_)):
            raise EstimatorContractError("valid must be boolean")
        object.__setattr__(self, "valid", bool(valid))

    @property
    def q_nb_estimate(self) -> np.ndarray:
        return self._q_nb_estimate.copy()

    @property
    def omega_b_estimate_rad_s(self) -> np.ndarray:
        return self._omega_b_estimate_rad_s.copy()


@dataclass(frozen=True)
class EstimatorDiagnostics:
    accepted: bool
    reason: str
    correction_eligible: bool = False
    correction_applied: bool = False
    correction_capped: bool = False
    elapsed_periods: int = 0
    missing_periods: int = 0
    gap_approximated: bool = False


@dataclass(frozen=True)
class EstimatorStepResult:
    estimate: StateEstimate
    diagnostics: EstimatorDiagnostics


@dataclass(frozen=True)
class EstimatorParameters:
    sample_period_s: float
    gravity_m_s2: float
    unit_norm_tolerance: float
    correction_gain_per_s: float
    accelerometer_gate_deviation_m_s2: float
    maximum_correction_step_rad: float
    timestamp_tolerance_s: float
    config_path: str
    g0_config_path: str


def _authoritative_validate(g0_path: Path) -> dict[str, Any]:
    validator_path = g0_path.parents[1] / "validate_config.py"
    spec = importlib.util.spec_from_file_location("b0_g0_estimator_validator", validator_path)
    if spec is None or spec.loader is None:
        raise EstimatorContractError("cannot load authoritative G0 validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    document = module.load_config(g0_path)
    module.validate_config(document)
    return document


def load_estimator_parameters(config_path: str | Path | None = None) -> EstimatorParameters:
    track = Path(__file__).resolve().parent
    candidate_path = Path(config_path) if config_path is not None else track / "configs/b0_g2_estimator.v1.json"
    try:
        candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EstimatorContractError(f"cannot load estimator configuration: {candidate_path}") from exc
    if candidate.get("schema_version") != "b0-g2-estimator/v1":
        raise EstimatorContractError("estimator configuration requires b0-g2-estimator/v1")
    try:
        approval_path = candidate_path.parent / "b0_g2_estimator_approval.v1.json"
        approval = json.loads(approval_path.read_text(encoding="utf-8"))
        if approval.get("schema_version") != "b0-g2-estimator-approval/v1" or approval.get("status") != "design_accepted":
            raise EstimatorContractError("estimator configuration lacks design acceptance")
        if _canonical_lf_digest(candidate_path) != approval["approved_config_canonical_lf_sha256"]:
            raise EstimatorContractError("estimator configuration differs from the design-accepted bytes")
        authority = candidate["authority"]
        choices = candidate["implementation_choices"]
        repo = track.parents[1]
        g0_path = repo / authority["g0_config_path"]
        if _canonical_lf_digest(g0_path) != authority["g0_canonical_lf_sha256"]:
            raise EstimatorContractError("loaded G0 configuration canonical digest mismatch")
        g0 = _authoritative_validate(g0_path)
        gravity = float(np.linalg.norm(_vector(g0["imu_contract"]["gravity_ned_m_s2"], 3, "gravity_ned_m_s2")))
        period = _scalar(g0["timing"]["base_period_s"], "base_period_s") * _integer(
            g0["timing"]["schedules"]["imu_every_ticks"], "imu_every_ticks"
        )
        return EstimatorParameters(
            sample_period_s=period,
            gravity_m_s2=gravity,
            unit_norm_tolerance=_scalar(g0["conventions"]["quaternion"]["unit_norm_tolerance"], "unit_norm_tolerance"),
            correction_gain_per_s=_scalar(choices["complementary_correction_gain_per_s"], "correction_gain_per_s"),
            accelerometer_gate_deviation_m_s2=_scalar(choices["accelerometer_norm_gate"]["maximum_absolute_deviation_m_s2"], "accelerometer_gate_deviation_m_s2"),
            maximum_correction_step_rad=_scalar(choices["maximum_correction_step_rad"], "maximum_correction_step_rad"),
            timestamp_tolerance_s=_scalar(choices["test_tolerances"]["timestamp_abs_s"], "timestamp_tolerance_s"),
            config_path=str(candidate_path),
            g0_config_path=str(g0_path),
        )
    except OSError as exc:
        raise EstimatorContractError(f"cannot load estimator design approval: {approval_path}") from exc
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise EstimatorContractError(f"invalid estimator configuration field: {exc}") from exc


class AttitudeEstimator:
    def __init__(self, parameters: EstimatorParameters | None = None) -> None:
        self._parameters = parameters or load_estimator_parameters()
        self._estimate: StateEstimate | None = None
        self._reset_epoch: ResetEpoch | None = None
        self._last_tick = 0
        self._rng_seed = 0

    @property
    def estimate(self) -> StateEstimate:
        if self._estimate is None:
            raise EstimatorContractError("estimator must be reset before use")
        return StateEstimate(
            self._estimate.q_nb_estimate,
            self._estimate.omega_b_estimate_rad_s,
            self._estimate.timestamp_s,
            self._estimate.valid,
        )

    def reset(self, initial_state: EstimatorInitialState, reset_epoch: ResetEpoch, rng_seed: Any) -> StateEstimate:
        if not isinstance(initial_state, EstimatorInitialState):
            raise EstimatorContractError("initial_state must be EstimatorInitialState")
        if not isinstance(reset_epoch, ResetEpoch):
            raise EstimatorContractError("reset_epoch must be ResetEpoch")
        seed = _integer(rng_seed, "rng_seed")
        q_input = initial_state.q_nb
        with np.errstate(over="raise", invalid="raise"):
            try:
                norm = float(np.linalg.norm(q_input))
            except FloatingPointError as exc:
                raise EstimatorContractError("initial quaternion norm is outside the supported numeric domain") from exc
        if not math.isfinite(norm) or abs(norm - 1.0) > self._parameters.unit_norm_tolerance:
            raise EstimatorContractError("initial quaternion violates G0 unit norm tolerance")
        if self._reset_epoch is not None:
            if reset_epoch.id <= self._reset_epoch.id:
                raise EstimatorContractError("reset epoch id must strictly increase")
            if self._estimate is not None and reset_epoch.timestamp_s < self._estimate.timestamp_s:
                raise EstimatorContractError("reset timestamp must not rewind scenario time")
        q = _normalize(q_input)
        omega = initial_state.omega_b_rad_s
        estimate = StateEstimate(q, omega, reset_epoch.timestamp_s, True)
        self._estimate = estimate
        self._reset_epoch = reset_epoch
        self._last_tick = 0
        self._rng_seed = seed
        return self.estimate

    def _reject(self, reason: str) -> EstimatorStepResult:
        return EstimatorStepResult(self.estimate, EstimatorDiagnostics(False, reason))

    def process(self, imu_sample: Any) -> EstimatorStepResult:
        if self._estimate is None or self._reset_epoch is None:
            raise EstimatorContractError("estimator must be reset before use")
        try:
            timestamp = _scalar(imu_sample.timestamp_s, "imu_sample.timestamp_s")
            gyro = _vector(imu_sample.gyro_b_rad_s, 3, "imu_sample.gyro_b_rad_s")
            force = _vector(imu_sample.specific_force_b_m_s2, 3, "imu_sample.specific_force_b_m_s2")
            if not isinstance(imu_sample.valid, (bool, np.bool_)):
                raise EstimatorContractError("imu_sample.valid must be boolean")
        except (AttributeError, EstimatorContractError) as exc:
            return self._reject(str(exc))
        if not bool(imu_sample.valid):
            return self._reject("imu_sample.valid is false")

        try:
            relative = (timestamp - self._reset_epoch.timestamp_s) / self._parameters.sample_period_s
            if not math.isfinite(relative) or abs(relative) > 2**53:
                raise EstimatorContractError("imu sample timestamp is outside the supported reset grid")
            tick = int(round(relative))
            expected = self._reset_epoch.timestamp_s + tick * self._parameters.sample_period_s
        except (ArithmeticError, ValueError, EstimatorContractError) as exc:
            return self._reject(str(exc))
        if tick <= self._last_tick:
            return self._reject("imu sample timestamp is duplicate or stale")
        if tick < 1 or abs(timestamp - expected) > self._parameters.timestamp_tolerance_s:
            return self._reject("imu sample timestamp is off the reset-epoch grid")
        if self._last_tick == 0 and tick != 1:
            return self._reject("first imu sample must occur at the first due tick after reset")

        try:
            with np.errstate(over="raise", invalid="raise", divide="raise"):
                elapsed_periods = tick - self._last_tick
                missing_periods = elapsed_periods - 1
                dt = elapsed_periods * self._parameters.sample_period_s
                previous = self._estimate
                q_pred = _normalize(_multiply(previous.q_nb_estimate, _rotation_quaternion(gyro * dt)))

                force_norm = float(np.linalg.norm(force))
                if not math.isfinite(force_norm):
                    raise EstimatorContractError("specific-force norm is outside the supported numeric domain")
                eligible = abs(force_norm - self._parameters.gravity_m_s2) <= self._parameters.accelerometer_gate_deviation_m_s2
                applied = False
                capped = False
                q_next = q_pred
                if eligible and force_norm > 0.0:
                    measured = force / force_norm
                    predicted = _rotate_ned_to_body(q_pred, np.array([0.0, 0.0, -1.0]))
                    innovation = np.cross(measured, predicted)
                    correction, capped = _magnitude_clamp(
                        self._parameters.correction_gain_per_s * dt * innovation,
                        self._parameters.maximum_correction_step_rad,
                    )
                    q_next = _normalize(_multiply(q_pred, _rotation_quaternion(correction)))
                    applied = bool(np.linalg.norm(correction) > 0.0)
        except (ArithmeticError, ValueError, EstimatorContractError) as exc:
            return self._reject(f"imu sample derived arithmetic rejected: {exc}")

        estimate = StateEstimate(q_next, gyro, timestamp, True)
        diagnostics = EstimatorDiagnostics(
            accepted=True,
            reason="accepted",
            correction_eligible=eligible,
            correction_applied=applied,
            correction_capped=capped,
            elapsed_periods=elapsed_periods,
            missing_periods=missing_periods,
            gap_approximated=missing_periods > 0,
        )
        self._estimate = estimate
        self._last_tick = tick
        return EstimatorStepResult(self.estimate, diagnostics)

    def step(self, imu_sample: Any) -> StateEstimate:
        result = self.process(imu_sample)
        if not result.diagnostics.accepted:
            raise EstimatorContractError(result.diagnostics.reason, result.diagnostics)
        return result.estimate


__all__ = [
    "AttitudeEstimator",
    "EstimatorContractError",
    "EstimatorDiagnostics",
    "EstimatorInitialState",
    "EstimatorParameters",
    "EstimatorStepResult",
    "ResetEpoch",
    "StateEstimate",
    "load_estimator_parameters",
]
