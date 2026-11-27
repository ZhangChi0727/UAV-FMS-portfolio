# Day 2–3: physically pruned and QDQ INT8 CODEBRIM detectors

## Objective

Compare four ONNX variants on the same decoded validation frame and export their
CPU4 detections on the same 104 test frames. CPU4 and the reused RTX 4060 GPU
trace are **development-host** measurements, not ARM/Jetson, cloud-service,
network, closed-loop, or flight measurements. No weights or data are published.

## Method and implementation (human vs AI)

The Owner specified L1 channel pruning, recovery, static PTQ, the split and the
measurement protocol. The engineering agent implemented the channel slicing,
calibration, evaluation and tests. All paths below are relative to the repository
root unless otherwise indicated.

- Day 1, read only: split SHA-256
  `7321eaef3d7cd3526e7489e4c3872554f6f8741a2030e5ff45dcb5bf461adf84`;
  PyTorch checkpoint
  `ffd8228000e0c5ca385b58389d212aba7a19a5b14a6a4f4e3b36209005e6f255`;
  GPU trace
  `b5737af3a6ddbafa9e8815e20d096e1dc46d712834fae1b4ec660d1b3d0a68a9`.
- Recovery sees only hash-verified copies of 832 train and 104 val images and
  labels in `build/day23-recovery-data/`. No test path in recovery YAML.
  One prespecified width (nearest multiple of four to two thirds of each
  internal width), **not** a search over sparsity ratios. Output-filter L1
  norms select surviving channels; residual branches share indices and
  concatenations use the corresponding slice offsets. All external feature
  widths and the five-class Detect output stay unchanged. This is physical
  removal, not a zero mask. Validation chooses the recovery checkpoint.
- Unfused source-model parameter counts **3,138,975 → 2,064,091**; same-library
  640-input GFLOP estimates **8.7542912 → 5.4528928**. These are not a count
  of measured CPU instructions. QDQ changes representation and kernels, not the
  source architecture's parameter count or nominal FLOPs. Day 1's fused-model
  estimate is not the denominator for the pruning comparison.
- Recovery: 20 epochs, 640, batch 16, seed 42, AdamW, initial learning rate
  0.001, AMP and TF32 disabled. Config, epoch metrics and actual checkpoint are
  local in `edge_inference/runs/yolov8n_pruned/`. No masked-model speedup inferred.
- Both PTQ conversions: same 100 train images, Python RNG seed 42 on sorted
  train filenames; byte hashes checked. Calibration calls the same letterbox,
  BGR→RGB and normalized FP32 NCHW preprocessing as ONNX inference. Static QDQ,
  per-channel signed weights, unsigned activations, fixed MinMax, Conv only;
  not a claim that all operators execute in integer arithmetic.
- Timing: separate CPU processes, ORT CPU intra-op 4 and inter-op 1; OpenCV 4.
  Fixed validation image `image_0000021.jpg`, 20 warmups plus 100 timed calls.
  The timer starts at decoded BGR; excludes file I/O, JPEG decode and transport.
  RSS is sampled between calls, not instantaneous peak memory or VRAM.
- Each final test pass has an exclusive pre-inference marker and incremental
  per-frame journal. Frozen threshold 0.15 / class-wise NMS 0.45, same decoder
  for all four. Payload sizes are the actual prepared file bytes (including MPO
  secondary views); boxes use the original stored raster's pixel coordinates.
  References are joined for offline scoring only. No test-based retuning.

## Scoring boundary

Day 1 did not establish exhaustive negatives. Its reference records deliberately
set `complete=false`. The strict `offload_sim.evaluate` contract returns
unavailable, **not zero**, when coverage is incomplete. Do not remove this flag
or substitute Day 1's PyTorch AP as an ONNX score. Day 1 AP used a different
decoder, score floor and evaluator. The split is image-disjoint, not established
bridge-disjoint, and its test images have already been used on Day 1.

## Environment and regression checks

Windows development-host CPU: Intel Core i9-12900HX. Recovery uses the local
RTX 4060 Laptop GPU; CPU profiling uses only ORT's CPUExecutionProvider. The
four-thread configuration limits ORT intra-op and OpenCV; it is not a four-core
affinity cap. File sizes and RSS here use decimal MB. No dataset-specific
conclusion about accuracy can be drawn from FLOP counts or tensor errors alone.

From each track's own directory, using the project virtual environment:

| Directory | Actual command | Result |
|---|---|---|
| `edge_inference` | `python -m pytest tests -q` | 98 passed |
| `simulation track` | `python -m pytest -q` | 25 passed |
| `estimation track` | `python -m pytest -q` | 52 passed |
| `integration track` | `python -m pytest -q` | 165 passed |

The compression tests exercise real channel removal and gradients in a synthetic
C2f, CPU execution of a quantized synthetic Conv, reproducible train-only
calibration membership, and typed simulator input with incomplete references.
The tests do not consume CODEBRIM test images. `python -m pip check`: no broken
requirements found.

## Recovery and quantization observations

Recovery completed epoch 20 (628.05 s cumulative epoch time, from `results.csv`).
Ultralytics' best-checkpoint **validation** mAP50 / mAP50-95: 0.342 / 0.154;
Day 1 reported 0.345 / 0.172 on those same 104 validation images. This is not
the four-variant ONNX test result or proof that task accuracy is preserved.
Recovery and export exited 0. Pruned checkpoint SHA-256:
`3777f0046fca8e678514cae3ca87c4fbd13fed6a19ae6cbbf0c82a8c4b304791`.
Reload preserved the reduced parameter count; the static opset-17 export was
explicitly simplified and checked, including a changed histogram of physical
Conv weight dimensions. Raw console: `build/day23-recovery.log`,
`build/day23-export.log`; epoch table SHA-256:
`6bfd3571ce06096de4d9f576ee025c5e6a0205f8de85d2e3422a00a8c11d1806`.

Both MinMax calibrations completed; ORT logged a preprocessing recommendation,
not a conversion failure. On the four alphabetically first validation frames,
the *pre-NMS* mean absolute change in box components (640-input pixels, all
anchors) ranged from 8.31–14.47 for baseline PTQ versus its FP32 parent and
12.15–24.74 for pruned PTQ versus its FP32 parent. The largest absolute
class-score change across those four images was 0.8382 and 0.4635, respectively.
These describe raw tensor changes, not localization error against labels.
No calibration change followed. Calibration IDs / node counts are in
`edge_inference/weights/yolov8n_int8.json` and `yolov8n_pruned_int8.json`
(same directory). Raw PTQ consoles: `build/day23-base-ptq.log` and
`build/day23-pruned-ptq.log`.

Frozen identities, evaluation settings and four-frame validation diagnostic:
`edge_inference/runs/yolov8n_pruned/variants-freeze.json`,
SHA-256 `eee4e008ffc36732876e82aba9e1fe31c2c3fbba6524f8ba28901166038bb544`.

## Four-variant results (development-host CPU4)

| Variant | MB | Source params / GFLOPs | Total mean / P95 / P99 (ms) | Sampled peak RSS (MB) | Retained boxes | Strict mAP50 / mAP50–95 |
|---|---:|---|---|---:|---:|---|
| fp32_baseline | 12.777 | 3,138,975 / 8.754 | 60.76 / 94.46 / 118.74 | 151.39 | 806 | N/A / N/A |
| pruned_fp32 | 8.482 | 2,064,091 / 5.453 | 45.16 / 66.01 / 79.55 | 156.04 | 713 | N/A / N/A |
| int8 | 3.590 | 3,138,975 / 8.754 | 60.86 / 78.26 / 95.31 | 156.80 | 762 | N/A / N/A |
| pruned_int8 | 2.499 | 2,064,091 / 5.453 | 58.83 / 88.58 / 100.78 | 158.30 | 668 | N/A / N/A |

All four passed structural trace validation. Each journal has one start plus
104 distinct frame records. Offline evaluator support: crack 255, spallation
193, efflorescence 97, exposed bar 161, corrosion stain 158 (864 rows).
**Crack, spallation and corrosion stain Recall/AP50 are N/A for every variant**
under the strict coverage rule above. Counts of detections are not accuracy.
No pretense of complete annotations or independently confirmed accuracy retention.

| Variant | Preprocess mean/P95/P99 | Inference mean/P95/P99 | Postprocess mean/P95/P99 |
|---|---|---|---|
| fp32_baseline | 4.17 / 5.23 / 10.98 | 56.16 / 89.82 / 105.72 | 0.43 / 0.50 / 0.66 |
| pruned_fp32 | 3.97 / 4.89 / 6.21 | 40.60 / 60.37 / 74.76 | 0.59 / 0.73 / 1.30 |
| int8 | 4.00 / 4.49 / 6.21 | 56.43 / 73.74 / 90.82 | 0.42 / 0.53 / 0.70 |
| pruned_int8 | 4.01 / 4.49 / 6.68 | 54.23 / 82.72 / 96.64 | 0.58 / 0.68 / 0.91 |

Milliseconds, one fixed validation frame. **Use the contemporary FP32 control:**
its P95 (94.46 ms) differs materially from Day 1's separate 31.44 ms CPU4 run.
This experiment did not control or establish the cause of that host variability.
Pruned FP32 had the lowest mean and P95 here; pruned INT8 had the smallest file,
but higher mean latency than pruned FP32. Neither one run per configuration
nor the unavailable strict accuracy justifies an overall deployment ranking.

| Variant | ONNX SHA-256 | CPU4 profile SHA-256 | CPU4 trace SHA-256 |
|---|---|---|---|
| fp32_baseline | `9ee091bd2a70a5b99ea3f93712d9f6774f02c65d1576f0e444d9b7f31d8fbc3e` | `a1f155b91844c92c1ab0c5bf5ca95ae39d6c204eb8c5711f077f39b63dbc4720` | `50a4bea5bcd3187f08bdb8ad00d85b32484c121b71c9ea48f0449acbbe9420d1` |
| pruned_fp32 | `bbad827344cadf33b07470c262a8c68167f29c1eda769ec77e04c64d13c459c1` | `207fbd5091b65d76c978e032d20571bfb6254d28ddb8bf843591f7a46ec45afc` | `e059a388a2a3f714c966e9c4694bafd39e49ad3b362d84730488bdb7a3a3b7de` |
| int8 | `b761044831aaf0c45b892fc217007543609e5a64bd8b4c915adb71acadf996bc` | `aefbe0bb10ea96c9e95682380237b2d962309687a904c6caeefca0b0bdfeabef` | `d7857b70faefbbb2e3f6538d0e44c853483e2505dd9d754ca9897000c8f62456` |
| pruned_int8 | `156e8fa5ba8aa20458582a6d1062b0460d19e65778856a8c2be7cb04dcb144cf` | `8e4d254ea6a44a816e8a5a757e2dfdd8bc7aa7bdb0362dba9d9ae5cf74e38062` | `ed3e3eee5dfc77c497eae8386bfbf0fac85f21be452757c403d2ca92fbf02fe8` |

ONNX: `edge_inference/weights/` (filenames in `MODELS`).
Raw timing and trace files: `edge_inference/docs/profile-<variant>-cpu4.json`
and `edge_inference/docs/trace-<variant>-cpu4.json`. Four labeled comparison
panels in `edge_inference/runs/compression_qualitative/` compare XML, baseline
FP32 and pruned INT8 (one displayed class per panel). The examples select by
annotated region count then ID, not by which model was correct.

## Commands, outcomes and reusable assets

Executed with the project virtual environment from the repository root, each
stage in a separate Python process, each listed command exited 0:

1. `python -u -m edge_inference.scripts.compress_pruning train` and
   `python -u -m edge_inference.scripts.compress_pruning export`.
2. `python -u -m edge_inference.scripts.quantize_int8` (baseline, during
   recovery) and `python -u -m edge_inference.scripts.quantize_int8 --pruned`.
3. `python -u -m edge_inference.scripts.eval_compression_variants freeze`.
4. `python -u -m edge_inference.scripts.eval_compression_variants profile <variant>`
   for fp32_baseline, pruned_fp32, int8, pruned_int8, in that order; then
   the same four commands with `trace` instead of `profile`. These completed
   sequentially after training and PTQ, with one test inference per image per
   model. Do not repeat the trace stage on these test data.
5. `python -m edge_inference.scripts.eval_compression_variants panels` and
   `python -m edge_inference.scripts.eval_compression_variants summarize`.
   The latter checks model/trace/profile identity, journal agreement and timing
   statistics from cached raw data only; output in `build/day23-summary.jsonl`.
