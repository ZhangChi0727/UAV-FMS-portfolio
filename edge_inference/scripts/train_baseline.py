"""Opt-in Day 1 FP32 training, once-only heldout evaluation, and ONNX export.

Run each stage explicitly. Existing run/evaluation artifacts are never replaced.
The test set must not be used for model selection or tuning after this run.
"""
import argparse
import hashlib
import importlib.metadata
from pathlib import Path
import platform
import shutil
import sys
import time

if __package__:
    from .build_paths import configure_ultralytics
    from .prepare_codebrim import CLASSES, EDGE, digest, write_json
else:
    from build_paths import configure_ultralytics
    from prepare_codebrim import CLASSES, EDGE, digest, write_json

RUN = EDGE / 'runs/yolov8n_fp32_baseline'
DATA = EDGE / 'data/codebrim_yolo'
WEIGHTS = EDGE / 'weights'


def verify_dataset(data):
    import json
    from PIL import Image
    manifest = json.loads((data / 'split_manifest.json').read_text(encoding='utf-8'))
    if tuple(manifest['classes']) != CLASSES:
        raise ValueError('class order mismatch')
    if digest(data / 'dataset.yaml') != manifest['dataset_yaml_sha256']:
        raise ValueError('dataset.yaml changed')
    seen = set()
    for split in ('train', 'val', 'test'):
        entry = manifest['splits'][split]
        names = entry['files']
        if len(names) != entry['image_count'] or len(set(names)) != len(names) or seen.intersection(names):
            raise ValueError('duplicate or inconsistent split membership')
        if hashlib.sha256(('\n'.join(names)+'\n').encode()).hexdigest() != entry['file_list_sha256']:
            raise ValueError('split file-list hash changed')
        if set(p.name for p in (data / 'images' / split).glob('*.jpg')) != set(names):
            raise ValueError('image directory differs from manifest')
        if set(p.stem for p in (data / 'labels' / split).glob('*.txt')) != {Path(n).stem for n in names}:
            raise ValueError('label directory differs from manifest')
        for name in names:
            if manifest['images'][name]['split'] != split:
                raise ValueError('per-image split mismatch')
        seen.update(names)
    if seen != set(manifest['images']):
        raise ValueError('unassigned manifest images')
    for name, record in manifest['images'].items():
        split = record['split']
        with Image.open(data / 'images' / split / name) as image:
            if image.size != (record['width'],record['height']) or image.getexif().get(274,1) != 1:
                raise ValueError(f'decoder/XML coordinate mismatch: {name}')
        for path, expected in ((data / 'images' / split / name, record['image_sha256']),
                (data / 'labels' / split / (Path(name).stem + '.txt'), record['label_sha256'])):
            if digest(path) != expected:
                raise ValueError(f'dataset content changed: {path}')
    return digest(data / 'split_manifest.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=('train', 'evaluate', 'export'))
    args = parser.parse_args()
    configure_ultralytics()
    import torch
    from ultralytics import YOLO
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA required; do not silently substitute CPU')
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    provenance = {'host_type': 'development-host', 'host': platform.node(),
        'python': sys.version, 'torch': torch.__version__, 'cuda': torch.version.cuda,
        'gpu': torch.cuda.get_device_name(0), 'command': sys.argv,
        'ultralytics': importlib.metadata.version('ultralytics-opencv-headless'),
        'precision': 'FP32; amp=False, half=False, TF32 disabled',
        'checkpoint_note': 'Ultralytics serializes EMA checkpoints in FP16; evaluation/export reloads to FP32. This is not a lossless FP32 checkpoint claim.',
        'script_sha256': digest(__file__), 'split_manifest_sha256': verify_dataset(DATA)}
    import json
    manifest = json.loads((DATA / 'split_manifest.json').read_text(encoding='utf-8'))
    if [manifest['splits'][s]['image_count'] for s in ('train','val','test')] != [832,104,104]:
        raise ValueError('Day 1 requires exact approved 832/104/104 split')
    if [len(manifest[k]) for k in ('excluded_missing_xml','excluded_ambiguous_xml','excluded_dimension_mismatch')] != [538,2,10]:
        raise ValueError('Day 1 exclusion counts changed')
    WEIGHTS.mkdir(parents=True, exist_ok=True)
    if args.stage == 'train':
        if RUN.exists():
            raise FileExistsError('run exists; retain it, do not silently resume or overwrite')
        model = YOLO(str(WEIGHTS / 'yolov8n.pt'))
        def verify_after_loader_setup(trainer):
            if verify_dataset(DATA) != provenance['split_manifest_sha256']:
                raise ValueError('manifest changed during loader setup')
        model.add_callback('on_pretrain_routine_end', verify_after_loader_setup)
        provenance['pretrained_sha256'] = digest(WEIGHTS / 'yolov8n.pt')
        write_json(EDGE / 'runs/day1_training_launch.json', provenance)
        start = time.time()
        model.train(data=str(DATA / 'dataset.yaml'), imgsz=640, batch=16,
                    epochs=50, patience=15, seed=42, workers=4, device=0,
                    amp=False, half=False, deterministic=True, cache=False,
                    project=str(RUN.parent), name=RUN.name, exist_ok=False)
        provenance['elapsed_seconds'] = time.time() - start
        provenance['best_sha256'] = digest(RUN / 'weights/best.pt')
        write_json(RUN / 'training_provenance.json', provenance)
    elif args.stage == 'evaluate':
        marker = RUN / 'test_evaluation_started.json'
        if marker.exists():
            raise FileExistsError('test evaluation already attempted; do not consume test again')
        provenance['best_sha256'] = digest(RUN / 'weights/best.pt')
        write_json(marker, provenance)
        result = YOLO(str(RUN / 'weights/best.pt')).val(
            data=str(DATA / 'dataset.yaml'), split='test', imgsz=640, batch=16,
            device=0, half=False, workers=4, conf=.001, iou=.7,
            project=str(RUN), name='heldout_test', exist_ok=False)
        per_class = {name: {'ap50': None, 'ap50_95': None, 'precision': None,
                            'recall': None, 'note': 'no reference instances'} for name in CLASSES}
        for index, class_id in enumerate(result.box.ap_class_index):
            p, r, ap50, ap = result.box.class_result(index)
            per_class[CLASSES[int(class_id)]] = dict(zip(
                ('precision', 'recall', 'ap50', 'ap50_95'), map(float, (p, r, ap50, ap))))
        write_json(RUN / 'test_metrics.json', {**provenance,
            'overall': {'map50': float(result.box.map50), 'map50_95': float(result.box.map)},
            'per_class': per_class, 'metric_implementation': 'Ultralytics DetectionValidator',
            'precision_recall_note': 'Ultralytics aggregate maximum-F1 confidence operating point, not trace confidence .15',
            'nms_iou': .7, 'candidate_confidence': .001})
    else:
        target = WEIGHTS / 'yolov8n_fp32_baseline.onnx'
        if target.exists():
            raise FileExistsError(target)
        import onnxslim
        original_slim = onnxslim.slim
        simplified = []
        def checked_slim(*a, **kw):
            result = original_slim(*a, **kw)
            simplified.append(True)
            return result
        # Ultralytics catches simplifier errors; refuse to certify such an export.
        onnxslim.slim = checked_slim
        try:
            exported = Path(YOLO(str(RUN / 'weights/best.pt')).export(
                format='onnx', imgsz=640, batch=1, opset=17, simplify=True,
                dynamic=False, half=False, device=0, nms=False))
        finally:
            onnxslim.slim = original_slim
        if not simplified:
            raise RuntimeError('ONNX simplifier did not complete successfully')
        import onnx
        graph = onnx.load(str(exported))
        onnx.checker.check_model(graph)
        shape = [d.dim_value for d in graph.graph.input[0].type.tensor_type.shape.dim]
        if shape != [1, 3, 640, 640]:
            raise ValueError(f'unexpected export shape {shape}')
        if graph.graph.input[0].type.tensor_type.elem_type != onnx.TensorProto.FLOAT:
            raise ValueError('ONNX input is not FP32')
        if any(t.data_type == onnx.TensorProto.FLOAT16 for t in graph.graph.initializer):
            raise ValueError('ONNX contains FP16 initializer')
        if not any(x.domain in ('', 'ai.onnx') and x.version == 17 for x in graph.opset_import):
            raise ValueError('ONNX opset is not 17')
        shutil.copy2(exported, target)
        write_json(WEIGHTS / 'onnx_export.json', {**provenance,
            'best_sha256': digest(RUN / 'weights/best.pt'), 'model_sha256': digest(target),
            'size_bytes': target.stat().st_size, 'size_MB': target.stat().st_size / 1e6,
            'input_shape': shape, 'opset': 17, 'simplify': True, 'model': str(target)})


if __name__ == '__main__':
    main()
