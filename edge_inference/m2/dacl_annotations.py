"""Conservative dacl10k-v2 annotation inventory for development splits only.

This is a metadata adapter, not an annotation-quality adjudicator. No omission or
empty shapes list is treated as a confirmed negative, and no image is opened.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Mapping

DEVELOPMENT_SPLITS = frozenset({'train', 'validation'})
DAMAGE_LABELS = frozenset({
    'Crack', 'ACrack', 'Wetspot', 'Efflorescence', 'Rust', 'Rockpocket',
    'Hollowareas', 'Cavity', 'Spalling', 'Graffiti', 'Weathering',
    'Restformwork', 'ExposedRebars',
})
OBJECT_LABELS = frozenset({'Bearing', 'EJoint', 'Drainage', 'PEquipment', 'JTape', 'WConccor'})
KNOWN_LABELS = DAMAGE_LABELS | OBJECT_LABELS


def summarize_annotation(document: Mapping[str, Any], expected_split: str) -> dict[str, Any]:
    """List annotated positives as unverified evidence, without inventing negatives."""
    if expected_split not in DEVELOPMENT_SPLITS:
        raise ValueError('only train and validation annotations may be inspected')
    if not isinstance(document, Mapping) or document.get('split') != expected_split:
        raise ValueError('annotation split is absent or does not match the allowed split')
    if document.get('dacl10k_version') != 'v2':
        raise ValueError('expected explicit dacl10k version v2')
    shapes = document.get('shapes')
    if not isinstance(shapes, list):
        raise ValueError('shapes must be a list')
    labels = []
    for shape in shapes:
        if not isinstance(shape, Mapping) or not isinstance(shape.get('label'), str) or not shape['label']:
            raise ValueError('each shape must have a nonempty string label')
        labels.append(shape['label'])
    present = sorted(set(labels) & KNOWN_LABELS)
    unknown = sorted(set(labels) - KNOWN_LABELS)
    return {
        'split': expected_split,
        'annotation_version': 'v2',
        'present_annotation_unverified': present,
        'unknown_labels': unknown,
        'no_annotation_for_classes': sorted(KNOWN_LABELS - set(present)),
        'reliable_positive_classes': [],
        'reliable_negative_classes': [],
        'shape_count': len(shapes),
        'caution': 'Annotation presence is not independently verified; missing annotation is unlabelled, not a reliable negative.',
    }


def read_development_annotation(dataset_root: Path, path: Path, expected_split: str) -> dict[str, Any]:
    """Read only a JSON file directly within annotations/train or validation.

    Reject held-out paths and symlinks before opening bytes. Callers must first
    establish the root and package provenance; this is not W1 approval.
    """
    if expected_split not in DEVELOPMENT_SPLITS:
        raise ValueError('held-out annotations are forbidden')
    root = dataset_root.absolute()
    target = path.absolute()
    expected_parent = root / 'annotations' / expected_split
    if target.parent != expected_parent or target.suffix.lower() != '.json':
        raise ValueError('annotation must be directly inside the declared development split')
    if re.search(r'(?i)(?:^|[_.-])(testdev|testchallenge)(?:$|[_.-])', target.name):
        raise ValueError('held-out annotation identifier is forbidden')
    if any(part.is_symlink() for part in (root, root / 'annotations', expected_parent, target)):
        raise ValueError('symlink paths are forbidden')
    with target.open('r', encoding='utf-8') as stream:
        document = json.load(stream)
    return summarize_annotation(document, expected_split)
