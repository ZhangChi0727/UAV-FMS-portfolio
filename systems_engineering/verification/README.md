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
record toward requirement satisfaction only when it is a complete pass, the
exact evidence bytes are present in an explicitly supplied cache and match the
recorded digest, retention is current, two-sided version applicability is
established, and independent review is accepted. A remote label or URI alone is
not verification: unavailable remote bytes remain `remote_unverified` and never
count toward acceptance. Fixture records are prohibited in the production ledger.

Relevant-file applicability hashes bind both the evidence source commit and the
controlled target commit. The checker reads each revision through Git, confirms
the declared dependency closure has identical bytes, and then confirms committed
`HEAD` still matches the target. It deliberately ignores uncommitted worktree
bytes, so checkout line endings and unrelated local edits cannot change identity.

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
