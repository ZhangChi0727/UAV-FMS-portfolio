# Current systems-engineering status snapshot

**Snapshot baseline:** G1 merge `de0006392a4ac6017c4be0b6befa35f1d6cefe0e`;
the G1 implementation was reviewed at `b1c529f0b956ad4abed6705ae62b35fd28e6daf7`.
This report is a versioned summary, not a live Issue mirror.

| Area | State | Supported conclusion |
|---|---|---|
| G0 contract | accepted/approved | v1/v2 validator and the approved v2 record are retained; no parameter or threshold change is made by G1.5-A |
| G1 plant, actuator and IMU | accepted | 25 component tests, deterministic component evidence and the CI artifact `b0-g1-component-evidence` were retained at the G1 baseline |
| G1.5-A structure/models | this PR | document responsibilities are migrated; model views are editable and bounded by the G0 contract |
| G2 estimator/controller | planned | no estimator or controller implementation/closed-loop result is claimed |
| G3 integration | planned | no truth-isolated estimated-state loop result is claimed |
| G4 release evidence | planned | no release, flight, HIL or broad performance evidence is claimed |
| Research and extensions | not active | candidates remain independently gated |

The G1 component evidence is not closed-loop performance evidence. For exact
commands and retained artifact metadata see [RESULTS.md](../../RESULTS.md), the
G1 component tests under `01_simulation/b0/tests`, and CI run
`38119306904` (the artifact is retained by that CI job). The V&V scope and
limitations remain in [v_and_v_report.md](v_and_v_report.md).

G1.5-A does not freeze new requirements, install a requirements tool, or claim
that future planned states have passed. G1.5-B is the next separate decision
point for a requirements/model joint baseline; G1.5-C remains later.
