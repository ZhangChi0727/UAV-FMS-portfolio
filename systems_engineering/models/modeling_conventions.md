# B0 structured modelling conventions

## Status, purpose, and review boundary

This document defines the method used by the **non-authoritative G1.5-B
phase-one structured pilot**.  It is a review aid, not a B0 requirements/model
joint baseline, a SysML conformance certificate, or an authorization to begin
G2/G3 implementation.  The pilot keeps the five `PILOT-ONLY-*` records outside
the formal requirements namespace and does not change G0, G1 behaviour,
acceptance values, or legacy identifiers.

The language reference is OMG SysML v2.0 Part 1, document
[`formal/2026-03-02`](https://www.omg.org/spec/SysML/2.0/Language/PDF), fixed
for this trial.  A later OMG publication is not silently adopted: changing the
target language version requires a new method review.

The pilot distinguishes four different claims:

| Claim | What this pilot establishes | What it does **not** establish |
|---|---|---|
| Language use | The checked textual slice uses a deliberately small subset of the named SysML v2.0 constructs. | OMG language compliance, tool certification, or complete semantic coverage. |
| Graphic notation | The review page is a project-generated textual reading aid. | A SysML standard graphical notation view or a diagram interchange claim. |
| Tool coverage | The fixed third-party parser can parse the adopted subset and expose the AST used by the checker. | Execution, simulation, formal verification, XMI interchange, or validation of every standard semantic rule. |
| Project semantic consistency | The repository checker validates the project contract, its source locators, endpoints, statuses, and generated projections. | Evidence that a planned design is implemented, satisfied, verified, or accepted. |

## Inputs, outcomes, and update triggers

| Method input | Controlled outcome | Review/update trigger |
|---|---|---|
| `05_integration/b0/configs/b0_g0_contract.v2.json` | Field-level source locators only; no copied G0 numeric threshold. | Approved G0 contract revision or locator failure. |
| G0 approval decision and legacy-requirement record | `not_applicable` disposition and its approval locator. | Change to the decision, disposition, or legacy scope. |
| Five pilot candidate records | One structured editable body source and generated reader/StrictDoc projections. | PA changes the pilot scope, count, or record wording. |
| `b0_truth_control_slice.sysml` | A bounded, textual truth/control interface slice. | A change to the declared model boundary, element identity, or flow endpoint. |
| Fixed parser/checker versions | Repeatable syntax/AST and project-consistency checks. | Dependency upgrade, parser limitation, or CI divergence. |

The method is reviewed before any of the following occurs: promotion of a
`PILOT-ONLY-*` identity, creation/renumbering of a formal requirement,
assertion of satisfaction or verification, adoption of a new SysML language
version, or a request for an executable/graphical MBSE platform.

## Authority and one-way derivation

There is exactly one editable source for every pilot record body:

| Concern | Unique editable authority | Controlled consumers / derived output |
|---|---|---|
| Record identity, title, statement, rationale, scope, applicability, acceptance condition, and status | `tools/systems_engineering/g15b_pilot/contract/pilot_structure.json` | Checker; generated StrictDoc and Markdown review projections. |
| Parent hierarchy | `parent` in the same JSON record; projected into StrictDoc native `Parent` relations. | StrictDoc hierarchy and generated reader view. |
| Typed record/model/development/verification relations | `relations` in the same JSON contract. | Checker and generated review views. |
| SysML textual element definitions and interface flows | `tools/systems_engineering/g15b_pilot/model/b0_truth_control_slice.sysml` | Parser/AST check and generated model reading aid. |
| Human-readable SDoc/Markdown/model view | Generated; never a second editable requirement source. | StrictDoc export and local review. |
| HTML preview/screenshot | A SHA-named temporary directory outside Git. | Local visual inspection only; not retained evidence. |

The JSON record body is the pilot's authority only.  The existing G0 JSON
contract, approval decision, and legacy records retain their own authorities.
The model may refer to a pilot record through a proxy identity, but does not
duplicate its normative statement or declare a `satisfy`/`verify` result.

## Field dictionary

The schema at
`tools/systems_engineering/g15b_pilot/contract/pilot_structure.schema.json`
is normative for the structured pilot.  The following table explains the
fields that matter in review.

| Field / object | Meaning and constraint |
|---|---|
| `records[].key` | Temporary `PILOT-ONLY-*` identity; it is never a `NAV-REQ-*`, `CTL-REQ-*`, or `FDI-REQ-*` identifier. |
| `statement`, `rationale` | The only editable body text for the five pilot records.  Generated projections copy it verbatim. |
| `applicability.state` | `applicable` or `not_applicable`.  The latter requires a separately checked `approval_ref`; it is not satisfaction. |
| `source_locator_ids` | References into a typed locator inventory.  Every locator is resolved against the repository, with Markdown anchors or JSON Pointers checked separately. |
| `acceptance_condition` | A planned inspection criterion.  It may reference an approved G0 field but may not reproduce G0 thresholds. |
| `evidence_status` | Pilot record status, currently `planned/not_run`; it is not an execution result. |
| `model_elements[]` | Stable `PILOT-MODEL-*` identities, their expected SysML definition type, and their intended bounded role. |
| `development_objects[]` | Allocated development candidates.  `planned` objects have no execution result or evidence claim. |
| `verification_provisions[]` | Planned review/verification definitions with inputs, steps, independent oracle, and acceptance condition. |
| `execution_evidence[]` | Reserved for a real future execution only; the current list is empty.  Evidence is never synthesized from a planned provision. |
| `relations[]` | Typed, directed cross-domain project extensions.  `origin` records whether a relationship is native SysML or a project extension; the current cross-domain links are extensions, not renamed SysML v1 relations. |
| `parent` | The sole structural hierarchy link.  Cycle detection applies only to this hierarchy, not to physical feedback flows in the SysML slice. |

## Relation map and endpoint rules

Native SysML relationships remain in the `.sysml` source.  The contract's
cross-domain links are intentionally labelled `project_extension`; they are
not assertions of SysML v1 `deriveReqt`, `refine`, `allocate`, `satisfy`, or
`verify` semantics.

| Project relation type | Allowed source → target | Direction | Meaning |
|---|---|---|---|
| `models` | `record` → `model_element` | `forward` | A candidate record is reviewed against a bounded model element. |
| `allocated_to` | `record` → `development_object` | `forward` | A candidate record is allocated to planned work; it does not claim implementation. |
| `specified_by` | `record` → `verification_provision` | `forward` | A candidate record has a planned independent review/verification provision. |
| `development_checked_by` | `development_object` → `verification_provision` | `forward` | A planned development object is associated with a planned provision. |
| `evidenced_by` | `verification_provision` → `execution_evidence` | `forward` | Permitted only after real execution; absent in this phase-one pilot. |

Many-to-many links are allowed.  A relation must name known endpoint IDs of
the specified kinds, use the declared direction, provide a source locator, and
not turn a `planned` object into `pass`, `satisfied`, or executed evidence.

## SysML v2 construct selection

The standard's document page numbers below are the printed Part 1 page numbers
(the PDF viewer index is different).  This table records why the pilot selects
each construct and, equally importantly, what it does not claim.

| Construct / notation | OMG SysML v2.0 Part 1 reference | Fixed parser support in this pilot | Project use / limit |
|---|---|---|---|
| Package, definitions, and usages | §§7.5–7.6, pp. 23–44; textual notation §§8.2.2.5–8.2.2.6, pp. 171–172 | Parsed as an AST. | One bounded package and stable quoted pilot identities. |
| Item definitions/usages | §7.10, pp. 56–57; §8.2.2.10, p. 175 | Parsed and inspected. | Declares command, sample, estimate, torque, feedback, and truth items; no quantity/value semantics are claimed. |
| Part definitions/usages | §7.11, pp. 58–60; §8.2.2.11, p. 175 | Parsed and inspected. | Plant, IMU, estimator, controller, actuator, evaluator, and B0 boundary roles. |
| Interfaces, connections, and flows | §§7.13–7.16, pp. 63–83; §§8.2.2.13–8.2.2.16, pp. 176–178 | Parsed; AST flow ends are consumed by the project checker. | Shows truth only toward evaluation and explicit estimator/controller interfaces; it is not executable data-flow simulation. |
| Requirement definition/proxy | §7.21, pp. 129–137; §8.2.2.21, pp. 188–189 | Parsed as a definition. | A model proxy identifies the G2 pilot topic only; its authoritative body stays in the JSON contract. |
| Verification case definition | §7.24, pp. 141–144; §8.2.2.24, p. 190 | Parsed as a definition. | Represents a planned check only; no `verify` usage or pass verdict is modelled. |
| Metadata | §7.27, pp. 157–161; §8.2.2.27, p. 192 | The parser version can parse some syntax but its model builder does not support the needed annotation path. | Not used as an identity mechanism; stable quoted definition names are used instead and the limitation is recorded. |
| Graphical notation / views | §8.2.3, p. 193 onward | Not rendered by the fixed parser. | The generated HTML/Markdown is a project review view, not standard graphical notation. |

The pilot intentionally does **not** use a `satisfy requirement` or `verify
requirement` usage.  Under the standard those terms carry semantic assertions;
the current records and development/verification objects are planned or
not-run, so such an assertion would be misleading.

## Fixed tooling decision

The trial checks its textual slice with `sysmlpy==0.33.2`, installed only in
the isolated G1.5-B tool environment.  It is a third-party, pure-Python
ANTLR-based parser, not an OMG reference implementation, a commercial MBSE
platform, or a certification tool.  The checker calls its grammar loader and
model loader/analyser for the adopted subset, then consumes the returned AST to
validate declared identities and flow endpoints.  It never hand-parses SysML
source with a project regex.

The fixed version is declared in `requirements/g15b-pilot.txt`.  To reproduce
the tool check, install that isolated requirements file, run
`check_g15b_phase1_pilot.py`, and run the scoped `g15b_pilot/tests` suite.  A
dependency upgrade, changed parser behaviour, or a need for metadata,
graphical notation, execution, simulation, or interchange is a method-review
trigger rather than a silent capability claim.

## Trace query and review use

The controlled generated review view exposes the following queryable chain:

```text
PILOT-ONLY record
  -> models -> PILOT-MODEL element
  -> allocated_to -> PILOT-DEV candidate (planned where applicable)
  -> development_checked_by / specified_by -> PILOT-VER provision (planned/not_run)
  -> evidenced_by -> real execution evidence (none in phase one)
```

This chain is enough to review intended ownership and planned verification
without claiming an implemented controller, completed test, or accepted G1.5
baseline.  Any future activation must add real evidence at its owning stage and
must be evaluated against the appropriate G0/G1/G2/G3 gate rather than against
this pilot alone.
