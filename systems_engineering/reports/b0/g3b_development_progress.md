# G3-B development progress — draft visibility snapshot

Date: 2026-11-16 (Australia/Perth).
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
comparison. Private RJ checks have received non-author delta reviews for sample
identity, failed extra-sample attempts, IMU-state continuity, timestamp-only
fault injection and same-tick retry binding. The public invalid-input route
remains closed until complete admission and joint RJ/RP evidence are accepted.

A synthetic-only development projection is being integrated to bind parameter
contents, observer-source descriptions, constructor identities and separate
main/twin reference domains. It is not an extension to the frozen runtime
schema, nor proof of real execution. Five component constructors must not be
misreported as six merely because six role identities exist.

Remaining gates are complete transaction/authority/reference checks, independent
oracle review, serializer size bounds, separately authorized data preparation,
finite test execution and non-author result review. No successful materialization,
RJ/RP test pass or complete eight-scenario/37-criterion result is claimed here.
The normal 50 ms saturation obligation is not resolved by synthetic tests.

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
