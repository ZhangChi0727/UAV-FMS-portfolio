# G2-A S0 independent verification matrix

Status: **candidate pending original-PA DESIGN_ACCEPT**. All rows are planned;
none is an execution result. Production helpers may not be used as the sole
oracle for quaternion propagation, gravity direction, gate decisions or state
atomicity.

| ID | Input and initial condition | Independent oracle | Decision rule / tolerance source | Scope after S0 |
|---|---|---|---|---|
| A-PROP-01 | Identity/non-identity starts; principal axes `±0.3 rad/s`; simultaneous `[0.3,-0.2,0.1] rad/s`; one and 200 samples at 0.005 s | Closed-form axis-angle quaternion using a hand-written test formula | Sign-aligned quaternion max-component error `<=1e-12`; norm error `<=1e-12`; rotation matrices agree componentwise `<=1e-12` | `B0-VER-ESTIMATOR-PROPAGATION` |
| A-PROP-02 | Rates 0, `1e-12`, `1e-9`, `1e-6 rad/s`; sequential x-then-y and y-then-x updates | Taylor/sinc limit and explicitly multiplied Hamilton quaternions | Finite normalized output; component error `<=1e-12`; noncommuting sequences match their distinct ordered oracle | propagation boundary |
| A-PROP-03 | Equivalent `q` and `-q` initial states | Rotation-matrix equality independent of sign | Same physical output; returned representation follows G0 sign policy | convention |
| A-FUSE-01 | ±0.1 rad roll, ±0.1 rad pitch and combined roll/pitch starts with ideal stationary `[0,0,-g]` | Hand-derived FRD gravity vector, cross-product sign and explicit right-multiplied expected quaternion | Gravity-vector and quaternion components agree `<=1e-12`; tilt decreases; yaw rotation matrix component remains `<=1e-12` from oracle | `B0-VER-ESTIMATOR-FUSION` |
| A-FUSE-02 | Two initial yaw values with gravity-equivalent observations | Gravity invariance under yaw rotation | No convergence claim to absolute yaw; relative yaw separation is retained | `B0-VER-YAW-LIMITATION` partial |
| A-GATE-01 | Axis-aligned vectors constructed at the boundary and with `math.nextafter` magnitudes toward/away from `g` | Compare the **actual computed float norm** to the float threshold; assert each constructed case lands on its intended side before calling production | Inclusive `abs(norm-g)<=threshold`; diagnostic and correction action agree | fusion gate |
| A-GATE-02 | Zero force and norm-valid lateral-contamination vector | Direct norm and geometry calculation | Zero is gated; near-g lateral case documents indistinguishability and bounded correction | `B0-VER-ACCEL-CONTAMINATION` module partial |
| A-CAP-01 | Public step at legal 0.005 s with maximum unit-vector cross product; pure clamp helper with explicit 0.02 rad non-production vector | `gain*dt*norm(cross)<=0.005 rad`; independent Euclidean magnitude clamp | Public step stays `<=0.005 rad`; helper maps 0.02 rad to 0.01 rad without changing direction | redundant bounded defence |
| A-TIME-01 | Reset at 0 and nonzero global time; first due sample | G0 period = `0.0025 * 2 = 0.005 s` | First step uses reset boundary and exact due period | reset/first-step |
| A-TIME-02 | Duplicate, stale, off-grid, zero/negative/nonfinite timestamps; valid tick after one rejected aligned sample | Reset-grid arithmetic with `1e-12 s` absolute tolerance and snapshot of owned state | Invalid call leaves propagation state identical; next grid-aligned valid tick is accepted without reset and integrates elapsed time from last accepted state | `B0-VER-INVALID-INPUT` |
| A-VALID-01 | `valid=false`, NaN/Inf, wrong shapes, non-unit reset quaternion | Explicit validation table, not production math | Reject before mutation with stable exception/reason category | invalid measurement/input |
| A-RESET-01 | Nonzero state; reset at nonzero boundary; repeat same-boundary reset before a step; reset after a valid sample | Reset epoch/time ordering plus two independently captured output sequences | Earlier boundary or non-increasing epoch ID rejects atomically; equal-time idempotent reset before a step is allowed with increasing ID; replay components agree `<=1e-12`; all history clears | `B0-VER-RESET` module partial |
| A-ISO-01 | Mutate caller arrays after construction and returned arrays after access | Pre-call deep copies | Estimator state and later outputs unchanged | memory isolation |
| A-TRUTH-01 | Static import/signature inspection plus isolated forbidden-input fixture | Runtime allow-list: IMU plus explicit initialization only | No post-reset truth-bearing type/path; negative fixture is detected | `B0-VER-TRUTH-BOUNDARY` partial |
| A-CONFIG-01 | Candidate/G0 altered, missing or wrong-version fixtures; identical G0 bytes with LF, CRLF and CR endings | Canonical committed LF SHA-256 `5b95531a...c34cd98c`, calculated after line-ending-only normalization, plus authoritative validator | All three line endings identify equivalently; numeric/field/non-line-ending byte change fails closed; no copied silent defaults | provenance/configuration |

Comparison rules: vectors use component absolute comparisons only where the
oracle is component-valued; attitudes use sign-invariant quaternion angle or
rotation-matrix comparison; boundary tests use exact decimal inputs where
possible and `math.nextafter` for adjacent floating-point cases. No test may
derive its expected result by calling the production quaternion or gate helper.

Evidence after implementation must retain the command, exact commit, Python and
NumPy versions, configuration identities, seed interface, per-row outcomes and
artifact hash. Passing module rows does not make the G3 portions of yaw,
contamination, reset or truth-boundary provisions complete.
