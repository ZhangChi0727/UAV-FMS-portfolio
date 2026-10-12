# Roadmap and work management

Version 0.2, 2026-10-09. This file owns scope, dependencies and gate definitions.
GitHub Issues own execution status; milestones group a bounded release.
No calendar duration or numerical result is implied.

## B0 backlog

Execution detail: [B0 work order](work_orders/B0_work_order.md).
Environment handoff: [development readiness work order](work_orders/development_readiness.md).
Systems-engineering sequence: [G1.5 total work order](work_orders/B0_G1_5_work_order.md),
[G1.5-A work order](work_orders/B0_G1_5_A_work_order.md), and the active
[G1.5-B structured phase-one pilot](work_orders/B0_G1_5_B_structured_sysml_pilot_work_order.md).
G1.5-A establishes the document/model structure. The G1.5-B pilot is a
non-authoritative review increment; the formal G1.5-B joint baseline and
G1.5-C remain planned.

Remote execution: [B0 milestone](https://github.com/ZhangChi0727/UAV-FMS-portfolio/milestone/1).
Issues [#3](https://github.com/ZhangChi0727/UAV-FMS-portfolio/issues/3)
through [#8](https://github.com/ZhangChi0727/UAV-FMS-portfolio/issues/8)
implement the six rows below in dependency order. Their live status is authoritative.

Execute in dependency order; G0 is the first implementation increment.

The governance sequence is an explicit release gate in addition to each
component's technical prerequisite: **G1 → G1.5-A → G1.5-B → G1.5-C → G2 →
G3**. G1.5-A establishes the structure and first model views, G1.5-B freezes
the joint requirements/model baseline, and G1.5-C completes verification
traceability and report presentation. G2 estimator/controller work may begin
only after all three G1.5 increments are accepted; G3 integration also retains
the G1/G2 technical prerequisites. This ordering does not change the
component-level dependencies shown below.

| Work item | Technical dependency | Governance gate | Acceptance |
|---|---|---|---|
| Define B0 contracts and metrics | None | Before G1 | G0 in development baseline |
| Implement rotational plant and IMU | G0 | Before G1.5-A | G1 |
| Establish systems-engineering structure and model views | G1 | G1.5-A | G1.5-A (governance increment; not a new product baseline) |
| Establish requirements/model joint baseline | G1.5-A | G1.5-B | G1.5-B formal joint baseline (planned; structured phase-one pilot active) |
| Establish verification traceability and report presentation | G1.5-B | G1.5-C | G1.5-C (planned) |
| Implement basic attitude estimator | G1 sensor fixtures | After G1.5-C; estimator part of G2 | Estimator part of G2 |
| Implement C++ cascaded controller | G0 | After G1.5-C; controller part of G2 | Controller part of G2 |
| Integrate estimated-state loop | G1, G2 | After G1.5-C | G3 |
| Release evidence and defect checks | G3 | After G1.5-C | G4 |

## Extension registry

These identifiers name work packages, not system requirements. G1.5 is an
internal governance increment and does not create or renumber NAV/CTL/FDI IDs.

| Package | Responsibility | Minimum dependency | Independent exit |
|---|---|---|---|
| EXT-NAV | INS/GNSS EKF, outage and recovery | Shared conventions, deterministic sensor fixtures | Navigation contract tests and scenario evidence; legacy v0.1 scope retained |
| EXT-FLIGHT | Translation, position/velocity loops, waypoint task | B0 | Closed-loop trajectory evidence with declared envelope |
| EXT-PX4 | Version-pinned autopilot adapter and source-level change | B0; EXT-FLIGHT for position claims | Baseline/change comparison and reproducible build/run |
| EXT-EMBED | STM32, RTOS, sensing, timing and actuator interface | B0 C++ core | Board traces, deadlines, same-input PC/board comparison and controlled rig |
| EXT-FW | Fixed-wing trim and longitudinal control | Shared B0 interfaces; new plant | Airspeed/altitude cases and operating-envelope analysis |
| EXT-HEALTH | Fault monitoring and recovery policy | Relevant estimator/control capability | Residual/threshold baseline, fault/recovery tests |
| EXT-VERIFY | Generic verification-suite adapter | Working local evidence chain | Reuse and domain-specific adaptation documented |
| EXT-HIL | Hardware controller coupled to real-time plant | EXT-EMBED or compatible hardware adapter | Closed-loop timing, signal mapping and evidence comparison |
| EXT-LEARN | Learning-based estimation/detection/control | Relevant classical baseline and screened research question | Dataset provenance, leakage controls, baselines and ablations |

Advanced control, UKF and visual navigation require a scoped extension proposal.
They are not implicitly mandatory because scaffold files exist.

## Work management

- Maintain one B0 milestone; create extension milestones only when activated.
- Issue states: backlog, ready, in progress, review, done, blocked.
- Limit active work to one primary engineering increment and one research exploration.
- Each issue specifies package, dependencies, inputs/outputs, acceptance and evidence.
- Each PR addresses a coherent increment; completed tests must be mandatory in CI.
- A green scaffold/contract CI is not proof of implemented B0 behavior.
- Research candidate -> screened -> active -> evaluated -> archived/published.
- Stop or narrow research when prior art removes the gap, evidence is infeasible,
  or the hypothesis fails; negative findings remain recorded.
- Do not mirror live issue status into many README tables.

## Migration decision

Preserve numbered implementation directories and imports. Update their responsibilities
and links now; move code only when an implementation change justifies it.
The old phase numbering is historical scaffold provenance, not the active roadmap.
Keep existing NAV/CTL/FDI identifiers and thresholds; review applicability rather
than renumbering them. Research claims remain candidates, independent of B0.
