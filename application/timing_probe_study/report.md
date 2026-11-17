Draft for author review; numbers pending author sign-off.

# Timing-probe effects on a host scheduler and transfer of a frozen gate: a measurement report

This note records retained host-bench counts for a timing-probe study and later transfer checks. It is a first-draft writing sample. It does not claim a new method, a solver contribution, or a property of any flight stack.

## 1 Problem

The engineering question is whether extra on-path recording (a probe that does work before an atomic publish) can change which sample a concurrent reader consumes, and whether that change can reverse a whole-window demand verdict on a scalar closed-loop model. A related question is whether a frozen, cheap prediction that uses only a measured gap on a lightly instrumented run, plus a calibrated net cost, can forecast the verdict of a paired run that actually performs the extra work.

Later packages ask a transfer question: given a frozen recording gate (record a pre-chosen consumed sample identifier only under stated queue and near-phase conditions), how often does that gate agree with an independent reconstruction on a different transport, and where does it false-accept?

The benches address those questions with synthetic phases and constructed loads. They are not a survey of natural miss rates. Queue layouts, message encodings, and public log timestamps are used as *workload generators* with cited engineering sources; this report draws no conclusion about PX4, any autopilot, or any flight target.

## 2 Test bench and measurement

All counts below come from Windows-host executions already retained under `research/*/evidence` (and, where named, `service/` and `holdback/`). Recapture, compiler, WSL, NATS, board, and overwrite-in-place report commands were not executed for the verification pass that produced the number table.

**Scheduler benches** (`research/paired_scheduler`, `research/scheduler_holdout`). A host C++ program runs concurrent publish and control work against a shared monotonic clock (QueryPerformanceCounter). Each run resets. Publish work copies and checks a diagnostic payload in pre-allocated memory, then publishes atomically. The control thread loads the sample identifier at its scheduled read and applies the control law of the measurement contract. Arm names distinguish extra frame work (off / light / stress on the paired bench; extra MAVLink ATTITUDE encoding on versus off on the holdout bench). Common timestamp probes are present on compared arms; the “baseline configuration” is extra-probe off with those common probes still enabled. Work duration is measured from actual execution; sleeps are not used to fake cost.

**Independent reconstruction.** A Python referee rebuilds sample choice from publish/read time *envelopes* and rebuilds the piecewise trajectory from applied controls and times only. It checks the implementation’s reported identifiers, controls, window minimum, and verdict. Overlapping or unseparated envelopes are retained as order-uncertain; identifiers are not used to invent order. The referee does not share the native dynamics implementation. It still shares the host clock and the logged sample points. There is no independent hardware observer.

[TO CONFIRM: the exact numeric demand predicate and model-time unit used by the independent reconstruction—the contracts state them, but those literals are not rows in the verified number table, so they are not copied into the counts below.]

**Holdout freeze.** The holdout package executes a previously frozen gap-prediction function on new strategies, payloads, and phases. Inputs to that rule are the lightly instrumented arm’s enclosing times and a scalar net-cost from an isolated calibration that does not use holdout verdicts, sample indices, or any field from the formal extra-work arm. Shared-queue versus split-queue dispatch is part of the design; shared dispatch runs both jobs to completion on one worker in release order (same-release publish first); split uses separate workers. MAVLink ATTITUDE encoding is an in-memory unsigned frame load, not a radio or onboard stream.

**Transfer benches.** `research/external_transfer` replays release times extracted from one public Flight Review log over an independent Linux/NATS loopback deployment (WSL). `research/pubsub_transfer` uses a separate PyZMQ XPUB/SUB TCP loopback implementation. In both cases, ULog or Flight Review times are replay markers for the bench; they are not treated as the original subscribers’ arrival times or as onboard control reads.

[TO CONFIRM: the precise JSON-to-contract map for labels `correct`, `false_reject`, `abstain`, `false_pass`, `VERIFIED`, and `AMBIGUOUS_ORDER`—this draft treats them as the audit counters named in `research/*/evidence/audit.json` and in the verification printouts, with `false_reject` read as “rule predicts violated while the reconstructed extra-work/low-perturbation arm is satisfied,” and `false_pass` as “rule predicts satisfied while the reconstruction is violated,” as written in the literature notes listed as sources.]

## 3 Paired experiment

Package: `research/paired_scheduler`. Design (contract): identical planned phases, initial state, control law, and payload algorithm on a pair; A is extra-probe off; B is the probe arm, except the sham condition which is off/off. Critical lead times were taken from a calibration that ignored per-arm warm-up runs and did not use demand verdicts to choose phase. Far-phase and sham cells are controls. All runs were retained. Phases were placed near a predicted critical delivery, so cell counts describe this design only.

Stored raw material comprises **228** runs = **36** calibration + **192** main (`analyze.py` skips calibration when scoring pairs). The pair table has **96** pairs (the analyzer fails if `len(details)` is not **96**). Scene groups are **12** groups with `all: 8` each.

Run-status counters on the retained audit are `VERIFIED` **214** and `AMBIGUOUS_ORDER` **14**. The **214** figure includes the **36** calibration runs; **214 − 36 = 178** main runs passed the uniqueness and numeric checks. Thus **178** of **192** main runs passed those checks, and **14** main runs were order-uncertain.

Unique-scene `sat_to_viol` counts: light.first **3**, light.second **7**, light.both **3**, and stress.first / stress.second / stress.both **8** each. Sum **3 + 7 + 3 + 8 + 8 + 8 = 37**. In those groups, `sat_to_viol` equals `verdict_flip`. [TO CONFIRM: whether `sat_to_viol` is defined only as a reconstructed satisfied→violated pair, versus any verdict change.] Direction: all **37** verified flips are satisfied → violated (off arm satisfied, probe arm violated). Far-phase groups (`*.early`, `*.late`) and sham groups have `verdict_flip` / `sat_to_viol` all **0**.

These counts support a *mechanism description on this host scheduler*: when extra work occupies the planned gap, the reader can consume an older sample and the reconstructed window demand can flip. They do not estimate how often that happens in unselected schedules.

## 4 Held-out evaluation

Package: `research/scheduler_holdout`. After freeze and calibration, **112** matched groups were run (the auditor raises if `len(records) != 112`). Each group has the AT/BL/AL/BT layout of the contract (fine-timestamp versus low-perturbation × extra encoding off versus on). The scoring target is the low-perturbation extra-encoding arm, reconstructed without reading that arm’s packet indices, predictions, or dense timestamps.

Frozen gap rule on `groups.all.gap`: **71** correct, **23** false-reject, **18** abstain (**23 + 71 + 18 = 112**). The same **71** / **23** / **18** split is the headline retained in the literature note.

A no-new-field policy that uses known shared-queue execution order scores `groups.shared.policy.correct` **56** (shared `two.correct` is also **56**). On the split queue, `groups.split.gap` is **51** correct, **3** abstain, **2** false-reject.

Read as an engineering comparison, not as a solver result: on this holdout set, naming the shared-queue completion order accounts for the shared subset without extra fields; residual errors and abstains remain on the split subset under the frozen gap rule. A dedicated solver is not claimed as a contribution.

## 5 Cross-source check (and pub/sub second bench)

### 5.1 Frozen gate on an independent source and deployment

Package: `research/external_transfer`. The frozen gate and scalar demand from the prior pub/sub holdback contract are applied without retraining. Score printouts used in verification: `primary.selective.correct` **192**; `challenge.selective.false_pass` **27**, `correct` **117** (**27 + 117 = 144**).

On the primary sample, `groups.primary.fifo` and `groups.primary.latest` each show `correct: 96` under the selective / baseline-none / one views reported in the number table, with no `false_pass` key—**0** / **96** false accepts per policy. On the challenge sample, **27** false accepts occur in **144** selected runs.

[TO CONFIRM: the operational meaning of `groups.*.selective`—this draft follows the literature note that each combination keeps the frozen gate’s chosen none or one arm per window, with independent replays per source window and policy.]

Periodic-service stress (same far-phase latest windows, subscriber service calendar restricted): `research/external_transfer/service/audit.json` `groups.none.all` **24**, `false_pass` **14** (the `one` arm is **12** / **24** `false_pass`). These **14** of **24** counts **match retained audit, not re-run**: the verification pass did not execute `service_report.py` because that script writes `research/external_transfer/service/audit.json` and would overwrite retained evidence.

The challenge and stress cells were constructed to hunt false accepts. They cannot be pooled with the primary sample to estimate a natural failure rate. The service calendar is an experimental receive-side constraint, not a statement about any vehicle configuration.

### 5.2 Pub/sub second bench (descriptive extracts only)

Package: `research/pubsub_transfer`. The following are extracted audit counts, not scored author claims.

| Extract | Value | Locator |
|---|---|---|
| Cost rows / pairs | **384** runs, **192** pairs | `research/pubsub_transfer/evidence/audit.json` `cost.rows` / `cost.pairs` |
| All windows, policy on none arm | **184** correct, **8** false_pass | `groups.all.policy_none` |
| All windows, policy on one arm (field masked) | **190** correct, **2** false_pass | `groups.all.policy_one` |
| All windows, one field open | **192** correct | `groups.all.one_field` |
| FIFO, policy none/one | **96** / **96** correct | `groups.fifo.policy_none` / `policy_one` |
| latest, policy none | **88** correct, **8** false_pass / **96** | `groups.latest.policy_none` |
| latest, policy one (masked) | **94** correct, **2** false_pass / **96** | `groups.latest.policy_one` |
| Holdback gated deployment | `total.selective.correct` **96**; selected arms one **34** / none **62** | `research/pubsub_transfer/holdback/audit.json` |

These extracts describe one loopback XPUB/SUB implementation under the frozen design. They are not used here to argue transfer success or failure.

## 6 Limitations

Windows host. No board execution used for these results. No independent hardware observer. Measurement windows were deliberately chosen near a critical phase so results cannot estimate a natural failure rate. Any dedicated solver is not claimed as a contribution. No novelty claim. No conclusion about PX4 or any flight target. The periodic-service stress result (**14** of **24**) was not re-derived in the verification pass (the generating script overwrites retained evidence) and must be labelled **matches retained audit, not re-run**.

Additional bounds already in the contracts: paired and holdout designs cannot freeze OS scheduling; arm-to-arm differences mix probe cost and rerun jitter; ULog/Flight Review timestamps are not network arrivals; WSL/NATS versus Windows/PyZMQ is a joint change of OS, broker, and receive path; host or simulator outputs do not meet the packages’ board-evidence conditions. Recapture was not run for this draft, so binary fingerprints and per-nanosecond traces are not re-collected here.

## 7 Reproduction

Read-only verification from the repository root. Use a virtualenv interpreter and do not point recapture at absolute toolchain paths. Placeholders: `<PYTHON>`, `<MINGW_BIN>`. Commands below match the package README blocks with those substitutions. They write under `build/` when `--output` is given, not over `evidence/`.

```powershell
<PYTHON> -B research/scheduler_holdout/reference.py
<PYTHON> -B research/scheduler_holdout/audit.py research/scheduler_holdout/evidence --output build/scheduler-holdout/reanalysis.json

<PYTHON> -B research/paired_scheduler/reference.py
<PYTHON> -B research/paired_scheduler/analyze.py research/paired_scheduler/evidence --output build/paired-scheduler/reanalysis.json

New-Item -ItemType Directory -Force build/external-transfer | Out-Null
<PYTHON> -B research/external_transfer/score.py research/external_transfer/evidence --output build/external-transfer/rescore.json

New-Item -ItemType Directory -Force build/pubsub-transfer | Out-Null
<PYTHON> -B research/pubsub_transfer/reference.py
<PYTHON> -B research/pubsub_transfer/audit.py research/pubsub_transfer/evidence --output build/pubsub-transfer/reanalysis.json
```

Do not run `research/external_transfer/service_report.py` or `research/pubsub_transfer/holdback.py score` against the retained trees: those paths write `service/audit.json` and `holdback/audit.json`. Do not run recapture (`g++` under `<MINGW_BIN>`, `scheduler.exe`, `plan.py` into a new directory, WSL `deployment.py`, `design.py`/`transport.py`, `holdback.py prepare`, `network_cost.py`) unless a new experiment tree is intended. Recapture, if ever repeated, would still be a Windows-host / loopback measurement, not board execution.

## 8 Number-to-source table

Every numeric token used as a result in Sections 3–6 (and the arithmetic that the number table already records). Paths are relative to the repository root.

| Number | Role in this report | Artifact | Re-derive command (read-only) |
|---|---|---|---|
| 228 | stored runs (calibration + main) | `research/paired_scheduler/evidence/audit.json`; length check in `research/paired_scheduler/analyze.py` | `<PYTHON> -B research/paired_scheduler/analyze.py research/paired_scheduler/evidence --output build/paired-scheduler/reanalysis.json` |
| 36 | calibration runs skipped by pair scoring | same; calibration skip in `analyze.py` | same |
| 192 | main paired runs (**96** pairs × A/B); also primary selective correct; pub/sub pairs; `one_field.correct` | `research/paired_scheduler/evidence/audit.json`; `research/external_transfer/evidence/audit.json` `primary.selective`; `research/pubsub_transfer/evidence/audit.json` `cost.pairs`, `groups.all.one_field` | paired `analyze.py`; external `score.py` on `research/external_transfer/evidence`; pub/sub `audit.py` on `research/pubsub_transfer/evidence` |
| 96 | paired pair count; per-policy primary `correct`; FIFO policy cells; holdback `total.selective.correct`; latest denominators | `research/paired_scheduler/evidence/audit.json`; `research/external_transfer/evidence/audit.json` `groups.primary.fifo` / `latest`; `research/pubsub_transfer/evidence/audit.json` `groups.fifo.*`, `groups.latest.*`; `research/pubsub_transfer/holdback/audit.json` | same family of auditors; holdback score **not** re-run (would overwrite) |
| 12 | paired scene-group count | `research/paired_scheduler/evidence/audit.json` `groups.*.all` | paired `analyze.py` |
| 8 | pairs per scene group; stress `sat_to_viol` per first/second/both; pub/sub `false_pass` on `policy_none` / latest none | paired `groups.*.all` and `groups.stress.*`; `research/pubsub_transfer/evidence/audit.json` `groups.all.policy_none`, `groups.latest.policy_none` | paired `analyze.py`; pub/sub `audit.py` |
| 214 | `run_status.VERIFIED` | `research/paired_scheduler/evidence/audit.json` `run_status` | paired `analyze.py` (print `Counter`) |
| 14 | `AMBIGUOUS_ORDER`; also service `false_pass` on none | paired `run_status`; `research/external_transfer/service/audit.json` `groups.none` | paired `analyze.py`; service **matches retained audit, not re-run** |
| 178 | main verified = **214 − 36** | derived from `run_status` + calibration skip | paired `analyze.py` |
| 3 | light.first and light.both `sat_to_viol`; split `abstain` | `research/paired_scheduler/evidence/audit.json` `groups.light.first` / `both`; `research/scheduler_holdout/evidence/audit.json` `groups.split.gap` | paired `analyze.py`; holdout `audit.py` |
| 7 | light.second `sat_to_viol` | `research/paired_scheduler/evidence/audit.json` `groups.light.second` | paired `analyze.py` |
| 37 | sum of unique-scene `sat_to_viol` | **3+7+3+8+8+8** on light/stress first/second/both | paired `analyze.py` |
| 0 | far/sham `verdict_flip` and `sat_to_viol`; primary false accepts per policy | paired `groups.light.early` / `late` / `sham`, `groups.stress.early` / `late` / `sham`; external `groups.primary.*` (no `false_pass` key) | paired `analyze.py`; external `score.py` |
| 112 | holdout groups | `research/scheduler_holdout/evidence/audit.json` (`groups.all.two.correct`; `groups.all.gap` **23+71+18**) | `<PYTHON> -B research/scheduler_holdout/audit.py research/scheduler_holdout/evidence --output build/scheduler-holdout/reanalysis.json` |
| 71 | frozen gap `correct` | `groups.all.gap.correct` | same |
| 23 | frozen gap `false_reject` | `groups.all.gap.false_reject` | same |
| 18 | frozen gap `abstain` | `groups.all.gap.abstain` | same |
| 56 | shared policy `correct` | `groups.shared.policy.correct` (also `groups.shared.two.correct`) | same |
| 51 | split gap `correct` | `groups.split.gap` | same |
| 2 | split `false_reject`; pub/sub masked-one `false_pass` | `groups.split.gap`; `research/pubsub_transfer/evidence/audit.json` `groups.all.policy_one`, `groups.latest.policy_one` | holdout `audit.py`; pub/sub `audit.py` |
| 27 | challenge `false_pass` | `research/external_transfer/evidence/audit.json` `groups.challenge.selective` | `<PYTHON> -B research/external_transfer/score.py research/external_transfer/evidence --output build/external-transfer/rescore.json` |
| 117 | challenge selective `correct` | same | same |
| 144 | **27+117** selected challenge runs | same | same |
| 24 | service `groups.none.all` (and `one` arm denominator) | `research/external_transfer/service/audit.json` | **matches retained audit, not re-run** |
| 12 | service `one` arm `false_pass` | same | **matches retained audit, not re-run** |
| 384 | pub/sub `cost.rows` | `research/pubsub_transfer/evidence/audit.json` | `<PYTHON> -B research/pubsub_transfer/audit.py research/pubsub_transfer/evidence --output build/pubsub-transfer/reanalysis.json` |
| 184 | `groups.all.policy_none` correct | same | same |
| 190 | `groups.all.policy_one` correct | same | same |
| 88 | `groups.latest.policy_none` correct | same | same |
| 94 | `groups.latest.policy_one` correct | same | same |
| 34 | holdback selected arm `one` | `research/pubsub_transfer/holdback/audit.json` | holdback score **not** re-run |
| 62 | holdback selected arm `none` | same | holdback score **not** re-run |

Self-check strings from `reference.py` (`gold reference self-check passed`, `independent reference self-check passed`, `physical projection self-check passed`) carry no extra numeric claims. Recapture, compiler, WSL, and board commands listed on the private number table were not executed.
