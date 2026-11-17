"""Matched measurements of the optional 4-byte write and host run costs."""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import platform
from statistics import median
import sys
from time import get_clock_info, perf_counter_ns

if __package__:
    from .field_sink import FIELD, sham_field, write_field
else:
    from field_sink import FIELD, sham_field, write_field


def _stats(values):
    return {'n': len(values), 'min': min(values), 'median': median(values), 'max': max(values)} if values else {'n': 0}


def _timed_batch(operation, values):
    # Allocate and check outside the timing window. Only the call, loop, and
    # data access are in the window; both paths receive the same value stream.
    target = bytearray(b'\xff' * FIELD.size)
    start = perf_counter_ns()
    for value in values:
        operation(target, value)
    duration = perf_counter_ns() - start
    expected = FIELD.pack(values[-1]) if operation is write_field else b'\xff' * FIELD.size
    if target != expected:
        raise ValueError('incorrect final field bytes')
    return duration


def benchmark(pairs=32, calls=32768):
    if pairs < 2 or pairs % 2 or calls < 1:
        raise ValueError('positive calls and an even number of at least two pairs required')
    values = tuple(i % 3 for i in range(calls))
    for operation in (sham_field, write_field, write_field, sham_field):
        _timed_batch(operation, values)
    samples = []
    operations = {'none': sham_field, 'one': write_field}
    for index in range(pairs):
        order = ('none', 'one') if index % 2 == 0 else ('one', 'none')
        elapsed = {name: _timed_batch(operations[name], values) for name in order}
        samples.append(dict(order=list(order), **elapsed,
                            paired_ns_per_call=(elapsed['one'] - elapsed['none']) / calls))
    clock = get_clock_info('perf_counter')
    if min(min(s['one'], s['none']) for s in samples) <= math.ceil(clock.resolution * 10**9):
        raise RuntimeError('batch did not resolve clock granularity')
    return dict(pairs=pairs, calls_per_path_per_pair=calls, clock=clock.implementation,
                clock_resolution_ns=clock.resolution*10**9,
                python=sys.version, platform=platform.platform(),
                one_payload_bytes_per_call=FIELD.size, sham_payload_bytes_per_call=0,
                one_bytes_written_per_batch=FIELD.size*calls,
                retained_buffer_bytes_per_batch=FIELD.size, samples=samples,
                paired_ns_per_call=_stats([s['paired_ns_per_call'] for s in samples]),
                one_ns_per_call=_stats([s['one']/calls for s in samples]),
                sham_ns_per_call=_stats([s['none']/calls for s in samples]))


def summarize_pairs(rows):
    """For matched none/one arms retain signed differences, including negatives."""
    groups = defaultdict(list)
    for row in rows:
        groups[row['pair_id']].append(row)
    details = []
    for pair_id, items in groups.items():
        codes = [row['field'] for row in items]
        if sorted(codes) != ['none', 'one']:
            raise ValueError(f'{pair_id}: expected exactly one row per field mode, got {codes}')
        a, b = sorted(items, key=lambda row: row['field'])
        for key in ('policy', 'chosen_read', 'unit_ns'):
            if a[key] != b[key]:
                raise ValueError(f'{pair_id}: unmatched {key}')
        for row in (a,b):
            width = 0 if row['field'] == 'none' else FIELD.size
            if int(row['field_bytes']) != width or len(bytes.fromhex(row['field_hex'])) != width:
                raise ValueError(f'{pair_id}: field payload width inconsistent')
            if int(row['field_lo_ns']) > int(row['field_hi_ns']):
                raise ValueError(f'{pair_id}: invalid field call interval')
        def window(row):
            return int(row['field_hi_ns']) - int(row['field_lo_ns'])
        details.append(dict(pair_id=pair_id, policy=a['policy'], chosen_read=a['chosen_read'],
                            none_window_ns=window(a), one_window_ns=window(b),
                            call_delta_ns=window(b)-window(a),
                            trial_delta_ns=int(b['trial_wall_ns'])-int(a['trial_wall_ns']),
                            horizon_delta_ns=int(b['end_ns'])-int(a['end_ns']),
                            field_bytes_delta=int(b['field_bytes'])-int(a['field_bytes'])))
    return dict(rows=sum(map(len, groups.values())), pairs=len(details), detail=details,
                distributions={key: _stats([p[key] for p in details])
                               for key in ('call_delta_ns', 'trial_delta_ns', 'horizon_delta_ns',
                                           'field_bytes_delta')})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    with args.output.open('x', encoding='utf-8') as output:
        json.dump(benchmark(), output, indent=2)
        output.write('\n')
