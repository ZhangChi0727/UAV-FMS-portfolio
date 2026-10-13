# G1.5-B D1 approval record

Decision date: 2026-10-13 (Australia/Perth)

Decision gate: D1 — formal source, tool boundary and numbering rule

## Approved candidate

- Reviewed PR head: `18e28a78c65608fb0b3b6f84877a81735d097c44`
- Decision-package Git blob:
  `7729499bcde95d0329f830a84a8ee5d05fe96d69`
- Decision package:
  `systems_engineering/reports/b0/g15b_joint_baseline_decisions.md`
- PA technical review:
  <https://github.com/ZhangChi0727/UAV-FMS-portfolio/pull/17#issuecomment-6136723382>

## Maintainer decision

The maintainer replied directly to the three numbered D1 requests:

> 1采用；2采用；3批准

Trusted conversation locator:

- Codex thread: `019f9ef3-4a0c-79f1-99d4-c8415f62bd29`
- User message: `01a13314-640a-7090-88ef-973338384dd2`

The approved meaning is exactly:

1. Adopt the JSON-led formal requirement source and authority boundaries in
   the reviewed decision package; StrictDoc and Markdown are generated reader
   projections.
2. Adopt `sysmlpy==0.33.2` only for the isolated parser/AST role and
   `strictdoc==0.30.1` for generated reading/export. Any adopted `expose`
   relation not retained by the parser requires a source-version-bound manual
   review record.
3. Adopt non-reusable `B0-REQ-NNNN` identities. A substantive obligation
   change receives a new identity and `supersedes` relation; historical and
   pilot identities are not renamed or reused.

## Scope of approval

This approval permits controlled S1–S4 implementation and preparation of an
S5 candidate package under the joint-baseline work order. It does not approve
the resulting requirement bodies, model, verification specifications, joint
freeze, G1.5-C implementation, G2/G3 implementation, PR merge, Issue closure,
or a C-ready declaration. Those remain subject to D2 and D3.
