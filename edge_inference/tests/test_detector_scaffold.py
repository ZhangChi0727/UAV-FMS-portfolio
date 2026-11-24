import json
import sys
from pathlib import Path
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.detector import EdgeDefectDetector
from src.benchmark import SyntheticDetector, main, run


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
