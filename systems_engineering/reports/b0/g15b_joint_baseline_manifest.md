# G1.5-B joint-baseline candidate manifest

Status: **candidate pending PA review and D2**.

- Candidate asset commit S: `533a0b48e2ad918ba378f63f651fe6ebfdc0dee9`
- Machine-readable asset/blob inventory:
  `systems_engineering/reports/b0/g15b_joint_baseline_manifest.json`
- Base: `02e59d4654e87d85ef3543e0812a5e373be684ac`
- D1 decision blob: `7729499bcde95d0329f830a84a8ee5d05fe96d69`

The JSON manifest lists every file changed by S, its Git blob from S, role,
fixed tool versions, and the deterministic projection rule. This manifest does
not list its own hash and does not modify any S asset, avoiding a circular
identity. The commit containing this file is candidate manifest commit M.

PA must review exact S plus M before the user is asked to approve D2. A later
approval record A may cite that real decision, but M does not prefill it.
