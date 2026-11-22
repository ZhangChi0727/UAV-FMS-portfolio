"""Synthetic unit fixtures only: no dataset images, instruction sets, or model."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from edge_inference.m2.finding_schema import validate_finding_record  # noqa: E402
from edge_inference.m2.input_adapter import adapt_development_input  # noqa: E402
from edge_inference.m2 import run_wrapper  # noqa: E402
from edge_inference.m2.run_wrapper import run_development, run_synthetic_smoke  # noqa: E402
from edge_inference.m2.scoring import score_item, summarize  # noqa: E402


def record(status='no_finding', findings=None):
    return {'status': status, 'findings': [] if findings is None else findings}


def finding(label='Rust', box=None, confidence=0.5):
    return {'defect_class': label, 'bbox': [1, 2, 9, 8] if box is None else box, 'confidence': confidence}


def fact(reference, observed, label='Rust', fact_id='f1'):
    return {'fact_id': fact_id, 'defect_class': label, 'reference': reference, 'observed': observed}


def request():
    return {'image': {'image_id': 'synthetic-train-image', 'path': 'images/train/image.png',
                      'width': 10, 'height': 10, 'source_split': 'train'},
            'task': {'target_element': 'bearing', 'location_tag': 'unspecified',
                     'defect_classes': ['crack'], 'required_views': ['overview']}}


def fixture_mapping():
    # Deliberately artificial, not a proposed dataset mapping or semantic claim.
    return {'status': 'verified', 'evidence_locator': 'synthetic-unit-fixture-only',
            'target_elements': {'bearing': 'Bearing'}, 'defect_classes': {'crack': ['Rust']},
            'context_rules': {'locations': {'unspecified': 'fixture'}, 'views': {'overview': 'fixture'}}}


def metadata():
    return {'model_id': 'unit-test/no-model', 'precision': 'not-applicable',
            'library_versions': {'python': 'unit-fixture'}, 'device_id': 'none',
            'code_revision': 'synthetic-fixture', 'seed': 0, 'host_id': 'unit-test',
            'raw_artifact_location': 'synthetic/not-written', 'analysis_command': 'unit-test'}


@pytest.mark.parametrize('state', ['no_finding', 'abstain', 'invalid'])
def test_empty_records_for_non_finding_states_are_well_formed(state):
    assert validate_finding_record(record(state), dataset_version='dacl10k/v2', width=10, height=10) == []


def test_finding_record_has_closed_class_pixel_box_and_confidence():
    assert not validate_finding_record(record('findings', [finding()]), dataset_version='dacl10k/v2', width=10, height=10)


@pytest.mark.parametrize('raw', [
    '', {}, {'status': [], 'findings': []}, record('findings'),
    record('no_finding', [finding()]), record('findings', [finding('not-a-class')]),
    record('findings', [finding(confidence=float('nan'))]),
    record('findings', [finding(confidence=True)]),
    record('findings', [finding(box=[1, 2, 11, 8])]),
    record('findings', [finding(box=[1, 2, 1, 8])]),
])
def test_malformed_records_are_rejected(raw):
    assert validate_finding_record(raw, dataset_version='dacl10k/v2', width=10, height=10)


def test_wrong_version_and_boolean_dimensions_are_invalid():
    assert validate_finding_record(record(), dataset_version='unknown', width=True, height=10)


def test_unresolved_mapping_is_unsupported_not_guessed():
    assert adapt_development_input(request(), {'status': 'unresolved'})['status'] == 'unsupported'


def test_explicit_synthetic_mapping_is_used_only_as_supplied():
    adapted = adapt_development_input(request(), fixture_mapping())
    assert adapted['status'] == 'supported'
    assert adapted['defect_labels'] == ['Rust']


def test_unrepresented_view_or_target_is_unsupported():
    mapping = fixture_mapping()
    mapping['context_rules']['views'] = {}
    assert adapt_development_input(request(), mapping)['status'] == 'unsupported'
    mapping = fixture_mapping()
    mapping['target_elements']['bearing'] = 'unknown'
    assert adapt_development_input(request(), mapping)['status'] == 'unsupported'


@pytest.mark.parametrize('split,path,image_id', [
    ('testdev', 'images/testdev/image.png', 'x'),
    ('train', 'images/testchallenge/image.png', 'x'),
    ('train', 'images/train/dacl10k_v2_testdev_0001.jpg', 'x'),
    ('validation', 'images/train/image.png', 'x'),
    ('train', 'images/train/../validation/image.png', 'x'),
    ('train', 'images\\train\\..\\testdev\\image.png', 'x'),
    ('train', '/images/train/image.png', 'x'),
    ('train', 'C:\\images\\train\\image.png', 'x'),
    ('train', 'C:images/train/image.png', 'x'),
    ('train', '//server/images/train/image.png', 'x'),
    ('train', 'images//train/image.png', 'x'),
    ('train', 'images/train//image.png', 'x'),
    ('train', 'images/train/./image.png', 'x'),
    ('train', 'images/train/image.png:stream', 'x'),
    ('train', 'images/train/image.png.', 'x'),
])
def test_quarantined_or_mismatched_image_sources_rejected(split, path, image_id):
    item = request()
    item['image'].update(source_split=split, path=path, image_id=image_id)
    assert adapt_development_input(item, fixture_mapping())['status'] == 'unsupported'


def test_normalized_relative_windows_development_path_is_accepted():
    item = request()
    item['image']['path'] = 'images\\train\\image.png'
    assert adapt_development_input(item, fixture_mapping())['status'] == 'supported'


def test_reference_input_is_not_accepted_by_runtime_adapter():
    item = request()
    item['reference'] = {'not': 'allowed'}
    assert adapt_development_input(item, fixture_mapping())['status'] == 'invalid'


def test_positive_labels_score_hit_and_miss_without_negative():
    output = record('findings', [finding()])
    hit = score_item(output, [fact('present', True)], width=10, height=10, fact_coverage_complete=True)
    miss = score_item(record(), [fact('present', False)], width=10, height=10, fact_coverage_complete=True)
    assert hit['category'] == 'unscoreable'
    assert hit['class_counts']['Rust']['hit'] == 1
    assert miss['category'] == 'error'
    assert miss['class_counts']['Rust']['missed'] == 1


def test_two_same_class_findings_one_positive_fact_never_marked_correct():
    output = record('findings', [finding('Rust', [1, 1, 4, 4]), finding('Rust', [5, 5, 9, 9])])
    outcome = score_item(output, [fact('present', True)], width=10, height=10, fact_coverage_complete=True)
    assert outcome['category'] == 'unscoreable'
    assert outcome['class_counts']['Rust']['hit'] == 1


def test_known_error_with_findings_remains_error():
    output = record('findings', [finding('Rust', [1, 1, 4, 4]), finding('Rust', [5, 5, 9, 9])])
    facts = [fact('present', True), fact('labelled_absent', True, fact_id='f2')]
    outcome = score_item(output, facts, width=10, height=10, fact_coverage_complete=True)
    assert outcome['category'] == 'error'
    assert outcome['class_counts']['Rust']['hit'] == 1
    assert outcome['class_counts']['Rust']['false_positive'] == 1


def test_negative_evidence_enables_false_positive_but_unknown_does_not():
    output = record('findings', [finding()])
    negative = score_item(output, [fact('labelled_absent', True)], width=10, height=10, fact_coverage_complete=True)
    unknown = score_item(output, [fact('unlabelled', True)], width=10, height=10, fact_coverage_complete=True)
    assert negative['category'] == 'error'
    assert negative['class_counts']['Rust']['false_positive'] == 1
    assert unknown['category'] == 'unscoreable'
    assert unknown['class_counts']['Rust']['undeterminable'] == 1
    assert unknown['class_counts']['Rust']['false_positive'] == 0


def test_valid_no_finding_can_be_correct_but_incomplete_evidence_cannot():
    args = (record(), [fact('labelled_absent', False)])
    assert score_item(*args, width=10, height=10, fact_coverage_complete=True)['category'] == 'correct'
    assert score_item(*args, width=10, height=10)['category'] == 'unscoreable'


def test_uncovered_predicted_class_cannot_be_marked_correct():
    output = record('findings', [finding('Rust')])
    outcome = score_item(output, [fact('labelled_absent', False, label='Crack')],
                         width=10, height=10, fact_coverage_complete=True)
    assert outcome['category'] == 'unscoreable'


def test_known_error_and_unknown_fact_keep_error_and_uncertainty():
    outcome = score_item(record(), [fact('present', False), fact('unlabelled', False, fact_id='f2')],
                         width=10, height=10, fact_coverage_complete=False)
    assert outcome['category'] == 'error'
    assert outcome['class_counts']['Rust']['undeterminable'] == 1


def test_observed_fact_cannot_be_invented_for_no_finding():
    with pytest.raises(ValueError, match='not represented'):
        score_item(record(), [fact('labelled_absent', True)], width=10, height=10)


def test_empty_facts_cannot_prove_complete_coverage():
    with pytest.raises(ValueError, match='empty evidence'):
        score_item(record(), [], width=10, height=10, fact_coverage_complete=True)


def test_selective_risk_denominator_and_zero_scoreable():
    out = summarize([{'category': 'unscoreable'}, {'category': 'abstain'}, {'category': 'failed'}])
    assert out['submitted'] == 3 and out['accepted'] == 1
    assert out['accepted_and_scoreable'] == 0 and out['errors'] == 0
    assert out['selective_risk'] is None
    assert out['complete_fabrication_rate'] is None


def test_summary_counts_invalid_and_failed_in_coverage_denominator():
    out = summarize([{'category': 'correct'}, {'category': 'error'}, {'category': 'unscoreable'},
                     {'category': 'invalid'}, {'category': 'failed'}, {'category': 'abstain'}])
    assert (out['submitted'], out['accepted'], out['accepted_and_scoreable'], out['errors']) == (6, 3, 2, 1)
    assert out['coverage'] == 0.5 and out['selective_risk'] == 0.5


def test_approved_smoke_config_does_not_enable_development_data_execution():
    config = json.loads((ROOT / 'edge_inference/m2/development_config.json').read_text(encoding='utf-8'))
    called = []
    result = run_development(request(), fixture_mapping(), config, metadata(), lambda value: called.append(value))
    assert result['execution_status'] == 'awaiting_development_data_approval'
    assert result['run_record']['host_type'] == 'development-host' and not called


def test_wrapper_calls_only_synthetic_callback_after_separate_unit_approval():
    config = {'model_selection': {'development_data_execution_authorized': True}}
    seen = []
    def synthetic_callback(value):
        seen.append(deepcopy(value))
        return record()
    result = run_development(request(), fixture_mapping(), config, metadata(), synthetic_callback)
    assert result['execution_status'] == 'completed'
    assert seen == [request()]
    assert result['raw_output'] == record()


def test_wrapper_retains_invalid_raw_and_records_failures():
    config = {'model_selection': {'development_data_execution_authorized': True}}
    malformed = run_development(request(), fixture_mapping(), config, metadata(), lambda _: '')
    assert malformed['execution_status'] == 'invalid' and malformed['raw_output'] == ''
    explicit = run_development(request(), fixture_mapping(), config, metadata(), lambda _: record('invalid'))
    assert explicit['execution_status'] == 'invalid' and explicit['raw_output'] == record('invalid')
    def failed(_):
        raise RuntimeError('synthetic failure')
    result = run_development(request(), fixture_mapping(), config, metadata(), failed)
    assert result['execution_status'] == 'failed' and result['error_type'] == 'RuntimeError'


def test_unsupported_mapping_never_calls_predictor():
    config = {'model_selection': {'development_data_execution_authorized': True}}
    called = []
    result = run_development(request(), {'status': 'unresolved'}, config, metadata(), lambda x: called.append(x))
    assert result['execution_status'] == 'unsupported' and called == []


def smoke_config():
    return json.loads((ROOT / 'edge_inference/m2/development_config.json').read_text(encoding='utf-8'))


def smoke_input():
    return {'source': 'synthetic', 'image_origin': 'generated_in_memory',
            'task_origin': 'synthetic', 'width': 512, 'height': 512}


def smoke_metadata():
    fields = metadata()
    fields.update(model_id='HuggingFaceTB/SmolVLM-256M-Instruct', precision='bfloat16')
    return fields


def test_synthetic_smoke_calls_m0_and_predictor_exactly_once(monkeypatch):
    seen = []
    actual_m0 = run_wrapper.build_run_record
    def instrumented_m0(**fields):
        seen.append(('m0', fields['host_type']))
        return actual_m0(**fields)
    monkeypatch.setattr(run_wrapper, 'build_run_record', instrumented_m0)
    def predictor():
        seen.append(('predictor',))
        return '{"status":"no_finding","findings":[]}'
    out = run_synthetic_smoke(smoke_input(), smoke_config(), smoke_metadata(), predictor)
    assert seen == [('m0', 'development-host'), ('predictor',)]
    assert out['execution_status'] == 'completed' and out['score_category'] == 'unscoreable'
    assert out['raw_output'] == '{"status":"no_finding","findings":[]}'
    assert out['run_record']['host_type'] == 'development-host'
    assert out['run_record']['config_hash'] == run_wrapper.config_hash(smoke_config())


@pytest.mark.parametrize('raw', ['', 'plain text', None, '{"status":"no_finding","findings":[],"status":"abstain"}',
                                 '{"status":"no_finding","findings":[],"x":NaN}', '{}'])
def test_synthetic_smoke_preserves_invalid_raw(raw):
    calls = []
    def predictor():
        calls.append(1)
        return raw
    out = run_synthetic_smoke(smoke_input(), smoke_config(), smoke_metadata(), predictor)
    assert out['execution_status'] == 'invalid' and out['score_category'] == 'invalid'
    assert out['raw_output'] == raw and calls == [1]


def test_synthetic_smoke_valid_finding_is_unscoreable_without_reference():
    raw = json.dumps(record('findings', [finding()]))
    out = run_synthetic_smoke(smoke_input(), smoke_config(), smoke_metadata(), lambda: raw)
    assert out['execution_status'] == 'completed' and out['score_category'] == 'unscoreable'


@pytest.mark.parametrize('status,expected', [('invalid', 'invalid'), ('abstain', 'abstain')])
def test_synthetic_smoke_preserves_explicit_nonfinding_status(status, expected):
    raw = json.dumps(record(status))
    out = run_synthetic_smoke(smoke_input(), smoke_config(), smoke_metadata(), lambda: raw)
    assert out['score_category'] == expected and out['raw_output'] == raw


def test_synthetic_smoke_retains_exception_and_does_not_retry():
    calls = []
    def predictor():
        calls.append(1)
        raise RuntimeError('synthetic fixture failure')
    out = run_synthetic_smoke(smoke_input(), smoke_config(), smoke_metadata(), predictor)
    assert calls == [1] and out['execution_status'] == 'failed' and out['raw_output'] is None
    assert out['error_type'] == 'RuntimeError' and out['error_message'] == 'synthetic fixture failure'


@pytest.mark.parametrize('change', [
    {'source': 'train'}, {'image_origin': 'file'}, {'task_origin': 'dataset'},
    {'width': 256}, {'height': 256}, {'extra': 'not-allowed'},
])
def test_synthetic_smoke_rejects_non_synthetic_or_wrong_size_before_predictor(change):
    supplied = smoke_input()
    supplied.update(change)
    calls = []
    out = run_synthetic_smoke(supplied, smoke_config(), smoke_metadata(), lambda: calls.append(1))
    assert out['execution_status'] == 'rejected' and out['score_category'] == 'unscoreable'
    assert calls == [] and out['run_record']['host_type'] == 'development-host'


@pytest.mark.parametrize('key,value', [
    ('max_new_tokens', 64), ('precision', 'float16'), ('input_resolution', [256, 256]),
    ('processor_size_longest_edge', 256), ('do_sample', True), ('trust_remote_code', True),
    ('download_and_dry_run_authorized', False), ('development_data_execution_authorized', True),
])
def test_synthetic_smoke_rejects_drifted_config_without_calling_predictor(key, value):
    config = smoke_config()
    config['model_selection'][key] = value
    calls = []
    out = run_synthetic_smoke(smoke_input(), config, smoke_metadata(), lambda: calls.append(1))
    assert out['execution_status'] == 'rejected' and calls == []


def test_synthetic_smoke_rejects_wrong_metadata_and_non_development_host():
    fields = smoke_metadata()
    fields['model_id'] = 'different/model'
    calls = []
    out = run_synthetic_smoke(smoke_input(), smoke_config(), fields, lambda: calls.append(1))
    assert out['execution_status'] == 'rejected' and calls == []
    fields['host_type'] = 'flight'
    with pytest.raises(ValueError, match='development-host'):
        run_synthetic_smoke(smoke_input(), smoke_config(), fields, lambda: calls.append(1))
