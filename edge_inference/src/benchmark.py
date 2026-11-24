"""Development-host timing runner; synthetic-only mode does not measure a model."""
import argparse
import hashlib
import json
import os
import platform
import time
from pathlib import Path
import numpy as np
import psutil
from .detector import EdgeDefectDetector


class SyntheticDetector:
    def infer(self, frame):
        t0 = time.perf_counter_ns()
        prepared = frame.astype(np.float32) / 255
        t1 = time.perf_counter_ns()
        value = float(prepared.mean())
        t2 = time.perf_counter_ns()
        detections = [{'synthetic_mean': value}]
        t3 = time.perf_counter_ns()
        return {'detections': detections, 'timings_ms': {'preprocess': (t1-t0)/1e6, 'inference': (t2-t1)/1e6, 'postprocess': (t3-t2)/1e6, 'total': (t3-t0)/1e6}}


def run(detector, frame, warmup, runs):
    if warmup < 0 or runs < 1:
        raise ValueError('warmup >= 0 and runs >= 1 required')
    process = psutil.Process(os.getpid())
    for _ in range(warmup):
        detector.infer(frame)
    rss = process.memory_info().rss
    rows = []
    for _ in range(runs):
        rows.append(detector.infer(frame)['timings_ms'])
        rss = max(rss, process.memory_info().rss)
    summary = {}
    for key in ('preprocess', 'inference', 'postprocess', 'total'):
        values = np.array([row[key] for row in rows], dtype=float)
        if not np.isfinite(values).all() or np.any(values < 0):
            raise ValueError('timing must be finite and nonnegative')
        summary[key] = {'mean': float(values.mean()), 'p95': float(np.percentile(values, 95)), 'p99': float(np.percentile(values, 99))}
    total = summary['total']['mean']
    return {'samples_ms': rows, 'summary_ms': summary, 'fps': 1000 / total if total else None, 'sampled_peak_rss_bytes': rss}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--synthetic', action='store_true', help='use synthetic frames; without --model use dummy workload')
    parser.add_argument('--model', type=Path)
    parser.add_argument('--provider', choices=('cpu', 'cuda'), default='cpu')
    parser.add_argument('--threads', type=int, default=4)
    parser.add_argument('--warmup', type=int, default=20)
    parser.add_argument('--runs', type=int, default=100)
    parser.add_argument('--output', type=Path, default=Path('docs/edge-benchmark.json'))
    args = parser.parse_args(argv)
    if not args.synthetic:
        parser.error('only --synthetic input is supported; no dataset is accessed')
    if args.threads < 1:
        parser.error('--threads must be positive')
    if args.model:
        if not args.model.is_file():
            parser.error('model file does not exist')
        detector = EdgeDefectDetector(args.model, args.provider, args.threads)
        model = {'path': str(args.model.resolve()), 'size_bytes': args.model.stat().st_size, 'sha256': hashlib.sha256(args.model.read_bytes()).hexdigest()}
    else:
        detector, model = SyntheticDetector(), None
    frame = np.random.default_rng(0).integers(0, 256, (640, 640, 3), dtype=np.uint8)
    result = run(detector, frame, args.warmup, args.runs)
    result.update({'host_type': 'development-host', 'host': platform.node(), 'platform': platform.platform(), 'input': 'synthetic_seed_0', 'workload': 'onnx_model' if model else 'dummy_not_model', 'model': model, 'provider': args.provider if model else None, 'threads': args.threads if model else None, 'warmup': args.warmup, 'runs': args.runs, 'rss_note': 'RSS sampled between calls, not guaranteed instantaneous peak', 'fps_note': '1000 / mean end-to-end latency; not pipelined throughput', 'accuracy': None})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(f'Wrote {args.output}; workload={result["workload"]}; host=development-host')


if __name__ == '__main__':
    main()
