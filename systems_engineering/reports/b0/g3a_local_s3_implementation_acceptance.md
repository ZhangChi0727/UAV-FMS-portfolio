# G3-A local S3 implementation acceptance

Original PA decision: `IMPLEMENTATION_ACCEPT`, 2026-10-26. This accepts the exact
local development integration source below, not G3-A closure or formal performance.
PR #23 candidate CI and post-merge main acceptance remain required.

## Exact object and actual execution

- Source: `a0190f3159e423eed85bf29f6196d862ac52129d`; tree
  `80510be19cc4df3d000e3627b6b56b9792cb688e` (57 runtime paths).
- Original work order SHA-256:
  `07173EF2CC3D939DA047EDC9ADFA028D9D38C480662CD828FB7D249B49DD9D82`.
- Real C++17 production binding: Debug
  `8288B28802C263B118A4EE78C38E2D785CD6050DC9A2E71C150C91C28852C2A4`;
  Release `69CB7EAF665E4F7F31DE2B85CECE6995033EF0CFDB69EC8D1A1D61B2D8EF44A2`.
- Runtime: WSL Ubuntu 20.04.6, GCC 9.4, Python 3.11.17, NumPy 1.26.4,
  pybind11 2.13.6, CMake 3.30.5; retained environment identity is
  `256A899ABE55C1BFDBB2C0D35592AF07970489856FE408E9450B083082922DA4`.
- Eight separately captured WSL calls completed once, without retries or cleanup:
  selected regression; Debug runner/bind/offline; Release runner/bind/offline; compare.
  Only development seed `2026100900` was used. Production initial parameters are unchanged.
- Actual selected pytest denominator: **328 passed**, zero failures/errors/skips/xfails.
  Debug and Release each have **one** offline pytest case, each containing 13 data
  diagnostics: one legal control and 12 independently specified single-defect records.
  The 26 diagnostic records are not 26 additional pytest cases or DUT simulations.

## Original six gaps and independent disposition

| Obligation | Retained real evidence and independent check | Local result |
| --- | --- | --- |
| Full reset/RNG | Odd/even reset with nonzero I/D/actuator/held prestate; reset-local first two IMU samples and full RNG integers; L/O twin streams | Accepted |
| Prior-epoch held roles | Five actual old-epoch candidates rejected by the ordinary guard before component calls or state change | Accepted |
| Illegal input/recovery | L400/L800 real rejection, same-tick correction without IMU resampling; O6 real missed-tick failure, reset-required rejection, explicit reset recovery | Accepted |
| Truth isolation | Fixed real E/C inputs with different evaluator truth; two actual derived forbidden-edge payloads rejected by the normal guard; retained static allowed-edge review | Accepted within the fixed-input/declared-edge scope |
| Publication/hold/pairing | S/L/O/E phases, three successive publications and longer streams; held identities/timestamps, real phase2 `[k-1,k)` feedback, events and adapter transforms | Accepted |
| Execution identity | Exact source/config/environment/build/module/F0, actual constructor input objects and loader reads, complete capture and sealed raw | Accepted; no private-core getter is claimed |

Three non-author domains independently reconstructed capture and all 114 count keys,
raw semantics/invariants, and inputs/diagnostic mutations. They did not import or rerun
the DUT, project checker, helper, simulation or seed. The original PA then accepted
GAE01–GAE10 for this source; GAE11–GAE12 are still pending.

Across both records the independent reconstruction checks 24 reset boundaries,
4,952 ordinary boundaries, 4,944 phase2 pairings, 2,474 publications and 2,478 holds.
All 213,364 matching hex-float leaves in the D/R profile trees are exactly equal;
time-grid maximum residual is zero. The maximum norm residual in 13,984 quaternion
vectors is `2.22e-16`, within the existing frozen tolerance. This is a finite
integration invariant result, not a flight-performance or physical-accuracy claim.

Each build actually constructs eight controller adapters and 16 C++ cores: eight
production and eight temporary parameter-validation cores. Two driver invocations
must not be reported as only two constructors. Core evidence is the passed constructor
object and statically reviewed copy path, not private internal parameter readback.

## Evidence locators and retention

Local retained base: `build/g3a-evidence-env/20261023-f0-preparation/`.
Generated evidence is ignored and is not committed. These local artifacts are not
claimed remotely verified; a future candidate must generate its own CI artifacts.

| Record under the base | SHA-256 |
| --- | --- |
| `pa-local-s3-f0-acceptance.v1.json` | `AB007D113F9CE49A74BADC3FB664E6D4FCDED45D0DE31C53B9B7634E4D6F3F45` |
| `s3-integration-batch.actual-observation.v1.json` | `D2E634EAA39CE2EC5DAB97969B84C1D0AE5A53D2EBA800CE98F9C5A5FFAC0867` |
| `s3-integration-batch-transport-receipt.v1.json` | `3C203657CBD36A789DE60BB2A1EDAA2FF9E64988B92E2E13B6FEA85253EBF04C` |
| `s3-integration-batch.actual-output-index.v1.json` | `664283394DEB999512C071950EF3283222D6441F5365B0DE9ADBEE9E1A2EAAA2` |
| Debug `s3-integration-batch-01/driver-output/debug/s3-onlydev0900-debug-01/raw/g3a-evidence.json` | `CEEBBC1E03E1AFE89319DE8BF55ABC24A92B3AC7D3309E3FE0CD25E59202C89B` |
| Release `s3-integration-batch-01/driver-output/release/s3-onlydev0900-release-01/raw/g3a-evidence.json` | `4E608ABED57EB5796698DE243A72AD8EB3AE908260FD92FA5B521CE8FA686AB3` |
| `s3-integration-batch-01/compare/debug-release.json` | `5F4D64F6C86A978D6B14B1A8B7B0B9C28424E66B28D7037A4F2BCCE242A9F6B0` |

The output index binds all 16 actual products; the separate PA implementation decision
records all three non-author conclusions and reconstructed denominators. Failed S1/S2
attempts remain unchanged. The previously disclosed missing unexecuted-draft retention
deviation is not repaired or relabeled complete by this acceptance.

## Remaining gates and exclusions

Candidate C must descend from this S3 and preserve all 56 non-workflow runtime blobs.
The separately reviewed G3-A workflow is a substantive runtime-path exception; it
requires fresh C source/build/F0/raw and independently acquired CI evidence. Local S3
results cannot be relabeled as C CI results. Exact candidate acceptance, authorized
merge and post-merge main verification are required before `G3_A_CLOSED`.

No parameter, model numerical-adequacy, normal eight-scenario/37-criterion, 50 ms
saturation, G3-B/C, G4/B1, board, HIL, flight or release acceptance is granted.
Acceptance seed `2026100906` remains permanently exposed and
`formal_study_evidence_complete=false`. Issue #7 remains open; no branch is deleted.
