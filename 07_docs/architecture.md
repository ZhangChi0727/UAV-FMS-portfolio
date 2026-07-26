# System Architecture

## Status

Baseline v0.1 freezes the navigation conventions and interfaces required for the
first Python navigation vertical slice. Control, fault-detection, visual-odometry,
and deployment details remain planned.

## Component Overview

```text
Truth trajectory
    -> IMU model -------> Python error-state EKF -----> state estimate
    -> GPS model -------^
```

The deterministic Python fixture is the initial source of truth and sensor data.
MATLAB/Simulink may replace or supplement it later without changing the
interfaces below.

## Coordinate and Unit Conventions

- Navigation frame: right-handed North-East-Down (NED).
- Body frame: right-handed, x forward, y right, z down.
- Position and distance: metres.
- Velocity: metres per second.
- Acceleration and specific force: metres per second squared.
- Angular rate: radians per second.
- Time and sample period: seconds.
- Timestamp origin: scenario start, with strictly increasing timestamps per stream.
- Floating-point representation: NumPy `float64` in the Python baseline.
- Gravity in NED: `g_n = [0, 0, 9.80665]` metres per second squared.

### Quaternion convention

- Ordering: scalar first, `q = [w, x, y, z]`.
- Meaning: `q_nb` rotates a body-frame vector into the NED frame.
- Multiplication: Hamilton product.
- Rotation matrix: `v_n = R_nb(q_nb) @ v_b`.
- The nominal quaternion shall be normalized after propagation and correction.
- Quaternion sign is not physically observable; comparisons shall account for
  `q` and `-q` representing the same attitude.

## IMU Measurement Convention

The accelerometer reports body-frame specific force:

```text
f_m_b = R_bn @ (a_n - g_n) + b_a + n_a
```

The gyroscope reports body-frame angular rate:

```text
omega_m_b = omega_ib_b + b_g + n_g
```

Bias and noise configuration shall use SI units and be supplied explicitly by
the scenario or filter configuration.

For an aligned, stationary, zero-bias vehicle, the ideal accelerometer
measurement is `[0, 0, -9.80665]` and the ideal gyro measurement is zero.

## EKF State Definition

### Nominal state

The nominal state has 16 elements:

| Slice | Quantity | Frame / convention |
|---|---|---|
| `[0:3]` | position `p_n` | NED |
| `[3:6]` | velocity `v_n` | NED |
| `[6:10]` | quaternion `q_nb` | scalar first |
| `[10:13]` | accelerometer bias `b_a` | body |
| `[13:16]` | gyroscope bias `b_g` | body |

The initial nominal quaternion is `[1, 0, 0, 0]`.

### Local error state

The local error state has 15 elements:

| Slice | Quantity |
|---|---|
| `[0:3]` | position error |
| `[3:6]` | velocity error |
| `[6:9]` | local attitude error |
| `[9:12]` | accelerometer bias error |
| `[12:15]` | gyroscope bias error |

The covariance `P` is therefore 15 by 15. Attitude corrections are injected
multiplicatively into the nominal quaternion, after which the local attitude
error is reset.

The local attitude error is right-multiplicative:

```text
q_true = q_nominal (x) delta_q
delta_q approximately [1, 0.5 * delta_theta]
```

Correction injects the estimated `delta_q` on the right of the nominal
quaternion before normalization. The local error definition and its reset
Jacobian shall be used consistently in propagation and correction.

## Filter Numerical Contract

- `dt` shall be finite and strictly positive.
- Public inputs shall have documented shapes and finite values.
- Covariance matrices shall remain symmetric within numerical tolerance.
- Covariance propagation shall use the approved local error dynamics.
- GPS correction shall use a numerically stable solve rather than an explicit
  matrix inverse.
- Measurement covariance shall be updated in Joseph form.
- Innovation and innovation covariance shall be available for verification.
- Invalid inputs shall raise a clear exception rather than silently modifying state.

## Interface Definitions

| Interface | Producer | Consumer | Data | Rate |
|---|---|---|---|---|
| Truth sample | Scenario fixture | Sensor models, analysis | timestamp, position, velocity, quaternion, acceleration, angular rate | 100 Hz baseline |
| IMU sample | IMU model | EKF, later TCN | timestamp, specific force (3), angular rate (3), validity | 100 Hz |
| GPS fix | GPS model | EKF | timestamp, position (3), velocity (3), validity | 10 Hz |
| Camera frame | Sensor model | Later VO module | 640 by 480 RGB | 30 Hz |
| State estimate | EKF | Controller, later TCN, analysis | timestamp, nominal state (16), covariance (15 by 15) | 100 Hz |
| Control command | Controller | Plant model | thrust, torques (3) | 100 Hz |
| Fault flag | TCN | Mode manager | class, confidence, timestamp | 10 Hz |

## Deterministic Fixture Contract

The first fixture shall support stationary, constant-velocity,
constant-acceleration, constant-yaw-rate, and GPS-outage cases.

- Stochastic cases require an explicit seed.
- Identical configuration and seed shall produce identical samples.
- Sampling times shall be derived from integer sample indices to avoid drift.
- GPS outage samples shall be represented by an invalid measurement flag and
  shall not be passed to the EKF correction function.
- Fixture configuration is test input, not a system requirement.

## Deferred Architecture

Visual-odometry measurement semantics, navigation mode management, persistent
HDF5 schema, plant/controller interfaces beyond the table above, and deployment
boundaries will be baselined with their implementation increments.
