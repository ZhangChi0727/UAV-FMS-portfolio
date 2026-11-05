# G3-A development evidence contract v1

Status: **design implementation only; not independently accepted or executed**.
Date: 2026-10-23 (Australia/Perth). Sole specification author: PA internal
`next_validation_scope_audit`. An independent non-author reviews this contract
and the eventual checker; the author does not sign their own acceptance.

Authority: [approved work order](../../../../docs/work_orders/B0_G3_A_evidence_closure_work_order.md),
SHA-256 `07173EF2CC3D939DA047EDC9ADFA028D9D38C480662CD828FB7D249B49DD9D82`,
and the subsequent Owner/PA releases recorded in
[the execution protocol](../../../../systems_engineering/reports/b0/g3a_evidence_closure_protocol.md).
The accompanying [JSON Schema](g3a_evidence_schema.v1.json) defines shape, not
evidence acceptance. No checker, schema validator, component, test, build,
simulation or seed was executed to produce this specification.

## 1 Purpose and fixed scope

This is the smallest record contract for the work order's S/L/O/E/T/N development
collection. It is not a generic verification platform, a copied plant/controller,
or a new system requirement. Existing G0/G1/G2 numerical contracts, parameters,
approval overlays and conventions remain authoritative.

The eight profile records, in execution order, are `S`, `L1`, `L2`, `O1`, `O2`,
`E`, `T1`, `T2`. N_E/N_C and five old-epoch probes attach to existing live
boundaries; they are not additional component profiles. All use development seed
`2026100900`. They are never named or classified as the eight normal G0 scenes.
No 50 ms, normal-scene, parameter-acceptance or physical-validity claim is made.

Source/configuration, actual build/module, environment/F0, raw transport
integrity, schema, semantic checks and PA acceptance are separate predicates.
Missing observation, unknown policy, skipped check or incomplete trace is
`execution_error_inconclusive`, never a pass. A retained aborted trace may be
structurally recordable without satisfying a successful profile or batch.

## 2 Three offline APIs and external authority

The eventual stdlib-only module exposes exactly these functions; this document
does not authorize their execution:

```python
check_record_set(raw_bytes: bytes, authority: dict) -> dict
compare_builds(debug_raw: bytes, release_raw: bytes,
               debug_authority: dict, release_authority: dict) -> dict
make_data_diagnostics(raw_bytes: bytes, authority: dict) -> tuple[dict, ...]
```

The functions must not import DUT packages, loaders, scheduler/events helpers,
NumPy, extension modules or an executable entry point; instantiate components;
sample randomness; run subprocesses; write files; or repair inputs. Pure stdlib
hashing, JSON decoding, integer arithmetic and scalar offline comparisons are
permitted only in a later explicitly released checker batch. Importing the
checker itself must have no action beyond definitions/constants.

`authority` is supplied from the externally accepted PA/F0 input, not recovered
from the raw's own identity claims. It contains:

- `authority_version = "b0-g3a-authority/v1"` and an externally sealed authority
  artifact locator/digest; source commit/tree and exact source-closure manifest;
- approved config/approval manifest, approved expected constructor input values
  derived as pure data (not actual future constructed objects), fixed
  profile-definition bytes/digest, immutable component and
  observer source versions, expected schema/spec/checker digests;
- accepted environment/F0 manifests; build type, actual loaded module path,
  bytes hash and ABI; expected frame/unit conventions;
- accepted field-comparison policy and fixed input/profile definitions;
- `transport`: expected SHA-256 of the bytes for this call, artifact locator,
  and optional diagnostic parent hash/ID. This per-artifact transport envelope is
  distinct from immutable source/config/module authority.

The normal raw transport hash is fixed before consumption. Diagnostic factories
may calculate a new transport hash for each isolated copy, but must carry the
same immutable authority without changing its source/module expectations. The
non-author checks the copy bytes/hash/diff. No hash of a raw object is embedded
inside that same raw object, and no raw-supplied expected digest authorizes itself.

The immutable pre-run authority basis contains expected approved inputs and pure
data/configuration bindings only. It must not call a loader, construct a DUT or
run an observer to invent future actual parameter snapshots. Actual constructor
parameters are produced by the later lifecycle observations and then compared
with that basis. The raw transport hash is produced only after the raw exists,
then sealed in a separate post-run transport envelope before offline consumption.
Environment/module facts are independently collected and checked against the
accepted policy; their actual byte binding is neither guessed before collection
nor inferred from raw's expected claims. No artifact contains its own full-byte
hash. CI preflight applies the PA-accepted policy and reports a machine check;
it does not fabricate a human `F0_ACCEPT` signature or replace PA review.

For config-document recomputation the in-memory API additionally receives
`authority["input_artifact_bytes"]`, a finite externally supplied mapping from
accepted artifact ID to actual immutable bytes, and
`authority["artifact_sha256"]`, its separately accepted digest mapping.
The checker hashes/decodes those bytes and validates all referenced input
artifacts, rather than opening raw-suggested paths or importing a loader.
The independently owned authority/collection helper may decode retained
base64/files into this in-memory mapping under its accepted manifest. Its own
execution, reads and byte/approval binding are separately accounted; the raw
cannot extend the mapping or choose its expected digest. No constructor,
loader or parameter getter is used to assemble that pure-data input.

The serialized authority basis stores those bytes as `input_artifact_base64`;
the independently owned `load_consumer_authority(path, expected_sha)` may
strictly decode them into `input_artifact_bytes`. It preserves the accepted
`artifact_sha256`, identity and parameter_inputs maps, and only the later
consumer copy adds `transport` and `authority_basis_sha256`. The checker never
calls this helper to derive expected parameters; it independently validates
the already supplied pure-data basis/transport/bytes. Source-relative config
path bindings resolve under the accepted actual source root, never raw claims.

`authority["identity"]` uses exactly the existing sixteen raw identity keys in
the schema; values come from accepted expected bindings/independently collected
facts, not the raw itself. Do not add a field to satisfy a mistaken field count.
`authority["parameter_inputs"]` is the pure-data expected manifest:
`manifest_version="b0-g3a-expected-parameter-inputs/v1"`,
`semantics="approved_expected_inputs_not_runtime_observations"`,
`components={plant,actuator,imu,estimator,controller}`, and `bindings` with
component/field/source_path/JSON pointer or approved literal/formula, encoding,
unit and source locator. Plant/actuator/IMU each contain the complete same typed
G1 values, not an untracked subset; estimator/controller contain their complete
typed parameter values. The raw kind `g1` is checked against the appropriate
observed consumer (and the common G1 map); `estimator` and `controller` map to
their named components, including adapter/core use. Paths derive only from the
accepted source-root/policy, no loader. The manifest hash binds these expected
inputs; actual observed values remain exclusively in raw parameter_objects.

`check_record_set` returns `report_version`, recomputed raw and authority digests,
`status` (`pass`, `reject`, `execution_error_inconclusive`), exact `reason`,
`path`, profile/group results, independently rebuilt and reported counts,
comparison maxima/locators, and limitations. `pass` means only that this accepted
G3-A evidence contract passed on that exact record set, not PA/G3-A acceptance.

`compare_builds` first requires each complete input to pass independently,
different accepted build/module identities, and matching source/config/profile
identity. It compares matching logical records, not module paths or inherently
different build metadata. It returns per-field-policy maxima and exact locations;
no omitted field, silent sign normalization or unapproved tolerance fallback.

`make_data_diagnostics` first checks the immutable input transport/identity and
returns thirteen in-memory entries in section 10 order: one unchanged legal
control, then twelve single-defect copies. Each entry contains `diagnostic_id`,
`parent_raw_sha256`, `raw_bytes`, `raw_sha256`, `transport`, `mutation` (JSON
pointer, operation, before, after), and `expected_reason`. It does not itself
call the checker thirteen times. The separately accounted negative-test batch
does so once per entry. It never edits the original or relaxes immutable authority.

## 3 Minimal raw structure and number encoding

Top-level keys are `schema_version`, `identity`, `conventions`, `completion`,
`termination_reason`, `parameter_objects`, `lifecycle_observations`, `profiles`,
and `reported_counts`. This is the single V1 merged-revision design, not a new
execution result. The first-review spec/schema bytes are retained by PA in
`build/g3a-evidence-env/20261022-initial/interrupted-static-source-snapshot.json`;
this revision does not rewrite that history or accept the interrupted TC draft.

`schema_version = "b0-g3a-evidence/v1"`. `identity` retains work-order,
source/tree/closure, config/approval, profile-definition, environment/F0,
observer and parameter-input manifest digests, actual module path/hash/ABI,
Debug/Release label, seed and the literal classification
`development_integration_not_normal_acceptance`. Those claims must match the
external authority and the actual execution/F0 records.

All signal floats are canonical finite Python/binary64 `float.hex()` strings,
including signed zero, fixed-shape vectors/matrices and timestamps. Accepted
canonical examples are `0x0.0p+0` and `0x1.0000000000000p+0` (Python's
canonical zero has one fractional hex digit, unlike nonzero normal values).
`nan`, `inf`, `-inf` are structurally representable solely to retain failed raw
and create owning diagnostic cases; they can never pass semantic preflight.
No decimal round-trip, string-to-boolean coercion, JSON nonstandard NaN numeric
literal, duplicate JSON key or integer/boolean interchange is permitted.

Time in real G3-A is S0's binary64 expression
`epoch_origin_s + local_tick * base_period_s` (multiply, then add, no FMA or
accumulation), not the synthetic P1 metric profile's rational tick/400 rule.
Integer identities remain the scheduling oracle regardless of timestamp tolerance.

Conventions are NED, body FRD, scalar-first Hamilton `q_nb` body-to-NED; time s,
angular rate rad/s, angular acceleration rad/s2, torque Nm, force m/s2 and
inertia kg m2. Units use the exact strings in the schema and are not inferred
from an axis label. Schema string fields intentionally retain bad frame/unit
values so semantic rejection can identify `frame_mismatch`/`unit_mismatch`.

### 3.1 Profile contents

Each profile has `profile_id`, `horizon_tick`, `reset_ticks`, `initial_inputs`,
`wires`, `boundaries`, `probes`, `snapshots`, and `reported_counts`.
`initial_inputs` fixes explicit plant/estimator quaternion/rate, actuator state,
controller initial/reset-local command and epoch-origin mapping from the accepted
profile definition. It cannot be sourced from live truth. No future run fills
these values by observing an output.

`wires` is a flat list of named producer values, not a general object graph.
Each has a unique `wire_id`, `kind`, producer operation/field, original producer
epoch/global tick/phase and typed `payload`. Calls reference these stable IDs.
Wire kinds are fixed: plant state, sensor truth, torque command, feedback, IMU,
estimate, attitude command, estimator diagnostics and controller diagnostics.
The consumer envelope epoch is retained at production, never retagged on
consumption by the controller adapter. `producer_operation_id = null` is allowed
only for a declared explicit initialization/reset input or evaluator-owned N/T
copy with its N probe derivation or fixed T definition/source locator; it is
not an untracked input escape.

Payload shapes follow the actual G1/G2 public messages. A torque command contains
request, limited target, three saturation flags and command timestamp. Feedback
contains actual, limited, flags, timestamp and paired command timestamp; pairing
recovers request from the exact held command reference. IMU contains gyro,
specific force, timestamp and validity. Estimate/attitude command carry their
actual fields, not evaluator labels. Truth records include quaternion/rate and
zero translational acceleration and are only sensor/evaluator inputs.

Wire names are canonical recorder names, with this explicit public-field map:
IMU `gyro_rad_s <- gyro_b_rad_s` and `specific_force_m_s2 <- specific_force_b_m_s2`;
estimate `q_nb <- q_nb_estimate`, `omega_b_rad_s <- omega_b_estimate_rad_s`;
attitude command `q_nb <- q_nb_command`; sensor truth
`translational_acceleration_n_m_s2 <- acceleration_n_m_s2`. Plant/torque/feedback
names otherwise retain their public names. The observer map records exact source
attributes, never guesses aliases by fallback. These serial names do not change
component APIs. Core snapshot held command additionally retains its real epoch.

All controller diagnostics fields are retained, including I-before/I-after,
measurement-D/filter, conditional/limit/lag AW, requested/limited/status,
epoch/tick/reason. Their existence is observation, not an independently recomputed
PID performance oracle. Estimator diagnostics retain accepted/reason, correction
eligibility/application/cap, elapsed/missing periods and `gap_approximated`.

### 3.2 Boundary/call contents

Each boundary retains `global_tick`, `epoch_id`, `epoch_origin_tick`, `local_tick`,
`epoch_origin_s`, `timestamp_s`, `boundary_kind` (`reset` or `ordinary`), resolved
`event_inputs`, `held_before_ref`, `published_after_ref`, and the actual ordered
`operations` array. Held reference is unchanged at non-publication boundaries.
`published_after_ref` is the command held after this boundary (not a fictitious
publication every tick); only an actual accepted phase6 operation changes it.
At initial reset, `held_before_ref` may be null, and the reset command becomes
the held-after value. Updated/held semantics are independently reconstructed
from this actual operation/reference history, not a self-reported boolean.

Each operation has a unique ID; actual `owner`, `method`, `phase`, `attempt_kind`,
`inputs`/`outputs` stable wire references, scalar/reset inputs, accepted/reason,
before/after snapshot references where required, and guard reference where
required. Phase labels do not establish order: the checker examines array order.
`attempt_kind` distinguishes normal, injected invalid, same-tick correction,
reset and publication. Internal delegation is recorded separately in counts,
not counted as another due update.

`inputs` uses only the fixed keys in the schema. `scalar_inputs` includes actual
dt, timestamp, explicit interval_start_tick/interval_end_tick for base steps,
external body torque, total plant torque and translational
acceleration where consumed. Reset inputs are actor-specific actual public
arguments (section3.3), not a fictional common q/rate/seed signature, and include
full actuator pairing from the controller reset output. No hidden default
argument, loader call, validator or helper is excused by this record shape.

A paper-only fragment illustrates the IDs; it is not a retained execution:

```json
{
  "operation_id": "S/k3/p2/actuator",
  "owner": "actuator", "method": "step_base", "phase": 2,
  "attempt_kind": "normal",
  "inputs": {"torque_command": "S/k2/p6/torque"},
  "outputs": {"feedback": "S/k3/p2/feedback"},
  "scalar_inputs": {"dt_s": "0x1.47ae147ae147bp-9"},
  "reset_inputs": null, "accepted": true, "reason": "accepted",
  "before_snapshot_ref": null, "after_snapshot_ref": null, "guard_ref": null
}
```

The dt above is the base-period binary64 representation, not a new parameter.
Complete records must resolve the named wires and match external approved inputs.

### 3.3 Actual lifecycle observations and actor-specific reset arguments

`lifecycle_observations` is one ordered top-level array so setup calls before the
first profile are observable too. It is a finite call ledger, not a scheduler,
general graph registry or replacement for the existing operation records.
Each record has contiguous `observation_index`, `call_id`, `parent_call_id`,
nullable `profile_id`/`operation_id`, `owner`, `method`, `event`
(`enter`, `return`, `exception`), `callsite`, nullable `actor_id`, `core_use`,
`arguments`, `result`, and `exception`. Stable call/actor IDs are audit identities
bound at the actual delegation/return site, never repr/memory addresses.

The finite methods are `constructor`, `load_parameters`, `load_config`,
`validate_config`, `capture_snapshot`, and `reset`. Owners are the enumerated
component/parameter/loader/validator/observer/session roles in the schema.
The accepted E2 callsite list fixes the actual functions and additional finite
helper counters, not an open-ended method-string escape. Every invocation has
one enter and exactly one return or exception; nested calls carry the active
parent, terminal records follow their children, and an aborted invocation stays
explicitly incomplete. A successful complete batch cannot contain an unmatched
call, missing wrapper, duplicate terminal event or unknown callsite.

Record enter immediately around the real delegated call, not from loop/profile
counts after execution. Record return only after that actual delegate returns;
record failure with its actual exception type/reason/message. Static non-author
review verifies every real entry path and transparent wrapper: no changed
argument/default, bypassed validation, extra core construction or overwritten
production algorithm. Where Python dynamic loading creates fresh validator
module objects, wrapping one previously loaded module does not cover the others.
Observe the accepted exact entry path before its first use or fail closed.

Every actual `CascadedController` invocation must be observed:
`core_use = temporary_validation` inside the actual controller loader, versus
`production` inside the actual adapter constructor. Link both via parent call
IDs, actual loaded binary identity, and precise parameters supplied to that
call. A loader count multiplied by2, a production adapter count multiplied by2,
or a driver-written literal16 is not sixteen observed core constructions.
Count entered/returned/failed invocations separately and reconcile the expected
sixteen successful core returns with this ledger and real call graph.

`parameter_objects` retains detached exact value snapshots taken from actual
parameter objects at the consuming constructor/return boundary. Entries have
unique `parameter_object_id`, `kind` (`g1`, `estimator`, `controller`),
`capture_kind` (`object_values` or `constructor_fields`), `values_sha256`, and
typed `values`. `constructor_fields` means actual field arguments of a
parameter-data constructor, not a falsely pre-existing constructed object.
The digest is SHA-256 of UTF-8 JSON of
`values`, sorted keys, compact separators, ensure_ascii=true, allow_nan=false;
all floating values use the canonical hex encoding above. The checker recomputes
it and compares actual fields with external approved expected values. This does
not replace the external configuration/approval/byte checks or pre-run authority.

Constructor arguments distinguish explicit parameters, raw `parameter_fields`,
a true default-loader path, module-only adapter construction, and a genuinely
empty parameter object. A fresh empty ControllerParameters factory return is
not falsely treated as an approved populated object: retain its real empty
arguments/actor return, then snapshot its actual populated values at the loader
return and each core-consuming constructor. Only actual consumed parameters,
populated loader results and corresponding constructor-field inputs are bound
to approved expected values; unused intermediate defaults cannot authorize one.
A default constructor must not be falsely logged as receiving a parameter
argument. Its nested loader's actual return snapshot and the component's public
parameter observation bind the eventual value. The C++ core only claims the
actual input parameter object plus the accepted static copy path, not private
readback. Core constructor enter captures that call's actual parameter value,
even when the same Python parameter object also went into a temporary core.
Loader returns reference their actual returned parameter snapshot; observer
calls reference actual capture/snapshot IDs and the observer-map digest.
Repeated captures may have distinct IDs with equal values; no fabricated alias
or readback. Audit actor bookkeeping must never authorize a guard decision.

Typed lifecycle argument variants are constructor, loader, config, observer,
or actor-specific reset. Config arguments record the actual path and consumed
byte digest for load_config, or the actual parsed-document value digest and its
bound consumed-byte source for validate_config; do not log validate_config as a
path-taking API. The underlying frozen bytes/document are available through the
externally sealed input artifact. `check_record_set` consumes the inline ledger
and parameter objects plus that external artifact binding; an unavailable,
unexamined sidecar is not an observed call. The same-byte/document-input
relationship is source-reviewed and independently rehashed.

The document-input digest uses UTF-8 JSON of the actual parsed argument with
sort_keys=true, compact separators, ensure_ascii=true, allow_nan=false, retaining
ordinary JSON number types; this is distinct from hex-valued parameter/signal
encoding. Reconstruct the expected parsed object from the accepted source bytes
and apply that exact document-digest rule. An actual validate_config argument
which differs from the loaded source document fails binding even if both
documents separately would validate. This is equality/provenance, not a new
invocation of the authority validator by the independent checker.

| reset_inputs.actor | Actual public arguments retained |
| --- | --- |
| controller | adapter `reset_epoch={id,timestamp_s}` only |
| controller_core | core `initial_state={}`, `reset_epoch={id,timestamp_s}`; nested call separately observed, not a second top-level reset |
| plant | `initial_state={q_nb,omega_b_rad_s}`, scalar `reset_epoch_s` |
| actuator | `initial_state={actual_torque_body_Nm,held_limited_torque_body_Nm,held_requested_torque_body_Nm,held_saturated,held_command_timestamp_s}`, scalar `reset_epoch_s` |
| imu | empty `initial_state={}`, scalar `reset_epoch_s`, `rng_seed` |
| estimator | `initial_state={q_nb,omega_b_rad_s}`, `reset_epoch={id,timestamp_s}`, `rng_seed` |

Actuator actual torque is the actual explicit initial argument, not inferred
from limited/requested. All held request/limited/status/timestamp arguments
must match the controller reset output field-for-field; its stable source is
`reset_command_ref`. Distinguish initial-state object creation from real reset
consumption; q/seed are never added to APIs which do not receive them. Operation
reset arguments and corresponding lifecycle enter arguments agree exactly.

Observer enter/return records surround each real read-only capture and link its
returned snapshot/capture IDs; source review establishes read-only coverage.
An observer does not recursively observe its own audit append. Audit counters,
call/actor bookkeeping and lifecycle observation arrays may be excluded from
functional snapshots only if no guard/scheduler/component reads them. Their
actual writes/calls remain accounted; this exclusion cannot hide functional
state or prove call occurrence merely by a summary count.

## 4 Independent literal expectations and call denominator

The checker contains a non-DUT literal table of the following cases and derives
due ticks with integer arithmetic. It never invokes IntegerScheduler,
EventSchedule, runner, loader or a component to generate expected results.

| Profile | Horizon/reset | Accepted base/due behavior |
| --- | --- | --- |
| S | 12/reset0 | P/A1..12; I/E/C2,4,6,8,10,12; original qx(0.1) on [2,10) |
| L1/L2 | 1200/reset0,1000 | P/A all ordinary ticks; due local even; C400 invalid_dt then exactly one corrected call; E800 stale then original same-sample correction |
| O1/O2 | 13/reset0,7 | P/A1..6,8..13; I/E2,4,6,9,11,13; C6 unexpected_tick without correction; ordinary7 rejects before components; reset7; C9/11/13 valid |
| E | 38/reset0 | P/A1..38; I/E/C even2..38; fixed events below |
| T1/T2 | replay1002,1004 | E/C only, from L1 sealed actual inputs; same explicit reset epoch/time and initial state; evaluator copy differs |

For T the JSON `horizon_tick` is1004, `reset_ticks=[1000]`, and the only retained
boundaries are reset1000 and replay1002/1004 (local0/2/4), not a falsely complete
0..1004 base-grid stream. Only E/C component reset and replay calls occur there.
Each accepted replay controller return is followed by real session-local phase6
publication/held-state bookkeeping and its actual held-after value; this is not
another DUT call or an operation invented solely by the serializer.
P/A/IMU initial-input fields are retained declared context, never constructed or
consumed. The global reset order below applies to five-component profiles;
T's restricted order is controller then estimator. T truth-copy wire producers
are explicitly evaluator-owned and their `producer_field` identifies the
accepted fixed T definition/source locator.

T's actual sparse session next_global_tick is1002 after reset1000,1004 after
replay1002, and the terminal next marker1005 after replay1004. It is not an
assertion that omitted base boundaries1001/1003 were executed or retained.
Normal five-component sessions keep next_global_tick = completed_tick + 1.

Reset boundaries are reset-only. Reset phase order is controller, actuator,
plant, IMU, estimator. An ordinary boundary's order is P1,A2,IMU3,measurement
adapter3,E4,C5,publish6 on due ticks and only P1,A2 otherwise. L/E/N corrections
do not replay any earlier phase or resample IMU. O's rejected ordinary7 is a
probe before reset7, not a second completed boundary at global7.

E commands are ±x [2,4)/[6,8), ±y [10,12)/[14,16), ±z [18,20)/[22,24);
external torque[26,28), replacement bias[30,32), additive force[34,36).
Payload magnitudes and plant-only offset bind to exact accepted G0 JSON pointers
in the external/profile input manifest. All start-1/start/end-1/end sides,
including non-due boundaries, are observed. No runtime magnitude selection.

| Calls/objects per complete build | Exact expected count |
| --- | ---: |
| Live five-component profiles / E-C replays | 6 / 2 |
| Plant / actuator top-level step_base | 2472 / 2472 |
| IMU sample | 1235 |
| Estimator process attempts / accepted / rejected | 1241 / 1239 / 2 |
| Controller step attempts / accepted / rejected | 1241 / 1237 / 4 |
| P/A/IMU reset, each | 10 |
| E/C reset, each | 12 |
| P/A/IMU construction, each | 6 |
| E/adapter construction, each | 8 |
| C++ core construction, including loader temporary | 16 |
| Old-epoch role rejects / needs-reset rejects / N rejects | 5 / 2 / 2 |

Per-profile derivation is explicit: S12/6, each L1199/599 plus E/C one rejection,
each O12/6 plus C's one rejection replacing its ordinary success, E38/19, each
T two E/C calls. Counts use actual ordered call records and accepted flags, not
driver summaries. Loader/validator, guard, observer, serialization and delegated
subcalls have their own manifest/counters. A missing due call fails even if
reported totals were edited; fewer calls than a budget is not success.

The component counter keys are fixed as `plant_step_base`, `actuator_step_base`,
`imu_sample`, `estimator_process`, `estimator_accepted`, `estimator_rejected`,
`controller_step`, `controller_accepted`, `controller_rejected`, `plant_reset`,
`actuator_reset`, `imu_reset`, `estimator_reset`, `controller_reset`,
`plant_constructor`, `actuator_constructor`, `imu_constructor`,
`estimator_constructor`, `controller_adapter_constructor`,
`controller_core_constructor`, `old_epoch_rejected`, `needs_reset_rejected`,
`truth_negative_rejected`. Profile counters use the same names (zero where not
applicable); total counters are sums. Additional finite helper/subcall keys are
fixed in the accepted E2 manifest, not invented by raw. Probe
`component_call_delta` contains only the twenty component step/outcome/reset/
construction keys, all zero for pre-consumption rejects; reject/guard/logging
bookkeeping is separate, not a falsely nonzero component delta.

## 5 Full functional snapshots, reset and state preservation

Snapshots are value copies at distinct actual capture points. They contain the
fixed `session`, `plant`, `actuator`, `imu`, `estimator`, `controller` sections;
absent P/A/IMU in T are explicitly null. The observer and field map are bound to
the accepted exact source, not assumed compatible across later implementations.
Captures cannot be aliases of a live object or of each other.

Required mutable fields (semantic validation checks this field set in addition
to the schema's object shell):

| Section | Full functional observation |
| --- | --- |
| session | actual lifecycle, needs-reset, epoch/origin/next/last-completed/phase cursor and envelope_sequence; held/feedback/raw sample/adapted sample/estimate/command/plant/truth values; last and pending event/input/publication slots; live stored initialization/configuration values |
| plant | state q/rate/timestamp; _last_reset_epoch, origin, local_tick, mode; actual cached inertia/inverse and parameter binding |
| actuator | actual/target/request/status/command timestamp/current timestamp; reset flag, last-reset/origin/local_tick/mode; limits/time-constant and parameter binding |
| IMU | reset epoch, last sample timestamp, samples_emitted, seed; last-reset/origin/local_tick/next_sample_tick/reset flag; complete bit-generator state and parameter binding |
| estimator | estimate q/rate/timestamp/valid; reset epoch id/time; last_tick, seed and parameter binding |
| controller | actual public complete snapshot: reset, epoch_id, tick_index, epoch_origin_s, expected_timestamp_s, integral, D-filter, previous-rate/has_previous_rate, full expected held command and last diagnostics; adapter epoch, actual public adapter parameter values and actual core parameter-input binding |

The exact component snapshot keys use source attribute names listed in the
schema: no fuzzy aliasing. `parameter_binding_sha256` binds the accepted actual
constructor-input snapshot, not private core readback. G1 cached immutable values
are captured too, so before/after checks cannot miss an accidental cache write.
`_rng_state` is a read-only value copy of `_rng.bit_generator.state`; it is not
a new production field. Session slots carry full copied wire values, not just
references to mutable objects. The new session's canonical snapshot keys are
fixed in `session_snapshot` to cover the interrupted session's actual
functional_state keys, plus actual stored configuration values; the accepted
observer map binds each key to its real storage. Epoch/origin may be null in
the pre-reset NEW state. All actual functional storage must be covered; unknown extra
functional storage blocks static acceptance rather than being silently ignored.

G1/E parameter value bindings in a capture are recomputed from the actual public
parameter values at that capture and matched to the observed constructor/input
binding; a cached initial digest alone cannot hide a later value mutation.
Controller `adapter_parameter_values` is the actual public `adapter.parameters`
value map (the adapter reads its limits); compare it exactly to its accepted
constructor-input map. It is separate from the unavailable private core getter.
Do not claim that observing mutable adapter input parameters reads back the
core's private copied parameters. The core binding remains actual constructor
input plus static copy-path evidence.

Only external append-only audit/counter bookkeeping is excluded from the state
equality comparison; it is separately counted and cannot influence scheduling,
guard decisions or algorithms. An actual mutable field not covered above must
be declared before runtime; missing state observation is not proven atomicity.

The shared guard may read only the immutable input envelope's recorded role,
epoch and producer token, active epoch/lifecycle, and the immutable accepted
allowed-producer table. It must not consult mutable audit records, lifecycle
observation arrays, record registries or self-declared pass flags to authorize
consumption. Actual role/producer/local_tick/parent IDs are retained in each
wire; provenance labels alone still do not prove the N derivation. The current
finite session design has no guard-authorizing mutable registry; adding one
requires an explicit typed functional snapshot and non-author review, not an
unobserved object graph. Snapshot actual lifecycle/mode wherever it gates
execution, not only the derived needs_reset boolean.

Snapshot encoding uses the same float rules and exact JSON structure. For
pre-consumption N/old-epoch/needs-reset rejects, complete before/after functional
values compare exactly. For real L component rejects, complete target component
state and uncommitted input/session slots compare exactly. O6 likewise requires
unchanged complete component states; its one permitted session-state transition
is the single specified transition represented by both
`lifecycle: active -> needs_reset` and `needs_reset: false -> true`, with all other functional fields
unchanged across that rejected call. This is not a blanket rejection rollback:
the session must actually enter needs-reset. No tolerance, repr, object address
or just-q shortcut. Earlier accepted P/A/IMU/E work on an invalid C boundary is
not rolled back or mislabeled unchanged from boundary start.

RNG state is copied read-only from the actual version-bound bit generator.
Capture must not draw/advance/reseed. No invented scalar-draw counter. On reset,
sample count0, last sample null, next_sample_tick2; first two public emitted
counts1/2. O's identical initial/reset-local inputs must match the first two raw
IMU vectors before/after reset, with timestamps mapped to local time. L/O twins
independently reproduce the same matching streams.

O must show nonzero pre-reset controller/actuator functional state and held
publication history under its fixed nonzero reset-local command. Noise alone or
an unactivated reset branch does not prove reset coverage. Missing activation
is a failed coverage obligation, not a reason to tune parameters automatically.

The controller has no private core-parameter getter. Retain the actual parameter
object supplied to that same constructor plus the accepted static copy path.
Call this constructor-input/static-copy evidence, not a private core readback.
An actual readback claim requiring an unavailable interface remains NOT_READY.

## 6 Epoch/invalid probes and recovery

Exactly five old-epoch probes target separate runner-held roles: held torque,
feedback, IMU, estimate, attitude command. Each probe preserves the actual older
envelope, records a concrete consumer/site and occurs before the same normal
consumer path. The shared guard rejects `stale_epoch`, complete functional
snapshot is unchanged and component-call delta0; then the original legal input
is consumed at that still-unconsumed tick. Five labels checked by a separate
test-only branch are not equivalent to five guarded consumers.

The five anchors are L1 after reset1000: held torque at1001 before actuator
phase2; IMU at1002 before E phase4; feedback, estimate and attitude command at1002
before their C phase5 consumption. Each stale candidate is the real retained
L1 pre-reset role value (last available value at/before998), with its original
epoch/time, not a current payload merely relabeled old. The original legal role
values remain intact. Guard checks run before adapter re-encoding/retagging.

Exact component reasons are `invalid_dt` for L400 C,
`imu sample timestamp is duplicate or stale` for L800 E, and `unexpected_tick`
for O6 C. Original component strings are not replaced with new categories.
The session's ordinary7 rejection reason is `needs_reset`.

L400 changes only dt to negative approved period, then one correction of that
same call's inputs/dt. L800 copies the actual newly sampled IMU with the previous
accepted timestamp, then uses the original new sample once. C O6 changes the
actual timestamp input to the declared future tick while retaining dt0.005,
does not make the normal C6 call, and recovers only by the reset7 transaction.
Before/after snapshots and every actual input/exception/result are retained.

## 7 Truth boundary: shared real guard, N and T

The runtime guard is the same implementation invoked before every normal,
invalid/retry and replay E/C input consumption, and before runner-held role
consumption. Store its actual site/call ID, input ref, role, source path,
accepted/reason and linked consumer operation; static source review verifies
coverage of all actual branches. Accepted normal inputs cannot bypass the guard.
Guard logs alone do not prove coverage without that static/run correspondence.

A normal guard record includes `checked_refs` with every actual input in its
bundle (C: attitude_command/estimate/feedback; E: adapted_imu). Its single
`guard_ref` can therefore identify one common guard invocation without pretending
one role covers three. Old-epoch/N records use the same guard with the candidate
substituted in that actual bundle and retain the original legal ref. Other
roles checked there must remain unchanged. A normal guard may have
`candidate_ref = null`, `role = "input_bundle"`; a rejecting role probe has its
concrete candidate/role and snapshot pair. Actual invocation counts are in E2.

N_E attaches to L1 global1002 before phase4: isolated IMU candidate's gyro comes
from the actual evaluator-owned truth omega; other IMU fields stay legal.
N_C attaches before phase5 there: isolated estimate candidate's quaternion comes
from the actual evaluator-owned truth quaternion; other estimate fields stay
legal. N records the actual full candidate payload, original legal ref,
evaluator truth ref, source field, target field and derivation site/call ID.
The checker independently verifies the copied payload/field equality, not just
an `origin=truth` flag. This path must reach the shared normal guard and reject
`truth_dependency_forbidden` before DUT consumption, with unchanged full state
and zero component delta, then consume the original legal object. N does not
construct/reset/step any extra DUT or feed contamination to a component.

An ordinary IMU is allowed to be generated by plant truth through the approved
sensor boundary; do not reject that legitimate ancestry. Evaluator-owned direct
derivation into E/C is forbidden. Explicit G0 initialization is allowed only
from the declared input, never inferred from current truth.

T1/T2 reset new E/C with L1's explicit initial state at its post-reset epoch/time
and replay L1's actual1002/1004 IMU/attitude/feedback inputs unchanged. Only the
separate evaluator-owned truth copy differs. All legal E/C inputs, accepted
diagnostics/outputs and torques compare with L1 and each other under section9.
No P/A/IMU, new noise or alternate initial state. This is finite fixed-input
invariance, not a proof against all possible hidden truth dependence.

## 8 Events, hold and pairing checks

Derive active events from literal integers, not DUT labels. The independent
axis quaternion uses scalar half-angle sin/cos and scalar-first Hamilton
composition; use the fixed sign/axis and approved composition order. Check
plant-only offset against the approved input; estimator reset stays identity.

For a phase2 interval ending at k, record `[k-1,k)`, held publication source,
request/limited/status, original command timestamp, actual torque and current
feedback timestamp. The held command must be published strictly before k.
At local1/2 hold reset; publish2 reaches3/4; publish4 reaches5/6. Status equals
strict `abs(request)>limit` per axis, and limited target equals the approved
controller limit operation; no actuator re-clamp or fabricated timestamp refresh.
Any unavailable independent request/limit observation is NOT_READY.

Plant phase1 consumes previous actual plus the independent external torque,
with those three vectors separately retained. Bias replacement is exactly
`(raw - nominal_bias) + replacement` per field, preserving actual noise/time.
Additive force changes only that vector. Event metadata is not an E/C field.
This verifies event adapters and data semantics, not independent plant/PID physics.

## 9 Comparison policies and meaning

Policies are predeclared for numerical implementation consistency, not physical
uncertainty, sensor specification, closed-loop performance or a derived global
forward-error bound. Failure is retained; values are not relaxed after inspection.

Exact IDs/order/counts mean the exact expected logical identity for the current
profile, not equality of intentionally distinct instance/profile names. Within
a record, references/copy pairing/snapshot preservation use the actual IDs
exactly. Across L1/L2 or O1/O2, match component streams by declared profile pair,
global/local tick, epoch mapping, phase, owner/method/attempt ordinal and role;
retain and validate each side's actual IDs/producer links. L1-only N/old-epoch
audit probes and their correctly declared envelope-sequence effects are not
silently demanded from L2. They remain independently checked with exact per-
profile counts; compare the real matching component inputs/results/reset/RNG
streams, not whole raw byte dumps. Across builds compare the same named profile
and logical records; each build identity/instance binding is validated first.

| Relation / fields | Policy / basis |
| --- | --- |
| Tick, epoch, phase, IDs, order, reasons, validity, flags, counts, seed | exact typed equality; integer S0/actual public contracts |
| Same payload copied/held/paired; protected rejection-snapshot state per section5; actual fixed-input T input copies | exact canonical value equality including q bit patterns: this is preservation of one value, not comparison of separately recomputed q |
| G3 timestamp vs independent origin+local*period | absolute1e-12 s as existing G1/G2 timestamp contract; integer identity also exact; never use this to accept a missing/off-grid integer call |
| Every separately recomputed quaternion component in L/O twins, reset replay, T outputs, event/offset calculation and S/L/O/E/T D/R, including nested snapshot q | absolute1e-12, rtol0, evaluated before any generic float/determinism rule; retain frozen G0/S0 component bound; no new bitexact q gate or unreported q/-q/sign normalization |
| S D/R every other finite float | `abs(a-b) <= 1e-12 + 1e-12*abs(b)` from accepted S0 G3-BIND; b is Release and units remain per field |
| L/O twins, reset replay, T separately computed non-q signal outputs within one build | exact canonical values where same explicit input/seed/source/order is required; q rule above takes priority and timestamps map by declared epoch/local tick |
| L/O/E/T D/R non-q computed signals | only the exhaustive path/unit whitelist below, absolute1e-12 in listed SI unit plus relative1e-12; numerical implementation consistency extension of S, not uncertainty, accuracy, stability or AW-efficacy evidence |
| Event raw-to-adapted additions/subtractions and plant torque addition | recompute the exact declared scalar binary64 operation order and compare canonical values exactly; no DUT event helper, no FMA/reassociation |

The proposed new D/R rows require explicit PA/non-author V1 policy acceptance
before they can be used. They are engineering consistency acceptance criteria,
not a theorem that accumulated L differences stay beneath them. No unspecified
float path inherits a generic tolerance: it is `comparison_policy_missing`
and blocks complete comparison. There is no other-dimensionless/unknown-field
fallback. Immutable copied params, source manifests, hashes and transport
metadata compare exactly. Recomputed snapshot signal values use the same
field-specific policy as their corresponding signal; rejection preservation
snapshots remain exact under the first relation rule.

Field selectors below are finite semantic path templates, not arbitrary recursive
key-name matching. `W(kind)` means `profiles[*].wires[*]` with that exact kind,
or the same typed full wire copied into a named session snapshot slot or
pending_inputs entry. `CS` means `profiles[*].snapshots[*].controller.snapshot`.
`PS/AS/IS/ES/SS` mean the correspondingly named snapshot sections. A copied
wire's payload remains the same fixed schema, not a new undeclared signal type.

| Non-q computed D/R paths (all vector/matrix components independently) | Unit / absolute bound, relative1e-12 |
| --- | --- |
| W(plant_state).payload.omega_b_rad_s; W(sensor_truth).payload.omega_b_rad_s; W(estimate).payload.omega_b_rad_s; W(imu).payload.gyro_rad_s | rad/s,1e-12 |
| W(sensor_truth).payload.translational_acceleration_n_m_s2; W(imu).payload.specific_force_m_s2 | m/s2,1e-12 |
| W(torque_command).payload.requested_torque_body_Nm, limited_torque_body_Nm; W(feedback).payload.actual_torque_body_Nm, limited_torque_body_Nm | Nm,1e-12 |
| profiles[*].boundaries[*].operations[*].scalar_inputs.total_plant_torque_body_Nm | Nm,1e-12; cross-build sum of each build's actual previous torque and copied external torque; each within-build addition is independently exact-order checked |
| W(controller_diagnostics).payload.rate_error_rad_s | rad/s,1e-12 |
| W(controller_diagnostics).payload.derivative_raw_rad_s2, derivative_filtered_rad_s2 | rad/s2,1e-12 |
| W(controller_diagnostics).payload.proportional_Nm, integral_before_Nm, derivative_Nm, integral_after_Nm, requested_Nm, limited_Nm | Nm,1e-12 |
| W(controller_diagnostics).payload.conditional_integral_rate_Nm_s, limit_backcalculation_rate_Nm_s, lag_backcalculation_rate_Nm_s | Nm/s,1e-12 |
| PS._state.omega_b_rad_s; ES._estimate.omega_b_rad_s; CS.previous_rate_rad_s | rad/s,1e-12 |
| AS._actual, _target, _requested; CS.integral_Nm; CS.expected_held_command.requested_torque_body_Nm, limited_torque_body_Nm | Nm,1e-12 |
| CS.derivative_filtered_rad_s2 | rad/s2,1e-12 |
| CS.last_diagnostics.<each explicitly named field in the four controller_diagnostics rows above> | same row/unit/bound; exact finite expansion, no additional field |
| PS._inertia_inverse | 1/(kg*m2),1e-12; same accepted NumPy/source inverse initialization, not an inertia-identification margin |

This table exhausts computed non-q signal fields. `estimator_diagnostics` has
only booleans/integers/reason, not a correction-norm float; no invented float
field is given a tolerance. Q selectors are W(plant_state/sensor_truth/estimate/
attitude_command).payload.q_nb, PS._state.q_nb, ES._estimate.q_nb, initial_inputs
plant_q_nb/estimator_q_nb/attitude_command_q_nb/reset_local_command_q_nb,
SS.configuration_values plant_q_nb/estimator_q_nb, and each
SS last/pending event state's command_q_nb. Recomputed axis/offset q in those
locations uses the q policy. Reset input q copied from the accepted input is
exact copy evidence; independently calculated expected q comparison uses the
q policy, not a second bitexact recomputation requirement.

Every actual timestamp path is explicitly time policy (absolute1e-12 s, no
relative term), except a copied/held/paired timestamp which must remain exact:
boundary epoch_origin_s/timestamp_s; W payload timestamp_s/command_timestamp_s;
scalar_inputs dt_s/timestamp_s; actor-specific reset epoch timestamps;
PS/AS/IS last-reset/origin/current/sample/command timestamps; ES._estimate and
ES._reset_epoch.timestamp_s; CS.epoch_origin_s/expected_timestamp_s and held
command.timestamp_s; SS.epoch_origin_s. Initial/configured time values and dt
copied from approved parameters compare exactly; their recomputed time-grid
comparison uses the time policy separately. Missing/null pre-reset values are
typed state, not floats to coerce.

All remaining finite float paths are exact copied configuration/data, explicitly:
parameter_objects.values in their typed g1/estimator/controller sets;
profiles[*].snapshots[*].controller.adapter_parameter_values;
initial_inputs non-q vectors/epoch_origin_s; event_inputs command_axes_rad/external
torque/replacement bias/additive force; operation scalar_inputs external
torque/acceleration under the exact scalar operation rule; actor-specific reset
initial-state vectors and epoch/seed input copies; PS._inertia;
AS._limits/_time_constant; SS.configuration_values non-q initialization vectors
and scenario_origin_s; and declared last/pending event payload magnitudes. Lifecycle
arguments/results reference those same typed copies. No hash byte string or RNG
integer state is parsed as a float. Any actual new path requires an explicit
accepted policy addition, not this paragraph's implied catch-all.

For new D/R rows retain the failing value, unit, absolute difference, permitted
bound, matching input/source location and policy ID. Positive separation for
the twelve data diagnostics is exact structural/identity/discrete/nonfinite
separation; those diagnostics do not rely on these floating policies.

## 10 Twelve single-defect diagnostics and rejection order

Use one sealed complete legal raw per build. Mechanical reserialization and
transport-hash/diff updates do not introduce a second semantic mutation. No
editing reported counts, references, payloads or immutable authority to hide
consequences. The following locator rules are deterministic and select the
first matching original record in profile order, boundary order, operation order.

| ID | One semantic mutation | Owning checker reason |
| --- | --- | --- |
| legal_control | unchanged bytes | pass / accepted |
| missing_due | remove S boundary2 accepted estimator operation, leave remainder | `missing_due` |
| duplicate_due | insert adjacent identical copy of that S operation | `duplicate_due` |
| phase_order | swap S boundary1 P/A operation positions, not their labels | `phase_order` |
| old_epoch | decrement epoch_id of L1 accepted1002 estimator IMU input envelope by1 | `stale_epoch` |
| feedback_pair | change S boundary2 feedback command_timestamp_s to the existing current boundary timestamp | `feedback_pair_mismatch` |
| wrong_source | replace identity.source_commit with another valid40-hex value | `source_mismatch` |
| wrong_module | replace identity.controller_module_sha256 with another valid64-hex value | `module_identity_mismatch` |
| missing_field | remove timestamp_s from S's first accepted IMU payload | `missing_required_field` |
| nan | replace the first gyro component of that payload with `nan` | `nonfinite_nan` |
| inf | replace the same component with `inf` | `nonfinite_inf` |
| frame | replace conventions.body_frame FRD with FLU | `frame_mismatch` |
| unit | replace conventions.angular_rate rad/s with deg/s | `unit_mismatch` |

The wrong-source/module alternate literal is deterministic (change the first
hex digit to0 unless already0, then1); the external expected identity is not
changed. Feedback pairing mutates only the feedback's paired timestamp, not its
own interval-end timestamp or the actual held command. All mutated paths must
exist and produce a real difference, otherwise generation is NOT_READY.

Semantic diagnostic precedence is fixed:

1. External authority shape/authenticity availability, bytes/hash, JSON syntax
   and duplicate keys; precise required-field/type failures (path retained).
2. Source/module/config/profile/env/F0 binding, frame/unit and nonfinite/canonical
   float checks, using their owning reason rather than generic schema failure.
3. Integer expected due multiplicities/order, reset-only and phase sequencing.
   Detect missing/duplicate due before orphan producer refs or derived count sums;
   inspect order before sorting or duplicate-ID postprocessing.
4. Input epoch, held/feedback pairing and guard/consumer semantics; stale epoch
   before its consequential guard/provenance disagreement.
5. Remaining producer references, event/payload/reset/recovery/snapshot/replay
   semantics, derived/reported counts and finite comparisons.

Thus a semantic mutation cannot be masked by its consequential missing-ref,
reported-count or checksum symptom. A schema implementation must map the known
required field/NaN/frame/unit case to its owning reason; it must not stop all
cases at a generic `schema_invalid`. Unknown malformed input still fails closed.
The complete legal control must pass, and each negative must reject for its
declared reason at the actual mutated/owning path. Data invalidity is not a
normal-scene performance failure.

The finite checker reason vocabulary, in addition to the owning twelve reasons
above, is: `accepted`, `authority_missing`, `authority_invalid`,
`transport_hash_mismatch`, `json_invalid`, `json_duplicate_key`,
`field_type_mismatch`, `unexpected_field`, `float_encoding_invalid`,
`config_identity_mismatch`, `profile_identity_mismatch`,
`environment_identity_mismatch`, `f0_identity_mismatch`,
`observer_identity_mismatch`, `parameter_identity_mismatch`, `partial_record`,
`missing_profile`, `duplicate_profile`, `profile_order`, `reset_only_violation`,
`clock_mismatch`, `initialization_mismatch`, `event_mismatch`,
`held_command_mismatch`, `producer_ref_missing`, `producer_mismatch`,
`guard_missing`, `guard_rejection_mismatch`, `truth_derivation_mismatch`,
`forbidden_truth_consumed`, `snapshot_incomplete`, `snapshot_changed`,
`invalid_recovery_mismatch`, `reset_mismatch`, `rng_replay_mismatch`,
`replay_mismatch`, `comparison_policy_missing`, `float_comparison_failed`,
`counter_set_mismatch`, `count_mismatch`, `probe_coverage_missing`,
`lifecycle_observation_missing`, `lifecycle_pairing_mismatch`,
`constructor_binding_mismatch`,
`build_identity_not_distinct`, `cross_build_identity_mismatch`, and
`unclassified_contract_violation`. Each rejection identifies the exact path and
expected/actual values; the last reason preserves an unexpected defect but can
never stand in for a required owning diagnostic. An unavailable authority,
observation or policy/partial execution is inconclusive; observed malformed or
semantically corrupt complete evidence is rejected, not a performance failure.

## 11 Original A mapping, stops and handoff

| Original group | This collection's independent evidence |
| --- | --- |
| G3-TIME | literal due/phase/reset oracle, all real boundaries, separate long/nonzero-origin scheduler nodes in the approved regression manifest |
| G3-INIT | explicit inputs, plant-only offset, reset snapshots and no tick0 integration |
| G3-HOLD | all publications and interval-end held/request/limit/status/pair/time |
| G3-EVENT | E nine half-open event intervals, signed axes and exact adapter transformations |
| G3-RESET | L/O live resets, full functional snapshots/RNG, five real old-epoch role probes |
| G3-INVALID | L actual two reasons/corrections; O missed tick, needs-reset and reset-only recovery |
| G3-TRUTH / G3-TRUTH-NEGATIVE | static allowlist/shared guard audit; actual N candidates; fixed-input T |
| G3-BIND / G3-REPLAY | accepted actual separate D/R module/F0, real S, L/O twins and T sealed replay |
| A-applicable G3-DATA / G3-EVIDENCE | exact closure/transport/observations, twelve owning diagnostics and independent recount |

Full G3-METRIC/G3-SCENARIO/8 scenes/37 criteria/50 ms remain later work. No
missing A observation is deferred just by calling it verification research.

Stop complete acceptance on any unknown identity/parameter binding, observer
field omission, unguarded branch, self-authorized raw, absent positive/negative
coverage, wrong source/module, missing/duplicate/reordered call, invalid accepted
input, state/RNG mutation on reject, incomplete reset, unapproved comparison
policy, unavailable raw, unknown process/consumption or mandatory skip/xfail.
Preserve exact failed/partial artifacts. The parent protocol controls diagnosis,
repair, source freezing and later finite runtime releases; this specification
does not independently grant any run/Git/CI/merge authority.

Current handoff is the stopped spec/schema bytes for TC interface alignment and
non-author static review. The checker is not yet implemented by this handoff.
