# Day 3–4: CODEBRIM cached-trace replay

## Question and boundary

Does confidence-gated offloading improve the descriptive detection score enough to offset transferring full encoded images? On this fixed replay, local inference often gives a similar mAP50 at far lower latency. For pruned FP32 at 20 Mbps and τ=0.35, offloading 92/104 frames raises crack recall from 0.0902 to 0.1373 while mean latency increases from 81.2 to 1,998.8 ms. This is a trade-off, not a validated operating threshold.

Owner specified the grid and authorized a separate annotation-relative analysis. The engineering agent joined the cached observations, ran the sweep and produced the figures. No test inference, training, threshold selection, real network use, or battery measurements were needed for replay. Only repository publication used the network.

## Inputs and method

- Source commit `53ec3f5`. Four CPU4 traces and one RTX 4060 CUDA reference verified against exact SHA-256 constants in `scripts/run_offloading_experiments.py` (relative to `edge_inference/`). Each CPU trace's embedded cloud predictions, timings, frame metadata and XML references were checked against the separate GPU trace. Same 104 frames in every condition, not independent replicates. No claim of bridge-disjoint generalization.
- `offload_sim.sweep`: full images, four variants × (21 CGAO points + 1 edge + 3 cloud baselines) = 100 records; cloud baselines repeat the same reference. Two additional 25-record grids set α=0.35 for CGAO only, giving 42 ROI sensitivity points plus 8 baseline records. RTT 20 ms, local compute 10 W, TX 3 W. Gate: offload if **any** retained local detection score lies in [0.15, τ); an empty list does not trigger offload.
- End-to-end modeled time includes local compute when used, payload bits / nominal link rate, RTT and measured GPU compute if offloaded. Bytes are whole prepared files, including extra MPO views where present. Energy is local compute time × compute power plus transmit time × TX power. No queuing, overlap, encoding, loss, propulsion, or cloud energy. Actual per-frame test timings, **not** repeated single validation-frame profile percentiles. All timing traces are development-host; policy, transport and energy results are analytical_simulation.
- Strict accuracy remains unavailable in the original simulator results. Separate descriptive scoring uses its score-sorted greedy one-to-one matches at IoU 0.50:0.05:0.95 and 101 recall points, not COCO API. Recall uses IoU 0.50 and confidence ≥0.25; AP uses retained predictions ≥0.15. Same-class unmatched detections reduce descriptive precision even when the underlying image area may be unannotated. No reference coverage flag was changed. No ROI scores were computed.

## Table 1. CPU4 standalone detectors

Annotation-relative descriptive metrics on the 104 admitted test images (864 XML reference rows); not exhaustive whole-image ground-truth coverage (`complete=false`).

| Model | mAP50 | mAP50–95 | crack AP50 / recall | spallation AP50 / recall | corrosion_stain AP50 / recall | efflorescence AP50 / recall | exposed_bar AP50 / recall |
|---|---|---|---|---|---|---|---|
| FP32 | 0.2997 | 0.1465 | 0.1240 / 0.1373 | 0.3905 / 0.4922 | 0.3324 / 0.3924 | 0.2043 / 0.2165 | 0.4474 / 0.5342 |
| Pruned FP32 | 0.2982 | 0.1322 | 0.1141 / 0.0902 | 0.4125 / 0.4715 | 0.3175 / 0.3734 | 0.1590 / 0.1753 | 0.4880 / 0.5280 |
| INT8 | 0.2813 | 0.1338 | 0.0841 / 0.0941 | 0.3616 / 0.4560 | 0.3137 / 0.3734 | 0.1981 / 0.2165 | 0.4491 / 0.5217 |
| Pruned INT8 | 0.2805 | 0.1208 | 0.0999 / 0.0863 | 0.3983 / 0.4508 | 0.3302 / 0.3671 | 0.1238 / 0.1443 | 0.4503 / 0.4845 |

## Table 2. Full-payload analytical replay

Annotation-relative descriptive metrics on the 104 admitted test images (864 XML reference rows); not exhaustive whole-image ground-truth coverage (`complete=false`).

| Model | Mbps | Policy | ρ | η (bytes) | Mean / P95 / P99 ms | mJ/frame | mAP50 | Crack R |
|---|---|---|---|---|---|---|---|---|
| FP32 | all | all_edge | 0.000 | 1.000 | 100.0 / 137.1 / 154.3 | 1000.4 | 0.2997 | 0.1373 |
| shared | 1 | all_cloud | 1.000 | 0.000 | 42526.8 / 82837.7 / 86299.9 | 127493.9 | 0.2997 | 0.1373 |
| FP32 | 1 | CGAO 0.35 | 0.856 | 0.105 | 38145.1 / 80412.8 / 85408.3 | 115061.2 | 0.2997 | 0.1373 |
| FP32 | 1 | CGAO 0.55 | 0.904 | 0.088 | 38876.0 / 80412.8 / 85408.3 | 117249.8 | 0.2997 | 0.1373 |
| FP32 | 1 | CGAO 0.75 | 0.904 | 0.088 | 38876.0 / 80412.8 / 85408.3 | 117249.8 | 0.2997 | 0.1373 |
| shared | 5 | all_cloud | 1.000 | 0.000 | 8528.5 / 16589.6 / 17282.7 | 25498.8 | 0.2997 | 0.1373 |
| FP32 | 5 | CGAO 0.35 | 0.856 | 0.105 | 7728.9 / 16147.2 / 17137.2 | 23812.6 | 0.2997 | 0.1373 |
| FP32 | 5 | CGAO 0.55 | 0.904 | 0.088 | 7876.2 / 16147.2 / 17137.2 | 24250.3 | 0.2997 | 0.1373 |
| FP32 | 5 | CGAO 0.75 | 0.904 | 0.088 | 7876.2 / 16147.2 / 17137.2 | 24250.3 | 0.2997 | 0.1373 |
| shared | 20 | all_cloud | 1.000 | 0.000 | 2153.8 / 4168.1 / 4341.9 | 6374.7 | 0.2997 | 0.1373 |
| FP32 | 20 | CGAO 0.35 | 0.856 | 0.105 | 2025.8 / 4097.4 / 4368.0 | 6703.5 | 0.2997 | 0.1373 |
| FP32 | 20 | CGAO 0.55 | 0.904 | 0.088 | 2063.7 / 4097.4 / 4368.0 | 6812.9 | 0.2997 | 0.1373 |
| FP32 | 20 | CGAO 0.75 | 0.904 | 0.088 | 2063.7 / 4097.4 / 4368.0 | 6812.9 | 0.2997 | 0.1373 |
| Pruned FP32 | all | all_edge | 0.000 | 1.000 | 81.2 / 119.5 / 127.6 | 812.0 | 0.2982 | 0.0902 |
| Pruned FP32 | 1 | CGAO 0.35 | 0.885 | 0.110 | 37947.5 / 80402.0 / 85398.7 | 114334.0 | 0.3008 | 0.1373 |
| Pruned FP32 | 1 | CGAO 0.55 | 0.904 | 0.087 | 38910.9 / 80402.0 / 85398.7 | 117222.5 | 0.3002 | 0.1373 |
| Pruned FP32 | 1 | CGAO 0.75 | 0.942 | 0.052 | 40411.9 / 80402.0 / 85398.7 | 121722.3 | 0.2998 | 0.1373 |
| Pruned FP32 | 5 | CGAO 0.35 | 0.885 | 0.110 | 7674.9 / 16136.4 / 17127.6 | 23516.4 | 0.3008 | 0.1373 |
| Pruned FP32 | 5 | CGAO 0.55 | 0.904 | 0.087 | 7868.0 / 16136.4 / 17127.6 | 24094.1 | 0.3002 | 0.1373 |
| Pruned FP32 | 5 | CGAO 0.75 | 0.942 | 0.052 | 8169.1 / 16136.4 / 17127.6 | 24994.0 | 0.2998 | 0.1373 |
| Pruned FP32 | 20 | CGAO 0.35 | 0.885 | 0.110 | 1998.8 / 4086.6 / 4386.1 | 6488.1 | 0.3008 | 0.1373 |
| Pruned FP32 | 20 | CGAO 0.55 | 0.904 | 0.087 | 2047.5 / 4086.6 / 4386.1 | 6632.5 | 0.3002 | 0.1373 |
| Pruned FP32 | 20 | CGAO 0.75 | 0.942 | 0.052 | 2123.6 / 4086.6 / 4386.1 | 6857.5 | 0.2998 | 0.1373 |
| INT8 | all | all_edge | 0.000 | 1.000 | 83.7 / 112.2 / 126.6 | 836.9 | 0.2813 | 0.0941 |
| INT8 | 1 | CGAO 0.35 | 0.846 | 0.151 | 36199.8 / 80404.2 / 85410.7 | 109111.6 | 0.3064 | 0.1373 |
| INT8 | 1 | CGAO 0.55 | 0.885 | 0.127 | 37202.3 / 80404.2 / 85410.7 | 112116.0 | 0.3009 | 0.1373 |
| INT8 | 1 | CGAO 0.75 | 0.904 | 0.101 | 38336.4 / 80404.2 / 85410.7 | 115516.5 | 0.2998 | 0.1373 |
| INT8 | 5 | CGAO 0.35 | 0.846 | 0.151 | 7326.5 / 16138.6 / 17139.6 | 22491.9 | 0.3064 | 0.1373 |
| INT8 | 5 | CGAO 0.55 | 0.885 | 0.127 | 7527.9 / 16138.6 / 17139.6 | 23092.7 | 0.3009 | 0.1373 |
| INT8 | 5 | CGAO 0.75 | 0.904 | 0.101 | 7755.2 / 16138.6 / 17139.6 | 23772.8 | 0.2998 | 0.1373 |
| INT8 | 20 | CGAO 0.35 | 0.846 | 0.151 | 1912.8 / 4088.8 / 4368.3 | 6250.7 | 0.3064 | 0.1373 |
| INT8 | 20 | CGAO 0.55 | 0.885 | 0.127 | 1964.0 / 4088.8 / 4368.3 | 6400.9 | 0.3009 | 0.1373 |
| INT8 | 20 | CGAO 0.75 | 0.904 | 0.101 | 2021.2 / 4088.8 / 4368.3 | 6570.9 | 0.2998 | 0.1373 |
| Pruned INT8 | all | all_edge | 0.000 | 1.000 | 79.6 / 112.9 / 124.1 | 795.8 | 0.2805 | 0.0863 |
| Pruned INT8 | 1 | CGAO 0.35 | 0.817 | 0.180 | 34930.5 / 80052.1 / 86334.1 | 105277.5 | 0.2954 | 0.1333 |
| Pruned INT8 | 1 | CGAO 0.55 | 0.837 | 0.166 | 35552.9 / 80052.1 / 86334.1 | 107143.1 | 0.2957 | 0.1333 |
| Pruned INT8 | 1 | CGAO 0.75 | 0.856 | 0.139 | 36687.0 / 80052.1 / 86334.1 | 110543.6 | 0.2951 | 0.1333 |
| Pruned INT8 | 5 | CGAO 0.35 | 0.817 | 0.180 | 7068.7 / 16069.7 / 17316.9 | 21692.1 | 0.2954 | 0.1333 |
| Pruned INT8 | 5 | CGAO 0.55 | 0.837 | 0.166 | 7193.6 / 16069.7 / 17316.9 | 22065.2 | 0.2957 | 0.1333 |
| Pruned INT8 | 5 | CGAO 0.75 | 0.856 | 0.139 | 7420.9 / 16069.7 / 17316.9 | 22745.3 | 0.2951 | 0.1333 |
| Pruned INT8 | 20 | CGAO 0.35 | 0.817 | 0.180 | 1844.6 / 4072.9 / 4376.6 | 6019.9 | 0.2954 | 0.1333 |
| Pruned INT8 | 20 | CGAO 0.55 | 0.837 | 0.166 | 1876.3 / 4072.9 / 4376.6 | 6113.2 | 0.2957 | 0.1333 |
| Pruned INT8 | 20 | CGAO 0.75 | 0.856 | 0.139 | 1933.5 / 4072.9 / 4376.6 | 6283.2 | 0.2951 | 0.1333 |

## Table 3. ROI communication sensitivity only

Same gates, 35% of full transmitted bytes; no ROI accuracy/timing measurement. TX energy saved per submitted frame, not percent total energy.

| Model | τ | η full → ROI | MB saved / 104 | TX mJ saved @1 | @5 | @20 |
|---|---|---|---|---|---|---|
| Pruned FP32 | 0.25 | 0.184 → 0.714 | 293.04 | 67624.3 | 13524.9 | 3381.2 |
| Pruned FP32 | 0.35 | 0.110 → 0.688 | 319.75 | 73789.3 | 14757.9 | 3689.5 |
| Pruned FP32 | 0.45 | 0.098 → 0.684 | 324.03 | 74775.4 | 14955.1 | 3738.8 |
| Pruned FP32 | 0.55 | 0.087 → 0.680 | 327.89 | 75666.9 | 15133.4 | 3783.3 |
| Pruned FP32 | 0.65 | 0.078 → 0.677 | 330.99 | 76381.4 | 15276.3 | 3819.1 |
| Pruned FP32 | 0.75 | 0.052 → 0.668 | 340.56 | 78591.7 | 15718.3 | 3929.6 |
| Pruned FP32 | 0.85 | 0.052 → 0.668 | 340.56 | 78591.7 | 15718.3 | 3929.6 |
| Pruned INT8 | 0.25 | 0.266 → 0.743 | 263.44 | 60794.9 | 12159.0 | 3039.7 |
| Pruned INT8 | 0.35 | 0.180 → 0.713 | 294.29 | 67913.1 | 13582.6 | 3395.7 |
| Pruned INT8 | 0.45 | 0.166 → 0.708 | 299.54 | 69125.7 | 13825.1 | 3456.3 |
| Pruned INT8 | 0.55 | 0.166 → 0.708 | 299.54 | 69125.7 | 13825.1 | 3456.3 |
| Pruned INT8 | 0.65 | 0.151 → 0.703 | 305.02 | 70389.2 | 14077.8 | 3519.5 |
| Pruned INT8 | 0.75 | 0.139 → 0.699 | 309.12 | 71336.1 | 14267.2 | 3566.8 |
| Pruned INT8 | 0.85 | 0.139 → 0.699 | 309.12 | 71336.1 | 14267.2 | 3566.8 |

The ROI saving of 65% of **transmitted** bytes/TX energy follows from the assumed scale, not a measured crop. For pruned FP32 at τ=0.35 it changes byte saving relative to all-cloud from 11.0% to 68.8%; it does not establish preservation of defect visibility or a 65% reduction of total energy.

## Figures and retained evidence

`edge_inference/docs/offload-sim-codebrim-results.json` contains configurations, rows, selected predictions, strict accuracy, separate descriptive scores for full payloads, metadata and summaries. `edge_inference/runs/offloading_figures/` contains two editable vector figures (SVG/PDF) and 600-dpi previews. Figure 1: all full-payload observations, by bandwidth and pair of objectives; dashed lines connect only observed non-dominated coordinates. Duplicate coordinates coincide. Figure 2: CGAO energy versus threshold and byte saving, which does not depend on link rate. No confidence intervals or significance claims: one deterministic replay, not multiple deployments.

Retained SHA-256:
```text
ae4e1c38c1383920f187fb1089ed562e1355eee569f8ccc8b3f9ba655e5c90ef  offload-sim-codebrim-results.json
b6b874f37cc7c53abb236355275f8d0eb342ff36c8be7c647ed57f8c36e36e68  01-accuracy-latency-frontiers.pdf
e7156d0349a22bf39262ee486dabbac1a5f968be51f9fae326559bdc7c5cecd9  01-accuracy-latency-frontiers.png
c42293e91fab97afb870cece433e797e7250bb91c2df009e7636aa1fcd1d6156  01-accuracy-latency-frontiers.svg
c88a4497409ceef2fb5c73d547f7c832fe1e97dc6342396539c5f836cc666764  02-energy-and-byte-savings.pdf
a9e89a8d350325fe43392b4b4869a540876b445514b47ec8012a2337e824ba84  02-energy-and-byte-savings.png
a156bb5941479a1b4e9555db42fe1596ddb5b614b37177b96666bb599f54d5f1  02-energy-and-byte-savings.svg
```

## Commands and checks

From repository root using the project virtual environment: `python -u -m edge_inference.scripts.run_offloading_experiments`, `python -m edge_inference.scripts.plot_offloading_results figures`, and `python -m edge_inference.scripts.plot_offloading_results tables` all exited 0. Rebuild figures/tables from the result JSON without repeating replay. The runner refuses to overwrite an existing result.

Figure source preflight: 13 pass, 1 warning (PNG preview rather than TIFF), 0 failures after explicit vector exports; both rendered layouts visually checked. No TIFF was requested. For the five existing sources named in the work order, Python ASTs before/after matched exactly; traceability anchors are comments only. The vault IDs are contextual pointers supplied by the Owner, not a claim that a paper established these numerical defaults. No private vault access.

Regression: project Python `-m pytest tests -q` in EDGE: 100 passed; `-m pytest -q` in B0 simulation / estimation / integration: 25 / 52 / 165 passed, respectively. Synthetic tests cover the separate scoring contract, absence of ground-truth mutation and Pareto ties. No runtime data staged.
