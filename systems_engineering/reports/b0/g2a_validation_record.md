# B0 G2-A attitude-estimator validation record

Date: 2026-10-14 (Australia/Perth). Implementation/evidence source commit:
`f70c243aa304cd3f5f5e5c092e0fc41fe53a5518`. This record covers the estimator
module only; it is not G2 completion, closed-loop performance evidence, or
authorization to start G2-B.

## Design authority

PA `DESIGN_ACCEPT` applies to S0 commit
`b7efe7c7e3b3b33e31661272f6f7551478782661`. The accepted design fixes the
correction gain at 1.0 s^-1, uses the inclusive acceleration-norm gate
`|norm(f)-g| <= 1.4709975 m/s^2`, limits each correction to 0.01 rad, uses the
cross product of normalized measured and predicted stationary specific force
with right-multiplication, and recovers a sample gap by holding the current
gyro across the elapsed accepted-state interval while exposing diagnostics.

## Actual execution

| Environment / source | Command scope | Actual result |
|---|---|---|
| Local estimator track, Python 3.11 virtual environment | `python -m ruff check .`; `python -m pytest -q tests`; `python evidence.py --output ...` | Ruff passed; 52 passed with 0 failed/skipped/xfailed; evidence generation passed |
| GitHub Actions run `38500645681`, Ubuntu latest, Python 3.11, NumPy 1.26.4, pytest 8.3.5, ruff 0.8.6 | Required B0 G2-A estimator evidence-producing job | Estimator job succeeded; governance failed as expected before this ledger was advanced to the new source commit |
| System-engineering traceability checker | Schema, identities, source/applicability hashes, dependency closure and report projection | 30 requirements, 26 model identities, 29 specifications, 3 production records, 9 executed specifications, 0 accepted records and 0 satisfied requirements |

The CI artifact is `b0-g2a-estimator-evidence`, artifact ID `11865801098`,
containing `g2a_estimator_evidence.json`. The retained file SHA-256 is
`cd25a5271e80792e9ed971f49daa2fb4fa9d691ab1cbb27bf26c7b47ca3e61b1`; the
download archive SHA-256 is
`5a8dea96e68802d10cdbe5f5cce59d5434238c66efac39703649e35f6f2d6b35`.
The artifact expires on 2027-01-12 and is recorded as `remote_unverified` until
an independent reviewer verifies retained bytes and accepts the evidence.

## Acceptance matrix

| Work-order item | Evidence / location | Candidate result |
|---|---|---|
| Explicit initialization and reset epoch | `02_estimation/b0/estimator.py`; reset and time-grid tests | Pass |
| Scalar-first Hamilton gyro propagation and normalization | `B0-VER-ESTIMATOR-PROPAGATION`; propagation evidence probe | Complete candidate evidence |
| Gravity-direction roll/pitch correction with declared sign/order | `B0-VER-ESTIMATOR-FUSION`; fusion and correction-limit probes | Complete candidate evidence |
| Inclusive acceleration gate and diagnostics | estimator configuration, contamination/gating tests and artifact | Pass at module scope |
| Gap recovery and stale/invalid input atomicity | gap-recovery and atomic-rejection probes | Pass at module scope |
| Truth isolation | public estimator interface and tests accept IMU/configuration/initialization only | Pass by inspection and negative tests |
| Relative-yaw limitation | `B0-VER-YAW-LIMITATION`; artifact limitation statement | Partial; no absolute-yaw claim |
| Acceleration-contamination characterization | `B0-VER-ACCEL-CONTAMINATION`; selected gate cases | Partial; integrated scenario characterization remains G3 work |
| Controller-facing state-estimate interface | immutable estimate/result objects in `estimator.py` | Available for subsequent G2-B integration |
| CI and auditable evidence chain | run, commit, artifact IDs/hashes, ledger records and closure checker | Candidate complete; PA review pending |

## S0 row-to-test closure

| S0 row | Executed test node(s) |
|---|---|
| A-PROP-01 | `test_constant_rate_propagation_matches_closed_form`; `test_two_hundred_constant_rate_samples_match_closed_form_and_rotation_matrix` |
| A-PROP-02/03 | `test_zero_and_small_angle_propagation_is_finite`; `test_nonidentity_and_noncommuting_propagation`; `test_quaternion_sign_equivalence_and_canonical_output` |
| A-FUSE-01/02 | `test_stationary_gravity_correction_matches_independent_formula`; `test_gravity_correction_does_not_create_absolute_yaw_observation` |
| A-GATE-01/02 | `test_accelerometer_gate_float_boundaries_and_zero_force`; retained artifact `observations.acceleration_contamination_gate` |
| A-CAP-01 | `test_gap_recovery_uses_elapsed_time_and_caps_public_correction`; `test_gap_recovery_cap_at_nonzero_reset_boundary` |
| A-TIME-01/02 | `test_first_sample_must_be_first_due_tick_and_rejection_is_atomic`; `test_duplicate_and_stale_timestamps_reject_then_next_grid_tick_recovers` |
| A-VALID-01 | `test_invalid_sample_is_atomic`; `test_extreme_finite_sample_is_rejected_atomically_and_step_wraps` |
| A-RESET-01 | `test_reset_epoch_order_time_and_replay`; `test_repeated_reset_before_step_is_idempotent_with_new_epoch_id`; reset wrong-type/non-unit atomicity tests |
| A-ISO-01/A-TRUTH-01 | `test_input_and_output_arrays_are_isolated`; `test_public_runtime_api_has_no_truth_input` |
| A-CONFIG-01 | line-ending, unapproved-estimator-change and altered/missing/wrong-version G0 loader tests |

## Limitations and disposition

- Gravity correction observes roll/pitch, not absolute yaw; yaw remains relative
  to initialization and integrates gyro error.
- The evidence is deterministic module evidence, not plant-estimator-controller
  closed-loop SIL, real-time HIL, board execution, flight evidence, or a
  performance claim.
- Acceleration contamination is demonstrated only for the retained selected
  cases. Broader event characterization and truth-based scoring belong to the
  evaluator/integration boundary in G3 and must not feed estimator inputs.
- Both ledger records remain pending review. Even the complete propagation and
  fusion record does not satisfy a requirement until evidence availability,
  applicability and independent acceptance conditions are all met.

Candidate disposition: ready for PA review after the final branch CI succeeds.
No merge, Issue closure, branch deletion, G2-B start or G3 authorization is
implied by this record.
