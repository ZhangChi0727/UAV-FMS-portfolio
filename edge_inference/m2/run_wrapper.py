"""Development-host runner interface; no real predictor is bundled."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

_REPO = str(Path(__file__).resolve().parents[2])
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)
from edge_inference.m0.run_record import build_run_record, config_hash  # noqa: E402
from edge_inference.m2.finding_schema import validate_finding_record  # noqa: E402
from edge_inference.m2.input_adapter import adapt_development_input  # noqa: E402
from edge_inference.m2.scoring import score_item  # noqa: E402


def _validate_smoke_config(config):
    """Check the fixed, PA-approved synthetic-only smoke settings."""
    if not isinstance(config, dict) or config.get('gpu_memory_budget_mib') != 8188:
        return False
    model = config.get('model_selection')
    if not isinstance(model, dict):
        return False
    expected = {
        'candidate_id': 'HuggingFaceTB/SmolVLM-256M-Instruct',
        'official_revision': 'd039ab0d4b9311b617e8ffec1d06c8464364aeb3',
        'precision': 'bfloat16', 'input_resolution': [512, 512],
        'max_new_tokens': 128, 'batch_size': 1, 'process_memory_cap_mib': 7168,
        'processor_size_longest_edge': 512,
        'attention_implementation': ['sdpa', 'eager'], 'weights_format': 'safetensors_only',
        'allowed_smoke_input': 'synthetic local image and synthetic task only',
        'status': 'PA_approved_synthetic_smoke_only_not_evaluation',
    }
    integer_keys = ('max_new_tokens', 'batch_size', 'process_memory_cap_mib', 'processor_size_longest_edge')
    return (type(config.get('gpu_memory_budget_mib')) is int
            and all(type(model.get(key)) is int for key in integer_keys)
            and isinstance(model.get('input_resolution'), list)
            and all(type(value) is int for value in model['input_resolution'])
            and all(model.get(key) == value for key, value in expected.items())
            and model.get('do_sample') is False and model.get('trust_remote_code') is False
            and model.get('download_and_dry_run_authorized') is True
            and model.get('development_data_execution_authorized') is False)


def _json_object_without_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON object key')
        result[key] = value
    return result


def _reject_json_constant(value):
    raise ValueError('non-finite JSON constant: ' + value)


def run_synthetic_smoke(synthetic_input, config, metadata, predictor):
    """Run one supplied closure on explicitly synthetic data; never load data itself.

    Source declarations are caller attestations, not proof of image provenance.
    Output is retained unmodified; JSON is interpreted only for schema validity.
    This produces no quality, reliability or performance result.
    """
    if not isinstance(metadata, dict) or metadata.get('host_type', 'development-host') != 'development-host':
        raise ValueError('only development-host metadata is allowed')
    fields = dict(metadata)
    fields['host_type'] = 'development-host'
    fields['config_hash'] = config_hash(config)
    run_record = build_run_record(**fields)
    expected_input = {'source': 'synthetic', 'image_origin': 'generated_in_memory',
                      'task_origin': 'synthetic', 'width': 512, 'height': 512}
    if not isinstance(synthetic_input, dict) or synthetic_input != expected_input:
        return {'run_record': run_record, 'execution_status': 'rejected',
                'score_category': 'unscoreable', 'reason': 'synthetic input declaration required'}
    if not _validate_smoke_config(config):
        return {'run_record': run_record, 'execution_status': 'rejected',
                'score_category': 'unscoreable', 'reason': 'fixed synthetic smoke configuration required'}
    if (run_record['model_id'] != config['model_selection']['candidate_id'] or
            run_record['precision'] != config['model_selection']['precision']):
        return {'run_record': run_record, 'execution_status': 'rejected',
                'score_category': 'unscoreable', 'reason': 'run metadata disagrees with fixed model or precision'}
    try:
        raw = predictor()
    except Exception as exc:
        return {'run_record': run_record, 'execution_status': 'failed', 'score_category': 'unscoreable',
                'raw_output': None, 'error_type': type(exc).__name__, 'error_message': str(exc)}
    result = {'run_record': run_record, 'raw_output': raw}
    if not isinstance(raw, str):
        result.update(execution_status='invalid', score_category='invalid',
                      validation_errors=['predictor output must be a JSON text string'])
        return result
    try:
        decoded = json.loads(raw, object_pairs_hook=_json_object_without_duplicates,
                             parse_constant=_reject_json_constant)
    except (ValueError, TypeError, RecursionError):
        result.update(execution_status='invalid', score_category='invalid',
                      validation_errors=['output is not valid unambiguous JSON'])
        return result
    errors = validate_finding_record(decoded, dataset_version='dacl10k/v2', width=512, height=512)
    if errors:
        result.update(execution_status='invalid', score_category='invalid', validation_errors=errors)
        return result
    score = score_item(decoded, [], width=512, height=512, fact_coverage_complete=False)
    category = score['category']
    result.update(execution_status='invalid' if category == 'invalid' else 'completed',
                  score_category=category, validation_errors=[], parsed_output=decoded)
    return result


def run_development(request, mapping, config, metadata, predictor):
    """Call M0 for every invocation and, if supported, call a supplied predictor.

    Only image metadata and task are passed to the predictor. Reference evidence
    is not accepted by the adapter. This wrapper neither writes results nor loads a
    model; unit-test callbacks are not a real model execution.
    """
    if not isinstance(metadata, dict) or metadata.get('host_type', 'development-host') != 'development-host':
        raise ValueError('only development-host metadata is allowed')
    fields = dict(metadata)
    fields['host_type'] = 'development-host'
    fields['config_hash'] = config_hash(config)
    run_record = build_run_record(**fields)
    model_selection = config.get('model_selection', {})
    if not isinstance(model_selection, dict) or model_selection.get('development_data_execution_authorized') is not True:
        return {'run_record': run_record, 'execution_status': 'awaiting_development_data_approval'}
    adapted = adapt_development_input(request, mapping)
    if adapted['status'] != 'supported':
        return {'run_record': run_record, 'execution_status': adapted['status'], 'adapter': adapted}
    try:
        raw = predictor(deepcopy(adapted['request']))
    except Exception as exc:
        return {'run_record': run_record, 'execution_status': 'failed', 'error_type': type(exc).__name__}
    image = adapted['request']['image']
    errors = validate_finding_record(raw, dataset_version=adapted['dataset_version'],
                                     width=image['width'], height=image['height'])
    return {'run_record': run_record, 'execution_status': 'invalid' if errors or raw['status'] == 'invalid' else 'completed',
            'raw_output': raw, 'validation_errors': errors}
