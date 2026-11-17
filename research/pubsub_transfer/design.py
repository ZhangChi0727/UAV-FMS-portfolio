"""Release-only queue predictors and a deterministic sample of disjoint trace windows."""
import argparse
import csv
import json
from itertools import product
from pathlib import Path
import random

SOURCE_STATE = "vehicle_attitude"
READ_CLOCK = "actuator_controls_0"
SEED = 2026110404


def predict(row):
    """All nominal queue outcomes at the two reads (same-time delivery may go either way)."""
    u = row["unit_ns"]
    states = row["states"]
    histories = [(0, 0, ())]
    for deadline in (2*u, 3*u):
        first=sum(s["offset_ns"] < deadline for s in states)
        last=sum(s["offset_ns"] <= deadline for s in states)
        next_histories = []
        for consumed, held, readings in histories:
            for available in range(max(first,consumed),last+1):
                count=available if row["policy"]=="latest" else min(consumed+1,available)
                seq=states[count-1]["seq"] if count>consumed else held
                next_histories.append((count,seq,readings+(seq,)))
        histories=next_histories
    return sorted({r for _,_,r in histories})


def scores(row, actual=None):
    paths=predict(row)
    if actual is not None:
        # Observe one source, retain nominal alternatives for the other read,
        # including when the observed source contradicts the nominal model.
        i=row["chosen_read"]-1
        paths=[tuple(actual if j==i else v for j,v in enumerate(path)) for path in paths]
    labels={"SAT" if path==(1,2) else "VIOL" for path in paths}
    return labels.pop() if len(labels)==1 else "UNRESOLVED"


def burst_peak(offsets):
    """Max message count in a half-open 1 ms interval."""
    left=peak=0
    for right,instant in enumerate(offsets):
        while instant-offsets[left]>=1_000_000:
            left+=1
        peak=max(peak,right-left+1)
    return peak


def windows(path):
    with path.open(newline="") as f:
        rows=list(csv.DictReader(f))
    events=[(int(r["timestamp_us"]),r["topic"],int(r["ulog_payload_bytes"])) for r in rows]
    times=[t for t,topic,_ in events if topic==READ_CLOCK]
    candidates=[]
    until=events[0][0]
    for r1,r2 in zip(times,times[1:]):
        u=r2-r1
        origin=r1-2*u
        end=origin+4*u
        if u<=0 or origin<until or end>events[-1][0]:
            continue
        selected=[((t-origin)*1000,topic,size) for t,topic,size in events if origin<=t<end]
        states=[dict(offset_ns=t,seq=1 if t<2500*u else 2)
                for t,topic,size in selected if topic==SOURCE_STATE and t>=1000*u]
        traffic=[dict(offset_ns=t,size_bytes=size) for t,topic,size in selected
                 if topic not in (SOURCE_STATE,READ_CLOCK)]
        offsets=sorted([s["offset_ns"] for s in states]+[s["offset_ns"] for s in traffic])
        distances=[min((abs(s["offset_ns"]-k*u*1000) for s in states),default=4*u*1000)
                   for k in (2,3)]
        candidates.append(dict(origin_us=origin,unit_ns=u*1000,states=states,traffic=traffic,
                               chosen_read=distances.index(min(distances))+1,phase_distance_ns=min(distances),
                               peak_1ms=burst_peak(offsets),source_background_bytes=sum(t["size_bytes"] for t in traffic)))
        until=end
    if len(candidates)<48:
        raise ValueError("Insufficient disjoint windows; no substitution allowed")
    indices=[i*(len(candidates)-1)//47 for i in range(48)]
    return len(candidates),[candidates[i] for i in indices]


def generate(trace, directory):
    directory.mkdir(parents=True,exist_ok=True)
    candidate_count,selected=windows(trace)
    print("disjoint candidates",candidate_count,"selected",len(selected))
    for session in (1,2):
        combos=list(product(range(48),("fifo","latest")))
        random.Random(SEED+session).shuffle(combos)
        path=directory/f"plan{session}.jsonl"
        with path.open("x",encoding="utf-8",newline="\n") as f:
            for idx,policy in combos:
                w=selected[idx]
                pair=f"{session}-{idx:02d}-{policy}"
                arms=("none","one") if (session+idx+(policy=="fifo"))%2 else ("one","none")
                for arm in arms:
                    row=dict(**w,pair_id=pair,run_id=pair+"-"+arm,field=arm,policy=policy)
                    f.write(json.dumps(row,separators=(",",":"))+"\n")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("trace",type=Path)
    p.add_argument("directory",type=Path)
    a=p.parse_args()
    generate(a.trace,a.directory)
