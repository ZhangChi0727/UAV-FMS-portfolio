# Systems engineering entry

This directory is the reader-facing engineering entry for B0. It separates
system relationships and their sources from executable module code, daily
operation notes, and retained evidence. G0 and the G1.5-B joint baseline are
approved, and G1 plant/actuator/IMU component acceptance is merged. The original
PA accepted closeout K3; G1.5-C is now the active verification-traceability and
reporting layer. G2-A is merged and post-merge accepted; G2-B PR #22 is closing
implementation-review findings with a retained candidate package for re-review
and is not yet accepted. This does not claim G2 overall, G3, G4, overall B0
completion, hardware, flight, or research results.

## Reading route

1. **Purpose and scope** — [project charter](project_charter.md) and
   [development baseline](development_baseline.md).
2. **Models** — [architecture source](models/architecture.md),
   [G0 model contract](models/g0_contract.md), [B0 system views](models/system_views.md),
   the [formal B0 model candidate](models/b0_system.sysml), and the
   [structured-pilot modelling conventions](models/modeling_conventions.md).
3. **Requirements state** — the [formal candidate source and reading guide](requirements/README.md)
   plus [legacy requirements and applicability](requirements/legacy_requirements.md).
   The isolated [G1.5-B phase-one pilot](../tools/systems_engineering/g15b_pilot/README.md) and its
   [decision package](reports/b0/g15b_phase1_requirements_tooling_numbering_decision.md)
   remain non-authoritative method records after their bounded acceptance; that
   acceptance did not create or freeze new B0 requirement identifiers. The pilot has
   one structured JSON record source and controlled StrictDoc/Markdown/model
   projections; it is not a formal SysML conformance or graphical-view claim.
   The formal joint baseline's [historical candidate review](reports/b0/g15b_joint_baseline_review.md)
   and [candidate input contract](reports/b0/g15c_readiness.md) retain their
   pre-approval wording. The [D2 approval](reports/b0/g15b_d2_approval.md) and
   [current closeout record](reports/b0/g15b_closeout_current.md) describe the
   effective lifecycle without rewriting those historical snapshots.
4. **Development state** — [current status snapshot](reports/current_status.md)
   and the module-local implementations under `01_simulation/`,
   `02_estimation/b0/`, `03_control/b0/` and `05_integration/`.
5. **Verification evidence** — [execution/evidence contract](verification/README.md)
   and the [current G1.5-C traceability status](reports/b0/g15c_verification_status.md).
   The report keeps design links, execution results, evidence availability,
   version applicability and review acceptance separate.
6. **Verification** — [verification plan](verification/verification_plan.md),
   [G0 acceptance](verification/g0_acceptance.md), and the
   [V&V report](reports/v_and_v_report.md).
7. **Evidence** — [RESULTS.md](../RESULTS.md), the G1/G2-A retained component
   artifacts, the [G2-B candidate validation record](reports/b0/g2b_validation_record.md),
   and versioned reports under `reports/`. Candidate generators or green tests
   do not imply PA acceptance.

## Source-of-truth boundaries

| Concern | Authoritative location | This entry does not do |
|---|---|---|
| Scope, dependencies, gates | [docs/roadmap.md](../docs/roadmap.md) | mirror live Issue state |
| Approved executable parameters | `05_integration/b0/configs/` and its validator | copy thresholds into diagrams |
| System relationships and allocation | `models/` | claim planned components are implemented |
| Requirement applicability | `requirements/` | invent or renumber NAV/CTL/FDI IDs |
| Verification planning | `verification/` | treat planned or not-run work as pass |
| Versioned conclusions | `reports/` and [RESULTS.md](../RESULTS.md) | replace retained raw artifacts |
| Execution steps | [docs/work_orders/](../docs/work_orders/) | become a second status database |

## Maturity legend

- **accepted** — reviewed or executed at the stated baseline and evidence link.
- **approved/planned** — contract or plan exists, but implementation or
  execution is not claimed.
- **not active** — an extension or future stage outside the current B0 scope.

The G1.5-A model views remain editable Markdown/Mermaid structural aids. The
G1.5-B source files intentionally retain their reviewed pre-approval status
bytes; the separate approval and current-status records establish the effective
frozen baseline. G1.5-C execution evidence belongs in a new layer and must not
rewrite the 29 frozen planned/not-run verification specifications.
