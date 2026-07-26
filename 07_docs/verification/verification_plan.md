# Verification Plan

## Status

Baseline v0.1 defines the evidence workflow and the gates for the Python
navigation vertical slice. Later tracks shall extend this plan without weakening
completed gates.

## Verification Levels

1. Unit verification: functions, input validation, and numerical invariants.
2. Analytical verification: stationary and closed-form motion cases.
3. Component verification: deterministic sensor fixture and EKF behavior.
4. Integration verification: multiple components over a mission scenario.
5. Requirement verification: approved scenarios and statistical or timing analysis.

## Evidence Chain

Each compliance result shall trace:

```text
requirement
    -> operating conditions and configuration
    -> test or analysis procedure
    -> software revision
    -> raw artifact
    -> summarized metric
    -> pass/fail statement
```

Expected evidence locations are:

- automated tests beside the applicable track;
- reusable test configurations under the applicable track;
- generated raw artifacts under a documented results directory;
- summarized portfolio results in `RESULTS.md`; and
- final argument and traceability in `07_docs/v_and_v_report.md`.

Generated numerical claims shall not be entered in `RESULTS.md` unless their
configuration and raw artifact can be reproduced.

## Navigation Baseline Verification

### Contract tests

Pending Phase 3A tests are marked as strict expected failures. This makes the
unimplemented contract visible while keeping the baseline CI honest. An
implementation pull request shall remove the applicable marker as part of
making the behavior pass.

The contract covers:

- nominal and error-state dimensions;
- identity quaternion initialization;
- stationary propagation;
- quaternion normalization;
- covariance symmetry and positive eigenvalues;
- local error-state transition structure;
- GPS correction direction and uncertainty reduction; and
- rejection of invalid time steps.

### Deterministic scenario tests

The fixture shall be checked independently from the EKF before end-to-end use.
Analytical cases shall precede stochastic cases. Randomized tests shall report
their seed on failure.

### NAV-REQ-001

The current requirement is not compliance-ready until the sensor profile,
aiding availability, trajectory, initialization uncertainty, error metric, and
statistical procedure in `requirements.md` are approved.

Development GPS-outage cases may be used to expose drift and regressions, but
they shall not be labelled as compliance evidence.

### NAV-REQ-002

The benchmark shall isolate the defined EKF cycle, use a monotonic high-resolution
timer, include a documented warm-up, and retain raw measurements. Hardware and
software environment metadata are part of the result.

## Baseline Gates

### Gate 0: contract approved

- Requirements interpretation reviewed.
- Architecture conventions reviewed.
- Pending behavior encoded in tests.
- Track-local CI passes.

### Gate 1: deterministic fixture complete

- Analytical fixture tests pass.
- Sampling and reproducibility tests pass.
- Scenario configuration is version controlled.

### Gate 2: EKF component complete

- Prediction and GPS-correction tests pass without expected-failure markers.
- Numerical invariants pass.
- Analytical and numerical Jacobians agree within the approved tolerance.
- CI enforces the completed scope.

### Gate 3: navigation evidence complete

- Requirement operating conditions are approved.
- Required scenario or benchmark is executed from a clean revision.
- Raw evidence and environment metadata are retained.
- `RESULTS.md` and the V&V report link the evidence and record pass/fail.

## CI Policy

- Pytest runs from inside each track directory.
- Completed checks are mandatory.
- Planned work uses explicit skip or strict expected-failure markers with a phase
  reason.
- Workflow-level `continue-on-error` shall not hide failure in completed scope.
- C++ and other algorithm tracks become mandatory when their baseline gate is
  activated.
