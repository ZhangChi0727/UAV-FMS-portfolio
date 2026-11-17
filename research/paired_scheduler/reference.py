"""Independent reference for the two-update host experiment.

Reconstruct order from timed brackets, and the continuous piecewise affine
state from the actual sample/command times. No scheduler code is imported.
All reported rational values are strings to allow lossless JSON serialization.
"""
from fractions import Fraction as F


BOUND = F(-3, 4)
# Native double serialisation is checked with absolute plus relative tolerance.
VALUE_TOL = F(1, 10**12)
READ_FIELDS = ('s1', 's2', 'u1', 'u2', 'x_read1', 'x_read2', 'x_end', 'x_min')


def _integer(row, name):
    value = row[name]
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError(f'{name} is not an integer')
    return int(value)


def _possible_sources(publications, read, guard):
    """Publication IDs monotonically increase on a single producer thread."""
    possible = []
    for seq in range(len(publications) + 1):
        for packet, (lo, hi) in enumerate(publications, start=1):
            before = hi + guard < read[0]
            after = read[1] + guard < lo
            if (packet > seq and before) or (packet <= seq and after):
                break
        else:
            possible.append(seq)
    return possible


def _integrate(times, seq1, seq2, unit):
    # Native timestamps are ns, and controller rates are per model time unit.
    def dt(later, earlier):
        return F(later - earlier, unit)

    ts1, tr1, ts2, tr2, end = times
    x0, slope0 = F(1), F(-1, 2)
    s1 = x0 + slope0 * dt(ts1, 0)
    xr1 = x0 + slope0 * dt(tr1, 0)
    u1 = -(x0, s1)[seq1]
    s2 = xr1 + u1 * dt(ts2, tr1)
    xr2 = xr1 + u1 * dt(tr2, tr1)
    u2 = -(x0, s1, s2)[seq2]
    xe = xr2 + u2 * dt(end, tr2)
    # Minimum over a continuous affine segment occurs at either endpoint.
    minimum, minimum_ns = min((x0, 0), (xr1, tr1), (xr2, tr2), (xe, end))
    return dict(zip(READ_FIELDS, (s1, s2, u1, u2, xr1, xr2, xe, minimum))), minimum_ns


def evaluate(row, clock_guard_ns=None):
    """Classify a single raw CSV row. A verified row has an independent order."""
    result = {'status': 'INVALID', 'verdict': None, 'reasons': []}
    try:
        if clock_guard_ns is None:
            guard = _integer(row, 'clock_guard_ns')
        else:
            guard = clock_guard_ns
            if 'clock_guard_ns' in row:
                guard = max(guard, _integer(row, 'clock_guard_ns'))
        if isinstance(guard, bool) or not isinstance(guard, int) or guard < 1:
            raise ValueError('clock guard must cover at least one counter tick')
        frequency = _integer(row, 'qpc_frequency_hz')
        if frequency <= 0 or guard < ((10**9 + frequency - 1) // frequency + 1):
            raise ValueError('clock guard too small for counter frequency and tick rounding')
        result['clock_guard_ns'] = guard
        unit = _integer(row, 'unit_ns')
        if unit <= 0:
            raise ValueError('nonpositive model time unit')

        reads, pubs, work_starts = [], [], []
        for i in (1, 2):
            read = tuple(_integer(row, f'read{i}_{end}_ns') for end in ('lo', 'hi'))
            pub = tuple(_integer(row, f'pub{i}_{end}_ns') for end in ('lo', 'hi'))
            work = tuple(_integer(row, f'work{i}_{end}_ns') for end in ('lo', 'hi'))
            sample = _integer(row, f's{i}_ns')
            due = _integer(row, f'due{i}_ns')
            if due != (i+1) * unit - _integer(row, f'lead{i}_ns'):
                raise ValueError(f'due time {i} disagrees with trial input')
            if not (0 <= work[0] <= work[1] <= pub[0] <= pub[1]):
                raise ValueError(f'invalid producer order {i}')
            if work[0] + guard < due or work[0] + guard < sample:
                raise ValueError(f'producer work {i} precedes release or sample')
            if not 0 <= read[0] <= read[1]:
                raise ValueError(f'invalid read bracket {i}')
            reads.append(read)
            pubs.append(pub)
            work_starts.append(work[0])
        if pubs[0][1] > work_starts[1]:
            raise ValueError('single producer work/publication brackets out of order')

        t1, t2, end = (_integer(row, k) for k in ('s1_ns', 's2_ns', 'end_ns'))
        if not (0 <= t1 <= reads[0][0] <= reads[0][1] <= t2 <=
                reads[1][0] <= reads[1][1] <= end):
            raise ValueError('main-thread sample/read/end chronology invalid')
        possibilities = [_possible_sources(pubs, read, guard) for read in reads]
        # Sample 2 is taken by the consumer thread after read 1. It cannot
        # be the source at read 1, regardless of timer rounding.
        possibilities[0] = [seq for seq in possibilities[0] if seq < 2]
        seqs = [_integer(row, f'seq{i}') for i in (1, 2)]
        result.update(possible_sources=possibilities, observed_seq=seqs)
        if seqs[0] > seqs[1] or any(seq not in allowed for seq, allowed
                                    in zip(seqs, possibilities)):
            raise ValueError('logged read inconsistent with publication/reader chronology')

        values, minimum_ns = _integrate((t1, reads[0][1], t2, reads[1][1], end),
                                        *seqs, unit)
        for key, expected in values.items():
            serialized = F(str(row[key]))
            if abs(serialized - expected) > VALUE_TOL * (1 + abs(expected)):
                raise ValueError(f'{key}: emitted {row[key]}, reconstructed {expected}')
        margin = values['x_min'] - BOUND
        serialized_margin = F(str(row['x_min'])) - BOUND
        if (margin < 0) != (serialized_margin < 0):
            raise ValueError('emitted minimum and exact minimum imply different verdicts')
        result.update(derived={k: str(v) for k, v in values.items()},
                      minimum_ns=minimum_ns, margin=str(margin),
                      beyond_value_tolerance=abs(margin) > VALUE_TOL * (1+abs(values['x_min'])),
                      read_minus_publish_ns=[
                          [read[0]-pub[1], read[1]-pub[0]]
                          for read, pub in zip(reads, pubs)])
        if any(len(allowed) != 1 for allowed in possibilities):
            result.update(status='AMBIGUOUS_ORDER', reasons=['source order unresolved by brackets'])
        else:
            result.update(status='VERIFIED', verdict='SAT' if margin >= 0 else 'VIOL')
    except (KeyError, ValueError, TypeError, ZeroDivisionError, OverflowError) as exc:
        result['reasons'].append(str(exc))
    return result


def evaluate_pair(bare_row, probe_row, clock_guard_ns=None):
    """Return a measured verdict difference only for two valid matched rows."""
    bare = evaluate(bare_row, clock_guard_ns)
    probe = evaluate(probe_row, clock_guard_ns)
    keys = ('pair_id', 'unit_ns', 'lead1_ns', 'lead2_ns')
    paired = (bare_row.get('arm') == 'off' and probe_row.get('arm') in ('off', 'light', 'stress')
              and all(str(bare_row.get(k)) == str(probe_row.get(k))
                      and k in bare_row and k in probe_row for k in keys))
    comparable = paired and bare['status'] == probe['status'] == 'VERIFIED'
    report = {'bare': bare, 'probe': probe, 'paired_inputs': paired, 'flip': None,
              'primary_flip': None, 'strong_flip': None}
    if not comparable:
        return report
    flip = bare['verdict'] != probe['verdict']
    qualifying_reads, spanning_reads = [], []
    guard = probe['clock_guard_ns']
    for i, (before, after) in enumerate(zip(bare['observed_seq'], probe['observed_seq']), 1):
        change = F(bare['derived'][f'u{i}']) - F(probe['derived'][f'u{i}'])
        if before != after and abs(change) > F(1, 8):
            qualifying_reads.append(i)
            spans = (_integer(probe_row, f'work{i}_lo_ns') + guard < _integer(probe_row, f'read{i}_lo_ns')
                     and _integer(probe_row, f'read{i}_hi_ns') + guard < _integer(probe_row, f'work{i}_hi_ns'))
            if probe_row['arm'] != 'off' and before == i and after < i and spans:
                spanning_reads.append(i)
    return dict(report, flip=flip, primary_flip=flip and bool(qualifying_reads),
                strong_flip=flip and bool(spanning_reads), qualifying_reads=qualifying_reads,
                spanning_reads=spanning_reads)


def self_check():
    # Hand-built data in model units. No scheduler or inspection of campaign data.
    bare = dict(pair_id='fixture', arm='off', unit_ns=1000, lead1_ns=200, lead2_ns=200,
                qpc_frequency_hz=10**9, clock_guard_ns=2, s1_ns=1000, s2_ns=2500, end_ns=4000,
                due1_ns=1800, due2_ns=2800, read1_lo_ns=1999, read1_hi_ns=2000,
                read2_lo_ns=2999, read2_hi_ns=3000, work1_lo_ns=1800, work1_hi_ns=1895,
                pub1_lo_ns=1900, pub1_hi_ns=1905, work2_lo_ns=2800, work2_hi_ns=2895,
                pub2_lo_ns=2900, pub2_hi_ns=2905, seq1=1, seq2=2, s1='0.5', s2='-0.25',
                u1='-0.5', u2='0.25', x_read1='0', x_read2='-0.5', x_end='-0.25', x_min='-0.5')
    probe = dict(bare, arm='light', work1_hi_ns=2040, pub1_lo_ns=2050, pub1_hi_ns=2055,
                 seq1=0, u1='-1', s2='-0.5', u2='0.5', x_read2='-1', x_end='-0.5', x_min='-1')
    result = evaluate_pair(bare, probe)
    assert result['strong_flip'] and result['spanning_reads'] == [1], result
    assert evaluate(dict(bare, pub1_hi_ns=1998))['status'] == 'AMBIGUOUS_ORDER'
    assert evaluate(dict(bare, seq1=0))['status'] == 'INVALID'
    assert evaluate(dict(bare, u2='-0.25'))['status'] == 'INVALID'
    assert evaluate(dict(probe, x_min='-0.5'))['status'] == 'INVALID'
    assert evaluate(dict(bare, clock_guard_ns=1))['status'] == 'INVALID'
    assert not evaluate_pair(bare, bare)['flip']


if __name__ == '__main__':
    self_check()
    print('independent reference self-check passed')
