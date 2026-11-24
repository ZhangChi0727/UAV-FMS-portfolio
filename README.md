# UAV FMS Portfolio

Two independent tracks are maintained:

- B0: historical component-level dynamics, estimator and C++17 controller evidence.
  Component acceptance is not whole-system or flight acceptance. Historical
  closed-loop material is retained in tag pre-surgery-2026-11-22.
- EDGE (Planned / Ready for Day-1 implementation): proposed civil bridge-defect detection, model compression and
  development-host profiling, traced to EDG-REQ-0034-0041. This is a scaffold,
  not a validated model or embedded-device performance claim. See
  [EDGE README](edge_inference/README.md).

Systems-engineering source is [requirements](requirements/README.md).
Maintain NED/body conventions, SI units and scalar-first Hamilton quaternions;
truth is excluded from controller and estimator inputs except initialization.

Run pytest within each B0 track directory. Build and test the C++ controller
using its CMake presets. Export requirements using
`strictdoc export requirements --output-dir build/strictdoc-check`.
Report actual host, commands and raw results for measurements.
