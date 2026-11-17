"""Independent, post-run classification of the recorded scalar trajectory.

No sequence ID, probe timing, predictor output, or scheduler import is needed.
The gold target is the signal driven by the recorded applied commands on the
recorded model clock. The checkpoints are outputs of that same program.
"""
from fractions import Fraction
import math


BOUND = Fraction(-3, 4)
VALUE_TOL = Fraction(1, 10**12)
TIME_FIELDS = ('unit_ns', 's1_ns', 'apply1_ns', 's2_ns', 'apply2_ns', 'end_ns')
FLOAT_FIELDS = ('u1', 'u2', 's1', 's2', 'x_read1', 'x_read2', 'x_end', 'x_min')


def _integer(value):
    if type(value) not in (int, str):
        raise ValueError('timestamp or unit is not an integer')
    return int(value)


def _recorded_double(value):
    # Round-trip the 17-digit native binary64 serialization before doing
    # exact rational arithmetic. Infinity/NaN have no plant semantics here.
    if isinstance(value, bool):
        raise ValueError('Boolean in numeric field')
    number = float(value)
    if not math.isfinite(number):
        raise ValueError('non-finite command or plant checkpoint')
    return Fraction.from_float(number)


def _tolerance(value):
    return VALUE_TOL * (1 + abs(value))


def evaluate(row):
    """Return VERIFIED, UNCERTAIN (missing input or boundary), or INVALID."""
    result = {'status': 'INVALID', 'verdict': None, 'reasons': []}
    required = TIME_FIELDS + FLOAT_FIELDS
    absent = [key for key in required if key not in row or row[key] is None or row[key] == '']
    if absent:
        return dict(result, status='UNCERTAIN', reasons=['missing ' + ', '.join(absent)])
    try:
        unit, t1, a1, t2, a2, end = (_integer(row[key]) for key in TIME_FIELDS)
        if unit <= 0 or not 0 <= t1 <= a1 <= t2 <= a2 <= end:
            raise ValueError('nonpositive unit or impossible sample/apply/end order')
        values = {key: _recorded_double(row[key]) for key in FLOAT_FIELDS}

        # Integrate separately from the native sample-by-sample double loop.
        # Timestamps are actual model times in ns, including any lateness.
        def dt(later, earlier):
            return Fraction(later - earlier, unit)

        x0, u0 = Fraction(1), Fraction(-1, 2)
        xa = x0 + u0 * dt(a1, 0)
        xb = xa + values['u1'] * dt(a2, a1)
        xe = xb + values['u2'] * dt(end, a2)
        extremum, when = min(((x0, 0), (xa, a1), (xb, a2), (xe, end)))
        reconstructed = {
            's1': x0 + u0 * dt(t1, 0), 'x_read1': xa,
            's2': xa + values['u1'] * dt(t2, a1), 'x_read2': xb,
            'x_end': xe, 'x_min': extremum,
        }
        margin = extremum - BOUND
        result.update(minimum=str(extremum), minimum_ns=when, margin=str(margin),
                      derived={key: str(val) for key, val in reconstructed.items()})
        for key, expected in reconstructed.items():
            if abs(values[key] - expected) > _tolerance(expected):
                raise ValueError(f'{key} inconsistent with recorded times and applied commands')
        # Every segment is affine. No smaller minimum exists between the
        # initial state, the two command applications and the terminal state.
        if abs(margin) <= _tolerance(extremum):
            return dict(result, status='UNCERTAIN', reasons=['minimum within numeric review band'])
        return dict(result, status='VERIFIED', verdict='SAT' if margin > 0 else 'VIOL')
    except (ValueError, TypeError, OverflowError) as exc:
        result['reasons'].append(str(exc))
        return result


def compare_diagnostic(lean_row, timed_row):
    """Compare gold labels under matching inputs, including uncertain pairs."""
    keys = ('pair_id', 'arm', 'policy', 'unit_ns', 'lead1_ns', 'lead2_ns', 'batch1', 'batch2')
    matched = (lean_row.get('reference') == 'lean' and timed_row.get('reference') == 'timed'
               and all(key in lean_row and key in timed_row
                       and str(lean_row[key]) == str(timed_row[key]) for key in keys))
    lean, timed = evaluate(lean_row), evaluate(timed_row)
    both = matched and lean['status'] == timed['status'] == 'VERIFIED'
    return {'matched': matched, 'lean': lean, 'timed': timed,
            'flip': lean['verdict'] != timed['verdict'] if both else None}


def self_check():
    # Hand-calculated sign reversal: end x=-0.25, earlier minimum x=-0.5.
    base = dict(unit_ns=1000, s1_ns=1000, apply1_ns=2000, s2_ns=2500,
                apply2_ns=3000, end_ns=4000, u1=-0.5, u2=0.25, s1=0.5,
                s2=-0.25, x_read1=0, x_read2=-0.5, x_end=-0.25, x_min=-0.5)
    sat = evaluate(base)
    assert sat['verdict'] == 'SAT' and sat['minimum_ns'] == 3000
    late = dict(base, s1_ns=900, apply1_ns=2100, s2_ns=2600, apply2_ns=3100,
                end_ns=4200, s1=.55, u1=-1, u2=.55, s2=-.55, x_read1=-.05,
                x_read2=-1.05, x_end=-.445, x_min=-1.05)
    assert evaluate(late)['verdict'] == 'VIOL'
    # Exactly touching, with every checkpoint consistent.
    equal = dict(base, u2=-.25, x_end=-.75, x_min=-.75)
    assert evaluate(equal)['status'] == 'UNCERTAIN'
    for wrong in (dict(base, u2=-.25), dict(base, x_min=-.25), dict(base, x_end='nan'),
                  dict(base, apply2_ns=200), dict(base, unit_ns=0)):
        assert evaluate(wrong)['status'] == 'INVALID'
    assert evaluate({key: value for key, value in base.items() if key != 'u2'})['status'] == 'UNCERTAIN'
    assert evaluate(dict(base, seq1=999, seq2='bad', read1_hi_ns=-1, prediction='VIOL')) == sat
    inputs = dict(pair_id='fixture', arm='off', policy='shared', lead1_ns=0, lead2_ns=0,
                  batch1=0, batch2=1)
    pair = compare_diagnostic(dict(base, reference='lean', **inputs), dict(late, reference='timed', **inputs))
    assert pair['matched'] and pair['flip']


if __name__ == '__main__':
    self_check()
    print('gold reference self-check passed')
