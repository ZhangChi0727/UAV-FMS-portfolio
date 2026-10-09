# Claim ledger

## Portfolio mapping (2026-10-09)

These historical pilot claims are optional research candidates, not B0 obligations.
CLM-001/002 inform RP-EST; CLM-003 informs RP-BENCH and RP-VERIFY. See
[research packages](../research/README.md). Timing and evidence-transfer questions
require new searches before any novelty claim. Existing records and review dates
below are preserved; this mapping does not imply new literature evidence.

Use this ledger for candidate thesis claims, including claims of novelty, superiority,
generality, safety, and practical relevance. Empty evidence fields mean the claim is
not ready for use.

## Status vocabulary

- `proposed`: phrased but not yet tested against the literature
- `needs_search`: material evidence gap remains
- `supported`: scoped statement is supported by the recorded evidence
- `narrowed`: evidence supports only a more limited statement
- `rejected`: contradicted or not supportable

## Claim index

| Claim ID | Short label | Status | Owner | Last reviewed |
|---|---|---|---|---|
| CLM-001 | Integrated resilience architecture and evaluation | needs_search | Chi Zhang | 2026-07-28 |
| CLM-002 | Confidence-weighted, reversible measurement recovery | needs_search | Chi Zhang | 2026-07-28 |
| CLM-003 | Reproducible cross-layer resilience benchmark | needs_search | Chi Zhang | 2026-07-28 |

Claim IDs are literature-workflow identifiers, not system requirement identifiers.

## CLM-001 — Integrated resilience architecture and evaluation

- **Candidate wording:** A traceable UAV navigation-resilience architecture that links
  hybrid state estimation, temporal sensor-health inference, confidence-aware recovery,
  and closed-loop control evaluation can provide system-level evidence not obtained by
  evaluating these elements independently.
- **Scope and definitions:** Small fixed-wing or multirotor UAV navigation under
  injected GNSS, inertial, and air-data measurement degradations; "system-level" means
  detection, estimation, recovery, and control consequences are evaluated on aligned
  scenarios and timelines.
- **Why it matters:** Pilot results show relevant techniques in each layer, while their
  evidence is commonly reported using layer-local metrics.
- **Evidence that would support it:** A broad search finds no closely matching
  end-to-end architecture and benchmark; experiments show that layer-local gains lead
  to measurable closed-loop resilience gains.
- **Evidence that would falsify or narrow it:** Prior work already evaluates the same
  estimator–health-inference–recovery chain under comparable closed-loop scenarios, or
  project experiments show no additional system-level insight.
- **Supporting studies:** None yet; full-text extraction has not started.
- **Contradicting studies:** None yet.
- **Adjacent or competing approaches:** REC-0002, REC-0004, REC-0005, REC-0007,
  REC-0008, REC-0009, REC-0012.
- **Searches completed:** PILOT-20260728-01 through PILOT-20260728-06.
- **Known search gaps:** IEEE Xplore, Scopus/Web of Science, Compendex, backward and
  forward citation searches, and full-text comparison.
- **Limitations and prohibited overstatement:** Do not claim the component algorithms
  are novel; do not claim an exhaustive gap from pilot semantic searches.
- **Decision and rationale:** `needs_search` — plausible integration-level contribution,
  but several close architectures exist and require full-text comparison.

## CLM-002 — Confidence-weighted, reversible measurement recovery

- **Candidate wording:** Temporal sensor-health confidence can be used to continuously
  adapt estimator measurement trust and govern reversible recovery, potentially
  reducing transients compared with fixed thresholds or binary sensor exclusion.
- **Scope and definitions:** Learned or hybrid health confidence influences Kalman
  measurement covariance, gating, or sensor reinstatement; recovery includes explicit
  hysteresis or persistence logic.
- **Why it matters:** Abrupt rejection and premature reinstatement can create estimation
  and control transients even when fault classification is accurate.
- **Evidence that would support it:** Prior-art review establishes a narrower gap in
  confidence-to-covariance and recovery coupling; ablations outperform binary gating on
  detection delay, false alarms, state error, and recovery time.
- **Evidence that would falsify or narrow it:** Existing methods already implement and
  validate the same continuous confidence and recovery mechanism, or no measurable
  benefit appears under representative faults.
- **Supporting studies:** None yet; full-text extraction has not started.
- **Contradicting studies:** None yet.
- **Adjacent or competing approaches:** REC-0001, REC-0002, REC-0003, REC-0007,
  REC-0012.
- **Searches completed:** PILOT-20260728-01, PILOT-20260728-03, and
  PILOT-20260728-06.
- **Known search gaps:** Adaptive measurement-noise estimation, probabilistic gating,
  sensor reinstatement, health-aware filtering, and fault-recovery literature outside
  UAV-specific venues.
- **Limitations and prohibited overstatement:** Do not claim learning-assisted Kalman
  adaptation or residual-based isolation as new; both are established in the seed set.
- **Decision and rationale:** `needs_search` — potentially differentiable at the
  confidence/recovery interface, but terminology-sensitive prior art is likely.

## CLM-003 — Reproducible cross-layer resilience benchmark

- **Candidate wording:** A reproducible cross-layer benchmark that aligns navigation
  sensor degradations with estimator, detector, recovery, and control timelines and
  reports both diagnostic and closed-loop consequence metrics may complement existing
  UAV fault datasets.
- **Scope and definitions:** Versioned scenarios, deterministic seeds, machine-readable
  outputs, traceable requirements, and metrics spanning diagnosis and closed-loop
  consequence.
- **Why it matters:** Algorithm-level accuracy alone does not establish operational
  resilience or expose trade-offs between false alarms, estimation error, and control
  deviation.
- **Evidence that would support it:** Dataset and benchmark searches find no sufficiently
  comparable open evaluation package; the project demonstrates repeatable baselines and
  cross-layer trade-offs.
- **Evidence that would falsify or narrow it:** An established open benchmark already
  provides equivalent navigation-sensor scenarios, estimator and recovery interfaces,
  control consequences, artifacts, and cross-layer metrics.
- **Supporting studies:** None yet; benchmark literature has not been systematically
  searched.
- **Contradicting studies:** None yet.
- **Adjacent or competing approaches:** REC-0004, REC-0005, REC-0007, REC-0008,
  REC-0010 (ALFA), REC-0011 (RflyMAD).
- **Searches completed:** PILOT-20260728-01 through PILOT-20260728-06.
- **Known search gaps:** Navigation-sensor-specific fault datasets, estimator recovery
  benchmarks, open-source FTC testbeds, and benchmark adoption/reproducibility studies.
- **Limitations and prohibited overstatement:** Do not claim the first UAV fault
  benchmark. ALFA and RflyMAD are substantial open benchmarks with real-flight data.
  A new benchmark is a contribution only if its cross-layer scope is clearly distinct,
  reusable, documented, and empirically informative.
- **Decision and rationale:** `needs_search` — generic benchmark novelty is contradicted
  by ALFA and RflyMAD; a narrower navigation-to-control benchmark contribution remains
  plausible and requires full-text comparison.
