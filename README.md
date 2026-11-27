# UAV FMS Portfolio

Two independent tracks are maintained:

- B0: historical component-level dynamics, estimator and C++17 controller evidence.
  Component acceptance is not whole-system or flight acceptance. Historical
  closed-loop material is retained in tag pre-surgery-2026-11-22.
- EDGE: the Day 1–4 pipeline trained a CODEBRIM detector, pruned and quantized it,
  profiled four variants on the development host, and replayed cached predictions.
  The [technical note](edge_inference/docs/technical_note_uav_edge_offloading.md)
  separates annotation-relative scores and measured host latency from modeled
  network latency and energy. See the [EDGE README](edge_inference/README.md)
  for the modules supporting EDG-REQ-0034-0041.

Systems-engineering source is [requirements](requirements/README.md).
The [compact requirements view](overview.html#requirements) can be opened offline.
Maintain NED/body conventions, SI units and scalar-first Hamilton quaternions;
truth is excluded from controller and estimator inputs except initialization.

Run pytest within each B0 track directory. Build and test the C++ controller
using its CMake presets. Export requirements using
`strictdoc export requirements --output-dir build/strictdoc-check`.
Report actual host, commands and raw results for measurements.

For Python access from outside the checkout, install the checkout-backed B0
namespace with `python -m pip install -e . --no-build-isolation --no-deps`
in an environment with NumPy. Import from `uav_b0.simulation`,
`uav_b0.estimation.estimator`, `uav_b0.control.controller`, or
`uav_b0.integration.validate_config`. The simulation alias retains the
original `b0.contract` message types. Per-track pytest also works without
installation; control tests require the matching native Python extension
from the Debug preset or an explicit `B0_CONTROLLER_MODULE_DIR`.
