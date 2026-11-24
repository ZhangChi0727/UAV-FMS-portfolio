# EDGE: bridge inspection model compression

The active proposed requirements are EDG-REQ-0034–0041. These files are scaffolding,
not a trained detector, functional compression pipeline, or benchmark. No accuracy,
latency, board or flight results are claimed.

- configs/baseline.yaml: CLI defaults for image size, warmup, runs and CPU threads.
- src/detector.py: ONNX raw YOLOv8 detection-head adapter and Ultralytics adapter.
- src/benchmark.py: synthetic-input timing runner.
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

## Isolated Windows environment

From the repository root (Python 3.11), create `.venv`; do not install into the
global interpreter or the preserved B0 environment:

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
