# UAV FMS Portfolio

**What does compressing a bridge-defect detector buy, and when does transmitting the image cost more than running the detector locally?** The EDGE track answers that question for one development host and a fixed set of CODEBRIM images. The independent GNC track provides a deterministic attitude-estimation and C++17 control baseline. Neither track makes a flight-performance claim.

**Start with the [illustrated technical note](edge_inference/docs/technical_note_uav_edge_offloading.md)** for the results, figures and limits. The [offloading specification](edge_inference/docs/offload_sim_spec.md) defines what a policy can observe and how bytes, latency and energy are counted.

## Results: four detector variants on CPU4

| ONNX variant | Size (MB) | CPU4 mean (ms) | CPU4 P95 (ms) | Descriptive mAP@50 |
| :--- | ---: | ---: | ---: | ---: |
| FP32 baseline | 12.78 | 60.76 | 94.46 | 0.2997 |
| Pruned-FP32 | 8.48 | 45.16 | 66.01 | 0.2982 |
| Static INT8 | 3.59 | 60.86 | 78.26 | 0.2813 |
| Pruned-INT8 | 2.50 | 58.83 | 88.58 | 0.2805 |

Pruned-FP32 had the lowest P95; Pruned-INT8 was the smallest. All four observed variants are non-dominated when **maximizing mAP@50 and minimizing P95 and ONNX size** together. This is not a significance test or a universal ranking.

**Measurement:** CPU4 is a four-thread **development-host** profile (20 warm-ups, 100 calls on one fixed validation image); the RTX 4060 CUDA profile supplies a remote-compute reference, not an onboard or cloud-service measurement.
**Accuracy:** the 104 test images contain 864 annotated class-box rows. With `complete=false`, mAP is descriptive and relative to those annotations, not a measure of field reliability.

**Offloading:** Pruned-FP32 with the confidence gate [0.15, 0.35) offloaded 92 of 104 frames. Relative to sending every full frame, full-payload gating saved **11.0%** of bytes. Keeping the same decisions but modeling each transmitted payload at 35% of its size (`alpha_roi=0.35`) raised savings to **68.8%**. No crop was encoded or scored. Network delay and energy are modeled, not measured.

## Two tracks, separate evidence

- **GNC:** simulation, attitude estimation and cascaded control share explicit message contracts: NED/body frames, SI units and scalar-first Hamilton quaternions. Estimator and controller inputs exclude truth except explicit initialization. Component acceptance is not closed-loop validation; historical integration material is retained at tag `pre-surgery-2026-11-22`.
- **EDGE:** [module guide and environment setup](edge_inference/README.md) for data preparation, pruning, static INT8 quantization, profiling and cached-trace replay. Dataset images, trained weights and raw runtime JSONs are not distributed in Git. The figures and reported tables can be read without them.
- **Traceability:** [StrictDoc requirements index](requirements/README.md) · [offline requirements view](overview.html#requirements). The eight EDGE prototype requirements (EDG-REQ-0034–0041) are approved and implemented; the StrictDoc files remain authoritative.

## Verification and reproduction

Verified baseline at `1baf1e4`: **440 pytest cases passed** (simulation 25, estimation 52, control 79, integration 165, EDGE 119). **25 CTest entries passed**, including four C++ mutation tests and the Python binding/adapter suite. The latter overlaps the 440; these are not 465 distinct tests.

From the repository root, in Bash with Python 3.11 and the project dependencies active:

```bash
# C++17 compiler and Ninja required. Use the binding built for this Python.
cmake --preset gnc-controller-debug -DPython3_EXECUTABLE="$(python -c 'import sys; print(sys.executable)')"
cmake --build --preset gnc-controller-debug
ctest --preset gnc-controller-debug --output-on-failure

# Each pytest invocation runs in its own track, not at the repository root.
(cd gnc_baseline/simulation && python -m pytest -q)
(cd gnc_baseline/estimation && python -m pytest -q)
(cd gnc_baseline/control && python -m pytest -q)
(cd gnc_baseline/integration && python -m pytest -q)
(cd edge_inference && python -m pytest -q)

# Check the committed offline view without rewriting it.
python requirements/render_overview.py --check
```

To verify the three-objective frontier **with the retained hash-matched JSONs** (four CPU4 profiles and the replay result), run:

```bash
python -m edge_inference.scripts.plot_offloading_results pareto
```

This reads cached results; it neither trains a model nor runs inference.
See the [Day 3–4 experiment log](edge_inference/logs/2026-11-24_day3_4_offloading_simulation_and_traceability.md) for the provenance of the replay and figures.

For GNC imports outside the checkout, run `python -m pip install -e . --no-build-isolation --no-deps` in an environment with NumPy, setuptools and wheel.
Import from `gnc_baseline.simulation`, `gnc_baseline.estimation`, `gnc_baseline.control` or
`gnc_baseline.integration`. The native binding is `gnc_controller`; there are no legacy import aliases.
