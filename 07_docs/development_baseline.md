# Development baseline B0 v0.2

Adopted 2026-10-09. This is a planning baseline, not an implementation release.
It supersedes v0.1 as the project-level priority. The previous navigation contract
is retained in [architecture](architecture.md) and assigned to EXT-NAV.

## Single objective

Implement and verify a minimal multirotor attitude-estimation and control loop:

command -> attitude controller -> rate controller -> bounded actuator model
-> rotational dynamics -> IMU -> attitude estimator -> controller.

Truth is available only to sensor generation and independent evaluation.

## Included

- Rigid-body rotational dynamics with positive-definite inertia and quaternion state.
- Explicit actuator limits and a simple documented actuator response model.
- Gyroscope and accelerometer models consistent with the stated motion assumptions.
- Quaternion propagation and basic complementary attitude fusion.
- Cascaded attitude/rate control with saturation and anti-windup.
- C++17 control core with unit tests; Python simulation and analysis.
- Deterministic configuration, reset, seed, timestamps, and repeatable evidence.
- Nominal, initial-offset, step, disturbance, noise, saturation, and recovery cases.

Gyroscope/accelerometer fusion alone does not make absolute yaw observable.
Report roll/pitch correction and yaw drift separately. Translational acceleration
must not be silently interpreted as gravity; B0 must declare its bounded-motion
assumptions and test the behavior when they are violated.

## Excluded from B0

Position/velocity loops, waypoint flight, full INS/GNSS EKF, UKF comparisons,
geometric/LQR/MPC control, TCN, VO/SLAM, PX4, embedded targets, fixed-wing models,
HIL, generic verification-suite integration, and papers.

## Delivery gates

| Gate | Deliverable | Exit condition |
|---|---|---|
| G0 | Executable contracts and scenario definitions | Frames, signs, time, inertia, actuator limits, estimator assumptions and metric definitions reviewed |
| G1 | Plant and sensors | Analytical rotation cases, specific-force signs, sampling and seed tests pass independently |
| G2 | Estimator and controller components | Quaternion, feedback sign, anti-windup, reset and invalid-input tests pass |
| G3 | Estimated-state closed loop | Required scenario suite runs; truth cannot enter controller inputs; bounded cases recover |
| G4 | Reproducible release evidence | Clean-checkout command, raw artifacts, plots, manifest, report and defect-detection demonstration retained |

G0 must define settling band/dwell, overshoot interpretation, rate/torque limits,
simulation horizon, tolerances, and comparison procedures before tuning.
Existing CTL thresholds are legacy candidates; their applicability must be reviewed
under [requirements](requirements.md). No new performance value is invented here.

## Definition of ready

An increment has bounded inputs/outputs, units, frames, assumptions, acceptance
checks, dependency status, and identified evidence. Hardware is not needed for B0.

## Definition of done

Scoped behavior is implemented without unexplained skips or placeholders; mandatory
checks pass; nominal, boundary and invalid inputs are covered; configuration and
software revision are recorded; results reproduce; limitations and traceability
are updated. G4 additionally proves selected tests detect intentionally introduced
sign, unit, or anti-windup defects in isolated test variants.

A baseline is complete when G0-G4 pass, regardless of extension or paper status.
