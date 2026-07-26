# Development Baseline v0.1

## Purpose

This baseline converts the Phase 0 scaffold into a controlled starting point for
implementation. It fixes the minimum technical contract, verification approach,
and delivery gates needed to develop without creating a speculative project plan.

The first vertical slice is:

```text
deterministic truth trajectory
    -> synthetic IMU and GPS
    -> Python error-state EKF
    -> automated verification evidence
```

## Scope

### Included in v0.1

- Navigation frames, units, quaternion convention, state definition, and interfaces.
- Verification conditions for the existing navigation requirements.
- Deterministic in-memory truth, IMU, and GPS fixtures.
- Python EKF prediction and GPS correction.
- Unit, analytical, and deterministic scenario tests.
- A reproducible runtime benchmark for `NAV-REQ-002`.
- Track-local CI for the completed navigation scope.
- Initial evidence recorded in `RESULTS.md` and the V&V report.

### Deferred

- Visual odometry and navigation mode management.
- UKF comparison and the full Monte Carlo campaign.
- C++ EKF and Python bindings.
- Geometric control and LQR.
- TCN training and fault-classification evidence.
- MATLAB/Simulink integration.
- Safety conclusions and final portfolio presentation.

Deferred work is sequenced after the navigation slice; it is not removed from
the portfolio scope.

## Governing Technical Decisions

The navigation conventions and interface definitions in
[`architecture.md`](architecture.md) are normative for the v0.1 slice.

The EKF shall use:

- a 16-element nominal state containing position, velocity, a unit quaternion,
  accelerometer bias, and gyroscope bias;
- a 15-element local error state containing position, velocity, attitude, and
  the two bias errors;
- a 15 by 15 error covariance;
- multiplicative quaternion correction and normalization; and
- a Joseph-form measurement covariance update.

The current Python and C++ placeholder implementations use a 16 by 16
covariance. Migrating that scaffold is planned implementation work, not evidence
that the v0.1 contract has already been met.

## Planned Delivery Increments

### Increment 1: baseline contract

- Approve this baseline.
- Freeze the navigation and sensor interfaces.
- Make pending EKF behavior visible through strict expected-failure tests.
- Run tests from the track directory in CI.

Exit condition: reviewers agree that the first implementation slice is
unambiguous enough to start.

### Increment 2: deterministic sensor fixture

- Generate stationary, constant-velocity, constant-acceleration,
  constant-yaw-rate, and GPS-outage scenarios.
- Require an explicit random seed for stochastic scenarios.
- Verify timestamps, sample rates, shapes, validity flags, and reproducibility.
- Keep tests in memory; persistence is optional until a shared dataset schema is
  needed.

Exit condition: analytical truth and sensor cases pass without the EKF.

### Increment 3: EKF prediction

- Implement initialization and input validation.
- Propagate position, velocity, quaternion, and biases.
- Propagate the 15 by 15 covariance.
- Compare the analytical transition Jacobian with a numerical reference.
- Check quaternion norm, covariance symmetry, and covariance eigenvalues.

Exit condition: prediction tests pass and their expected-failure markers are
removed.

### Increment 4: GPS correction

- Implement position and velocity innovation.
- Apply multiplicative error-state correction.
- Use a Joseph-form covariance update.
- Expose innovation information needed for later consistency analysis.

Exit condition: correction tests pass and uncertainty decreases in the observed
state components.

### Increment 5: navigation evidence

- Execute deterministic end-to-end navigation scenarios.
- Define and execute the `NAV-REQ-002` benchmark protocol.
- Record configuration, environment, raw artifacts, summary, and pass/fail.
- Do not claim `NAV-REQ-001` compliance until its sensor and aiding assumptions
  are approved and the required statistical campaign has been run.

Exit condition: results are reproducible from a clean checkout and traceable to
the applicable requirement.

## Lightweight Backlog

Use one milestone named `Baseline v0.1 - Python navigation vertical slice`.
Create implementation issues in this order:

1. Approve navigation conventions and EKF architecture.
2. Approve verification conditions for `NAV-REQ-001` and `NAV-REQ-002`.
3. Add the deterministic truth and IMU/GPS fixture.
4. Implement EKF initialization and input validation.
5. Implement EKF prediction and covariance propagation.
6. Implement GPS correction.
7. Add analytical and numerical-Jacobian verification.
8. Add deterministic navigation scenario evaluation.
9. Benchmark the EKF update cycle.
10. Record navigation evidence in `RESULTS.md` and the V&V report.

These items are a dependency-ordered backlog, not a fixed-duration schedule.

## Definition of Ready

An implementation issue is ready when:

- its scope is bounded;
- input and output interfaces are defined;
- frames, units, signs, and array shapes are known;
- acceptance checks are written before implementation;
- dependencies and deferred behavior are explicit;
- required evidence is identified;
- it does not require unavailable MATLAB functionality; and
- it does not introduce a new requirement identifier without requirements review.

## Definition of Done

An implementation issue is done when:

- production code implements the approved scope;
- nominal, boundary, and invalid-input tests pass;
- no unexplained skip or `NotImplementedError` remains in that scope;
- numerical invariants are checked where applicable;
- formatting and static checks pass;
- public interfaces document units and shapes;
- relevant artifacts can be reproduced;
- requirement traceability is updated where applicable;
- limitations and deferred behavior are recorded; and
- CI reports failures rather than suppressing them for the completed scope.

Execution without an exception is not sufficient evidence for a numerical
algorithm.

## Pull Request Policy

- Keep each pull request to one coherent increment.
- Activate strict expected-failure tests by removing their marker as behavior is
  implemented.
- Include the requirement or technical contract being verified.
- Report exact commands and environments used for validation.
- Do not add generated results to `RESULTS.md` unless the underlying artifact is
  reproducible and retained.
- Default implementation pull requests to draft until their exit condition is
  met.

## Baseline Change Control

Changes to frames, quaternion convention, state ordering, covariance dimension,
sensor semantics, or requirement verification conditions affect downstream
tracks. Such changes require an architecture or requirements update in the same
pull request and an explanation of migration impact.

Algorithm tuning, fixture configuration, and benchmark configuration are
version-controlled inputs. They are not new system requirements.
