# Day 1: CODEBRIM detection preparation and FP32 baseline

## Objective

Prepare an image-disjoint CODEBRIM detection split, train YOLOv8n, and retain
annotation-relative test metrics and development-host ONNX timing traces.
No onboard, cloud-service, flight, or bridge-disjoint generalization claim.

## Method and implementation (human vs AI)

Owner specified seed 42, 80/10/10 image split, 640-pixel input, batch 16,
50 epochs, patience 15, four loader workers, and a development RTX 4060.
AI implemented the converter, explicit train/evaluate/export entry points,
trace exporter, and synthetic regression tests. The original archive and
existing study notes were not changed.

Initial XML-present inventory, as requested by Owner:

> 1,052 annotated images included; 538 images without XML excluded (unannotated for object detection, not treated as verified negatives)

This sentence describes the initial inventory, **not final training admission**.
Subsequent checks found quality exclusions described below. Owner approved
excluding `image_0000300.jpg` and `image_0001396.jpg`, leaving 1,050 candidates.
Owner subsequently approved excluding the ten dimension/aspect-ratio mismatches,
leaving exactly 1,040 admitted images, with the required 832 / 104 / 104 split.

Coordinates use VOC one-based inclusive bounds converted to zero-based half-open
bounds, then normalized. One positive defect flag produces one YOLO row; multiple
flags on the same box produce multiple rows. No missing or all-zero label is
silently converted to a background negative. Exact image duplicates would be
grouped before splitting. This grouping does not establish bridge independence.

## Quantitative results

These are **data-preparation checks**, not detector accuracy or performance.

| Check | Actual result | Raw artifact |
|---|---|---|
| Archive bytes | 8,310,630,622 | `edge_inference/data/codebrim_raw/CODEBRIM_original_images.zip` |
| Official MD5 comparison | `27baf3a036d0b7d757ff4df47c08c449`, matched | `edge_inference/data/codebrim_raw/extraction.json` |
| JPEG files / XML files | 1,590 / 1,052 | `edge_inference/data/codebrim_raw/annotation_audit.json` |
| Missing XML | 538, excluded by Owner decision | same audit |
| All-zero object flags | 3 objects in 2 images; both images excluded by Owner decision | same audit |
| XML/image dimension mismatch | 10 images, excluded by Owner decision | same audit |
| JPEG full-decode failures among XML-present images | 0 | same audit |
| Exact duplicate image groups among XML-present images | 0 | same audit |
| Bounding boxes requiring clipping in XML coordinates | 0 | all-XML parser audit stdout |
| Valid training / test scoring / ONNX export / CUDA and CPU4 profiles / trace | Completed, each exit 0 | artifacts and commands below |

The ten dimension-mismatch IDs are 0000197, 0000221, 0000224, 0000226,
0000227, 0000229, 0000249, 0000264, 0000286, 0000297. Every corresponding JPEG
is 6000 x 4000; its XML declares 4608 x 3456. No coordinate rescaling or inferred
label repair was applied. These ten are excluded in addition to the 538 missing
XML images and the two images with ambiguous zero-flag boxes. The raw files and
all exclusion IDs remain in the audit artifacts.

### Final admitted split (seed 42)

| Split | Images | Explicit-background empty labels | Crack | Spallation | Corrosion stain | Efflorescence | Exposed bar |
|---|---:|---:|---:|---:|---:|---:|---:|
| train | 832 | 23 | 2021 | 1561 | 1255 | 638 | 1234 |
| val | 104 | 1 | 219 | 134 | 133 | 90 | 105 |
| test | 104 | 1 | 255 | 193 | 158 | 97 | 161 |

Counts are class-box rows: a multilabel region contributes once per positive
class, not once per physical defect. The 25 empty-label images have explicit
XML background flags. They are not missing-XML or ambiguous-label images.
Manifest: `edge_inference/data/codebrim_yolo/split_manifest.json`, SHA-256
`7321eaef3d7cd3526e7489e4c3872554f6f8741a2030e5ff45dcb5bf461adf84`.
Split-list SHA-256 values are retained in that manifest.

The admitted files comprise 755 MPO multi-picture JPEG containers and 285 JPEGs.
Inference decodes the first view; payload bytes include the entire prepared file.
Only nine single-stream JPEGs had bytes stripped after their last end-of-image
(EOI) marker. No MPO container was tail-stripped: all 755 prepared MPOs retain
a second JPEG view, and 646 of the 755 do not end in an EOI marker. Truncating
at the first view's EOI would discard the secondary view. The nine JPEGs were
trimmed only in working copies, with exact OpenCV decoded-pixel equality
checked before writing (no JPEG re-encoding). Both source and prepared image
hashes, format, and removed byte counts are retained per image in the manifest.
Fifty-seven files also have non-identity EXIF orientation (29 at 3, 16 at 6,
12 at 8). XML coordinates use the stored raster; automatic display rotation must
not be applied to the pixels without transforming the boxes. Prepared copies
therefore set only the primary EXIF orientation value to 1, without re-encoding,
changing APP segment lengths, or shifting MPO secondary-view offsets. Exact
decoded BGR equality against the original **stored raster** is checked, and its
hash is retained for each changed file. Original EXIF values and source bytes
are retained. This is coordinate normalization, not label editing or augmentation.

### Completed FP32 baseline (development-host)

Data source: Mundt et al., [CODEBRIM v1.0 (CVPR 2019)](https://zenodo.org/records/2620293),
original-image archive. The authors' [dataset licence](https://zenodo.org/records/2620293/files/license.md)
limits use to non-commercial research and education and restricts redistribution
of images and derivatives. This repository does not supply the dataset or trained weights.

Final attempt 03 completed all 50 epochs in 1,138.843 seconds (18.98 minutes).
Only this attempt's validation results selected the checkpoint. The maximum
validation mAP50-95 in `results.csv` is at epoch 45 (0.17170). The library's
automatic optimizer selected AdamW, learning rate 0.001111, momentum 0.9;
the complete executed arguments are in `runs/yolov8n_fp32_baseline/args.yaml`.
The first two interrupted attempts below are retained, not combined with this run.

Environment: Windows development host `Chi`, RTX 4060 Laptop GPU (8,188 MiB),
Python 3.11.5, PyTorch 2.6.0+cu124 / CUDA 12.4, Ultralytics headless 8.4.218,
ONNX 1.23.2, ONNX Runtime GPU 1.21.1, onnxslim 0.1.82. AMP and TF32 were disabled.

**Once-only test metrics**, 104 images / 864 class-box reference rows:

| Class | Precision | Recall | AP50 | AP50-95 |
|---|---:|---:|---:|---:|
| crack | 0.40378 | 0.21569 | 0.19316 | 0.07862 |
| spallation | 0.47091 | 0.51295 | 0.39834 | 0.19694 |
| efflorescence | 0.47298 | 0.26804 | 0.27195 | 0.12479 |
| exposed_bar | 0.50087 | 0.57965 | 0.47995 | 0.22449 |
| corrosion_stain | 0.46374 | 0.44304 | 0.39093 | 0.18869 |
| Overall mAP | — | — | **0.34687** | **0.16271** |

Raw source: `runs/yolov8n_fp32_baseline/test_metrics.json` (paths in this
section are relative to `edge_inference/`). These are annotation-relative
Ultralytics PyTorch checkpoint metrics, with candidate confidence 0.001 and
NMS IoU 0.7. P/R use the library's aggregate maximum-F1 confidence operating
point, not the trace's fixed 0.15 floor. No ONNX accuracy-equivalence test or
additional ONNX mAP evaluation was performed. The test set is now exposed;
it must not be reused as independent evidence after future test-informed tuning.

Export: static FP32 ONNX, opset 17, simplification completed and ONNX checker
passed; input `[1,3,640,640]`, output `[1,9,8400]`. Serialized size is
**12,777,171 bytes (12.777171 decimal MB)**. Library fused-model estimate:
3,133,679 parameters / 8.6 GFLOPs; this is an estimate, not measured FLOPs.

**Warm-state stage timings**, milliseconds, from independent processes:

| Stage | CUDA mean | CUDA P95 | CUDA P99 | CPU4 mean | CPU4 P95 | CPU4 P99 |
|---|---:|---:|---:|---:|---:|---:|
| Preprocess | 2.68138 | 2.86698 | 3.05525 | 2.91607 | 3.25159 | 3.32187 |
| Inference | 4.66846 | 5.54693 | 5.67954 | 26.68935 | 28.05311 | 29.52491 |
| Postprocess | 0.29878 | 0.34214 | 0.36435 | 0.30770 | 0.35322 | 0.43945 |
| Total | **7.64862** | **8.50212** | **8.94884** | **29.91312** | **31.43908** | **33.00557** |

| Measurement | CUDA | CPU4 |
|---|---:|---:|
| 1000 / mean total latency (FPS, not pipelined throughput) | 130.74252 | 33.43014 |
| Sampled peak process RSS, decimal MB (not VRAM) | 777.535488 | 154.947584 |

Each profile used 20 warmups then 100 calls on the fixed first alphabetical
validation image `image_0000021.jpg`, 640 letterboxed input, confidence 0.15,
NMS IoU 0.45. CPU ONNX intra-op threads = 4, inter-op threads = 1; OpenCV threads
= 4 in both profiles. This is a thread-constrained development CPU profile, not
a four-core affinity cap or embedded-device emulation guarantee. CUDA TF32 is
disabled. Timings include decoded BGR-to-detection processing and host/device
transfers inside synchronous ONNX calls, but exclude file I/O, image decoding,
encoding and transport. A single repeated validation frame is not a dataset-wide
latency distribution. Stage percentiles do not sum to total percentiles.

Raw timing rows and provider options: `docs/fp32-baseline-gpu.json` and
`docs/fp32-baseline-cpu4.json`. A separate artifact audit recomputed their
mean/P95/P99 and FPS from all 100 retained samples without running the model.

### Test-frame reference trace and visual inspection

`docs/fp32-test-trace.json` contains exactly **104 unique test frames**, 864
reference class-box rows and **806 retained predictions**, with per-frame GPU
stage timings, actual prepared-file payload bytes and hashes, original-pixel
boxes, confidence and class IDs. The first six alphabetical frames have paired
GT/prediction images in `runs/yolov8n_fp32_baseline/qualitative_samples/`.
Visual inspection of `image_0000028.jpg` and `image_0000137.jpg` checked panel
orientation and box placement; the latter has explicit empty background labels.
Overlapping labels on multilabel regions can overlap visually. These panels are
diagnostics, not an additional quantitative evaluation or a best-case selection.

"Cloud reference" names the future simulator role only: all inference ran on
the local development GPU. `edge_profile` remains null; no compressed model,
remote cloud service or network was measured. Reference `complete=false`
explicitly avoids claiming exhaustive negative-label coverage. This partial
trace alone is not a complete edge/cloud offloading comparison.

The final read-only artifact audit passed: unique IDs and exact test membership,
model/manifest/image hashes, payload sizes, coordinate bounds, finite timings,
stage sums, 864 reference rows, and six qualitative images. Its command/output
are `python build/day1_artifact_audit.py` / `build/day1-artifact-audit.txt`.
This verifies artifact consistency, not an independent accuracy scorer.

### Retained evidence hashes (SHA-256)

| Artifact (relative to `edge_inference/`) | SHA-256 |
|---|---|
| `runs/yolov8n_fp32_baseline/weights/best.pt` | `ffd8228000e0c5ca385b58389d212aba7a19a5b14a6a4f4e3b36209005e6f255` |
| `runs/yolov8n_fp32_baseline/training_provenance.json` | `40097880948a8374b9b47b24af455c6987322c250d637d412725c947168b26a7` |
| `runs/yolov8n_fp32_baseline/test_metrics.json` | `880cc8426cbc59b1237f274b505f602686698d2575815ada07e9a5df2c74a067` |
| `weights/yolov8n_fp32_baseline.onnx` | `9ee091bd2a70a5b99ea3f93712d9f6774f02c65d1576f0e444d9b7f31d8fbc3e` |
| `weights/onnx_export.json` | `6eaa4797fbead64da82c8a9ef5aa77cfd0e2af75a2f05a3159f7d44d811337f4` |
| `docs/fp32-baseline-gpu.json` | `0a4145a60ad5c44f6a44a0fba33a237529eadb52ff6a4bec122a9f40d4dacc3d` |
| `docs/fp32-baseline-cpu4.json` | `2bcdd29686157e2e3a0606fdd509c0703fa49846a93fe93729447f22e00e7ff7` |
| `docs/fp32-test-trace.json` | `b5737af3a6ddbafa9e8815e20d096e1dc46d712834fae1b4ec660d1b3d0a68a9` |

### Executed commands and outcomes

Commands below used the project `.venv/Scripts/python.exe`; pytest was run from
each indicated module directory, not from the repository root.

- `python edge_inference/scripts/prepare_codebrim.py --archive edge_inference/data/codebrim_raw/CODEBRIM_original_images.zip --exclude-unannotated`:
  initial extraction failed with a ZIP local-header offset error. The official
  MD5 matched. The compatibility adjustment identified 868 local-header offsets
  displaced by exactly 4 GiB. An initial implementation assumed a newer Python
  `ZipInfo._end_offset` field and failed; that version check was corrected.
  Extraction then succeeded, checking names and CRCs during streaming. The
  archive bytes were never modified. Conversion stopped on ambiguous flags.
- `python edge_inference/scripts/prepare_codebrim.py --exclude-unannotated --exclude-ambiguous`:
  exit 1, deliberately rejected the ten XML/image dimension mismatches after
  fully decoding and hashing all XML-present images. Audit retained.
- `python edge_inference/scripts/prepare_codebrim.py --exclude-unannotated --exclude-ambiguous --exclude-dimension-mismatch`:
  **exit 0**, admitted 1,040 images, generated 832 / 104 / 104 split and manifest.
  This command was repeated after adding pixel-preserving JPEG tail normalization;
  split membership and all class counts stayed identical.
- `python -u edge_inference/scripts/train_baseline.py train` attempt 01:
  intentionally interrupted in epoch 1 after the loader reported automatic JPEG
  rewrites. No completed epoch/checkpoint was accepted or used for selection.
  Preserved `edge_inference/runs/yolov8n_fp32_baseline_attempt01/`,
  `edge_inference/data/codebrim_yolo_attempt01/`, and
  `build/day1-training-console.txt`. Initial manifest SHA-256 was
  `fd7b3d96c0ffa3a18a5c33fe81960f21213e3429bd1fbd52f394fd3df6ff17f6`.
  Raw source images were unchanged. The replacement run uses the same training
  seed/configuration from scratch, with a post-loader hash guard.
- Attempt 02 was interrupted during epoch 14 after the additional EXIF audit
  found a coordinate-system mismatch missed by the initial header-size check.
  Its validation scores/checkpoints are not used for selection or claimed as
  results. Preserved `edge_inference/runs/yolov8n_fp32_baseline_attempt02/`,
  `edge_inference/data/codebrim_yolo_attempt02/`, and
  `build/day1-training-attempt02-console.txt`. Attempt 02 manifest SHA-256:
  `9f50c26c7270a3c7bb61d47096c8f4e57b7ced1938ecf7a9fd775f3dcb2f7777`.
  The final run restarts from the original pretrained model with unchanged
  seed, sample membership, labels and hyperparameters after metadata normalization.
- `python -u edge_inference/scripts/train_baseline.py train` attempt 03:
  **exit 0**, 50 epochs; console `build/day1-training-attempt03-console.txt`.
- `python -u edge_inference/scripts/train_baseline.py evaluate`: **exit 0**;
  console `build/day1-test-evaluation-console.txt`. Transient font-download TLS
  retries did not prevent completion; no second test evaluation was launched.
- `python -u edge_inference/scripts/train_baseline.py export`: **exit 0**;
  console `build/day1-onnx-export-console.txt`.
- `python -u edge_inference/scripts/export_fp32_trace.py gpu`: **exit 0**;
  console `build/day1-profile-gpu-console.txt`.
- `python -u edge_inference/scripts/export_fp32_trace.py cpu4`: **exit 0**;
  console `build/day1-profile-cpu4-console.txt`.
- `python -u edge_inference/scripts/export_fp32_trace.py trace`: **exit 0**;
  console `build/day1-test-trace-console.txt`.
- `python build/day1_artifact_audit.py`: **exit 0**; audit described above.
- From `edge_inference`: `python -m pytest tests -q`: **94 passed**.
- From `01_simulation/b0`: `python -m pytest -q`: **25 passed**.
- From `02_estimation/b0`: `python -m pytest -q`: **52 passed**.
- From `05_integration/b0`: `python -m pytest -q`: **165 passed**.
- `python -m pip check`: **No broken requirements found** after restoring
  `sympy==1.13.1` and installing `onnxslim==0.1.82`. The attempted latest
  onnxslim install and an overlapping corrective install failed; both ended
  before the successful serial reinstall. No training used that transient state.
- Official `ultralytics/assets` release v8.4.0 pretrained `yolov8n.pt` was
  downloaded after transient TLS failures, 6,549,796 bytes, SHA-256
  `f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36`.

## Failure analysis and insights

Missing XML, an explicit background label, and an all-zero flag vector are
different conditions. A valid XML document also does not prove agreement with
its JPEG dimensions. Admission must follow all these checks, before training.
Owner approved all three exclusion classes before training. These exclusions
are quality checks, not performance-driven data selection.

The intended FP32 pipeline disables AMP and TF32. Ultralytics serializes EMA
checkpoints in FP16 before reloading for FP32 evaluation/export; this is disclosed
rather than described as lossless FP32 checkpoint storage. The ONNX trace decoder
uses single-best-class anchors and per-class NMS at confidence .15 / IoU .45;
its predictions are not identical by definition to Ultralytics' metric decoder.
RSS is sampled between calls and is not an instantaneous memory peak or VRAM.

The baseline has limited accuracy, particularly crack recall (0.21569) and AP50-95
(0.07862). It is a starting measurement, not an accepted inspection system.
Multilabel regions were expanded into class-box rows while the custom ONNX
decoder keeps one best class per anchor, so decoder semantics must remain
explicit in downstream comparisons. No thresholds or hyperparameters were
changed using these test results. No pruning or INT8 experiment was performed.

## Reusable assets

- `scripts/prepare_codebrim.py`: fail-closed XML/image audit, explicit exclusions,
  deterministic grouping and split manifest, official-archive extraction.
- `scripts/train_baseline.py`: separate training, once-only test evaluation,
  checked static FP32 ONNX export.
- `scripts/export_fp32_trace.py`: independent GPU/CPU4 processes, raw timing
  samples, per-test-frame payloads and offline references, qualitative panels.
- `tests/test_prepare_codebrim.py`, `tests/test_day1_exports.py`: synthetic checks.

Official sources checked: [CODEBRIM archive and checksum](https://zenodo.org/records/2620293),
[ONNX Runtime CUDA TF32 control](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html#use_tf32).
No dataset images or generated models are included in Git.
