"""Read-only final artifact audit; no model execution or metric rescoring."""
import hashlib
import json
import math
from pathlib import Path
import statistics

root = Path(__file__).resolve().parents[1]
edge = root / 'edge_inference'
def sha(path):
    return hashlib.file_digest(Path(path).open('rb'), 'sha256').hexdigest()
def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))
manifest_path = edge / 'data/codebrim_yolo/split_manifest.json'
manifest = read(manifest_path)
assert [manifest['splits'][s]['image_count'] for s in ('train','val','test')] == [832,104,104]
assert [len(manifest[k]) for k in ('excluded_missing_xml','excluded_ambiguous_xml','excluded_dimension_mismatch')] == [538,2,10]
model = edge / 'weights/yolov8n_fp32_baseline.onnx'
export = read(edge / 'weights/onnx_export.json')
assert sha(model) == export['model_sha256']
assert sha(manifest_path) == export['split_manifest_sha256']
for mode in ('gpu','cpu4'):
    path = edge / f'docs/fp32-baseline-{mode}.json'
    record = read(path)
    assert sha(path) == read(path.with_name(path.stem+'-sha256.json'))['sha256']
    assert record['model_sha256'] == sha(model)
    assert len(record['samples_ms']) == record['runs'] == 100
    for stage in ('preprocess','inference','postprocess','total'):
        values = sorted(row[stage] for row in record['samples_ms'])
        assert all(math.isfinite(v) and v >= 0 for v in values)
        summary = record['summary_ms'][stage]
        assert math.isclose(statistics.mean(values),summary['mean'],abs_tol=1e-12)
        for q in (95,99):
            pos = (len(values)-1)*q/100
            low = math.floor(pos)
            value = values[low]+(pos-low)*(values[math.ceil(pos)]-values[low])
            assert math.isclose(value,summary[f'p{q}'],abs_tol=1e-12)
    assert math.isclose(record['fps'],1000/record['summary_ms']['total']['mean'])
    print(mode, '100 raw samples: mean/P95/P99/FPS independently recomputed')
path = edge / 'docs/fp32-test-trace.json'
trace = read(path)
assert sha(path) == read(path.with_name(path.stem+'-sha256.json'))['sha256']
assert trace['provenance']['model_sha256'] == sha(model)
assert trace['provenance']['split_manifest_sha256'] == sha(manifest_path)
ids = {Path(n).stem for n in manifest['splits']['test']['files']}
assert len(trace['frames']) == trace['sample_count'] == len(ids) == 104
assert {f['frame_id'] for f in trace['frames']} == ids
assert set(trace['cloud_predictions']) == set(trace['ground_truth']) == set(trace['cloud_timings']) == ids
pred_count = truth_count = 0
for frame in trace['frames']:
    key = frame['frame_id']
    name = key+'.jpg'
    image = edge / 'data/codebrim_yolo/images/test' / name
    assert frame['payload_bytes'] == image.stat().st_size
    assert frame['image_sha256'] == sha(image) == manifest['images'][name]['image_sha256']
    assert (frame['width'],frame['height']) == (manifest['images'][name]['width'],manifest['images'][name]['height'])
    truth = trace['ground_truth'][key]
    predictions = trace['cloud_predictions'][key]
    assert truth['complete'] is False
    truth_count += len(truth['boxes'])
    pred_count += len(predictions)
    for box in truth['boxes']+predictions:
        x1,y1,x2,y2 = box['bbox']
        assert all(math.isfinite(v) for v in box['bbox'])
        assert 0 <= x1 < x2 <= frame['width'] and 0 <= y1 < y2 <= frame['height']
        assert box['class_id'] in manifest['classes']
        if 'confidence' in box:
            assert .15 <= box['confidence'] <= 1
    times = trace['cloud_timings'][key]
    assert times['sample_id'] == key
    assert all(math.isfinite(times[k]) and times[k]>=0 for k in ('preprocess','inference','postprocess','total'))
    assert math.isclose(sum(times[k] for k in ('preprocess','inference','postprocess')),times['total'],abs_tol=1e-9)
assert truth_count == 864
assert len(list((edge / 'runs/yolov8n_fp32_baseline/qualitative_samples').glob('*.jpg'))) == 6
print(f'trace: 104 unique frames, {truth_count} reference rows, {pred_count} predictions; geometry/payload/hash/timing checks passed; 6 panels')
for name in ('split_manifest.json',):
    print(name, sha(manifest_path))
for path in (edge / 'runs/yolov8n_fp32_baseline/test_metrics.json',edge / 'weights/onnx_export.json',edge / 'runs/yolov8n_fp32_baseline/training_provenance.json'):
    print(path.relative_to(root),sha(path))
