# B0 formal requirements

The G1.5-B candidate baseline uses one JSON-led requirement authority. Its use
was approved at D1; individual requirement bodies and the joint baseline remain
candidate until D2.

## Authority map

- `b0_requirements.json` owns requirement bodies, source references,
  applicability, allocation/model/verification references, lifecycle/change
  state and directed cross-domain relations.
- `b0_id_registry.json` owns allocated, retired and superseded B0 requirement
  identities. An allocated ordinal is never reused.
- `b0_requirements.schema.json` owns structural shape. The project checker owns
  cross-object and repository rules.
- `../models/b0_system.sysml` owns native model structure and relationships.
- `../verification/b0_verification_specifications.json` owns verification
  provision bodies. Execution results do not belong in either planning source.
- `../../05_integration/b0/configs/b0_g0_contract.v2.json` remains the sole
  authority for approved G0 numerical/configuration values.
- `generated/` contains deterministic reader projections. Never edit them as
  requirement sources.

## Read and rebuild

The JSON files are directly readable without a special tool. From the repository
root, the formal checker and projection builder are:

```text
python -B tools/systems_engineering/check_g15b_joint_baseline.py
python -B tools/systems_engineering/build_g15b_joint_views.py --check
python -B tools/systems_engineering/build_g15b_joint_views.py --write
```

StrictDoc is required only for native validation/export of the generated SDoc,
not to recover or edit the authority. Use the isolated, pinned environment from
`requirements/g15b-pilot.txt`.

## Identity and change rule

- New identities are allocated monotonically as `B0-REQ-NNNN` and recorded in
  the registry before use.
- Rejected, withdrawn, retired and superseded identities remain in the registry
  forever and are never reassigned.
- An editorial correction retains identity and records a change note.
- A substantive normative change allocates a new identity and links it with
  `supersedes`; the prior record becomes retained history.
- `PILOT-ONLY-*`, `NAV-REQ-*`, `CTL-REQ-*` and `FDI-REQ-*` are references only
  and never consume or alias a B0 ordinal.

All current records are candidate inputs to D2. `candidate_pending_d2` is not an
approval, implementation status, satisfaction statement or execution result.
