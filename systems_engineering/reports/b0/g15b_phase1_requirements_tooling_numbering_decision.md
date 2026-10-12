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
| Rendering | Native HTML export to a temporary directory | Directly reviewable text; no second renderer | Generated HTML is not committed or evidence of satisfaction. |
| Project-specific fields | Standard `COMMENT` labels in this fixture | Explicit labeled fields | Thin checker owns exact applicability/scope, approved-not-applicable reference, JSON pointers, Markdown anchors, model elements, verification and acceptance checks. |
| Git review | Plain-text diff | Plain-text diff | Five equivalent records only; not a full-baseline migration proof. |
| Future migration | Plain-text source with rebuildable native output | Plain-text source | A later approved import is one-way and reviewed into one chosen source. The twin remains only as a fixture/conclusion. |

The native command is deliberately described narrowly: `strictdoc export` is a
parser/export exercise, not an all-purpose project requirement validator.
Duplicate keys, broken parents, unknown model elements, required fields,
approved-not-applicable references, JSON pointers, Markdown anchors and
cross-format drift are tested by the dedicated thin checker and its negative
fixtures.

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

/tmp/uav-fms-g15b-strictdoc/bin/strictdoc export --formats=html \
  --output-dir /tmp/uav-fms-g15b-html-current --no-parallelization \
  tools/systems_engineering/g15b_pilot/strictdoc
# exit 0; generated .../html/strictdoc/b0_phase1_pilot.html

/tmp/uav-fms-g15b-strictdoc/bin/python tools/systems_engineering/check_g15b_phase1_pilot.py
# exit 0; G1.5-B phase-one pilot check passed (5 non-authoritative records)

/tmp/uav-fms-g15b-strictdoc/bin/python -m pytest -q \
  tools/systems_engineering/g15b_pilot/tests/test_g15b_phase1_pilot.py \
  tools/systems_engineering/g15b_pilot/tests/test_g15b_native_strictdoc.py
# exit 0; 17 passed in 9.73s
```

The native test suite proves that the evaluated StrictDoc CLI rejects a
duplicate temporary UID and a parent relation targeting an absent temporary
UID; the thin checker separately proves the project-specific failures. The
rendered HTML contained all five trial records, `planned/not_run`, and a
resolved Git version/branch macro. A pre-commit render showed
`56fe38b (Git branch: codex/b0-g15-requirements)`, which is correctly only the
last committed state at that moment; it must not be mistaken for a hash of
uncommitted source. The CI test asserts that the macro is resolved, and the PR
head/CI run are the authoritative final render identity.

`strictdoc --help` exposed `export` but no native `validate` subcommand in
0.30.1. The direct trial inputs are pinned, while StrictDoc's large transitive
dependency closure is not a separately hash-locked file; that resolver surface
is a maintenance cost for a future approval decision, not hidden reproducibility
evidence.

### User-facing temporary preview, not a repository artifact

The same successful native export was also written outside Git to
`%LOCALAPPDATA%\Temp\uav-fms-g15b-strictdoc-preview-20261012\html\strictdoc\b0_phase1_pilot.html`.
It is a short-lived, local browser preview of the five `PILOT-ONLY-*` fixtures,
not a formal requirements view or retained evidence artifact. Recreate it with
the documented `strictdoc export` command and a local temporary output path;
do not copy it into the repository.

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

**Recommendation for PA review:** subject to the observed command evidence,
provisionally prefer one StrictDoc `.sdoc` source for a future approved phase
two baseline, retaining the small project checker for non-native semantics.
It offers native hierarchy and readable temporary HTML while remaining text.
Lightweight Markdown plus the same checker is the credible fallback, not a
selection. Doorstop has not been installed/evaluated because StrictDoc is the
requested first candidate, not because Doorstop is ruled out.

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
