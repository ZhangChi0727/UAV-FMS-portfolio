"""Development-host FP32 ONNX profiles and frame-associated cloud-reference trace.

Run gpu, cpu4, and trace in separate processes so CPU RSS excludes a live GPU
session. Test labels are read only after prediction, for offline export/display.
This is only the GPU-reference half of a future offload simulator input.
"""
import argparse
import importlib.metadata
import json
from pathlib import Path
import platform
import sys

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.benchmark import load_config, run
from src.detector import EdgeDefectDetector
if __package__:
    from .prepare_codebrim import CLASSES, EDGE, digest, write_json
else:
    from prepare_codebrim import CLASSES, EDGE, digest, write_json

DATA = EDGE / 'data/codebrim_yolo'
MODEL = EDGE / 'weights/yolov8n_fp32_baseline.onnx'
RUN = EDGE / 'runs/yolov8n_fp32_baseline'


def ground_truth(path, width, height):
    boxes = []
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        c, x, y, w, h = map(float, line.split())
        if c != int(c) or not 0 <= c < len(CLASSES) or not all(0 <= v <= 1 for v in (x,y,w,h)):
            raise ValueError('invalid ground truth row')
        boxes.append({'class_id': CLASSES[int(c)],
                      'bbox': [max(0., (x-w/2)*width), max(0., (y-h/2)*height),
                               min(float(width), (x+w/2)*width), min(float(height), (y+h/2)*height)]})
    return boxes


def qualitative(frame, truth, predictions, target):
    panels = []
    for heading, boxes, color in [('XML ground truth', truth, (0,180,0)),
                                  ('FP32 predictions >= 0.15', predictions, (0,100,255))]:
        scale = min(640/frame.shape[1], 640/frame.shape[0])
        canvas = cv2.resize(frame, None, fx=scale, fy=scale)
        canvas = cv2.copyMakeBorder(canvas, 30, 0, 0, 0, cv2.BORDER_CONSTANT)
        cv2.putText(canvas, heading, (8,22), cv2.FONT_HERSHEY_SIMPLEX, .5, (255,255,255), 1)
        for b in boxes:
            x1,y1,x2,y2 = (round(v*scale) for v in b['bbox'])
            cv2.rectangle(canvas, (x1,y1+30), (x2,y2+30), color, 1)
            title = b['class_id'] + (f" {b['confidence']:.2f}" if 'confidence' in b else '')
            cv2.putText(canvas, title, (x1,max(42,y1+28)), cv2.FONT_HERSHEY_SIMPLEX, .35, color, 1)
        panels.append(canvas)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(target), np.hstack(panels)):
        raise OSError('qualitative image write failed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('gpu', 'cpu4', 'trace'))
    args = parser.parse_args()
    out = EDGE / 'docs' / ('fp32-test-trace.json' if args.stage == 'trace' else f'fp32-baseline-{args.stage}.json')
    if out.exists():
        raise FileExistsError(out)
    manifest = json.loads((DATA / 'split_manifest.json').read_text(encoding='utf-8'))
    config = load_config(EDGE / 'configs/baseline.yaml')
    if [config[k] for k in ('imgsz','warmup_runs','benchmark_runs','cpu_threads')] != [640,20,100,4]:
        raise ValueError('Day 1 benchmark configuration changed')
    export = json.loads((EDGE / 'weights/onnx_export.json').read_text(encoding='utf-8'))
    if digest(MODEL) != export['model_sha256'] or digest(DATA / 'split_manifest.json') != export['split_manifest_sha256']:
        raise ValueError('model or dataset differs from export provenance')
    if tuple(manifest['classes']) != CLASSES:
        raise ValueError('class map mismatch')
    provider = 'cpu' if args.stage == 'cpu4' else 'cuda'
    cv2.setNumThreads(4)
    detector = EdgeDefectDetector(MODEL, provider=provider, threads=4, confidence=.15, iou=.45)
    provenance = {'host_type': 'development-host', 'host': platform.node(),
        'platform': platform.platform(), 'precision': 'FP32', 'backend': 'ONNX Runtime',
        'cpu': platform.processor(), 'gpu': export['gpu'],
        'onnx_export_provenance_sha256': digest(EDGE / 'weights/onnx_export.json'),
        'onnxruntime': importlib.metadata.version('onnxruntime-gpu'), 'provider': provider,
        'selected_providers': detector.session.get_providers(),
        'provider_options': detector.session.get_provider_options(),
        'threads': 4, 'cpu_inter_op_threads': 1 if provider == 'cpu' else None,
        'opencv_threads': cv2.getNumThreads(),
        'command': sys.argv, 'script_sha256': digest(__file__),
        'detector_sha256': digest(EDGE / 'src/detector.py'), 'model_sha256': digest(MODEL),
        'model_size_bytes': MODEL.stat().st_size,
        'config_sha256': digest(EDGE / 'configs/baseline.yaml'),
        'split_manifest_sha256': digest(DATA / 'split_manifest.json'),
        'nms_iou': .45, 'gate_retention_floor': .15, 'imgsz': 640,
        'decoding': 'single best class per anchor; per-class NMS (not the Ultralytics validation decoder)',
        'coordinate_convention': 'zero-based half-open original-image pixels',
        'timing_scope': 'Decoded BGR input to detections; file I/O, image decoding/encoding and transport excluded',
        'limits': 'Local development-host only; no cloud-service, onboard, network or flight measurement. Image-disjoint, not bridge-disjoint.'}
    def read_image(name, split):
        path = DATA / 'images' / split / name
        if digest(path) != manifest['images'][name]['image_sha256']:
            raise ValueError('image hash mismatch')
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError(f'cannot decode {path}')
        return image
    # A fixed validation image benchmarks compute without choosing from test results.
    benchmark_name = manifest['splits']['val']['files'][0]
    frame = read_image(benchmark_name, 'val')
    if args.stage != 'trace':
        result = run(detector, frame, warmup=20, runs=100)
        write_json(out, {**provenance, **result, 'warmup': 20, 'runs': 100,
            'input_frame': benchmark_name, 'input_split': 'val',
            'rss_note': 'Process RSS sampled between calls, not instantaneous peak; excludes GPU VRAM',
            'sampled_peak_rss_MB': result['sampled_peak_rss_bytes'] / 1e6})
    else:
        for _ in range(20):
            detector.infer(frame)
        frames, predictions, truth, timings = [], {}, {}, {}
        for index, name in enumerate(manifest['splits']['test']['files']):
            image = read_image(name, 'test')
            h,w = image.shape[:2]
            result = detector.infer(image)
            frame_id = Path(name).stem
            predictions[frame_id] = [{'bbox': d['xyxy'], 'class_id': CLASSES[d['class_id']],
                                     'confidence': d['confidence']} for d in result['detections']]
            label = DATA / 'labels/test' / (frame_id + '.txt')
            if digest(label) != manifest['images'][name]['label_sha256']:
                raise ValueError('label hash mismatch')
            boxes = ground_truth(label, w, h)
            truth[frame_id] = {'width': w, 'height': h, 'boxes': boxes,
                'complete': False, 'coverage_note': 'Supplied XML annotations; exhaustive full-image negative coverage not verified',
                'xml_sha256': manifest['images'][name]['xml_sha256']}
            frames.append({'frame_id': frame_id, 'width': w, 'height': h,
                'payload_bytes': (DATA / 'images/test' / name).stat().st_size,
                'encoded_format': manifest['images'][name]['encoded_format'],
                'payload_note': 'Exact prepared file bytes; MPO includes secondary JPEG views, while inference uses the first decoded view',
                'image_sha256': manifest['images'][name]['image_sha256']})
            timings[frame_id] = {**result['timings_ms'], 'sample_id': frame_id}
            if index < 6:
                qualitative(image, boxes, predictions[frame_id], RUN / 'qualitative_samples' / f'{frame_id}.jpg')
        write_json(out, {'trace_kind': 'development_host_trace', 'provenance': provenance,
            'classes': CLASSES, 'gate_retention_floor': .15, 'warmup': 20,
            'warmup_frame': benchmark_name, 'sample_count': len(frames),
            'frames': frames, 'cloud_predictions': predictions, 'ground_truth': truth,
            'cloud_timings': timings, 'edge_profile': None,
            'note': 'GPU-reference partial trace only; no compressed edge profile supplied. Full-coverage accuracy is not asserted.'})
    write_json(out.with_name(out.stem + '-sha256.json'), {'file': out.name, 'sha256': digest(out)})
    print(f'{out}: {digest(out)}')


if __name__ == '__main__':
    main()
