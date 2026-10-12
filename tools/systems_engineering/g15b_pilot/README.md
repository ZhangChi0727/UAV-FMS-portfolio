# G1.5-B phase-one requirements-tooling pilot

## Status and boundary

This directory is a **non-authoritative phase-one fixture** for the G1.5-B
tool/source-format and numbering decision. It contains exactly five
`PILOT-ONLY-*` candidate records. They do not allocate B0 requirement IDs,
contribute to requirements coverage, replace a legacy requirement, or assert a
frozen joint baseline.

The execution contract is the [G1.5-B work order](../../../docs/work_orders/B0_G1_5_B_work_order.md).
The evaluation outcome and proposed numbering rule are in the
[phase-one decision package](../../../systems_engineering/reports/b0/g15b_phase1_requirements_tooling_numbering_decision.md).

## Trial sources

- `strictdoc/b0_phase1_pilot.sdoc` is an editable native StrictDoc source.
- `strictdoc/strictdoc_config.py` and `strictdoc/presentation.css` are the
  source-owned, StrictDoc-0.30.1-native presentation configuration. They make
  the one-document pilot easier to review without changing a record, its
  hierarchy, or any generated link.
- `lightweight/b0_phase1_pilot.md` is an equivalent, readable lightweight-text
  comparison source.

The two files intentionally duplicate only the five trial records so that the
checker can expose source-format drift. They are not two active requirement
sources. Phase two may select at most one authoritative format only after PA
technical review and explicit maintainer approval of the formal numbering rule.

## Isolated reproduction

Use a temporary environment rather than `.venv-b0` or a literature environment:

```text
/home/chi/src/uav-fms-portfolio/.venv-b0/bin/python -m venv /tmp/uav-fms-g15b-strictdoc
/tmp/uav-fms-g15b-strictdoc/bin/python -m pip install -r requirements/g15b-pilot.txt
/tmp/uav-fms-g15b-strictdoc/bin/strictdoc export --config tools/systems_engineering/g15b_pilot/strictdoc/strictdoc_config.py tools/systems_engineering/g15b_pilot/strictdoc --formats=html --output-dir /tmp/uav-fms-g15b-html --no-parallelization
/tmp/uav-fms-g15b-strictdoc/bin/python tools/systems_engineering/check_g15b_phase1_pilot.py
/tmp/uav-fms-g15b-strictdoc/bin/python -m pytest -q tools/systems_engineering/g15b_pilot/tests/test_g15b_phase1_pilot.py tools/systems_engineering/g15b_pilot/tests/test_g15b_native_strictdoc.py
```

The `.sdoc` and Markdown sources remain readable without StrictDoc. StrictDoc
copies the source-owned stylesheet to `html/_static/custom.css`; do not edit
that generated copy. Generated HTML and temporary test outputs belong under
`/tmp` and are not committed. Structural tests verify that the configured asset
is exported; a person still reviews the temporary HTML for visual readability.
