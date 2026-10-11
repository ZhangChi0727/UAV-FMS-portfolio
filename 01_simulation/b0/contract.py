"""Typed, immutable interfaces for the B0 G1 component models.

The G1 component track deliberately stops at plant, actuator, and sensor
boundaries. It does not expose a controller or estimator interface. Arrays
are copied on input and on output so a caller cannot mutate model state
through a returned message.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


class ContractValidationError(ValueError):
    """Raised when a G1 message or parameter violates the frozen contract."""


def _scalar(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ContractValidationError(f"{name} must be a finite scalar")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{name} must be a finite scalar") from exc
    if not math.isfinite(result):
        raise ContractValidationError(f"{name} must be a finite scalar")
    return result


def _integer(value: Any, name: str, *, nonnegative: bool = False) -> int:
    if isinstance(value, bool):
        raise ContractValidationError(f"{name} must be an integer")
    try:
        converted = int(value)
        exact = converted == value
    except (TypeError, ValueError, OverflowError) as exc:
        raise ContractValidationError(f"{name} must be an integer") from exc
    if not isinstance(exact, (bool, np.bool_)) or not bool(exact) or (nonnegative and converted < 0):
        suffix = " and non-negative" if nonnegative else ""
        raise ContractValidationError(f"{name} must be an integer{suffix}")
    return converted


def _boolean(value: Any, name: str) -> bool:
    if not isinstance(value, (bool, np.bool_)):
        raise ContractValidationError(f"{name} must be a boolean")
    return bool(value)


def _boolean_vector(value: Any, length: int, name: str) -> np.ndarray:
    try:
        result = np.asarray(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{name} must be a boolean vector of length {length}") from exc
    if result.shape != (length,) or result.dtype != np.dtype(bool):
        raise ContractValidationError(f"{name} must be a boolean vector of length {length}")
    return result.astype(bool, copy=True)


def _vector(value: Any, length: int, name: str) -> np.ndarray:
    try:
        result = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{name} must be a finite vector of length {length}") from exc
    if result.shape != (length,) or not np.all(np.isfinite(result)):
        raise ContractValidationError(f"{name} must be a finite vector of length {length}")
    return result.copy()


def _matrix(value: Any, shape: tuple[int, int], name: str) -> np.ndarray:
    try:
        result = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{name} must be a finite {shape} matrix") from exc
    if result.shape != shape or not np.all(np.isfinite(result)):
        raise ContractValidationError(f"{name} must be a finite {shape} matrix")
    return result.copy()


def _copy(value: np.ndarray) -> np.ndarray:
    return np.asarray(value, dtype=np.float64).copy()


@dataclass(frozen=True, init=False)
class PlantInitialState:
    _q_nb: np.ndarray
    _omega_b_rad_s: np.ndarray

    def __init__(self, q_nb: Any, omega_b_rad_s: Any) -> None:
        object.__setattr__(self, "_q_nb", _vector(q_nb, 4, "q_nb"))
        object.__setattr__(self, "_omega_b_rad_s", _vector(omega_b_rad_s, 3, "omega_b_rad_s"))

    @property
    def q_nb(self) -> np.ndarray:
        return _copy(self._q_nb)

    @property
    def omega_b_rad_s(self) -> np.ndarray:
        return _copy(self._omega_b_rad_s)


@dataclass(frozen=True, init=False)
class PlantState:
    _q_nb: np.ndarray
    _omega_b_rad_s: np.ndarray
    timestamp_s: float

    def __init__(self, q_nb: Any, omega_b_rad_s: Any, timestamp_s: Any) -> None:
        object.__setattr__(self, "_q_nb", _vector(q_nb, 4, "q_nb"))
        object.__setattr__(self, "_omega_b_rad_s", _vector(omega_b_rad_s, 3, "omega_b_rad_s"))
        object.__setattr__(self, "timestamp_s", _scalar(timestamp_s, "timestamp_s"))

    @property
    def q_nb(self) -> np.ndarray:
        return _copy(self._q_nb)

    @property
    def omega_b_rad_s(self) -> np.ndarray:
        return _copy(self._omega_b_rad_s)


@dataclass(frozen=True, init=False)
class TorqueCommand:
    """Controller-owned, already paired requested and limited torque fields."""

    _requested_torque_body_Nm: np.ndarray
    _limited_torque_body_Nm: np.ndarray
    _saturated: np.ndarray
    timestamp_s: float

    def __init__(
        self,
        requested_torque_body_Nm: Any,
        limited_torque_body_Nm: Any,
        timestamp_s: Any,
        saturated: Any,
        *,
        limits_Nm: Any,
    ) -> None:
        requested = _vector(requested_torque_body_Nm, 3, "requested_torque_body_Nm")
        limited = _vector(limited_torque_body_Nm, 3, "limited_torque_body_Nm")
        limits = _vector(limits_Nm, 3, "limits_Nm")
        if np.any(limits <= 0.0):
            raise ContractValidationError("limits_Nm must be strictly positive")
        expected = np.clip(requested, -limits, limits)
        if not np.allclose(limited, expected, rtol=0.0, atol=1e-12):
            raise ContractValidationError(
                "limited_torque_body_Nm must be the controller-provided "
                "componentwise clamp of requested_torque_body_Nm"
            )
        saturation = _boolean_vector(saturated, 3, "saturated")
        expected_saturation = np.abs(requested) > limits
        if not np.array_equal(saturation, expected_saturation):
            raise ContractValidationError(
                "saturated must be true exactly when requested torque exceeds a component limit"
            )
        object.__setattr__(self, "_requested_torque_body_Nm", requested)
        object.__setattr__(self, "_limited_torque_body_Nm", limited)
        object.__setattr__(self, "_saturated", saturation)
        object.__setattr__(self, "timestamp_s", _scalar(timestamp_s, "timestamp_s"))

    @property
    def requested_torque_body_Nm(self) -> np.ndarray:
        return _copy(self._requested_torque_body_Nm)

    @property
    def limited_torque_body_Nm(self) -> np.ndarray:
        return _copy(self._limited_torque_body_Nm)

    @property
    def saturated(self) -> np.ndarray:
        return self._saturated.copy()

    @property
    def command_timestamp_s(self) -> float:
        """Compatibility view explicitly mapped to G0 ``timestamp_s``."""

        return self.timestamp_s


@dataclass(frozen=True, init=False)
class ActuatorInitialState:
    _actual_torque_body_Nm: np.ndarray
    _held_limited_torque_body_Nm: np.ndarray
    _held_requested_torque_body_Nm: np.ndarray
    _held_saturated: np.ndarray
    held_command_timestamp_s: float | None

    def __init__(
        self,
        actual_torque_body_Nm: Any = (0.0, 0.0, 0.0),
        held_limited_torque_body_Nm: Any = (0.0, 0.0, 0.0),
        held_command_timestamp_s: Any = None,
        held_saturated: Any = (False, False, False),
        held_requested_torque_body_Nm: Any = (0.0, 0.0, 0.0),
    ) -> None:
        object.__setattr__(self, "_actual_torque_body_Nm", _vector(actual_torque_body_Nm, 3, "actual_torque_body_Nm"))
        object.__setattr__(self, "_held_limited_torque_body_Nm", _vector(held_limited_torque_body_Nm, 3, "held_limited_torque_body_Nm"))
        object.__setattr__(self, "_held_requested_torque_body_Nm", _vector(held_requested_torque_body_Nm, 3, "held_requested_torque_body_Nm"))
        object.__setattr__(self, "_held_saturated", _boolean_vector(held_saturated, 3, "held_saturated"))
        if held_command_timestamp_s is None:
            object.__setattr__(self, "held_command_timestamp_s", None)
        else:
            object.__setattr__(self, "held_command_timestamp_s", _scalar(held_command_timestamp_s, "held_command_timestamp_s"))

    @property
    def actual_torque_body_Nm(self) -> np.ndarray:
        return _copy(self._actual_torque_body_Nm)

    @property
    def held_limited_torque_body_Nm(self) -> np.ndarray:
        return _copy(self._held_limited_torque_body_Nm)

    @property
    def held_saturated(self) -> np.ndarray:
        return self._held_saturated.copy()

    @property
    def held_requested_torque_body_Nm(self) -> np.ndarray:
        return _copy(self._held_requested_torque_body_Nm)


@dataclass(frozen=True, init=False)
class ActuatorFeedback:
    _actual_torque_body_Nm: np.ndarray
    _limited_torque_body_Nm: np.ndarray
    _saturated: np.ndarray
    timestamp_s: float
    command_timestamp_s: float

    def __init__(
        self,
        actual_torque_body_Nm: Any,
        limited_torque_body_Nm: Any,
        saturated: Any,
        timestamp_s: Any,
        command_timestamp_s: Any,
    ) -> None:
        object.__setattr__(self, "_actual_torque_body_Nm", _vector(actual_torque_body_Nm, 3, "actual_torque_body_Nm"))
        object.__setattr__(self, "_limited_torque_body_Nm", _vector(limited_torque_body_Nm, 3, "limited_torque_body_Nm"))
        object.__setattr__(self, "_saturated", _boolean_vector(saturated, 3, "saturated"))
        object.__setattr__(self, "timestamp_s", _scalar(timestamp_s, "timestamp_s"))
        object.__setattr__(self, "command_timestamp_s", _scalar(command_timestamp_s, "command_timestamp_s"))

    @property
    def actual_torque_body_Nm(self) -> np.ndarray:
        return _copy(self._actual_torque_body_Nm)

    @property
    def limited_torque_body_Nm(self) -> np.ndarray:
        return _copy(self._limited_torque_body_Nm)

    @property
    def saturated(self) -> np.ndarray:
        return self._saturated.copy()

    @property
    def feedback_timestamp_s(self) -> float:
        """Compatibility view explicitly mapped to the G0 ``timestamp_s``."""

        return self.timestamp_s


@dataclass(frozen=True, init=False)
class SensorTruth:
    """Truth presented only at the IMU boundary."""

    _q_nb: np.ndarray
    _omega_b_rad_s: np.ndarray
    _acceleration_n_m_s2: np.ndarray

    def __init__(self, q_nb: Any, omega_b_rad_s: Any, acceleration_n_m_s2: Any) -> None:
        object.__setattr__(self, "_q_nb", _vector(q_nb, 4, "q_nb"))
        object.__setattr__(self, "_omega_b_rad_s", _vector(omega_b_rad_s, 3, "omega_b_rad_s"))
        object.__setattr__(self, "_acceleration_n_m_s2", _vector(acceleration_n_m_s2, 3, "acceleration_n_m_s2"))

    @property
    def q_nb(self) -> np.ndarray:
        return _copy(self._q_nb)

    @property
    def omega_b_rad_s(self) -> np.ndarray:
        return _copy(self._omega_b_rad_s)

    @property
    def acceleration_n_m_s2(self) -> np.ndarray:
        return _copy(self._acceleration_n_m_s2)


@dataclass(frozen=True, init=False)
class IMUInitialState:
    """Explicit IMU reset payload; the sensor has no hidden physical state."""

    def __init__(self) -> None:
        return


@dataclass(frozen=True, init=False)
class IMUState:
    reset_epoch_s: float
    last_sample_timestamp_s: float | None
    samples_emitted: int
    rng_seed: int

    def __init__(self, reset_epoch_s: Any, last_sample_timestamp_s: Any, samples_emitted: Any, rng_seed: Any) -> None:
        object.__setattr__(self, "reset_epoch_s", _scalar(reset_epoch_s, "reset_epoch_s"))
        if last_sample_timestamp_s is None:
            object.__setattr__(self, "last_sample_timestamp_s", None)
        else:
            object.__setattr__(self, "last_sample_timestamp_s", _scalar(last_sample_timestamp_s, "last_sample_timestamp_s"))
        object.__setattr__(self, "samples_emitted", _integer(samples_emitted, "samples_emitted", nonnegative=True))
        object.__setattr__(self, "rng_seed", _integer(rng_seed, "rng_seed", nonnegative=True))


@dataclass(frozen=True, init=False)
class IMUSample:
    timestamp_s: float
    _gyro_b_rad_s: np.ndarray
    _specific_force_b_m_s2: np.ndarray
    valid: bool

    def __init__(self, timestamp_s: Any, gyro_b_rad_s: Any, specific_force_b_m_s2: Any, valid: Any) -> None:
        object.__setattr__(self, "timestamp_s", _scalar(timestamp_s, "timestamp_s"))
        object.__setattr__(self, "_gyro_b_rad_s", _vector(gyro_b_rad_s, 3, "gyro_b_rad_s"))
        object.__setattr__(self, "_specific_force_b_m_s2", _vector(specific_force_b_m_s2, 3, "specific_force_b_m_s2"))
        object.__setattr__(self, "valid", _boolean(valid, "valid"))

    @property
    def gyro_b_rad_s(self) -> np.ndarray:
        return _copy(self._gyro_b_rad_s)

    @property
    def specific_force_b_m_s2(self) -> np.ndarray:
        return _copy(self._specific_force_b_m_s2)


@dataclass(frozen=True, init=False)
class G1Parameters:
    """Validated values copied from the approved B0 G0 v2 contract."""

    _inertia_kg_m2: np.ndarray
    _actuator_time_constant_s: float
    _actuator_limits_Nm: np.ndarray
    _gravity_n_m_s2: np.ndarray
    _gyro_noise_std_rad_s: np.ndarray
    _gyro_bias_rad_s: np.ndarray
    _accelerometer_noise_std_m_s2: np.ndarray
    _accelerometer_bias_m_s2: np.ndarray
    _base_period_s: float
    _imu_period_ticks: int
    config_path: str

    def __init__(
        self,
        inertia_kg_m2: Any,
        actuator_time_constant_s: Any,
        actuator_limits_Nm: Any,
        gravity_n_m_s2: Any,
        gyro_noise_std_rad_s: Any,
        gyro_bias_rad_s: Any,
        accelerometer_noise_std_m_s2: Any,
        accelerometer_bias_m_s2: Any,
        base_period_s: Any,
        imu_period_ticks: Any,
        config_path: str = "<explicit>",
    ) -> None:
        inertia = _matrix(inertia_kg_m2, (3, 3), "inertia_kg_m2")
        if not np.allclose(inertia, np.diag(np.diag(inertia)), rtol=0.0, atol=0.0):
            raise ContractValidationError("inertia_kg_m2 must be diagonal for G1")
        if np.any(np.diag(inertia) <= 0.0):
            raise ContractValidationError("inertia_kg_m2 diagonal must be positive")
        tau = _scalar(actuator_time_constant_s, "actuator_time_constant_s")
        if tau <= 0.0:
            raise ContractValidationError("actuator_time_constant_s must be positive")
        limits = _vector(actuator_limits_Nm, 3, "actuator_limits_Nm")
        if np.any(limits <= 0.0):
            raise ContractValidationError("actuator_limits_Nm must be positive")
        gravity = _vector(gravity_n_m_s2, 3, "gravity_n_m_s2")
        gyro_std = _vector(gyro_noise_std_rad_s, 3, "gyro_noise_std_rad_s")
        accel_std = _vector(accelerometer_noise_std_m_s2, 3, "accelerometer_noise_std_m_s2")
        if np.any(gyro_std < 0.0) or np.any(accel_std < 0.0):
            raise ContractValidationError("IMU noise standard deviations must be non-negative")
        base_period = _scalar(base_period_s, "base_period_s")
        if base_period <= 0.0:
            raise ContractValidationError("base_period_s must be positive")
        period_ticks = _integer(imu_period_ticks, "imu_period_ticks", nonnegative=True)
        if period_ticks <= 0:
            raise ContractValidationError("imu_period_ticks must be positive")
        object.__setattr__(self, "_inertia_kg_m2", inertia)
        object.__setattr__(self, "_actuator_time_constant_s", tau)
        object.__setattr__(self, "_actuator_limits_Nm", limits)
        object.__setattr__(self, "_gravity_n_m_s2", gravity)
        object.__setattr__(self, "_gyro_noise_std_rad_s", gyro_std)
        object.__setattr__(self, "_gyro_bias_rad_s", _vector(gyro_bias_rad_s, 3, "gyro_bias_rad_s"))
        object.__setattr__(self, "_accelerometer_noise_std_m_s2", accel_std)
        object.__setattr__(self, "_accelerometer_bias_m_s2", _vector(accelerometer_bias_m_s2, 3, "accelerometer_bias_m_s2"))
        object.__setattr__(self, "_base_period_s", base_period)
        object.__setattr__(self, "_imu_period_ticks", period_ticks)
        object.__setattr__(self, "config_path", str(config_path))

    @property
    def inertia_kg_m2(self) -> np.ndarray:
        return _copy(self._inertia_kg_m2)

    @property
    def actuator_time_constant_s(self) -> float:
        return self._actuator_time_constant_s

    @property
    def actuator_limits_Nm(self) -> np.ndarray:
        return _copy(self._actuator_limits_Nm)

    @property
    def gravity_n_m_s2(self) -> np.ndarray:
        return _copy(self._gravity_n_m_s2)

    @property
    def gyro_noise_std_rad_s(self) -> np.ndarray:
        return _copy(self._gyro_noise_std_rad_s)

    @property
    def gyro_bias_rad_s(self) -> np.ndarray:
        return _copy(self._gyro_bias_rad_s)

    @property
    def accelerometer_noise_std_m_s2(self) -> np.ndarray:
        return _copy(self._accelerometer_noise_std_m_s2)

    @property
    def accelerometer_bias_m_s2(self) -> np.ndarray:
        return _copy(self._accelerometer_bias_m_s2)

    @property
    def base_period_s(self) -> float:
        return self._base_period_s

    @property
    def imu_period_ticks(self) -> int:
        return self._imu_period_ticks

    @property
    def imu_period_s(self) -> float:
        return self._base_period_s * self._imu_period_ticks


def load_g1_parameters(config_path: str | Path | None = None) -> G1Parameters:
    """Load and validate the plant/actuator/IMU values from G0 v2."""

    if config_path is None:
        config_path = Path(__file__).resolve().parents[2] / "05_integration/b0/configs/b0_g0_contract.v2.json"
    path = Path(config_path)
    try:
        with path.open(encoding="utf-8") as handle:
            document = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractValidationError(f"cannot load G1 contract: {path}") from exc
    if not isinstance(document, dict):
        raise ContractValidationError("G1 contract root must be a JSON object")
    if document.get("schema_version") != "b0-g0-contract/v2":
        raise ContractValidationError("G1 requires the approved b0-g0-contract/v2 schema")
    _validate_with_authority(path)
    try:
        plant = document["plant_contract"]
        actuator = document["actuator_contract"]
        imu = document["imu_contract"]
        gyro = imu["gyro"]
        accelerometer = imu["accelerometer"]
        return G1Parameters(
            inertia_kg_m2=plant["inertia_kg_m2"],
            actuator_time_constant_s=actuator["time_constant_s"],
            actuator_limits_Nm=actuator["limits_Nm"],
            gravity_n_m_s2=imu["gravity_ned_m_s2"],
            gyro_noise_std_rad_s=gyro["noise_std_rad_s"],
            gyro_bias_rad_s=gyro["bias_rad_s"],
            accelerometer_noise_std_m_s2=accelerometer["noise_std_m_s2"],
            accelerometer_bias_m_s2=accelerometer["bias_m_s2"],
            base_period_s=document["timing"]["base_period_s"],
            imu_period_ticks=document["timing"]["schedules"]["imu_every_ticks"],
            config_path=str(path),
        )
    except KeyError as exc:
        raise ContractValidationError(f"missing G1 contract field: {exc}") from exc


def _validate_with_authority(config_path: Path) -> None:
    """Run the repository's single authoritative G0 validator before extraction."""

    import importlib.util

    validator_path = Path(__file__).resolve().parents[2] / "05_integration/b0/validate_config.py"
    try:
        spec = importlib.util.spec_from_file_location("b0_g0_authoritative_validator", validator_path)
        if spec is None or spec.loader is None:
            raise ContractValidationError("cannot load authoritative G0 validator")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        document = module.load_config(config_path)
        module.validate_config(document)
    except ContractValidationError:
        raise
    except Exception as exc:
        raise ContractValidationError(f"authoritative G0 validation failed: {config_path}") from exc


__all__ = [
    "ActuatorFeedback",
    "ActuatorInitialState",
    "ContractValidationError",
    "G1Parameters",
    "IMUInitialState",
    "IMUSample",
    "IMUState",
    "PlantInitialState",
    "PlantState",
    "SensorTruth",
    "TorqueCommand",
    "load_g1_parameters",
]
