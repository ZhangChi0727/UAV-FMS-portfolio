# B0 G2-A attitude-estimator validation record

Date: 2026-10-14 (Australia/Perth). Implementation/evidence source commit:
`31a3412f94cc5ebe2a394ef2a3eba98b240a6d40`. This record covers the estimator
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
| Local estimator track, Python 3.11 virtual environment | `python -m ruff check .`; `python -m pytest -q tests`; `python evidence.py --output ...` | Ruff passed; 39 passed with 0 failed/skipped/xfailed; evidence generation passed |
| GitHub Actions run `38498412303`, Ubuntu latest, Python 3.11, NumPy 1.26.4, pytest 8.3.5, ruff 0.8.6 | Required B0 G2-A estimator job plus the six retained jobs | 7/7 jobs succeeded |
| System-engineering traceability checker | Schema, identities, source/applicability hashes, dependency closure and report projection | 30 requirements, 26 model identities, 29 specifications, 3 production records, 9 executed specifications, 0 accepted records and 0 satisfied requirements |

The CI artifact is `b0-g2a-estimator-evidence`, artifact ID `11864753892`,
containing `g2a_estimator_evidence.json`. The retained file SHA-256 is
`9d0accc7d79fe3740d7c1a61327b192a40e5fccd4bab5c60cacac9ae9a82b978`; the
download archive SHA-256 is
`cc5429312de6b1b04776705e56be4d0dd6284c308e8e0ce66f186072538bf03e`.
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
