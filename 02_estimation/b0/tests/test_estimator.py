from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pytest

from estimator import (
    AttitudeEstimator,
    EstimatorContractError,
    EstimatorInitialState,
    ResetEpoch,
    _canonical_lf_digest,
    _magnitude_clamp,
    load_estimator_parameters,
)


TRACK = Path(__file__).resolve().parents[1]
REPO = TRACK.parents[1]
Q_TOL = 1e-12


@dataclass
class Sample:
    timestamp_s: float
    gyro_b_rad_s: object = (0.0, 0.0, 0.0)
    specific_force_b_m_s2: object = (0.0, 0.0, -9.80665)
    valid: object = True


def qmul(left, right):
    lw, lx, ly, lz = np.asarray(left, dtype=float)
    rw, rx, ry, rz = np.asarray(right, dtype=float)
    return np.array(
        [
            lw * rw - lx * rx - ly * ry - lz * rz,
            lw * rx + lx * rw + ly * rz - lz * ry,
            lw * ry - lx * rz + ly * rw + lz * rx,
            lw * rz + lx * ry - ly * rx + lz * rw,
        ]
    )


def axis_angle(vector):
    vector = np.asarray(vector, dtype=float)
    angle = np.linalg.norm(vector)
    if angle == 0:
        return np.array([1.0, 0.0, 0.0, 0.0])
    return np.r_[math.cos(angle / 2), math.sin(angle / 2) * vector / angle]


def align(actual, expected):
    actual = np.asarray(actual)
    expected = np.asarray(expected)
    return -actual if np.dot(actual, expected) < 0 else actual


def rotate_n_to_b(q_nb, vector):
    q_nb = np.asarray(q_nb)
    qc = q_nb * np.array([1.0, -1.0, -1.0, -1.0])
    return qmul(qmul(qc, np.r_[0.0, vector]), q_nb)[1:]


def make_estimator(q=(1.0, 0.0, 0.0, 0.0), omega=(0.0, 0.0, 0.0), *, epoch=0, time=0.0):
    estimator = AttitudeEstimator()
    estimator.reset(EstimatorInitialState(q, omega), ResetEpoch(epoch, time), 7)
    return estimator


@pytest.mark.parametrize(
    "rate",
    [
        (0.3, 0.0, 0.0),
        (-0.3, 0.0, 0.0),
        (0.0, 0.3, 0.0),
        (0.0, -0.3, 0.0),
        (0.0, 0.0, 0.3),
        (0.0, 0.0, -0.3),
        (0.3, -0.2, 0.1),
    ],
)
def test_constant_rate_propagation_matches_closed_form(rate):
    estimator = make_estimator()
    output = estimator.step(Sample(0.005, rate, (0.0, 0.0, 0.0)))
    expected = axis_angle(np.asarray(rate) * 0.005)
    assert np.max(np.abs(align(output.q_nb_estimate, expected) - expected)) <= Q_TOL
    assert abs(np.linalg.norm(output.q_nb_estimate) - 1.0) <= Q_TOL


def test_two_hundred_constant_rate_samples_match_closed_form_and_rotation_matrix():
    rate = np.array([0.3, -0.2, 0.1])
    estimator = make_estimator(axis_angle([0.2, -0.1, 0.05]))
    initial = estimator.estimate.q_nb_estimate
    output = None
    for tick in range(1, 201):
        output = estimator.step(Sample(tick * 0.005, rate, (0.0, 0.0, 0.0)))
    expected = qmul(initial, axis_angle(rate * 1.0))
    actual = align(output.q_nb_estimate, expected)
    assert np.max(np.abs(actual - expected)) <= Q_TOL
    assert abs(np.linalg.norm(actual) - 1.0) <= Q_TOL
    actual_matrix = np.array([rotate_n_to_b(actual, axis) for axis in np.eye(3)]).T
    expected_matrix = np.array([rotate_n_to_b(expected, axis) for axis in np.eye(3)]).T
    assert np.max(np.abs(actual_matrix - expected_matrix)) <= Q_TOL


def test_nonidentity_and_noncommuting_propagation():
    initial = axis_angle([0.2, -0.1, 0.05])
    xy = make_estimator(initial)
    xy.step(Sample(0.005, (0.3, 0.0, 0.0), (0.0, 0.0, 0.0)))
    actual = xy.step(Sample(0.010, (0.0, 0.3, 0.0), (0.0, 0.0, 0.0))).q_nb_estimate
    expected = qmul(qmul(initial, axis_angle([0.0015, 0.0, 0.0])), axis_angle([0.0, 0.0015, 0.0]))
    assert np.max(np.abs(align(actual, expected) - expected)) <= Q_TOL
    reverse = qmul(qmul(initial, axis_angle([0.0, 0.0015, 0.0])), axis_angle([0.0015, 0.0, 0.0]))
    assert not np.allclose(expected, reverse, rtol=0.0, atol=1e-9)


@pytest.mark.parametrize("rate", [0.0, 1e-12, 1e-9, 1e-6])
def test_zero_and_small_angle_propagation_is_finite(rate):
    output = make_estimator().step(Sample(0.005, (rate, 0.0, 0.0), (0.0, 0.0, 0.0)))
    expected = axis_angle([rate * 0.005, 0.0, 0.0])
    assert np.all(np.isfinite(output.q_nb_estimate))
    assert np.max(np.abs(output.q_nb_estimate - expected)) <= Q_TOL


def test_quaternion_sign_equivalence_and_canonical_output():
    positive = make_estimator((0.0, 1.0, 0.0, 0.0)).step(Sample(0.005, specific_force_b_m_s2=(0, 0, 0)))
    negative = make_estimator((0.0, -1.0, 0.0, 0.0)).step(Sample(0.005, specific_force_b_m_s2=(0, 0, 0)))
    assert np.array_equal(positive.q_nb_estimate, negative.q_nb_estimate)
    assert positive.q_nb_estimate[1] > 0.0


@pytest.mark.parametrize("rotation", [(0.1, 0, 0), (-0.1, 0, 0), (0, 0.1, 0), (0, -0.1, 0), (0.1, -0.1, 0)])
def test_stationary_gravity_correction_matches_independent_formula(rotation):
    initial = axis_angle(rotation)
    estimator = make_estimator(initial)
    result = estimator.process(Sample(0.005))
    predicted = rotate_n_to_b(initial, [0.0, 0.0, -1.0])
    innovation = np.cross([0.0, 0.0, -1.0], predicted)
    expected = qmul(initial, axis_angle(0.005 * innovation))
    expected /= np.linalg.norm(expected)
    assert result.diagnostics.correction_applied
    assert np.max(np.abs(align(result.estimate.q_nb_estimate, expected) - expected)) <= Q_TOL


def test_gravity_correction_does_not_create_absolute_yaw_observation():
    yaw_a = axis_angle([0.0, 0.0, 0.4])
    yaw_b = axis_angle([0.0, 0.0, -0.7])
    a = make_estimator(yaw_a).step(Sample(0.005)).q_nb_estimate
    b = make_estimator(yaw_b).step(Sample(0.005)).q_nb_estimate
    assert np.max(np.abs(a - yaw_a)) <= Q_TOL
    assert np.max(np.abs(b - yaw_b)) <= Q_TOL


def test_accelerometer_gate_float_boundaries_and_zero_force():
    params = load_estimator_parameters()
    lower = params.gravity_m_s2 - params.accelerometer_gate_deviation_m_s2
    upper = params.gravity_m_s2 + params.accelerometer_gate_deviation_m_s2
    cases = [
        (lower, True),
        (math.nextafter(lower, params.gravity_m_s2), True),
        (math.nextafter(lower, -math.inf), False),
        (upper, True),
        (math.nextafter(upper, params.gravity_m_s2), True),
        (math.nextafter(upper, math.inf), False),
    ]
    for magnitude, expected in cases:
        actual_norm = float(np.linalg.norm([magnitude, 0, 0]))
        assert (abs(actual_norm - params.gravity_m_s2) <= params.accelerometer_gate_deviation_m_s2) is expected
        result = make_estimator().process(Sample(0.005, specific_force_b_m_s2=(magnitude, 0, 0)))
        assert result.diagnostics.correction_eligible is expected
    zero = make_estimator().process(Sample(0.005, specific_force_b_m_s2=(0, 0, 0)))
    assert not zero.diagnostics.correction_eligible


def test_gap_recovery_uses_elapsed_time_and_caps_public_correction():
    estimator = make_estimator()
    estimator.step(Sample(0.005, specific_force_b_m_s2=(0, 0, 0)))
    before = estimator.estimate
    assert not estimator.process(Sample(0.010, valid=False)).diagnostics.accepted
    assert not estimator.process(Sample(0.015, valid=False)).diagnostics.accepted
    result = estimator.process(Sample(0.020, specific_force_b_m_s2=(9.80665, 0, 0)))
    assert result.diagnostics.elapsed_periods == 3
    assert result.diagnostics.missing_periods == 2
    assert result.diagnostics.gap_approximated
    assert result.diagnostics.correction_capped
    delta = qmul(before.q_nb_estimate * np.array([1, -1, -1, -1]), result.estimate.q_nb_estimate)
    angle = 2 * math.atan2(np.linalg.norm(delta[1:]), abs(delta[0]))
    assert angle == pytest.approx(0.01, abs=2e-12)


def test_gap_recovery_cap_at_nonzero_reset_boundary():
    estimator = make_estimator(epoch=8, time=25.0)
    estimator.step(Sample(25.005, specific_force_b_m_s2=(0, 0, 0)))
    estimator.process(Sample(25.010, valid=False))
    estimator.process(Sample(25.015, valid=False))
    result = estimator.process(Sample(25.020, specific_force_b_m_s2=(9.80665, 0, 0)))
    assert result.diagnostics.correction_capped
    assert result.diagnostics.elapsed_periods == 3
    assert result.diagnostics.missing_periods == 2


def test_gap_recovery_gyro_constant_approximation_at_nonzero_epoch():
    estimator = make_estimator(epoch=4, time=12.0)
    estimator.step(Sample(12.005, specific_force_b_m_s2=(0, 0, 0)))
    estimator.process(Sample(12.010, valid=False))
    output = estimator.process(Sample(12.015, gyro_b_rad_s=(0.0, 0.0, 0.2), specific_force_b_m_s2=(0, 0, 0)))
    expected = axis_angle([0.0, 0.0, 0.2 * 0.010])
    assert np.max(np.abs(output.estimate.q_nb_estimate - expected)) <= Q_TOL
    assert output.diagnostics.gap_approximated


def test_magnitude_clamp_helper_preserves_direction():
    result, capped = _magnitude_clamp(np.array([0.012, -0.016, 0.0]), 0.01)
    assert capped
    assert np.linalg.norm(result) == pytest.approx(0.01, abs=1e-15)
    assert np.cross(result, [0.012, -0.016, 0.0])[2] == pytest.approx(0.0, abs=1e-15)


@pytest.mark.parametrize(
    "sample",
    [
        Sample(0.005, valid=False),
        Sample(0.005, gyro_b_rad_s=(math.nan, 0, 0)),
        Sample(0.005, gyro_b_rad_s=(0, 0)),
        Sample(0.005, specific_force_b_m_s2=(0, math.inf, 0)),
        Sample(math.nan),
        Sample(0.004),
    ],
)
def test_invalid_sample_is_atomic(sample):
    estimator = make_estimator()
    before = estimator.estimate
    result = estimator.process(sample)
    after = estimator.estimate
    assert not result.diagnostics.accepted
    assert np.array_equal(before.q_nb_estimate, after.q_nb_estimate)
    assert np.array_equal(before.omega_b_estimate_rad_s, after.omega_b_estimate_rad_s)
    assert before.timestamp_s == after.timestamp_s


def test_duplicate_and_stale_timestamps_reject_then_next_grid_tick_recovers():
    estimator = make_estimator()
    estimator.step(Sample(0.005))
    assert not estimator.process(Sample(0.005)).diagnostics.accepted
    assert not estimator.process(Sample(0.0)).diagnostics.accepted
    recovered = estimator.process(Sample(0.010))
    assert recovered.diagnostics.accepted
    assert recovered.diagnostics.elapsed_periods == 1


@pytest.mark.parametrize("epoch,time", [(0, 0.0), (7, 12.0)])
def test_first_sample_must_be_first_due_tick_and_rejection_is_atomic(epoch, time):
    estimator = make_estimator(epoch=epoch, time=time)
    before = estimator.estimate
    rejected = estimator.process(Sample(time + 0.010))
    assert not rejected.diagnostics.accepted
    assert "first due tick" in rejected.diagnostics.reason
    assert np.array_equal(before.q_nb_estimate, estimator.estimate.q_nb_estimate)
    accepted = estimator.process(Sample(time + 0.005))
    assert accepted.diagnostics.accepted
    assert accepted.diagnostics.elapsed_periods == 1


@pytest.mark.parametrize(
    "sample",
    [
        Sample(1e308),
        Sample(0.005, gyro_b_rad_s=(1e308, 0, 0), specific_force_b_m_s2=(0, 0, 0)),
        Sample(0.005, gyro_b_rad_s=(10**1000, 0, 0), specific_force_b_m_s2=(0, 0, 0)),
        Sample(0.005, specific_force_b_m_s2=(1e308, 1e308, 1e308)),
    ],
)
def test_extreme_finite_sample_is_rejected_atomically_and_step_wraps(sample):
    estimator = make_estimator()
    before = estimator.estimate
    result = estimator.process(sample)
    assert not result.diagnostics.accepted
    assert np.array_equal(before.q_nb_estimate, estimator.estimate.q_nb_estimate)
    with pytest.raises(EstimatorContractError) as caught:
        estimator.step(sample)
    assert not caught.value.diagnostics.accepted


def test_step_raises_with_diagnostics_without_state_change():
    estimator = make_estimator()
    before = estimator.estimate
    with pytest.raises(EstimatorContractError) as caught:
        estimator.step(Sample(0.005, valid=False))
    assert not caught.value.diagnostics.accepted
    assert np.array_equal(estimator.estimate.q_nb_estimate, before.q_nb_estimate)


def test_reset_epoch_order_time_and_replay():
    estimator = make_estimator(epoch=1, time=2.0)
    first = estimator.step(Sample(2.005, gyro_b_rad_s=(0.1, 0.2, -0.1), specific_force_b_m_s2=(0, 0, 0)))
    with pytest.raises(EstimatorContractError):
        estimator.reset(EstimatorInitialState((1, 0, 0, 0), (0, 0, 0)), ResetEpoch(1, 2.005), 7)
    with pytest.raises(EstimatorContractError):
        estimator.reset(EstimatorInitialState((1, 0, 0, 0), (0, 0, 0)), ResetEpoch(2, 2.0), 7)
    estimator.reset(EstimatorInitialState((1, 0, 0, 0), (0, 0, 0)), ResetEpoch(2, 2.005), 7)
    second = estimator.step(Sample(2.010, gyro_b_rad_s=(0.1, 0.2, -0.1), specific_force_b_m_s2=(0, 0, 0)))
    assert np.max(np.abs(first.q_nb_estimate - second.q_nb_estimate)) <= Q_TOL


def test_repeated_reset_before_step_is_idempotent_with_new_epoch_id():
    estimator = make_estimator(epoch=1, time=4.0)
    first = estimator.reset(EstimatorInitialState((1, 0, 0, 0), (0, 0, 0)), ResetEpoch(2, 4.0), 9)
    second = estimator.reset(EstimatorInitialState((1, 0, 0, 0), (0, 0, 0)), ResetEpoch(3, 4.0), 9)
    assert np.array_equal(first.q_nb_estimate, second.q_nb_estimate)


def test_reset_rejects_nonunit_quaternion_and_bad_seed_atomically():
    estimator = make_estimator()
    before = estimator.estimate
    with pytest.raises(EstimatorContractError):
        estimator.reset(EstimatorInitialState((2, 0, 0, 0), (0, 0, 0)), ResetEpoch(1, 0), 7)
    with pytest.raises(EstimatorContractError):
        estimator.reset(EstimatorInitialState((1, 0, 0, 0), (0, 0, 0)), ResetEpoch(1, 0), -1)
    assert np.array_equal(before.q_nb_estimate, estimator.estimate.q_nb_estimate)


@pytest.mark.parametrize("initial,epoch", [(None, ResetEpoch(1, 0)), (EstimatorInitialState((1, 0, 0, 0), (0, 0, 0)), None)])
def test_reset_wrong_public_types_raise_contract_error_atomically(initial, epoch):
    estimator = make_estimator()
    before = estimator.estimate
    with pytest.raises(EstimatorContractError):
        estimator.reset(initial, epoch, 7)
    assert np.array_equal(before.q_nb_estimate, estimator.estimate.q_nb_estimate)


def test_input_and_output_arrays_are_isolated():
    q = np.array([1.0, 0.0, 0.0, 0.0])
    gyro = np.array([0.1, 0.0, 0.0])
    initial = EstimatorInitialState(q, np.zeros(3))
    estimator = AttitudeEstimator()
    estimator.reset(initial, ResetEpoch(0, 0), 7)
    q[0] = 0.0
    sample = Sample(0.005, gyro, np.array([0.0, 0.0, 0.0]))
    output = estimator.step(sample)
    gyro[0] = 99.0
    returned = output.q_nb_estimate
    returned[:] = 0.0
    assert estimator.estimate.q_nb_estimate[0] > 0.0
    assert estimator.estimate.omega_b_estimate_rad_s[0] == pytest.approx(0.1)


def test_configuration_line_endings_are_equivalent_and_semantic_change_rejects(tmp_path):
    g0_bytes = (REPO / "05_integration/b0/configs/b0_g0_contract.v2.json").read_bytes().replace(b"\r\n", b"\n")
    expected = hashlib.sha256(g0_bytes).hexdigest()
    assert expected == "5b95531a6f96cb67ce25f624d6921bd313696f3c0b9868ec1de13c24c34cd98c"
    for separator in (b"\n", b"\r\n", b"\r"):
        variant = tmp_path / f"g0-{len(separator)}.json"
        variant.write_bytes(separator.join(g0_bytes.split(b"\n")))
        assert _canonical_lf_digest(variant) == expected
    changed = g0_bytes.replace(b'"base_period_s": 0.0025', b'"base_period_s": 0.0030')
    assert hashlib.sha256(changed).hexdigest() != expected


def test_unapproved_estimator_configuration_change_fails_closed(tmp_path):
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    source_config = TRACK / "configs/b0_g2_estimator.v1.json"
    source_approval = TRACK / "configs/b0_g2_estimator_approval.v1.json"
    document = json.loads(source_config.read_text(encoding="utf-8"))
    document["implementation_choices"]["complementary_correction_gain_per_s"] = 2.0
    candidate = config_dir / source_config.name
    candidate.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    (config_dir / source_approval.name).write_bytes(source_approval.read_bytes())
    with pytest.raises(EstimatorContractError, match="differs from the design-accepted bytes"):
        load_estimator_parameters(candidate)


@pytest.mark.parametrize("mutation", ["numeric", "missing_field", "wrong_version", "missing_file"])
def test_loader_rejects_altered_missing_or_wrong_version_g0(tmp_path, mutation):
    source_g0 = REPO / "05_integration/b0/configs/b0_g0_contract.v2.json"
    g0_document = json.loads(source_g0.read_text(encoding="utf-8"))
    g0_path = tmp_path / "g0.json"
    if mutation == "numeric":
        g0_document["timing"]["base_period_s"] = 0.003
    elif mutation == "missing_field":
        del g0_document["timing"]["base_period_s"]
    elif mutation == "wrong_version":
        g0_document["schema_version"] = "b0-g0-contract/v999"
    if mutation != "missing_file":
        g0_path.write_text(json.dumps(g0_document, indent=2) + "\n", encoding="utf-8")

    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    source_config = TRACK / "configs/b0_g2_estimator.v1.json"
    source_approval = TRACK / "configs/b0_g2_estimator_approval.v1.json"
    candidate_document = json.loads(source_config.read_text(encoding="utf-8"))
    candidate_document["authority"]["g0_config_path"] = str(g0_path)
    candidate = config_dir / source_config.name
    candidate.write_text(json.dumps(candidate_document, indent=2) + "\n", encoding="utf-8")
    approval_document = json.loads(source_approval.read_text(encoding="utf-8"))
    approval_document["approved_config_canonical_lf_sha256"] = _canonical_lf_digest(candidate)
    (config_dir / source_approval.name).write_text(json.dumps(approval_document, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(EstimatorContractError):
        load_estimator_parameters(candidate)


def test_public_runtime_api_has_no_truth_input():
    names = set(AttitudeEstimator.process.__code__.co_varnames)
    assert "truth" not in " ".join(names).lower()
    assert "plant" not in " ".join(names).lower()
    estimator = make_estimator()
    with pytest.raises(TypeError):
        estimator.process(Sample(0.005), truth={"q_nb": [1, 0, 0, 0]})
