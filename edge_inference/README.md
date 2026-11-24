# EDGE: bridge inspection model compression

The active proposed requirements are EDG-REQ-0034–0041. These files are scaffolding,
not a trained detector, functional compression pipeline, or benchmark. No accuracy,
latency, board or flight results are claimed.

- configs/baseline.yaml: proposed run settings, not automatically consumed by the CLI.
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

Raw per-call times are retained in ignored JSON under docs/. RSS is sampled
between calls, not a guaranteed instantaneous peak. No mAP is measured with
synthetic input. CPU thread limits do not emulate an ARM or Jetson device.
Results are development-host measurements; no hardware or flight claim follows.
Datasets and weights are not included; verify licences and class mappings first.
