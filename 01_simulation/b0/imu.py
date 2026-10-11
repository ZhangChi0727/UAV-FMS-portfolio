"""B0 G1 IMU boundary: body-rate and specific-force observations."""

from __future__ import annotations

from typing import Any

import numpy as np

try:
    from .contract import (
        ContractValidationError,
        G1Parameters,
        IMUInitialState,
        IMUSample,
        IMUState,
        SensorTruth,
        _integer,
        _scalar,
        load_g1_parameters,
    )
    from .quaternion import rotate_ned_to_body
except ImportError:  # pragma: no cover - supports direct track execution
    from contract import (
        ContractValidationError,
        G1Parameters,
        IMUInitialState,
        IMUSample,
        IMUState,
        SensorTruth,
        _integer,
        _scalar,
        load_g1_parameters,
    )
    from quaternion import rotate_ned_to_body


class IMU:
    """Generate seeded, independent Gaussian gyro and accelerometer samples."""

    def __init__(self, parameters: G1Parameters | None = None) -> None:
        self._parameters = parameters or load_g1_parameters()
        self._rng: np.random.Generator | None = None
        self._reset_epoch = 0.0
        self._last_sample_timestamp: float | None = None
        self._samples_emitted = 0
        self._rng_seed = 0
        self._last_reset_epoch: float | None = None
        self._epoch_origin_s: float | None = None
        self._local_tick = 0
        self._next_sample_tick = 0
        self._reset = False

    @property
    def parameters(self) -> G1Parameters:
        return self._parameters

    @property
    def epoch_origin_s(self) -> float:
        if not self._reset or self._epoch_origin_s is None:
            raise ContractValidationError("IMU must be reset before use")
        return self._epoch_origin_s

    @property
    def local_tick(self) -> int:
        if not self._reset:
            raise ContractValidationError("IMU must be reset before use")
        return self._local_tick

    @property
    def next_sample_tick(self) -> int:
        if not self._reset:
            raise ContractValidationError("IMU must be reset before use")
        return self._next_sample_tick

    @property
    def state(self) -> IMUState:
        if not self._reset:
            raise ContractValidationError("IMU must be reset before use")
        return IMUState(
            self._reset_epoch,
            self._last_sample_timestamp,
            self._samples_emitted,
            self._rng_seed,
        )

    def reset(self, initial_state: IMUInitialState, reset_epoch: Any, rng_seed: Any) -> IMUState:
        if not isinstance(initial_state, IMUInitialState):
            raise ContractValidationError("reset requires IMUInitialState")
        epoch = _scalar(reset_epoch, "reset_epoch")
        seed = _integer(rng_seed, "rng_seed", nonnegative=True)
        current_timestamp = self._last_sample_timestamp if self._last_sample_timestamp is not None else self._last_reset_epoch
        if current_timestamp is not None and epoch < current_timestamp - 1e-12:
            raise ContractValidationError("reset epoch cannot move the scenario clock backwards")
        try:
            rng = np.random.default_rng(seed)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ContractValidationError("rng_seed must be a non-negative integer") from exc
        self._reset_epoch = epoch
        self._last_sample_timestamp = None
        self._samples_emitted = 0
        self._rng_seed = seed
        self._rng = rng
        self._last_reset_epoch = epoch
        self._epoch_origin_s = epoch
        self._local_tick = 0
        self._next_sample_tick = self._parameters.imu_period_ticks
        self._reset = True
        return self.state

    def sample(self, truth_state: SensorTruth, sample_timestamp_s: Any) -> IMUSample:
        if not self._reset or self._rng is None:
            raise ContractValidationError("IMU must be reset before use")
        if not isinstance(truth_state, SensorTruth):
            raise ContractValidationError("sample requires SensorTruth at the sensor boundary")
        timestamp = _scalar(sample_timestamp_s, "sample_timestamp_s")
        expected_timestamp = self.epoch_origin_s + self._next_sample_tick * self._parameters.base_period_s
        if abs(timestamp - expected_timestamp) > 1e-12:
            raise ContractValidationError("sample timestamp must match the G0 IMU period")
        q = truth_state.q_nb
        omega = truth_state.omega_b_rad_s
        acceleration_n = truth_state.acceleration_n_m_s2
        specific_force_b = rotate_ned_to_body(
            q,
            acceleration_n - self._parameters.gravity_n_m_s2,
        )
        gyro = omega + self._parameters.gyro_bias_rad_s
        gyro = gyro + self._rng.normal(0.0, self._parameters.gyro_noise_std_rad_s)
        specific_force_b = specific_force_b + self._parameters.accelerometer_bias_m_s2
        specific_force_b = specific_force_b + self._rng.normal(
            0.0,
            self._parameters.accelerometer_noise_std_m_s2,
        )
        sample = IMUSample(timestamp, gyro, specific_force_b, True)
        self._last_sample_timestamp = timestamp
        self._samples_emitted += 1
        self._local_tick = self._next_sample_tick
        self._next_sample_tick += self._parameters.imu_period_ticks
        return sample


__all__ = ["IMU"]
