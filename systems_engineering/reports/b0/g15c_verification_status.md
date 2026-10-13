# B0 G1.5-C verification traceability status

> Controlled current view; frozen verification specifications remain planned/not_run and are not rewritten.

## First-screen conclusion

- Design traceability: **30/30 requirements** have source, model and verification relations; the controlled catalog contains **26 model identities** and **29/29 planned specifications**.
- Execution: **5/29 specifications** have at least one current production execution record.
- Accepted evidence: **0/1 production records**.
- Requirement satisfaction: **0/30**. A requirement counts only when every required specification has complete, applicable, available and accepted pass evidence.
- Current gap: The retained G1 component artifact is identified and hash-bound but is offline-unverified, partial and pending independent review; it proves no requirement satisfied.

## Version boundary

- Frozen requirements/model base: `ddd281fd0a94ee59635accb5f41500fac05284b7`.
- Controlled current applicability target: `62aad74babd41d31c472038db2cdd10999ea426e`.
- Evaluated repository revision: committed `HEAD`, resolved by the checker at runtime; uncommitted worktree bytes are excluded.

## Execution records

| Record | Level | Result | Evidence | Applicability | Review | Coverage |
|---|---|---|---|---|---|---|
| `B0-EXEC-G1-COMPONENT-20261013` | module | pass | remote_unverified | applicable_by_analysis | pending | partial |

## Requirement index

Static groups: [stakeholder](#group-stakeholder), [system](#group-system), [component](#group-component), [with execution](#group-with-execution), [without execution](#group-without-execution).

### Group: stakeholder
<a id="group-stakeholder"></a>

[`B0-REQ-0001`](#b0-req-0001), [`B0-REQ-0030`](#b0-req-0030)

### Group: system
<a id="group-system"></a>

[`B0-REQ-0002`](#b0-req-0002), [`B0-REQ-0003`](#b0-req-0003), [`B0-REQ-0004`](#b0-req-0004), [`B0-REQ-0014`](#b0-req-0014), [`B0-REQ-0019`](#b0-req-0019), [`B0-REQ-0020`](#b0-req-0020), [`B0-REQ-0021`](#b0-req-0021), [`B0-REQ-0022`](#b0-req-0022), [`B0-REQ-0023`](#b0-req-0023), [`B0-REQ-0024`](#b0-req-0024), [`B0-REQ-0025`](#b0-req-0025), [`B0-REQ-0026`](#b0-req-0026), [`B0-REQ-0027`](#b0-req-0027), [`B0-REQ-0028`](#b0-req-0028)

### Group: component
<a id="group-component"></a>

[`B0-REQ-0005`](#b0-req-0005), [`B0-REQ-0006`](#b0-req-0006), [`B0-REQ-0007`](#b0-req-0007), [`B0-REQ-0008`](#b0-req-0008), [`B0-REQ-0009`](#b0-req-0009), [`B0-REQ-0010`](#b0-req-0010), [`B0-REQ-0011`](#b0-req-0011), [`B0-REQ-0012`](#b0-req-0012), [`B0-REQ-0013`](#b0-req-0013), [`B0-REQ-0015`](#b0-req-0015), [`B0-REQ-0016`](#b0-req-0016), [`B0-REQ-0017`](#b0-req-0017), [`B0-REQ-0018`](#b0-req-0018), [`B0-REQ-0029`](#b0-req-0029)

### Group: with execution
<a id="group-with-execution"></a>

[`B0-REQ-0005`](#b0-req-0005), [`B0-REQ-0006`](#b0-req-0006), [`B0-REQ-0008`](#b0-req-0008), [`B0-REQ-0010`](#b0-req-0010), [`B0-REQ-0011`](#b0-req-0011)

### Group: without execution
<a id="group-without-execution"></a>

[`B0-REQ-0001`](#b0-req-0001), [`B0-REQ-0002`](#b0-req-0002), [`B0-REQ-0003`](#b0-req-0003), [`B0-REQ-0004`](#b0-req-0004), [`B0-REQ-0007`](#b0-req-0007), [`B0-REQ-0009`](#b0-req-0009), [`B0-REQ-0012`](#b0-req-0012), [`B0-REQ-0013`](#b0-req-0013), [`B0-REQ-0014`](#b0-req-0014), [`B0-REQ-0015`](#b0-req-0015), [`B0-REQ-0016`](#b0-req-0016), [`B0-REQ-0017`](#b0-req-0017), [`B0-REQ-0018`](#b0-req-0018), [`B0-REQ-0019`](#b0-req-0019), [`B0-REQ-0020`](#b0-req-0020), [`B0-REQ-0021`](#b0-req-0021), [`B0-REQ-0022`](#b0-req-0022), [`B0-REQ-0023`](#b0-req-0023), [`B0-REQ-0024`](#b0-req-0024), [`B0-REQ-0025`](#b0-req-0025), [`B0-REQ-0026`](#b0-req-0026), [`B0-REQ-0027`](#b0-req-0027), [`B0-REQ-0028`](#b0-req-0028), [`B0-REQ-0029`](#b0-req-0029), [`B0-REQ-0030`](#b0-req-0030)

## Requirement chains

### B0-REQ-0001

- Title: Bounded attitude experiment
- Source: `B0-SRC-CHARTER` → `systems_engineering/project_charter.md` (#purpose and #product-boundaries); `B0-SRC-BASELINE` → `systems_engineering/development_baseline.md` (#single-objective, #included, #excluded-from-b0 and #delivery-gates)
- Requirement: The B0 system shall execute a configured bounded multirotor attitude-estimation and control experiment without representing the experiment as full-flight capability.
- Rationale: Defines the single B0 product use while preventing scaffold and extension scope from becoming an implicit obligation.
- Model/responsibility: `B0-MODEL-SYSTEM`, `B0-MODEL-COMMAND-SOURCE`; responsible `B0-MODEL-SYSTEM`.
- Verification: `B0-VER-SCOPE-INSPECTION` (inspection; systems engineering reviewer; planned `not_run`)
- Execution/evidence/review: Not executed; evidence and review are pending.
- Gap: No accepted complete evidence.

### B0-REQ-0002

- Title: Deterministic configuration and replay
- Source: `B0-SRC-BASELINE` → `systems_engineering/development_baseline.md` (#single-objective, #included, #excluded-from-b0 and #delivery-gates); `B0-SRC-G0-V2` → `05_integration/b0/configs/b0_g0_contract.v2.json` (JSON Pointer recorded by each acceptance condition)
- Requirement: The B0 system shall produce repeatable samples and state evolution for identical approved configuration, seed, initial state, input sequence, reset sequence and software revision.
- Rationale: Repeatability is required for engineering comparison and release evidence.
- Model/responsibility: `B0-MODEL-EXECUTION`, `B0-MODEL-SCENARIO`; responsible `B0-MODEL-EXECUTION`.
- Verification: `B0-VER-REPLAY` (test; integration verification; planned `not_run`)
- Execution/evidence/review: Not executed; evidence and review are pending.
- Gap: No accepted complete evidence.

### B0-REQ-0003

- Title: Runtime truth isolation
- Source: `B0-SRC-BASELINE` → `systems_engineering/development_baseline.md` (#single-objective, #included, #excluded-from-b0 and #delivery-gates); `B0-SRC-G0-V2` → `05_integration/b0/configs/b0_g0_contract.v2.json` (JSON Pointer recorded by each acceptance condition); `B0-SRC-ARCHITECTURE` → `systems_engineering/models/architecture.md` (#modular-boundaries, #coordinate-and-unit-conventions and #imu-measurement-convention)
- Requirement: The B0 system shall prevent live plant truth from entering estimator or controller runtime inputs after explicit initialization while permitting truth to reach sensor generation and independent evaluation.
- Rationale: Prevents circular validation and unrealistically privileged control or estimation.
- Model/responsibility: `B0-MODEL-TRUTH`, `B0-MODEL-ESTIMATOR`, `B0-MODEL-CONTROLLER`, `B0-MODEL-EVALUATOR`; responsible `B0-MODEL-EXECUTION`.
- Verification: `B0-VER-TRUTH-BOUNDARY` (inspection; integration verification; planned `not_run`)
- Execution/evidence/review: Not executed; evidence and review are pending.
- Gap: No accepted complete evidence.

### B0-REQ-0004

- Title: Shared frames units and quaternion convention
- Source: `B0-SRC-ARCHITECTURE` → `systems_engineering/models/architecture.md` (#modular-boundaries, #coordinate-and-unit-conventions and #imu-measurement-convention); `B0-SRC-G0-V2` → `05_integration/b0/configs/b0_g0_contract.v2.json` (JSON Pointer recorded by each acceptance condition)
- Requirement: The B0 system shall represent exchanged quantities using the approved NED and body frames, SI units, and scalar-first Hamilton quaternion convention.
- Rationale: A single convention prevents silent sign, frame and ordering defects across components.
- Model/responsibility: `B0-MODEL-SYSTEM`; responsible `B0-MODEL-SYSTEM`.
- Verification: `B0-VER-CONVENTIONS` (inspection; systems engineering reviewer; planned `not_run`)
- Execution/evidence/review: Not executed; evidence and review are pending.
- Gap: No accepted complete evidence.

### B0-REQ-0005

- Title: Rigid-body rotational dynamics
- Source: `B0-SRC-BASELINE` → `systems_engineering/development_baseline.md` (#single-objective, #included, #excluded-from-b0 and #delivery-gates); `B0-SRC-G0-V2` → `05_integration/b0/configs/b0_g0_contract.v2.json` (JSON Pointer recorded by each acceptance condition); `B0-SRC-G1` → `01_simulation/b0/README.md` (component scope, commands and evidence limits)
- Requirement: The B0 plant shall propagate body angular velocity using the approved rigid-body rotational equation and positive-definite inertia contract.
- Rationale: Defines the physical responsibility required by the bounded attitude experiment.
- Model/responsibility: `B0-MODEL-PLANT`; responsible `B0-MODEL-PLANT`.
- Verification: `B0-VER-PLANT-DYNAMICS` (test; plant verification; planned `not_run`)
- Execution/evidence/review: `B0-EXEC-G1-COMPONENT-20261013`: pass, remote_unverified, review pending, coverage partial
- Gap: No accepted complete evidence.

### B0-REQ-0006

- Title: Quaternion plant state
- Source: `B0-SRC-G0-V2` → `05_integration/b0/configs/b0_g0_contract.v2.json` (JSON Pointer recorded by each acceptance condition); `B0-SRC-ARCHITECTURE` → `systems_engineering/models/architecture.md` (#modular-boundaries, #coordinate-and-unit-conventions and #imu-measurement-convention); `B0-SRC-G1` → `01_simulation/b0/README.md` (component scope, commands and evidence limits)
- Requirement: The B0 plant shall propagate and normalize its scalar-first attitude quaternion using the approved body-rate and frame convention.
- Rationale: Attitude propagation must remain consistent with the shared representation.
- Model/responsibility: `B0-MODEL-PLANT`, `B0-MODEL-TRUTH`; responsible `B0-MODEL-PLANT`.
- Verification: `B0-VER-PLANT-QUATERNION` (test; plant verification; planned `not_run`)
- Execution/evidence/review: `B0-EXEC-G1-COMPONENT-20261013`: pass, remote_unverified, review pending, coverage partial
- Gap: No accepted complete evidence.

### B0-REQ-0007

- Title: Paired torque command
- Source: `B0-SRC-G0-V2` → `05_integration/b0/configs/b0_g0_contract.v2.json` (JSON Pointer recorded by each acceptance condition)
- Requirement: The B0 controller shall publish one timestamped torque command that pairs requested torque, limited target and saturation status from the same controller due tick.
- Rationale: The pairing closes ambiguity between request, clamp result and anti-windup feedback.
- Model/responsibility: `B0-MODEL-CONTROLLER`, `B0-MODEL-TORQUE-COMMAND`; responsible `B0-MODEL-CONTROLLER`.
- Verification: `B0-VER-PAIRED-COMMAND` (test; controller verification; planned `not_run`)
- Execution/evidence/review: Not executed; evidence and review are pending.
- Gap: No accepted complete evidence.

### B0-REQ-0008

- Title: Limited-target actuator dynamics
- Source: `B0-SRC-G0-V2` → `05_integration/b0/configs/b0_g0_contract.v2.json` (JSON Pointer recorded by each acceptance condition); `B0-SRC-G1` → `01_simulation/b0/README.md` (component scope, commands and evidence limits)
- Requirement: The B0 actuator shall advance its response using only the held limited target from the latest eligible paired torque command.
- Rationale: Prevents a raw request from bypassing the controller's unique saturation responsibility.
- Model/responsibility: `B0-MODEL-ACTUATOR`, `B0-MODEL-TORQUE-COMMAND`; responsible `B0-MODEL-ACTUATOR`.
- Verification: `B0-VER-ACTUATOR-DYNAMICS` (test; actuator verification; planned `not_run`)
- Execution/evidence/review: `B0-EXEC-G1-COMPONENT-20261013`: pass, remote_unverified, review pending, coverage partial
- Gap: No accepted complete evidence.

### B0-REQ-0009

- Title: Actuator feedback pairing
- Source: `B0-SRC-G0-V2` → `05_integration/b0/configs/b0_g0_contract.v2.json` (JSON Pointer recorded by each acceptance condition)
- Requirement: The B0 actuator shall publish actual torque and the originating paired-command timestamp in actuator feedback.
- Rationale: Controller anti-windup must associate actual response with the correct limited target.
- Model/responsibility: `B0-MODEL-ACTUATOR`, `B0-MODEL-ACTUATOR-FEEDBACK`; responsible `B0-MODEL-ACTUATOR`.
- Verification: `B0-VER-PAIRED-FEEDBACK` (test; integration verification; planned `not_run`)
- Execution/evidence/review: Not executed; evidence and review are pending.
- Gap: No accepted complete evidence.

### B0-REQ-0010

- Title: Gyroscope measurement
- Source: `B0-SRC-G0-V2` → `05_integration/b0/configs/b0_g0_contract.v2.json` (JSON Pointer recorded by each acceptance condition); `B0-SRC-ARCHITECTURE` → `systems_engineering/models/architecture.md` (#modular-boundaries, #coordinate-and-unit-conventions and #imu-measurement-convention); `B0-SRC-G1` → `01_simulation/b0/README.md` (component scope, commands and evidence limits)
- Requirement: The B0 IMU shall produce timestamped body-frame angular-rate measurements with the approved bias, noise, validity and seed semantics.
- Rationale: Defines the estimator's angular-rate observation boundary.
- Model/responsibility: `B0-MODEL-IMU`, `B0-MODEL-IMU-SAMPLE`; responsible `B0-MODEL-IMU`.
- Verification: `B0-VER-IMU-GYRO` (test; IMU verification; planned `not_run`)
- Execution/evidence/review: `B0-EXEC-G1-COMPONENT-20261013`: pass, remote_unverified, review pending, coverage partial
- Gap: No accepted complete evidence.

### B0-REQ-0011

- Title: Accelerometer specific force
- Source: `B0-SRC-G0-V2` → `05_integration/b0/configs/b0_g0_contract.v2.json` (JSON Pointer recorded by each acceptance condition); `B0-SRC-ARCHITECTURE` → `systems_engineering/models/architecture.md` (#modular-boundaries, #coordinate-and-unit-conventions and #imu-measurement-convention); `B0-SRC-G1` → `01_simulation/b0/README.md` (component scope, commands and evidence limits)
- Requirement: The B0 IMU shall produce timestamped body-frame specific-force measurements using the approved gravity sign, bias, noise, validity and seed semantics.
- Rationale: Specific force rather than inertial acceleration is the estimator input.
- Model/responsibility: `B0-MODEL-IMU`, `B0-MODEL-IMU-SAMPLE`; responsible `B0-MODEL-IMU`.
- Verification: `B0-VER-IMU-SPECIFIC-FORCE` (test; IMU verification; planned `not_run`)
- Execution/evidence/review: `B0-EXEC-G1-COMPONENT-20261013`: pass, remote_unverified, review pending, coverage partial
- Gap: No accepted complete evidence.

### B0-REQ-0012

- Title: Estimator propagation
- Source: `B0-SRC-BASELINE` → `systems_engineering/development_baseline.md` (#single-objective, #included, #excluded-from-b0 and #delivery-gates); `B0-SRC-G0-V2` → `05_integration/b0/configs/b0_g0_contract.v2.json` (JSON Pointer recorded by each acceptance condition)
- Requirement: The B0 estimator shall propagate and normalize a scalar-first attitude estimate from valid gyroscope samples and approved positive time increments.
- Rationale: Defines the minimum planned G2 attitude propagation responsibility.
- Model/responsibility: `B0-MODEL-ESTIMATOR`, `B0-MODEL-STATE-ESTIMATE`; responsible `B0-MODEL-ESTIMATOR`.
- Verification: `B0-VER-ESTIMATOR-PROPAGATION` (test; estimator verification; planned `not_run`)
- Execution/evidence/review: Not executed; evidence and review are pending.
- Gap: No accepted complete evidence.

### B0-REQ-0013

- Title: Roll and pitch fusion
- Source: `B0-SRC-BASELINE` → `systems_engineering/development_baseline.md` (#single-objective, #included, #excluded-from-b0 and #delivery-gates); `B0-SRC-G0-V2` → `05_integration/b0/configs/b0_g0_contract.v2.json` (JSON Pointer recorded by each acceptance condition)
- Requirement: The B0 estimator shall apply bounded accelerometer-based roll and pitch correction only when the approved validity and bounded-specific-force conditions permit it.
- Rationale: Gravity-based tilt correction is conditional and must not silently treat all acceleration as gravity.
- Model/responsibility: `B0-MODEL-ESTIMATOR`, `B0-MODEL-IMU-SAMPLE`; responsible `B0-MODEL-ESTIMATOR`.
- Verification: `B0-VER-ESTIMATOR-FUSION` (test; estimator verification; planned `not_run`)
- Execution/evidence/review: Not executed; evidence and review are pending.
- Gap: No accepted complete evidence.

### B0-REQ-0014

- Title: Yaw observability limitation
- Source: `B0-SRC-BASELINE` → `systems_engineering/development_baseline.md` (#single-objective, #included, #excluded-from-b0 and #delivery-gates); `B0-SRC-G0-V2` → `05_integration/b0/configs/b0_g0_contract.v2.json` (JSON Pointer recorded by each acceptance condition)
- Requirement: The B0 system shall report yaw as relative propagation and drift without claiming absolute yaw observability from gyroscope and accelerometer measurements alone.
- Rationale: Gravity provides no absolute heading reference.
- Model/responsibility: `B0-MODEL-ESTIMATOR`, `B0-MODEL-EVALUATOR`; responsible `B0-MODEL-ESTIMATOR`, `B0-MODEL-EVALUATOR`.
- Verification: `B0-VER-YAW-LIMITATION` (analysis; estimator verification; planned `not_run`)
- Execution/evidence/review: Not executed; evidence and review are pending.
- Gap: No accepted complete evidence.

### B0-REQ-0015

- Title: Acceleration contamination handling
- Source: `B0-SRC-BASELINE` → `systems_engineering/development_baseline.md` (#single-objective, #included, #excluded-from-b0 and #delivery-gates); `B0-SRC-G0-V2` → `05_integration/b0/configs/b0_g0_contract.v2.json` (JSON Pointer recorded by each acceptance condition); `B0-SRC-G0-ACCEPTANCE` → `systems_engineering/verification/g0_acceptance.md` (#指标口径 and #八类场景)
- Requirement: The B0 estimator shall expose the approved limitation or correction-gating status when non-gravitational specific force violates its bounded tilt-correction assumptions.
- Rationale: The bounded attitude model lacks complete translational dynamics and must characterize rather than hide this limitation.
- Model/responsibility: `B0-MODEL-ESTIMATOR`, `B0-MODEL-STATE-ESTIMATE`; responsible `B0-MODEL-ESTIMATOR`.
- Verification: `B0-VER-ACCEL-CONTAMINATION` (test; integration verification; planned `not_run`)
- Execution/evidence/review: Not executed; evidence and review are pending.
- Gap: No accepted complete evidence.

### B0-REQ-0016

- Title: Cascaded attitude and rate control
- Source: `B0-SRC-BASELINE` → `systems_engineering/development_baseline.md` (#single-objective, #included, #excluded-from-b0 and #delivery-gates); `B0-SRC-G0-V2` → `05_integration/b0/configs/b0_g0_contract.v2.json` (JSON Pointer recorded by each acceptance condition)
- Requirement: The B0 controller shall compute body-torque request through the approved attitude-error and body-rate feedback signs in a cascaded attitude and rate structure.
- Rationale: Defines the planned G2 controller responsibility without importing legacy geometric or LQR scaffolds.
- Model/responsibility: `B0-MODEL-CONTROLLER`, `B0-MODEL-COMMAND`, `B0-MODEL-STATE-ESTIMATE`; responsible `B0-MODEL-CONTROLLER`.
- Verification: `B0-VER-CONTROLLER-SIGN` (test; controller verification; planned `not_run`)
- Execution/evidence/review: Not executed; evidence and review are pending.
- Gap: No accepted complete evidence.

### B0-REQ-0017

- Title: Unique controller saturation responsibility
- Source: `B0-SRC-G0-V2` → `05_integration/b0/configs/b0_g0_contract.v2.json` (JSON Pointer recorded by each acceptance condition)
- Requirement: The B0 controller shall be the sole component that limits requested body torque to the approved target bounds and sets the paired saturation status.
- Rationale: A single clamp authority prevents inconsistent targets and ambiguous feedback.
- Model/responsibility: `B0-MODEL-CONTROLLER`, `B0-MODEL-TORQUE-COMMAND`; responsible `B0-MODEL-CONTROLLER`.
- Verification: `B0-VER-CONTROLLER-SATURATION` (test; controller verification; planned `not_run`)
- Execution/evidence/review: Not executed; evidence and review are pending.
- Gap: No accepted complete evidence.

### B0-REQ-0018

- Title: Anti-windup update
- Source: `B0-SRC-G0-V2` → `05_integration/b0/configs/b0_g0_contract.v2.json` (JSON Pointer recorded by each acceptance condition)
- Requirement: The B0 controller shall update each rate-integral contribution using the approved conditional-integration and paired-feedback back-calculation rule and shall enforce the approved per-axis integral bounds.
- Rationale: The complete discrete rule must respond to both clamp saturation and actuator lag without silently accumulating beyond bounds.
- Model/responsibility: `B0-MODEL-CONTROLLER`, `B0-MODEL-ACTUATOR-FEEDBACK`; responsible `B0-MODEL-CONTROLLER`.
- Verification: `B0-VER-ANTI-WINDUP` (test; controller verification; planned `not_run`)
- Execution/evidence/review: Not executed; evidence and review are pending.
- Gap: No accepted complete evidence.

### B0-REQ-0019

- Title: Invalid input rejection
- Source: `B0-SRC-G0-V2` → `05_integration/b0/configs/b0_g0_contract.v2.json` (JSON Pointer recorded by each acceptance condition); `B0-SRC-G0-ACCEPTANCE` → `systems_engineering/verification/g0_acceptance.md` (#指标口径 and #八类场景)
- Requirement: The B0 system shall reject invalid, non-finite, stale, mis-shaped or non-positive-time inputs according to the owning component contract without silently advancing state.
- Rationale: Explicit rejection preserves state ownership and makes invalid trials auditable.
- Model/responsibility: `B0-MODEL-EXECUTION`, `B0-MODEL-IMU-SAMPLE`, `B0-MODEL-COMMAND`; responsible `B0-MODEL-EXECUTION`.
- Verification: `B0-VER-INVALID-INPUT` (test; component owners; planned `not_run`)
- Execution/evidence/review: Not executed; evidence and review are pending.
- Gap: No accepted complete evidence.

### B0-REQ-0020

- Title: Reset contract
- Source: `B0-SRC-G0-V2` → `05_integration/b0/configs/b0_g0_contract.v2.json` (JSON Pointer recorded by each acceptance condition); `B0-SRC-G0-ACCEPTANCE` → `systems_engineering/verification/g0_acceptance.md` (#指标口径 and #八类场景)
- Requirement: The B0 system shall reset all stateful components to explicit initial state, seed and epoch-local scheduling while preserving the monotonically increasing scenario clock and discarding pre-reset held commands and feedback.
- Rationale: A single reset boundary is necessary for deterministic replay without stale state leakage.
- Model/responsibility: `B0-MODEL-EXECUTION`, `B0-MODEL-RESET`; responsible `B0-MODEL-EXECUTION`.
- Verification: `B0-VER-RESET` (test; integration verification; planned `not_run`)
- Execution/evidence/review: Not executed; evidence and review are pending.
- Gap: No accepted complete evidence.

### B0-REQ-0021

- Title: Deterministic scheduling and timestamps
- Source: `B0-SRC-G0-V2` → `05_integration/b0/configs/b0_g0_contract.v2.json` (JSON Pointer recorded by each acceptance condition)
- Requirement: The B0 execution adapter shall schedule component updates and construct timestamps from integer base ticks using the approved due-phase, consumption and held-command rules.
- Rationale: The execution adapter owns ordering and prevents timing drift or ambiguous sample consumption.
- Model/responsibility: `B0-MODEL-EXECUTION`; responsible `B0-MODEL-EXECUTION`.
- Verification: `B0-VER-SCHEDULING` (test; integration verification; planned `not_run`)
- Execution/evidence/review: Not executed; evidence and review are pending.
- Gap: No accepted complete evidence.

### B0-REQ-0022

- Title: Approved scenario suite
- Source: `B0-SRC-G0-V2` → `05_integration/b0/configs/b0_g0_contract.v2.json` (JSON Pointer recorded by each acceptance condition); `B0-SRC-G0-ACCEPTANCE` → `systems_engineering/verification/g0_acceptance.md` (#指标口径 and #八类场景)
- Requirement: The B0 system shall support the approved normal, initial-offset, signed-step, disturbance, noise-and-bias, saturation-withdrawal, acceleration-contamination, and invalid-input-and-reset scenarios.
- Rationale: These scenarios bound the required engineering questions without extending to flight.
- Model/responsibility: `B0-MODEL-SCENARIO`, `B0-MODEL-SYSTEM`; responsible `B0-MODEL-SCENARIO`.
- Verification: `B0-VER-SCENARIO-CATALOGUE` (inspection; systems engineering reviewer; planned `not_run`)
- Execution/evidence/review: Not executed; evidence and review are pending.
- Gap: No accepted complete evidence.

### B0-REQ-0023

- Title: Independent evaluation
- Source: `B0-SRC-G0-V2` → `05_integration/b0/configs/b0_g0_contract.v2.json` (JSON Pointer recorded by each acceptance condition); `B0-SRC-G0-ACCEPTANCE` → `systems_engineering/verification/g0_acceptance.md` (#指标口径 and #八类场景); `B0-SRC-VERIFICATION` → `systems_engineering/verification/verification_plan.md` (#b0-checks and #evidence-chain)
- Requirement: The B0 evaluator shall compute acceptance metrics independently of estimator and controller implementations using the approved raw signals, windows, units, aggregation and invalid-data rules.
- Rationale: Independent oracles prevent the tested algorithm from grading itself.
- Model/responsibility: `B0-MODEL-EVALUATOR`, `B0-MODEL-TRUTH`; responsible `B0-MODEL-EVALUATOR`.
- Verification: `B0-VER-EVALUATOR-INDEPENDENCE` (inspection; independent verification reviewer; planned `not_run`)
- Execution/evidence/review: Not executed; evidence and review are pending.
- Gap: No accepted complete evidence.

### B0-REQ-0024

- Title: Evidence provenance
- Source: `B0-SRC-BASELINE` → `systems_engineering/development_baseline.md` (#single-objective, #included, #excluded-from-b0 and #delivery-gates); `B0-SRC-VERIFICATION` → `systems_engineering/verification/verification_plan.md` (#b0-checks and #evidence-chain); `B0-SRC-G0-V2` → `05_integration/b0/configs/b0_g0_contract.v2.json` (JSON Pointer recorded by each acceptance condition)
- Requirement: The B0 release evidence shall identify software revision, approved configuration hash, scenario, seed, environment, command, raw artifact, metric implementation and terminal result classification.
- Rationale: A pass/fail statement without provenance is not reproducible evidence.
- Model/responsibility: `B0-MODEL-EVALUATOR`, `B0-MODEL-EVIDENCE`; responsible `B0-MODEL-EVALUATOR`.
- Verification: `B0-VER-EVIDENCE-PROVENANCE` (inspection; release verification; planned `not_run`)
- Execution/evidence/review: Not executed; evidence and review are pending.
- Gap: No accepted complete evidence.

### B0-REQ-0025

- Title: Defect-detection demonstration
- Source: `B0-SRC-BASELINE` → `systems_engineering/development_baseline.md` (#single-objective, #included, #excluded-from-b0 and #delivery-gates); `B0-SRC-VERIFICATION` → `systems_engineering/verification/verification_plan.md` (#b0-checks and #evidence-chain)
- Requirement: The B0 release process shall demonstrate that selected independent checks detect isolated sign, unit, quaternion-ordering or anti-windup defects without modifying the approved production baseline.
- Rationale: A limited mutation demonstration provides evidence that critical checks are capable of failing.
- Model/responsibility: `B0-MODEL-EVALUATOR`; responsible `B0-MODEL-EVALUATOR`.
- Verification: `B0-VER-DEFECT-DETECTION` (demonstration; release verification; planned `not_run`)
- Execution/evidence/review: Not executed; evidence and review are pending.
- Gap: No accepted complete evidence.

### B0-REQ-0026

- Title: Implementation language boundary
- Source: `B0-SRC-BASELINE` → `systems_engineering/development_baseline.md` (#single-objective, #included, #excluded-from-b0 and #delivery-gates); `B0-SRC-ARCHITECTURE` → `systems_engineering/models/architecture.md` (#modular-boundaries, #coordinate-and-unit-conventions and #imu-measurement-convention)
- Requirement: The B0 implementation shall provide the control core in C++17 and may use Python for simulation, orchestration and independent analysis through the approved interface boundary.
- Rationale: Preserves the intended portable control core while retaining productive analysis tooling.
- Model/responsibility: `B0-MODEL-CONTROLLER`, `B0-MODEL-EXECUTION`; responsible `B0-MODEL-CONTROLLER`, `B0-MODEL-EXECUTION`.
- Verification: `B0-VER-LANGUAGE-BOUNDARY` (inspection; architecture reviewer; planned `not_run`)
- Execution/evidence/review: Not executed; evidence and review are pending.
- Gap: No accepted complete evidence.

### B0-REQ-0027

- Title: Clean-checkout reproduction
- Source: `B0-SRC-BASELINE` → `systems_engineering/development_baseline.md` (#single-objective, #included, #excluded-from-b0 and #delivery-gates); `B0-SRC-VERIFICATION` → `systems_engineering/verification/verification_plan.md` (#b0-checks and #evidence-chain)
- Requirement: The B0 release shall be reproducible from a clean checkout using documented dependency versions and commands without relying on untracked developer state.
- Rationale: A local green workspace is insufficient release evidence.
- Model/responsibility: `B0-MODEL-EXECUTION`, `B0-MODEL-EVIDENCE`; responsible `B0-MODEL-EXECUTION`.
- Verification: `B0-VER-CLEAN-CHECKOUT` (demonstration; release verification; planned `not_run`)
- Execution/evidence/review: Not executed; evidence and review are pending.
- Gap: No accepted complete evidence.

### B0-REQ-0028

- Title: Legacy control disposition
- Source: `B0-SRC-LEGACY` → `systems_engineering/requirements/legacy_requirements.md` (#control-requirements and #status); `B0-SRC-G0-APPROVAL` → `systems_engineering/reports/b0/g0_approval_decision.md` (#决定); `B0-SRC-G0-V2` → `05_integration/b0/configs/b0_g0_contract.v2.json` (JSON Pointer recorded by each acceptance condition)
- Requirement: The B0 system shall retain CTL-REQ-001 and CTL-REQ-002 unchanged as historical references and shall record their approved not-applicable disposition for current B0 without a satisfaction claim.
- Rationale: Preserves historical identifiers while preventing incompatible legacy thresholds from silently becoming B0 criteria.
- Model/responsibility: `B0-MODEL-SYSTEM`; responsible `B0-MODEL-SYSTEM`.
- Verification: `B0-VER-LEGACY-DISPOSITION` (inspection; systems engineering reviewer; planned `not_run`)
- Execution/evidence/review: Not executed; evidence and review are pending.
- Gap: No accepted complete evidence.

### B0-REQ-0029

- Title: Invalid measurement handling
- Source: `B0-SRC-G0-V2` → `05_integration/b0/configs/b0_g0_contract.v2.json` (JSON Pointer recorded by each acceptance condition)
- Requirement: The B0 estimator and controller shall not consume an invalid or stale measurement as a valid update and shall expose the approved rejection or hold status.
- Rationale: Validity must affect consumption rather than serving as passive metadata.
- Model/responsibility: `B0-MODEL-ESTIMATOR`, `B0-MODEL-CONTROLLER`, `B0-MODEL-IMU-SAMPLE`; responsible `B0-MODEL-ESTIMATOR`, `B0-MODEL-CONTROLLER`.
- Verification: `B0-VER-INVALID-MEASUREMENT` (test; component and integration verification; planned `not_run`)
- Execution/evidence/review: Not executed; evidence and review are pending.
- Gap: No accepted complete evidence.

### B0-REQ-0030

- Title: B0 exclusion boundary
- Source: `B0-SRC-CHARTER` → `systems_engineering/project_charter.md` (#purpose and #product-boundaries); `B0-SRC-BASELINE` → `systems_engineering/development_baseline.md` (#single-objective, #included, #excluded-from-b0 and #delivery-gates)
- Requirement: The B0 system shall exclude position and velocity loops, waypoint flight, full INS or GNSS estimation, advanced-control comparisons, learning algorithms, embedded targets, HIL and flight claims unless a separately approved extension activates them.
- Rationale: Makes the stopping rule reviewable and prevents legacy scaffolds from expanding B0.
- Model/responsibility: `B0-MODEL-SYSTEM`; responsible `B0-MODEL-SYSTEM`.
- Verification: `B0-VER-SCOPE-INSPECTION` (inspection; systems engineering reviewer; planned `not_run`)
- Execution/evidence/review: Not executed; evidence and review are pending.
- Gap: No accepted complete evidence.

## Reading and filtering

Use the ledger fields `execution.level`, `execution.result`, `evidence.availability`, `applicability.status`, `review.status`, and `coverage`. Module and integration records are distinct; fixture records are prohibited from the production ledger.

## Evidence chain

The current record links the frozen specification IDs to G1 implementation paths, an Actions run artifact, SHA-256 content identity, relevant-file applicability hashes, and an explicit pending review. Artifact expiry changes evidence availability and must not silently preserve an auditable-pass claim.

## External research-suite interface

A future external suite may contribute a record only by supplying the same version, criterion, command, raw-evidence hash/URI, applicability, and review fields. This repository does not run or write to an external suite in G1.5-C.
