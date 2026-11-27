# EDGE: bridge inspection model compression

The Day 1–4 pipeline covers CODEBRIM data preparation, YOLOv8n training,
compression, development-host profiling and cached-trace replay. The
[technical note](docs/technical_note_uav_edge_offloading.md) reports the four
variants and the limits of the comparison. EDG-REQ-0034–0041 are approved
prototype requirements; the results are not board or flight measurements.

[Review the archived run records](logs/evidence/2026-11-24/README.md): interrupted and completed training, exports, quantization and the environment check, with SHA-256 hashes for all 18 files.

- configs/baseline.yaml: CLI defaults for image size, warmup, runs and CPU threads.
- src/detector.py: ONNX raw YOLOv8 detection-head adapter and Ultralytics adapter.
- src/benchmark.py: stage timings on synthetic inputs, with a dummy workload or an ONNX model.
- scripts/prepare_codebrim.py, train_baseline.py and export_fp32_trace.py: audit and split the annotated images, train the FP32 baseline, and export its trace.
- scripts/compress_pruning.py, quantize_int8.py and eval_compression_variants.py: physically prune channels, calibrate static INT8 on training images and profile the four variants.
- src/offload_sim.py and scripts/run_offloading_experiments.py: apply offload policies to fixed traces and score full-frame predictions against available annotations. scripts/plot_offloading_results.py renders tables and figures from cached results.
- logs/TEMPLATE.md: experiment record template.
- data/ and models/: local artifacts, not committed.

From edge_inference/, run `python -m src.benchmark --synthetic` for a dummy
workload, or add `--model path/to/model.onnx --provider cpu --threads 4` for
an actual model. CUDA requires an available CUDAExecutionProvider; there is no
silent CPU fallback. Raw YOLOv8 ONNX output only is supported, not end-to-end
NMS exports or arbitrary architectures. Model/dataset class mappings are not
established by the configured class list. The Ultralytics adapter is accessible
through the Python interface but not the benchmark CLI.

`--config PATH` selects another YAML file. `--imgsz`, `--warmup`, `--runs`
and `--threads` override its defaults. The default config and output paths are
resolved relative to this module, independent of the working directory.
Image size controls synthetic input size, not the fixed ONNX model input shape.

Raw per-call times are retained in ignored JSON under docs/. RSS is sampled
between calls, not a guaranteed instantaneous peak. No mAP is measured with
synthetic input. CPU thread limits do not emulate an ARM or Jetson device.
Results are development-host measurements; no hardware or flight claim follows.
Datasets and weights are not included; verify licences and class mappings first.

## Analytical offloading replay (synthetic demonstration)

From `edge_inference/`, run `python -m src.offload_sim --synthetic`.
The ignored output is `docs/offload-sim-synthetic.json`, explicitly labeled
`synthetic_not_measured`, `development-host`, and `analytical_simulation`.
No model is loaded and no dataset or network service is accessed.
The [design specification](docs/offload_sim_spec.md) defines the equations.

The default sweep contains 21 CGAO points and two baseline families: All-Edge
is evaluated once; All-Cloud has three bandwidth-dependent results (25 result
records in total), with no redundant threshold runs. `--alpha-roi` changes only
CGAO's modeled transmitted bytes. Non-unit ROI factors have no accuracy claim
without corresponding ROI traces, so accuracy is explicitly unavailable.

The Python API accepts typed `TraceInputs`, `FrameTrace`, `StageTiming` and
`Detection` records joined by frame ID. Keep benchmark profile/source hashes,
model/configuration, class mapping and timing-sample associations in provenance.
The existing benchmark JSON alone is not a complete simulator input.
Ground truth reaches only the offline evaluator, never `decide`.
Evaluator v1 uses deterministic class-wise greedy matching and 101-point
interpolated AP, without COCO area/maxDets/crowd handling. It is not a claim of
COCO API parity. Missing/incomplete reference coverage yields unavailable
accuracy; unsupported classes without GT support have null recall. The default
recall operating point (score 0.25, IoU 0.5) is for synthetic demonstration;
freeze real evaluation settings on training/calibration data before test use.

## Isolated Windows environment

From the repository root (Python 3.11), create `.venv`; do not install into the
global interpreter or the preserved GNC environment:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cu124
.venv/Scripts/python.exe -m pip install -r edge_inference/requirements.txt -c requirements.txt torch==2.6.0 torchvision==0.21.0
.venv/Scripts/python.exe -m pip check
```

The headless Ultralytics distribution exposes `import ultralytics` without
installing a second, conflicting OpenCV GUI distribution. Install only one ORT
distribution: this environment uses `onnxruntime-gpu`, which also supports CPU.
The CUDA adapter preloads runtime DLLs from the PyTorch installation before
creating its session. Provider availability alone is not a trained-model test.
See the [PyTorch wheel matrix](https://pytorch.org/get-started/previous-versions/)
and [ORT CUDA DLL guidance](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html).

On this host, Python 3.11.5 is based on Anaconda, whose adjacent MSVC 14.29 DLLs
shadow the installed Windows MSVC 14.44 runtime. Plain ORT import initially
failed with DLL initialization error 1114. This local `.venv` therefore has an
ignored `Lib/site-packages/sitecustomize.py` that preloads `msvcp140.dll`,
`msvcp140_1.dll` and `msvcp140_2.dll` from `%SystemRoot%/System32` via
`ctypes.WinDLL`, retaining their handles. This is process-local: no Anaconda or
system DLL was replaced. Recreating an environment from this Anaconda requires
the same workaround or a compatible standalone Python; do not copy old DLLs
over system files. Recheck imports and all tests after environment changes.
