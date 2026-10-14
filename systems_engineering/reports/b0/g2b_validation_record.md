# G2-B cascaded-controller candidate validation record

Status: **`ready_for_review` once the exact candidate head named in the PA
handoff has a completely green CI run**. The evidence-source package below is
complete. Recording that evidence necessarily creates a later candidate head,
so its non-recursive CI identity is retained in the PR and PA handoff; no review
request may be sent before that run is green.

## Controlled boundary

- PR: [#22](https://github.com/ZhangChi0727/UAV-FMS-portfolio/pull/22).
- Base: `5f817ec1fb2405aa269dcf6a701a33cff846c748` (merged G2-A).
- S0 design accepted at:
  `7084584ef9e69995b88201164fa8659e4ef57c79`.
- First implementation review head:
  `9d79caba593ac9383c5f3db7bf884f76ea6d595c`; decision `REWORK` in
  [g2b_review_9d79cab.md](g2b_review_9d79cab.md).
- Re-review evidence-source commit:
  `5b81b9749ce048a358c60b5f799494361b907ded`; Actions run
  [38555772322](https://github.com/ZhangChi0727/UAV-FMS-portfolio/actions/runs/38555772322).
  The G2-A, G2-B Debug and G2-B Release evidence jobs succeeded. The source
  run's only failed job was the expected pre-closeout governance check against
  the then-committed older ledger; the later candidate-head run is the complete
  green gate.
- Protected local-only work order:
  `docs/work_orders/B0_G1_5_work_order.md`; expected SHA-256
  `96d45d4215c2215bb50ea0c7b863b627fa2e7d8d64ada3bb456950a2aa0d44a5`.

This record covers the G2-B platform-independent C++17 controller and mandatory
Python boundary at module/component level. It does not claim G3 scheduling or
closed-loop performance, SIL, real-time HIL, board execution, flight, G4, or B0
completion. Frozen multi-stage specifications remain partial wherever G3 has
unexecuted prerequisites.

## Review finding closure map

| Finding | Candidate change and permanent check | Evidence needed before re-review |
|---|---|---|
| R1 command/validity/type contract | `controller.hpp`, `controller.cpp`, binding and adapter enforce `q_nb_command`, explicit validity, strict bool/int64/finite scalar conversion; adapter/binding invalid-input tests | Debug and Release CTest nodes plus retained rejection/snapshot trace |
| R2 integer time grid | controller state derives due time from epoch plus integer tick and rejects unrepresentable progress; long-grid/huge-epoch and retry tests | deterministic long regression in both build types |
| R3 G1 output compatibility | adapter constructs the existing G1 `contract.TorqueCommand` without reclamping; real G2-A estimate/G1 actuator fixture | Python fixture collected by CTest and module identity in artifact |
| R4 supersession integrity | traceability checker separates historical source/target integrity from current-HEAD applicability; corrupt historical hash/revision fixtures | systems-engineering positive and negative test log |
| R5 complete S0 matrix and defect detection | row-to-node map remains in [g2b_s0_controller_verification_matrix.md](g2b_s0_controller_verification_matrix.md); C++/Python checks and isolated subject mutations must all execute | exact node list, mutation build/run log, clean restored production pass |
| R6 reproducible build and evidence | exact pybind11/Catch2 resolution, Python CTest working directory, clean Debug rebuild, Debug/Release logs, deterministic JSON artifacts, controller dependency closure and ledger records | actual run/commit/module/config identities, artifact files/IDs/hashes/expiry and pending PA review source |
| F1 strict Python scalar boundary | binding and adapter reject NumPy complex values, booleans and lossy integer-to-double coercions atomically while accepting losslessly representable real scalars | collected CTest/Python nodes and retained rejection traces in both build types |
| F2 complete raw S0 evidence | evidence generation imports mandatory CTest and pytest JUnit plus the controlled matrix, retains every mapped node execution and fails closed on missing, stale or malformed inputs | 26/26 matrix rows and 139/139 sampled cases, including all four unchanged-oracle mutation detections |
| F3 transitive dependency closure | applicability profile now includes the imported simulation package and transitive `__init__`, actuator, contract, IMU, plant and quaternion files | exact 34-file Git-blob SHA-256 closure for both controller records |

## Required commands and results

The candidate records the output and pass/fail totals for every command below.
No root pytest collection is used.

```text
cmake --preset b0-controller-debug
cmake --build --preset b0-controller-debug
ctest --preset b0-controller-debug
cmake -E remove_directory build/b0-controller/debug
cmake --preset b0-controller-debug
cmake --build --preset b0-controller-debug
ctest --preset b0-controller-debug

cmake --preset b0-controller-release
cmake --build --preset b0-controller-release
ctest --preset b0-controller-release

cd tools/systems_engineering
python -m pytest -q tests
```

Local corrective checks on 2026-10-14 establish the candidate behavior but do
not replace the retained CI package. The Debug and Release CTest presets each
reported **25/25 passed**: 20 production Catch2 nodes, one Python track, and
four isolated mutation-detection nodes; their separately retained pytest JUnit
files each report **79/79 passed**. The repository systems-engineering suite
reported **185 passed in 541.57 s** from its track on Windows, excluding the
native StrictDoc cases, and those **6 native StrictDoc cases passed in 12.84 s**
under WSL. Ruff and `git diff --check` passed for the corrective sources. No
skip or xfail is counted as evidence.

The checked-in CI generator ran against the exact Debug and Release modules at
`5b81b9749ce048a358c60b5f799494361b907ded`. Both JSON files retain that source
commit and checked-out identity, all selected criteria are true, all **26 S0
rows / 139 sampled cases** pass, and the adjacent JUnit files report 25 CTest
nodes plus 79 pytest cases with zero failures and zero skips in each build.

The CI evidence step reruns the matching CTest preset with XML/log retention and
retains a separate pytest JUnit, then invokes `03_control/b0/evidence.py`
against that preset's exact module, CMake cache and controlled S0 matrix. The
generator fails closed if either JUnit or the matrix is absent or byte-mismatched,
if the imported module is outside the
declared build, if actual pybind11 is not 2.13.6, if Catch2 is not the pinned
revision/exact 3.5.4 package, if a review-critical artifact field is absent, or
if a selected independent numerical criterion fails.

## Retained artifact package

| Build | Actions artifact | Required files | ID / content SHA-256 / archive SHA-256 / expiry |
|---|---|---|---|
| Debug | `b0-g2b-controller-evidence-debug` | `ctest-debug.log`, `ctest-debug.xml`, `pytest-debug.xml`, `g2b_controller_evidence_debug.json` | ID `11890396601`; job `115824406590`; JSON `da38fea5213fc47b17cb98a03afc0ded6474c5662fe6909a777e963066e41b52`; archive `596c6cc908cacad091ebe0a8ff774740eff35f171896aabb6a95f21f8151887c`; expires `2027-01-12T11:19:37Z` |
| Release | `b0-g2b-controller-evidence-release` | `ctest-release.log`, `ctest-release.xml`, `pytest-release.xml`, `g2b_controller_evidence_release.json` | ID `11890331486`; job `115824406773`; JSON `119e0980f8a1380e3e197b3a3d84ee518a788783c5d1742be8fbfc7430c5dfea`; archive `5ddd200cfac14be93071ad00606e1b57876fcfd3b9f9fbcddc93afcd6b8db169`; expires `2027-01-12T11:19:37Z` |
| G2-A refresh | `b0-g2a-estimator-evidence` | `g2a_estimator_evidence.json` | ID `11888862827`; job `115824406625`; JSON `8a93f61948f8368330f6d5dcf46631acb8e3193c6445b7472fa2176428bb1082`; archive `2e4d78fbcd323f9fdc942f4072dc77cdb5f932388c3f34e887ecff01def77ffa`; expires `2027-01-12T11:19:37Z` |

The Debug log/CTest XML/pytest XML SHA-256 values are respectively
`d7ba95377d796f9ea52698c4570f16e5e5347e183c5d01779829ac70240ab95e`,
`960f1c2f64d22638942ffd95387afa27d2619b13a8ae7d7108f65e49aa8b2b64`
and `061934ece9f5cec461a728a42c858cb362be381f4d15f2dbc703b369dd9d351c`.
The Release values are
`c0720260480ce17b2a8bc6a4260f280ba800def8c69bbad92f41b0612f743fd3`,
`fb701fbeecfadab72d54e76b0a796773de95c854adcc3110f86cbbbc18bba143`
and `69a9cdd04a78db38a87cc292b3a2052f81350ec2f133d87f56f0564c7b2bbee6`.

The G2-B JSON retains the exact source commit; build type and directories;
compiler, CMake, Python/ABI and imported-module identity; actual pybind11 and
Catch2 resolution; implementation/approval/G0/validator digests; independent
attitude and anti-windup oracles; I/P/D/back-calculation diagnostics; a three
tick command/feedback/epoch trace; invalid-input snapshots; criteria and claim
limitations. The JSON retains the complete 26-row raw S0 mapping, all 139
sampled comparisons and both JUnit source identities; it does not replace the
raw XML/log files bundled beside it.

The G2-A and G2-B evidence jobs explicitly check out
`${{ github.event.pull_request.head.sha || github.sha }}`. On a pull request the
artifact `source_commit` is therefore the precise branch head that supplied the
bytes. The Actions run ID, event name, `GITHUB_REF` and `GITHUB_SHA` metadata are
retained separately; the latter may identify GitHub's synthetic merge ref and
must not be substituted for the checked-out source commit. On `push`/`main`, the
same expression falls back to `github.sha`.

## Mandatory controller dependency closure

The controller scope profile in `g15c_traceability.py` must reject any current
record omitting one of the following classes. The final ledger expands these to
exact paths and committed source/target SHA-256 values:

- core/build: root `CMakeLists.txt`, `CMakePresets.json`, B0 controller CMake,
  public header and C++ implementation;
- boundary: pybind source, Python loader/adapter, actual G2-A estimate and G1
  simulation package dependencies (`__init__`, contract, actuator, IMU, plant
  and quaternion);
- checks/oracles: all C++ and Python controller tests, mutation runner and the
  evidence-contract negative fixtures, including
  `03_control/b0/tests/expect_mutation_detected.py`,
  `tools/systems_engineering/tests/test_g2b_evidence_contract.py` and
  `tools/systems_engineering/tests/test_g2b_matrix_closure.py`;
- authority: G0 v2 bytes and actual validator, G2 implementation config and S0
  approval, accepted S0 design and row matrix;
- evidence/reproduction: `evidence.py`, B0 dependency lock, CI workflow,
  controller README and the traceability checker itself.

Changing the workflow changes the G2-A declared closure. Therefore the same
final workflow must rerun G2-A, and new ledger records must supersede the prior
G2-A refresh records while retaining and validating their historical source
and target identities.

## Re-review gate

This record is eligible for PA re-review only after all of the following are
true:

1. every S0 row names an existing collected node and all required rows pass in
   the declared environment with no skip/xfail;
2. all four subject mutations compile and are detected by their predeclared
   unchanged oracle, followed by a clean production rebuild/pass;
3. Debug, Release, clean Debug and the complete CI are green at one exact head;
4. both G2-B artifacts and the required G2-A refresh have real run/artifact
   identities and hashes in the ledger;
5. the controller and refreshed estimator closure profiles validate against
   committed HEAD; generated traceability projection is current;
6. the protected work-order hash and final `git status` are reported, and no
   merge, Issue closure, branch deletion or G3 work is implied.

Items 1, 2, 4 and 5 are retained above; item 6 is checked again immediately
before handoff. Item 3 is satisfied only by the completely green run for the
exact candidate head containing this record, which the PR and PA handoff must
name. The evidence-source run is not misrepresented as that final run.
