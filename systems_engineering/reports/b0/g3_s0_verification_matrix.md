# B0 G3 S0 verification matrix candidate

Status: pending original-PA `DESIGN_ACCEPT`. This matrix fixes the planned
coverage and oracle inputs before implementation. It does not record execution.
Authority is G0 v2 canonical LF SHA-256
`5b95531a6f96cb67ce25f624d6921bd313696f3c0b9868ec1de13c24c34cd98c`.

## Integration test closure

| Group | Predeclared checks | Independent expected result | Primary allocation |
| --- | --- | --- | --- |
| G3-TIME | reset-only tick 0; first due tick; due/non-due; long sequence; non-zero origin; duplicate/omitted/reordered phase negative cases | Integer oracle independently derives every phase, timestamp and update count | B0-REQ-0002; B0-REQ-0021; B0-VER-REPLAY; B0-VER-SCHEDULING |
| G3-HOLD | reset command; publications at local 2/4/6; base-tick holds; request/limited/status and feedback command identity | Actuator consumes only a command published strictly before the interval | B0-REQ-0007; B0-REQ-0009; B0-VER-PAIRED-COMMAND; B0-VER-PAIRED-FEEDBACK |
| G3-EVENT | declaration-order ties; unsorted/same-signal/cross-type overlap negatives; all four sides of every event; six signed steps; bias replacement; force addition; torque separation | Authoritative and independent validation agree; exact `[start,end)` activity and owner-specific transformation | B0-REQ-0011; B0-REQ-0015; B0-REQ-0022; B0-VER-IMU-SPECIFIC-FORCE; B0-VER-ACCEL-CONTAMINATION; B0-VER-SCENARIO-CATALOGUE |
| G3-INIT | plant-only offset; explicit estimator identity; zero controller/actuator; no tick-zero integration | Initialization provenance has no implicit truth transfer | B0-REQ-0003; B0-REQ-0004; B0-VER-TRUTH-BOUNDARY; B0-VER-CONVENTIONS |
| G3-RESET | even/odd global reset; local R+2/R+4 updates; old-epoch object replay; all state/RNG/holds cleared | Runner/session boundary rejects stale-epoch objects without component call or state change; independent twin reproduces at least two valid post-reset updates | B0-REQ-0002; B0-REQ-0020; B0-VER-REPLAY; B0-VER-RESET |
| G3-INVALID | negative controller dt; stale estimator sample; full snapshot; one same-tick corrected retry; no second IMU sample | Exact owner/reason set, atomic state and clean-twin equality | B0-REQ-0019; B0-REQ-0029; B0-VER-INVALID-INPUT; B0-VER-INVALID-MEASUREMENT |
| G3-TRUTH | static provenance allowlist and runtime evaluator-truth metamorphic test | Changing evaluator-only truth cannot change estimator/controller/torque trace | B0-REQ-0003; B0-VER-TRUTH-BOUNDARY |
| G3-TRUTH-NEGATIVE | isolated truth-derived estimator initialization/controller input fixtures | Boundary checker rejects every predeclared forbidden edge | B0-REQ-0003; B0-REQ-0025; B0-VER-TRUTH-BOUNDARY; B0-VER-DEFECT-DETECTION |
| G3-BIND | actual module path/hash/ABI; G1/G2 package identity; mismatch negatives; actual Debug and Release modules each independently run a 12-local-tick real-component tuning-seed closed loop | Both loops generate their own plant/actuator/IMU/estimator feedback while loading their own controller build; integer/status outputs match exactly and floating traces match with `atol=rtol=1e-12` | B0-REQ-0026; B0-VER-LANGUAGE-BOUNDARY |
| G3-METRIC | hand-built positive/negative signals for each metric family, q/-q, threshold-adjacent floats, 99/100-tick dwell, half-open end, late peak, negative/zero step, yaw branch, overlapping saturation, no event and insufficient reset updates | Independent hand calculation agrees; each isolated defect fails or becomes the declared not-applicable/inconclusive class | B0-REQ-0023; B0-REQ-0025; B0-VER-EVALUATOR-INDEPENDENCE; B0-VER-DEFECT-DETECTION |
| G3-DATA | missing due tick/field, wrong frame/unit, non-finite, false pairing, clipped window, duplicate rejection | Outcome is inconclusive or validation failure, never a pass | B0-REQ-0023; B0-REQ-0024; B0-VER-EVALUATOR-INDEPENDENCE; B0-VER-EVIDENCE-PROVENANCE |
| G3-SCENARIO | exact eight scenario IDs, 13 event IDs and 37 criterion IDs | Exact-set closure; each row has raw locator, value and terminal status | B0-REQ-0022; B0-REQ-0023; B0-VER-SCENARIO-CATALOGUE; B0-VER-EVALUATOR-INDEPENDENCE |
| G3-REPLAY | two full runs and post-reset trace replay at matching version/config/seed | Identical schedule and declared deterministic streams | B0-REQ-0002; B0-REQ-0020; B0-VER-REPLAY; B0-VER-RESET |
| G3-EVIDENCE | schema, hashes, module/config identity, closure and expiry; deleted/altered/mismatched negatives | Validator recomputes and fails closed | B0-REQ-0024; B0-REQ-0027; B0-VER-EVIDENCE-PROVENANCE; B0-VER-CLEAN-CHECKOUT |

Every named check must be collected and pass with no skip/xfail before it is
used as implementation evidence. The final node names and JUnit locators are
filled in without changing the row meaning.

## Scenario catalogue

| Scenario | Class | Seed | Duration | Event rows | Events | Criterion rows | Required terminal class |
| --- | --- | ---: | ---: | ---: | --- | ---: | --- |
| `stationary_zero_command` | `in_envelope_performance` | 2026100901 | 2000 intervals | 0 | none | 3 | `performance_pass` or `performance_fail` |
| `initial_attitude_offset` | `in_envelope_performance` | 2026100902 | 2400 intervals | 0 | plant initial offset | 2 | `performance_pass` or `performance_fail` |
| `tri_axis_signed_steps` | `in_envelope_performance` | 2026100903 | 5600 intervals | 6 | six x/y/z signed command steps | 18 | `performance_pass` or `performance_fail` |
| `external_torque_disturbance` | `in_envelope_performance` | 2026100904 | 2000 intervals | 1 | one body torque event | 3 | `performance_pass` or `performance_fail` |
| `imu_noise_and_bias` | `in_envelope_performance` | 2026100905 | 4000 intervals | 1 | one nominal-bias replacement | 2 | `performance_pass` or `performance_fail` |
| `saturation_withdrawal` | `in_envelope_performance` | 2026100906 | 2400 intervals | 1 | one x command and withdrawal | 6 | `performance_pass` or `performance_fail` |
| `acceleration_contamination` | `limitation_characterization` | 2026100907 | 2000 intervals | 1 | one additive body specific-force event | 1 | `limitation_characterized` |
| `invalid_input_and_reset` | `invalid_input` | 2026100908 | 1200 intervals | 3 | two invalid calls and one all-component reset | 2 | `invalid_input_rejected` |

Any execution, identity, schedule or data-integrity defect overrides these
classes with `execution_error_inconclusive`.

## Exact 13-event projection

The runner loads these rows from G0 rather than from this table; the table is a
reviewable projection that the S0 asset test compares field-for-field with G0.
Intervals are global base-tick half-open intervals and declaration order is
preserved within each scenario.

| Scenario | Event ID | Type | Interval | Frozen payload |
| --- | --- | --- | --- | --- |
| `tri_axis_signed_steps` | `step_x_positive` | `command_step` | `[200,900)` | `{"axis":"x","value_rad":0.174533,"post_event_action":"return_axis_to_zero"}` |
| `tri_axis_signed_steps` | `step_x_negative` | `command_step` | `[1000,1700)` | `{"axis":"x","value_rad":-0.174533,"post_event_action":"return_axis_to_zero"}` |
| `tri_axis_signed_steps` | `step_y_positive` | `command_step` | `[1800,2500)` | `{"axis":"y","value_rad":0.174533,"post_event_action":"return_axis_to_zero"}` |
| `tri_axis_signed_steps` | `step_y_negative` | `command_step` | `[2600,3300)` | `{"axis":"y","value_rad":-0.174533,"post_event_action":"return_axis_to_zero"}` |
| `tri_axis_signed_steps` | `step_z_positive` | `command_step` | `[3400,4100)` | `{"axis":"z","value_rad":0.174533,"post_event_action":"return_axis_to_zero"}` |
| `tri_axis_signed_steps` | `step_z_negative` | `command_step` | `[4200,4900)` | `{"axis":"z","value_rad":-0.174533,"post_event_action":"return_axis_to_zero"}` |
| `external_torque_disturbance` | `bounded_external_torque` | `external_torque` | `[400,800)` | `{"vector_Nm":[0.08,-0.05,0.04]}` |
| `imu_noise_and_bias` | `replace_nominal_imu_bias` | `imu_bias` | `[0,4000)` | `{"gyro_bias_rad_s":[0.004,-0.003,0.002],"accelerometer_bias_m_s2":[0.06,-0.04,0.03],"application":"replace_nominal_bias"}` |
| `saturation_withdrawal` | `saturation_command` | `command_step` | `[200,1000)` | `{"axis":"x","value_rad":0.698132,"post_event_action":"return_axis_to_zero"}` |
| `acceleration_contamination` | `additive_specific_force_contamination` | `specific_force_disturbance` | `[400,1200)` | `{"vector_m_s2":[2,0,0],"application":"additive_to_nominal_specific_force"}` |
| `invalid_input_and_reset` | `negative_dt_rejection` | `invalid_input` | `[400,401)` | `{"invalid_kind":"negative_dt"}` |
| `invalid_input_and_reset` | `stale_timestamp_rejection` | `invalid_input` | `[800,801)` | `{"invalid_kind":"stale_timestamp"}` |
| `invalid_input_and_reset` | `deterministic_all_component_reset` | `reset` | `[1000,1001)` | `{"target":"all_components"}` |

## Metric-family signal contract

| Metric family | Required sealed raw inputs and selection | Independent output |
| --- | --- | --- |
| Attitude/tilt/cross axis | valid command/truth quaternions, frame `body FRD -> NED`, updated/held flags, base ticks | shortest-angle scalar or reference-body-FRD rotation-vector components |
| Body-rate error | truth and estimate body-FRD rad/s at valid estimator due ticks | per-axis error and declared max-absolute reduction |
| Quaternion norm | raw estimator quaternion at valid estimator due ticks | `abs(norm(q)-1)`; no pre-normalization |
| Settling | base-grid attitude/tilt error and declared origin/window/band/dwell | first complete 100-interval in-band start or finite failure/inconclusive reason |
| Overshoot | pre-event and target command plus truth quaternion over the event | signed-axis progress and percent overshoot |
| Roll/pitch RMS | truth and estimate relative quaternion at valid estimator due ticks | separate roll and pitch RMS values; both compared |
| Yaw drift | relative truth/estimate quaternion and actual due timestamps | unwrapped relative-yaw adjacent rates and maximum absolute rate |
| Saturation time | each phase-2 actuator interval-end record with paired requested, limited and status fields | union of clipped `[k-1,k)` intervals across axes; publication 200 then saturated consumptions 201/202 gives 0.005 s in `[200,202)`, while ticks 200/203 are boundary negatives |
| Controller integral | successful controller-tick `integral_before` and `integral_after` | per-axis maximum absolute value over both retained series |
| Limitation | event activity, adapted/raw sample, truth/estimate and estimator gate diagnostics | complete limitation record boolean; no algorithm feedback |
| Invalid/reset | event ID/kind/owner/reason, before/after snapshot and retry/replay traces | exact rejection set/count and reset replay boolean |

## Exact 37-criterion closure

`Window` values are half-open base-tick intervals. For settling, the origin is
event start for tracking, event end for disturbance/withdrawal, and zero for
initial offset. `G3-METRIC` supplies positive, negative and boundary oracles for
every metric family; `G3-SCENARIO` binds the real run.

| Scenario | Criterion ID | Metric / reducer | Event or axis | Window | Comparison | Raw selector / planned check |
| --- | --- | --- | --- | --- | --- | --- |
| `stationary_zero_command` | `stationary_attitude_peak` | `attitude_error_rad / max_abs` | — | `[0,2000)` | `<= 0.0174533 rad` | base truth vs identity command; G3-METRIC/SCENARIO |
| `stationary_zero_command` | `stationary_rate_peak` | `body_rate_error_rad_s / max_abs` | — | `[0,2000)` | `<= 0.05 rad/s` | valid due truth-estimate rate; G3-METRIC/SCENARIO |
| `stationary_zero_command` | `stationary_quaternion_norm` | `quaternion_norm_error / max_abs` | — | `[0,2000)` | `<= 1e-6 1` | updated valid estimates; G3-METRIC/SCENARIO |
| `initial_attitude_offset` | `offset_tilt_settling_time` | `tilt_settling_time_s / max` | — | `[0,2400)` | `<= 3 s` | origin 0; truth vs identity command, 100 intervals; G3-METRIC/SCENARIO |
| `initial_attitude_offset` | `offset_tilt_peak_error` | `tilt_error_rad / peak` | — | `[0,2400)` | `<= 0.4 rad` | base truth tilt; G3-METRIC/SCENARIO |
| `tri_axis_signed_steps` | `step_x_positive_settling_time` | `tracking_settling_time_s / max` | `step_x_positive` | `[200,900)` | `<= 1.2 s` | event-start origin, 100 intervals; G3-METRIC/SCENARIO |
| `tri_axis_signed_steps` | `step_x_positive_overshoot` | `tracking_overshoot_percent / max` | `step_x_positive` | `[200,900)` | `<= 20 %` | signed x progress; G3-METRIC/SCENARIO |
| `tri_axis_signed_steps` | `step_x_positive_cross_axis` | `cross_axis_attitude_error_rad / max_abs` | `step_x_positive` | `[200,900)` | `<= 0.0523599 rad` | max y/z log component; G3-METRIC/SCENARIO |
| `tri_axis_signed_steps` | `step_x_negative_settling_time` | `tracking_settling_time_s / max` | `step_x_negative` | `[1000,1700)` | `<= 1.2 s` | event-start origin, 100 intervals; G3-METRIC/SCENARIO |
| `tri_axis_signed_steps` | `step_x_negative_overshoot` | `tracking_overshoot_percent / max` | `step_x_negative` | `[1000,1700)` | `<= 20 %` | signed x progress; G3-METRIC/SCENARIO |
| `tri_axis_signed_steps` | `step_x_negative_cross_axis` | `cross_axis_attitude_error_rad / max_abs` | `step_x_negative` | `[1000,1700)` | `<= 0.0523599 rad` | max y/z log component; G3-METRIC/SCENARIO |
| `tri_axis_signed_steps` | `step_y_positive_settling_time` | `tracking_settling_time_s / max` | `step_y_positive` | `[1800,2500)` | `<= 1.2 s` | event-start origin, 100 intervals; G3-METRIC/SCENARIO |
| `tri_axis_signed_steps` | `step_y_positive_overshoot` | `tracking_overshoot_percent / max` | `step_y_positive` | `[1800,2500)` | `<= 20 %` | signed y progress; G3-METRIC/SCENARIO |
| `tri_axis_signed_steps` | `step_y_positive_cross_axis` | `cross_axis_attitude_error_rad / max_abs` | `step_y_positive` | `[1800,2500)` | `<= 0.0523599 rad` | max x/z log component; G3-METRIC/SCENARIO |
| `tri_axis_signed_steps` | `step_y_negative_settling_time` | `tracking_settling_time_s / max` | `step_y_negative` | `[2600,3300)` | `<= 1.2 s` | event-start origin, 100 intervals; G3-METRIC/SCENARIO |
| `tri_axis_signed_steps` | `step_y_negative_overshoot` | `tracking_overshoot_percent / max` | `step_y_negative` | `[2600,3300)` | `<= 20 %` | signed y progress; G3-METRIC/SCENARIO |
| `tri_axis_signed_steps` | `step_y_negative_cross_axis` | `cross_axis_attitude_error_rad / max_abs` | `step_y_negative` | `[2600,3300)` | `<= 0.0523599 rad` | max x/z log component; G3-METRIC/SCENARIO |
| `tri_axis_signed_steps` | `step_z_positive_settling_time` | `tracking_settling_time_s / max` | `step_z_positive` | `[3400,4100)` | `<= 1.2 s` | event-start origin, 100 intervals; G3-METRIC/SCENARIO |
| `tri_axis_signed_steps` | `step_z_positive_overshoot` | `tracking_overshoot_percent / max` | `step_z_positive` | `[3400,4100)` | `<= 20 %` | signed z progress; G3-METRIC/SCENARIO |
| `tri_axis_signed_steps` | `step_z_positive_cross_axis` | `cross_axis_attitude_error_rad / max_abs` | `step_z_positive` | `[3400,4100)` | `<= 0.0523599 rad` | max x/y log component; G3-METRIC/SCENARIO |
| `tri_axis_signed_steps` | `step_z_negative_settling_time` | `tracking_settling_time_s / max` | `step_z_negative` | `[4200,4900)` | `<= 1.2 s` | event-start origin, 100 intervals; G3-METRIC/SCENARIO |
| `tri_axis_signed_steps` | `step_z_negative_overshoot` | `tracking_overshoot_percent / max` | `step_z_negative` | `[4200,4900)` | `<= 20 %` | signed z progress; G3-METRIC/SCENARIO |
| `tri_axis_signed_steps` | `step_z_negative_cross_axis` | `cross_axis_attitude_error_rad / max_abs` | `step_z_negative` | `[4200,4900)` | `<= 0.0523599 rad` | max x/y log component; G3-METRIC/SCENARIO |
| `external_torque_disturbance` | `disturbance_peak_attitude` | `attitude_error_rad / peak` | `bounded_external_torque` | `[400,2000)` | `<= 0.35 rad` | truth vs command; G3-METRIC/SCENARIO |
| `external_torque_disturbance` | `disturbance_recovery` | `attitude_settling_time_s / max` | `bounded_external_torque` | `[800,2000)` | `<= 2.5 s` | event-end origin, 100 intervals; G3-METRIC/SCENARIO |
| `external_torque_disturbance` | `disturbance_saturation_time` | `actuator_saturation_time_s / total_time` | — | `[0,2000)` | `<= 1 s` | paired held interval union; G3-METRIC/SCENARIO |
| `imu_noise_and_bias` | `imu_roll_pitch_rms` | `roll_pitch_estimation_error_rad / rms` | — | `[0,4000)` | each `<= 0.0872665 rad` | valid due relative q, two outputs; G3-METRIC/SCENARIO |
| `imu_noise_and_bias` | `imu_yaw_drift` | `yaw_drift_rad_s / max_abs` | — | `[0,4000)` | `<= 0.05 rad/s` | valid due relative-yaw differences; G3-METRIC/SCENARIO |
| `saturation_withdrawal` | `saturation_integral_x_limit` | `controller_integral_Nm / max_abs` | x | `[0,2400)` | `<= 0.15 Nm` | before/after union; G3-METRIC/SCENARIO |
| `saturation_withdrawal` | `saturation_integral_y_limit` | `controller_integral_Nm / max_abs` | y | `[0,2400)` | `<= 0.15 Nm` | before/after union; G3-METRIC/SCENARIO |
| `saturation_withdrawal` | `saturation_integral_z_limit` | `controller_integral_Nm / max_abs` | z | `[0,2400)` | `<= 0.1 Nm` | before/after union; G3-METRIC/SCENARIO |
| `saturation_withdrawal` | `saturation_recovery` | `attitude_settling_time_s / max` | `saturation_command` | `[1000,2400)` | `<= 2 s` | event-end origin, 100 intervals; G3-METRIC/SCENARIO |
| `saturation_withdrawal` | `saturation_duration_upper_bound` | `actuator_saturation_time_s / total_time` | — | `[0,2400)` | `<= 2 s` | paired held interval union; G3-METRIC/SCENARIO |
| `saturation_withdrawal` | `saturation_triggered_duration` | `actuator_saturation_time_s / total_time` | `saturation_command` | `[200,1000)` | `>= 0.05 s` | positive reachability gate; G3-METRIC/SCENARIO |
| `acceleration_contamination` | `acceleration_limitation_recorded` | `limitation_event_recorded / all` | `additive_specific_force_contamination` | `[400,1200)` | `== true bool` | raw/adapted sample and diagnostics; G3-EVENT/SCENARIO |
| `invalid_input_and_reset` | `invalid_input_rejected` | `invalid_input_rejection_count / min` | — | `[0,1200)` | `>= 2 count` plus exact-set closure | exact two invalid events; owner/reason/snapshot/retry; G3-INVALID/SCENARIO |
| `invalid_input_and_reset` | `reset_is_deterministic` | `reset_replay_match / all` | `deterministic_all_component_reset` | `[1000,1200)` | `== true bool` | local +2/+4 valid updates; G3-RESET/REPLAY/SCENARIO |

## Criterion record requirements

Each implemented row shall retain its scenario and criterion ID, the G0 JSON
pointer and digest, event/axis, window/origin/dwell, raw signal names with
frame/unit and updated/held policy, metric version and formula, selector,
reducer, operator/limit/unit, scalar or vector result, status, reason, raw
locator/hash, independent oracle node and requirement/specification allocation.
The set of criterion IDs must be exact and unique; a family-level aggregate
cannot substitute for any row.

The Debug/Release G3-BIND positive check builds and loads each real controller
extension rather than reusing one artifact under two labels. The planned
test-only helper is `run_g3_bind_smoke(module_dir, build_type)`; it rejects any
seed other than tuning seed `2026100900` and is not exposed as an approved
scenario CLI entry or configuration overlay. Each build independently runs the
real plant→actuator→IMU→estimator→controller loop over local boundaries 0..12
with approved G1/G2 parameters, plant/estimator identity quaternion, zero body
rate, zero controller and actuator state, and command `qx(0.1 rad)` active on
local `[2,10)`, then zero.
Plant and actuator each receive exactly 12 calls at local ticks 1..12;
IMU/estimator/controller each receive exactly six calls at 2,4,6,8,10,12.
IMU samples and actuator feedback must emerge from that build's own loop;
replaying a precomputed IMU/feedback trace or using only a zero command is not
this check. Module path/hash/build type must differ as expected; schedule,
booleans, reasons, update flags and integer fields match exactly, and every
finite floating field is compared with
`abs(a-b) <= 1e-12 + 1e-12*abs(b)`. This development
interface/reproducibility fixture is not a ninth G0 scenario and is not
acceptance-seed performance evidence.

## Fail-closed rules

- Valid complete data that misses a numerical limit is `fail`; no settling
  dwell is not represented by an artificial finite value.
- Missing due ticks, fields, windows or non-finite/wrong-frame data is
  `inconclusive`, not `fail` or `pass`.
- A zero signed command delta alone makes overshoot `not_applicable`; no current
  G0 signed-step row has a zero delta.
- A saturated flag is cross-checked against request/limit and is never the sole
  saturation oracle.
- Event labels and truth remain evaluator inputs only and cannot alter
  estimator/controller execution.
- JSON Schema acceptance alone is never an evidence pass. The semantic
  validator must reject duplicate IDs even when their payloads differ,
  criterion-to-scenario or event misbinding, incomplete 8/13/37 projections,
  inconsistent computed values/status/outcomes/counts, raw/hash/JUnit
  truncation, false replay, and unavailable evidence represented as verified.
- A failed or inconclusive run may validly satisfy the structural schema so its
  failure is retained; only recomputed semantic closure may authorize an
  accepted terminal claim.
- Raw test-report counters are non-negative structural data. A report with
  failures, skips, xfails or zero collection remains recordable but cannot
  support `ACCEPT`; the mandatory semantic gate must reconcile JUnit totals,
  require nonzero collection and require all mandatory production tests to
  pass with zero skipped/xfail.
