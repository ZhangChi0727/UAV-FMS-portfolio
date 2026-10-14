# G2-A S0 independent verification matrix

Status: **candidate pending original-PA DESIGN_ACCEPT**. All rows are planned;
none is an execution result. Production helpers may not be used as the sole
oracle for quaternion propagation, gravity direction, gate decisions or state
atomicity.

| ID | Input and initial condition | Independent oracle | Decision rule / tolerance source | Scope after S0 |
|---|---|---|---|---|
| A-PROP-01 | Identity and each body axis, positive/negative constant rate, one and many 0.005 s samples | Closed-form axis-angle quaternion using hand-written test formula | Physical attitude angle error and norm meet G0 quaternion tolerance | `B0-VER-ESTIMATOR-PROPAGATION` |
| A-PROP-02 | Zero and near-zero rates | Taylor/sinc limit and identity quaternion | Finite normalized output; no discontinuity at chosen test points | propagation boundary |
| A-PROP-03 | Equivalent `q` and `-q` initial states | Rotation-matrix equality independent of sign | Same physical output; returned representation follows G0 sign policy | convention |
| A-FUSE-01 | Positive/negative roll and pitch offsets with ideal stationary `[0,0,-g]` | Hand-derived FRD gravity vector and required correction sign | Tilt error decreases on every tested axis; yaw is unchanged within arithmetic tolerance | `B0-VER-ESTIMATOR-FUSION` |
| A-FUSE-02 | Two initial yaw values with gravity-equivalent observations | Gravity invariance under yaw rotation | No convergence claim to absolute yaw; relative yaw separation is retained | `B0-VER-YAW-LIMITATION` partial |
| A-GATE-01 | Norm exactly at, just inside and just outside `g ± 1.4709975` | Direct scalar norm comparison | Inclusive boundary; diagnostic and correction action agree | fusion gate |
| A-GATE-02 | Zero force and norm-valid lateral-contamination vector | Direct norm and geometry calculation | Zero is gated; near-g lateral case documents indistinguishability and bounded correction | `B0-VER-ACCEL-CONTAMINATION` module partial |
| A-CAP-01 | Maximum cross-product innovation at large dt allowed by fixture | Independent vector-norm clamp | Applied rotation-vector norm is at most 0.01 rad | bounded correction |
| A-TIME-01 | Reset at 0 and nonzero global time; first due sample | G0 period = `0.0025 * 2 = 0.005 s` | First step uses reset boundary and exact due period | reset/first-step |
| A-TIME-02 | Duplicate, stale, early, late, zero/negative/nonfinite effective dt | Snapshot owned state before call | Clear rejection and byte/value-identical owned state afterward | `B0-VER-INVALID-INPUT` |
| A-VALID-01 | `valid=false`, NaN/Inf, wrong shapes, non-unit reset quaternion | Explicit validation table, not production math | Reject before mutation with stable exception/reason category | invalid measurement/input |
| A-RESET-01 | Nonzero state then repeated reset/replay using same inputs and seed | Two independently captured output sequences | Exact replay for deterministic fields; all history/counters reset | `B0-VER-RESET` module partial |
| A-ISO-01 | Mutate caller arrays after construction and returned arrays after access | Pre-call deep copies | Estimator state and later outputs unchanged | memory isolation |
| A-TRUTH-01 | Static import/signature inspection plus isolated forbidden-input fixture | Runtime allow-list: IMU plus explicit initialization only | No post-reset truth-bearing type/path; negative fixture is detected | `B0-VER-TRUTH-BOUNDARY` partial |
| A-CONFIG-01 | Candidate and G0 file altered/missing/wrong version fixtures | Declared blob/SHA and JSON pointers | Fail closed; no copied silent defaults | provenance/configuration |

Comparison rules: vectors use component absolute comparisons only where the
oracle is component-valued; attitudes use sign-invariant quaternion angle or
rotation-matrix comparison; boundary tests use exact decimal inputs where
possible and `math.nextafter` for adjacent floating-point cases. No test may
derive its expected result by calling the production quaternion or gate helper.

Evidence after implementation must retain the command, exact commit, Python and
NumPy versions, configuration identities, seed interface, per-row outcomes and
artifact hash. Passing module rows does not make the G3 portions of yaw,
contamination, reset or truth-boundary provisions complete.
