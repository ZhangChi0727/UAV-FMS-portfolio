# G3-A frozen saturation reachability diagnostic

Date: 2026-10-15 (Australia/Perth). Classification: development reachability
diagnostic, not scenario acceptance. Decision state: **valid shortfall; parameter
change gate required**.

## Controlled execution identity

- Approved S0 design: `e3a5df2c7b21b4f4a4c7c6f296e0711222ac2569`.
- Executed G3 source: `78abbbe27a6e451049d80fbcf9c8e031a5001b0c`.
- Scenario and frozen seed: `saturation_withdrawal`, `2026100906`.
- Purpose: `reachability_diagnostic`; `acceptance_seed_exposed=true` from this run onward.
- Build: Debug, Python 3.11 WSL, real controller extension
  `build/b0-controller/debug/03_control/b0/b0_controller.cpython-311-x86_64-linux-gnu.so`.
- Controller module SHA-256:
  `2692faceb020bbe43a95aac6e2f4a4d38efabc4454a9b3e7784cb76b7da3d3cc`.
- G0 canonical LF SHA-256:
  `5b95531a6f96cb67ce25f624d6921bd313696f3c0b9868ec1de13c24c34cd98c`.
- Run ID: `g3a-reachability-debug-20261015-01`.

The ignored local run directory is
`build/g3-development/g3a-reachability-debug-20261015-01`. Generated data is
not committed and is currently local-only.

| Retained file | SHA-256 | Bytes |
| --- | --- | ---: |
| `seed-exposure-start.json` | `5cdf8a7a76e683e2d15e79d3716db232897d6f2f47a0a04c66a3e1fa4e399f0c` | 820 |
| `reachability-result.json` | `79e691f5b17655935943ad2e4ae1cb784e1cc82d8a122c36cde8a5a385075a0b` | 1,203,150 |
| `seed-exposure-final.json` | `6a7771ebd67f86cd55822563ee5cb71530d964c19a6a1667f0af4919a7e65dde` | 1,149 |
| `reachability-derived-summary.v1.json` | `0bf9b9f3a5704c559cfcbcc3e639deabd0c1717136e8b71869d3afc7af2905c3` | derived, source-preserving summary |

The start record was created exclusively before component execution. The final
record binds start-record hash
`5cdf8a7a76e683e2d15e79d3716db232897d6f2f47a0a04c66a3e1fa4e399f0c`
to result hash
`79e691f5b17655935943ad2e4ae1cb784e1cc82d8a122c36cde8a5a385075a0b`
and records `execution_status=structurally_complete`.

## Actual result

The frozen `[200,1000)` positive-reachability window produced no saturated
controller publication and no saturated held actuator interval.

| Quantity | Actual | Frozen comparison |
| --- | ---: | --- |
| Saturation union duration | `0.0 s` | `>= 0.05 s` |
| x requested torque minimum | `-0.16653682382488663 Nm` | negative withdrawal response; within `-0.35 Nm` limit |
| x requested torque maximum | `0.16076572340476172 Nm` | below `0.35 Nm` positive limit |
| y requested torque range | `[-0.0026453459741338837, 0.0026074076617446573] Nm` | within `±0.35 Nm` |
| z requested torque range | `[-0.002029010343015998, 0.0020694580450473098] Nm` | within `±0.2 Nm` |

The source result remains byte-for-byte unchanged. The later derived summary
uses signed-limit headroom names and records the x-axis negative and positive
headrooms as `0.18346317617511335 Nm` and `0.18923427659523825 Nm`, respectively.
Positive headroom means that the request remained inside the corresponding
signed limit; it is not saturation margin in the sense of an exercised limit.

The result is `valid_shortfall`, not an execution error. It confirms the S0
reachability risk: the accepted initial controller parameters and frozen 40°
command do not exercise the saturation/anti-windup path. The upper-duration
criterion alone cannot establish that saturation occurred.

## Stop/go consequence

G3 must not fabricate the saturated flag, lower the positive-duration
criterion, change the command, reduce actuator limits, or silently replace the
accepted controller parameters. A second acceptance-seed run would be another
exposure and would not restore an untouched holdout.

The recommended next action is a separately approved, versioned G3 controller
parameter study that:

1. uses only tuning seed `2026100900` while selecting parameters;
2. stays inside the already declared G0 parameter ranges;
3. leaves the frozen scenario, seed, actuator limits and criteria unchanged;
4. records cross-scenario effects and reruns all G2 controller regression and
   G3 interface checks for each proposed final set;
5. returns one explicit parameter overlay and its rationale to the original PA
   for approval before any further acceptance-seed execution.

The diagnostic does not itself authorize tuning. Until the PA decides this
change path, the saturation reachability gate blocks G3 scenario acceptance,
but it does not erase the separately passing scheduler/event/interface checks.
