# UAV Flight Control & Navigation Development and Verification Platform

A modular experimental platform for flight-control development, state estimation,
embedded implementation, and reproducible verification.

**Current status:** planning baseline B0 v0.2 is active. G0 contracts and the
G1.5-B joint requirements/model baseline are approved; G1 plant/actuator/IMU
component acceptance is complete. G1.5-C verification traceability/reporting is
the planned next governance increment; the combined work is still in K closeout
rework and the original PA has not released C implementation. G2/G3/G4 and
overall B0 completion remain open.
No completed flight, hardware, broad performance, or research results are claimed.

## Start here

- [Systems-engineering entry](systems_engineering/README.md): models, requirements status, development and verification route.
- [Project charter](systems_engineering/project_charter.md): purpose, scope, and completion rules.
- [B0 development baseline](systems_engineering/development_baseline.md): first deliverable.
- [Architecture and model views](systems_engineering/models/architecture.md): interfaces and numerical conventions.
- [Roadmap and backlog](docs/roadmap.md): dependency-ordered work and extensions.
- [Research packages](research/README.md): independent questions and publication gates.
- [Verification plan](systems_engineering/verification/verification_plan.md) and [results](RESULTS.md).
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
| systems_engineering/ | Models, requirements status, verification and reports | G1.5-B frozen; K closeout rework; C not released |
| docs/ | Roadmap, environment and work orders | Combined closeout/C work remains at the closeout gate |
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
See [management rules](docs/roadmap.md#work-management).

MIT license. Maintainer: Chi Zhang.
