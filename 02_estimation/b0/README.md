# B0 G2-A attitude estimator

This track contains the deterministic six-axis attitude estimator for B0. It is
separate from the legacy navigation EKF under `02_estimation/python`.

The estimator consumes only an explicit reset state and timestamped IMU samples.
It propagates scalar-first Hamilton `q_nb` from the gyro and conditionally
corrects observable tilt from accelerometer direction. Absolute yaw is not
observable, accelerometer norm gating cannot identify every lateral acceleration,
and a gap-recovery estimate uses the newest gyro as a constant approximation
over the missing interval. Diagnostics make those conditions visible.

From this directory in the B0 virtual environment:

```text
python -m ruff check .
python -m pytest -q tests
python evidence.py --output <temporary-directory>/g2a_estimator_evidence.json
```

Configuration is split deliberately: G0 values are loaded from the approved G0
v2 JSON and verified by canonical committed-byte digest plus the authoritative
validator; G2-only choices are in `configs/b0_g2_estimator.v1.json`. The separate
approval overlay records the original-PA design decision. No generated evidence
file belongs in Git.
