# B0 truth/control model slice — generated review view

**Generated from:** `contract/pilot_structure.json` and the `sysmlpy` AST of `b0_truth_control_slice.sysml`.

This is a textual project reading aid, not a SysML graphical notation view, simulation, or conformance claim.

## Declared model elements

| Identity | Display name | Parsed type | Scope | Related records | Intended bounded role |
|---|---|---|---|---|---|
| `PILOT-MODEL-ACTUATOR-01` | Actuator | `part_definition` | planned G2 controller interface boundary |  | B0 actuator role. |
| `PILOT-MODEL-B0-BOUNDARY-01` | B0 phase-one boundary | `part_definition` | current B0 phase-one bounded attitude experiment | `PILOT-ONLY-LEGACY-04`, `PILOT-ONLY-NEED-01` | Bounded phase-one attitude experiment boundary. |
| `PILOT-MODEL-COMMAND-SOURCE-01` | Command source | `part_definition` | current B0 phase-one bounded attitude experiment |  | Bounded experiment command source. |
| `PILOT-MODEL-CONTROLLER-01` | Planned controller | `part_definition` | planned G2 controller interface boundary | `PILOT-ONLY-G2-05`, `PILOT-ONLY-INTERFACE-02` | Planned G2 controller boundary only. |
| `PILOT-MODEL-ESTIMATOR-01` | Estimator | `part_definition` | current B0 truth-isolation boundary |  | B0 estimator role. |
| `PILOT-MODEL-EVALUATOR-01` | Independent evaluator | `part_definition` | current B0 truth-isolation boundary |  | Independent evaluation role. |
| `PILOT-MODEL-IF-ACTUATOR-CONTROLLER-01` | Actuator to controller interface | `interface_definition` | planned G2 controller interface boundary |  | Paired-feedback-to-controller interface. |
| `PILOT-MODEL-IF-COMMAND-CONTROLLER-01` | Command to controller interface | `interface_definition` | planned G2 controller interface boundary |  | Command-to-controller interface. |
| `PILOT-MODEL-IF-CONTROLLER-ACTUATOR-01` | Controller to actuator interface | `interface_definition` | planned G2 controller interface boundary | `PILOT-ONLY-G2-05` | Paired-command interface; the actuator uses limited target as its dynamics input. |
| `PILOT-MODEL-IF-ESTIMATE-CONTROLLER-01` | Estimate to controller interface | `interface_definition` | planned G2 controller interface boundary |  | State-estimate-to-controller interface. |
| `PILOT-MODEL-IF-IMU-ESTIMATOR-01` | IMU to estimator interface | `interface_definition` | current B0 truth-isolation boundary |  | IMU-sample-to-estimator interface. |
| `PILOT-MODEL-IF-TRUTH-EVALUATOR-01` | Truth to evaluator interface | `interface_definition` | current B0 truth-isolation boundary | `PILOT-ONLY-INTERFACE-02` | Plant-truth-to-evaluator interface. |
| `PILOT-MODEL-IMU-01` | IMU | `part_definition` | current B0 truth-isolation boundary |  | B0 sensor role. |
| `PILOT-MODEL-ITEM-ACTUATOR-FEEDBACK-01` | Actuator feedback item | `item_definition` | planned G2 controller interface boundary |  | Paired actuator feedback item provided to the controller. |
| `PILOT-MODEL-ITEM-COMMAND-01` | Command item | `item_definition` | current B0 phase-one bounded attitude experiment |  | Command item exposed to the planned controller. |
| `PILOT-MODEL-ITEM-IMU-SAMPLE-01` | IMU sample item | `item_definition` | current B0 phase-one bounded attitude experiment |  | Sensor sample item provided to the estimator. |
| `PILOT-MODEL-ITEM-LIMITED-TARGET-01` | Limited target item | `item_definition` | planned G2 controller interface boundary |  | Limited actuator target and sole dynamics-input field within the paired command. |
| `PILOT-MODEL-ITEM-PAIRED-TORQUE-COMMAND-01` | Paired torque command | `item_definition` | planned G2 controller interface boundary |  | One-due-tick bundle of requested torque, limited target, and saturation status; actuator dynamics consume only the limited target. |
| `PILOT-MODEL-ITEM-PLANT-TRUTH-01` | Plant truth item | `item_definition` | current B0 truth-isolation boundary |  | Plant truth item restricted to plant, sensor, and evaluator responsibilities. |
| `PILOT-MODEL-ITEM-SATURATION-STATUS-01` | Saturation status item | `item_definition` | planned G2 controller interface boundary |  | Saturation-status field paired with request and limited target at the same due tick. |
| `PILOT-MODEL-ITEM-STATE-ESTIMATE-01` | State estimate item | `item_definition` | planned G2 controller interface boundary |  | Estimated state item provided to the controller. |
| `PILOT-MODEL-ITEM-TORQUE-REQUEST-01` | Torque request item | `item_definition` | planned G2 controller interface boundary |  | Requested torque field retained inside the paired command for review; it is not the actuator dynamics input. |
| `PILOT-MODEL-PLANT-01` | Plant | `part_definition` | current B0 phase-one bounded attitude experiment |  | B0 plant role. |
| `PILOT-MODEL-REQ-PROXY-G2-05` | G2 record proxy | `requirement_definition` | planned G2 controller interface boundary | `PILOT-ONLY-G2-05` | Reference-only proxy for the planned G2 pilot record. |
| `PILOT-MODEL-VER-BOUNDARY-01` | Boundary verification definition | `verification_definition` | current B0 phase-one bounded attitude experiment | `PILOT-ONLY-ACCEPTANCE-03` | Planned boundary review definition. |
| `PILOT-MODEL-VER-TRUTH-01` | Truth verification definition | `verification_definition` | current B0 truth-isolation boundary |  | Planned truth-isolation review definition. |
| `PILOT-MODEL-VIEW-B0-STRUCTURE-01` | B0 structure view usage | `view_usage` | current B0 phase-one bounded attitude experiment | `PILOT-ONLY-NEED-01` | Standard SysML v2 textual view usage exposing the same B0 boundary modeled in this source. |
| `PILOT-MODEL-VIEWDEF-B0-STRUCTURE-01` | B0 structure view definition | `view_definition` | current B0 phase-one bounded attitude experiment |  | Standard SysML v2 textual view definition for the bounded structure review. |

## Parsed flow endpoints

- `PILOT-MODEL-ACTUATOR-01.feedback` → `PILOT-MODEL-CONTROLLER-01.feedback`
- `PILOT-MODEL-COMMAND-SOURCE-01.command` → `PILOT-MODEL-CONTROLLER-01.command`
- `PILOT-MODEL-CONTROLLER-01.paired_command` → `PILOT-MODEL-ACTUATOR-01.paired_command`
- `PILOT-MODEL-ESTIMATOR-01.estimate` → `PILOT-MODEL-CONTROLLER-01.estimate`
- `PILOT-MODEL-IMU-01.sample` → `PILOT-MODEL-ESTIMATOR-01.sample`
- `PILOT-MODEL-PLANT-01.truth` → `PILOT-MODEL-EVALUATOR-01.truth`
- `PILOT-MODEL-PLANT-01.truth` → `PILOT-MODEL-IMU-01.truth`

## Standard textual view declaration

- View definition: `PILOT-MODEL-VIEWDEF-B0-STRUCTURE-01` (`view def`).
- View usage: `PILOT-MODEL-VIEW-B0-STRUCTURE-01` (`view`) exposes `PILOT-MODEL-B0-BOUNDARY-01` from the same SysML source.
- Notation basis: OMG SysML v2.0 Part 1 §8.2.2.26 (Views and Viewpoints Textual Notation).
- Tool boundary: the fixed parser confirms both view identities/types but does not retain the expose relationship in its AST or render graphical notation; the source declaration remains the review authority for that expose statement.

## Cross-domain trace links

| Relation | Source | Target | Status boundary |
|---|---|---|---|
| `models` | `PILOT-ONLY-NEED-01` | `PILOT-MODEL-B0-BOUNDARY-01` | project_extension / planned where stated |
| `models` | `PILOT-ONLY-INTERFACE-02` | `PILOT-MODEL-IF-TRUTH-EVALUATOR-01` | project_extension / planned where stated |
| `models` | `PILOT-ONLY-INTERFACE-02` | `PILOT-MODEL-CONTROLLER-01` | project_extension / planned where stated |
| `models` | `PILOT-ONLY-ACCEPTANCE-03` | `PILOT-MODEL-VER-BOUNDARY-01` | project_extension / planned where stated |
| `models` | `PILOT-ONLY-LEGACY-04` | `PILOT-MODEL-B0-BOUNDARY-01` | project_extension / planned where stated |
| `models` | `PILOT-ONLY-G2-05` | `PILOT-MODEL-CONTROLLER-01` | project_extension / planned where stated |
| `models` | `PILOT-ONLY-G2-05` | `PILOT-MODEL-REQ-PROXY-G2-05` | project_extension / planned where stated |
| `models` | `PILOT-ONLY-G2-05` | `PILOT-MODEL-IF-CONTROLLER-ACTUATOR-01` | project_extension / planned where stated |
| `models` | `PILOT-ONLY-NEED-01` | `PILOT-MODEL-VIEW-B0-STRUCTURE-01` | project_extension / planned where stated |
| `allocated_to` | `PILOT-ONLY-NEED-01` | `PILOT-DEV-REVIEW-BOUNDARY-01` | project_extension / planned where stated |
| `allocated_to` | `PILOT-ONLY-INTERFACE-02` | `PILOT-DEV-INTEGRATION-ADAPTER-01` | project_extension / planned where stated |
| `allocated_to` | `PILOT-ONLY-G2-05` | `PILOT-DEV-CONTROLLER-CORE-01` | project_extension / planned where stated |
| `specified_by` | `PILOT-ONLY-NEED-01` | `PILOT-VER-BOUNDARY-01` | project_extension / planned where stated |
| `specified_by` | `PILOT-ONLY-INTERFACE-02` | `PILOT-VER-TRUTH-01` | project_extension / planned where stated |
| `specified_by` | `PILOT-ONLY-ACCEPTANCE-03` | `PILOT-VER-G0-REFERENCE-01` | project_extension / planned where stated |
| `specified_by` | `PILOT-ONLY-LEGACY-04` | `PILOT-VER-LEGACY-01` | project_extension / planned where stated |
| `specified_by` | `PILOT-ONLY-G2-05` | `PILOT-VER-G2-INTERFACE-01` | project_extension / planned where stated |
| `development_checked_by` | `PILOT-DEV-REVIEW-BOUNDARY-01` | `PILOT-VER-BOUNDARY-01` | project_extension / planned where stated |
| `development_checked_by` | `PILOT-DEV-INTEGRATION-ADAPTER-01` | `PILOT-VER-TRUTH-01` | project_extension / planned where stated |
| `development_checked_by` | `PILOT-DEV-CONTROLLER-CORE-01` | `PILOT-VER-G2-INTERFACE-01` | project_extension / planned where stated |

## Parser analysis warnings

The fixed parser reports the following non-error warnings; they are retained as a tool limitation rather than suppressed:

- `SemanticIssue(severity='warning', code='NAMING_CONVENTION', message="Definition ''PILOT-MODEL-ITEM-COMMAND-01'' should be PascalCase (e.g., ''PILOT-MODEL-ITEM-COMMAND-01'')", element=Item(definition=True, name="'PILOT-MODEL-ITEM-COMMAND-01'"), reference="'PILOT-MODEL-ITEM-COMMAND-01'")`
- `SemanticIssue(severity='warning', code='NAMING_CONVENTION', message="Definition ''PILOT-MODEL-PLANT-01'' should be PascalCase (e.g., ''PILOT-MODEL-PLANT-01'')", element=Part(definition=True, name="'PILOT-MODEL-PLANT-01'"), reference="'PILOT-MODEL-PLANT-01'")`
- `SemanticIssue(severity='warning', code='NAMING_CONVENTION', message="Definition ''PILOT-MODEL-IMU-01'' should be PascalCase (e.g., ''PILOT-MODEL-IMU-01'')", element=Part(definition=True, name="'PILOT-MODEL-IMU-01'"), reference="'PILOT-MODEL-IMU-01'")`
- `SemanticIssue(severity='warning', code='NAMING_CONVENTION', message="Definition ''PILOT-MODEL-ESTIMATOR-01'' should be PascalCase (e.g., ''PILOT-MODEL-ESTIMATOR-01'')", element=Part(definition=True, name="'PILOT-MODEL-ESTIMATOR-01'"), reference="'PILOT-MODEL-ESTIMATOR-01'")`
- `SemanticIssue(severity='warning', code='NAMING_CONVENTION', message="Definition ''PILOT-MODEL-CONTROLLER-01'' should be PascalCase (e.g., ''PILOT-MODEL-CONTROLLER-01'')", element=Part(definition=True, name="'PILOT-MODEL-CONTROLLER-01'"), reference="'PILOT-MODEL-CONTROLLER-01'")`
- `SemanticIssue(severity='warning', code='NAMING_CONVENTION', message="Definition ''PILOT-MODEL-ACTUATOR-01'' should be PascalCase (e.g., ''PILOT-MODEL-ACTUATOR-01'')", element=Part(definition=True, name="'PILOT-MODEL-ACTUATOR-01'"), reference="'PILOT-MODEL-ACTUATOR-01'")`
- `SemanticIssue(severity='warning', code='NAMING_CONVENTION', message="Definition ''PILOT-MODEL-EVALUATOR-01'' should be PascalCase (e.g., ''PILOT-MODEL-EVALUATOR-01'')", element=Part(definition=True, name="'PILOT-MODEL-EVALUATOR-01'"), reference="'PILOT-MODEL-EVALUATOR-01'")`
- `SemanticIssue(severity='warning', code='NAMING_CONVENTION', message="Definition ''PILOT-MODEL-REQ-PROXY-G2-05'' should be PascalCase (e.g., ''PILOT-MODEL-REQ-PROXY-G2-05'')", element=Requirement(definition=True, name="'PILOT-MODEL-REQ-PROXY-G2-05'"), reference="'PILOT-MODEL-REQ-PROXY-G2-05'")`
- `SemanticIssue(severity='warning', code='NAMING_CONVENTION', message="Definition ''PILOT-MODEL-VER-BOUNDARY-01'' should be PascalCase (e.g., ''PILOT-MODEL-VER-BOUNDARY-01'')", element=VerificationCase(definition=True, name="'PILOT-MODEL-VER-BOUNDARY-01'"), reference="'PILOT-MODEL-VER-BOUNDARY-01'")`
- `SemanticIssue(severity='warning', code='NAMING_CONVENTION', message="Definition ''PILOT-MODEL-VER-TRUTH-01'' should be PascalCase (e.g., ''PILOT-MODEL-VER-TRUTH-01'')", element=VerificationCase(definition=True, name="'PILOT-MODEL-VER-TRUTH-01'"), reference="'PILOT-MODEL-VER-TRUTH-01'")`
- `SemanticIssue(severity='warning', code='NAMING_CONVENTION', message="Definition ''PILOT-MODEL-B0-BOUNDARY-01'' should be PascalCase (e.g., ''PILOT-MODEL-B0-BOUNDARY-01'')", element=Part(definition=True, name="'PILOT-MODEL-B0-BOUNDARY-01'"), reference="'PILOT-MODEL-B0-BOUNDARY-01'")`
