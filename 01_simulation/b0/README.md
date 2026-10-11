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
at its explicit sensor boundary and accepts samples only at the contract
period (`base_period_s * imu_every_ticks = 0.005 s`); no estimator or
controller consumes truth. `Plant.step` and `Actuator.step` are explicit
numerical/ZOH component oracles that accept a positive interval for analytic
checks. `step_base` on each component is the G0 scheduling adapter and rejects
intervals other than the configured 0.0025 s base period.
The G0 adapters derive timestamps from `reset_epoch + local_tick *
base_period_s`; they reject mixing an oracle substep with a scheduled tick
path. IMU samples use the same integer tick origin and are due every two base
ticks.
