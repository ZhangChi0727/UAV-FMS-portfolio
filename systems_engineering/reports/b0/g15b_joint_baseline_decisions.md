# G1.5-B joint-baseline unified decision package

Status: **S0 candidate for PA review and D1 maintainer decision**

Prepared: 2026-10-13 (Australia/Perth)

Execution PR: [#17](https://github.com/ZhangChi0727/UAV-FMS-portfolio/pull/17)

Execution issue: [#18](https://github.com/ZhangChi0727/UAV-FMS-portfolio/issues/18)

Base: `02e59d4654e87d85ef3543e0812a5e373be684ac`

This package makes no formal B0 requirement authoritative, allocates no
`B0-REQ-*` identity, imports no full baseline, and approves no joint freeze.
It is the single S0 input to approval gate D1.

## 1. Boundary and inherited evidence

PR #16 accepted only a five-record, non-authoritative method/tooling pilot. It
proved that one structured source can drive controlled reader projections,
that StrictDoc 0.30.1 accepts a declared custom grammar field, and that a
bounded SysML textual slice can be parsed and inspected. It did not select a
formal requirement source, activate numbering, prove model conformance, or
freeze requirements, model, relations, or verification provisions.

This increment is limited to B0 v0.2's bounded attitude experiment. It may
establish a formal requirement/model/verification-planning baseline after the
required approvals. It may not alter frozen G0 v1/v2 values, G1 numerical
behaviour, historical `NAV-REQ-*`, `CTL-REQ-*` or `FDI-REQ-*` records, or
implement G1.5-C, G2 or G3.

The following remain explicit method limits:

- parser success does not prove runtime same-tick behaviour or engineering
  adequacy;
- the fixed parser does not retain the pilot view's `expose` relation in its
  AST and does not prove graphical notation or OMG conformance;
- generated StrictDoc, Markdown and HTML are reader projections, not execution
  evidence or a second requirement authority;
- planned verification relations are design structure, not a satisfaction or
  pass verdict.

## 2. Source inventory and authority classification

All Git blob identities below are from the base commit. Section headings and
JSON Pointers remain the human review locators; a blob alone is not a semantic
locator.

| Source | Base blob | Role in S0 | Authority / limitation |
|---|---|---|---|
| `systems_engineering/project_charter.md` | `0fe6a744ff9aa71649d05d99240b4c3870a91603` | Purpose, product boundary, stopping rules | Approved project intent; not a detailed requirement catalogue. |
| `systems_engineering/development_baseline.md` | `dcb95c8d26eb61fd7a10966d4b27508b45f58f21` | B0 objective, included/excluded scope, gate semantics | Planning baseline; does not claim implementation completion. |
| `05_integration/b0/configs/b0_g0_contract.v2.json` | `1beff6e6a9a81d0ab92b2059a93207ffed9d291d` | Frozen frames, timing, messages, scenarios, metric definitions and parameter values | Sole machine authority for approved G0 v2 contract values; must be referenced, not copied. |
| `systems_engineering/reports/b0/g0_approval_decision.md` | `293fe48e6ba23f7cd7bacb65b2f4d9d418b037c3` | G0 approval and legacy-control disposition | Approval fact; `CTL-REQ-001/002` are not applicable to current B0 and are not satisfied. |
| `systems_engineering/models/architecture.md` | `a11252d52c757923d101b5f222052a472d7e143c` | Existing component and convention summary | Informative summary. Its requested-torque-only wording is stale against the paired-command/limited-target-only G0 contract and must be corrected after D1, without changing G0. |
| `systems_engineering/requirements/legacy_requirements.md` | `b3d9c73e73c244914d6c0ee8be32dc3452c2848b` | Historical NAV/CTL/FDI identifiers and thresholds | Preserved historical text. Its statement that CTL applicability still requires review is stale against the approved G0 decision; history and IDs remain unchanged. |
| `systems_engineering/verification/verification_plan.md` | `15a29b5773ce0e31a01d59cad3c550b8e3a56fb4` | Existing B0 check/evidence-chain planning | Planning source, not a full set of verification specifications and not results. |
| `01_simulation/b0/evidence.py` | `bb522a3d8a06943ce050c327be98986f4c250313` | Existing G1 evidence generator | Implementation/evidence mechanism only; it cannot originate all obligations. |
| `systems_engineering/reports/b0/g15b_phase1_requirements_tooling_numbering_decision.md` | `114390bb4ba2dbbb153cbe9a9aa928facd4bdf6f` | Historical tool and numbering proposal plus structured-pilot addendum | Trial conclusion only. D1 must independently approve formal use. |

The five `PILOT-ONLY-*` records and their migration oracle remain historical
fixtures. They may supply source mappings and method examples, but they are not
renamed into formal records and do not define completeness.

## 3. Formal requirement-source options

### Option A — JSON-led formal source (recommended)

One checked JSON document owns each formal requirement body, identity,
applicability, rationale, source locator references, allocation references,
verification-specification references, approval/change state and directed
cross-domain relations. A JSON Schema owns structural shape; a small semantic
checker owns cross-object rules. StrictDoc and Markdown are deterministic
reader projections.

Advantages:

- typed nested fields and directed relations are explicit and already covered
  by fail-closed negative-fixture patterns;
- JSON Pointer locators, lifecycle separation and controlled generation have
  already been exercised in the pilot;
- offline recovery needs only JSON plus the repository checker; StrictDoc is
  not required to recover the authority;
- migration is one reviewed import into one source, with byte-drift checks for
  committed text projections;
- identity, replacement and retired-ID rules can be enforced without encoding
  type or hierarchy in the identifier.

Costs and risks:

- direct editing is more verbose and less prose-friendly than SDoc;
- the project must maintain a schema, semantic checker and projection builder;
- JSON validation alone cannot prove requirement quality, scope sufficiency or
  independent-oracle adequacy;
- relation semantics are project extensions and must not be presented as native
  SysML relationships.

### Option B — StrictDoc custom-grammar-led formal source

One SDoc source owns requirement bodies and declared custom fields. Native UID,
Parent and requirement relations are used where their semantics fit. A project
checker validates external locators and cross-domain model/development/
verification references.

Advantages:

- prose-oriented Git review and native human-readable source;
- native hierarchy, web export and project navigation;
- the retained 0.30.1 probe proves that custom fields such as `ACCEPTANCE`
  parse and render. This option is not rejected on a false claim that StrictDoc
  lacks custom fields.

Costs and risks:

- a full custom grammar, import/recovery procedure and equivalent negative
  checks have not yet been demonstrated for the complete B0 record set;
- typed cross-domain endpoint kinds, lifecycle/result separation and complex
  verification objects still need project validation;
- representing large structured verification provisions in SDoc increases
  grammar and parsing maintenance;
- adoption makes the larger StrictDoc dependency closure necessary to edit and
  validate the authority, rather than only to render a review projection.

### Option C — lightweight Markdown plus project conventions

This remains a fallback only if A and B become unsuitable. It has the lowest
tool dependency and best raw readability, but would require a new convention
parser for structured fields and relations. That would recreate a bespoke
requirements system with weaker shape guarantees. No evidence justifies that
cost now, so it is not recommended. Doorstop and online/commercial platforms
are not introduced in this increment.

### Recommendation

Approve **Option A, JSON-led**, for this bounded formal baseline. The reason is
the demonstrated typed/state/relationship contract and recovery boundary, not
a limitation of StrictDoc custom fields. StrictDoc 0.30.1 remains a pinned,
isolated reader/export tool. The recommendation is deliberately local to B0;
it is not a project-wide MBSE mandate.

## 4. Proposed exact authority boundaries after D1

The following files are proposals and must not be created as active formal
sources before D1 approval:

| Proposed path | Unique authority after approval | Not authoritative for |
|---|---|---|
| `systems_engineering/requirements/b0_requirements.json` | Requirement bodies, IDs, types/levels, rationale, source references, applicability, allocation/model/verification references, lifecycle/change state, legacy disposition and directed cross-domain relation edges | G0 numeric values, SysML structure, verification-provision bodies, execution results |
| `systems_engineering/requirements/b0_requirements.schema.json` | JSON structural contract | Engineering sufficiency or approval |
| `systems_engineering/requirements/b0_id_registry.json` | Allocated, retired and superseded formal B0 identifiers and non-reuse state | Requirement body or satisfaction |
| `systems_engineering/models/b0_system.sysml` | B0 system boundary, stable model identities, responsibilities, interfaces, flows, behaviour/view declarations | Requirement prose, parameter values, execution or pass verdicts |
| `systems_engineering/verification/b0_verification_specifications.json` | Verification-provision identity and body: method, stage, preconditions, inputs, steps, oracle, metrics/units/tolerances, decision rule, invalid/failure handling, expected evidence and responsibility | Execution result or evidence index |
| `05_integration/b0/configs/b0_g0_contract.v2.json` | Existing approved G0 numeric/configuration contract | Requirement approval or later execution result |
| `systems_engineering/requirements/generated/b0_requirements.sdoc` | Deterministic StrictDoc reader input generated from the requirement authority | Editable requirement source |
| `systems_engineering/requirements/generated/b0_requirements.md` | Deterministic no-tool review projection | Editable requirement source |

Relations are edited exactly once: requirement-to-model/allocation/
verification edges in `b0_requirements.json`; native SysML structure/flow/view
relations in `b0_system.sysml`. Reverse queries and reader links are generated.
No requirement body is hand-copied into SysML proxies or verification files.

## 5. Numbering and change-control proposal

D1 is asked to approve the previously reviewed pattern without instantiating it
inside this decision package:

1. Formal B0 identities match `B0-REQ-NNNN`, with a four-digit monotonically
   allocated ordinal.
2. Type, level, component, hierarchy and status remain fields; they are never
   encoded in the identifier.
3. An allocated ordinal is never reused, including after rejection, retirement
   or deletion. Intentional gaps retain a registry reason.
4. A substantive change to the normative obligation creates a new identity and
   an explicit `supersedes` edge. Editorial corrections retain identity and add
   a versioned change note.
5. `PILOT-ONLY-*` identities are migration origins only. They are never renamed
   or reused as formal identities.
6. Historical `NAV-REQ-*`, `CTL-REQ-*` and `FDI-REQ-*` identities and text are
   preserved. They appear only through typed legacy references and approved
   applicability/disposition records.
7. Model and verification identities use independent namespaces; they do not
   consume B0 requirement ordinals.

No formal identity is allocated until D1 approval is recorded against this
document version.

## 6. SysML tool provenance, licence and adoption boundary

### Closed provenance facts

The earlier pilot correctly treated licence/source metadata as unresolved. S0
now closes that due diligence for the exact evaluated release:

- PyPI release: `sysmlpy==0.33.2`, released 2026-06-14, source distribution
  SHA-256 `34dc4ae0112db649a41f7639c19b5d4793ae668d64697f98d8eee5f925d5b4da`.
- PyPI publish attestation identifies repository
  `https://github.com/mycr0ft/sysmlpy` and publishing commit
  `58c7c51365e2c7d3e047096f50e5638bf50240ee`.
- The installed distribution contains
  `sysmlpy-0.33.2.dist-info/licenses/LICENSE`, SHA-256
  `8d36a7594baed525e00f95bbaab15130ea270e1541be42310253fc36f014ac78`,
  with MIT License text and named copyright holders.
- Primary release record:
  <https://pypi.org/project/sysmlpy/0.33.2/>; source repository:
  <https://github.com/mycr0ft/sysmlpy>.

StrictDoc remains `0.30.1`; its tagged repository licence is Apache-2.0 and the
installed licence file SHA-256 is
`3392558ba768e0454ed2340433d5b9daf1ef32860368b9bf82b87a441fcd0438`.
Primary tagged licence:
<https://github.com/strictdoc-project/strictdoc/blob/0.30.1/LICENSE>.

### Recommended adoption boundary

Approve `sysmlpy==0.33.2` only in the isolated systems-engineering environment
as a syntax/parser/analyser and AST inspection helper for the explicitly
adopted textual subset. Pin the exact version and retain the release/provenance
record. Do not call it an OMG reference implementation, full semantic
validator, graphical tool, simulation engine, interchange proof or runtime
behaviour verifier.

For constructs the fixed AST does not retain—currently the standard textual
view's `expose` mapping—use a mandatory manual checklist that records:

- reviewed Git blob and blob-byte SHA-256 of the `.sysml` source;
- view definition and view usage identities;
- each exposed element identity and intended target;
- standard clause locator, reviewer, date and conclusion;
- invalidation whenever the source blob changes.

The generator may display that recorded conclusion but may not hard-code it as
if it were parser evidence. If the dependency becomes unavailable or changes
behaviour, the fallback is plain-text source plus the same version-bound manual
checklist and project relation checker; no cloud or commercial tool is needed.

## 7. Preliminary coverage and conflict inventory

These rows are engineering questions, not requirement IDs and not completed
verification results.

| Scope | Principal sources | Preliminary responsibility / verification need | S0 finding or decision needed |
|---|---|---|---|
| Normal, initial-offset, step, disturbance, noise, saturation/recovery, contamination, invalid/reset and replay scenarios | G0 v2 `#/scenarios`, acceptance policy and timing | Scenario runner, affected components and independent evaluator; each needs explicit provision and evidence type | Full coverage exists as approved contract structure but must be decomposed into atomic obligations without copying thresholds. |
| Plant / actuator / IMU | Baseline included scope; G0 plant/actuator/IMU and interface contracts; G1 source/tests | Plant, actuator, IMU and component verification | Historical G1 evidence must be mapped obligation by obligation; implementation cannot be the sole source. |
| Estimation | Baseline, G0 estimator contract and limitations | Planned G2 estimator; component and integrated provisions | Absolute yaw remains unobservable; acceleration contamination and invalid samples require explicit conditional behaviour. |
| Control | Baseline, G0 controller/anti-windup/interface contracts | Planned G2 controller; component and integrated provisions | Architecture summary is stale: controller emits one paired command and actuator dynamics consume limited target only. |
| Integration timing/reset | G0 timing, sequencing, message and reset contracts | Execution adapter plus each stateful component | Epoch-local reset, held-command pairing, timestamps, dt and rejection paths must remain consistent. |
| Truth boundary | Charter, baseline, architecture and G0 truth visibility/forbidden-input fields | Plant/sensor/evaluator visibility; estimator/controller isolation | Explicit reset initialization is the only exception; runtime truth leakage needs static and later dynamic checks. |
| Shared conventions | Architecture and G0 convention fields | All components and verification | NED/body, SI, scalar-first Hamilton and double precision must be referenced consistently. |
| Verification and release | Verification plan, G0 metric definitions, G4 baseline text | Independent evaluator and release/evidence responsibilities | B defines provisions; C later owns result/expiry/report linkage. No result may be pre-created. |
| Exclusions and risk | Charter/baseline exclusions and roadmap extension registry | Governance inspection | Translation, absolute yaw, hardware, HIL, flight and research remain excluded or separately gated. |
| Legacy applicability | Legacy requirements plus approved G0 decision | Applicability inspection | Current legacy summary must be updated to point to the already approved not-applicable disposition without rewriting history. |

## 8. D1 decision request

After PA technical review, the maintainer is asked to approve or reject each
item separately against the exact committed version of this package:

1. **Formal source:** approve JSON-led Option A and the authority/file
   boundaries in sections 3–4.
2. **Tool boundary:** approve pinned `sysmlpy==0.33.2` under the limited parser/
   AST role and mandatory version-bound manual `expose` checklist; retain
   StrictDoc 0.30.1 only as an isolated generated-reader/export tool.
3. **Numbering:** approve the non-reusable `B0-REQ-NNNN` rules in section 5.

Approval must identify the reviewed commit or document blob and retain the
user's words, date and message/comment locator. Until all three are explicitly
approved, stop before formal-ID allocation, authoritative-source creation,
full migration or any claim of a joint baseline.
