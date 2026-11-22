"""M2 finding schema for named dacl10k v2 damage classes; no model inference."""
from __future__ import annotations

from collections.abc import Mapping
import math
from numbers import Real

DACL10K_V2_DAMAGE_CLASSES = frozenset({
    'Crack', 'ACrack', 'Wetspot', 'Efflorescence', 'Rust', 'Rockpocket',
    'Hollowareas', 'Cavity', 'Spalling', 'Graffiti', 'Weathering',
    'Restformwork', 'ExposedRebars',
})
DACL10K_V2_OBJECT_CLASSES = frozenset({'Bearing', 'EJoint', 'Drainage', 'PEquipment', 'JTape', 'WConccor'})
STATUSES = frozenset({'findings', 'no_finding', 'abstain', 'invalid'})


def _finite_number(value):
    if not isinstance(value, Real) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def validate_finding_record(record, *, dataset_version, width, height):
    """Return validation errors; bbox is [xmin,ymin,xmax,ymax] in source pixels."""
    errors = []
    if dataset_version != 'dacl10k/v2':
        errors.append('unsupported dataset version')
    if any(not isinstance(x, int) or isinstance(x, bool) or x <= 0 for x in (width, height)):
        errors.append('width and height must be positive integer pixels')
    if not isinstance(record, Mapping):
        return errors + ['record must be a mapping']
    if set(record) != {'status', 'findings'}:
        errors.append('record must contain exactly status and findings')
    status = record.get('status')
    if not isinstance(status, str) or status not in STATUSES:
        errors.append('unknown status')
    findings = record.get('findings')
    if not isinstance(findings, list):
        return errors + ['findings must be a list']
    if status == 'findings' and not findings:
        errors.append('findings status requires a nonempty list')
    if isinstance(status, str) and status in {'no_finding', 'abstain', 'invalid'} and findings:
        errors.append('non-findings status requires an empty findings list')
    for index, finding in enumerate(findings):
        label = f'findings[{index}]'
        if not isinstance(finding, Mapping) or set(finding) != {'defect_class', 'bbox', 'confidence'}:
            errors.append(f'{label} must contain exactly defect_class, bbox and confidence')
            continue
        defect = finding['defect_class']
        if not isinstance(defect, str) or defect not in DACL10K_V2_DAMAGE_CLASSES:
            errors.append(f'{label} has unknown defect class')
        confidence = finding['confidence']
        if not _finite_number(confidence) or not 0 <= confidence <= 1:
            errors.append(f'{label} confidence must be finite and in [0, 1]')
        box = finding['bbox']
        if not isinstance(box, list) or len(box) != 4 or not all(_finite_number(v) for v in box):
            errors.append(f'{label} bbox must have four finite numeric coordinates')
        elif not is_valid_box(box, width, height):
            errors.append(f'{label} bbox must have positive area within the source image')
    return errors


def is_valid_box(box, width, height):
    """Return whether a continuous-coordinate xyxy box is inside image bounds."""
    if any(not isinstance(x, int) or isinstance(x, bool) or x <= 0 for x in (width, height)):
        return False
    x0, y0, x1, y1 = box
    return 0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height
