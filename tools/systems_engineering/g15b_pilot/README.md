# G1.5-B phase-one structured requirements/model pilot

## Status and boundary

This directory is a **non-authoritative phase-one fixture** for the G1.5-B method/tooling decision. It contains exactly five `PILOT-ONLY-*` candidate records. They do not allocate B0 requirement IDs, contribute to formal coverage, replace legacy requirements, assert G2/G3 implementation, or freeze a joint baseline.

The execution contract is the [G1.5-B structured pilot work order](../../../docs/work_orders/B0_G1_5_B_structured_sysml_pilot_work_order.md). The historical phase-one comparison decision is retained in the [decision package](../../../systems_engineering/reports/b0/g15b_phase1_requirements_tooling_numbering_decision.md); the current structured increment is added there as a separate, review-pending section rather than retroactively changing its history.

The method, field dictionary, relation rules, standard clauses, and fixed-tool limitations are in [the B0 modelling conventions](../../../systems_engineering/models/modeling_conventions.md).

## Authority and controlled outputs

`contract/pilot_structure.json` is the only editable source for the five record bodies and their structured review metadata. Its JSON Schema is `contract/pilot_structure.schema.json`.

| Source / output | Role |
|---|---|
| `contract/pilot_structure.json` | Unique editable record body, locator, allocation, verification, evidence-status, and cross-domain-relation source. |
| `model/b0_truth_control_slice.sysml` | Editable bounded textual SysML source; it does not duplicate record bodies. |
| `strictdoc/b0_phase1_pilot.sdoc` | Controlled generated projection of native fields and `Parent` hierarchy. Do not edit it. |
| `lightweight/b0_phase1_pilot.md` | Controlled generated no-tool reading view. Do not edit it. |
| `model/b0_truth_control_slice_view.md` | Controlled generated parser-AST reading view. It is not SysML graphical notation. |
| `tests/fixtures/prestructured_semantic_baseline.json` | Test-only immutable migration oracle from `ce350a488ff9b0c50cf32bb4d22c5833b33db597`; never an editable record authority. |
| Temporary HTML / screenshot | Review-only output outside Git; never an evidence artifact. |

StrictDoc 0.30.1 accepts only its fixed native requirement fields. The rich structured data therefore remains in the JSON contract and is displayed by the generated Markdown/HTML views rather than being hidden in `COMMENT`.

## Isolated reproduction

Use an isolated environment; do not install these packages into `.venv-b0`, the Windows literature environment, or a project-wide development environment. The fixed dependencies are in `requirements/g15b-pilot.txt`:

```text
<isolated-python> -m pip install -r requirements/g15b-pilot.txt
<isolated-python> -B tools/systems_engineering/g15b_pilot/build_pilot_views.py --write
<isolated-python> -B tools/systems_engineering/check_g15b_phase1_pilot.py
<isolated-strictdoc> export --config tools/systems_engineering/g15b_pilot/strictdoc/strictdoc_config.py --formats=html --output-dir <temporary-output> --no-parallelization tools/systems_engineering/g15b_pilot/strictdoc
<isolated-python> -m pytest -q tools/systems_engineering/g15b_pilot/tests -p no:cacheprovider
```

The checker runs the fixed `sysmlpy==0.33.2` parser/analyser over the adopted textual subset and consumes its AST; it does not parse SysML with project regexes. `sysmlpy` is a third-party parser, not an OMG reference implementation or a graphical/execution platform. Its documented parser limitations and non-error naming warnings are retained in the generated model view rather than suppressed.

For a review-only local web page, generate a fresh temporary output named for the exact reviewed SHA:

```text
<isolated-python> -B tools/systems_engineering/g15b_pilot/build_pilot_views.py --preview-output <temporary-SHA-directory>
```

Serve only that fresh directory on loopback for the required viewport review. Do not commit the generated HTML, screenshots, or any browser output.
