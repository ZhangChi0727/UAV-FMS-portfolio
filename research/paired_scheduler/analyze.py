"""Audit the complete run plans, reconstruct all runs, summarize matched pairs."""
import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

from reference import evaluate, evaluate_pair


def rows(path):
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def covered_run(raw):
    ref = evaluate(raw)
    measurements = []
    for i in (1, 2):
        def n(prefix):
            return int(raw[prefix.format(i=i)])
        lo = n("read{i}_lo_ns") - n("pub{i}_hi_ns")
        hi = n("read{i}_hi_ns") - n("pub{i}_lo_ns")
        guard = int(raw["clock_guard_ns"])
        size = {"light":1024,"stress":262144,"off":0}[raw["arm"]]
        if int(raw[f"bytes{i}"]) != size or (int(raw[f"digest{i}"]) == 0) != (size == 0):
            raise ValueError("Trace work counter or digest contradicts the assigned load")
        measurements.append(dict(
            gap_lo_ns=lo, gap_hi_ns=hi,
            work_ns=n("work{i}_hi_ns")-n("work{i}_lo_ns"),
            release_lateness_ns=n("work{i}_lo_ns")-(i+1)*int(raw["unit_ns"])+n("lead{i}_ns"),
            read_inside_work=(n("work{i}_lo_ns")+guard < n("read{i}_lo_ns") and
                              n("read{i}_hi_ns")+guard < n("work{i}_hi_ns"))))
    return dict(run_id=raw["run_id"], reference=ref, reads=measurements)


def pair_result(a, b):
    paired = evaluate_pair(a, b)
    if not paired["paired_inputs"]:
        raise ValueError("Mismatched pair")
    result = dict(verified=False, changed_read=None, changed_feedback=None, verdict_flip=None,
                  chain=None, covered_chain=None, sat_to_viol=None, reasons=[])
    refs = [paired["bare"], paired["probe"]]
    if any(r["status"] != "VERIFIED" for r in refs):
        result["reasons"] = [r["status"] for r in refs]
        return result
    ra, rb = refs
    switched = [i for i in (0,1) if ra["observed_seq"][i] != rb["observed_seq"][i]]
    result.update(verified=True, changed_read=bool(switched), changed_feedback=bool(paired["qualifying_reads"]),
                  verdict_flip=paired["flip"], chain=paired["primary_flip"],
                  covered_chain=paired["strong_flip"], sat_to_viol=ra["verdict"]=="SAT" and rb["verdict"]=="VIOL",
                  switched_reads=[i+1 for i in switched], covered_reads=paired["spanning_reads"])
    return result


def gap_prediction(bare, extra_ns):
    """Exploratory baseline: use only A's gap brackets and calibration medians."""
    guard = int(bare["clock_guard_ns"])
    reads = []
    for i in (1, 2):
        lo = int(bare[f"read{i}_lo_ns"]) - int(bare[f"pub{i}_hi_ns"])
        hi = int(bare[f"read{i}_hi_ns"]) - int(bare[f"pub{i}_lo_ns"])
        if lo > extra_ns + guard:
            reads.append("new")
        elif hi < extra_ns - guard:
            reads.append("old")
        else:
            reads.append("unresolved")
    # Nominal two-read decision derived in phase one; scheduler jitter can violate it.
    if "old" in reads:
        return "VIOL"
    return "SAT" if reads == ["new","new"] else "UNRESOLVED"


def audit(directory):
    calibration = json.loads((directory/"calibration_settings.json").read_text())["median_elapsed_ns"]
    runs, pairs, hashes = {}, {}, {}
    counters = defaultdict(Counter)
    populations = defaultdict(list)
    for batch in ("calibration","main1","main2"):
        paths = [directory/f"{batch}_{kind}.csv" for kind in ("plan","raw")]
        plan, data = [rows(p) for p in paths]
        for path in paths:
            hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        for setup, raw in zip(plan,data,strict=True):
            if any(raw[k] != value for k,value in setup.items()):
                raise ValueError(f"Plan mismatch: {setup}")
            rid = raw["run_id"]
            if rid in runs:
                raise ValueError(f"Repeated ID {rid}")
            run = covered_run(raw)
            runs[rid] = run
            if batch == "calibration":
                continue
            session, block, load, scene, side = rid.split("-")
            if int(session) != int(batch[-1]) or (raw["arm"] !=
                    ("off" if side=="A" or scene=="sham" else load)):
                raise ValueError(f"Unexpected session or arm {rid}")
            for i, item in enumerate(run["reads"],1):
                prefix = f"{load}.{scene}.{side}.read{i}."
                for key in ("work_ns","gap_lo_ns","gap_hi_ns","release_lateness_ns"):
                    populations[prefix+key].append(item[key])
            if side not in ("A","B"):
                raise ValueError(rid)
            pairs.setdefault(raw["pair_id"], {})[side] = raw
    details = {}
    for pid, ids in pairs.items():
        session, block, load, scene = pid.split("-")
        result = pair_result(ids["A"],ids["B"])
        extra = calibration[ids["B"]["arm"]] - calibration["off"]
        prediction = gap_prediction(ids["A"], extra)
        reference = runs[ids["B"]["run_id"]]["reference"]
        result["gap_prediction"] = prediction
        result["gap_prediction_matches"] = (prediction == reference["verdict"]
                if result["verified"] and prediction != "UNRESOLVED" else None)
        order = "".join(ids.keys())  # insertion order from the actual output file
        details[pid] = dict(order=order, **result)
        for key in (f"{load}.{scene}", f"session.{session}.{load}.{scene}",
                    f"order.{order}.{load}.{scene}"):
            count = counters[key]
            count["all"] += 1
            for metric in ("verified","changed_read","changed_feedback","verdict_flip",
                           "chain","covered_chain","sat_to_viol"):
                count[metric] += int(bool(result[metric]))
    if len(details)!=96 or len(runs)!=228:
        raise ValueError("Incomplete experiment")
    for name, count in counters.items():
        expected = 4 if name.startswith(("session.","order.")) else 8
        if count["all"] != expected:
            raise ValueError(f"Unbalanced {name}")
    for rid,run in runs.items():
        if run["reference"]["status"]=="INVALID":
            print("INVALID",rid,run["reference"]["reasons"])
    stats = {k:dict(n=len(v),min=min(v),median=median(v),max=max(v)) for k,v in populations.items()}
    return dict(file_sha256=hashes, run_status=Counter(v["reference"]["status"] for v in runs.values()),
                groups=dict(counters), measurements_ns=stats, pairs=details, runs=runs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args=parser.parse_args()
    report=audit(args.directory)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=1)+"\n",encoding="utf-8")
    print("Run status",report["run_status"])
    for key,cnt in sorted(report["groups"].items()):
        if not key.startswith(("order.","session.")):
            print(key,dict(cnt))
