# Development-host run records · 24 November 2026

These are the 18 files originally retained in the local checkout's `build/` directory. The [SHA-256 manifest](SHA256SUMS.txt) covers their original bytes, including console escape sequences and line endings. Paths printed by the tools identify the original checkout; they are not download links.

| What to review | Records |
| --- | --- |
| FP32 training | [Attempt 01](records/day1-training-console.txt) was interrupted after the loader rewrote JPEGs. [Attempt 02](records/day1-training-attempt02-console.txt) was interrupted after an EXIF coordinate mismatch was found. [Attempt 03](records/day1-training-attempt03-console.txt) is the completed 50-epoch run. The [Day 1 log](../../2026-11-24_day1_yolov8n_fp32_baseline.md) explains the interruption decisions; the first two attempts were not used for model selection. |
| Evaluation and FP32 export | [Test evaluation](records/day1-test-evaluation-console.txt) and [ONNX export](records/day1-onnx-export-console.txt). The [CPU4](records/day1-profile-cpu4-console.txt), [GPU](records/day1-profile-gpu-console.txt) and [trace](records/day1-test-trace-console.txt) receipts contain paths and hashes, **not** the underlying timing samples or predictions. |
| Compression | [Recovery training](records/day23-recovery.log), [pruned-model export](records/day23-export.log), [baseline PTQ](records/day23-base-ptq.log) and [pruned PTQ](records/day23-pruned-ptq.log). See the [Day 2–3 log](../../2026-11-24_day2_3_pruning_int8_compression.md) for the commands and interpretation. |
| Recorded environment | [Package snapshot](records/edge-environment-freeze.txt), [CUDA/ONNX smoke check](records/edge-environment-smoke.py) and [its actual output](records/edge-environment-smoke.log). Local wheel URLs describe that installation, not a portable install recipe. |
| Derived checks | [Day 1 audit script](records/day1_artifact_audit.py), [its output](records/day1-artifact-audit.txt) and the [four-variant summary](records/day23-summary.jsonl). These are checks and summaries, not new measurements. |

**Verify without a GPU or dataset.** From a checkout, run in Bash:

```bash
cd edge_inference/logs/evidence/2026-11-24
sha256sum -c SHA256SUMS.txt
```

All 18 entries must report `OK`. This verifies the published files against the manifest. It does not rerun training or prove the scoring logic correct. To audit the historical command lines, read the consoles directly.

To execute the archived Day 1 audit, use a separate reproduction checkout with the original local inputs and its historical script path, `build/day1_artifact_audit.py`. The script resolves the repo relative to its own location; do not use that historical layout for new EDGE runs. Images, weights, per-call timing JSONs and prediction traces are not included in this evidence set. Descriptive scores remain annotation-relative (`complete=false`); these are development-host records, not flight results.
