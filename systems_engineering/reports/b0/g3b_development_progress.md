# G3-B development progress — draft visibility snapshot

Date: 2026-11-17 (Australia/Perth).
Base: `3dc9050da9bc4cd79ce19f751a05419117e9b286` (merged PR #23).
Status: **work in progress; not G3-B acceptance and not ready to merge**.

## Purpose and boundary

G3-B is the independent metric/evidence evaluation increment following G3-A.
This documentation-only snapshot makes locally reviewed progress visible while
implementation and independent synthetic test data remain under review.
It changes no executable source, workflow, frozen requirement, parameter,
scenario, tolerance or seed. It does not start G3-C or authorize merge.

## Completed finite work

The project retains separately sealed, locally executed test batches:

| Batch | Accepted finite result | Limitation |
| --- | --- | --- |
| XD01 | 25 selected metric/comparison tests | Historical exact source and synthetic inputs only |
| XD02 | 15 selected axis/saturation/replay tests | Historical exact source and synthetic inputs only |
| Ordinary L1 | 10 selected tests | Ordinary-parent subset, not all scenarios |
| LI L1 | 7 selected tests | Synthetic LI parent/mutation subset only |

These are separate batches, not one combined run. Their acceptance does not
transfer automatically to the current modified evaluator. Local raw inputs,
JUnit, manifests and logs are retained but are not published with this snapshot;
remote readers cannot independently reproduce these claims from this PR alone.
A future source/evidence delivery must provide portable bindings and suitable
artifact access before claiming reproducible CI coverage.

For the accepted LI batch, retained SHA-256 identifiers are:

- Source metrics: `8CBC20F98D8A1B4B47B4FB96A7745690221E0B43A522225708A64CCF7458E2A3`.
- Test source: `9EB9E176E8DD56513E604E6209501759BA98C405463A0A8009D9DECDCD3E6885`.
- Launch manifest: `0C3F22214A6A1E56AF369601018C8121122AEF00A23CB0FE918A28111C753CE5`.
- JUnit: `7127CC2F79956A2FCF79F11F6529D4E62BFC13461873DDC6D15ADF768C59AAE8`.

## Current RJ/RP work

RJ covers rejected-input transactions and recovery; RP covers reset/replay
comparison. RJ/RP preparation attempt 04 has received PA acceptance following
non-author source, serialization-size and artifact review. Its correction makes
boundary envelope inventories follow canonical port-key order with matching
source references and stable de-duplication. Independent expected values,
tolerances, production parameters, frozen contracts and data-size limits are
unchanged.

All earlier failed or partial preparation and test attempts remain retained.
They have not been overwritten or retrospectively accepted.

Attempt 05 completed its sole released run with all nine prescribed nodes
passing, zero failures/errors/skips and no xfail/xpass. PA accepted this finite
batch after non-author artifact, source and execution-receipt review. Earlier
failed attempts remain retained. The retained JUnit SHA-256 is
`02BF65A4D75A3B80052C722615218D2A0A3A8E74487BD04ECE13717AA2A23208`.
The review does not claim per-call dynamic counters absent from the logs.

These synthetic verification inputs do not prove real component execution or
complete eight-scenario/37-criterion coverage. Nine-node acceptance is limited to this exact batch;
overall G3-B acceptance is not claimed. The normal 50 ms saturation obligation
remains separate.

The parallel research C1 finite check stage has separate acceptance. It is not
a G3-B prerequisite and does not close outstanding G3-B gates; subsequent data
generation and training are not authorized by that acceptance.

## Publication and next steps

This draft intentionally includes only this sanitized progress report. It
excludes unfinished source, workstation-bound test paths, generated bundles,
private logs, research data and unrelated user edits. Detailed local reports
remain unchanged. Subsequent implementation publication requires an exact clean
source snapshot and portability/CI review; this draft is not that delivery.

Documentation validation is static text, evidence-identity and scope review.
No new model, test, build, simulation or seed run is performed for this snapshot.
The documentation commit requests CI skipping to avoid triggering the existing
unfiltered integration workflows solely for visibility. Skipped/pending checks
are not test evidence, and the draft must not be merged on that basis.
