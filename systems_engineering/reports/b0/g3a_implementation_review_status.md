# G3-A implementation review status

Date: 2026-10-15 (Australia/Perth). Review authority: original Project
Administrator. State: **implementation acceptance not granted**. Draft PR #23
remains open and must not be merged under this record.

This status separates implemented development checks from the independent
evidence still required by the G3 work order. A passing item below is not a
claim that the complete G3-A exit has passed.

## Completed and retained

| Item | Current evidence | Boundary |
| --- | --- | --- |
| Exact S0 design | Original-PA `DESIGN_ACCEPT` at `e3a5df2c7b21b4f4a4c7c6f296e0711222ac2569` | Design approval only |
| Integer schedule and event adapters | Unit tests cover reset-only tick zero, due boundaries, phase rejection and event behavior | Does not replace full scenario execution |
| Real-component interface smoke | Debug and Release 12-tick G1/G2 loops and independent comparison are mandatory in `g3a.yml` | Development interface check, not performance evidence |
| Controller-first reset transaction | Runner derives actuator reset state from the controller reset command | Full runtime reset/RNG/old-epoch evidence remains open |
| Bounded gain study | Seven predeclared x-rate-Kp candidates executed once with tuning seed only; zero feasible; original PA accepts this finite negative result | No `PARAMETER_ACCEPT`; approved production parameters remain unchanged |
| Exposure provenance | Historical seed `2026100906` remains permanently exposed; future records separate this-run, previous and cumulative state | Sealed v1 raw records remain unchanged |
| Source identity enforcement | 33-path behavior closure covers runtime, public G1 package/quaternion, C++ core/header/binding, CMake/dependencies and both workflows | Historical study captured only 16 paths in `authority.files`; formal study evidence remains incomplete |
| Filter fail-closed rule | Exact Git bytes or canonical LF equivalence only; semantic smudge-filter counterexample is rejected | Checkout-filter hash is diagnostic, never an independent acceptance path |

## Still required before G3-A implementation acceptance

| Open proof | Required outcome |
| --- | --- |
| Runtime reset and RNG | Even/odd reset boundaries, RNG cleanup and first valid updates must be independently checked |
| Old-epoch rejection | Stale prior-epoch messages must be rejected without state contamination |
| Invalid-call recovery | Approved invalid controller/estimator calls, unchanged snapshots and same-tick or declared recovery must be demonstrated |
| Truth isolation | Positive fixed-input invariance and a controlled forbidden-truth negative variant must both be detected independently |
| Hold and feedback pairing | Multiple publications, intervening holds, timestamps, request/limited/status and paired actuator feedback require complete evidence |
| Source/build identity evidence | Full behavior/build closure must be captured during the relevant execution, not reconstructed afterward |
| Review decision | The original PA must review an exact head and issue `IMPLEMENTATION_ACCEPT`; none has been issued |

G3-B independent metrics and eight-scenario acceptance, G3-C evidence closure,
G4, B1, merge, Issue closure, branch deletion and release remain outside this
record and require their own authorization. Human discussion of inner/outer-loop
gain design, actuator constraints and the 50 ms verification stimulus has not
changed any frozen contract, parameter, budget, seed or scenario criterion.
