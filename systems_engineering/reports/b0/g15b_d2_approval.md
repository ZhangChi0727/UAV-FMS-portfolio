# B0 G1.5-B D2 joint-freeze approval

Date: 2026-10-13 (Australia/Perth)

Status: **D2 approved; exact joint baseline frozen pending D3/merge.** This is a
configuration-control decision, not implementation, satisfaction, verification
execution, merge, G1.5-C start, or C-ready evidence.

## Approved object

- Candidate asset commit S:
  `ddd281fd0a94ee59635accb5f41500fac05284b7`
- Candidate manifest commit M:
  `88074e21e1f5c71f24fc7b79e842b00e37ecdb7b`
- M machine-manifest blob:
  `298eaf714bb54cc9a4efa93b456035ca4276edcd`
- M human-manifest blob:
  `d3e082bad7d2f0e4f677e4f4822aad5379d1ed71`
- Base commit: `02e59d4654e87d85ef3543e0812a5e373be684ac`

The 23 assets and blob identities listed by M are the approved freeze scope.
The source-owned `candidate_pending_d2` fields are retained as bytes of the
reviewed pre-approval snapshot; this approval record is the authoritative
post-review lifecycle overlay. They must not be rewritten in place merely to
make the snapshot describe its later approval.

## Review and approval evidence

- PA review: `APPROVE_FOR_D2`, recorded at
  <https://github.com/ZhangChi0727/UAV-FMS-portfolio/pull/17#issuecomment-6137491722>.
- User reading acceptance for the corrected exact S was recorded at
  <https://github.com/ZhangChi0727/UAV-FMS-portfolio/pull/17#issuecomment-6137471604>.
- The user then replied **“批准并授权。”** in controlling Codex thread
  `019fa435-f674-71e3-85ba-10e28ad94470`, explicitly answering the request to
  approve exact S/M and authorize the D2 record/freeze closeout. The retained
  PR record is
  <https://github.com/ZhangChi0727/UAV-FMS-portfolio/pull/17#issuecomment-6137541739>.
- CI run `38340944096` passed all six jobs at M.

## Decision and boundary

1. Approve and freeze the exact S assets identified by M.
2. Preserve the D1-approved JSON-led source, nonreusable B0 numbering and
   version-bound SysML/StrictDoc method.
3. Treat all 29 verification specifications as planned/not-run; D2 does not
   create a product verdict or import historical evidence as satisfaction.
4. Require a new S/M candidate and repeated review for any substantive semantic
   change to the frozen scope.
5. Keep PR #17 Draft. D2 does not authorize Ready, merge, Issue #18 closure,
   G1.5-C execution, G2/G3, or a C-ready declaration.

The next action is independent PA review of this approval-bearing head. D3 and
merge/post-merge checks remain separate gates.
