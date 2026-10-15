# B0 deterministic integration track

This track owns the approved G0 contract and the G3 execution adapters. G3-A
currently provides integer scheduling, fail-closed event adapters and a small
real-component development loop. It does not yet provide the G3-B independent
metric evaluator or eight-scenario acceptance suite.

Run track tests from this directory:

```sh
python -m pytest -q tests
python -m ruff check .
```

The fixed tuning-only interface check loads one real controller build and runs
12 base ticks through the accepted plant, actuator, IMU, estimator and
controller components:

```sh
python runner.py --g3-bind-smoke \
  --module-dir <absolute-controller-module-directory> \
  --build-type Debug --output <temporary-json>
```

The Debug and Release outputs are compared with
`binding_checks/compare_g3_bind_smoke.py`. CI executes each loop against its own
module and retains the temporary JSON with the controller job artifacts. This
is a development interface check, not a ninth scenario or performance result.

The first frozen saturation diagnostic is intentionally separate because it
irreversibly exposes acceptance seed `2026100906`. It requires committed G3
execution sources, an unused run ID and an ignored or temporary output root:

```sh
python runner.py --reachability-diagnostic \
  --module-dir <absolute-controller-module-directory> \
  --build-type Debug --output-root <ignored-or-temporary-root> \
  --run-id <unique-run-id>
```

Before component execution, the command exclusively creates a seed-exposure
start record. It then writes the diagnostic result and a separate final record
that binds the start-record hash to the result hash. Existing run directories
are never overwritten. A structurally complete shortfall remains a real
shortfall; the runner does not change the frozen command, limits or threshold.

Generated traces and exposure records remain outside tracked source. They are
inputs to later G3 evidence work, not repository documentation by themselves.
