# Technical Note: Compression-Aware Adaptive Edge–Cloud Offloading for UAV Structural Defect Inspection

**Author:** Chi Zhang
**Repository:** [UAV-FMS-Portfolio (`edge_inference/`)](https://github.com/ZhangChi0727/UAV-FMS-portfolio)
**Date:** November 2026

---

## Abstract

Unmanned Aerial Vehicles (UAVs) performing close-range bridge and civil infrastructure inspection face a coupled perception–communication–control bottleneck: onboard processors are constrained by Size, Weight, and Power (SWaP) limits, whereas high-resolution structural imagery can exceed the capacity of a constrained uplink before the next inspection decision. This technical note presents a reproducible, trace-driven analytical benchmark evaluating how structured model compression interacts with **Confidence-Gated Adaptive Offloading (CGAO)** on the public **CODEBRIM** concrete defect dataset. Following a strict three-stage data hygiene audit (retaining 1,040 geometrically verified images across an 832/104/104 split), we evaluate four `YOLOv8n` ONNX variants (`FP32`, `Pruned-FP32`, `INT8`, and `Pruned-INT8`) on a thread-constrained CPU profile (`CPU4`) paired with an `RTX 4060` CUDA cloud reference. While structured L1-norm channel pruning reduces model parameters by 34.2% (3.14M to 2.06M) and lowers mean CPU4 detector latency (preprocessing through postprocessing) by 25.7% (60.76 ms to 45.16 ms), full-frame binary offloading across dense multi-defect scenes triggers high offload ratios ($\rho \in [0.731, 0.942]$ across the full seven-threshold grid) and incurs modeled mean end-to-end delays of 1.66–2.12 s at 20 Mbps. Sensitivity analysis demonstrates that modeling a smaller Regions-of-Interest (ROI) payload ($\alpha_{\text{roi}} = 0.35$) for Pruned-FP32 at the 0.35 gate increases byte-weighted uplink savings from 11.0% to 68.8% (saving 319.75 MB across 104 test frames), motivating semantic ROI partitioning and perception-latency-aware flight control co-design for next-generation edge–cloud UAV systems.

---

## 1. System Motivation and Problem Formulation

In close-range infrastructure inspection, visual defect detection does not operate as an open-loop throughput benchmark; rather, end-to-end perception-to-action latency $\tau_p$ can affect closed-loop Guidance, Navigation, and Control (GNC). For illustration, a constant-speed reaction delay followed by constant braking gives a stopping-distance velocity bound $v_{\max}(\tau_p)$ under braking distance $d_s$ and deceleration $a_{\max}$:

$$v_{\max}(\tau_p) = \sqrt{(a_{\max}\tau_p)^2 + 2a_{\max}d_s} - a_{\max}\tau_p, \qquad \Delta\phi(\omega) = -\omega\tau_p.$$

Here $\Delta\phi$ is the phase lag of a pure delay at angular frequency $\omega$, not a measured stability margin. Long delays can also degrade information freshness (Age of Information, $\Delta(t) = t - U(t)$). Neither safe flight speed, thermal response nor closed-loop stability was measured here. To study this trade-off deterministically without unverified hardware claims, we decouple perception profiling from analytical network replay:

1. **Onboard Execution (`All-Edge`, $u_i = 0$):** Frame $i$ is processed entirely locally ($T_i^{\text{e2e}} = T_{\text{edge},i}$).
2. **Remote Execution (`All-Cloud`, $u_i = 1$):** Full encoded payload $S_i$ (bytes) is transmitted over nominal uplink bandwidth $B$ (Mbps) with round-trip overhead $T_{\text{rtt}} = 20.0\text{ ms}$:
   $$T_{\text{tx},i}(B) = \frac{8 S_i}{1000 B}\;[\mathrm{ms}], \qquad T_i^{\text{all\_cloud}} = T_{\text{tx},i} + T_{\text{rtt}} + T_{\text{cloud},i}.$$
3. **Confidence-Gated Adaptive Offloading (`CGAO`):** After lightweight onboard inference, frame $i$ is offloaded ($u_i = 1$) if and only if **any** retained local detection candidate $k$ falls within an uncertainty confidence band $[\tau_{\text{low}}, \tau)$ with $\tau_{\text{low}} = 0.15$:
   $$u_i(\tau) = \mathbf{1}\{\exists k : \tau_{\text{low}} \le p_{ik} < \tau\}, \qquad T_i^{\text{cgao}} = T_{\text{edge},i} + u_i\left(\alpha_{\text{roi}} T_{\text{tx},i} + T_{\text{rtt}} + T_{\text{cloud},i}\right).$$
   Onboard dynamic compute and radio transmit energy per frame are modeled analytically as $E_i = P_{\text{comp}} T_{\text{edge},i}^{\text{used}} + u_i P_{\text{tx}} a_i T_{\text{tx},i}$ ($P_{\text{comp}} = 10.0\text{ W}$, $P_{\text{tx}} = 3.0\text{ W}$), where $a_i$ is the payload fraction (one for full-frame transmission), explicitly excluding unmeasured rotor propulsion power and cloud wall-power.

---

## 2. Dataset Hygiene Audit and Experimental Setup

### 2.1 CODEBRIM Three-Stage Quality Audit
From the official 1,590-image CODEBRIM archive (MD5 verified), deterministic pre-training audits excluded three non-conforming subsets before splitting (`seed=42`):
- **538 images** lacking Pascal VOC `.xml` detection files (multi-label classification background subset; excluded rather than assumed as verified detection negatives);
- **2 images** (`image_0000300`, `image_0001396`) containing 3 bounding boxes with all-zero defect and background flags;
- **10 images** exhibiting aspect-ratio mismatches between JPEG rasters (`6000×4000`, 3:2) and XML declarations (`4608×3456`, 4:3).

The remaining **1,040** geometrically consistent images (EXIF orientation metadata normalized in 57 prepared files without changing stored-raster pixels) were partitioned into **832 train / 104 val / 104 test** splits (864 test class-box reference rows across `crack`, `spallation`, `corrosion_stain`, `efflorescence`, and `exposed_bar`).

### 2.2 Model Compression and Measurement Protocol
- **Structured L1-Norm Channel Pruning (`Pruned-FP32`):** Physical channel slicing (2/3 target width rounded to multiples of 4) across `C2f` residual/concatenation topologies and `Detect` towers, followed by 20-epoch recovery fine-tuning (`640×640`, `AdamW`, `lr0=0.001`, `seed=42`).
- **Static QDQ INT8 Quantization (`INT8`, `Pruned-INT8`):** Post-training static `MinMax` QDQ quantization (`QUInt8` activations, per-channel `QInt8` weights on `Conv` operators) calibrated strictly on 100 deterministic `train` images.
- **Scope & Evaluation Disclaimers:** Latency traces (`CPU4` intra-op 4 threads vs. `RTX 4060` CUDA reference) are **development-host** measurements, not embedded ARM/Jetson or flight telemetry. Because CODEBRIM XML annotations do not guarantee exhaustive whole-image negative coverage (`complete=false`), accuracy metrics below are reported explicitly as **annotation-relative descriptive metrics** (`greedy-101point-v1`).

---

## 3. Quantitative Results and Systems Analysis

### 3.1 Compression Efficiency vs. Descriptive Accuracy (`CPU4` Standalone)

| ONNX Variant | Size (MB) | Params / GFLOPs | CPU4 Mean / P95 / P99 (ms) | Sampled peak process RSS (MB) | Descriptive mAP@50 | Descriptive mAP@50:95 | `crack` AP50 / Recall | `spallation` AP50 / Recall |
| :--- | ---: | :---: | :---: | ---: | ---: | ---: | :---: | :---: |
| **FP32 Baseline** | 12.78 | 3.14M / 8.75 | 60.76 / 94.46 / 118.74 | 151.39 | 0.2997 | 0.1465 | 0.1240 / 0.1373 | 0.3905 / 0.4922 |
| **Pruned-FP32** | 8.48 | 2.06M / 5.45 | **45.16 / 66.01 / 79.55** | 156.04 | 0.2982 | 0.1322 | 0.1141 / 0.0902 | **0.4125 / 0.4715** |
| **Static INT8** | 3.59 | 3.14M / 8.75 | 60.86 / 78.26 / 95.31 | 156.80 | 0.2813 | 0.1338 | 0.0841 / 0.0941 | 0.3616 / 0.4560 |
| **Pruned-INT8** | **2.50** | 2.06M / 5.45 | 58.83 / 88.58 / 100.78 | 158.30 | 0.2805 | 0.1208 | 0.0999 / 0.0863 | 0.3983 / 0.4508 |

*Annotation-relative descriptive metrics on the 104 admitted test images (864 XML reference rows); not exhaustive whole-image ground-truth coverage (`complete=false`).* The CPU4 profile used 20 warm-ups and 100 calls on one fixed validation image. GFLOPs are source-architecture estimates; RSS excludes GPU memory.

**Key Findings:**
1. **Pruning Accelerates CPU Execution; QDQ Shrinks Storage Footprint:** Physical channel pruning reduces `CPU4` mean latency by **25.7%** (45.16 ms vs. 60.76 ms) with a small decrease in overall descriptive `mAP@50` (`0.2982` vs. `0.2997`). Conversely, `Pruned-INT8` compresses disk footprint by **80.4%** (2.50 MB), but its mean latency (58.83 ms) exceeds Pruned-FP32’s, and descriptive `mAP@50:95` falls to `0.1208`. No operator-level timing isolated the cause.
2. **Fine-Grained Crack Sensitivity:** Pruned-FP32 scores higher on `spallation` AP50 but lower on its recall than baseline FP32; `crack` recall drops from `0.1373` to `0.0902` (`Pruned-FP32`), creating a natural use case for selective cloud escalation.

---

### 3.2 Trace-Driven Edge–Cloud Offloading Replay (Full-Payload vs. ROI Sensitivity)

| Edge Model | Link (Mbps) | Policy | Offload Ratio $\rho$ | Byte Saving $\eta_{\text{bw}}$ | E2E Mean / P95 (ms) | Mean Energy (mJ/frame) | Descriptive mAP@50 | `crack` Recall |
| :--- | :---: | :--- | :---: | :---: | :---: | ---: | ---: | ---: |
| **Pruned-FP32** | — | `All-Edge` | 0.000 | 1.000 | **81.2 / 119.5** | **812.0** | 0.2982 | 0.0902 |
| **Cloud Ref** | 20 | `All-Cloud` | 1.000 | 0.000 | 2,153.8 / 4,168.1 | 6,374.7 | 0.2997 | 0.1373 |
| **Pruned-FP32** | 20 | `CGAO (τ=0.35)` | 0.885 | 0.110 | 1,998.8 / 4,086.6 | 6,488.1 | **0.3008** | **0.1373** |
| **Pruned-FP32** | 5 | `CGAO (τ=0.35)` | 0.885 | 0.110 | 7,674.9 / 16,136.4 | 23,516.4 | **0.3008** | **0.1373** |
| **Pruned-FP32** | 1 | `CGAO (τ=0.35)` | 0.885 | 0.110 | 37,947.5 / 80,402.0 | 114,334.0 | **0.3008** | **0.1373** |
| **Static INT8** | 20 | `CGAO (τ=0.35)` | 0.846 | 0.151 | 1,912.8 / 4,088.8 | 6,250.7 | **0.3064** | **0.1373** |
| **Pruned-INT8** | 20 | `CGAO (τ=0.35)` | 0.817 | 0.180 | 1,844.6 / 4,072.9 | 6,019.9 | 0.2954 | 0.1333 |

*Annotation-relative descriptive metrics on the 104 admitted test images (864 XML reference rows); not exhaustive whole-image ground-truth coverage (`complete=false`).* Replay uses per-frame timings, not the repeated validation-frame timings in §3.1.

**Key Systems Insights (see Figures `01-accuracy-latency-frontiers.pdf` and `02-energy-and-byte-savings.pdf`):**
1. **Why Full-Image Binary Offloading Bottlenecks on High-Resolution Inspection:** Although `CGAO (τ=0.35)` restores `crack` recall from `0.0902` back to the `0.1373` cloud baseline, the admitted test images average 5.31 MB of encoded payload and 8.3 XML class-box rows per image (not necessarily distinct or overlapping defects). Across the four variants, 81.7%–88.5% of frames contain at least one uncertain candidate in $[0.15, 0.35)$, causing full-payload serialization to dominate latency (mean end-to-end latency of 1.84–2.03 s across the four variants at 20 Mbps; Pruned-FP32 alone takes 1,998.8 ms versus 81.2 ms locally).
2. **ROI Cropping Sensitivity ($\alpha_{\text{roi}} = 0.35$):** Under a communication-only sensitivity sweep that scales transmitted bytes to 35% without encoding or scoring any crops, `Pruned-FP32` ($\tau = 0.35$) increases byte-weighted bandwidth savings $\eta_{\text{bw}}$ from **11.0% to 68.8%** (saving **319.75 MB across 104 frames**). The modeled **TX energy saving per submitted frame** is **3.69 J** at 20 Mbps or **73.79 J** at 1 Mbps.
3. **False-Negative Blind Spot of Confidence Banding:** Frames with zero local detections above $\tau_{\text{low}} = 0.15$ are accepted locally without offloading, so this gate cannot request a second opinion for a missed crack on such a frame.

---

## 4. Threats to Validity and Future Research Directions

- **Analytical Scope:** All network, energy, and ROI figures represent deterministic independent-frame analytical simulations without wireless packet loss, queuing dynamics, or closed-loop flight actuation.
- **Evaluation scope:** The split is image-disjoint, not verified bridge-disjoint. Neither descriptive scores nor these host profiles establish field detection reliability.
- **Next-Stage Research Agenda:** (1) Implementing physical **ROI-cropped semantic offloading** paired with coordinate remapping and cloud-side accuracy validation; (2) introducing **uncertainty- and AoI-aware rate control** (`Δ(t)` bounds) that couples offloading decisions with UAV hover/inspection velocity commands; and (3) benchmarking quantized detectors on embedded TensorRT/NPU hardware (`Jetson Orin Nano`).

## Evidence and reproduction

See the [simulator specification](offload_sim_spec.md), [Day 1 dataset audit](../logs/2026-11-24_day1_yolov8n_fp32_baseline.md), [Day 2–3 compression profiles](../logs/2026-11-24_day2_3_pruning_int8_compression.md), and [Day 3–4 replay tables and artifact hashes](../logs/2026-11-24_day3_4_offloading_simulation_and_traceability.md). With the cached replay JSON available, run `python -m edge_inference.scripts.plot_offloading_results figures` from the repository root to generate the two figures locally without inference or simulation. The footer-only correction does not change the source data; the original log records the pre-correction Figure 1 hashes.
