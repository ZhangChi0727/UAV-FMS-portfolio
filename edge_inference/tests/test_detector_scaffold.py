import json
import sys
from pathlib import Path
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.detector import EdgeDefectDetector, letterbox_tensor
from src.benchmark import EDGE_ROOT, SyntheticDetector, load_config, main, run


def test_invalid_frame_rejected():
    detector = EdgeDefectDetector.__new__(EdgeDefectDetector)
    with pytest.raises(ValueError):
        detector.infer(np.zeros((4, 4), dtype=np.uint8))


def test_synthetic_samples_and_boundaries():
    result = run(SyntheticDetector(), np.zeros((4, 4, 3), dtype=np.uint8), 1, 3)
    assert len(result['samples_ms']) == 3
    assert result['summary_ms']['total']['p99'] >= 0
    with pytest.raises(ValueError):
        run(SyntheticDetector(), np.zeros((4, 4, 3), dtype=np.uint8), 0, 0)


def test_cli_records_synthetic_not_model(tmp_path):
    out = tmp_path / 'report.json'
    main(['--synthetic', '--warmup', '0', '--runs', '2', '--output', str(out)])
    report = json.loads(out.read_text(encoding='utf-8'))
    assert report['host_type'] == 'development-host'
    assert report['workload'] == 'dummy_not_model' and report['model'] is None
    assert len(report['samples_ms']) == 2


def test_baseline_config():
    config = load_config(EDGE_ROOT / 'configs/baseline.yaml')
    assert [config[k] for k in ('imgsz', 'warmup_runs', 'benchmark_runs', 'cpu_threads')] == [640, 20, 100, 4]


def test_config_overrides_and_working_directory(tmp_path, monkeypatch):
    config = tmp_path / 'custom.yaml'
    config.write_text('imgsz: 16\nwarmup_runs: 0\nbenchmark_runs: 3\ncpu_threads: 2\n')
    out = tmp_path / 'out.json'
    monkeypatch.chdir(tmp_path)
    main(['--synthetic', '--config', str(config), '--output', str(out)])
    report = json.loads(out.read_text())
    assert (report['imgsz'], report['runs'], report['warmup']) == (16, 3, 0)
    main(['--synthetic', '--config', str(config), '--imgsz', '8', '--runs', '1', '--output', str(out)])
    assert json.loads(out.read_text())['imgsz'] == 8
    main(['--synthetic', '--runs', '1', '--warmup', '0', '--output', str(out)])
    assert json.loads(out.read_text())['imgsz'] == 640


@pytest.mark.parametrize('value', ['true', '0', '-1', '1.5'])
def test_invalid_config(tmp_path, value):
    config = tmp_path / 'bad.yaml'
    config.write_text(f'imgsz: {value}\nwarmup_runs: 0\nbenchmark_runs: 1\ncpu_threads: 1\n')
    with pytest.raises(ValueError):
        load_config(config)


def test_cpu_thread_options(monkeypatch):
    from types import SimpleNamespace
    captured = {}
    def session(model, sess_options, providers):
        captured['options'] = sess_options
        return SimpleNamespace(get_providers=lambda: providers,
                               get_inputs=lambda: [SimpleNamespace(type='tensor(float)')])
    monkeypatch.setitem(sys.modules, 'onnxruntime', SimpleNamespace(
        get_available_providers=lambda: ['CPUExecutionProvider'],
        SessionOptions=SimpleNamespace, InferenceSession=session))
    EdgeDefectDetector('unused.onnx', threads=3)
    assert captured['options'].intra_op_num_threads == 3
    assert captured['options'].inter_op_num_threads == 1


def test_cuda_fp32_disables_tf32(monkeypatch):
    from types import SimpleNamespace
    captured = {}
    def session(model, sess_options, providers):
        captured['providers'] = providers
        return SimpleNamespace(get_providers=lambda: ['CUDAExecutionProvider'],
                               get_inputs=lambda: [SimpleNamespace(type='tensor(float)')])
    monkeypatch.setitem(sys.modules, 'onnxruntime', SimpleNamespace(
        preload_dlls=lambda: None, get_available_providers=lambda: ['CUDAExecutionProvider'],
        SessionOptions=SimpleNamespace, InferenceSession=session))
    EdgeDefectDetector('unused.onnx', provider='cuda')
    assert captured['providers'] == [('CUDAExecutionProvider', {'use_tf32': 0})]


def raw_head_detector(raw, confidence=.25):
    from types import SimpleNamespace
    detector = EdgeDefectDetector.__new__(EdgeDefectDetector)
    detector.backend = 'onnx'
    detector.confidence, detector.iou = confidence, .45
    detector.input = SimpleNamespace(shape=[1,3,8,8], name='images')
    detector.session = SimpleNamespace(run=lambda *a: [raw])
    return detector


def test_onnx_retains_score_at_gate_floor():
    raw = np.zeros((1, 5, 10), dtype=np.float32)
    raw[0, :, 0] = [4,4,4,4,.15]
    detector = raw_head_detector(raw, confidence=float(np.float32(.15)))
    result = detector.infer(np.zeros((8,8,3), dtype=np.uint8))
    assert len(result['detections']) == 1
    assert result['detections'][0]['confidence'] == detector.confidence


@pytest.mark.parametrize('hw,offset', [((2, 4), (0, 1)), ((4, 2), (1, 0))])
def test_letterbox_padding_and_rgb_planes(hw, offset):
    # 4x2 -> 6x3 (or transpose); odd spare pixels belong on the bottom/right.
    frame = np.full((*hw, 3), (10, 50, 200), dtype=np.uint8)
    tensor, scale, left, top = letterbox_tensor(frame, 6, 6)
    assert (scale, left, top) == (1.5, *offset)
    expected = np.full((1, 3, 6, 6), 114, dtype=np.float32)
    height, width = (3, 6) if hw == (2, 4) else (6, 3)
    expected[0, :, top:top+height, left:left+width] = np.array([200, 50, 10])[:, None, None]
    np.testing.assert_array_equal(tensor, expected / 255)


def test_onnx_unprojects_box_to_original_pixels():
    # A 4x2 frame becomes 8x4 with two rows of padding above and below.
    raw = np.zeros((1, 5, 10), dtype=np.float32)
    raw[0, :, 0] = [4, 4, 4, 2, .75]
    boxes = raw_head_detector(raw).infer(np.zeros((2, 4, 3), np.uint8))['detections']
    assert boxes == [{'xyxy': [1, .5, 3, 1.5], 'confidence': .75, 'class_id': 0}]


def test_nms_suppresses_only_within_class():
    raw = np.zeros((1, 6, 10), dtype=np.float32)
    raw[0, :, 0] = [4, 4, 4, 4, .875, 0]
    raw[0, :, 1] = [4, 4, 4, 4, .625, 0]
    raw[0, :, 2] = [4, 4, 4, 4, 0, .75]
    boxes = raw_head_detector(raw).infer(np.zeros((8, 8, 3), np.uint8))['detections']
    assert sorted((b['class_id'], b['confidence']) for b in boxes) == [(0, .875), (1, .75)]


@pytest.mark.parametrize('field,value', [(0, np.nan), (4, np.inf), (3, -np.inf)])
def test_nonfinite_head_rejects_entire_frame(field, value):
    raw = np.zeros((1, 5, 10), dtype=np.float32)
    raw[0, :, 0] = [4, 4, 4, 4, .875]
    raw[0, field, 1] = value  # even a corrupt low-confidence anchor invalidates the frame
    with pytest.raises(ValueError, match='non-finite'):
        raw_head_detector(raw).infer(np.zeros((8, 8, 3), np.uint8))


def test_ultralytics_adapter_does_not_import_cv2(monkeypatch):
    from types import SimpleNamespace
    import builtins
    original = builtins.__import__
    def guarded(name, *args, **kwargs):
        if name == 'cv2':
            raise AssertionError('adapter imported cv2 on Ultralytics path')
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', guarded)
    detector = EdgeDefectDetector.__new__(EdgeDefectDetector)
    detector.backend, detector.provider = 'ultralytics', 'cpu'
    detector.confidence, detector.iou = .37, .62
    def predict(frame, *, device, conf, iou, verbose):
        assert (device, conf, iou, verbose) == ('cpu', .37, .62, False)
        return [SimpleNamespace(boxes=None, speed=dict(preprocess=0, inference=0, postprocess=0))]
    detector.model = SimpleNamespace(predict=predict)
    assert detector.infer(np.zeros((4, 4, 3), dtype=np.uint8))['detections'] == []


def test_default_output_location(tmp_path, monkeypatch):
    import src.benchmark as benchmark
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(benchmark, 'EDGE_ROOT', tmp_path / 'edge_inference')
    main(['--synthetic', '--config', str(EDGE_ROOT / 'configs/baseline.yaml'),
          '--warmup', '0', '--runs', '1', '--imgsz', '4'])
    assert (tmp_path / 'edge_inference/docs/edge-benchmark.json').is_file()
    assert not (tmp_path / 'docs/edge-benchmark.json').exists()


def test_model_receives_config_threads_and_cli_override(tmp_path, monkeypatch):
    import src.benchmark as benchmark
    calls = []
    def fake_detector(model, provider, threads):
        calls.append((provider, threads))
        return SyntheticDetector()
    monkeypatch.setattr(benchmark, 'EdgeDefectDetector', fake_detector)
    model = tmp_path / 'fake.onnx'
    model.write_bytes(b'test fixture, not an ONNX graph')
    config = tmp_path / 'config.yaml'
    config.write_text('imgsz: 4\nwarmup_runs: 0\nbenchmark_runs: 1\ncpu_threads: 2\n')
    args = ['--synthetic', '--model', str(model), '--config', str(config),
            '--output', str(tmp_path / 'result.json')]
    main(args)
    main(args + ['--threads', '3', '--warmup', '1', '--runs', '2'])
    assert calls == [('cpu', 2), ('cpu', 3)]
    report = json.loads((tmp_path / 'result.json').read_text())
    assert (report['warmup'], report['runs']) == (1, 2)
