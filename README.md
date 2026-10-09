# UAV Flight Control & Navigation Development and Verification Platform

A modular experimental platform for flight-control development, state estimation,
embedded implementation, and reproducible verification.

**Current status:** planning baseline B0 v0.2 adopted; implementation remains
scaffold code. No completed flight, hardware, performance, or research results
are claimed. The repository name is retained for URL compatibility.

## Start here

- [Project charter](07_docs/project_charter.md): purpose, scope, and completion rules.
- [B0 development baseline](07_docs/development_baseline.md): first deliverable.
- [Architecture](07_docs/architecture.md): interfaces and numerical conventions.
- [Roadmap and backlog](07_docs/roadmap.md): dependency-ordered work and extensions.
- [Research packages](research/README.md): independent questions and publication gates.
- [Verification plan](07_docs/verification/verification_plan.md) and [results](RESULTS.md).
- [Literature record](literature/README.md): discovery, screening, and claim evidence.

## First baseline: attitude closed loop

B0 implements a bounded multirotor attitude experiment: rotational dynamics,
gyroscope/accelerometer observations, basic quaternion attitude fusion, cascaded
attitude/rate control, actuator saturation, and automated evaluation. C++17 is
the planned control-core language; Python provides simulation and analysis.

B0 does not require position flight, INS/GNSS, PX4, STM32, HIL, learning algorithms,
or a publication. Each is independently scoped in the extension registry.

## Repository map

| Directory | Responsibility | Current implementation |
|---|---|---|
| 01_simulation/ | Plant, sensors, actuators, environment | Legacy generator scaffold |
| 02_estimation/ | Attitude estimation; optional navigation | Legacy EKF/UKF scaffold |
| 03_control/ | B0 cascaded control; optional advanced control | Legacy geometric/LQR scaffold |
| 04_fault_detection/ | Optional health and recovery | Legacy TCN scaffold |
| 05_integration/ | Execution adapters, scenarios, evidence integration | Legacy integration scaffold |
| 06_safety/ | Failure analysis and limitations | Preliminary analysis |
| 07_docs/ | Governing engineering and management documents | B0 v0.2 planning baseline |
| research/ | Independently gated research packages | Candidates only |
| literature/ | Shared bibliographic and evidence record | Historical pilot screening |

Existing code paths are preserved to avoid breaking imports and build references.
Module ownership, rather than chronological phase numbers, governs new work.

## Development checks

Python 3.11+ is used by the existing navigation contract suite:

```sh
python -m pip install numpy==1.26.4 pytest==8.2.0
cd 02_estimation/python
python -m pytest -v
```

Run pytest inside each track; root collection is not supported. Expected failures
in navigation contracts describe pending extension behavior, not B0 completion.
The existing root CMake build targets the optional navigation EKF scaffold; it
does not yet build a B0 controller. Its prerequisites include Eigen3 and Catch2.
MATLAB, PyTorch, PX4, and hardware tools are extension-specific dependencies.

No B0 run command exists yet. Add it with the implementation and retain a
small reproducible scenario suite before declaring B0 complete.

## Contribution policy

Use one coherent issue and pull request per increment. Record assumptions,
acceptance checks, validation commands, and evidence. Numerical results must
link retained artifacts; pending behavior and limitations must remain visible.
See [management rules](07_docs/roadmap.md#work-management).

MIT license. Maintainer: Chi Zhang.
