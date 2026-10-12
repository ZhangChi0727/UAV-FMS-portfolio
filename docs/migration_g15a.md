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
| `07_docs/work_orders/B0_G0_PR11_repair_work_order.md` | `docs/work_orders/B0_G0_PR11_repair_work_order.md` | execution and handoff record |
| `07_docs/work_orders/B0_G0_PR11_round2_repair.md` | `docs/work_orders/B0_G0_PR11_round2_repair.md` | execution and handoff record |
| `07_docs/work_orders/B0_G0_work_order.md` | `docs/work_orders/B0_G0_work_order.md` | execution and handoff record |
| `07_docs/work_orders/B0_G1_development_readiness.md` | `docs/work_orders/B0_G1_development_readiness.md` | execution and handoff record |
| `07_docs/work_orders/B0_G1_work_order.md` | `docs/work_orders/B0_G1_work_order.md` | execution and handoff record |
| `07_docs/work_orders/B0_PR11_v2_G1_closeout.md` | `docs/work_orders/B0_PR11_v2_G1_closeout.md` | execution and handoff record |
| `07_docs/work_orders/B0_work_order.md` | `docs/work_orders/B0_work_order.md` | execution and handoff record |
| `07_docs/work_orders/development_readiness.md` | `docs/work_orders/development_readiness.md` | execution and handoff record |

The previous wildcard mapping is intentionally not used: every historical work
order is listed so that an omitted or colliding target is review-visible.

## New files in this increment

These files have no `07_docs/` predecessor and are additions, not migrations:

| New path | Responsibility |
|---|---|
| `docs/migration_g15a.md` | migration map, compatibility policy and verification record |
| `docs/work_orders/B0_G1_5_A_work_order.md` | G1.5-A execution and acceptance scope |
| `docs/work_orders/B0_G1_5_work_order.md` | G1.5 sequence and handoff scope |
| `systems_engineering/README.md` | first-level reader entry and navigation |
| `systems_engineering/models/system_views.md` | five editable B0 system views |
| `systems_engineering/reports/current_status.md` | current status snapshot and evidence route |
| `tools/systems_engineering/check_governance.py` | dependency-free governance checker |
| `tools/systems_engineering/governance_manifest.json` | required-file/model/obligation manifest |
| `tools/systems_engineering/tests/fixtures/valid_manifest.json` | positive checker fixture |
| `tools/systems_engineering/tests/fixtures/missing_evidence.json` | negative checker fixture |
| `tools/systems_engineering/tests/fixtures/unknown_model.json` | negative checker fixture |
| `tools/systems_engineering/tests/fixtures/bad_migration.json` | negative checker fixture |
| `tools/systems_engineering/tests/test_governance.py` | checker and link-test suite |

## Files modified in place

The following paths were not migrated; they were modified only to update active
links, path compatibility, status/navigation, or the CI gate:

| Path | Reason |
|---|---|
| `.github/workflows/ci.yml` | add the isolated governance checker/test job |
| `01_simulation/README.md` | update systems-engineering links |
| `02_estimation/README.md` | update systems-engineering links |
| `03_control/README.md` | update systems-engineering links |
| `04_fault_detection/README.md` | update systems-engineering links |
| `05_integration/README.md` | update systems-engineering links |
| `05_integration/b0/tests/test_config_validation.py` | test migrated G0 approval resolution |
| `05_integration/b0/validate_config.py` | resolve the exact historical G0 source to its migrated report |
| `06_safety/README.md` | update systems-engineering links |
| `AGENTS.md` | point mandatory document paths at the new entry points |
| `README.md` | expose the first-level systems-engineering route and truthful status |
| `RESULTS.md` | link the current status report without duplicating evidence |

For the reviewed base-to-head range, the complete `git diff --name-status`
inventory is therefore: the migrated rows above, the additions above, and the
in-place modifications above; there are no unaccounted deletions. This audit
does not change the frozen G0 JSON bytes or thresholds.

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
renderings are temporary and are not authoritative repository assets. After the
G1.5-A review correction, the interface view was rendered again in the same
Mermaid Live Editor `v12.1.0`; the controller input set, sole limiter, paired
feedback loop and truth-boundary arrows were visually inspected before the
follow-up review commit.
