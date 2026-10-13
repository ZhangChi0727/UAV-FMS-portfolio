# G1.5-C input contract — candidate

Status: **candidate pending PA review and D2**. G1.5-C is not started by this
document, and this is not a verification result or C-ready declaration.

## Machine-readable inputs

| Authority | Path | Role |
|---|---|---|
| Requirement text and forward allocations | `systems_engineering/requirements/b0_requirements.json` | single normative requirement source |
| Requirement schema | `systems_engineering/requirements/b0_requirements.schema.json` | field/shape contract |
| Identity registry | `systems_engineering/requirements/b0_id_registry.json` | allocation, retirement and next ordinal |
| System model | `systems_engineering/models/b0_system.sysml` | stable elements and message-flow structure |
| Verification catalogue | `systems_engineering/verification/b0_verification_specifications.json` | planned methods, oracles and reverse allocations |
| Numerical/configuration authority | `05_integration/b0/configs/b0_g0_contract.v2.json` | approved G0 values, timing and acceptance definitions |

The later S/M manifest will bind the exact candidate blobs. Until D2, consumers
must treat every formal entry as `candidate_pending_d2`.

## Identity and relation contract

- Requirement identities use nonreusable `B0-REQ-NNNN`; type and level are
  fields, not encoded in the ID. Model identities use `B0-MODEL-*` and
  verification identities use `B0-VER-*`.
- Requirements own source, parent, model and verification forward links.
  Verification specifications own their requirement reverse links. The checker
  requires exact bidirectional agreement and allows intentional many-to-many
  allocations.
- G0 configuration owns numerical values. Implementation paths/symbols will be
  owned by their implementation increments. Execution evidence and verdicts
  remain absent until actually produced and retained.

## Planned versus existing evidence

All 29 catalogue entries are defined but `not_run`; their null results are
mandatory. G0 approval and G1 component artifacts may be source or historical
evidence, but do not automatically satisfy newly allocated requirements. C must
record a scope/difference decision before presenting any historical artifact as
support.

## G1.5-C responsibility boundary

C may add result/evidence lifecycle validation, expiry checks, report
presentation and CI linkage against the D2-approved S/M/A baseline. It must not
change frozen requirement/model/verification semantics, invent results, infer
pass from a link, or collapse replay, board execution, real-time HIL and flight
into one evidence class. Changed semantics return to a new joint-baseline
candidate and approval cycle.

## Deterministic consumer rehearsal

From repository root in the fixed isolated Python environment:

```text
python tools/systems_engineering/check_g15b_joint_baseline.py
python tools/systems_engineering/build_g15b_joint_views.py --check
pytest -q tools/systems_engineering/tests/test_g15b_joint_baseline.py
```

The candidate review found no critical interpretation TBD in purpose, paired
torque semantics, truth isolation, reset/scheduling, verification allocation or
legacy applicability. This is a design-review conclusion, not product evidence.
