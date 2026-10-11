# B0 G1 component track

This track implements only the contract-owned rotational plant, bounded
first-order actuator boundary, and IMU boundary. It is not a controller,
estimator, closed-loop, real-time, HIL, or flight result.

Run the track from this directory so Python test collection stays scoped:

```sh
/home/chi/src/uav-fms-portfolio/.venv-b0/bin/python -m pytest -q tests
/home/chi/src/uav-fms-portfolio/.venv-b0/bin/python -m ruff check .
/home/chi/src/uav-fms-portfolio/.venv-b0/bin/python evidence.py
```

The parameter loader reads the approved
`05_integration/b0/configs/b0_g0_contract.v2.json`. The IMU accepts truth only
at its explicit sensor boundary; no estimator or controller consumes truth.
