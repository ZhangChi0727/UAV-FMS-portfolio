# B0 G3 S0 integration design candidate

Status: **original-PA `DESIGN_ACCEPT` for exact candidate
`e3a5df2c7b21b4f4a4c7c6f296e0711222ac2569`**. Date: 2026-10-15
(Australia/Perth). Scope: G3-A deterministic integration, the G3-B metric
interpretations needed before implementation, and the G3-C evidence envelope.
The decision accepts this document's design only. Implementation and scenario
results remain separately reviewed and are not claimed by this document.

## Authority and identity

The runner shall load
`05_integration/b0/configs/b0_g0_contract.v2.json`, normalize only CRLF/CR to
LF, verify Git blob `1beff6e6a9a81d0ab92b2059a93207ffed9d291d` and canonical
SHA-256 `5b95531a6f96cb67ce25f624d6921bd313696f3c0b9868ec1de13c24c34cd98c`,
and invoke `05_integration/b0/validate_config.py` on the same bytes that it
uses. The accepted G2-A and G2-B configuration and approval overlays remain
authoritative. G3 neither copies their algorithms nor changes G0 thresholds,
events, seeds or parameter values.

The component path is:

```text
command sampler -> C++17 controller -> held TorqueCommand -> actuator
       estimate <- estimator <- event-adapted IMUSample <- IMU <- plant truth

plant truth -----------------------------------------------> sealed evaluator log
```

Plant truth may enter the IMU sensor boundary and the sealed post-run evaluator
only. Estimator initialization is the explicit G0 default, not plant truth.
Controller inputs are command, `StateEstimate` and paired `ActuatorFeedback`.

## Integer time model and phase order

The unique time identity is `(scenario_id, global_tick, epoch_id,
epoch_boundary_tick, local_tick)`, where
`local_tick = global_tick - epoch_boundary_tick`. The base period is exactly
0.0025 s. Each timestamp is derived as
`epoch_origin_s + local_tick * base_period_s`; accumulated floating-point time
and wall clock are prohibited scheduling sources.

A duration of `N` base intervals retains boundaries `0..N` (N+1 boundary
records). All event and criterion windows remain half-open `[start_tick,
end_tick)`, so the final boundary does not add duration. Global tick 0 and each
runtime reset tick are reset-only boundaries with no component step. For every
ordinary local tick `l >= 1`, the fixed order is:

1. Plant consumes the actuator actual torque retained from the preceding
   boundary plus any external body torque active at the current global tick,
   then advances one base interval.
2. Actuator consumes the `TorqueCommand` published strictly before the current
   tick and advances one base interval.
3. On local ticks `l >= 2` with `l mod 2 == 0`, IMU samples the phase-1
   interval-end truth exactly once; measurement events then adapt that sample.
4. On the same due tick, estimator consumes exactly that new IMU sample.
5. On the same due tick, controller consumes the current command, accepted
   estimate and phase-2 feedback with `dt_s = 0.005`.
6. Only after an accepted controller update is its new torque command published
   for actuator consumption on later ticks.

Plant and actuator are due every ordinary tick. IMU, estimator and controller
are due only on local ticks 2, 4, 6, .... An independent schedule oracle shall
recompute these sets from integers; component internal counters are not the
sole expected result.

At startup, local ticks 1 and 2 consume the reset command. The controller first
publishes at local tick 2; the actuator first consumes that publication at
local tick 3. A held command preserves epoch, publication tick, original
timestamp, requested torque, limited torque and saturation flags. Logging it at
another base boundary sets `updated=false` and never synthesizes a new command
timestamp. Feedback timestamp advances every actuator step, while its command
timestamp and limited/status fields identify the command actually held.

## Initialization and reset transaction

Plant initialization uses only the scenario's declared base quaternion/body
rate and any declared plant offset. The offset composition is
`q_base ⊗ qx(roll) ⊗ qy(pitch) ⊗ qz(yaw)` in scalar-first Hamilton
form. Estimator reset uses the explicit identity/zero G0 initial state;
command is identity; controller integral/filter state and actuator actual
torque are zero.

At a reset boundary, the runner performs one semantic transaction:

1. allocate the next monotonically increasing epoch ID and retain the current
   scenario time as epoch origin;
2. reset the controller first to obtain its reset `TorqueCommand`;
3. construct the actuator initial state explicitly from every paired field of
   that reset command and reset the actuator;
4. reset plant, IMU and estimator with their declared states, the same boundary
   time, and the scenario seed where required;
5. discard all pre-reset runner-held command, feedback, IMU, event and pairing
   state, then hold only the new reset command.

If any member reset fails, the run terminates as
`execution_error_inconclusive`; a partially reset loop must not continue. A
runtime reset at global tick R is reset-only. Its first normal tick is R+1 and
its first two estimator/controller updates are R+2 and R+4 regardless of R's
global parity. Scenario time never rewinds. IMU reset recreates the seeded RNG;
evidence records its public zero-based sample index before each sample and the
public emitted count afterwards, not an invented private scalar-draw index.

Reset replay uses an independent twin with the same explicit initial state,
seed, boundary and sealed input trace. It compares at least the first two valid
post-reset estimator updates (local ticks 2 and 4); the reset output itself is
not an update. Quaternion components use absolute tolerance `1e-12` as frozen
by G0.

## Event ownership and boundaries

Every event is active exactly when `start_tick <= global_tick < end_tick`.
Before reset or execution, the authoritative validator must accept the event
list. The runner independently requires nondecreasing `start_tick`, uses
declaration index as the stable tie break, rejects overlap on the same signal,
and rejects every cross-type overlap because the approved
`allowed_cross_type_overlap_pairs` set is empty. It never silently sorts or
resolves an invalid list. Tests lock ordering, prohibited overlap and the four
sides `start-1`, `start`, `end-1`, `end`.

At each ordinary boundary the event schedule is resolved before phase 1.
Command state is therefore available for the phase-5 controller sample;
external torque is applied only in phase 1; IMU measurement events only after
the single phase-3 sample; and invalid events only at their phase-4/5 owner.
A valid reset event is non-overlapping, makes its boundary reset-only, and
suppresses all ordinary phases without needing a priority rule over another
event.

- `command_step`: the sampler maintains per-axis declared values, applies the
  start value and returns that axis to zero at end, and composes
  `qx(value_x) ⊗ qy(value_y) ⊗ qz(value_z)` into a unit body-to-NED
  command quaternion. Approved events do not overlap; the per-axis state does
  not authorize overlapping commands. Only command quaternion,
  timestamp and validity reach the controller; event labels and truth do not.
- `external_torque`: phase 1 adds the declared body-FRD torque to previous
  actuator actual torque. The log retains actuator, external and total plant
  torque separately. External torque is neither clamped nor written into
  `ActuatorFeedback`.
- `imu_bias`: IMU is sampled once. A pure measurement adapter computes
  `raw - nominal_G1_bias + declared_replacement_bias`, preserving that sample's
  noise, timestamp and validity. It does not mutate G1 private parameters,
  recreate the IMU or reset its RNG.
- `specific_force_disturbance`: a pure measurement adapter adds the declared
  body-FRD vector to the sampled specific force only. Gyro, noise and time are
  unchanged. The event/limitation label is evaluator metadata, never an
  estimator input. The attitude-only SensorTruth translational acceleration is
  fixed at `[0, 0, 0]` m/s².

The external torque's first affected plant interval is the interval ending at
its `start_tick` phase-1 result, and exactly `end_tick-start_tick` phase-1 calls
are affected. This discrete endpoint interpretation is an S0 choice requiring
explicit PA acceptance.

## Invalid calls and same-tick recovery

The two approved invalid events exercise public component interfaces and each
counts once only when the expected rejection and state preservation are both
observed.

- At controller due tick 400, snapshot the C++ controller, call the real
  adapter with negative controller period, require reason `invalid_dt` and an
  unchanged complete snapshot, then retry once on the same tick with the same
  command/estimate/feedback and correct 0.005 s. Earlier phases are not rolled
  back.
- At estimator due tick 800, obtain the real IMU sample once, copy it with the
  previous accepted timestamp, call `AttitudeEstimator.process`, require
  `accepted=false`, reason `imu sample timestamp is duplicate or stale` and
  unchanged owned state, then submit the original correct sample on the same
  tick. Noise is not sampled again.

Wrong reason, failed retry, changed state, a second sensor sample or duplicate
event counting terminates the run as `execution_error_inconclusive`. Skipping a
controller due tick is not an approved recovery; a genuinely missed controller
tick requires the explicit all-component reset path.

## Truth isolation and module identity

Static checks use an import/call allowlist and provenance inspection to prevent
plant state, SensorTruth, truth quaternion/rate or event labels from entering
estimator/controller input construction. Runtime metamorphic checks hold the
IMU, command, initial-state and feedback traces fixed while changing only an
evaluator-owned truth copy; estimate and controller/torque traces must remain
identical. A separately isolated negative fixture deliberately introduces a
truth-derived estimator/controller input and must be rejected by the boundary
checker; production code contains no mutation switch.

G1 uses the package name `b0`, while G2-A and the controller extension have
different loading boundaries. The runner must resolve absolute paths, guard
`sys.modules`, and record the actual controller extension path, SHA-256, build
type, Python ABI and dependency versions. It must reject an unexpected G1
package, controller module, Debug/Release mix, or unapproved configuration.
G1 wire types remain unchanged even though their messages do not carry epoch
IDs; runner session metadata owns epoch identity and discards old objects on
reset. Every runner-held object is paired with that metadata. If its epoch does
not equal the current session epoch, the runner rejects it before any component
call, phase advance or held-state change; the G3-RESET negative check replays a
pre-reset object and requires a byte-for-byte unchanged runner/component
snapshot.

## Independent metric interpretations proposed for approval

The evaluator consumes a sealed raw trace after the run and does not import
production estimator/controller helpers as its oracle. It first rejects
non-finite values, wrong frame/unit, missing due ticks and quaternions outside
the declared norm tolerance; it does not normalize invalid data into a pass.
For every quaternion sample, `q_raw` must be finite and satisfy
`abs(norm(q_raw)-1) <= 1e-6`. `quaternion_norm_error` is evaluated on that
raw sample. Only after this check may the evaluator normalize a private copy
for the angle, logarithm and Euler calculations below.

- Overall attitude error is
  `2*acos(clamp(abs(dot(q_reference,q_candidate)),0,1))`.
- Axis and cross-axis errors use
  `q_rc = canonical(normalize(conjugate(q_reference) ⊗ q_candidate))`.
  Because each `q_nb` maps body FRD to NED, `q_rc` maps candidate-body
  coordinates into reference-body coordinates and its vector is expressed in
  reference-body FRD. After canonicalization to `w >= 0`, let
  `theta = 2*atan2(norm(v), w)` and use rotation vector
  `r = theta*v/norm(v)`, or exactly zero when `norm(v) == 0`. At the
  `w == 0` (pi-angle) tie, the first non-zero vector component is made
  positive, as in the accepted G2 canonical rule. Cross-axis error is the
  maximum absolute non-command-axis component, with command as reference and
  truth as candidate.
- Initial-offset tilt does not use yaw or the logarithm. It is exactly
  `acos(clamp(dot(R_nb(q_command)[:,2], R_nb(q_truth)[:,2]),-1,1))`, using
  the third columns of the body-to-NED rotation matrices.
- Signed overshoot uses the pre-event command as reference. The signed command
  delta and each response are shortest-log rotation vectors. Let
  `u = sign(delta_axis)*e_axis`; progress is `dot(response,u)` and target
  progress is `abs(delta_axis)`. Overshoot is
  `100*max(0,max(progress)-abs(delta_axis))/abs(delta_axis)`. Only a zero
  command delta is not applicable. Quaternion signs are made continuous before
  logarithm; the ±π tie break follows the accepted G2 canonical rule.
- Settling uses base-grid forward intervals. Boundary sample `k` labels the
  interval `[k,k+1)`. A 0.25 s dwell therefore requires exactly 100
  consecutive in-band interval-start samples `k..k+99`, whose covered dwell
  ends at boundary `k+100`; the end boundary is not itself sampled or counted
  because windows are half-open. Ninety-nine samples fail the dwell and exactly
  100 pass it. Settling time is `(k-origin_tick)*0.0025 s`. Step origin is
  event start, disturbance/withdrawal origin is event end, and initial-offset
  origin is zero. A complete valid window with no dwell is `performance_fail`;
  missing/truncated data is `inconclusive`.
- Roll, pitch and relative yaw use
  `q_te = canonical(normalize(conjugate(q_truth) ⊗ q_estimate))`, which maps
  estimate-body into truth-body coordinates. For scalar-first
  `q_te=(w,x,y,z)`, the fixed NED/FRD 3-2-1 extraction is
  `roll=atan2(2*(w*x+y*z),1-2*(x*x+y*y))`,
  `pitch=asin(clamp(2*(w*y-z*x),-1,1))`, and
  `yaw=atan2(2*(w*z+x*y),1-2*(y*y+z*z))`. Roll/yaw use the `[-pi,pi]`
  principal branch (with the same pi tie rule); pitch uses `[-pi/2,pi/2]`.
  Roll and pitch RMS are retained separately and both must satisfy the scalar
  limit; they are never collapsed before comparison.
- Relative yaw is unwrapped by choosing each adjacent due-sample branch nearest
  the preceding unwrapped value, then referenced to its first value and
  differenced using the actual adjacent timestamps. The maximum absolute rad/s
  value is compared. Held base samples are not differentiated and the result is
  not called absolute yaw.
- Saturation time is recomputed from each actuator interval's paired held
  requested/limited/status fields using strict `abs(request)>limit`. The
  phase-2 feedback recorded at boundary tick `k` describes the actuator
  interval `[k-1,k)`, not `[k,k+1)`. For criterion window `[a,b)`, its
  time weight is
  `max(0,min(k,b)-max(k-1,a))*0.0025 s`; duration is the union over axes
  after this interval clipping, never a count of sparse publications or a sum
  over axes. A controller publication at tick 200 is first consumed at
  actuator ticks 201 and 202, which represent `[200,201)` and `[201,202)`;
  if both are saturated, window `[200,202)` contributes exactly 0.005 s.
  Actuator tick 200 (before publication) and tick 203 (after the window) are
  explicit negative boundary fixtures. This actuator interval-end convention
  is independent of the settling metric's forward boundary-sample convention.
- Integral limits inspect both `integral_before_Nm` used in the current request
  and `integral_after_Nm` stored for the next step; the criterion uses the
  maximum absolute declared-axis value across their union, while evidence
  retains the two series separately.
- Invalid rejection requires the exact two event IDs, owners and stable reasons,
  not merely any count of two. Limitation characterization retains event
  activity plus estimator correction eligible/applied/capped diagnostics; it
  does not feed them back to the algorithm.

The axis-log choice, settling interval convention, per-axis RMS interpretation,
yaw differencing, held-interval saturation weighting, before/after integral
union and exact invalid-event set are explicit S0 choices requiring PA
`DESIGN_ACCEPT` before metric implementation.

## Scenario outcome rules

The eight approved scenarios and all 37 criterion IDs are closed by
[`g3_s0_verification_matrix.md`](g3_s0_verification_matrix.md). Six performance
scenarios are `performance_pass` only when every applicable criterion passes;
a valid numerical miss is `performance_fail`. Acceleration contamination ends
as `limitation_characterized` only when its declared limitation record is
complete. Invalid/reset ends as `invalid_input_rejected` only when the exact
rejections and replay criterion pass. Missing, inconsistent or invalid base
data always takes precedence as `execution_error_inconclusive`.

## Reachability gates

The frozen saturation-withdrawal case is high risk and is not statically proven
to trigger positive saturation. At the 40° x-step onset, the outer target is
clamped to 2 rad/s and zero-history proportional request is only 0.16 Nm versus
the 0.35 Nm limit. Even the optimistic two-second integral contribution at a
constant 2 rad/s error is 0.08 Nm, while derivative and lag feedback need not
increase the request. Saturation is possible elsewhere in controller state
space, but the frozen scenario trajectory must demonstrate it.

Immediately after `DESIGN_ACCEPT`, the first real-loop development probe shall
run seed `2026100906` unchanged and report request extrema, limit margin, every
saturated publication, mapped held base intervals, and their union duration.
The required 0.05 s is 20 base actuator intervals or 10 controller hold periods
within `[200,1000)`. A valid shortfall is `performance_fail`, not permission to
alter command, limit, criterion or flags. Any tuning proposal must be separately
versioned, use only the tuning seed, remain within approved ranges, explain
cross-scenario effects, and obtain PA approval.

That first diagnostic irreversibly exposes the acceptance seed. Before it
starts, the runner must create an immutable seed-exposure record with scenario,
seed, purpose `reachability_diagnostic`, exact source/config/module identities
and start time. Immediately after execution and before result inspection, it
finalizes the record with the output hash; thereafter
`acceptance_seed_exposed=true` remains in all later evidence. The exposure can
never be described as an untouched holdout and its result cannot be used to
tune or select parameters. Repeated diagnostics are separately logged. Only
tuning seed `2026100900` may be used for tuning work.

The 2 m/s² lateral acceleration contamination changes stationary specific
force magnitude by about 0.202 m/s², below the accepted estimator gate of about
1.471 m/s². Therefore that scenario characterizes a limitation and records
correction diagnostics; it must not claim to demonstrate gate rejection.

## S0 environment probe

The 2026-10-15 read-only WSL probe found system Python 3.8.10 and GCC 9.4.0.
The B0 virtual environment provides Python 3.11.17, CMake 3.30.5 and Ninja
1.11.1; system PATH does not provide CMake or Ninja, so commands must activate
that environment or use its absolute executables. Existing real modules were
found at the separate ignored Debug and Release build paths, and the existing
G2-B binding test file passed 49/49 against each module. This establishes the S0
tool/interface prerequisite only; it is not the planned G3-BIND 12-tick
closed-loop check or G3 performance evidence. No new account, service,
permission or dependency is required by this design candidate.

The planned G3-BIND check uses the test-only
`run_g3_bind_smoke(module_dir, build_type)` helper, never the approved-scenario
CLI. It accepts only tuning seed `2026100900`. Debug and Release each create
their own real-component loop with the approved G1/G2 parameters, identity
plant/estimator attitude, zero body rate and zero controller/actuator state. A
non-zero `qx(0.1 rad)` command is
active on local `[2,10)` over boundaries 0..12. Plant and actuator are called
12 times at local ticks 1..12; IMU, estimator and controller are each called six
times at 2,4,6,8,10,12. Sensor and feedback traces must emerge independently in
each loop and cannot be precomputed playback. This is a development fixture,
not a ninth G0 scenario, configuration overlay or acceptance-seed run.

## Implementation and command boundary after approval

G3-A may add a small runner, event adapter and adjacent tests under
`05_integration/b0/`; G3-B may then add the independent evaluator. Production
PID, plant, sensor, estimator and actuator algorithms remain in their accepted
modules. The proposed track-local interfaces are:

```text
cd 05_integration/b0
python runner.py --config configs/b0_g0_contract.v2.json \
  --scenario <approved-id> --module-dir <absolute-built-module-directory> \
  --build-type Debug|Release --run-id <unique-run-id> \
  --output-root <ignored-or-temporary-root>
python metrics.py --run-dir <sealed-run-directory> \
  --output <temporary-evaluation-json>
python evidence.py --runs-root <temporary-run-root> \
  --output <temporary-evidence-manifest>
```

`--all-scenarios` is mutually exclusive with `--scenario` and is reserved
for the later G3-B suite. `--run-id` is required, is provenance rather than an
RNG seed, and must match `[A-Za-z0-9][A-Za-z0-9._-]{0,63}`. The output
directory is exactly `<output-root>/<run-id>` and must not already exist;
overwrite or append is prohibited. The resolved config must be the approved
repository path and identity above, while the module directory must be absolute
and contain the requested build type and ABI. Every record carries run/scenario
ID, global/local tick, epoch ID/origin and seed. G3-A smoke uses tuning seed
`2026100900`, is labelled development-only and cannot populate accepted
criteria. Output paths must be outside tracked source or ignored; generated
traces, HTML, images and notebook outputs are not committed.

Exit semantics are fixed before implementation. `runner.py` returns 0 only for
a structurally complete execution (not a performance pass), 2 for CLI,
authority, config or module-identity failure, and 3 for
`execution_error_inconclusive`. `metrics.py` returns 0 only when every
required scenario outcome is accepted, 2 for setup/authority failure, 3 for
inconclusive or invalid data, and 4 for a valid criterion failure.
`evidence.py` returns 0 only for a validated manifest/closure, 2 for setup or
authority failure, and 5 for evidence/closure mismatch. No command maps a
failed or inconclusive criterion to success.

The evidence envelope is drafted in
`05_integration/b0/schema/b0_g3_integration_evidence.schema.json`. Each later
candidate records source, authority, module identity, schedule counts, raw
artifact hashes, scenario/criterion results, test/JUnit results, replay and
claim boundaries and seed exposure. JSON Schema is deliberately only the
structural envelope: it permits a faithfully recorded failed or inconclusive
run and cannot enforce uniqueness by an object's ID or recompute numerical
results. A mandatory G3-C semantic validator must project the exact eight
scenarios, 13 events and 37 criteria from G0, reject missing/duplicate/misbound
rows, recompute counts, outcomes, criteria, hashes and closure from raw data,
and check report totals and artifact availability against claims. Negative
tests must cover duplicate IDs with different payloads, scenario/criterion
misbinding, mismatched counts/statuses, deleted raw rows, altered values,
truncated JUnit, false replay, wrong source/module, hash mismatch and expired or
unverified evidence presented as verified.

The same separation applies to test reports. Their structural schema retains
the actual non-negative `collected/passed/failed/skipped/xfailed` counters,
including failed, skipped, xfailed or zero-collection reports. Such a record is
valid evidence *of what happened*, but cannot support `ACCEPT`. The later
semantic acceptance gate must reconcile all counters with retained JUnit,
require each mandatory production suite to collect at least one test, and
require `passed == collected` with zero failed/skipped/xfailed. S0 tests only
prove that the envelope can retain both passing and nonpassing reports; they do
not claim that the G3-C semantic gate already exists.

## Review decisions requested

The original PA is asked to accept or reject the following as one S0 package:

1. integer epoch-local schedule and the six fixed phases;
2. reset transaction, local phase restart, RNG/replay identity and held-command
   pairing;
3. event endpoint/ownership rules and same-tick invalid-call recovery;
4. truth-isolation and module-identity checks;
5. the independent metric interpretations above and the 37-row matrix;
6. evidence schema/semantic-validator boundary and fail-closed outcome
   precedence;
7. saturation reachability as an explicit post-acceptance stop/go probe rather
   than an assumed pass.

Until `DESIGN_ACCEPT` names this exact commit, scheduler, event and metric
implementation remains prohibited.
