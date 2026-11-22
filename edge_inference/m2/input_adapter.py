"""Fail-closed development task adapter; it never reads images or references."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import re
import sys

_REPO = str(Path(__file__).resolve().parents[2])
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)
from edge_inference.m1.task_schema import validate_task  # noqa: E402
from edge_inference.m2.finding_schema import DACL10K_V2_DAMAGE_CLASSES, DACL10K_V2_OBJECT_CLASSES  # noqa: E402


def adapt_development_input(request, mapping):
    """Return supported, unsupported, or invalid without implicit label mapping.

    A verified mapping must explicitly cover the target element and every requested
    defect class, and attach an evidence locator. The checked-in mapping is unresolved.
    The adapter does not itself approve a mapping or establish label completeness.
    """
    if not isinstance(request, Mapping) or set(request) != {'image', 'task'}:
        return {'status': 'invalid', 'errors': ['request must contain exactly image and task']}
    image, task = request['image'], request['task']
    if not isinstance(image, Mapping) or set(image) != {'image_id', 'path', 'width', 'height', 'source_split'}:
        return {'status': 'invalid', 'errors': ['invalid image metadata fields']}
    if not isinstance(image['source_split'], str) or image['source_split'] not in {'train', 'validation'}:
        return {'status': 'unsupported', 'errors': ['only development source splits are allowed']}
    if any(not isinstance(image[k], str) or not image[k] for k in ('image_id', 'path')):
        return {'status': 'invalid', 'errors': ['image_id and path must be nonempty strings']}
    if any(re.search(r'(?i)(?:^|[/\\_.-])(testdev|testchallenge)(?:$|[/\\_.-])', image[k]) for k in ('image_id', 'path')):
        return {'status': 'unsupported', 'errors': ['test-source identifier is quarantined']}
    # Pure lexical check only. It neither opens files nor establishes manifest
    # membership, real-path containment, symlink safety or provenance.
    path_parts = image['path'].replace('\\', '/').split('/')
    if (len(path_parts) < 3 or path_parts[:2] != ['images', image['source_split']] or
            any(part in {'', '.', '..'} or ':' in part or '\x00' in part or
                part.endswith(('.', ' ')) for part in path_parts)):
        return {'status': 'unsupported', 'errors': ['path must be a normalized relative development image path']}
    if any(not isinstance(image[k], int) or isinstance(image[k], bool) or image[k] <= 0 for k in ('width', 'height')):
        return {'status': 'invalid', 'errors': ['image dimensions must be positive integer pixels']}
    try:
        task_errors = validate_task(task)
    except (TypeError, ValueError):
        task_errors = ['malformed task']
    if task_errors:
        return {'status': 'invalid', 'errors': task_errors}
    if (not isinstance(mapping, Mapping) or mapping.get('status') != 'verified' or
            not isinstance(mapping.get('evidence_locator'), str) or not mapping['evidence_locator'].strip()):
        return {'status': 'unsupported', 'errors': ['task-to-dataset mapping not verified']}
    targets, defects = mapping.get('target_elements'), mapping.get('defect_classes')
    if not isinstance(targets, Mapping) or not isinstance(defects, Mapping):
        return {'status': 'unsupported', 'errors': ['target or defect mapping missing']}
    target = targets.get(task['target_element'])
    if not isinstance(target, str) or target not in DACL10K_V2_OBJECT_CLASSES:
        return {'status': 'unsupported', 'errors': ['target element not mapped']}
    contexts = mapping.get('context_rules')
    if not isinstance(contexts, Mapping) or not isinstance(contexts.get('locations'), Mapping) or not isinstance(contexts.get('views'), Mapping):
        return {'status': 'unsupported', 'errors': ['location and view mappings are not verified']}
    required_contexts = [contexts['locations'].get(task['location_tag'])] + [contexts['views'].get(view) for view in task['required_views']]
    if any(not isinstance(value, str) or not value.strip() for value in required_contexts):
        return {'status': 'unsupported', 'errors': ['requested location or view is not represented']}
    mapped = []
    for defect in task['defect_classes']:
        labels = defects.get(defect)
        if (not isinstance(labels, list) or not labels or
                any(not isinstance(x, str) or x not in DACL10K_V2_DAMAGE_CLASSES for x in labels)):
            return {'status': 'unsupported', 'errors': [f'defect class not mapped: {defect}']}
        mapped.extend(labels)
    return {'status': 'supported', 'dataset_version': 'dacl10k/v2',
            'target_label': target, 'defect_labels': sorted(set(mapped)),
            'request': {'image': dict(image), 'task': dict(task)}}
