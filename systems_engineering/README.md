# Systems engineering entry

This directory is the reader-facing engineering entry for B0. It separates
system relationships and their sources from executable module code, daily
operation notes, and retained evidence. The current snapshot is based on G0
approval and the merged G1 plant/actuator/IMU component acceptance; it does not
claim G2, G3, G4, overall B0 completion, hardware, flight, or research results.

## Reading route

1. **Purpose and scope** — [project charter](project_charter.md) and
   [development baseline](development_baseline.md).
2. **Models** — [architecture source](models/architecture.md),
   [G0 model contract](models/g0_contract.md), and the
   [B0 system views](models/system_views.md).
3. **Requirements state** — [legacy requirements and applicability](requirements/legacy_requirements.md).
   The isolated [G1.5-B phase-one pilot](../tools/systems_engineering/g15b_pilot/README.md) and its
   [decision package](reports/b0/g15b_phase1_requirements_tooling_numbering_decision.md)
   remain non-authoritative until PA review and maintainer approval; they do
   not create or freeze new B0 requirement identifiers.
4. **Development state** — [current status snapshot](reports/current_status.md)
   and the module-local implementations under `01_simulation/` and
   `05_integration/`.
5. **Verification** — [verification plan](verification/verification_plan.md),
   [G0 acceptance](verification/g0_acceptance.md), and the
   [V&V report](reports/v_and_v_report.md).
6. **Evidence** — [RESULTS.md](../RESULTS.md), the G1 evidence generator and
   its CI artifact, and the versioned reports under `reports/`.

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

The G1.5-A model views are editable Markdown/Mermaid sources. They are a
structural aid for the B0 work and intentionally do not replace the G0 JSON
contract or the future requirements/model joint freeze.
