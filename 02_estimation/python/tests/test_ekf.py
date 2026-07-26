"""Executable contract for the Phase 3A Python error-state EKF."""

import numpy as np
import pytest

from ekf import EKF


PENDING_PHASE_3A = pytest.mark.xfail(
    strict=True,
    reason="Phase 3A contract: remove the marker as each behavior is implemented",
)

GRAVITY = 9.80665


@PENDING_PHASE_3A
def test_initial_state_matches_navigation_contract() -> None:
    """Nominal state is 16D; local-error covariance is 15D."""
    ekf = EKF()

    assert ekf.x.shape == (16,)
    np.testing.assert_allclose(ekf.x[0:6], 0.0)
    np.testing.assert_allclose(ekf.x[6:10], [1.0, 0.0, 0.0, 0.0])
    np.testing.assert_allclose(ekf.x[10:16], 0.0)
    assert ekf.P.shape == (15, 15)
    np.testing.assert_allclose(ekf.P, ekf.P.T, atol=1e-12)
    assert np.all(np.linalg.eigvalsh(ekf.P) > 0.0)


@PENDING_PHASE_3A
def test_predict_step_zero_input() -> None:
    """An aligned stationary IMU shall preserve the nominal state."""
    ekf = EKF()
    x0 = ekf.x.copy()
    stationary_specific_force = np.array([0.0, 0.0, -GRAVITY])

    ekf.predict(
        accel=stationary_specific_force,
        gyro=np.zeros(3),
        dt=0.01,
    )

    np.testing.assert_allclose(ekf.x, x0, atol=1e-10)
    assert np.linalg.norm(ekf.x[6:10]) == pytest.approx(1.0, abs=1e-12)


@PENDING_PHASE_3A
def test_covariance_positive_definite() -> None:
    """Prediction preserves covariance symmetry and positive eigenvalues."""
    ekf = EKF()
    ekf.predict(
        accel=np.array([0.0, 0.0, -GRAVITY]),
        gyro=np.zeros(3),
        dt=0.01,
    )

    np.testing.assert_allclose(ekf.P, ekf.P.T, atol=1e-12)
    eigenvalues = np.linalg.eigvalsh(ekf.P)
    assert np.all(eigenvalues > 0), "P must be positive definite"


@PENDING_PHASE_3A
def test_stationary_transition_structure() -> None:
    """Stationary local-error transition has required first-order blocks."""
    dt = 0.01
    ekf = EKF()
    transition = ekf._compute_jacobian_F(
        accel=np.array([0.0, 0.0, -GRAVITY]),
        gyro=np.zeros(3),
        dt=dt,
    )

    assert transition.shape == (15, 15)
    np.testing.assert_allclose(transition[0:3, 3:6], dt * np.eye(3), atol=1e-12)
    np.testing.assert_allclose(transition[3:6, 9:12], -dt * np.eye(3), atol=1e-12)
    np.testing.assert_allclose(
        transition[6:9, 12:15],
        -dt * np.eye(3),
        atol=1e-12,
    )


@PENDING_PHASE_3A
def test_gps_update_reduces_uncertainty() -> None:
    """GPS correction moves the estimate and reduces observed uncertainty."""
    ekf = EKF()
    trace_before = np.trace(ekf.P[0:6, 0:6])
    measurement = np.array([10.0, -4.0, 2.0, 1.0, 0.5, -0.25])

    ekf.update_gps(measurement)

    assert ekf.x[0] > 0.0
    assert ekf.x[1] < 0.0
    assert ekf.x[2] > 0.0
    assert np.trace(ekf.P[0:6, 0:6]) < trace_before
    np.testing.assert_allclose(ekf.P, ekf.P.T, atol=1e-12)


@PENDING_PHASE_3A
@pytest.mark.parametrize("dt", [0.0, -0.01, np.nan, np.inf])
def test_predict_rejects_invalid_dt(dt: float) -> None:
    """Prediction rejects non-positive or non-finite sample periods."""
    ekf = EKF()

    with pytest.raises(ValueError):
        ekf.predict(
            accel=np.array([0.0, 0.0, -GRAVITY]),
            gyro=np.zeros(3),
            dt=dt,
        )


@pytest.mark.skip(reason="Phase 4B: requires approved NAV-REQ-001 conditions")
def test_gps_dropout_requirement_campaign() -> None:
    """Execute the approved NAV-REQ-001 statistical GPS-outage campaign."""
