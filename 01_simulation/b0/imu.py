"""B0 G1 IMU boundary: body-rate and specific-force observations."""

from __future__ import annotations

from typing import Any

import numpy as np

from contract import (
    ContractValidationError,
    G1Parameters,
    IMUInitialState,
    IMUSample,
    IMUState,
    SensorTruth,
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
        self._reset = False

    @property
    def parameters(self) -> G1Parameters:
        return self._parameters

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
        if isinstance(rng_seed, bool) or int(rng_seed) != rng_seed:
            raise ContractValidationError("rng_seed must be an integer")
        self._reset_epoch = epoch
        self._last_sample_timestamp = None
        self._samples_emitted = 0
        self._rng_seed = int(rng_seed)
        self._rng = np.random.default_rng(self._rng_seed)
        self._reset = True
        return self.state

    def sample(self, truth_state: SensorTruth, sample_timestamp_s: Any) -> IMUSample:
        if not self._reset or self._rng is None:
            raise ContractValidationError("IMU must be reset before use")
        if not isinstance(truth_state, SensorTruth):
            raise ContractValidationError("sample requires SensorTruth at the sensor boundary")
        timestamp = _scalar(sample_timestamp_s, "sample_timestamp_s")
        if timestamp <= self._reset_epoch:
            raise ContractValidationError("sample timestamp must be after reset epoch")
        if self._last_sample_timestamp is not None and timestamp <= self._last_sample_timestamp:
            raise ContractValidationError("sample timestamps must be strictly increasing")
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
        sample = IMUSample(timestamp, gyro, specific_force_b)
        self._last_sample_timestamp = timestamp
        self._samples_emitted += 1
        return sample


__all__ = ["IMU"]
