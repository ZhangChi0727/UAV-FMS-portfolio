"""Extract relative-to-boot topic timestamps from the pinned PX4/pyulog fixture.

The extractor supports only this SHA-256-pinned, uncompressed ULog and the five
selected multi_id=0 topics. No vehicle measurements or positions are exported.
"""

import argparse
import csv
import hashlib
from pathlib import Path
import statistics
import struct


SOURCE_SHA256 = "81952e6059bc095717e7911c010e07f85749d6b04d332a5ffc51575a3fd0a558"
TOPICS = ("sensor_combined", "vehicle_attitude", "vehicle_rates_setpoint",
          "actuator_controls_0", "vehicle_attitude_setpoint")
WINDOW_US = (113_000_000, 143_000_000)


def read_topics(path):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError("ULog SHA-256 differs from the pinned fixture")
    if raw[:8] != b"ULog\x01\x12\x35\x00":
        raise ValueError("expected the ULog v0 fixture")
    formats = {}
    subscriptions = {}
    records = {topic: [] for topic in TOPICS}
    offset = 16
    ordinal = 0
    while offset < len(raw):
        size, record_type = struct.unpack_from("<Hc", raw, offset)
        offset += 3
        payload = raw[offset:offset + size]
        if len(payload) != size:
            raise ValueError("truncated message")
        offset += size
        if record_type == b"F":
            topic, fields = payload.decode("ascii").split(":", 1)
            formats[topic] = fields
        elif record_type == b"A":
            multi_id, msg_id = struct.unpack_from("<BH", payload)
            subscriptions[msg_id] = (payload[3:].decode("ascii"), multi_id)
        elif record_type == b"D":
            msg_id, = struct.unpack_from("<H", payload)
            topic, multi_id = subscriptions[msg_id]
            if topic in records and multi_id == 0:
                if not formats[topic].startswith("uint64_t timestamp;"):
                    raise ValueError(f"unexpected layout for {topic}")
                timestamp, = struct.unpack_from("<Q", payload, 2)
                records[topic].append((timestamp, size, ordinal))
        ordinal += 1
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ulog", type=Path)
    parser.add_argument("--out", type=Path, default=Path(__file__).with_name("trace.csv"))
    args = parser.parse_args()
    rows = []
    for topic, records in read_topics(args.ulog).items():
        timestamps = [record[0] for record in records]
        selected_records = [r for r in records if WINDOW_US[0] <= r[0] < WINDOW_US[1]]
        selected = [r[0] for r in selected_records]
        if len(selected) < 2 or selected != sorted(selected):
            raise ValueError(f"insufficient or nonmonotone timestamps for {topic}")
        gaps = [b-a for a, b in zip(selected, selected[1:])]
        print(f"{topic}: full={len(timestamps)} [{min(timestamps)},{max(timestamps)}] "
              f"window={len(selected)} [{selected[0]},{selected[-1]}] "
              f"window gap min/median/max={min(gaps)}/{statistics.median(gaps):g}/{max(gaps)} us")
        rows.extend((topic, *record) for record in selected_records)
    rows.sort(key=lambda row: (row[1], row[3]))
    with args.out.open("w", newline="", encoding="ascii") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(("topic", "timestamp_us", "ulog_payload_bytes", "ulog_record_ordinal"))
        writer.writerows(rows)
    print(f"rows={len(rows)} sha256={hashlib.sha256(args.out.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
