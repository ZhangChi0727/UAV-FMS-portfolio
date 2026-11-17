"""Apply the previous independent host-trajectory reference to the IPC trace.

Only the declared physical observation projection is visible to the evaluator.
This program has no dependency on the subscriber or the optional field sink.
"""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


_path = Path(__file__).resolve().parents[1] / 'scheduler_holdout' / 'reference.py'
_spec = spec_from_file_location('holdout_trajectory_evaluator', _path)
_old = module_from_spec(_spec)
_spec.loader.exec_module(_old)
GOLD_FIELDS = _old.TIME_FIELDS + _old.FLOAT_FIELDS


def evaluate(row):
    """Return an exact host-model minimum and an explicit evidence status."""
    projection = {field: row[field] for field in GOLD_FIELDS if field in row}
    return _old.evaluate(projection)


def self_check():
    _old.self_check()
    fixture = dict(unit_ns=1000, s1_ns=1000, apply1_ns=2000, s2_ns=2500,
                   apply2_ns=3000, end_ns=4000, u1=-0.5, u2=0.25, s1=0.5,
                   s2=-0.25, x_read1=0, x_read2=-0.5, x_end=-0.25, x_min=-0.5)
    gold = evaluate(fixture)
    assert gold['verdict'] == 'SAT'
    assert evaluate(dict(fixture, field_hex='ffffffff', field_bytes=4, queue='invalid',
                         seq1=99, seq2=-4, prediction='VIOL')) == gold
    assert evaluate(dict(fixture, u2='nan'))['status'] == 'INVALID'
    assert evaluate({key: val for key, val in fixture.items() if key != 'x_min'})['status'] == 'UNCERTAIN'


if __name__ == '__main__':
    self_check()
    print('physical projection self-check passed')
