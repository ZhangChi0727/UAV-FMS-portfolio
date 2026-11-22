# EDGE track: learning modules

Goal: place vision-language and language-model inference across onboard, edge and
cloud resources for UAV bridge inspection, and measure the trade-offs by replay.
Requirements are in [requirements/edge.sdoc](../requirements/edge.sdoc).

No module below has code yet. A module is added with its tests and its
requirement status in the same change.

| Module | Learning goal | External interface | Internal logic | Requirements |
|---|---|---|---|---|
| M0 Environment and harness | Reproducible runs | config file, seed, run record | fixed versions, seeded runs, raw output files | EDG-REQ-0003, 0008 |
| M1 Instruction to task | Structured output from a language model | instruction text to task record (JSON schema) | constrained decoding or rule baseline; schema check | EDG-REQ-0001, 0010 |
| M2 Image to finding | Vision-language inference with abstention | image and task to finding (class, region, confidence, abstain) | model inference; threshold on confidence | EDG-REQ-0002, 0003 |
| M3 Profiling | Latency and memory measurement | model, precision, input to per-run timing and memory | warm-up, repeated runs, percentiles from raw data | EDG-REQ-0004, 0009 |
| M4 Placement policy | Deterministic placement under constraints | task, device profile, link state to placement | rule-based function compared with fixed and greedy baselines | EDG-REQ-0005, 0012 |
| M5 Fallback and replay | Behaviour under link loss and budget violation | event trace to logged decisions | injected events; seeded replay | EDG-REQ-0006, 0007 |

## Constraints

- Development PC only (Intel i9 CPU, NVIDIA RTX 4060 GPU). Every result is labelled
  with its host.
- Imagery is public or synthetic, with the licence recorded.
- The track does not depend on the B0 control modules (EDG-REQ-0011).

## Learning card: M0 run records and hashing

Code: [m0/run_record.py](m0/run_record.py). Tests: `cd edge_inference/m0 && python -m pytest -q` (40 passed on the development PC).

**External interface**

| Function | Input | Output |
|---|---|---|
| `build_run_record(**fields)` | model, precision, library versions, device, code revision, config hash, seed, host, raw artifact path, analysis command | validated dict, or `RunRecordError` |
| `config_hash(config)` | mapping | SHA-256 of canonical JSON |
| `event_log_hash(events)` | list of event dicts | SHA-256 after removing `run_id` and `wall_clock_s` |

**Internal logic**

1. Canonical JSON: sorted keys, no whitespace, NaN rejected. Equal content gives equal bytes.
2. Validation: every required field present and non-empty; `host_type` must be `development-host`; `seed` must be an integer (not a bool).
3. Normalisation: only the two named keys are dropped. Any other change, including event order, changes the hash.

**Requirement coverage**

| Requirement | Where it is enforced | Test |
|---|---|---|
| EDG-REQ-0003 | required model, precision, library, device fields | `test_each_required_field_is_enforced` |
| EDG-REQ-0008 | code revision, config hash, seed, host, artifact, command | same, plus empty-field test |
| EDG-REQ-0007 | `normalise_event_log`, `event_log_hash` | `test_wall_clock_and_run_id_do_not_change_hash`, `test_reordered_events_change_hash` |
| EDG-REQ-0009 | `ALLOWED_HOST_TYPES` | `test_non_development_host_is_rejected` |

**Exercise (hand calculation)**

Given events `[{"run_id":"a","wall_clock_s":1.0,"event":"submit"}]` and the same list with `run_id` `"b"` and `wall_clock_s` `7.5`, the normalised logs are identical, so the hashes are equal. Change `"event"` to `"discard"` and the hash changes. Explain why `run_id` is removed but `event` is not.

**Not covered by M0**: no model is run, no timing is measured, and no result exists yet.

## Learning card: M1 instruction to task

Code: [m1/](m1/) (`task_schema.py`, `rule_parser.py`, `evaluate.py`). Tests: `cd edge_inference/m1 && python -m pytest -q` (50 passed on the development PC). Data: `m1/data/` with a hash manifest (`MANIFEST.json`).

**External interface**

| Function | Input | Output |
|---|---|---|
| `parse_instruction(text)` | one instruction string | `ParseResult(status="task" or "rejected", task, reason)` |
| `validate_task(task)` | task mapping | list of violations; empty means valid |
| `score(items, parse)` | dataset items and a parser | status accuracy, per-field accuracy, schema violations, raw outputs |

**Internal logic (rule baseline, fixed order)**

1. Civil-scope refusal first (EDG-REQ-0010). Any non-civil term rejects the instruction.
2. Target element by priority: abutment, bearing, girder, pier, deck. "Bearing" precedes "pier" so "bearings on pier 1" is a bearing task.
3. Defect classes: every matching keyword, sorted by the rule table. No match rejects the instruction; the parser never guesses.
4. Location: abutment, then pier number, then span number, else `unspecified`.
5. Views: every matching keyword; if none, `overview` is set and this default is recorded as a rule.
6. The result is validated against the schema before it is returned. A failure becomes a rejection, so the parser never emits an invalid task.

**Requirement coverage**

| Requirement | Where | Evidence |
|---|---|---|
| EDG-REQ-0001 | schema and rejection path; per-field scoring with raw outputs and violation counts | `test_task_schema.py`, `test_evaluate.py` |
| EDG-REQ-0010 | vocabularies contain only civil bridge terms; civil refusal is first in the rule order | `test_non_civil_class_cannot_be_represented`, `test_civil_refusal_comes_first` |
| EDG-REQ-0015, 0028 | manifest verification before scoring | `test_manifest_detects_changed_file` |

**Result and its limit (read before quoting)**

- Development set (12 items): status 1.0; field accuracy 1.0 for all four fields; 0 schema violations.
- Held-out set (8 items): status 1.0; field accuracy 1.0; 0 schema violations.

These numbers are not evidence of generalisation. Both sets were written by the same author, in the same phrasing style, while the rules were being written, and the held-out set is only eight items. The result shows that the rules match the author's own sentences. A fair test needs instructions written by someone else, in varied wording, and scored once.

**Exercise (hand calculation)**

Trace "Examine the girder of span 1 for cracks; underside view required." through the rules. Why does `side_view` not match? Why is `required_views` `["underside"]` and not `["overview"]`? Then find one sentence the rules would wrongly reject and explain which rule causes it.

**Not covered by M1**: no language model, no image, no latency, and no external instruction set.
