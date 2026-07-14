# AGENTS.md

## Cursor Cloud specific instructions

This repo is a **UAV Flight Management System algorithm portfolio** (Python 3.11+ and
C++17). It is currently a **Phase 0 scaffold**: most source functions are placeholders
that `raise NotImplementedError("Phase 3X")` and many tests `pytest.skip(...)`. There
are no long-running services, databases, or web servers — it is a local scientific
computing codebase. Standard commands live in `README.md` and `.github/workflows/ci.yml`.

### Python environment
- Dependencies are installed into a virtualenv at `.venv/` (created by the update
  script). Activate it before running anything: `source .venv/bin/activate`.
- `python3` is 3.12 (satisfies the 3.11+ requirement); there is no bare `python` binary
  outside the venv.

### Running Python tests (non-obvious)
- Track directories start with digits (e.g. `02_estimation/`) and each test imports its
  **track-local** module (e.g. `from ekf import EKF`, `from models.tcn import TCN`).
  Running `pytest` from the repo root **fails collection** with `ModuleNotFoundError`.
- Run tests from **within each track directory** instead, e.g.:
  - `cd 02_estimation/python && python -m pytest -v`
  - `cd 03_control/python && python -m pytest -v`
  - `cd 04_fault_detection && python -m pytest -v`
- Failures like `NotImplementedError: Phase 3A/3C` and `pytest.skip` are **expected**
  scaffold behavior, not environment problems. CI runs pytest/ruff/black from root with
  `continue-on-error: true`, so it tolerates these.

### C++ build (02_estimation)
- System deps (`libeigen3-dev`, `catch2`, `pybind11-dev`, and the clang/`libstdc++-14-dev`
  toolchain that `/usr/bin/c++` resolves to) are preinstalled in the VM snapshot; the
  update script does not reinstall them.
- Configure + build: `cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build`.
- Targets `ekf_lib` (static lib) and `ekf_cpp` (pybind11 module) build cleanly. The
  `ekf_tests` target currently **fails to compile** because `test_ekf.cpp` uses unqualified
  `Approx(...)` which Catch2 v3 exposes only as `Catch::Approx` — this is a pre-existing
  source bug, not a setup issue. Build only the good targets with
  `cmake --build build --target ekf_lib ekf_cpp` if you need to avoid it.
- The compiled binding is `build/ekf_cpp.cpython-3XX-*.so`; import it by adding `build/`
  to `sys.path` (it is built against system Python 3.12, ABI-compatible with the venv).

### Out of scope
- `README.md` lists MATLAB R2023b + Simulink as a prerequisite for the plant model, but it
  is proprietary/unavailable in this environment and current code does not call it.
