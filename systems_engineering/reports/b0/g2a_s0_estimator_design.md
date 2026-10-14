# G2-A S0 attitude-estimator design candidate

Status: **candidate pending original-PA DESIGN_ACCEPT**  
Date: 2026-10-14 (Australia/Perth)  
Base: `main@731f1adde0676733474e2038734cc4e2cc70c67b`  
Execution issue: #5

## Decision boundary

This record proposes bounded G2 implementation choices; it does not change or
reinterpret frozen G0, requirements, model or verification specifications. The
approved G0 v2 JSON remains the authority for messages, timing, reset, frames,
units and quaternion policy. Its blob is
`1beff6e6a9a81d0ab92b2059a93207ffed9d291d` and its file SHA-256 is
`cf3ba49791a316e5c5f99b3eb0989633659327b544c95a89a0162828cc72c86a`.

G0 deliberately does **not** prescribe a complementary correction gain, an
accelerometer-norm gate width, or a maximum correction step. The candidate
values live only in
`02_estimation/b0/configs/b0_g2_estimator.v1.json`. They are not G0-approved
values, performance tuning, or literature-derived flight limits.

## Interface and state ownership

The implementation will expose:

```text
reset(EstimatorInitialState, reset_epoch_s, rng_seed) -> StateEstimate
step(IMUSample) -> StateEstimate
```

Owned state is the canonical unit `q_nb`, the last accepted angular-rate
estimate, reset epoch, last accepted sample timestamp and accepted/rejected
diagnostic counters. `rng_seed` is retained for replay-interface consistency;
the deterministic estimator performs no random draws. Reset accepts an explicit
estimator initial quaternion/rate only. Plant truth, `PlantState`, `SensorTruth`,
scenario attitude offsets and true sensor bias are absent from the runtime API.

The reset return is timestamped at the reset boundary and uses the explicit
initial state. The first accepted sample must be exactly one configured IMU
period after that boundary. Later samples must be exactly one configured period
after the last accepted sample within the existing G0 numerical comparison
tolerance. A rejected call changes no quaternion, rate, timestamp, cache or
counter except a separately returned immutable rejection diagnostic; production
state remains atomic.

## Numerical update

For accepted sample time `t_k`, `dt = t_k - t_previous` (or reset boundary on
the first step). With body angular rate `omega_m_b`, propagate body-to-NED
attitude using the scalar-first Hamilton convention:

```text
q_pred = normalize(q_previous ⊗ ExpQuaternion(omega_m_b * dt))
```

The exponential uses stable small-angle sinc evaluation and the zero-rate
identity. Quaternion sign is canonicalized only after normalization using the
G0 scalar-nonnegative/first-nonzero-vector-positive policy. This representation
choice never changes physical attitude.

For a valid accelerometer vector `f_m_b`, form

```text
f_pred_b = R_bn(q_pred) * [0, 0, -1]
innovation_b = cross(normalize(f_m_b), f_pred_b)
```

The sign makes a positive estimated roll error under stationary gravity produce
a negative roll correction. Correction is eligible only when
`abs(norm(f_m_b) - norm(g_n)) <= 1.4709975 m/s^2` (15% of standard gravity).
When eligible:

```text
delta_theta = correction_gain_per_s * dt * innovation_b
delta_theta = magnitude_clamp(delta_theta, 0.01 rad)
q_next = canonicalize(normalize(q_pred ⊗ ExpQuaternion(delta_theta)))
```

The proposed gain is `1.0 s^-1`; at the G0 0.005 s IMU period the small-error
correction fraction is approximately 0.005 per sample. The 0.01 rad step cap
bounds a single accepted correction independently of vector direction. These
are conservative component-design choices intended to make sign, gating and
atomicity independently testable before G3 tuning; they assert no closed-loop
settling or flight envelope.

If the accelerometer is outside the norm gate, gyro propagation still occurs
and the diagnostic reports `correction_applied=false` with a gate reason. A
zero vector is necessarily outside the gate. A nonfinite/wrong-shape vector or
`valid=false` rejects the whole sample before propagation. The rate output is a
copy of the current accepted gyro measurement; G2-A does not estimate bias.

## Limits and alternatives considered

- Norm-only gating cannot distinguish stationary gravity from some lateral
  accelerations whose total magnitude remains near `g`. The design reports the
  gate decision but does not claim contamination detection in all directions.
- Absolute yaw is unobservable. Gravity correction changes only observable
  tilt; no truth or artificial yaw reference is introduced.
- A direct vector blend was rejected because it obscures quaternion frame/sign
  semantics and makes a maximum angular correction less explicit.
- An always-on correction was rejected because G0 requires contaminated samples
  to be gated, but G0 does not supply the gate width.
- A gain scheduled from scenario labels was rejected because it would leak
  scenario/truth knowledge into the estimator.

Changing the G0 timing, message fields, operating envelope, acceptance criteria
or frozen verification decision rules is outside this S0. If PA determines the
candidate choices do so, implementation stops for a user-controlled normative
change request.

## Planned implementation boundary

After DESIGN_ACCEPT, G2-A may add `estimator.py`, immutable messages/adapters,
tests, a deterministic evidence generator, CI and traceability records under
`02_estimation/b0/`. It may import or explicitly adapt G1 `IMUSample` without
making G1 depend on G2. It must not add a G3 scheduler, controller, complete
scenario performance claim, or satisfaction verdict.

The detailed pre-implementation oracles are in
`g2a_s0_estimator_verification_matrix.md`. Design approval must identify the
exact commit containing both this record and the candidate configuration.
