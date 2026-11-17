"""Loopback XPUB/SUB transport experiment. Usage: transport.py PLAN.jsonl OUTPUT.jsonl."""
import hashlib
import json
import math
import os
import queue
import struct
import sys
import threading
import time
from pathlib import Path

import zmq

from field_sink import sham_field, write_field


ORDER = struct.Struct("<I")
STATE = struct.Struct("<Bd")
CAP = 65536


def wait_until(deadline):
    while True:
        remaining = deadline - time.perf_counter_ns()
        if remaining <= 0:
            return
        time.sleep((remaining - 200_000) / 1e9 if remaining > 400_000 else 0)


def build_jobs(plan):
    u = plan["unit_ns"]
    if not isinstance(u, int) or not 100_000 <= u <= 1_000_000_000:
        raise ValueError("unit_ns must be an integer in [100 us,1 s]")
    if plan["field"] not in ("none", "one") or plan["policy"] not in ("fifo", "latest"):
        raise ValueError("unknown field or policy")
    if plan["chosen_read"] not in (1, 2):
        raise ValueError("chosen_read must be 1 or 2")
    if len(plan["states"]) + len(plan["traffic"]) + 2 >= CAP:
        raise ValueError("window exceeds declared queue capacity")
    jobs = []
    for event in plan["states"]:
        t, seq = event["offset_ns"], event["seq"]
        if not isinstance(t, int) or not u <= t <= 4*u or seq != (1 if 2*t < 5*u else 2):
            raise ValueError("invalid state release")
        jobs.append((t, b"S", seq))
    traffic_bytes = 0
    for i, event in enumerate(plan["traffic"]):
        t, size = event["offset_ns"], event["size_bytes"]
        if not isinstance(t, int) or not 0 <= t <= 4*u or not isinstance(size, int) or not 0 <= size <= 65535:
            raise ValueError("invalid traffic release")
        traffic_bytes += size
        if traffic_bytes > 32*1024*1024:
            raise ValueError("traffic budget exceeded")
        if "payload_hex" in event:
            body = bytes.fromhex(event["payload_hex"])
            if len(body) != size:
                raise ValueError("traffic size disagrees with supplied payload")
        else:
            # Trace exposes size/timing; wire traffic uses deterministic substitute bytes.
            body = bytes([i % 256]) * size
        jobs.append((t, b"B", body))
    return sorted(jobs, key=lambda job: job[0])  # equal-release states before background


def trace_one(plan):
    jobs = build_jobs(plan)
    start_wall = time.perf_counter_ns()
    start_cpu = time.process_time_ns()
    start_control_cpu = time.thread_time_ns()
    unit = plan["unit_ns"]
    prefix = hashlib.sha256(plan["run_id"].encode()).digest()[:12] + b"/"
    header = len(prefix)
    sink = bytearray(4)
    field_call = write_field if plan["field"] == "one" else sham_field
    # Two independent socket owners. Thread channels carry endpoint, epoch and
    # sample availability, never delivery or consumption decisions.
    ctx = zmq.Context()
    address, epoch_queue = queue.Queue(), queue.Queue()
    ack_tail = threading.Event()
    sample_ready = [threading.Event(), threading.Event()]
    samples = [None, None]
    sent, received, failures = [], [], []
    row = {k: v for k, v in plan.items() if k not in ("states", "traffic")}
    state_hash = hashlib.sha256(json.dumps(plan["states"], sort_keys=True).encode()).hexdigest()
    traffic_hash = hashlib.sha256(json.dumps(plan["traffic"], sort_keys=True).encode()).hexdigest()
    row.update(state_plan_sha256=state_hash, traffic_plan_sha256=traffic_hash)

    def publish():
        start_producer_cpu = time.thread_time_ns()
        try:
            with ctx.socket(zmq.XPUB) as pub:
                pub.linger = 0
                pub.sndhwm = CAP
                pub.sndtimeo = 5000
                pub.rcvtimeo = 5000
                pub.setsockopt(zmq.XPUB_NODROP, 1)
                port = pub.bind_to_random_port("tcp://127.0.0.1")
                address.put(f"tcp://127.0.0.1:{port}")
                if pub.recv() != b"\x01" + prefix:
                    raise RuntimeError("subscription notification did not match this run")
                pub.send(prefix + b"W")
                epoch = epoch_queue.get(timeout=5)
                for i, (offset, kind, content) in enumerate(jobs):
                    wait_until(epoch + offset)
                    if kind == b"S":
                        if not sample_ready[content-1].wait(5):
                            raise RuntimeError("sample unavailable")
                        body = STATE.pack(content, samples[content-1])
                    else:
                        body = content
                    packet = prefix + kind + ORDER.pack(i) + body
                    pub.send(packet)
                    sent.append(packet)
                pub.send(prefix + b"E")
                if not ack_tail.wait(8):
                    raise RuntimeError("receiver did not confirm end of stream")
        except Exception as err:
            failures.append(err)
        finally:
            row["publisher_thread_cpu_ns"] = time.thread_time_ns() - start_producer_cpu

    worker = threading.Thread(target=publish)
    worker.start()
    saw_end = False
    try:
        with ctx.socket(zmq.SUB) as sub:
            sub.linger = 0
            sub.rcvhwm = CAP
            sub.rcvtimeo = 5000
            sub.setsockopt(zmq.SUBSCRIBE, prefix)
            sub.connect(address.get(timeout=5))
            if sub.recv() != prefix + b"W":
                raise RuntimeError("subscriber warm-up failed")
            epoch = time.perf_counter_ns() + 2_000_000
            epoch_queue.put(epoch)
            now = lambda: time.perf_counter_ns() - epoch
            selected = (0, 1.0)
            x, rate, last, minimum = 1.0, -0.5, 0, 1.0

            def advance(t):
                nonlocal x, last, minimum
                x += rate * ((t - last) / unit)
                last = t
                minimum = min(minimum, x)

            def consume(packet):
                nonlocal saw_end
                if packet == prefix + b"E":
                    saw_end = True
                    return None
                if not packet.startswith(prefix) or saw_end:
                    raise RuntimeError("cross-run or post-end record")
                received.append(packet)
                if packet[header:header+1] == b"B":
                    return None
                if packet[header:header+1] != b"S":
                    raise RuntimeError("unrecognized data topic")
                return STATE.unpack_from(packet, header+1+ORDER.size)

            for read in (1, 2):
                wait_until(epoch + (unit if read == 1 else 5*unit//2))
                capture = now()
                advance(capture)
                row[f"s{read}_ns"], row[f"s{read}"] = capture, x
                samples[read-1] = x
                sample_ready[read-1].set()
                wait_until(epoch + (read+1)*unit)
                for _ in range(len(jobs)+2):
                    if saw_end:
                        break
                    try:
                        packet = sub.recv(flags=zmq.DONTWAIT)
                    except zmq.Again:
                        break
                    state = consume(packet)
                    if state is not None:
                        selected = state
                        if plan["policy"] == "fifo":
                            break
                next_rate = -selected[1]
                apply = now()
                advance(apply)
                rate = next_rate
                row[f"apply{read}_ns"], row[f"u{read}"], row[f"x_read{read}"] = apply, rate, x
                if read == plan["chosen_read"]:
                    before = now()
                    field_call(sink, selected[0])
                    after = now()
                    row.update(field_lo_ns=before, field_hi_ns=after)
            wait_until(epoch + 4*unit)
            end = now()
            advance(end)
            row.update(end_ns=end, x_end=x, x_min=minimum)
            received_at_end = len(received)
            while not saw_end:
                consume(sub.recv())
            ack_tail.set()
    finally:
        ack_tail.set()
        worker.join()
        ctx.term()
    if failures:
        raise RuntimeError("publisher failed") from failures[0]
    if not saw_end or sent != received or len(sent) != len(jobs):
        raise RuntimeError("transport dropped, substituted or reordered records")
    field = bytes(sink) if plan["field"] == "one" else b""
    digest = hashlib.sha256()
    for packet in received:
        digest.update(ORDER.pack(len(packet)))
        digest.update(packet)
    row.update(field_hex=field.hex(), field_bytes=len(field), state_messages=len(plan["states"]),
               traffic_messages=len(plan["traffic"]), traffic_payload_bytes=sum(e["size_bytes"] for e in plan["traffic"]),
               sent=len(sent), received=len(received), drained_after_control=len(received)-received_at_end,
               stream_sha256=digest.hexdigest(), integrity=True, hwm=CAP, subscription_ready=True,
               clock_guard_ns=math.ceil(time.get_clock_info("perf_counter").resolution*1e9)+1,
               pyzmq=zmq.__version__, libzmq=zmq.zmq_version(),
               controller_thread_cpu_ns=time.thread_time_ns()-start_control_cpu,
               process_cpu_ns=time.process_time_ns()-start_cpu,
               trial_wall_ns=time.perf_counter_ns()-start_wall)
    return row


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: transport.py PLAN.jsonl OUTPUT.jsonl")
    target = Path(sys.argv[2])
    part = target.with_name(target.name+".part")
    if target.exists():
        raise FileExistsError(target)
    with Path(sys.argv[1]).open(encoding="utf-8") as stream, part.open("x", encoding="utf-8") as output:
        for line in stream:
            if line.strip():
                output.write(json.dumps(trace_one(json.loads(line)), allow_nan=False)+"\n")
                output.flush()
    os.rename(part, target)


if __name__ == "__main__":
    main()
