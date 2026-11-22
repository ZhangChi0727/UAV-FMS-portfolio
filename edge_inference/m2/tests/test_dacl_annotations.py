"""Synthetic metadata only; no real dataset, images or held-out labels."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dacl_annotations import read_development_annotation, summarize_annotation


def document(shapes, split='train'):
    return {'split': split, 'dacl10k_version': 'v2', 'shapes': shapes}


def test_empty_shapes_remain_unlabelled_not_negative():
    result = summarize_annotation(document([]), 'train')
    assert not result['reliable_positive_classes']
    assert not result['reliable_negative_classes']
    assert 'Crack' in result['no_annotation_for_classes']


def test_positive_annotation_is_unverified_and_unknowns_are_separate():
    result = summarize_annotation(document([{'label': 'Crack'}, {'label': 'unrecognised'}]), 'train')
    assert result['present_annotation_unverified'] == ['Crack']
    assert result['unknown_labels'] == ['unrecognised']
    assert not result['reliable_positive_classes']
    assert not result['reliable_negative_classes']


def test_heldout_path_rejected_before_open(tmp_path):
    nonexistent = tmp_path / 'annotations' / 'testchallenge' / 'not-opened.json'
    with pytest.raises(ValueError, match='forbidden'):
        read_development_annotation(tmp_path, nonexistent, 'testchallenge')
    with pytest.raises(ValueError, match='development split'):
        read_development_annotation(tmp_path, nonexistent, 'train')
    disguised = tmp_path / 'annotations' / 'train' / 'dacl10k_v2_testchallenge_0001.json'
    with pytest.raises(ValueError, match='identifier'):
        read_development_annotation(tmp_path, disguised, 'train')


def test_allowed_synthetic_document_and_mismatched_split(tmp_path):
    folder = tmp_path / 'annotations' / 'validation'
    folder.mkdir(parents=True)
    path = folder / 'synthetic.json'
    path.write_text(json.dumps(document([], split='validation')), encoding='utf-8')
    assert read_development_annotation(tmp_path, path, 'validation')['split'] == 'validation'
    path.write_text(json.dumps(document([], split='testdev')), encoding='utf-8')
    with pytest.raises(ValueError, match='split'):
        read_development_annotation(tmp_path, path, 'validation')


def test_invalid_shapes_do_not_become_negative_evidence():
    with pytest.raises(ValueError, match='nonempty'):
        summarize_annotation(document([{'label': ''}]), 'train')
    with pytest.raises(ValueError, match='shapes'):
        summarize_annotation(document(None), 'train')
