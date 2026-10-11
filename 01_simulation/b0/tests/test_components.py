"""Component-level acceptance and negative tests for the B0 G1 track."""

from __future__ import annotations

import math

import numpy as np
import pytest

from actuator import Actuator
from contract import (
    ActuatorInitialState,
    ContractValidationError,
    G1Parameters,
    IMUInitialState,
    PlantInitialState,
    SensorTruth,
    TorqueCommand,
    load_g1_parameters,
)
from imu import IMU
from plant import Plant
from quaternion import (
    normalize_quaternion,
    quaternion_distance_rad,
    quaternion_from_axis_angle,
    quaternion_inverse,
    quaternion_multiply,
    rotate_ned_to_body,
)


PARAMETERS = load_g1_parameters()
IDENTITY = np.array([1.0, 0.0, 0.0, 0.0])


def _command(requested: np.ndarray, timestamp: float = 0.0) -> TorqueCommand:
    limited = np.clip(requested, -PARAMETERS.actuator_limits_Nm, PARAMETERS.actuator_limits_Nm)
    return TorqueCommand(requested, limited, timestamp, limits_Nm=PARAMETERS.actuator_limits_Nm)


@pytest.mark.parametrize("axis", range(3))
@pytest.mark.parametrize("sign", (-1.0, 1.0))
def test_principal_axis_analytic_response(axis: int, sign: float) -> None:
    torque = np.zeros(3)
    torque[axis] = sign * 0.01
    dt = 0.00025
    duration = 0.01
    plant = Plant(PARAMETERS)
    plant.reset(PlantInitialState(IDENTITY, np.zeros(3)), 0.0)
    for _ in range(round(duration / dt)):
        state = plant.step(torque, dt)
    expected_omega = torque[axis] * duration / PARAMETERS.inertia_kg_m2[axis, axis]
    expected_angle = 0.5 * torque[axis] * duration**2 / PARAMETERS.inertia_kg_m2[axis, axis]
    expected_q = quaternion_from_axis_angle(np.eye(3)[axis], expected_angle)
    assert abs(state.omega_b_rad_s[axis] - expected_omega) <= 1e-10
    assert np.max(np.abs(np.delete(state.omega_b_rad_s, axis))) <= 1e-12
    assert quaternion_distance_rad(expected_q, state.q_nb) <= 1e-10
    assert abs(np.linalg.norm(state.q_nb) - 1.0) <= 1e-14


def _integrate(timestep: float) -> tuple[np.ndarray, np.ndarray]:
    torque = np.array([0.01, -0.01, 0.005])
    plant = Plant(PARAMETERS)
    plant.reset(PlantInitialState(IDENTITY, np.zeros(3)), 0.0)
    for _ in range(round(0.05 / timestep)):
        state = plant.step(torque, timestep)
    return state.q_nb, state.omega_b_rad_s


def test_rk4_step_halving_against_fine_reference() -> None:
    coarse_q, coarse_omega = _integrate(0.0025)
    half_q, half_omega = _integrate(0.00125)
    reference_q, reference_omega = _integrate(0.00015625)
    coarse_attitude_error = quaternion_distance_rad(reference_q, coarse_q)
    half_attitude_error = quaternion_distance_rad(reference_q, half_q)
    coarse_rate_error = float(np.linalg.norm(coarse_omega - reference_omega))
    half_rate_error = float(np.linalg.norm(half_omega - reference_omega))
    assert coarse_attitude_error <= 1e-8
    assert half_attitude_error <= 1e-8
    assert coarse_rate_error <= 1e-8
    assert half_rate_error <= 1e-8
    assert half_attitude_error < coarse_attitude_error
    assert half_rate_error < coarse_rate_error


def test_quaternion_oracle_is_sign_invariant_and_normalizes() -> None:
    ninety_x = quaternion_from_axis_angle([1.0, 0.0, 0.0], math.pi / 2.0)
    assert quaternion_distance_rad(IDENTITY, -IDENTITY) == pytest.approx(0.0, abs=1e-15)
    assert quaternion_distance_rad(ninety_x, 3.0 * ninety_x) == pytest.approx(0.0, abs=1e-15)
    assert quaternion_distance_rad(IDENTITY, ninety_x) == pytest.approx(math.pi / 2.0, abs=1e-15)
    assert np.allclose(quaternion_multiply(ninety_x, quaternion_inverse(ninety_x)), IDENTITY)
    assert np.allclose(normalize_quaternion([2.0, 0.0, 0.0, 0.0]), IDENTITY)
    with pytest.raises(ContractValidationError):
        normalize_quaternion([0.0, 0.0, 0.0, 0.0])
    with pytest.raises(ContractValidationError):
        normalize_quaternion([1.0, 0.0, np.nan, 0.0])


def test_plant_rejects_invalid_step_without_mutating_state() -> None:
    plant = Plant(PARAMETERS)
    plant.reset(PlantInitialState(IDENTITY, np.zeros(3)), 4.0)
    before = plant.state
    for bad_torque, bad_dt in (([0.0, 0.0], 0.01), ([0.0, 0.0, np.nan], 0.01), ([0.0, 0.0, 0.0], 0.0)):
        with pytest.raises(ContractValidationError):
            plant.step(bad_torque, bad_dt)
        after = plant.state
        assert np.array_equal(after.q_nb, before.q_nb)
        assert np.array_equal(after.omega_b_rad_s, before.omega_b_rad_s)
        assert after.timestamp_s == before.timestamp_s
    with pytest.raises(ContractValidationError):
        plant.reset(PlantInitialState([0.0, 0.0, 0.0, 0.0], np.zeros(3)), 4.0)


def test_plant_outputs_are_copies() -> None:
    plant = Plant(PARAMETERS)
    plant.reset(PlantInitialState(IDENTITY, np.zeros(3)), 0.0)
    state = plant.step(np.zeros(3), 0.01)
    q = state.q_nb
    q[0] = 0.0
    assert plant.state.q_nb[0] == pytest.approx(1.0)


def test_actuator_exact_zoh_and_zero_target() -> None:
    actuator = Actuator(PARAMETERS)
    actuator.reset(ActuatorInitialState(), 0.0)
    target = np.array([0.1, -0.1, 0.05])
    dt = 0.015
    feedback = actuator.step(_command(target), dt)
    expected = target * (1.0 - math.exp(-dt / PARAMETERS.actuator_time_constant_s))
    assert np.allclose(feedback.actual_torque_body_Nm, expected, rtol=0.0, atol=1e-14)
    feedback = actuator.step(_command(np.zeros(3), timestamp=0.015), dt)
    expected = expected * math.exp(-dt / PARAMETERS.actuator_time_constant_s)
    assert np.allclose(feedback.actual_torque_body_Nm, expected, rtol=0.0, atol=1e-14)
    assert np.allclose(feedback.limited_torque_body_Nm, np.zeros(3))


def test_actuator_signed_limits_and_no_hidden_clamp() -> None:
    actuator = Actuator(PARAMETERS)
    actuator.reset(ActuatorInitialState(), 0.0)
    limits = PARAMETERS.actuator_limits_Nm
    requested = np.array([2.0, -2.0, 2.0])
    feedback = actuator.step(_command(requested), 0.01)
    assert np.allclose(feedback.limited_torque_body_Nm, limits * [1.0, -1.0, 1.0])
    assert np.all(np.abs(feedback.actual_torque_body_Nm) <= limits)
    malicious = TorqueCommand([0.4, 0.0, 0.0], [0.4, 0.0, 0.0], 0.01, limits_Nm=[1.0, 1.0, 1.0])
    with pytest.raises(ContractValidationError, match="does not clamp"):
        actuator.step(malicious, 0.01)


def test_actuator_timestamp_pairing_and_reset() -> None:
    actuator = Actuator(PARAMETERS)
    actuator.reset(ActuatorInitialState(), 1.0)
    actuator.step(_command(np.array([0.1, 0.0, 0.0]), timestamp=1.0), 0.01)
    with pytest.raises(ContractValidationError, match="future"):
        actuator.step(_command(np.zeros(3), timestamp=2.0), 0.01)
    with pytest.raises(ContractValidationError, match="non-decreasing"):
        actuator.step(_command(np.zeros(3), timestamp=0.5), 0.01)
    feedback = actuator.reset(ActuatorInitialState(), 8.0)
    assert np.allclose(feedback.actual_torque_body_Nm, np.zeros(3))
    assert np.allclose(feedback.limited_torque_body_Nm, np.zeros(3))
    assert feedback.feedback_timestamp_s == pytest.approx(8.0)


def _zero_noise_parameters() -> G1Parameters:
    return G1Parameters(
        inertia_kg_m2=PARAMETERS.inertia_kg_m2,
        actuator_time_constant_s=PARAMETERS.actuator_time_constant_s,
        actuator_limits_Nm=PARAMETERS.actuator_limits_Nm,
        gravity_n_m_s2=PARAMETERS.gravity_n_m_s2,
        gyro_noise_std_rad_s=np.zeros(3),
        gyro_bias_rad_s=PARAMETERS.gyro_bias_rad_s,
        accelerometer_noise_std_m_s2=np.zeros(3),
        accelerometer_bias_m_s2=PARAMETERS.accelerometer_bias_m_s2,
    )


def test_imu_stationary_and_known_acceleration_without_noise() -> None:
    parameters = _zero_noise_parameters()
    imu = IMU(parameters)
    imu.reset(IMUInitialState(), 0.0, 42)
    truth = SensorTruth(IDENTITY, np.zeros(3), np.zeros(3))
    sample = imu.sample(truth, 0.002)
    assert np.allclose(sample.gyro_b_rad_s, parameters.gyro_bias_rad_s)
    assert np.allclose(
        sample.specific_force_b_m_s2,
        np.array([0.0, 0.0, -9.80665]) + parameters.accelerometer_bias_m_s2,
    )
    q = quaternion_from_axis_angle([1.0, 0.0, 0.0], math.pi / 2.0)
    acceleration = np.array([1.0, 2.0, 3.0])
    expected = rotate_ned_to_body(q, acceleration - parameters.gravity_n_m_s2)
    sample = imu.sample(SensorTruth(q, [0.1, 0.2, 0.3], acceleration), 0.004)
    assert np.allclose(sample.gyro_b_rad_s, np.array([0.1, 0.2, 0.3]) + parameters.gyro_bias_rad_s)
    assert np.allclose(sample.specific_force_b_m_s2, expected + parameters.accelerometer_bias_m_s2)


def test_imu_seed_reproducibility_and_reset() -> None:
    truth = SensorTruth(IDENTITY, [0.1, 0.2, 0.3], [1.0, -2.0, 0.5])
    first = IMU(PARAMETERS)
    second = IMU(PARAMETERS)
    first.reset(IMUInitialState(), 0.0, 123)
    second.reset(IMUInitialState(), 0.0, 123)
    for timestamp in (0.002, 0.004, 0.006):
        a = first.sample(truth, timestamp)
        b = second.sample(truth, timestamp)
        assert np.array_equal(a.gyro_b_rad_s, b.gyro_b_rad_s)
        assert np.array_equal(a.specific_force_b_m_s2, b.specific_force_b_m_s2)
    third = IMU(PARAMETERS)
    third.reset(IMUInitialState(), 0.0, 124)
    different = third.sample(truth, 0.002)
    assert not np.array_equal(different.gyro_b_rad_s, first.sample(truth, 0.008).gyro_b_rad_s)
    first.reset(IMUInitialState(), 0.0, 123)
    replay = first.sample(truth, 0.002)
    second.reset(IMUInitialState(), 0.0, 123)
    assert np.array_equal(replay.gyro_b_rad_s, second.sample(truth, 0.002).gyro_b_rad_s)


def test_imu_invalid_timestamp_does_not_consume_rng() -> None:
    truth = SensorTruth(IDENTITY, np.zeros(3), np.zeros(3))
    control = IMU(PARAMETERS)
    trial = IMU(PARAMETERS)
    control.reset(IMUInitialState(), 1.0, 99)
    trial.reset(IMUInitialState(), 1.0, 99)
    with pytest.raises(ContractValidationError):
        trial.sample(truth, 1.0)
    with pytest.raises(ContractValidationError):
        trial.sample(truth, float("nan"))
    expected = control.sample(truth, 1.002)
    actual = trial.sample(truth, 1.002)
    assert np.array_equal(expected.gyro_b_rad_s, actual.gyro_b_rad_s)
    assert np.array_equal(expected.specific_force_b_m_s2, actual.specific_force_b_m_s2)
    with pytest.raises(ContractValidationError, match="strictly increasing"):
        trial.sample(truth, 1.001)
