# Trace-driven edge-cloud offloading simulator design specification

## 1. Purpose and interpretation

This document specifies the interface and analytical model implemented in
[`src/offload_sim.py`](../src/offload_sim.py). The [Day 3–4 replay log](../logs/2026-11-24_day3_4_offloading_simulation_and_traceability.md)
records the results obtained from cached CODEBRIM traces. This specification
is not an additional requirements, verification or status authority:
`requirements/*.sdoc` remains the sole systems-engineering source.

All system latency and energy parameters are used in a **parametric analytical
model for trace-driven simulation**, not as hardware, UAV battery, network or
flight measurements. Real benchmark samples, when available, must retain their
`development-host` identity. A four-thread CPU profile is a constrained desktop
reference, not measured onboard hardware; an RTX 4060 profile is a local GPU
reference, not measured remote-cloud service latency. Synthetic dummy timings
from `benchmark.py` are plumbing checks, not detector latency evidence.

The model treats each frame independently and sequentially within a policy.
It excludes contention, queuing, overlapping computation/transmission, packet
loss, retries, outages, control dynamics and deadlines. No closed-loop,
real-time schedulability or flight-safety claim follows from this simulation.

## 2. Input data contract

Let frames be indexed by \(i\in\{1,\ldots,N\}\), with \(N>0\). All inputs use
stable frame IDs; array position alone must not establish correspondence.

| Input | Meaning and constraints |
| --- | --- |
| `frame_id` | Unique identifier shared by payload, prediction and label records |
| `payload_bytes` \(S_i\) | Positive integer Bytes of the encoded full-frame payload actually proposed for transmission; \(8S_i\) bits, not inferred from tensor dimensions |
| `edge_profile` | Compressed-model CPU trace, ORT `intra_op_num_threads=4`, `inter_op_num_threads=1`; host type `development-host` |
| `cloud_profile` | Higher-accuracy candidate GPU model trace on RTX 4060; host type `development-host`; accuracy superiority is to be evaluated, not assumed |
| `timings_ms` | Finite nonnegative `preprocess`, `inference`, `postprocess`, `total` samples, excluding warmup; retain each sample and its association |
| \(\mathcal D_{\mathrm{edge},i}\), \(\mathcal D_{\mathrm{cloud},i}\) | Per-frame detection lists \(\{(b_k,c_k,p_k)\}\); either list may be empty |
| \(\mathcal G_i\) | Ground-truth annotations, label coverage/ignore metadata and provenance, available only to the offline evaluator |

Boxes \(b_k=(x_1,y_1,x_2,y_2)\) use original-image pixel coordinates, top-left
origin, \(0\le x_1<x_2\le W_i\), \(0\le y_1<y_2\le H_i\). Class IDs
\(c_k\) resolve through one explicit common class map; confidence
\(p_k\in[0,1]\) is a model score, not a guaranteed calibrated probability.
Store source dimensions, coordinate convention, model/weights/config hashes,
precision, backend, provider, host, thread settings, benchmark command, warmup
and sample counts, dataset/split identity and trace file hashes.

Define \(T_{\mathrm{edge},i}\) and \(T_{\mathrm{cloud},i}\) in ms from retained
end-to-end `total` samples, not from the sum of stage percentiles. Stage samples
are diagnostic; measured `total` can include overhead beyond their sum.
Prefer frame-associated measurements. If empirical distributions are replayed
instead, freeze a seed and sample-index mapping shared across policies/sweeps,
record that this is sampled replay, and do not claim frame-specific timing or
an unmeasured correlation between confidence and latency.

Current benchmark timing JSON alone does not contain per-frame payloads,
predictions or ground truth; those future trace products must be joined and
checked explicitly. Missing IDs, duplicate IDs, incompatible class/box formats,
nonfinite values and missing timings are errors, not zero-cost observations.
Missing annotations are not automatically reliable negative labels.

## 3. Policies and decision visibility

The decision \(u_i(\tau)\in\{0,1\}\) selects local acceptance (0) or offloading
(1). Runtime policy code must not receive ground truth, cloud predictions or
future timing outcomes. Ground truth is used only after decisions are fixed.

The replay gives an `OffloadingPolicy` only an immutable `FrameContext`:
frame ID, retained local detections (pixel xyxy), full payload bytes, and
elapsed local latency in ms. Optional `ObservedFrameTrace` supplies a current
`aoi_ms` or `uq_radius`; absent observations are None, never inferred from
cloud results. A direct All-Cloud request has no local detections or elapsed
edge compute. CGAO returns all triggering boxes in input order in its
`OffloadDecision`; these describe candidates, not actual encoded crops.

- **All-Edge:** \(u_i=0\) for every frame; run the edge detector only.
- **All-Cloud:** \(u_i=1\) for every frame; skip edge inference and transmit the
  full frame directly.
- **Confidence-Gated Adaptive Offloading (CGAO):** run the compressed edge
  detector first, then apply

\[
u_i(\tau)=\mathbf 1\!\left[\exists(b_k,c_k,p_k)\in
\mathcal D_{\mathrm{edge},i}:\tau_{\mathrm{low}}\le p_k<\tau\right].
\]

Default \(\tau_{\mathrm{low}}=0.15\), allowed \(\tau\in[0.25,0.95]\).
The lower boundary is inclusive; the upper boundary is exclusive. An empty
detection set, or scores all outside this band, causes local acceptance. In
particular, a missed defect with no detection does not trigger offloading;
this is a limitation, not a guarantee that the frame is easy or safe.

Gate traces must preserve detections down to at least 0.15 after a declared,
fixed NMS procedure. A detector filtered at 0.25 cannot supply the specified
gate without losing scores in [0.15, 0.25). Keep gate-score retention separate
from the evaluator's reporting operating point; do not tune either on test data.

Optional ROI factor \(\alpha_{\mathrm{roi}}\in(0,1]\), default 1.0, scales
the CGAO transmitted payload in the analytical model. Define modeled bytes

\[
Q_i^{\mathrm{edge}}=0,\qquad Q_i^{\mathrm{cloud}}=S_i,\qquad
Q_i^{\mathrm{CGAO}}=u_i(\tau)\alpha_{\mathrm{roi}}S_i.
\]

At the default, all offloaded frames are full frames. For a non-unit factor,
fractional modeled bytes are permitted but must be distinguished from actual
encoded payload sizes. Holding full-frame cloud predictions/timings unchanged
while reducing bytes is only an optimistic communication sensitivity analysis,
not an implemented ROI system. Accuracy claims about ROI require matching
crop/encoding, coordinate restoration, predictions and timing traces; they
cannot reuse full-frame accuracy as evidence of ROI accuracy.

## 4. End-to-end latency model

Bandwidth \(B>0\) is in decimal Mbps (\(10^6\) bits/s). The full-frame uplink
time and base round-trip overhead are

\[
T_{\mathrm{tx},i}(B)=\frac{8S_i}{1000B}\quad[\mathrm{ms}],\qquad
T_{\mathrm{rtt}}\ge0\quad[\mathrm{ms}].
\]

\(T_{\mathrm{rtt}}\) excludes the modeled image uplink serialization time and
cloud inference; otherwise those terms would be counted twice. Return payload
serialization is neglected and must be declared as such. With
\(\alpha_{\mathrm{roi}}=1\), per-frame latency is exactly

\[
T_i^{\mathrm{edge}}=T_{\mathrm{edge},i},
\]
\[
T_i^{\mathrm{cloud}}=T_{\mathrm{tx},i}(B)+T_{\mathrm{rtt}}+
T_{\mathrm{cloud},i},
\]
\[
T_i^{\mathrm{CGAO}}=T_{\mathrm{edge},i}+u_i(\tau)
\left(T_{\mathrm{tx},i}(B)+T_{\mathrm{rtt}}+T_{\mathrm{cloud},i}\right).
\]

For optional ROI sensitivity, replace only CGAO's transmission term by
\(\alpha_{\mathrm{roi}}T_{\mathrm{tx},i}(B)\). All-Cloud remains the full-frame
reference. In particular, CGAO pays edge compute even for offloaded frames;
All-Cloud does not. No policy uses a negative or free transmission time.

For each policy/grid point report
\(\bar T_{\mathrm{e2e}}=N^{-1}\sum_iT_i\), P95 and P99 of the per-frame
\(T_i\) array. Use the same declared linear-interpolation percentile convention
as `numpy.percentile(..., method="linear")`; never add marginal percentiles.
Retain individual samples, units and counts alongside summaries.

## 5. Parametric onboard energy model

Use dynamic compute power \(P_{\mathrm{comp}}\ge0\) and uplink transmit power
\(P_{\mathrm{tx}}\ge0\), both in W. Illustrative reference values are 10 W
and 3 W respectively. They are analytical parameters, **not physical
current-sensor measurements** or device-specific power estimates validated by
this work. Since \(1\,\mathrm W\cdot1\,\mathrm{ms}=1\,\mathrm{mJ}\),

\[
E_i^{\mathrm{edge}}=P_{\mathrm{comp}}T_{\mathrm{edge},i},
\]
\[
E_i^{\mathrm{cloud}}=P_{\mathrm{tx}}T_{\mathrm{tx},i}(B),
\]
\[
E_i^{\mathrm{CGAO}}=P_{\mathrm{comp}}T_{\mathrm{edge},i}
+u_i(\tau)P_{\mathrm{tx}}T_{\mathrm{tx},i}(B).
\]

All energies above are in mJ. With optional ROI sensitivity, multiply only
CGAO's transmission term by \(\alpha_{\mathrm{roi}}\). Report
\(\bar E=N^{-1}\sum_iE_i\). Cloud wall-power is outside this modeled onboard
battery budget. Camera, encoding, baseline/idle power, RX/wait power during RTT
and cloud execution, propulsion and other avionics are excluded. Consequently
this is a partial dynamic-energy estimate, not total battery use or endurance.

## 6. Effective predictions, efficacy and sweep

For each policy, select a single result set rather than merging detections:

\[
\mathcal D_{\mathrm{sys},i}(\tau)=
\begin{cases}
\mathcal D_{\mathrm{cloud},i},&u_i(\tau)=1,\\
\mathcal D_{\mathrm{edge},i},&u_i(\tau)=0.
\end{cases}
\]

Offload ratio and uplink-byte saving against full-frame All-Cloud are

\[
\rho=\frac1N\sum_i u_i,\qquad
\eta_{\mathrm{bw}}=1-\frac{\sum_iQ_i}{\sum_iS_i}.
\]

For default CGAO, this is \(1-\sum_i u_iS_i/\sum_iS_i\), not generally
\(1-\rho\) when payload sizes vary. It measures traffic-byte savings, not a
measured increase in link capacity. All-Edge has \((\rho,\eta_{\mathrm{bw}})
=(0,1)\); All-Cloud has \((1,0)\). Ratios are stored as fractions; percentage
displays must be labeled.

Evaluate the selected sets against \(\mathcal G_i\), reporting mAP@50,
mAP@50:95 (IoU 0.50 to 0.95 in steps of 0.05), and per-class Recall for `crack`,
`spallation`, `corrosion_stain`. Freeze the evaluator/version, class mapping,
matching/ignore rules, AP aggregation, score operating point and recall IoU
before test scoring, using only training/calibration data to select settings.
Report classes without valid reference support as unavailable, not zero or
perfect. Incomplete annotation coverage must qualify false-positive claims.
Cloud detections are predictions, not ground truth. Report \(\bar E\) and all
three latency aggregates with accuracy and traffic metrics.

Default analytical grid:

- \(B\in\{1.0,5.0,20.0\}\) Mbps;
- \(T_{\mathrm{rtt}}=20.0\) ms;
- \(\tau\in\{0.25,0.35,0.45,0.55,0.65,0.75,0.85\}\);
- \(\tau_{\mathrm{low}}=0.15\), \(\alpha_{\mathrm{roi}}=1.0\);
- illustrative \(P_{\mathrm{comp}}=10\) W, \(P_{\mathrm{tx}}=3\) W.

These are modeling settings, not acceptance thresholds or measured constants.
The grid comprises 21 CGAO points; baselines need no duplicate threshold runs.
With fixed predictions and decisions, varying B or RTT changes latency/energy,
not accuracy. No late-result discard or deadline-dependent efficacy is modeled.
Test-grid presentation is descriptive, not permission to choose a winning
threshold on test data and claim an independent evaluation.

## 7. Software interface and retained outputs

The replay accepts the legacy policy names or a strategy instance via
`SimulationConfig(policy=my_policy)`. Custom strategies run after edge
inference and transmit the full payload when selected. Only CGAO uses the
existing ROI byte-sensitivity factor. Custom strategy parameters and versions
belong in the experiment provenance; the result records the strategy class.

```python
OffloadingPolicy.decide(context: FrameContext) -> OffloadDecision
decide(edge_detections: Sequence[Detection], *, policy: Policy,
       tau_low: float, tau: float) -> bool
simulate(traces: TraceInputs, config: SimulationConfig) -> SimulationResult
evaluate(predictions: Mapping[FrameId, Sequence[Detection]],
         references: ReferenceInputs, config: EvaluationConfig) -> AccuracyResult
```

`Detection`, `TraceInputs` and `SimulationConfig` carry the fields and units
defined above. The simulator joins fixed trace records, applies policies and
calculates analytical outputs; it does not train models, fetch images, rerun
inference or expose evaluator references to `decide`. Reject invalid parameters
or trace joins with an explicit error identifying the field/frame. Unsupported
or missing accuracy annotations produce an explicit unavailable accuracy result,
not a fabricated score; latency-only runs must be labeled accordingly.

Retain one per-frame output row per policy/grid point: frame ID, policy,
parameters, decision, input and modeled transmitted bytes, timing sample IDs,
edge/cloud time, transmission/RTT terms, effective E2E latency, modeled mJ and
selected prediction source. The run header includes input hashes, configuration,
replay sampling/mapping, host-profile provenance and analytical assumptions.
Summaries retain N, offload count, total bytes, \(\rho\), \(\eta_{\mathrm{bw}}\),
latency mean/P95/P99, mean energy and evaluator outputs/limitations.

Runtime benchmark/simulation JSON remains ignored under `edge_inference/docs/`;
this Markdown design specification is tracked. Saving it does not authorize
implementation, training or a new measurement campaign.
