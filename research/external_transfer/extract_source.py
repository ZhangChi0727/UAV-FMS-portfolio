"""Extract timestamp-only replay inputs from one pinned public PX4 Flight Review ULog."""

import argparse
import csv
import hashlib
from pathlib import Path
import statistics
import struct


SOURCE_SHA = "9e0a1f07a19a8e482051577d43ec835e8b4a7d720d5ef1c047e74b92dcc68ce6"
WINDOW = (546_000_000, 666_000_000)
TOPICS = ("vehicle_attitude", "actuator_outputs", "vehicle_rates_setpoint",
          "sensor_combined", "vehicle_attitude_setpoint")


def extract(ulog):
    raw = ulog.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA or not raw.startswith(b"ULog\x01\x12\x35"):
        raise ValueError("Requires the SHA-pinned public Flight Review file")
    formats, subscriptions = {}, {}
    rows = []
    offset, ordinal = 16, 0
    while offset < len(raw):
        size, typ = struct.unpack_from("<Hc", raw, offset)
        payload = memoryview(raw)[offset + 3:offset + 3 + size]
        if len(payload) != size:
            raise ValueError("Truncated input")
        offset += 3 + size
        if typ == b"F":
            name, fields = bytes(payload).decode("ascii").split(":", 1)
            formats[name] = fields
        elif typ == b"A":
            multi, msg_id = struct.unpack_from("<BH", payload)
            subscriptions[msg_id] = (bytes(payload[3:]).decode("ascii"), multi)
        elif typ == b"D":
            msg_id, = struct.unpack_from("<H", payload)
            name, multi = subscriptions[msg_id]
            if multi == 0 and name in TOPICS:
                if not formats[name].startswith("uint64_t timestamp;"):
                    raise ValueError(f"Unexpected field layout for {name}")
                timestamp, = struct.unpack_from("<Q", payload, 2)
                if WINDOW[0] <= timestamp < WINDOW[1]:
                    rows.append((name, timestamp, size, ordinal))
        ordinal += 1
    return sorted(rows, key=lambda row: (row[1], row[3]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ulog", type=Path)
    parser.add_argument("--out", type=Path, default=Path(__file__).with_name("source.csv"))
    args = parser.parse_args()
    rows = extract(args.ulog)
    for topic in TOPICS:
        times = [r[1] for r in rows if r[0] == topic]
        gaps = [b-a for a,b in zip(times,times[1:])]
        print(topic, len(times), times[0], times[-1], min(gaps), statistics.median(gaps), max(gaps),
              sorted({r[2] for r in rows if r[0] == topic}))
    with args.out.open("w", encoding="ascii", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(("topic", "timestamp_us", "ulog_payload_bytes", "ulog_record_ordinal"))
        writer.writerows(rows)
    print(len(rows), hashlib.sha256(args.out.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
