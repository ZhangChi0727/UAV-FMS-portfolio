# G1.5-A document migration record

This record maps every file moved by G1.5-A. Git moves preserve history; the
old paths are not maintained as duplicate authoritative copies. The G0 JSON
approval source string is the one explicit compatibility exception and is
resolved by `05_integration/b0/validate_config.py` to the migrated report.

| Previous path | Current path | Responsibility / reason |
|---|---|---|
| `07_docs/project_charter.md` | `systems_engineering/project_charter.md` | system purpose, scope and change rules |
| `07_docs/development_baseline.md` | `systems_engineering/development_baseline.md` | B0 baseline and gates |
| `07_docs/architecture.md` | `systems_engineering/models/architecture.md` | architecture and numerical conventions |
| `07_docs/requirements.md` | `systems_engineering/requirements/legacy_requirements.md` | existing IDs and applicability; no new IDs |
| `07_docs/verification/verification_plan.md` | `systems_engineering/verification/verification_plan.md` | verification planning |
| `07_docs/v_and_v_report.md` | `systems_engineering/reports/v_and_v_report.md` | V&V conclusions and limits |
| `07_docs/development_readiness_report.md` | `systems_engineering/reports/development_readiness_report.md` | historical readiness report |
| `07_docs/b0/g0_contract.md` | `systems_engineering/models/g0_contract.md` | G0 model/contract explanation |
| `07_docs/b0/g0_acceptance.md` | `systems_engineering/verification/g0_acceptance.md` | G0 acceptance matrix |
| `07_docs/b0/g0_approval.md` | `systems_engineering/reports/b0/g0_approval.md` | approval package summary |
| `07_docs/b0/g0_approval_decision.md` | `systems_engineering/reports/b0/g0_approval_decision.md` | authoritative decision record |
| `07_docs/b0/g0_review_resolution.md` | `systems_engineering/reports/b0/g0_review_resolution.md` | review resolution history |
| `07_docs/b0/pr11_review_report.md` | `systems_engineering/reports/b0/pr11_review_report.md` | historical PR review |
| `07_docs/roadmap.md` | `docs/roadmap.md` | unique scope/dependency owner |
| `07_docs/development_environment.md` | `docs/development_environment.md` | operator-facing environment notes |
| `07_docs/work_orders/*` | `docs/work_orders/*` | execution and handoff records |

## Reference policy

- Current entry points and module READMEs point to `systems_engineering/` or
  `docs/`; there is no fallback search based on the caller's working directory.
- Historical report text that records what an earlier validator or review
  required may retain `07_docs/...` as evidence of the old contract. Those are
  not current links and are covered by the exact compatibility test.
- G0 v1/v2 JSON bytes, thresholds, IDs, approval fields and evidence values are
  not rewritten as part of this migration. Only the validator's location
  mapping changes how the frozen historical source is checked.

## Verification

The migration checker and positive/negative fixtures live in
`tools/systems_engineering/`. Markdown links are checked against the current
tree, while the historical compatibility exception is required to remain
exact. Model sources are rendered with the documented Mermaid check for the
reviewed commit: Mermaid Live Editor `v12.1.0` was used to render all five
views and inspect node labels, arrows, status wording and reading order. The
renderings are temporary and are not authoritative repository assets.
