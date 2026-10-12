# B0 system views

These five views are the first lightweight systems-engineering model set. Each
view states its identifier, purpose, scope, baseline, sources, and maturity
legend before the editable Mermaid source. Labels marked **accepted** describe
the G0/G1 evidence that exists; **approved/planned** and **not active** are not
implementation claims.

## SE-MODEL-CONTEXT-001 — system context and use

**Purpose:** bound the B0 attitude experiment and show its users and external
dependencies. **Scope/baseline:** B0 v0.2, G0 v2, G1 merged at
`de0006392a4ac6017c4be0b6befa35f1d6cefe0e`. **Sources:**
[project charter](../project_charter.md), [development baseline](../development_baseline.md),
and the G0 operating envelope. **Maturity:** the platform boundary and G0/G1
component scope are accepted; the closed-loop estimator/controller use is
approved/planned until G2/G3.

```mermaid
flowchart LR
    User[Engineer or reviewer]
    Evidence[Independent evaluator and retained evidence]
    B0((B0 attitude experiment boundary))
    Plant[Rotational plant\naccepted G1 component]
    Sensors[IMU model\naccepted G1 component]
    Estimator[Attitude estimator\napproved/planned G2]
    Controller[Cascaded controller\napproved/planned G2]
    Hardware[Board, HIL, flight\nnot active in B0]
    Research[Research packages\nnot active unless separately gated]
    User -->|configure, run, review| B0
    B0 -->|commands and scenario inputs| Plant
    Plant --> Sensors
    Sensors -->|measurements| B0
    B0 -->|planned estimated-state loop| Estimator
    Estimator --> Controller
    Controller --> Plant
    B0 --> Evidence
    Evidence --> User
    Hardware -. excluded boundary .-> B0
    Research -. separate gate .-> B0
```

The planned loop is shown as a boundary relationship, not as a claim that G2 or
G3 is implemented. Hardware, HIL, flight, navigation, learning and papers are
outside this model's active scope.

## SE-MODEL-ARCH-001 — functional and logical allocation

**Purpose:** allocate B0 functions without moving module ownership. **Scope:**
plant, sensor, estimator, control, actuator, integration and independent
verification. **Baseline/sources:** G0 interface contract, G1 component tests,
and [architecture](architecture.md). **Maturity:** Plant, actuator and IMU are
accepted at G1; estimator/control/integration are approved/planned; verification
is an independent responsibility, not a component of the controller.

```mermaid
flowchart LR
    Scenario[Scenario clock and command\n05_integration approved/planned]
    Plant[Plant\n01_simulation/b0\naccepted G1]
    IMU[IMU\n01_simulation/b0\naccepted G1]
    Estimator[Estimator\n02_estimation/b0\napproved/planned G2]
    Control[Rate and attitude control\n03_control/b0\napproved/planned G2]
    Actuator[Actuator\n01_simulation/b0\naccepted G1]
    Integration[Scenario integration\n05_integration/b0\napproved/planned G3]
    Verify[Independent verification\nsystems_engineering/verification\naccepted process; future coverage planned]
    Scenario --> Plant
    Plant --> IMU
    IMU --> Estimator
    Estimator --> Control
    Control --> Actuator
    Actuator --> Plant
    Scenario --> Integration
    Integration -. drives and records .-> Plant
    Integration -. reports signals .-> Verify
    Plant -. oracle truth only .-> Verify
```

The dotted truth path terminates at independent verification. It is not an
input path to the estimator or controller.

## SE-MODEL-INTERFACE-001 — interface and data flow

**Purpose:** make the message direction, ownership and truth boundary explicit.
**Scope/baseline:** G0 v2 interface/timing/initialization contracts; no new
thresholds. **Sources:** `05_integration/b0/configs/b0_g0_contract.v2.json`
(`interface_contract`, `timing`, `initialization_contract`) and
[G0 model contract](g0_contract.md). **Maturity:** G0 message semantics are
approved; consuming implementations are accepted only for the G1 components.

```mermaid
flowchart LR
    Command[command\nq_nb_command, timestamp_s]
    IMU[imu_sample\nomega_b rad/s; specific_force_b m/s2\nNED/FRD, scenario clock]
    Est[estimator state\nq_nb_estimate; state timestamp]
    Controller[controller\ncommand + estimate + paired feedback]
    Torque[torque command\nrequested + limited torque; saturated; timestamp]
    Actuator[actuator\nadvances paired limited target]
    Feedback[actuator feedback\nlimited/actual torque; saturated; paired timestamp]
    Truth[plant truth\nq_nb_truth, omega_b_truth\nevaluation only]
    Eval[oracle/evaluator\nindependent ownership]
    Command --> Controller
    IMU --> Est
    Est --> Controller
    Feedback --> Controller
    Controller -->|request, componentwise limit, saturation flag| Torque
    Torque --> Actuator
    Actuator --> Feedback
    Feedback --> Eval
    Truth --> Eval
    Est --> Eval
    Controller --> Eval
    Eval -. no truth input .-> Est
    Eval -. no truth input .-> Controller
```

All vectors retain SI units, NED/body frame conventions and scalar-first
Hamilton quaternion order. The controller consumes the attitude command,
current estimate and tagged actuator feedback, then produces the requested
torque, its componentwise limited target and the saturation flag in one
controller tick. The controller is the sole limiting authority; the actuator
advances the paired limited target and reports actual/limited torque and the
paired saturation status back to the controller and evaluator. Scenario-clock
timestamps pair samples and feedback. Truth is owned by the plant/evaluator
boundary and is never silently copied into an estimator or controller input.

## SE-MODEL-BEHAVIOR-001 — lifecycle and rejection behavior

**Purpose:** describe the already-contracted startup/reset/rejection ordering
without inventing a scheduler. **Scope/baseline:** G0 timing, reset and invalid
input rules; G1 component reset behavior. **Sources:** G0 v2
`timing`, `initialization_contract`, `acceptance_policy`, and G1 tests.
**Maturity:** startup/reset and input rejection are approved/partially accepted;
the full estimated-state loop is planned for G2/G3.

```mermaid
stateDiagram-v2
    [*] --> Startup
    Startup --> Ready: epoch-local tick zero\nreset command held
    Ready --> Update: due sample and valid timestamp
    Update --> Ready: component step completes
    Ready --> Reject: invalid dt, stale or malformed input
    Reject --> Ready: rejection recorded, state unchanged
    Ready --> Reset: explicit runtime reset
    Reset --> Startup: clear state and restart local phase
    Update --> PlannedLoop: G2/G3 estimate/control integration
    PlannedLoop --> Ready: future scheduler contract
```

The `PlannedLoop` state is deliberately future work: G1 does not claim an
estimated-state closed loop. Reset starts a new local epoch; no previous truth,
timestamp or hidden state is reused as an input.

## SE-MODEL-DEPLOY-001 — deployment and extension boundary

**Purpose:** show what can be run today and what remains an extension boundary.
**Scope/baseline:** G1 accepted Python components, development-readiness toolchain,
and the B0 roadmap. **Sources:** G1 evidence/CI and [roadmap](../../docs/roadmap.md).
**Maturity:** Python component execution is accepted; C++ core, board/HIL and
external verification adapters are approved/planned or not active.

```mermaid
flowchart TB
    Dev[Developer workstation\nPython 3.11, C++17 toolchain]
    Py[Python B0 components\nplant, actuator, IMU\naccepted G1]
    Cpp[Planned C++ control core\napproved/planned G2]
    CI[CI and retained artifact\nb0-g1-component-evidence\naccepted G1 evidence]
    ExtNav[EXT-NAV legacy EKF\nseparate scope]
    ExtVerify[EXT-VERIFY adapter\nnot active]
    Board[EXT-EMBED board and HIL\nnot active]
    Dev --> Py
    Dev --> Cpp
    Py --> CI
    Cpp -. future same-contract core .-> CI
    ExtNav -. legacy conventions only .-> Py
    ExtVerify -. future adapter boundary .-> CI
    Board -.->|future execution level| Cpp
```

No deployment arrow means that a board, HIL loop, flight stack or external
verification suite is currently operational. Those are extension interfaces and
require their own scope, evidence and approval.
