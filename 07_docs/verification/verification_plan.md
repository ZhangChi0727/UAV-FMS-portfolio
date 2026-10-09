# Verification plan

## Active scope

B0 v0.2: independent plant/sensor checks, estimator/controller component checks,
estimated-state integration, and reproducible scenario evidence.
The [development baseline](../development_baseline.md) owns G0-G4.

## Evidence chain

Obligation -> operating conditions -> scenario/procedure -> software revision
-> raw signals -> independent oracle -> metric/outcome -> report.

Record configuration hash, seed, clock/sample policy, environment, units, raw artifact
location/checksum and analysis version. Truth is accessible to evaluation but not
to the controller or estimator. An invalid setup yields inconclusive evidence,
not a pass. Keep experimental failure distinct from execution/tool failure.

## B0 checks

- Plant: analytical angular motion, quaternion normalization, inertia constraints.
- Sensors: specific-force sign, bias/noise units, timestamp and repeatability.
- Estimation: gyro propagation, bounded roll/pitch correction, yaw observability
  limitation, invalid samples, reset and acceleration-contamination behavior.
- Control: feedback sign, cascade behavior, saturation and anti-windup recovery.
- Integration: nominal, initial-offset, step, disturbance, noise and saturation cases.
- Evidence: independent metric checks and known-defect detection; retain negative runs.

Freeze settling band/dwell, overshoot definition, envelope, limits, tolerances and
run length at G0. Statistical trial counts follow an experimental rationale;
they are not fixed by the old scaffold.

## Retained navigation contract

EXT-NAV retains nominal/error-state dimensions, stationary propagation, normalization,
covariance and Jacobian checks, GPS correction and invalid-time tests.
Strict expected failures identify pending behavior. GPS-outage development runs
do not prove NAV-REQ-001 compliance without the approved sensor/aiding/statistical
conditions. NAV-REQ-002 requires recorded hardware, warmup, timer and cycle definition.

## Execution levels

Local simulation, recorded-data replay, board execution, real-time closed-loop HIL
and physical flight are distinct evidence levels. A board receiving replay data
is not itself HIL. State clock synchronization, latency and fidelity limitations
when comparing levels.

## CI

Run pytest within each track. Preserve existing navigation regression contracts.
Add mandatory B0 checks as each increment is implemented; do not hide completed
scope failures with continue-on-error. Skips/xfails are not completion evidence.
Research notebooks audit records, not controller correctness.
