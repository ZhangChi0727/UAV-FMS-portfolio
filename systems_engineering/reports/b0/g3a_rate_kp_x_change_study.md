# G3-A rate-Kp-x bounded change-study result

Date: 2026-10-15 (Australia/Perth). Classification: development feasibility
study, not parameter acceptance and not scenario acceptance. Decision state:
**no feasible candidate; stop and return to the original PA**.

## Authority and fixed scope

The original PA accepted a single bounded study under `CHANGE_STUDY_ACCEPT`.
Only `controller.rate_pid.kp.x` could vary in `[0.0, 0.2] Nm*s/rad`; all other
controller parameters, the G0 scenario, event interval, horizon, criteria,
limits, schedule, plant, IMU, estimator and reset transaction remained frozen.
The seven candidates were predeclared before execution and each could run once.

- Approved S0 design: `e3a5df2c7b21b4f4a4c7c6f296e0711222ac2569`.
- Executed source: `559716a27b2dcc191d9ec674d7e621a0bc08340a`.
- Protocol: `05_integration/b0/configs/b0_g3_rate_kp_x_study.v1.json`.
- Protocol SHA-256: `52758860a585f01aae5eeb07cc8f9da5deef6b854ca868bdba656a35d06959b6`.
- Study ID: `g3a-rate-kp-x-study-v1-debug-20261015`.
- Build: Debug; real C++ controller binding; WSL Python 3.11.
- Scenario: `saturation_withdrawal`; tuning seed `2026100900` only.
- Acceptance seed `2026100906` was not executed by this study.
- Feasibility rule: saturation union duration `>= 0.05 s` in `[200,1000)`
  with all declared integrity checks satisfied.

The ignored local run directory is
`build/g3-development/g3a-rate-kp-x-study-v1-debug-20261015`. Generated raw
JSON remains local-only and is not committed. Its `study-summary.json` is 3,311
bytes with SHA-256
`905f0cde814527d7590dbcd147144e3b7a92f1a34a29eae7c66ca4bf4a484eea`.

## Candidate results

All seven declared candidates completed once. Parameter hashes bind the
candidate overlay; result hashes bind the retained rich trace. No candidate
met the duration rule, so no overlay is ranked or proposed.

| Candidate | rate Kp x | Saturation duration | Feasible | Parameter SHA-256 | Result SHA-256 |
| --- | ---: | ---: | --- | --- | --- |
| `01-kp-x-0p080` | 0.08 | 0.000 s | no | `afb617fd9bfc92eb0cf5bf1191a477375bd9740cfccd38a0135a0b85f8da509c` | `b32f4fcaaffa1ee2726e085934ae074aca2f6d13d3e5313ca3fc71b1f0c279e1` |
| `02-kp-x-0p170` | 0.17 | 0.000 s | no | `39948d407c59ec538b78a661e508da48a96498f8ff660fa410a2c5973ad724d0` | `806d8e106825db54e070b5fa568e657ed3f5fce8a2f3a2e16cee5a7b6cec9879` |
| `03-kp-x-0p175` | 0.175 | 0.005 s | no | `adfd9a631d404bd3ee9fc6ccbfbbd08c337ee02999b4946001c6a65d117ba45c` | `392f5c8f646fb81c359d0005eccab1780afd5d9971035e5ba660f38908f2d105` |
| `04-kp-x-0p176` | 0.176 | 0.010 s | no | `d9ba812c9d8cd0e6f3cdb2cc058748074fbb78f0f9b0f6f7a74fe4bf8c9e4f37` | `6c95e20f0334491a9a02afd63d2a3a84e14f6e76ae183bebd6f22f8e9462e917` |
| `05-kp-x-0p180` | 0.18 | 0.010 s | no | `3fc95e733ee66f035d83fbaca6a40b98d3b2368b24459dce36e8fc6c809d366f` | `6e5f138a4f1113b985842d010bf5a93b95a6eff01733790cf1a9f24061930587` |
| `06-kp-x-0p190` | 0.19 | 0.020 s | no | `01aae5c899bf784c857c7a60248347e96eb38c620ad15481c702eab37ecf5cff` | `ab271030b3a0539b5ece4c7d95253c5b6cf41499e1c5182987a7942508ba6268` |
| `07-kp-x-0p200` | 0.20 | 0.025 s | no | `6d9d79b0e8864dc800a76780c4c49004b22ed0960693519bfd2d1feaa7ab7ed1` | `1ae3216db217c46bc8382bae9f54ef96a0261ae35d8110862c1c7be78430752a` |

The per-candidate start/final record hashes are retained below so the local
execution transaction can be checked independently of the result payload.

| Candidate | Start record SHA-256 | Final record SHA-256 |
| --- | --- | --- |
| `01-kp-x-0p080` | `b6f8745018b07b9e86ea158517f47134e2b5fa1ab132c3cfdedec1e2f1bad6a7` | `a187465c2d52f14b6d56a67a0482dae5d834c3f3615dc08b6b812f1c95aa0de5` |
| `02-kp-x-0p170` | `ceb46ca2a27ba1263a6d81e20ee6c2f8ffe5e442574a554aaa54ec64914a3543` | `c948f281f2a399e497507a76d87b34e7b89040b5b77bebe9ecd116fbaefe7cbf` |
| `03-kp-x-0p175` | `8efe75333cf7a978ebb2f521eadf9e873d50d93e944e627d983195584e19cc9b` | `a2dadd6407194f44ec4a0652b8cc353e2cbb6fb8aecafa40546bc99573b05601` |
| `04-kp-x-0p176` | `eda51aa13c945f0b3ab61450e3a1080fd71d65600d52505f8ae85b64a0bac472` | `3b7017054304f8834bb17eb85f12ab264ae06ea52c32d616ad946aabeb89a862` |
| `05-kp-x-0p180` | `4f15cddebebaa8411a2e89dafe24fe48b00e9f51f468ab9c68f407e9d60d79d7` | `5935f35d15a7bc6a4efd970819b8117dd458fdf1f8af2ac60029446b5f01a998` |
| `06-kp-x-0p190` | `60c83c3a14714eebd02f852a3cf98ef9f478683b1d51a275b0f40301e09f9946` | `9511425a3b86ac2b4e7eab78681172b12c910cbd3464da3cf31f282f2e2ee35b` |
| `07-kp-x-0p200` | `725a684e618c0396a15733878524e85ea1f00039c913cf9f1c3090a2b6fb1496` | `a606735900b11583575e83195455137c0b5291fb78b66191c17a59d1e182dee0` |

## Post-execution provenance erratum

PA review identified that the sealed tuning-v1 field
`acceptance_seed_exposed=false` ambiguously described only the current run. It
does **not** reverse the earlier permanent exposure of acceptance seed
`2026100906`. The effective interpretation for every candidate is therefore:

- `acceptance_seed_executed_this_run=false`;
- `acceptance_seed_previously_exposed=true`;
- `acceptance_seed_exposure_cumulative=true`.

The original seven candidate files, study summary and historical exposure files
remain byte-for-byte unchanged. A versioned, ignored local sidecar atomically
links all seven start/result/final triples to the historical exposure
start/result/final hashes. It was generated by a read-only verification at
attestation head `5f359236b6cfba9c25a5446e4d3dfda5e3acccf9`:

- path: `build/g3-development/g3a-rate-kp-x-study-v1-debug-20261015/provenance-erratum.v1.json`;
- SHA-256: `96bee5b0c61b3a266ae3bddbf259640ee9639e1a159143b31b70f4dd59d5217b`;
- seven candidate chains verified; historical exposure chain verified;
- 33 behavior-closure paths checked against source
  `559716a27b2dcc191d9ec674d7e621a0bc08340a`;
- 16 paths had execution-time hashes in the sealed v1 records; 17 missing paths
  were reconstructed after execution from the source commit and are labelled as
  such;
- the currently available controller module hash still matches all seven sealed
  candidate records;
- raw SHA and canonical-LF/source-checkout hashes are distinguished so Windows
  line-ending filters cannot create a false source mismatch.

A non-scenario identity check at commit
`c71c3c0dde3533985eeea0b67f81de1cde751df4` exercised the new enforcement:
all 33 live closure paths matched that source commit, and the Debug controller
module SHA-256 remained
`2692faceb020bbe43a95aac6e2f4a4d38efabc4454a9b3e7784cb76b7da3d3cc`.
This check did not execute a scenario or seed and does not repair the historical
study's missing execution-time capture.

This is deliberately classified as
`post_execution_attestation_negative_feasibility_finding_formal_evidence_incomplete`.
The missing execution-time closure cannot be retroactively presented as if it
had been captured during the study. The negative feasibility finding remains
locally useful, but the study is not complete formal implementation or
acceptance evidence. Future records use separate current-run, previous-exposure
and cumulative-exposure fields and require the full behavior closure to match
the source commit before execution.

## Integrity and interpretation

The original runner sealed the whitelist and checked the direct controller-core
relationships `P = Kp * rate_error` and
`request = P + I_before + D`. Each result retains raw/adapted IMU, truth,
estimate, command, requested/limited/actual torque, saturation pairing and
I/P/D/anti-windup diagnostics. Source identity covers the G0/G1/G2/G3 inputs,
approval records, build files and G3-A workflow.

The monotonic increase from `0.000 s` to `0.025 s` does not satisfy the frozen
`0.05 s` lower bound and does not authorize extrapolation beyond the declared
range. This is a bounded negative feasibility finding, not evidence that the
scenario criterion is wrong and not approval to change another gain.

## Required decision

The protocol's stopping rule now applies. Do not add candidates, vary Ki/Kd or
attitude gains, change another axis, alter the scenario/criterion, or run an
acceptance seed. There is no parameter overlay to approve. The original PA must
decide whether to accept the negative study result and authorize a separately
bounded change path; until then, G3 scenario acceptance remains blocked while
the independently passing G3-A scheduler, event and interface work remains
valid.
