# G2-B S0 controller verification matrix

Status: candidate pending original-PA `DESIGN_ACCEPT`. These are component checks, not G3 performance acceptance. Unless a row states otherwise, comparison is `abs(actual-expected) <= 1e-12` with `rtol=0`; exact booleans, reason codes, integers and bit-preserved pairing values use equality. Each oracle is implemented in test code without calling production controller helpers.

| ID | Predeclared inputs and independent oracle | Required test node(s) | G2 disposition / linked frozen specification |
|---|---|---|---|
| B-ATT-01 | identity estimate; +/- x/y/z angles `1e-8`, `.1`; hand Hamilton product and `2*sin(theta/2)*axis` | `cpp/attitude_error_axes_and_small_angle` | complete component check; `B0-VER-CONTROLLER-SIGN`, `B0-VER-CONVENTIONS` |
| B-ATT-02 | nonidentity/multiaxis normalized quaternions; independent four-term Hamilton expansion | `cpp/attitude_error_nonidentity_multiaxis` | same |
| B-ATT-03 | q and -q, exact pi about axes and mixed axis; explicit first-nonzero tie-break | `cpp/attitude_error_antipodes_and_half_turn` | same |
| B-RATE-01 | identity/known attitude fixtures isolate outer loop and both sides/exact boundary of rate clamp | `cpp/outer_loop_and_rate_clamp` | complete component check; `B0-VER-CONTROLLER-SIGN` |
| B-RATE-02 | zero D/I, then one nonzero gain at a time; hand P/I/D sums | `cpp/rate_pid_terms` | same |
| B-DERIV-01 | constant omega, omega step, command-only step; `alpha=dt/(tau+dt)` recurrence | `cpp/measurement_derivative_filter` | complete component check; `B0-VER-CONTROLLER-SIGN` |
| B-DERIV-02 | reset then nonzero first omega; first derivative exactly zero; second hand step | `cpp/derivative_first_step_and_reset` | same |
| B-LIMIT-01 | each axis +/- exact, `nextafter(limit,0)`, `nextafter(limit,+inf)`; independent clamp/strict compare | `cpp/torque_limit_boundaries` | complete; `B0-VER-CONTROLLER-SATURATION`, `B0-VER-PAIRED-COMMAND` |
| B-LIMIT-02 | inspect same-tick request/limited/status/timestamp bundle | `cpp/torque_command_atomic_bundle` | same |
| B-AW-01 | unsaturated, push/exit saturation; hand conditional Ki rate | `cpp/antiwindup_conditional_integration` | complete component check; `B0-VER-ANTI-WINDUP` |
| B-AW-02 | lag-only and limit-only fixtures, then both; hand each rate and I before/after | `cpp/antiwindup_backcalculation_terms` | same |
| B-AW-03 | +/- each I bound and saturation removal over fixed 4-step sequence | `cpp/antiwindup_bounds_and_release` | component recovery only; G3 performance remains open |
| B-PAIR-01 | reset feedback then three consecutive due ticks from design record | `cpp/paired_feedback_three_ticks` | complete component pairing; `B0-VER-PAIRED-FEEDBACK` |
| B-PAIR-02 | same held values with known distinct timestamps; unknown/future/old epoch/fake limited/status | `cpp/paired_feedback_rejections` | same |
| B-TIME-01 | nonzero reset; first tick exact/early/late; duplicate/stale/off-grid; dt 0/-/NaN/Inf | `cpp/time_grid_and_dt_rejections` | controller portion complete; `B0-VER-INVALID-INPUT` |
| B-TIME-02 | reject at due tick, valid same-tick retry vs clean twin; miss tick then later call | `cpp/retry_and_missed_tick_recovery` | declared reset-required recovery; full scheduler recovery G3 |
| B-INVALID-01 | valid=false, wrong shape/type in binding, zero/nonunit q, NaN/Inf, derived overflow | `cpp/invalid_numeric_inputs`, `py/test_invalid_inputs.py::test_invalid_inputs_are_atomic` | component portions; `B0-VER-INVALID-MEASUREMENT`, `B0-VER-LANGUAGE-BOUNDARY` |
| B-INVALID-02 | Python integers at int64 edges and one beyond; caller arrays mutated after call | `py/test_binding.py::test_integer_bounds_and_input_copy` | binding portion; `B0-VER-LANGUAGE-BOUNDARY` |
| B-RESET-01 | establish nonzero I/D/held, reset to next epoch, inspect zero output/state/history | `cpp/reset_clears_all_controller_state` | controller portion; `B0-VER-RESET` |
| B-RESET-02 | duplicate/lower epoch, backward/equal-after-step timestamp, replay old feedback | `cpp/reset_epoch_and_replay_rejections` | same; integrated all-component reset remains G3 |
| B-BIND-01 | fixed vectors through C++ and binding; exact fields/reasons; imported module path asserted | `py/test_binding.py::test_cpp_python_parity_and_module_identity` | component language boundary |
| B-BIND-02 | real G2-A estimate and G1 feedback adapters; G1 `TorqueCommand` construction and actuator consume | `py/test_binding.py::test_g2a_g1_adapter_fixture` | interface compatibility only; no closed-loop claim |
| B-DETECT-01 | isolated compile-time test oracle variants invert attitude-feedback sign and AW feedback sign | `cpp/detect_sign_mutations` | each specified mutation must fail its owning comparison |
| B-DETECT-02 | oracle variant omits AW and substitutes current limited in lag term | `cpp/detect_antiwindup_bypass_and_mispair` | same; production restored before retained run |
| B-CONFIG-01 | actual loader on LF/CRLF/CR byte-equivalent G0; verify digest then authority validator | `py/test_config.py::test_line_endings_and_authoritative_validation` | complete loader behavior |
| B-CONFIG-02 | changed/missing/wrong-version G0 or implementation config; illegal gain/range/tolerance | `py/test_config.py::test_configuration_fail_closed` | complete loader behavior |

## Artifact fields

The component evidence row will retain exact source/build/module/config identities; tool and ABI versions; every case ID and node; raw inputs, independent expected values, actual values and comparison; I/P/D and both back-calculation terms; command/feedback/epoch sequence; rejection snapshots; logs/archive hashes; source run, expiry and review source. Multi-stage frozen specifications remain `partial` where G3 prerequisites are absent. No test result will be entered until it is actually executed.
