# UAV Flight Management System — Algorithm Portfolio

> A simulation-driven algorithm portfolio demonstrating state estimation,
> geometric control, and deep learning fault detection for autonomous systems —
> implemented in Python and C++, with a parametric data generation pipeline.

[![CI](https://github.com/ZhangChi0727/uav-fms-portfolio/actions/workflows/ci.yml/badge.svg)](https://github.com/ZhangChi0727/uav-fms-portfolio/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![C++](https://img.shields.io/badge/C++-17-blue.svg)](https://isocpp.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Overview

This project designs and implements a simulation environment for autonomous UAV
flight, used as both the development platform and verification evidence generator
for three algorithm tracks:

| Track | Algorithm | Implementation |
|---|---|---|
| State Estimation | EKF INS/GNSS fusion + Monocular VO | Python + C++17 |
| Geometric Control | SO(3) attitude controller + LQR baseline | Python + Simulink |
| Fault Detection | TCN sensor anomaly classifier | Python + PyTorch |

The simulation pipeline generates parametric synthetic datasets for DL training,
runs integrated software-in-the-loop (SIL) scenarios, and produces Monte Carlo
benchmarks comparing EKF vs UKF under parameterized GPS outage conditions.

Development is governed by the lightweight
[Development Baseline v0.1](07_docs/development_baseline.md). The first vertical
slice is a deterministic Python truth/sensor fixture, a Python error-state EKF,
and reproducible navigation evidence.

---

## Repository Structure

```
uav-fms-portfolio/
├── 01_simulation/          # Plant model, sensor models, scenario generator
├── 02_estimation/          # EKF/UKF — Python implementation + C++17 port
├── 03_control/             # Geometric control on SO(3) + LQR comparison
├── 04_fault_detection/     # TCN fault classifier — data pipeline + training
├── 05_integration/         # Integrated SIL, fault scenarios, Monte Carlo
├── 06_safety/              # FMEA/FTA artifacts from Isograph RWB
└── 07_docs/                # Requirements, architecture, V&V report
```

---

## Key Results

> *To be populated as each phase completes.*

| Metric | Requirement | Result |
|---|---|---|
| Position error (30s GPS outage, 95th pct) | < 5m | — |
| Attitude settling time (10° step) | < 0.8s | — |
| Fault detection latency (IMU bias) | < 2s | — |
| EKF vs UKF position error (Monte Carlo, N=500) | — | — |
| C++ EKF speedup vs Python | — | — |

---

## Algorithm Architecture

```
┌─────────────────────────────────────────────────┐
│              Simulation Environment              │
│  Quadrotor 6-DOF Plant + Sensor Models (MATLAB) │
└────────────┬──────────────────────┬─────────────┘
             │ IMU + GPS + Camera   │ Actuator commands
             ▼                      │
┌────────────────────┐              │
│  Navigation Layer  │              │
│  EKF (IMU + GPS)   │              │
│  Mono VO (camera)  │              │
│  Mode Manager      │              │
└────────┬───────────┘              │
         │ State estimates          │
         ▼                          │
┌────────────────────┐              │
│   Control Layer    │──────────────┘
│  Geometric SO(3)   │
│  LQR baseline      │
└────────────────────┘
         │ Raw sensor stream
         ▼
┌────────────────────┐
│  Fault Detection   │
│  TCN classifier    │
│  → Control switch  │
└────────────────────┘
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- CMake 3.20+
- MATLAB R2023b+ with Simulink, Aerospace Blockset, UAV Toolbox
- PyTorch 2.x
- C++17 compatible compiler (GCC 11+ or Clang 14+)

### Python Environment

```bash
git clone https://github.com/ZhangChi0727/uav-fms-portfolio.git
cd uav-fms-portfolio
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### C++ Build

```bash
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)
```

### Run Tests

```bash
# Python tests
pytest --tb=short -v

# C++ tests (after build)
cd build && ctest --output-on-failure
```

---

## Development Phases

| Phase | Description | Status |
|---|---|---|
| 0 | Repository setup, CI, environment | ✅ Complete |
| 1+2 | Requirements and architecture | 🔲 Planned |
| 3A | EKF Python implementation | 🔲 Planned |
| 4A | Plant model + scenario generator | 🔲 Planned |
| 3B | Geometric control | 🔲 Planned |
| 3C | TCN fault detection | 🔲 Planned |
| 3D | C++ EKF + pybind11 | 🔲 Planned |
| 4B–E | Integration, fault scenarios, Monte Carlo | 🔲 Planned |
| 5 | Safety analysis | 🔲 Planned |
| 7 | V&V report and portfolio polish | 🔲 Planned |

---

## Author

**Chi Zhang (张驰)**
Master of Engineering, Aviation System Engineering
Shanghai Jiao Tong University

- GitHub: [@ZhangChi0727](https://github.com/ZhangChi0727)

---

## License

MIT License — see [LICENSE](LICENSE) for details.
