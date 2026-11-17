"""Supplemental paired TCP service-cost experiment for a compact log sink.

Frames are pre-encoded. The timed window runs from the publisher's first
send to its receipt of a local acknowledgement that all batch records were
verified by the subscriber. This is a batch service measurement.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform
from queue import Queue
from statistics import median
from struct import Struct
from threading import Thread
from time import get_clock_info, perf_counter_ns

import zmq

if __package__:
    from .field_sink import write_field
else:
    from field_sink import write_field


TOPIC = b'log/'
SEQ = Struct('<I')
N_MESSAGES = 2048
N_PAIRS = 24
TIMEOUT_MS = 8000


def _build_frames():
    base, extra = [], []
    sink = bytearray(4)
    for i in range(N_MESSAGES):
        # Same synthetic base log record for matched message i on both paths.
        frame = TOPIC + SEQ.pack(i) + b'K' * 16
        base.append(frame)
        write_field(sink, i % 3)
        extra.append(frame + bytes(sink))
    return {'none': base, 'one': extra}


def _stats(vals):
    return dict(min=min(vals), median=median(vals), max=max(vals))


def run():
    layouts = _build_frames()
    orders = [('none', 'one') if i % 2 == 0 else ('one', 'none') for i in range(N_PAIRS)]
    warm = ['none', 'one', 'one', 'none']
    modes = warm + [mode for order in orders for mode in order]
    markers = [TOPIC + b'END!' + SEQ.pack(i) for i in range(len(modes))]
    batches = []
    ack = Queue()
    with zmq.Context() as ctx, ctx.socket(zmq.XPUB) as publisher:
        publisher.linger = 0
        publisher.sndhwm = 2*N_MESSAGES
        publisher.sndtimeo = TIMEOUT_MS
        publisher.rcvtimeo = TIMEOUT_MS
        publisher.setsockopt(zmq.XPUB_NODROP, 1)
        port = publisher.bind_to_random_port('tcp://127.0.0.1')

        def receive():
            try:
                with ctx.socket(zmq.SUB) as subscriber:
                    subscriber.linger = 0
                    subscriber.rcvhwm = 2*N_MESSAGES
                    subscriber.rcvtimeo = TIMEOUT_MS
                    subscriber.setsockopt(zmq.SUBSCRIBE, TOPIC)
                    subscriber.connect(f'tcp://127.0.0.1:{port}')
                    for i, mode in enumerate(modes):
                        for expected in layouts[mode]:
                            if subscriber.recv() != expected:
                                raise ValueError(f'batch {i} missing, reordered, or wrong bytes')
                        if subscriber.recv() != markers[i]:
                            raise ValueError(f'batch {i} marker mismatch')
                        ack.put(i)
            except Exception as error:
                ack.put(error)

        receiver = Thread(target=receive, daemon=True)
        receiver.start()
        try:
            if publisher.recv() != b'\x01' + TOPIC:
                raise ValueError('subscription handshake failed')
            for i, mode in enumerate(modes):
                started = perf_counter_ns()
                for frame in layouts[mode]:
                    publisher.send(frame)
                publisher.send(markers[i])
                receipt = ack.get(timeout=TIMEOUT_MS / 1000)
                duration = perf_counter_ns() - started
                if isinstance(receipt, Exception):
                    raise RuntimeError('subscriber could not verify batch') from receipt
                if receipt != i:
                    raise ValueError('wrong receiver acknowledgement')
                batches.append(dict(mode=mode, duration_ns=duration,
                                    messages=N_MESSAGES, marker_bytes=len(markers[i]),
                                    data_payload_bytes=N_MESSAGES*len(layouts[mode][0])))
        finally:
            receiver.join(timeout=TIMEOUT_MS / 1000 + 1)
            if receiver.is_alive():
                raise RuntimeError('subscriber did not terminate')
    samples = []
    for i, order in enumerate(orders):
        pair = {b['mode']: b for b in batches[len(warm)+2*i:len(warm)+2*i+2]}
        delta = pair['one']['duration_ns'] - pair['none']['duration_ns']
        samples.append(dict(order=order, none=pair['none'], one=pair['one'],
                            delta_ns=delta, delta_ns_per_message=delta/N_MESSAGES))
    deltas = [s['delta_ns_per_message'] for s in samples]
    return dict(design='Supplemental post-design TCP loopback piggyback service-cost comparison',
                endpoint_scope='127.0.0.1 only', socket_types='XPUB/SUB',
                preencoded=True, handshake_verified=True, validated_all_records=True,
                local_ack_after_all_frames=True, high_water_mark=2*N_MESSAGES,
                timing_definition='publisher first send through subscriber whole-frame byte comparisons and local ack; includes end marker',
                cost_scope='application record payload; TCP/IP and ZeroMQ wire overhead unmeasured',
                platform=platform.platform(), pyzmq=zmq.__version__, libzmq=zmq.zmq_version(),
                clock_resolution_ns=get_clock_info('perf_counter').resolution*1e9,
                record_width={m: len(frames[0]) for m, frames in layouts.items()},
                common_marker_bytes=len(markers[0]), payload_bytes_delta_per_message=4,
                per_layout_sha256={m: sha256(b''.join(frames)).hexdigest() for m, frames in layouts.items()},
                pairs=N_PAIRS, records_per_batch=N_MESSAGES, warmup=batches[:len(warm)],
                samples=samples, delta_ns_per_message=_stats(deltas),
                positive=sum(d > 0 for d in deltas), negative=sum(d < 0 for d in deltas),
                zero=sum(d == 0 for d in deltas), per_order={str(order): _stats(
                    [s['delta_ns_per_message'] for s in samples if s['order']==order])
                    for order in set(orders)})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output already exists')
    result = run()
    with args.output.open('x', encoding='utf-8') as out:
        json.dump(result, out, indent=2)
        out.write('\n')
