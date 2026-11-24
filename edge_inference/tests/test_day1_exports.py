from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.export_fp32_trace import ground_truth
from scripts.train_baseline import verify_dataset
from scripts.prepare_codebrim import CLASSES
from src.offload_sim import CLASSES as SIM_CLASSES


def test_class_order_agrees_with_simulator():
    assert CLASSES == SIM_CLASSES


def test_ground_truth_pixel_roundtrip(tmp_path):
    path = tmp_path / 'labels.txt'
    path.write_text('0 0.5 0.5 1 1\n3 0.5 0.5 0.5 0.5\n')
    assert ground_truth(path, 100, 50) == [
        {'class_id':'crack','bbox':[0.,0.,100.,50.]},
        {'class_id':'exposed_bar','bbox':[25.,12.5,75.,37.5]}]


def test_invalid_ground_truth_class(tmp_path):
    path = tmp_path / 'labels.txt'
    path.write_text('9 0.5 0.5 1 1\n')
    with pytest.raises(ValueError):
        ground_truth(path,100,50)


def test_dataset_verifier_rejects_changes(tmp_path):
    import json
    from PIL import Image
    from scripts.prepare_codebrim import prepare, FLAGS
    raw = tmp_path / 'raw'
    (raw / 'images').mkdir(parents=True)
    (raw / 'annotations').mkdir()
    Image.new('RGB', (10,10), 'white').save(raw / 'images/one.jpg')
    flags = ''.join(f'<{k}>{int(k == "Background")}</{k}>' for k in ('Background', *FLAGS))
    (raw / 'annotations/one.xml').write_text('<annotation><filename>one.jpg</filename><size><width>10</width><height>10</height></size>'
        f'<object><Defect>{flags}</Defect><bndbox><xmin>1</xmin><ymin>1</ymin><xmax>10</xmax><ymax>10</ymax></bndbox></object></annotation>')
    data = tmp_path / 'dataset'
    prepare(raw, data)
    assert len(verify_dataset(data)) == 64
    label = data / 'labels/test/one.txt'
    label.write_text('0 0.5 0.5 1 1\n')
    with pytest.raises(ValueError, match='content changed'):
        verify_dataset(data)
