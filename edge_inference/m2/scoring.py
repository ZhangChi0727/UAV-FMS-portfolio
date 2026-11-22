"""Conservative scoring of explicitly adjudicated facts, not an image matcher.

This scaffold does not infer labels, absent regions, matches, or a threshold.
Until a reviewed adjudication rule and independent references exist, results from
this function are interface exercises only, not evaluated model performance.
In particular, class-level facts do not prove per-finding or per-region coverage:
findings without a determined error remain unscoreable, never correct.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping

from .finding_schema import DACL10K_V2_DAMAGE_CLASSES, validate_finding_record

REFERENCE_STATES = frozenset({'present', 'labelled_absent', 'unlabelled'})


def score_item(record, facts, *, width, height, fact_coverage_complete=False):
    """Score pre-adjudicated boolean facts and retain uncertainty explicitly.

    Each fact has an explicit id, class, reference state and whether the prediction
    was adjudicated to assert it. This function does not construct these facts from
    dacl10k polygons, nor match a predicted box to any labelled region.
    """
    errors = validate_finding_record(record, dataset_version='dacl10k/v2', width=width, height=height)
    if errors:
        return {'category': 'invalid', 'validation_errors': errors, 'class_counts': {}}
    status = record['status']
    if status in {'abstain', 'invalid'}:
        return {'category': status, 'class_counts': {}}
    if not isinstance(fact_coverage_complete, bool):
        raise ValueError('fact_coverage_complete must be bool')
    if not isinstance(facts, list):
        raise ValueError('facts must be a list')
    if fact_coverage_complete and not facts:
        raise ValueError('empty evidence cannot establish complete fact coverage')
    counts = defaultdict(lambda: {'present': 0, 'labelled_absent': 0, 'unlabelled': 0,
                                  'undeterminable': 0, 'hit': 0, 'missed': 0, 'false_positive': 0})
    seen = set()
    covered_labels = set()
    item_error = False
    uncertain = False
    predicted_labels = {entry['defect_class'] for entry in record['findings']}
    for fact in facts:
        if not isinstance(fact, Mapping) or set(fact) != {'fact_id', 'defect_class', 'reference', 'observed'}:
            raise ValueError('fact must contain exactly fact_id, defect_class, reference and observed')
        fact_id, label, reference, observed = (fact[k] for k in ('fact_id', 'defect_class', 'reference', 'observed'))
        if not isinstance(fact_id, str) or not fact_id or fact_id in seen:
            raise ValueError('fact_id must be a unique nonempty string')
        seen.add(fact_id)
        if not isinstance(label, str) or label not in DACL10K_V2_DAMAGE_CLASSES:
            raise ValueError('unknown fact class')
        covered_labels.add(label)
        if not isinstance(reference, str) or reference not in REFERENCE_STATES or not isinstance(observed, bool):
            raise ValueError('invalid reference or observation')
        if observed and label not in predicted_labels:
            raise ValueError('observed fact is not represented by a predicted class')
        row = counts[label]
        row[reference] += 1
        if reference == 'unlabelled':
            row['undeterminable'] += 1
            uncertain = True
        elif reference == 'present' and observed:
            row['hit'] += 1
        elif reference == 'present' and not observed:
            row['missed'] += 1
            item_error = True
        elif reference == 'labelled_absent' and observed:
            row['false_positive'] += 1
            item_error = True
    if predicted_labels - covered_labels:
        uncertain = True
    category = ('error' if item_error else
                'unscoreable' if status == 'findings' or uncertain or not fact_coverage_complete else
                'correct')
    return {'category': category, 'class_counts': dict(counts)}


def summarize(outcomes):
    """Summarize all submitted items; None denotes a zero denominator (NA)."""
    if not isinstance(outcomes, list):
        raise ValueError('outcomes must be a list')
    allowed = {'correct', 'error', 'unscoreable', 'abstain', 'invalid', 'failed'}
    categories = []
    counts = defaultdict(lambda: {'present': 0, 'labelled_absent': 0, 'unlabelled': 0,
                                  'undeterminable': 0, 'hit': 0, 'missed': 0, 'false_positive': 0})
    for outcome in outcomes:
        if not isinstance(outcome, Mapping) or outcome.get('category') not in allowed:
            raise ValueError('unknown outcome')
        categories.append(outcome['category'])
        for label, values in outcome.get('class_counts', {}).items():
            if label not in DACL10K_V2_DAMAGE_CLASSES or set(values) != set(counts[label]):
                raise ValueError('invalid class counts')
            for key, value in values.items():
                if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                    raise ValueError('class counts must be nonnegative integers')
                counts[label][key] += value
    submitted = len(categories)
    accepted = sum(c in {'correct', 'error', 'unscoreable'} for c in categories)
    scoreable = sum(c in {'correct', 'error'} for c in categories)
    errors = categories.count('error')
    return {'submitted': submitted, 'accepted': accepted, 'accepted_and_scoreable': scoreable,
            'errors': errors, 'unscoreable': categories.count('unscoreable'),
            'abstain': categories.count('abstain'), 'invalid': categories.count('invalid'),
            'failed': categories.count('failed'),
            'coverage': accepted / submitted if submitted else None,
            'selective_risk': errors / scoreable if scoreable else None,
            'class_counts': dict(counts),
            'complete_fabrication_rate': None}
