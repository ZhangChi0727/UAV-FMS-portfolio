# B0 verification evidence layer

The frozen planning authority remains
[`b0_verification_specifications.json`](b0_verification_specifications.json).
Its 29 `not_run` records describe planned verification and are not overwritten
by execution results.

Current execution evidence is recorded in
[`b0_execution_evidence.json`](b0_execution_evidence.json) under the structural
contract in [`b0_execution_evidence.schema.json`](b0_execution_evidence.schema.json).
The ledger separates:

- execution result;
- raw-evidence availability and identity;
- applicability to the current implementation/configuration bytes;
- independent review acceptance.

A passing command alone does not satisfy a requirement. The checker counts a
record toward requirement satisfaction only when it is a complete pass, its
evidence is available, its version applicability is established, and its review
status is accepted. Fixtures never enter production totals.

Relevant-file applicability hashes use committed Git bytes rather than working
tree bytes, so Windows/Unix checkout line-ending conversion cannot change the
recorded identity.

Run the offline gate from the repository root:

```text
python tools/systems_engineering/check_g15c_traceability.py --check-report --json
```

To build an uncommitted reader artifact:

```text
python tools/systems_engineering/check_g15c_traceability.py --html-output <temporary-directory>/index.html
```

The CI artifact contains this HTML view. Generated HTML, screenshots and raw
logs stay outside the repository. Future external research suites may only
contribute through the same version, criterion, evidence-hash, applicability
and review fields; G1.5-C does not execute or write to those suites.
