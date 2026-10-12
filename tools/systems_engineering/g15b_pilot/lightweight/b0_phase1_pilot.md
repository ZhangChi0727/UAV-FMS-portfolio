# G1.5-B phase-one structured pilot

**Generated review projection.** Edit `contract/pilot_structure.json`; do not edit this Markdown file.

This is a non-authoritative five-record trial. It does not freeze formal requirements, assert G2/G3 implementation, or claim execution evidence.

## PILOT-ONLY-NEED-01

- **Title:** Bounded attitude experiment use
- **Record type:** user_need
- **Approval status:** candidate_only
- **Applicability:** applicable
- **Scope:** current B0 bounded attitude experiments only; excludes hardware, flight, and unactivated extensions
- **Parent:** none
- **Evidence status:** planned/not_run
- **Source locators:**
  - `systems_engineering/project_charter.md#purpose`
  - `systems_engineering/development_baseline.md#single-objective`
- **Cross-domain links:**
  - `models` → `PILOT-MODEL-B0-BOUNDARY-01` (project_extension)
  - `allocated_to` → `PILOT-DEV-REVIEW-BOUNDARY-01` (project_extension)
  - `specified_by` → `PILOT-VER-BOUNDARY-01` (project_extension)

### Statement

The B0 system shall support a configured, repeatable bounded attitude experiment for engineering review without claiming full-flight capability.

### Rationale

This is a source-format trial of a user-need record. It is not a formal B0 requirement and is not part of coverage accounting.

### Planned acceptance condition

Planned inspection confirms the declared experiment boundary and exclusions are present.

## PILOT-ONLY-INTERFACE-02

- **Title:** Runtime truth isolation
- **Record type:** system_constraint
- **Approval status:** candidate_only
- **Applicability:** applicable
- **Scope:** current B0 after explicit reset initialization
- **Parent:** PILOT-ONLY-NEED-01
- **Evidence status:** planned/not_run
- **Source locators:**
  - `05_integration/b0/configs/b0_g0_contract.v2.json#/plant_contract/truth_visibility`
  - `05_integration/b0/configs/b0_g0_contract.v2.json#/controller_contract/truth_inputs_forbidden`
  - `systems_engineering/models/architecture.md#modular-boundaries`
- **Cross-domain links:**
  - `models` → `PILOT-MODEL-IF-TRUTH-EVALUATOR-01` (project_extension)
  - `models` → `PILOT-MODEL-CONTROLLER-01` (project_extension)
  - `allocated_to` → `PILOT-DEV-INTEGRATION-ADAPTER-01` (project_extension)
  - `specified_by` → `PILOT-VER-TRUTH-01` (project_extension)

### Statement

After explicit reset initialization, the estimator and controller shall not receive live truth as a runtime input; truth is limited to plant, sensor, and evaluation responsibilities.

### Rationale

This trial represents an interface constraint and a child relationship without treating existing component behavior as the sole source of the obligation.

### Planned acceptance condition

Planned inspection verifies declared runtime inputs exclude live truth and evaluation remains independent.

## PILOT-ONLY-ACCEPTANCE-03

- **Title:** Frozen acceptance-field reference
- **Record type:** system_constraint
- **Approval status:** candidate_only
- **Applicability:** applicable
- **Scope:** current B0 signed three-axis step assessment; configuration evidence remains proposed_not_executed
- **Parent:** PILOT-ONLY-NEED-01
- **Evidence status:** planned/not_run
- **Source locators:**
  - `05_integration/b0/configs/b0_g0_contract.v2.json#/acceptance_policy/metric_definitions`
  - `05_integration/b0/configs/b0_g0_contract.v2.json#/scenarios/6/id`
  - `05_integration/b0/configs/b0_g0_contract.v2.json#/scenarios/6/acceptance`
- **Cross-domain links:**
  - `models` → `PILOT-MODEL-VER-BOUNDARY-01` (project_extension)
  - `specified_by` → `PILOT-VER-G0-REFERENCE-01` (project_extension)

### Statement

Any assessment of the signed three-axis step scenario shall cite the approved G0 v2 configuration fields for its event window and metrics instead of copying numerical thresholds into a second requirement source.

### Rationale

This trial represents a performance/acceptance reference while preserving the JSON contract as the sole parameter source and avoiding a false performance result.

### Planned acceptance condition

Planned inspection verifies each assessment points to a versioned JSON field and does not duplicate a numeric threshold.

## PILOT-ONLY-LEGACY-04

- **Title:** Preserved legacy control applicability
- **Record type:** applicability_record
- **Approval status:** candidate_only
- **Applicability:** not_applicable
- **Scope:** current B0 only; CTL-REQ-001 and CTL-REQ-002 remain preserved for their historical scopes under the approved disposition
- **Parent:** PILOT-ONLY-NEED-01
- **Evidence status:** planned/not_run
- **Source locators:**
  - `systems_engineering/requirements/legacy_requirements.md#control-requirements`
  - `systems_engineering/reports/b0/g0_approval_decision.md#决定`
  - `05_integration/b0/configs/b0_g0_contract.v2.json#/contract_status/approval_record/ctl_applicability`
- **Approval locator:** `systems_engineering/reports/b0/g0_approval_decision.md#决定`
- **Cross-domain links:**
  - `models` → `PILOT-MODEL-B0-BOUNDARY-01` (project_extension)
  - `specified_by` → `PILOT-VER-LEGACY-01` (project_extension)

### Statement

For current B0, the applicability record shall preserve CTL-REQ-001 and CTL-REQ-002 unchanged and record their approved not-applicable status without claiming that either legacy performance threshold is satisfied.

### Rationale

This trial represents a non-applicable legacy relationship. The legacy identifiers remain references only and are never candidate identifiers for reuse.

### Planned acceptance condition

Planned inspection verifies both legacy identifiers, their decision locator, and the absence of a satisfaction claim.

## PILOT-ONLY-G2-05

- **Title:** Planned controller interface boundary
- **Record type:** component_constraint
- **Approval status:** candidate_only
- **Applicability:** applicable
- **Scope:** planned G2 controller only; not an implemented or accepted component
- **Parent:** PILOT-ONLY-INTERFACE-02
- **Evidence status:** planned/not_run
- **Source locators:**
  - `05_integration/b0/configs/b0_g0_contract.v2.json#/controller_contract`
  - `05_integration/b0/configs/b0_g0_contract.v2.json#/interface_contract/messages/torque_command`
  - `05_integration/b0/configs/b0_g0_contract.v2.json#/interface_contract/component_calls/controller`
- **Cross-domain links:**
  - `models` → `PILOT-MODEL-CONTROLLER-01` (project_extension)
  - `models` → `PILOT-MODEL-REQ-PROXY-G2-05` (project_extension)
  - `allocated_to` → `PILOT-DEV-CONTROLLER-CORE-01` (project_extension)
  - `specified_by` → `PILOT-VER-G2-INTERFACE-01` (project_extension)

### Statement

The planned G2 controller shall consume the declared command, state estimate, and paired actuator feedback; it shall expose requested torque, limited target, and saturation status under the approved reset and step contract.

### Rationale

This is a planned component candidate used to test truthful planned/not-run status. It does not claim a G2 implementation or closed-loop evidence.

### Planned acceptance condition

Planned G2 verification defines inputs, reset and step behavior, an independent oracle, and execution evidence before any pass claim.
