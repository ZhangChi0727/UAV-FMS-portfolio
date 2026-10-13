# G1.5-B D2-candidate validation record

Date: 2026-10-13 (Australia/Perth). Candidate asset commit:
`ddd281fd0a94ee59635accb5f41500fac05284b7` (S). All commands exited zero unless
explicitly stated. Counts are checks executed, not B0 behaviour claims.

| cwd / environment | Command scope | Actual result |
|---|---|---|
| `05_integration/b0`, Python 3.11.17 `.venv-b0` | Ruff; default/v1/v2 `validate_config.py`; track pytest | Ruff passed; three configurations valid; 165 passed |
| `01_simulation/b0`, same environment | Ruff; `pytest -q tests`; `evidence.py --output /tmp/...` | Ruff passed; 25 passed; temporary JSON SHA-256 `4d289e74322367e571a225332bda7a8e66af3df24da381722c3dbbb3a9cd4abd` |
| repository / isolated G1.5-B environment | formal checker; formal fixtures | 30 requirements, 26 model identities, 29 planned verifications; 24 passed |
| `tools/systems_engineering` / isolated environment | governance fixtures | 6 passed |
| `tools/systems_engineering/g15b_pilot` / isolated environment | historical structured-pilot and native StrictDoc fixtures | 40 passed plus 6 passed; historical total 46 preserved |
| repository / isolated environment | sysmlpy parse/analyse; StrictDoc export; projection check; Ruff | zero SysML semantic errors; export completed to `/tmp`; projections current; Ruff passed |

Fixed isolated versions: Python 3.11.17, jsonschema 4.23.0, pytest 8.3.5,
StrictDoc 0.30.1, sysmlpy 0.33.2. The G1 evidence output was temporary and its
embedded `git_sha` is the pre-S committed head used by that existing generator;
the G1 implementation/configuration tree had no diff from `origin/main`, so it
is regression evidence only and is not imported as satisfaction evidence.

Repository checks found:

- G0 v1 blob `0c1ac44105d8dffed09c2c8835cab697bc978068` equals `origin/main`.
- G0 v2 blob `1beff6e6a9a81d0ab92b2059a93207ffed9d291d` equals `origin/main`.
- No `01_simulation/b0` or G0 configuration source diff from `origin/main`.
- `git diff --check` passed.
- Protected local work-order SHA-256 remained
  `96d45d4215c2215bb50ea0c7b863b627fa2e7d8d64ada3bb456950a2aa0d44a5`
  and that file is excluded from S/M.

Manual reading acceptance at 1280×720 and 1440×900 is deliberately not
pre-filled. It must be recorded from the user's observation of the exact S
StrictDoc export before PA handoff.

The earlier S/M candidate was superseded after reading inspection found that
the StrictDoc projection did not display `acceptance_condition`. The new S adds
distinct labelled Acceptance and planned Verification fields and a regression
test; authoritative requirement bodies and acceptance text are unchanged.
