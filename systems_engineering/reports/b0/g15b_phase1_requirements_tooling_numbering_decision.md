# B0 G1.5-B phase-one requirements-tooling and numbering decision package

**Status:** candidate decision package, pending PA technical review and explicit
maintainer approval of the numbering rule. It is not a formal requirements
baseline or a joint-freeze record.

**Scope:** the G1.5-B phase-one comparison specified by
[the work order](../../../docs/work_orders/B0_G1_5_B_work_order.md): source
inventory, an isolated StrictDoc-versus-lightweight-text pilot, and a formal
numbering-rule proposal. This package neither changes nor claims execution of
G0 configuration, G1 behavior, acceptance thresholds, G2/G3 implementation,
or requirements coverage.

## Current structured-pilot increment — review pending

This document retains the historical StrictDoc-versus-lightweight comparison
below for traceability. Its statements that both documents are editable and
its provisional preference for a future StrictDoc source describe that earlier
comparison only; they are **not** a present source-selection approval.

The active G1.5-B structured phase-one increment uses
`tools/systems_engineering/g15b_pilot/contract/pilot_structure.json` as the
single editable pilot-record body and metadata source. It generates the
StrictDoc and Markdown reader projections and uses the separate editable
`model/b0_truth_control_slice.sysml` only for bounded model structure. The
choice is not forced by a StrictDoc field limitation: StrictDoc 0.30.1 supports
declared custom grammars and the retained probe successfully parses and renders
an `ACCEPTANCE` field. JSON remains the experimental source because its schema
and checker provide the current pilot's clearest cross-domain typing,
phase-one state locks, deterministic projections, and migration oracle.

This is a phase-one method experiment, not a maintainer-approved selection of
a formal future source. It adds a JSON Schema, deterministic projections,
AST-backed textual SysML checks, and an explicit source/field/relation contract
for comparison. Any later formal-source decision must weigh the JSON schema and
generator maintenance cost, migration/import path, StrictDoc's retained native
hierarchy/rendering role, tool coverage, and maintainer workflow—not merely the
convenience of this fixture. No formal ID, source migration, freeze, or
implementation claim is authorized by this increment.

## Review boundary and protected inputs

| Item | Value or source | Treatment in this package |
|---|---|---|
| Review base | main `37d623a639e81c17933b7863b2634a948df82137` | The phase-one branch is compared with this merged G1.5-A baseline. The PR head is supplied separately for PA review; this report deliberately does not self-hash a future review commit. |
| G0 v2 configuration | `05_integration/b0/configs/b0_g0_contract.v2.json`, Git blob `1beff6e6a9a81d0ab92b2059a93207ffed9d291d` | Approved parameter/acceptance contract; field-referenced only. |
| B work order before protection | Windows byte SHA-256 `b5348bec9509e6ab68ff06185507ebc4d02074449fe81c526fc217339f51fcd6` | Preserved unchanged at `docs/work_orders/B0_G1_5_B_work_order.md`; execution authority, not a requirement source. |
| Candidate records | `tools/systems_engineering/g15b_pilot/` | Exactly five `PILOT-ONLY-*` comparison records; isolated fixtures, not authoritative requirements. |

The protected work-order stash is retained in addition to the committed,
byte-preserved work-order file. Generated StrictDoc output is not committed.

## Source inventory and applicability

A locator can inform a later approved source but does not itself become a
requirement. Implementation/tests are evidence or context, never the sole
authority for a new obligation.

| Source | Relevant locator(s) | B0 role | Phase-one treatment |
|---|---|---|---|
| Project charter | `systems_engineering/project_charter.md#purpose`, `#product-boundaries`, `#success-and-stopping-rules`, `#change-decision` | User need, boundary and change decisions | Candidate top-level need/exclusions. |
| Development baseline | `systems_engineering/development_baseline.md#single-objective`, `#included`, `#excluded-from-b0`, `#delivery-gates` | Active B0 scope/delivery boundary | Candidate applicability, not numerical authority. |
| Approved G0 v2 contract | `05_integration/b0/configs/b0_g0_contract.v2.json#/conventions`, `/timing`, `/interface_contract`, `/initialization_contract`, `/plant_contract`, `/actuator_contract`, `/imu_contract`, `/controller_contract`, `/operating_envelope`, `/acceptance_policy`, `/scenarios` | Approved convention, interface, state/reset, parameter and scenario contract | Field locators only; no duplicated thresholds or performance claim. |
| G0 approval decision | `systems_engineering/reports/b0/g0_approval_decision.md#决定` | Current-B0 `CTL-REQ-001`/`CTL-REQ-002` disposition | Legacy candidate records the decision without editing/reusing either ID. |
| Legacy requirements | `systems_engineering/requirements/legacy_requirements.md#control-requirements` | Historical NAV/CTL/FDI wording/identifiers | Preserve IDs/thresholds as legacy references only. |
| G0 acceptance matrix | `systems_engineering/verification/g0_acceptance.md#ctl-req-适用性审查` | Acceptance planning and historical applicability summary | Inspection-plan locator only; conflict recorded below. |
| G1 work order/component tests | `docs/work_orders/B0_G1_work_order.md`; `01_simulation/b0/tests/test_components.py` | G1 execution/evidence context | May support later evidence mapping, never sole requirement authority. |
| A model views | `systems_engineering/models/system_views.md` | Existing view/element identities for context, allocation, interface and lifecycle | Pilot validates actual `view:element` references; it does not mint model IDs. |
| Architecture | `systems_engineering/models/architecture.md#modular-boundaries` | Boundaries, conventions and legacy EXT-NAV separation | Truth-isolation context; navigation remains outside B0 expansion. |
| Verification plan | `systems_engineering/verification/verification_plan.md#evidence-chain`, `#b0-checks` | Verification ownership/evidence chain | Each pilot record has a plan locator and unexecuted status. |
| Roadmap | `docs/roadmap.md` | Scope order and gate ownership | Context only; never a new obligation source. |

### Recorded conflict, not repaired in phase one

`systems_engineering/requirements/legacy_requirements.md` and the current
summary in `systems_engineering/verification/g0_acceptance.md` retain wording
that says CTL applicability review is pending. The approved G0 v2 contract and
`g0_approval_decision.md` instead record `CTL-REQ-001` and `CTL-REQ-002` as not
applicable to current B0. Phase one does **not** alter historical wording,
thresholds, or identifiers. A later approved baseline must record the decision
locator and reconcile its reader-facing summary without rewriting history.

## Isolated five-record comparison fixture

Both editable formats live in `tools/systems_engineering/g15b_pilot/`, outside
the future authoritative `systems_engineering/requirements/` location. They
represent exactly the same five records and the thin checker fails on drift.

| Temporary key | Representative purpose | Truthful status |
|---|---|---|
| `PILOT-ONLY-NEED-01` | Bounded B0 use/boundary and root relation | candidate only; planned/not run |
| `PILOT-ONLY-INTERFACE-02` | Runtime truth isolation, field locators and interface model element | candidate only; planned/not run |
| `PILOT-ONLY-ACCEPTANCE-03` | Versioned G0 acceptance-field reference without copied numbers | candidate only; planned/not run |
| `PILOT-ONLY-LEGACY-04` | Legacy CTL disposition and approval locator | candidate only; planned/not run |
| `PILOT-ONLY-G2-05` | Planned controller allocation/interface and planned verification obligation | candidate only; planned/not run |

Each fixture has a temporary key, level, title, single statement, parent,
source locator, rationale, applicability, scope, allocation, `view:element`
model reference, verification-plan locator, acceptance condition, evidence
status and `candidate_only: true`. The legacy record also requires an approval
reference.
No fixture enters coverage accounting or claims implementation/verification.

## Tool and source-format trial

| Criterion | StrictDoc native `.sdoc` | Lightweight Markdown `.md` | Project boundary |
|---|---|---|---|
| Offline editing/review | UTF-8 text without a tool | UTF-8 text without a tool | Neither is generated or a database export. |
| Key/hierarchy | Native `UID` plus `Parent` relation | Heading/key plus `Parent` field | Thin checker rejects duplicate/broken temporary relations. |
| Rendering | Native HTML export to a temporary directory using the source-owned `strictdoc_config.py` and `presentation.css` | Directly reviewable text; no second renderer | Generated HTML is not committed or evidence of satisfaction. The native export copies the CSS as `html/_static/custom.css`; generated output is never hand-edited. |
| Project-specific fields | Declared custom grammar fields are supported; the retained `ACCEPTANCE` probe parses and renders. The main generated projection deliberately uses the default grammar. | Explicit labeled fields | The JSON-led pilot checker owns applicability/scope, approval reference, locators, typed model/development/verification relations and phase-one state locks. |
| Type/relationship expressiveness | Custom fields and native relations are available, but the trial has not designed a complete SDoc grammar for all cross-domain objects. | Labels require a separate checker and convention. | JSON Schema plus semantic checks currently provides the most explicit bounded contract. |
| Generator/schema maintenance | A source-led SDoc design could reduce one projection but would require a reviewed custom grammar/import and equivalent project checks. | Low rendering cost but project semantics remain external. | JSON-led operation pays generator/schema cost and byte-drift checks. |
| Recovery/drift | Plain text and native export are recoverable; a future SDoc-led migration must prove round-trip and relation preservation. | Plain text is recoverable; semantics depend on checker. | Current JSON source regenerates both reader formats and fails closed on drift. |
| Git review | Plain-text diff | Plain-text diff | Five equivalent records only; not a full-baseline migration proof. |
| Future migration | Plain-text source with rebuildable native output | Plain-text source | A later approved import is one-way and reviewed into one chosen source. The twin remains only as a fixture/conclusion. |

The native command is deliberately described narrowly: `strictdoc export` is a
parser/export exercise, not an all-purpose project requirement validator.
Duplicate keys, broken parents, unknown model elements, required fields, the
fixed CTL applicability decision, JSON pointers (including array-index form),
Markdown anchors and cross-format drift are tested by the dedicated thin
checker and its negative fixtures.

### Tool provenance and reproducibility record

| Item | Recorded value |
|---|---|
| Evaluation date | 2026-10-12 (Australia/Perth) |
| Operating environment | Ubuntu 20.04.6 LTS under WSL; isolated temporary venv only |
| Base interpreter | `/home/chi/src/uav-fms-portfolio/.venv-b0/bin/python` (Python 3.11.17), used only to create the evaluation venv; `.venv-b0` is not modified |
| Evaluated package | `strictdoc==0.30.1` in `/tmp/uav-fms-g15b-strictdoc`, installed from `requirements/g15b-pilot.txt` |
| Official references checked | [StrictDoc user guide](https://strictdoc.readthedocs.io/en/stable/stable/docs/strictdoc_01_user_guide-TABLE.html), [project repository and Apache-2.0 license](https://github.com/strictdoc-project/strictdoc), [evaluated PyPI release](https://pypi.org/project/strictdoc/0.30.1/) |
| Version discrepancy retained | Stable docs displayed a `0.30.2` Git-commit label on review date; the evaluated PyPI package/CLI is `0.30.1`. All capability claims here refer only to the observed `0.30.1` CLI. |

### Observed execution evidence

The following were actually run from the WSL checkout after the PA rework of
the trial source, checker and isolated test placement, before its response
commit. The remaining evidence-report text does not alter those executable
assets; the PR handoff supplies the final reviewed head and CI reruns the same
scoped commands there.

```text
/tmp/uav-fms-g15b-strictdoc/bin/strictdoc --version
# exit 0; output: 0.30.1

/tmp/uav-fms-g15b-strictdoc/bin/strictdoc export \
  --config tools/systems_engineering/g15b_pilot/strictdoc/strictdoc_config.py \
  --formats=html \
  --output-dir /tmp/uav-fms-g15b-html-current --no-parallelization \
  tools/systems_engineering/g15b_pilot/strictdoc
# exit 0; generated .../html/strictdoc/b0_phase1_pilot.html

/tmp/uav-fms-g15b-strictdoc/bin/python tools/systems_engineering/check_g15b_phase1_pilot.py
# exit 0; G1.5-B phase-one pilot check passed (5 non-authoritative records)

/tmp/uav-fms-g15b-strictdoc/bin/python -m pytest -q \
  tools/systems_engineering/g15b_pilot/tests/test_g15b_phase1_pilot.py \
  tools/systems_engineering/g15b_pilot/tests/test_g15b_native_strictdoc.py
# exit 0; 25 passed (timing recorded in the PR validation evidence)
```

The native test suite proves that the evaluated StrictDoc CLI accepts and
renders the retained declared `ACCEPTANCE` custom field, and rejects a
duplicate temporary UID and a parent relation targeting an absent temporary
UID; the thin checker separately proves the project-specific failures. The
rendered HTML contained all five trial records, `planned/not_run`, and a
resolved Git version/branch macro. A pre-commit render showed
`56fe38b (Git branch: codex/b0-g15-requirements)`, which is correctly only the
last committed state at that moment; it must not be mistaken for a hash of
uncommitted source. The CI test asserts that the macro is resolved, and the PR
head/CI run are the authoritative final render identity.

### Execution provenance for PA recheck

The local source checkout used for the recheck was Windows
`E:\\Project\\uav-fms-portfolio`, mounted in WSL as
`/mnt/e/Project/uav-fms-portfolio`. Its recorded `git rev-parse HEAD` before
the rework response was
`7d486b1b417cd1a93f63a75f1ef496f9b411a9ce`. The scoped commands ran after
`cd /mnt/e/Project/uav-fms-portfolio`; source and test paths therefore resolved
from that checkout. The similarly named `/home/chi/src/uav-fms-portfolio`
checkout observed by PA remains at `56fe38b7…`; it was not the source under
test and supplied only the pre-existing `.venv-b0` interpreter executable.
This path split explains the differing HEAD values without claiming that the
stale checkout executed this pilot.

The recheck command sequence included the G0 default/v1/v2 config CLIs, G0
and G1 track-local pytest/Ruff commands, the phase-one checker, the isolated
StrictDoc export, the two phase-one test modules, and `git diff --check`.
The exact commands and 25-test result are recorded in PR #16; the remote CI
run `38217640484` independently reran all six jobs at the reviewed head.

`strictdoc --help` exposed `export` but no native `validate` subcommand in
0.30.1. The direct trial inputs are pinned, while StrictDoc's large transitive
dependency closure is not a separately hash-locked file; that resolver surface
is a maintenance cost for a future approval decision, not hidden reproducibility
evidence.

### User-facing temporary preview, not a repository artifact

The source-owned `strictdoc_config.py` uses StrictDoc 0.30.1's native
`custom_css_path` support to load `presentation.css` after the bundled
stylesheets. It narrows the review layout to the content and five-entry
navigation on wide displays, places the reader-facing statement/rationale ahead
of the metadata panel, distinguishes the record comment as review detail, and
labels every record as `PILOT-ONLY`. These are presentation-only changes: the
five `.sdoc` records, their fields, hierarchy and generated relation links are
unchanged. The native test proves configuration linkage and asset copying, not
visual quality.

A fresh successful native export may be written outside Git to a uniquely named
`%LOCALAPPDATA%\Temp\uav-fms-g15b-strictdoc-preview-<head>\html\strictdoc\b0_phase1_pilot.html`.
It is a short-lived, local browser preview of the five `PILOT-ONLY-*` fixtures,
not a formal requirements view or retained evidence artifact. The native test
also asserts that all five generated anchors occur in the navigation and that
the four parent links target the declared parent records. Visual acceptance is
still a human review action: inspect the pilot banner, each statement and
review-detail panel, the navigation, and the four parent links in the local
preview before any phase-one approval. Recreate it with the documented
`strictdoc export` command and a local temporary output path; do not copy it
into the repository.

The browser-automation policy in this task rejects `file://` URLs, so the
executor did not bypass that protection or fabricate a browser screenshot.
Manual Chrome inspection remains the visual verification step for document
navigation, the five requirement bodies and native parent traceability links.
Any manual screenshot is user-supplied review evidence rather than a committed
project artifact.

## Proposed formal B0 numbering rule — not approved or instantiated

This proposal creates no numbered requirement. It only asks the maintainer to
approve or reject these rules:

1. Use one B0-only namespace matching `B0-REQ-NNNN`, a zero-padded,
   monotonically allocated four-digit ordinal. Type, level, component,
   lifecycle state and parent are fields, not identifier encoding.
2. Maintain one approved allocation registry in the chosen authoritative
   source. Allocation is sequential; assigned identifiers are never reused,
   including after deletion, withdrawal or deprecation. Intentional gaps retain
   their decision record.
3. A substantive normative change receives a new identifier and a `supersedes`
   relation. A non-substantive correction retains its identifier and records
   version/change rationale.
4. `NAV-REQ-*`, `CTL-REQ-*` and `FDI-REQ-*` remain historical. They can occur
   only as `legacy_ref` plus explicit applicability/disposition; never rename,
   alias, reallocate or include them in the B0 sequence.
5. `PILOT-ONLY-*` is permanently non-formal. An approved pilot idea receives a
   newly allocated formal candidate and may cite its origin; it is never a
   renamed or reused temporary key.

Until an explicit maintainer decision, phase two cannot select an authoritative
source, allocate formal IDs, import requirements, freeze a joint baseline, or
start C/G2/G3.

## Provisional recommendation, costs and stop conditions

**Current recommendation for PA review:** retain JSON-led operation for this
bounded experimental pilot only, with generated default-grammar SDoc and
Markdown readers. This minimizes immediate migration risk and keeps typed
relations and phase-one truthfulness in one checked contract. It is not a
formal-source selection. Before any later baseline, the maintainer must choose
among (a) JSON-led continuation, (b) an SDoc-led custom-grammar pilot with
equivalent relation/state validation and a one-way migration proof, or (c)
another separately evaluated tool/governance approach. Doorstop remains
unevaluated rather than rejected.

Costs/limits: a pinned `strictdoc==0.30.1` dependency, isolated Ubuntu CI job,
project checks for non-native semantics and a single future human-reviewed
import. The checker cannot prove engineering adequacy, numerical realism,
requirements completeness, independent-oracle quality, or execution success.

PA must accept or reject the source/tool direction. The maintainer must
explicitly approve or reject the numbering rule. Without both decisions, stop:
no formal IDs, authoritative source, full import, joint freeze, C, G2 or G3.

## PA review request

Review the exact PR head supplied with this package and answer separately:

1. Does this isolated StrictDoc-versus-lightweight trial provide sufficient
   actual evidence for a future source-format direction under its limits?
2. Is the B0-only non-reusable numbering rule technically fit for maintainer
   approval without allocating an identifier now?

PA technical approval is not maintainer numbering approval and does not
authorize merge/freeze. After PA review, execution stops for that decision.

## Structured SysML pilot addendum — 2026-10-12, PA review pending

### What changed, and what did not

This addendum records the active structured phase-one method. It does not rewrite the preceding historical comparison or turn its provisional future-source recommendation into a decision.

| Area | Current structured pilot | Deliberately unchanged / not claimed |
|---|---|---|
| Record body authority | `contract/pilot_structure.json` is the sole editable source for all five candidate statements and rationales. | No formal B0 requirement source has been selected or migrated. |
| Rich metadata | Typed locator inventory, applicability, allocation, development objects, verification provisions, execution-evidence collection, and directed relations are schema-checked in the JSON contract. | No metadata is hidden in StrictDoc `COMMENT`; no evidence is fabricated. |
| StrictDoc | Generated default-grammar body/Parent projection plus a retained custom-grammar `ACCEPTANCE` capability probe under StrictDoc 0.30.1. | No claim that the main projection exhausts StrictDoc custom-field capability. |
| SysML | A bounded textual `PILOT-MODEL-*` slice is parsed and AST-inspected. | No OMG conformance, graphical notation, execution, simulation, interchange, satisfaction, or verification verdict is claimed. |
| G0/G1/G2/G3 | G0 field locators and the approved legacy disposition are checked; G2 objects remain planned/not-run. | No numerical threshold is copied, and no G1 behaviour or G2/G3 code is changed. |

The source split is intentional: JSON owns review-record semantics, while the `.sysml` source owns the bounded model structure. The SysML requirement proxy contains no copied record body and the verification definitions carry no `verify` usage or pass result. Cross-domain `models`, `allocated_to`, `specified_by`, `development_checked_by`, and future `evidenced_by` links are explicitly labelled project extensions, rather than incorrectly reusing SysML v1 relationship names.

### Standard, tool, and presentation boundaries

The language reference is OMG SysML v2.0 Part 1 [`formal/2026-03-02`](https://www.omg.org/spec/SysML/2.0/Language/PDF), held fixed for this review. The selected textual subset is documented with sections and printed page numbers in [modeling_conventions.md](../../models/modeling_conventions.md): packages and definitions/usages (§§7.5–7.6), items (§7.10), parts (§7.11), interfaces/connections/flows (§§7.13–7.16), requirements (§7.21), verification cases (§7.24), and metadata (§7.27). The standard's graphical notation is explicitly outside this parser-based review slice.

The isolated dependency file pins `jsonschema==4.23.0`, `strictdoc==0.30.1`, and `sysmlpy==0.33.2` (plus the scoped test runner). `sysmlpy` is a third-party pure-Python parser/analyser. The implementation calls its grammar loader, model loader, and analyser, and consumes its AST to check stable model identities and flow endpoints. The observed fixed-version analysis issues are non-error naming-convention warnings caused by quoted, stable `PILOT-MODEL-*` identities; they are surfaced in the generated model view rather than suppressed. Metadata annotations are not used because this parser version's model builder does not support the needed annotation path.

StrictDoc 0.30.1 accepted the correctly declared custom `ACCEPTANCE` field and rendered it in native HTML. The main generated SDoc still uses the default body and hierarchy fields because this increment selected JSON-led cross-domain typing and deterministic projections for comparison. Locators/relations/statuses therefore remain typed JSON data instead of labels in `COMMENT`. The HTML is a SHA-named, loopback-only temporary review page, not a standard SysML graphic or retained evidence artifact.

### Standard-view disposition

The model now contains a minimal standard SysML v2 textual view definition and typed view usage under Part 1 §8.2.2.26. The usage exposes `PILOT-MODEL-B0-BOUNDARY-01` from the same `.sysml` source; the generated model reading aid records the two view identities, the exposed boundary, the standard locator, and the rebuild path. The fixed `sysmlpy==0.33.2` parser accepts and identifies both view declarations but does not retain the `expose` relationship in its AST and does not render graphical notation. Accordingly this closes only the work-order's smallest standard-grounded **view** need; it does not claim a SysML graphical diagram, layout/interchange fidelity, or OMG/tool conformance. Design-time verification definitions remain planned structure, never test verdicts.

### Migration coverage and checks

The earlier fixture had 26 collected test instances: 21 text/checker instances including four JSON-pointer-index parameters, plus five native StrictDoc CLI instances. The structured suite retains those checks, adds the native custom-grammar capability probe, and replaces the hand-maintained two-text equivalence test with a test-only pre-structured semantic baseline plus controlled-projection drift checks. It expands to 46 collected instances, including raw-request actuation, paired-command type/member/direction mutations, fabricated lifecycle/result, orphan evidence, and wrong-existing model-target counterexamples, without skips, xfails, or `continue-on-error`.

| Earlier coverage | Structured replacement / retention |
|---|---|
| Paired handwritten SDoc/Markdown parsing and drift | Single JSON authority plus byte-exact generated SDoc/Markdown/model-view drift check. |
| Temporary UID / Parent shape | JSON uniqueness and Parent-only cycle checks, plus retained native StrictDoc duplicate/missing-Parent rejection. |
| JSON Pointer / Markdown locator checks | Retained with separate malformed-anchor and four invalid-array-index counterexamples. |
| Legacy applicability reference | Retained fixed approved-decision locator and both CTL disposition checks. |
| Mermaid-derived model references | Actual `sysmlpy` AST identity/type/flow checks, unknown-target and dangling/invalid-model counterexamples. |
| Planned/not-run wording | Separate development lifecycle, verification execution status, and evidence collection checks that reject planned `pass` or attached evidence. |
| No equivalent earlier coverage | Schema required-field/enumeration checks; typed relation endpoint/direction checks; G2 trace-chain check; legal M:N relation; truth-to-controller leak check. |
| Local review navigation | A generated-preview check requires stable identity links for record navigation, native Parent traversal, model elements, and planned development/verification objects. |

The scoped commands for final PR validation are:

```text
python -B tools/systems_engineering/check_g15b_phase1_pilot.py
strictdoc export --config tools/systems_engineering/g15b_pilot/strictdoc/strictdoc_config.py --formats=html --output-dir <temporary-output> --no-parallelization tools/systems_engineering/g15b_pilot/strictdoc
python -B -m pytest -q tools/systems_engineering/g15b_pilot/tests -p no:cacheprovider
```

They are run only in the isolated G1.5-B tool environment. The final PR head, fresh output path, CI result, and viewport-review observations are supplied to PA as handoff evidence; neither this addendum nor a green tool exit converts a candidate record into a formal requirement or a planned object into execution evidence.

### Decision needed after PA technical review

PA should assess whether the structured pilot has accurately separated record authority, native tool limits, project extensions, and evidence status. A maintainer—not this pilot or PA technical approval alone—must still decide whether a future formal source is JSON-led, StrictDoc-led, another evaluated tool, or a different governance approach; whether to adopt the numbering rule; and whether a controlled migration is warranted. Until then, the stop conditions remain: no formal IDs, no full source migration, no joint freeze, and no C/G2/G3 start authorization.
