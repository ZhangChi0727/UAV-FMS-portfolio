# UAV FMS Portfolio

A small, reproducible engineering project with two parts:

1. **B0 attitude platform** (frozen at component level): rigid-body and sensor
   models, a complementary attitude estimator, and a C++17 cascaded
   attitude/rate controller with a Python binding and tests.
2. **EDGE track** (planned): distributed edge AI for UAV bridge inspection.
   Language-model and vision-language inference is placed across onboard, edge
   and cloud resources, and measured by replay. See
   [requirements/edge.sdoc](requirements/edge.sdoc).

No flight, hardware or closed-loop performance result is claimed.
All numbers below come from the commands listed in this file.

## Status

| Area | Requirements | State | Evidence |
|---|---|---|---|
| B0 plant, IMU, actuator | B0-REQ-0004 to 0011 | implemented, unit-tested | `01_simulation/b0`, 25 pytest cases |
| B0 estimator | B0-REQ-0012 to 0015, 0019 | implemented, unit-tested | `02_estimation/b0`, 52 pytest cases |
| B0 controller | B0-REQ-0007, 0016 to 0019, 0026 | implemented, C++ and binding tested | `03_control/b0`, 25 CTest cases (Debug) |
| B0 closed-loop integration | B0-REQ-0002, 0003, 0020 to 0025 | not in active tree | archived at tag `pre-surgery-2026-11-22` |
| EDGE track | EDG-REQ-0001 to 0012 | planned | none yet |

B0 is not accepted as a whole. Its closed-loop integration layer, a saturation
reachability negative finding, and several evidence chains were removed from the
active tree by the lean-restructuring PR. They remain in git history at the tag.

## Repository layout

| Path | Content |
|---|---|
| `requirements/` | StrictDoc requirements: the single systems-engineering source |
| `01_simulation/b0/` | Frame and quaternion conventions, rigid-body plant, IMU, actuator |
| `02_estimation/b0/` | Complementary attitude estimator and its configuration |
| `03_control/b0/` | C++17 controller core, pybind11 binding, Python adapter, tests |
| `05_integration/b0/` | G0 contract (v1 and v2), its validator, and validator tests |
| `edge_inference/` | Planned learning modules for the EDGE track |
| `research/` | Scheduler and probe-timing study code and data |
| `literature/references.bib` | Bibliography |

`05_integration/b0` is kept only because the estimator and controller load and
validate the G0 contract at runtime. The approval records for the estimator and
controller are read by the same loaders.

## Reproduce

Python 3.11 and a C++17 compiler are required. Python dependencies:

```sh
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # Windows
# .venv/bin/python -m pip install -r requirements.txt     # Linux/macOS
```

Python tests run inside each track directory:

```sh
cd 01_simulation/b0 && python -m pytest -q
cd 02_estimation/b0 && python -m pytest -q
cd 05_integration/b0 && python -m pytest -q
```

The C++ controller and its Python binding are built and tested with CMake. The
Python binding test needs the MinGW runtime DLLs next to the module on Windows.

```sh
cmake --preset b0-controller-debug
cmake --build --preset b0-controller-debug
ctest --preset b0-controller-debug
```

Requirements are exported with StrictDoc:

```sh
strictdoc export requirements --output-dir requirements/build
```

## Roadmap

1. **Now**: merge the lean-restructuring PR; freeze `requirements/` at a tag after review.
2. **EDGE-1**: task instruction to structured task (EDG-REQ-0001) on the development GPU.
3. **EDGE-2**: image to structured finding with abstention (EDG-REQ-0002).
4. **EDGE-3**: latency and resource profiling of the models (EDG-REQ-0004).
5. **EDGE-4**: placement policy and fallback on replayed scenarios (EDG-REQ-0005 to 0007).

Each step adds code, tests and a requirement update in the same change. See
[edge_inference/README.md](edge_inference/README.md) for the module structure.

## Conventions

NED navigation frame, body frame x forward, y right, z down. SI units. Quaternions
are scalar-first Hamilton, rotating body vectors into the navigation frame.
Simulation truth is never an estimator or controller input after initialization.
