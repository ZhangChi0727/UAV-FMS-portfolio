# G3-A external authority and finite F0 candidate collection

Status: static implementation candidate; not executed, syntax-checked, imported,
tested, or accepted by its author. Only PA and a non-author can release/accept a
specific metadata invocation. This is not a build runner, test framework, generic
attestation service, or proof of a complete operating-system supply chain.

## 1 Ownership and two non-circular stages

`g3a_authority.py` is independent of the subject driver/session. It imports only
the standard library. Import-time work defines constants/functions; no component,
metadata collection, Git call, file access or argument parsing happens at import.

1. `collect`, before any DUT import/construction, reads externally accepted policy
   bytes and actual source/config/environment/build/module bytes. It produces
   **candidate facts**, not a human signature. It never reads a raw evidence trace.
   Expected parameters are pure approved-data mappings, not future object states.
2. `bind-transport`, after the raw exists, verifies the separately supplied basis
   digest, reads the raw once, and writes a new consumer authority containing its
   transport hash/locator. It never obtains expected identity/parameters from raw.
   The immutable basis and raw are not modified. There is no embedded self-hash.

`load_consumer_authority(path, expected_sha256)` strictly admits the serialized
consumer bytes and base64 registry, then supplies `input_artifact_bytes` for the
independently owned three offline checker APIs. A consumer may equivalently decode
the documented base64 format itself. The checker does not call this collector to
create expectations or call a production loader.

PA owns `configs/g3a_authority_policy.v1.json`; this helper cannot change it.
The helper author does not independently accept this helper or its own output.
TC owns subject implementation/real lifecycle observations, not this authority.

## 2 CLI and retained artifacts

The following are interface descriptions, **not released runnable commands**:

```text
collect --policy PATH --expected-policy-sha256 HEX
        --source-root ROOT --build-type Debug|Release --phase prebuild|preflight
        --environment-facts ENV_JSON --out-dir NEWROOT
        (--git-executable ABSOLUTE_GIT |
         --source-facts SOURCE_JSON --expected-source-facts-sha256 HEX)
        [--build-facts BUILD_JSON --build-dir BUILD_DIR --module MODULE]
        [--github-event EVENT_JSON --github-event-name pull_request|push
         --github-repository OWNER/REPO --github-sha SHA
         --github-run-id ID --github-run-attempt N]

bind-transport --basis BASIS_JSON --expected-basis-sha256 HEX
               --raw RAW_FILE --locator ARTIFACT_ID --output NEWFILE
               [--parent-raw-sha256 HEX --diagnostic-id ID]
```

The approved command supplies an expected policy digest independently: a local PA
value, or the constant in the exact candidate workflow already reviewed by PA.
Computing that expected digest from an arbitrary unaccepted policy is not approval.
The policy has neither its own digest nor a not-yet-existing source commit hash.
All actual source files, including policy/helper/checker/workflow/test definitions,
must belong to its finite `source_paths`. Its own file is not in `fixed_files`.
Collection runs with the accepted normal-site Linux venv interpreter using
`-I -B`; missing isolated/no-bytecode flags refuse environment collection.
The already reviewed finite startup chain is a prerequisite, not silently
replaced by this helper. `prebuild` cannot resolve `$BUILD_DIR` boundaries unless
an actual existing `--build-dir` is explicitly supplied for those finite inputs.

Output directory/file must be new; the directory's parent must already exist.
No overwrite, retry, amend, source repair, install or fallback occurs. Failure
before output creation leaves no output; interrupted writes may leave a partial
root, which must be retained and may not be treated as successful evidence.

`prebuild` writes source/config/expected-parameter/observer/environment manifests,
snapshots and `collection-state.json` with `PREBUILD_ONLY`. It creates **no**
`authority-basis.json`, requires no future binary, and cannot qualify a DUT run.

`preflight` additionally requires real build metadata/module/execution records,
writes `f0-candidate.json` and an immutable `authority-basis.json`. Status is
`CANDIDATE_FACTS_READY_FOR_PA_F0_REVIEW`, or `CI_POLICY_PREFLIGHT_PASS` under the
accepted CI policy. Every output retains `human_f0_accept=false`.

Each input is read into bytes, checked/parsed from that same value, and archived.
`snapshot-index.json` lists snapshot locator/path/size/raw SHA-256. Source text,
configuration, profile/spec/schema/checker and derived manifests are base64 encoded
in the authority registry. Environment/tool/header/native-library/module raw bytes
are separate retained snapshots: not copied into every diagnostic consumer object.
Their independently observed hashes and paths are in the environment/F0 manifests.
Snapshot retention and expected in-memory checker inputs are different finite sets.

Manifests are canonical compact ASCII JSON plus one final LF. Parameter **values**
digests use compact sorted ASCII JSON without the LF, matching the evidence spec.
Full-byte artifact digests always include the actual artifact's LF if present.
No artifact contains its own full-byte digest.

## 3 Exact finite policy interface

Required root fields:

| Field | Meaning |
| --- | --- |
| `policy_version` | `b0-g3a-authority-policy/v1` |
| `work_order` | `{path, sha256}`; actual approved bytes |
| `source_paths` | Unique canonical repo-relative regular file paths |
| `fixed_files` | Relative file to expected raw SHA-256 mapping |
| `config_approval_paths` | JSON configuration/approval inputs for raw/LF/parsed digests |
| `parameter_bindings` | Exactly the full G1/E/C field bindings below |
| `evidence_files` | Exact `profile`, `spec`, `schema`, `checker` paths |
| `observer_paths` | Actual recorder/observer/adapter source paths |
| `comparison_policy`, `conventions` | PA-accepted finite policy, unchanged into basis |
| `environment`, `build`, `ci` | Finite rules below |
| `execution_plan` | Accepted fixed lifecycle callsites/auxiliary counters, not observations |

Unknown root keys are refused. Optional `canonical_lf_checks` entries have
`{path, sha256}`. Optional `approval_digest_checks` entries have
`{document_path, approval_path, approval_pointer, kind}` where kind is
`canonical_lf_sha256` or `canonical_json_sha256`. The helper compares only those
explicit approved digest definitions; it does not execute the G0 validator.
The actual production validation remains part of later observed lifecycle calls.

Paths reject absolute/traversal/backslash spellings, source symlink escape and
untracked/different Git blob bytes. This execution policy requires exact Git raw
bytes (normally isolated LF checkout), not the shared Windows CRLF planning copy.
Canonical-LF config approval checks never silently rewrite any consumed byte.

Source identity uses one accepted provider:

- Three Git builtins: `rev-parse --verify HEAD`, `rev-parse --verify COMMIT^{tree}`,
  `ls-tree -r -z COMMIT -- FINITE_PATHS`. COMMIT is the validated forty-hex value
  from the first read, preventing mixed HEAD/tree reads. Each uses the explicit absolute Git binary,
  `--no-optional-locks`, `-c core.fsmonitor=false`, exact cwd, no stdin and a 30 s
  child timeout. No `status`, clean/smudge, `cat-file --filters`, hook, signing,
  checkout or network command is invoked. Effective Git startup/configuration and
  binary identity must already be accepted in the invocation manifest. The helper
  removes inherited `GIT_*` variables and disables prompting/optional locks; it
  does not alter persistent user configuration or bypass mandatory Git writes.
- External JSON `b0-g3a-source-facts/v1` with `source_commit`, `source_tree`, and
  exact `files:{relative_path:git_blob_sha1}`. Its independent expected SHA-256 is
  mandatory. This provider is accepted external Git evidence, not a label proving
  itself. Every file still matches the declared blob's Git object digest from
  the actual same-read bytes. Source commit/tree are forty-digit Git SHA-1 IDs.

The source manifest records real commit/tree and every raw SHA-256/byte count/blob
ID. A label in raw cannot replace this source basis. Protection is finite closure
consistency, not a concurrent adversarial-filesystem security proof.
`source-provider.json` separately retains the actual Git executable/hash/argv or
external-facts digest; differing Git installations do not change the source-only
closure digest across Debug/Release. Whole-checkout cleanliness and absence of
undeclared import-shadowing files remain prerequisites established in accepted
isolation/E2 evidence, not a claim made by hashing only the declared source set.

`execution_plan` has `plan_version=b0-g3a-execution-plan/v1`, nonempty
`lifecycle_callsites:{site:{owner,method,parent_site}}`, and
`auxiliary_counts:{profile_id:{counter:nonnegative_integer}}` for exactly the eight
S/L1/L2/O1/O2/E/T1/T2 profiles. Parent is null or a nonempty explicit allowed-parent
site list; references must exist. Booleans are not integer counts. Missing/empty
plans refuse collection, never an empty complete-ready escape. The helper only
checks this finite typed envelope and exports it unchanged; the independent
checker reconstructs actual records and counter semantics. No expected count is
used to fabricate a raw invocation or return. Null-profile setup allocation is
part of the PA-accepted E2 plan, not inferred here.

## 4 Expected parameters, never anticipated actual objects

Bindings use `component = g1|estimator|controller`, unique `field`, nonempty
`unit`, and one source choice:

- `source_path` + RFC6901 `json_pointer`, from a `fixed_files` JSON input;
- `literal` + nonempty `source_locator`, a specifically accepted fixed result
  or path. There is no formula/expression evaluator.

Encoding is `float64_tree` (finite scalar/vector/matrix numbers to canonical
`float.hex()`), `exact_json` (typed JSON values, including integer ticks), or
`source_relative_path` (literal approved relative config file expanded under actual
source root; only `config_path`/`g0_config_path`). No raw-proposed path is used.

Complete field sets are frozen to the actual public parameter definitions:

- G1: `inertia_kg_m2`, `actuator_time_constant_s`, `actuator_limits_Nm`,
  `gravity_n_m_s2`, `gyro_noise_std_rad_s`, `gyro_bias_rad_s`,
  `accelerometer_noise_std_m_s2`, `accelerometer_bias_m_s2`, `base_period_s`,
  integer `imu_period_ticks`, `config_path`.
- Estimator: `sample_period_s`, `gravity_m_s2`, `unit_norm_tolerance`,
  `correction_gain_per_s`, `accelerometer_gate_deviation_m_s2`,
  `maximum_correction_step_rad`, `timestamp_tolerance_s`, `config_path`,
  `g0_config_path`.
- Controller: nine vectors `attitude_kp`, `rate_kp`, `rate_ki`, `rate_kd`,
  `integral_limit_Nm`, `rate_limit_rad_s`, `torque_limit_Nm`, `kaw_limit_per_s`,
  `kaw_lag_per_s`; four scalars `derivative_time_constant_s`,
  `controller_period_s`, `timestamp_tolerance_s`, `quaternion_norm_tolerance`.

`parameter_inputs` is a `b0-g3a-expected-parameter-inputs/v1` manifest with
`semantics=approved_expected_inputs_not_runtime_observations`, `components`,
`bindings`, `values_sha256`. `components.plant/actuator/imu` each contains the
same complete G1 values; estimator/controller contain their complete values.
The three digests are keyed `g1`, `estimator`, `controller`. Actual object IDs,
constructor fields, returned objects and readbacks exist only in the subsequent
real lifecycle records. The independent checker must compare them to this basis.
No default loader, validator, parameter getter or throwaway core is called here.

## 5 Environment and build facts are independently re-read

`environment-facts` is JSON with `schema_version=b0-g3a-environment-facts/v1`,
`python:{major,minor,soabi,prefix,base_prefix,executable}`, `package_versions`,
and finite `files:[{role,path,bytes,sha256}]`. This is an E2/workflow input, not
data generated by the subject raw. The collector compares Python fields to its
own actual interpreter, package versions/names to `importlib.metadata` without
importing those packages, and each file's actual bytes to the finite manifest.

`environment` policy contains `python_major`, `python_minor`, `package_versions`,
`trusted_platform_boundary`, `required_file_roles` and `file_role_rules`. Required
roles and rule keys must be exactly the observed roles. Every rule contains
`allowed_roots`, `allowed_paths`, `min_files`, `max_files`; counts are positive
finite integers. Aliases are only `$SOURCE_ROOT`, `$BUILD_DIR`, `$PYTHON_PREFIX`,
`$PYTHON_BASE_PREFIX`, `$PYTHON_EXECUTABLE`, `$PYTHON_INCLUDE`, optionally followed
by a fixed relative suffix. There is no recursive scan or arbitrary expression.
Actual resolved paths must remain within an allowed root or equal an exact path.
Duplicate resolved paths or per-role boundary-relative names are refused. Relative
names include the chosen registered boundary index: the real CMake launcher and
binary may legitimately both have basename `cmake` under different roots. Rules are a
finite selected-file contract, not proof that a broad role label is complete.
PA/non-author must accept the E2 file set/recipe before actual collection.

Semantic bindings include actual `python_binary`, actual venv `pyvenv.cfg` under
`python_configuration`, actual installed distribution METADATA **and RECORD**
under each `package_metadata:NAME` role, actual PATH cmake/ninja launchers, and
the build Cache's actual CMake/compiler/Ninja binary paths. A CMake launcher hash
cannot be substituted for its underlying ELF. Dependency headers/native/vendor
files use the separately accepted finite roles/ranges. No version command, ldd,
compiler probe, NumPy/pybind import or all-venv capture is hidden in collection.

`build-facts` has `schema_version=b0-g3a-build-facts/v1`, real `source_commit`,
`source_tree`, `build_type`, finite `files`, and `execution_evidence` with
`status=completed`, integer `configure_exit_code=0`, `build_exit_code=0`.
The policy supplies `required_file_roles`, `file_role_rules` and
`required_cache_values`. Cache/compile_commands/build.ninja are bound to the
actual `--build-dir`; source/type/required flags and actual tool paths must match.
Roles include `cmake_cache`, `compile_commands`, `build_ninja`, `ninja_rules`,
one or more `execution_log`, and `controller_module`.
`ninja_rules` is exactly the build's `CMakeFiles/rules.ninja`, not an arbitrary
same-role file. `compile_commands` must be nonempty JSON; toolchain flags and
actual compiler execution remain subject to the independently reviewed E2/F0
evidence, not inferred solely from that file's existence.
Cache `CMAKE_HOME_DIRECTORY`, `CMAKE_COMMAND`, `CMAKE_CXX_COMPILER` and
`CMAKE_MAKE_PROGRAM` must each exist as a nonempty absolute-path string before
resolution/comparison. Missing, empty or relative entries are refused, including
when the collector's current working directory happens to be the source root.
No missing path is interpreted as `Path("")` or repaired from the current cwd.

The accepted route is explicitly pinned Catch source, not an installed-package
branch. Cache `Catch2_DIR` must be absent or `Catch2_DIR-NOTFOUND`;
`Catch2_SOURCE_DIR` and the explicitly provided `FETCHCONTENT_SOURCE_DIR_CATCH2`
must be nonempty absolute paths resolving to the same real directory. All finite
`catch_source` records must lie under that actual consumed root. This binds the
captured dependency to the selected CMake path rather than merely an allowed
directory. Exact Catch version/revision and file-set applicability still need
retained E2 evidence; directory existence is not a claim of the pinned identity.

The actual module is inside that build directory, named `b0_controller` plus the
actual interpreter EXT_SUFFIX, has ELF magic, and has same-read raw bytes retained.
ABI binding here is interpreter/build identity and file naming, not an extension
import test. A completed-build input/log is retained external workflow/supervisor
evidence; the collector does not rerun the build or make cryptographic malicious-
builder attestation. PA evaluates the actual build execution/source applicability.

Trust boundaries are explicit: OS/kernel/system loader and selected system
libraries; CPython standard library except explicit startup records; installed
native tool behavior under accepted execution policy. This is deliberately not
all dynamic-library/all-file-I/O attestation. Unknown paths, omitted/extra roles,
wrong interpreter/package/module/configuration or incomplete build facts refuse
the batch. Missing evidence is not filled from a previous run or subject claim.

## 6 CI and local release are different from human acceptance

CI accepts only declared `pull_request`/`push` events and exact repository name.
It reads actual external event bytes. PR selects `pull_request.head.sha`, never
the synthetic merge SHA; push selects `after` and also matches `GITHUB_SHA`.
The selected head equals actual checkout HEAD. Run ID/attempt are positive and
retained. The actual event JSON digest is retained independently of raw.

The trusted root is PA's prior review of the exact policy/workflow/helper
candidate. A workflow constant supplies the fixed expected policy digest.
Accepted CI source policy can delegate qualification of that event head under
these rules; it does not demand a future module digest before compilation or
PA physically signing every ephemeral run. The collector reports
`CI_POLICY_PREFLIGHT_PASS`, never a human `F0_ACCEPT`. This arrangement is **not**
a general security proof against malicious candidate workflows or compromised CI.

This implementation's environment preflight is Linux/ELF only, matching the
accepted WSL/Ubuntu route. It does not qualify a native Windows ABI/build.

Local collection remains candidate facts until original PA accepts the exact
input/build/module and separately releases the DUT invocation. CI must complete
accepted policy preflight before DUT loading. PA later independently reviews the
candidate CI evidence. No automatic merge, parameter acceptance, B0 normal-scene
acceptance, Issue closure, G3-B/C/G4/B1 activation or hardware claim follows.

## 7 Transport and checker data contract

The basis preserves exactly the existing **sixteen** identity fields in the
evidence schema/driver. No seventeenth field is invented. All other authority
data is outside identity. The basis has `authority_version`, `identity`,
`parameter_inputs`, `comparison_policy`, `conventions`, collection/policy facts,
`execution_plan`, `artifact_sha256` and `input_artifact_base64`. It has no
`transport` or own hash.

`bind-transport` admits the expected basis bytes, checks every internal base64
artifact/digest, and writes a new copy with only `transport` and
`authority_basis_sha256` added. Transport has `sha256`, `artifact_locator` and
optional paired `parent_raw_sha256`/`diagnostic_id`. It does not parse raw identity
or call the independent semantic checker. The raw may still be invalid; the
result explicitly says `TRANSPORT_BOUND_NOT_SEMANTICALLY_ACCEPTED`.

`load_consumer_authority` checks expected consumer digest, verifies the canonical
basis reconstructed without those two added fields, checks artifact registry,
and decodes detached bytes. Reconstructed-basis digest assumes the collector's
documented canonical-plus-LF basis format; arbitrary reformatted basis JSON is
not silently accepted. Checker rules, config-document recomputation, lifecycle
comparison and diagnostic single-defect checks remain independently owned.

## 8 Static candidate validation boundary

Tests in `tests/test_g3a_authority.py` are source only until PA releases their
explicit execution. They use synthetic small fixtures, not plant/controller/
estimator simulation or seeds. They address strict JSON, policy/source/parameter
bindings, immutable basis/transport, external event mismatch, role boundaries,
prebuild non-F0 and absence of raw/loader use. They are not substitute G3-A
lifecycle proof or complete environment/build qualification.

This author has not run imports, compilation, syntax tools, lints, tests, Git
subprocesses, metadata scripts or builds. Non-author static review and later
explicitly accounted execution are required before reporting any passed check.
