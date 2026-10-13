# B0 joint requirement baseline

> Candidate pending D2; no execution result is claimed.

## B0-REQ-0001 — Bounded attitude experiment

The B0 system shall execute a configured bounded multirotor attitude-estimation and control experiment without representing the experiment as full-flight capability.

**Acceptance:** Inspection confirms the joint baseline includes the bounded experiment and excludes translation, flight, hardware and unactivated extensions.

**Verification:** B0-VER-SCOPE-INSPECTION

- `B0-VER-SCOPE-INSPECTION`: inspection; status `not_run`.

## B0-REQ-0002 — Deterministic configuration and replay

The B0 system shall produce repeatable samples and state evolution for identical approved configuration, seed, initial state, input sequence, reset sequence and software revision.

**Acceptance:** The procedure in B0-VER-REPLAY compares two approved replays at the G0 reset-replay fields and tolerances and records configuration, seed and revision.

**Verification:** B0-VER-REPLAY

- `B0-VER-REPLAY`: test; status `not_run`.

## B0-REQ-0003 — Runtime truth isolation

The B0 system shall prevent live plant truth from entering estimator or controller runtime inputs after explicit initialization while permitting truth to reach sensor generation and independent evaluation.

**Acceptance:** Static interface inspection and a later integrated negative test show no runtime truth path to estimator or controller, using the G0 truth_visibility and truth_inputs_forbidden fields.

**Verification:** B0-VER-TRUTH-BOUNDARY

- `B0-VER-TRUTH-BOUNDARY`: inspection; status `not_run`.

## B0-REQ-0004 — Shared frames units and quaternion convention

The B0 system shall represent exchanged quantities using the approved NED and body frames, SI units, and scalar-first Hamilton quaternion convention.

**Acceptance:** Inspection and component analytical cases confirm every interface and oracle references the approved G0 convention fields without a conflicting local definition.

**Verification:** B0-VER-CONVENTIONS

- `B0-VER-CONVENTIONS`: inspection; status `not_run`.

## B0-REQ-0005 — Rigid-body rotational dynamics

The B0 plant shall propagate body angular velocity using the approved rigid-body rotational equation and positive-definite inertia contract.

**Acceptance:** Analytical zero-torque and principal-axis cases match an independent equation oracle at the G0 precision and inertia references.

**Verification:** B0-VER-PLANT-DYNAMICS

- `B0-VER-PLANT-DYNAMICS`: test; status `not_run`.

## B0-REQ-0006 — Quaternion plant state

The B0 plant shall propagate and normalize its scalar-first attitude quaternion using the approved body-rate and frame convention.

**Acceptance:** Independent constant-rate analytical cases account for q/-q equivalence and confirm normalization within the approved G0 tolerance.

**Verification:** B0-VER-PLANT-QUATERNION

- `B0-VER-PLANT-QUATERNION`: test; status `not_run`.

## B0-REQ-0007 — Paired torque command

The B0 controller shall publish one timestamped torque command that pairs requested torque, limited target and saturation status from the same controller due tick.

**Acceptance:** Interface inspection and a later timing test confirm the three fields and timestamp correspond to one due tick as defined by the G0 torque-command and request-limit-pairing fields.

**Verification:** B0-VER-PAIRED-COMMAND

- `B0-VER-PAIRED-COMMAND`: test; status `not_run`.

## B0-REQ-0008 — Limited-target actuator dynamics

The B0 actuator shall advance its response using only the held limited target from the latest eligible paired torque command.

**Acceptance:** Component tests compare the response with an independent first-order and clamp oracle and reject a raw-request dynamics path using the G0 dynamics_input field.

**Verification:** B0-VER-ACTUATOR-DYNAMICS

- `B0-VER-ACTUATOR-DYNAMICS`: test; status `not_run`.

## B0-REQ-0009 — Actuator feedback pairing

The B0 actuator shall publish actual torque and the originating paired-command timestamp in actuator feedback.

**Acceptance:** A multi-rate interface test confirms feedback preserves the eligible command timestamp and corresponding limited target according to the G0 held-command contract.

**Verification:** B0-VER-PAIRED-FEEDBACK

- `B0-VER-PAIRED-FEEDBACK`: test; status `not_run`.

## B0-REQ-0010 — Gyroscope measurement

The B0 IMU shall produce timestamped body-frame angular-rate measurements with the approved bias, noise, validity and seed semantics.

**Acceptance:** Stationary, constant-rate, bias and deterministic-noise component cases match independent signal and random-sequence oracles.

**Verification:** B0-VER-IMU-GYRO

- `B0-VER-IMU-GYRO`: test; status `not_run`.

## B0-REQ-0011 — Accelerometer specific force

The B0 IMU shall produce timestamped body-frame specific-force measurements using the approved gravity sign, bias, noise, validity and seed semantics.

**Acceptance:** Aligned and rotated stationary cases, bias and deterministic-noise cases match the independent G0 specific-force equation and sign oracle.

**Verification:** B0-VER-IMU-SPECIFIC-FORCE

- `B0-VER-IMU-SPECIFIC-FORCE`: test; status `not_run`.

## B0-REQ-0012 — Estimator propagation

The B0 estimator shall propagate and normalize a scalar-first attitude estimate from valid gyroscope samples and approved positive time increments.

**Acceptance:** Planned component tests compare constant-rate propagation with an independent quaternion oracle and verify normalization and invalid-dt rejection.

**Verification:** B0-VER-ESTIMATOR-PROPAGATION

- `B0-VER-ESTIMATOR-PROPAGATION`: test; status `not_run`.

## B0-REQ-0013 — Roll and pitch fusion

The B0 estimator shall apply bounded accelerometer-based roll and pitch correction only when the approved validity and bounded-specific-force conditions permit it.

**Acceptance:** Planned stationary-tilt and gated-contamination tests compare with an independent tilt oracle and the G0 estimator correction conditions.

**Verification:** B0-VER-ESTIMATOR-FUSION

- `B0-VER-ESTIMATOR-FUSION`: test; status `not_run`.

## B0-REQ-0014 — Yaw observability limitation

The B0 system shall report yaw as relative propagation and drift without claiming absolute yaw observability from gyroscope and accelerometer measurements alone.

**Acceptance:** Inspection and the noise/bias scenario report separate roll/pitch correction from relative yaw drift and contain no absolute-yaw recovery claim.

**Verification:** B0-VER-YAW-LIMITATION

- `B0-VER-YAW-LIMITATION`: analysis; status `not_run`.

## B0-REQ-0015 — Acceleration contamination handling

The B0 estimator shall expose the approved limitation or correction-gating status when non-gravitational specific force violates its bounded tilt-correction assumptions.

**Acceptance:** The planned contamination provision observes required raw signals and limitation status and classifies the case as limitation characterization rather than performance pass.

**Verification:** B0-VER-ACCEL-CONTAMINATION

- `B0-VER-ACCEL-CONTAMINATION`: test; status `not_run`.

## B0-REQ-0016 — Cascaded attitude and rate control

The B0 controller shall compute body-torque request through the approved attitude-error and body-rate feedback signs in a cascaded attitude and rate structure.

**Acceptance:** Planned unit tests use independent sign and axis oracles for positive/negative attitude and rate errors and reject the opposite-feedback mutation.

**Verification:** B0-VER-CONTROLLER-SIGN

- `B0-VER-CONTROLLER-SIGN`: test; status `not_run`.

## B0-REQ-0017 — Unique controller saturation responsibility

The B0 controller shall be the sole component that limits requested body torque to the approved target bounds and sets the paired saturation status.

**Acceptance:** Boundary tests exercise every axis and confirm request, limited target and saturation status against the G0 controller limits while no downstream component reclamps the target.

**Verification:** B0-VER-CONTROLLER-SATURATION

- `B0-VER-CONTROLLER-SATURATION`: test; status `not_run`.

## B0-REQ-0018 — Anti-windup update

The B0 controller shall update each rate-integral contribution using the approved conditional-integration and paired-feedback back-calculation rule and shall enforce the approved per-axis integral bounds.

**Acceptance:** Planned discrete-step tests independently calculate conditional integration, back-calculation and each axis bound from the approved G0 anti-windup fields.

**Verification:** B0-VER-ANTI-WINDUP

- `B0-VER-ANTI-WINDUP`: test; status `not_run`.

## B0-REQ-0019 — Invalid input rejection

The B0 system shall reject invalid, non-finite, stale, mis-shaped or non-positive-time inputs according to the owning component contract without silently advancing state.

**Acceptance:** Negative-dt, stale-timestamp and representative invalid-value tests observe the approved rejection reason and unchanged owned state.

**Verification:** B0-VER-INVALID-INPUT

- `B0-VER-INVALID-INPUT`: test; status `not_run`.

## B0-REQ-0020 — Reset contract

The B0 system shall reset all stateful components to explicit initial state, seed and epoch-local scheduling while preserving the monotonically increasing scenario clock and discarding pre-reset held commands and feedback.

**Acceptance:** The reset provision verifies the G0 reset tick, epoch-local first due updates, scenario timestamps, cleared held data and deterministic comparison window.

**Verification:** B0-VER-RESET

- `B0-VER-RESET`: test; status `not_run`.

## B0-REQ-0021 — Deterministic scheduling and timestamps

The B0 execution adapter shall schedule component updates and construct timestamps from integer base ticks using the approved due-phase, consumption and held-command rules.

**Acceptance:** A trace inspection and later multi-rate test match every produced/consumed sample and command to the G0 sequence, period, first-due-tick and timestamp rules.

**Verification:** B0-VER-SCHEDULING

- `B0-VER-SCHEDULING`: test; status `not_run`.

## B0-REQ-0022 — Approved scenario suite

The B0 system shall support the approved normal, initial-offset, signed-step, disturbance, noise-and-bias, saturation-withdrawal, acceleration-contamination, and invalid-input-and-reset scenarios.

**Acceptance:** Inspection confirms each approved G0 v2 scenario ID has a verification purpose, required observations, applicable criteria, responsibility and invalid-result handling.

**Verification:** B0-VER-SCENARIO-CATALOGUE

- `B0-VER-SCENARIO-CATALOGUE`: inspection; status `not_run`.

## B0-REQ-0023 — Independent evaluation

The B0 evaluator shall compute acceptance metrics independently of estimator and controller implementations using the approved raw signals, windows, units, aggregation and invalid-data rules.

**Acceptance:** Design inspection identifies a distinct oracle and all required raw-signal dependencies for each verification provision; later executions use the G0 metric definitions and result classes.

**Verification:** B0-VER-EVALUATOR-INDEPENDENCE

- `B0-VER-EVALUATOR-INDEPENDENCE`: inspection; status `not_run`.

## B0-REQ-0024 — Evidence provenance

The B0 release evidence shall identify software revision, approved configuration hash, scenario, seed, environment, command, raw artifact, metric implementation and terminal result classification.

**Acceptance:** The planned evidence manifest schema and release demonstration require every listed provenance field and reject missing or mismatched versions; execution remains assigned to later stages.

**Verification:** B0-VER-EVIDENCE-PROVENANCE

- `B0-VER-EVIDENCE-PROVENANCE`: inspection; status `not_run`.

## B0-REQ-0025 — Defect-detection demonstration

The B0 release process shall demonstrate that selected independent checks detect isolated sign, unit, quaternion-ordering or anti-windup defects without modifying the approved production baseline.

**Acceptance:** The G4 provision defines isolated variants, expected failing checks, restoration controls and retained outcomes; this baseline contains no fabricated mutation result.

**Verification:** B0-VER-DEFECT-DETECTION

- `B0-VER-DEFECT-DETECTION`: demonstration; status `not_run`.

## B0-REQ-0026 — Implementation language boundary

The B0 implementation shall provide the control core in C++17 and may use Python for simulation, orchestration and independent analysis through the approved interface boundary.

**Acceptance:** Build and interface inspection confirm the control-core target uses C++17 and Python-facing integration does not bypass the declared messages or truth boundary.

**Verification:** B0-VER-LANGUAGE-BOUNDARY

- `B0-VER-LANGUAGE-BOUNDARY`: inspection; status `not_run`.

## B0-REQ-0027 — Clean-checkout reproduction

The B0 release shall be reproducible from a clean checkout using documented dependency versions and commands without relying on untracked developer state.

**Acceptance:** The G4 reproduction provision starts from a clean revision, installs pinned dependencies, runs documented commands and verifies retained artifact hashes; execution is not claimed in G1.5-B.

**Verification:** B0-VER-CLEAN-CHECKOUT

- `B0-VER-CLEAN-CHECKOUT`: demonstration; status `not_run`.

## B0-REQ-0028 — Legacy control disposition

The B0 system shall retain CTL-REQ-001 and CTL-REQ-002 unchanged as historical references and shall record their approved not-applicable disposition for current B0 without a satisfaction claim.

**Acceptance:** Inspection confirms both historical records and thresholds are unchanged, the approval locator resolves, current B0 says not applicable, and no satisfied/pass state is attached.

**Verification:** B0-VER-LEGACY-DISPOSITION

- `B0-VER-LEGACY-DISPOSITION`: inspection; status `not_run`.

## B0-REQ-0029 — Invalid measurement handling

The B0 estimator and controller shall not consume an invalid or stale measurement as a valid update and shall expose the approved rejection or hold status.

**Acceptance:** Planned component and integration tests inject invalid and stale samples and confirm no valid update occurs, state ownership is preserved and the required status is observable.

**Verification:** B0-VER-INVALID-MEASUREMENT

- `B0-VER-INVALID-MEASUREMENT`: test; status `not_run`.

## B0-REQ-0030 — B0 exclusion boundary

The B0 system shall exclude position and velocity loops, waypoint flight, full INS or GNSS estimation, advanced-control comparisons, learning algorithms, embedded targets, HIL and flight claims unless a separately approved extension activates them.

**Acceptance:** Inspection of requirements, model, verification specifications and reports finds no activated excluded capability or unsupported flight, HIL, hardware or research claim.

**Verification:** B0-VER-SCOPE-INSPECTION

- `B0-VER-SCOPE-INSPECTION`: inspection; status `not_run`.
