# G1.5-B current closeout and G1.5-C handoff

Date: 2026-10-13 (Australia/Perth)

This is a current lifecycle overlay. It does not alter the historical S/M/A
snapshot, rewrite its `candidate_pending_d2` source bytes, or convert planned
verification specifications into executed results.

## Current conclusion

- G1.5-B is approved, frozen, merged and post-merge accepted.
- The 23 assets listed by M match the PR #17 merge tree.
- G1.5-C technical inputs are ready, but the original PA returned `REWORK` on K
  `bd4ff5e`. Local uncommitted C1/C2 work was started prematurely after an
  internal same-name subagent was mistaken for the original gate authority. It
  is paused and is not a C start authorization, completed increment or result.
- G2/G3 and overall B0 remain outside this increment.

## Version and decision chain

| Event | Exact object | Direct source | Effect |
|---|---|---|---|
| D2 approval | 2026-10-13 03:28:22Z; S `ddd281f`, M `88074e2` | [user approval](https://github.com/ZhangChi0727/UAV-FMS-portfolio/pull/17#issuecomment-6137541739) | user freezes 23 manifest assets |
| Approval-bearing head | A `c844922` | [status overlay](g15b_joint_baseline_status.json) | records D2 without changing S/M |
| D3/merge | 2026-10-13 03:54:20Z; `c2aa92e` | [PR #17](https://github.com/ZhangChi0727/UAV-FMS-portfolio/pull/17); D3 validity stated in [work order §2](../../../docs/work_orders/B0_G1_5_C_closeout_and_verification_work_order.md) | maintainer places the approved tree on main |
| Post-merge acceptance | 2026-10-13 03:56:30Z; main CI `38343895365` | [complete TC transcription](https://github.com/ZhangChi0727/UAV-FMS-portfolio/pull/17#issuecomment-6142639167); [retained complete source](https://github.com/ZhangChi0727/UAV-FMS-portfolio/issues/18#issuecomment-6137888147); [truncated original](https://github.com/ZhangChi0727/UAV-FMS-portfolio/pull/17#issuecomment-6137887761) | historical PA completes B and makes C inputs ready |
| Combined follow-on authorization | event time not independently preserved | [current work order](../../../docs/work_orders/B0_G1_5_C_closeout_and_verification_work_order.md) | controlling user permits K, then C only after original-PA closeout gate |
| Sequence deviation | after K `bd4ff5e`, before original-PA REWORK | original PA turn `01a13480-e45e-7841-a56d-ed51b22e3ea4` in controlling thread | TC paused uncommitted local C work; no retrospective authorization claimed |

## Historical integrity and current-difference classification

The merge-tree audit resolved every path in M and found all 23 Git blobs equal
to their S identities. G0 v1/v2 and `01_simulation/b0` have no B-closeout
semantic change. The protected total work order remains an uncommitted local
user modification and is excluded from the branch.

| Change class in K | Files | Reason | Normative impact |
|---|---|---|---|
| execution contract | `docs/work_orders/B0_G1_5_C_closeout_and_verification_work_order.md` | authorize ordered closeout/C work | none; does not change frozen requirements |
| reader navigation/status | root README, systems-engineering README, roadmap | replace stale candidate wording with current lifecycle links | none |
| lifecycle overlay | this Markdown and adjacent JSON | separate D2, merge, C authorization and C start states | none; historical records remain immutable |
| remote execution summaries | PR #17 and Issue #18 bodies | remove stale pending fields/literal escapes; link #19/#20 | none; old comments retained |

Any later C schema, tool, test, report or CI change is a separate C-class
increment after PA accepts K. A normative-source/model/verification-criterion or
G0/G1 behaviour change is prohibited and requires a separate controlled change.

## Administrative remainder

Issue #18 remains open because closing it needs separate authorization. This is
not a technical blocker and does not make the frozen baseline provisional.
