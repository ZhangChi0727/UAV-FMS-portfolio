# Algorithm Performance Requirements

## Status

Baseline v0.1 defines the development and verification interpretation of the
existing requirements. Thresholds are unchanged. A requirement is not
compliance-ready until its operating conditions and evidence procedure below
are approved.

## Navigation Requirements

| ID | Description | Threshold | Verification |
|---|---|---|---|
| NAV-REQ-001 | Position error during 30 s GPS outage (95th percentile) | < 5 m | Test + Analysis |
| NAV-REQ-002 | EKF update cycle time | < 10 ms | Analysis |

### NAV-REQ-001 verification conditions

Before compliance testing, the scenario configuration shall identify:

- the navigation and body conventions from `architecture.md`;
- whether visual odometry or another aiding source remains available;
- the position, velocity, attitude, and bias initialization errors;
- the vehicle trajectory and maneuver envelope during the outage;
- the IMU noise, bias, and sampling configuration;
- the GPS behavior immediately before and after the outage;
- whether position error is horizontal, vertical, or three-dimensional;
- whether the threshold applies at outage end or throughout the outage;
- the trial count, seed set, and percentile calculation; and
- the retained raw artifact and summary used for pass/fail.

Until these values are approved, deterministic GPS-outage tests are development
evidence only and shall not be reported as compliance with `NAV-REQ-001`.

### NAV-REQ-002 verification conditions

The benchmark record shall identify:

- whether a cycle is predict-only or predict plus GPS correction;
- target hardware, operating system, Python, NumPy, and build configuration;
- input dimensions and enabled diagnostics;
- warm-up and measured iteration counts;
- timing source and aggregation statistic;
- treatment of logging, allocation, and file I/O; and
- the retained raw timing artifact and summary used for pass/fail.

The benchmark configuration shall be version controlled. A result from an
unrecorded developer environment is informative only.

## Control Requirements

| ID | Description | Threshold | Verification |
|---|---|---|---|
| CTL-REQ-001 | Attitude settling time - 10 degree step input | < 0.8 s | Test |
| CTL-REQ-002 | Attitude overshoot | < 15% | Test |
| CTL-REQ-003 | Cross-track error at cruise | < 1.2 m | Test |

Control operating conditions, plant parameters, command definition, and metric
calculation shall be frozen before Phase 3B compliance evidence is generated.

## Fault Detection Requirements

| ID | Description | Threshold | Verification |
|---|---|---|---|
| FDI-REQ-001 | IMU bias fault detection latency | < 2 s | Test |
| FDI-REQ-002 | False alarm rate (clean data, 100 s) | < 1% | Test + Analysis |
| FDI-REQ-003 | GPS spoof detection latency | < 3 s | Test |

Fault magnitude, onset definition, dataset split, detection threshold, latency
calculation, and random-seed policy shall be frozen before Phase 3C compliance
evidence is generated.

## Traceability Rule

Every compliance statement shall link:

```text
requirement
    -> approved operating conditions
    -> version-controlled test or analysis
    -> retained raw artifact
    -> summarized result
    -> pass/fail statement
```

Unit tests support correctness but do not alone demonstrate system-level
performance compliance.
