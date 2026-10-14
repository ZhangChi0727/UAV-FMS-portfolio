# G2-B S0 cascaded-controller design candidate

Status: candidate pending original-PA `DESIGN_ACCEPT`. Scope: G2-B component only; no G3 closed-loop or performance claim.

## Authority and boundary

The implementation loads `05_integration/b0/configs/b0_g0_contract.v2.json`, normalizes only CRLF/CR to LF, verifies Git blob `1beff6e6a9a81d0ab92b2059a93207ffed9d291d` and canonical SHA-256 `5b95531a6f96cb67ce25f624d6921bd313696f3c0b9868ec1de13c24c34cd98c`, then invokes `05_integration/b0/validate_config.py`. The G2-only candidate is `03_control/b0/configs/b0_g2_controller.v1.json`; it records choices that G0 did not freeze. A later approval overlay will bind the accepted S0 commit and configuration digest. It will not alter G0.

The platform-independent C++17 core receives only command, `StateEstimate`, paired actuator feedback and parameters. It has no Python, file-system, plant-truth, scenario or evaluator dependency. Python loads/validates configuration and performs explicit G2-A/G1 message adaptation. The binding must copy input arrays before validation and must never recompute or replace the C++ torque limit.

## Public types and calls

Namespace: `b0::control`. Fixed-size `std::array<double, N>` value types: `AttitudeCommand`, `StateEstimate`, `ActuatorFeedback`, `TorqueCommand`, `ControllerInitialState`, `ResetEpoch`, `ControllerParameters`, and `ControllerDiagnostics`. Every runtime message carries a finite timestamp. `TorqueCommand` contains requested torque, `limited_torque_body_Nm`, three saturation flags and publication timestamp as one value.

```text
reset(ControllerInitialState, ResetEpoch) -> TorqueCommand
step(AttitudeCommand, StateEstimate, ActuatorFeedback, dt_s) -> TorqueCommand
```

`ControllerContractError` is the C++ error. Python exposes a `ValueError` subclass with the same stable reason code. `step` in both languages returns only the G0 `TorqueCommand`; `last_diagnostics()` and `snapshot()` are separate read-only copied inspection APIs. A successful step commits its diagnostics together with control state. A rejected call throws before commit, carries the reason code, and does not replace the last successful diagnostics. Diagnostics report facts, never a verification verdict. Validation of all inputs and derived finite values precedes commit, so rejection cannot change epoch, accepted tick, integral, derivative/filter history or expected held command. G0 has no separate timestamp-comparison tolerance; S0 proposes an implementation tolerance of `1e-12 s` for grid-derived float64 timestamps, while integer epoch/tick identities remain exact.

The frozen G2-A `StateEstimate` and G1 `ActuatorFeedback`/`TorqueCommand` wire fields are not extended. The adapter owns an active controller-session context established by `reset_epoch`; it wraps copied payload fields with that session epoch for the core and rejects use without an active context. This epoch is implementation metadata, not a new frozen message field. G3 must route messages within the active reset session. Independently of caller metadata, the core requires feedback timestamp/value/status to match its own single expected held command, and scenario timestamps never rewind across epochs.

## Attitude and rate computation

All quantities use NED/FRD, SI, double and scalar-first Hamilton body-to-NED quaternions. Unit norm is checked against the G0 tolerance; arbitrary inputs are not normalized into validity.

1. Compute `q_err = conjugate(q_est) Hamilton-product q_cmd`.
2. Canonicalize by negating when scalar is negative. At scalar zero, negate when the first nonzero vector component is negative.
3. Define `e_att = 2 * q_err.vector`, expressed in the estimated body frame. For small rotation vector `delta_theta`, `e_att = delta_theta + O(|delta_theta|^3)`. At pi its magnitude is 2 and the G0 tie-break makes its sign deterministic; continuity across the unavoidable antipodal cut is not claimed.
4. `omega_sp = componentwise_clamp(K_att * e_att, +/- omega_limit)`.
5. `e_rate = omega_sp - omega_est`.
6. On the first step after reset, set `d_raw=0` and initialize `omega_prev=omega_est`. Otherwise `d_raw=(omega_est-omega_prev)/dt`.
7. Backward-Euler low-pass: `alpha=dt/(tau_D+dt)` and `d_filtered=d_previous+alpha*(d_raw-d_previous)`.
8. `request=Kp*e_rate+I_current-Kd*d_filtered`; the setpoint is not differentiated.
9. `limited=clamp(request,+/-torque_limit)` and `saturated_i=(abs(request_i)>limit_i)`. Equality is not saturation.

This tick publishes the request computed with `I_current`. Only afterward is `I_next` calculated for the following tick; no algebraic loop exists.

## Anti-windup and pairing

For each axis, `conditional_Ki_e` equals `Ki*e_rate` unless the axis is saturated and `(request-limited)` has the same nonzero sign as `e_rate`; in that case it is zero. An error that reduces saturation remains enabled.

```text
I_next = clamp(I_current + dt * (
  conditional_Ki_e
  + kaw_limit * (current_limited-current_request)
  + kaw_lag * (feedback_actual-matched_held_limited)),
  -I_limit, +I_limit)
```

The controller retains one expected held command: the most recent command it successfully published strictly before the current due tick. On the first step this is the reset command; thereafter it is the preceding successful step command. Feedback identity `(controller-session epoch, command_timestamp_s)` must identify exactly that command, not merely any known earlier publication. Its limited vector and saturation flags must match (timestamp within the S0 `1e-12 s` tolerance; values bit-identical to the published doubles). The feedback sample timestamp must equal the current due tick within that tolerance; actual torque must be a finite three-vector within the G0 component limits. Unknown, future, prior-epoch, superseded, out-of-range-actual or value/status-mismatched feedback is rejected. Thus the lag term can never substitute either the current limited value or an older superseded target for the actually held command value.

## Reset, time and recovery

Reset accepts a finite timestamp and a nonnegative signed-64-bit epoch strictly greater than the instance's previous epoch. Time cannot move backward; a reset after steps must be strictly later than the last accepted step. It publishes the epoch-boundary zero command, clears I/D/previous-rate/expected-held-command state, and seeds the new expected held command with that reset command. The reset tick performs no step. The first step is exactly one configured controller period later (normally `2*0.0025=0.005 s`), uses that dt, and pairs feedback to the reset command.

Command and estimate timestamps equal the current due tick within the S0 `1e-12 s` tolerance. Feedback is the current actuator sample and identifies the single expected held command. Every rejection is strictly atomic: even a late-call rejection does not set a hidden fault flag. A corrected retry at the still-expected due tick is allowed and must equal a trajectory without the rejected call. An early/off-grid call may likewise be retried when that expected tick arrives. A duplicate/stale call after a successful step does not disturb the already scheduled next tick. If the expected due tick is actually missed, a later tick is rejected and the caller must reset before progress can resume; this obligation is derived from the unchanged expected tick, not from state mutated during rejection. The controller will not invent unobserved I/D or held-feedback evolution. This deliberately differs from the estimator gap policy.

| rejected call relative to expected `T` | accepted state after rejection | next acceptable action |
|---|---|---|
| command/estimate/feedback/dt invalid at `T` | byte-equivalent to pre-call snapshot; expected tick remains `T` | corrected call at `T` |
| finite call before `T` or off-grid below `T` | unchanged; expected tick remains `T` | valid call at `T` |
| stale/duplicate call below `T` after a prior success | unchanged; expected tick remains `T` | valid call at `T` |
| call later than `T`, proving `T` was missed | unchanged; expected tick remains `T` | `reset` with a higher epoch and valid nonrewinding boundary; reset returns the new zero command, then first step is one period later |
| off-grid call above `T` | unchanged; expected tick remains `T` | same reset sequence, because the due tick is already missed |

## Hand calculation: three due ticks and rejected retry

Illustrative x-axis fixture, with all unlisted axes zero: reset at `t=10.000`, `dt=.005`, `q_est=[1,0,0,0]`, `q_cmd=[cos(.05),sin(.05),0,0]`, `Katt=4`, `Kp=.08`, `Ki=.02`, `Kd=.004`, `tau=.02`; limits are not reached. Values below are rounded display values; tests use the full double expressions.

| publication | current / feedback / paired-command time (s) | omega x | I before | request = limited | limit backcalc rate | feedback actual / held limited | lag backcalc rate | I after |
|---|---|---:|---:|---:|---:|---|---:|---:|
| reset | 10.000 / n/a / n/a | n/a | 0 | 0 | 0 | n/a | 0 | 0 |
| tick 1 | 10.005 / 10.005 / 10.000 | 0 | 0 | 0.031986668 | 0 | 0 / 0 | 0 | 0.0000399833 |
| tick 2 | 10.010 / 10.010 / 10.005 | .1 | 0.0000399833 | 0.008026652 | 0 | .005 / .031986668 | -0.053973337 | -0.0001999000 |
| tick 3 | 10.015 / 10.015 / 10.010 | .12 | -0.0001999000 | 0.006186768 | 0 | .006 / .008026651 | -0.004053302 | -0.0001921832 |

At tick 2, `d_raw=20`, `alpha=.2`, `d_filtered=4`; at tick 3 `d_raw=4` and the filtered value remains 4. Conditional Ki rates are approximately `.007996667`, `.005996667`, `.005596667` Nm/s. Before valid tick 3, inject feedback claiming tick-2 timestamp but a changed limited value. The call is rejected and a complete snapshot remains equal. Retrying tick 3 with the valid tick-2 feedback produces the row above and the same command/state as the no-rejection control instance; the held publication remains tick 2 until that successful retry.

## Requirement and specification allocation

| Requirement | G2-B component decision | Frozen verification specification | Remaining boundary |
|---|---|---|---|
| `B0-REQ-0003` | core/adapters exclude runtime truth types | `B0-VER-TRUTH-BOUNDARY` | full runtime dependency trace remains G3 |
| `B0-REQ-0004` | fixed NED/FRD, SI, Hamilton body-to-NED types and tests | `B0-VER-CONVENTIONS` | integrated chain remains G3 |
| `B0-REQ-0007` | one atomic requested/limited/status/timestamp bundle | `B0-VER-PAIRED-COMMAND` | component-complete target |
| `B0-REQ-0009` | feedback resolves to a controller-published held command | `B0-VER-PAIRED-FEEDBACK` | integrated scheduling remains G3 |
| `B0-REQ-0016` | approved error sign and cascaded P/PID equations | `B0-VER-CONTROLLER-SIGN` | component-complete target |
| `B0-REQ-0017` | controller is sole clamp owner | `B0-VER-CONTROLLER-SATURATION` | downstream inspection included; full chain G3 |
| `B0-REQ-0018` | conditional integration and both paired back-calculation terms | `B0-VER-ANTI-WINDUP` | component-complete target; performance G3 |
| `B0-REQ-0019` | reject invalid numeric/time/type inputs atomically | `B0-VER-INVALID-INPUT` | controller portion only |
| `B0-REQ-0020` | epoch reset clears every controller-owned state | `B0-VER-RESET` | all-component reset remains G3 |
| `B0-REQ-0026` | C++ core and mandatory Python boundary have parity | `B0-VER-LANGUAGE-BOUNDARY` | controller portion only |
| `B0-REQ-0029` | invalid/stale estimate cannot update controller | `B0-VER-INVALID-MEASUREMENT` | controller portion only |

## Build and interface plan

`03_control/b0/CMakeLists.txt` will define `b0_controller_core`, mandatory `b0_controller_cpp_tests`, and mandatory pybind11 module `b0_controller`; C++17 is required and extensions are off. Root options/presets will disable legacy navigation and configure Debug and Release B0 builds. Catch2 stays at the repository-pinned commit and pybind11 at 2.13.6. The core remains independently linkable.

Defect detection keeps the correct independent oracle and owning numeric tests unchanged. A build-only script copies the audited core source into the temporary build tree and applies exactly one declared textual mutation per separate, noninstalled test target: attitude-feedback sign reversal, anti-windup back-calculation sign reversal, anti-windup removal, or using current limited torque for lag. Each variant must compile and then fail the predeclared numeric comparison (a compiler failure is not detection evidence). The unmodified production target is then clean-built and must pass. No mutation switch or fault branch enters the installed production target.

Python tests live under `03_control/b0/python/tests`; their loader verifies the actual imported module path. Adapters copy G2-A `q_nb_estimate`, `omega_b_estimate_rad_s`, timestamp and validity, and construct G1 `TorqueCommand` from the C++ bundle using original field names. Interface fixtures prove consumption compatibility only, not closed-loop performance.

## G3 responsibility boundary

G3 samples/holds attitude commands, supplies the current due-tick estimate and current actuator feedback, schedules the controller exactly on the integer grid, and carries epoch identity across adapters. G2-B owns control state, command history, validation, the unique torque clamp and component diagnostics. Scheduler recovery, full-loop reset orchestration and performance metrics remain G3 work.
