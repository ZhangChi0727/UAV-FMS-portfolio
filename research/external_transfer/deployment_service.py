"""Positive-control subscription service calendar; wrapper for frozen NATS deployment.

Clock origin is Linux CLOCK_MONOTONIC zero, independent of trial epoch, releases,
reads, policy and evidence arm. W/E control messages are outside the calendar.
"""
from collections import Counter
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import deployment as base


PERIOD_NS = 4_492_000
OPEN_NS = PERIOD_NS // 4


def until_open(t):
    phase = t % PERIOD_NS
    return 0 if phase < OPEN_NS else PERIOD_NS - phase


def install():
    initial_message = base.Client.message
    initial_trial = base.trial
    stats = Counter()
    state_grants = {}

    def serviced_message(client):
        subject, body = initial_message(client)
        kind = subject.rsplit(b".", 1)[-1]
        if kind not in (b"S", b"B"):
            return subject, body
        entered = clock = base.NOW()
        initial_wait = until_open(clock)
        while until_open(clock):
            base.wait(clock + until_open(clock))
            clock = base.NOW()
        delay = clock - entered
        stats["data_count"] += 1
        stats["initially_closed_count"] += int(initial_wait > 0)
        stats["observed_gate_wait_total_ns"] += delay
        stats["observed_gate_wait_max_ns"] = max(stats["observed_gate_wait_max_ns"], delay)
        if kind == b"S":
            ordinal = base.ORDER.unpack_from(body)[0]
            state_grants[ordinal] = dict(initial_calendar_wait_ns=initial_wait,
                                         observed_gate_wait_ns=delay,
                                         grant_phase_ns=clock % PERIOD_NS)
        # Permission is granted at the sampled in-slot instant above. Subsequent
        # return, parsing and application enqueue are still scheduled by the OS.
        return subject, body

    def serviced_trial(plan, port, broker_pid):
        stats.clear()
        state_grants.clear()
        row = initial_trial(plan, port, broker_pid)
        if stats["data_count"] != row["received"]:
            raise RuntimeError("service calendar omitted a received data record")
        states = row["diagnostics"]["state_events"]
        if {event["ordinal"] for event in states} != set(state_grants):
            raise RuntimeError("state calendar and broker diagnostics disagree")
        for event in states:
            event.update(state_grants[event["ordinal"]])
        row["diagnostics"]["service_calendar"] = dict(
            period_ns=PERIOD_NS, open_ns=OPEN_NS, origin_monotonic_ns=0,
            data_count=stats["data_count"], initially_closed_count=stats["initially_closed_count"],
            observed_gate_wait_total_ns=stats["observed_gate_wait_total_ns"],
            observed_gate_wait_max_ns=stats["observed_gate_wait_max_ns"])
        return row

    base.Client.message = serviced_message
    base.trial = serviced_trial


if __name__ == "__main__":
    install()
    base.main()
