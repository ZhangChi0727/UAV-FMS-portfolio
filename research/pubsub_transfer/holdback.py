"""Independent future time block for the now-fixed selective deployment policy."""
import argparse
import csv
from collections import Counter,defaultdict
import hashlib
import json
import random
from pathlib import Path

from audit import mark,records
from design import SEED,scores,windows
from extract_trace import read_topics
from reference import evaluate


def prepare(source,directory):
    data=read_topics(source)
    rows=sorted((t,ordinal,k,size) for k,rec in data.items() for t,size,ordinal in rec
                if 143_000_000<=t<173_000_000)
    directory.mkdir(exist_ok=True,parents=True)
    trace=directory/"trace.csv"
    with trace.open("x",newline="") as f:
        writer=csv.writer(f,lineterminator="\n")
        writer.writerow(("topic","timestamp_us","ulog_payload_bytes","ulog_record_ordinal"))
        writer.writerows((k,t,size,i) for t,i,k,size in rows)
    candidates,selected=windows(trace)
    combos=[(i,p) for i in range(48) for p in ("fifo","latest")]
    random.Random(SEED+3).shuffle(combos)
    with (directory/"plan.jsonl").open("x",newline="\n") as f:
        for i,p in combos:
            w=selected[i]
            pid=f"next-{i:02d}-{p}"
            for arm in (("none","one") if (i+(p=="fifo"))%2 else ("one","none")):
                row=dict(**w,pair_id=pid,run_id=pid+"-"+arm,policy=p,field=arm)
                f.write(json.dumps(row,separators=(",",":"))+"\n")
    print("trace rows",len(rows),"candidates",candidates)


def score(directory):
    plan=records(directory/"plan.jsonl")
    raw=records(directory/"raw.jsonl")
    sums=defaultdict(Counter)
    details={}
    if len(plan)!=192:
        raise ValueError("Expected 48 windows by two policies by two cost arms")
    for p,r in zip(plan,raw,strict=True):
        if any(r[k]!=p[k] for k in p if k not in ("states","traffic")) or not r["integrity"]:
            raise ValueError("Incomplete or mismatched transport execution")
        if not r["subscription_ready"] or r["sent"]!=r["received"] or r["sent"]!=len(p["states"])+len(p["traffic"]):
            raise ValueError("End of stream not verified")
        for k,h in (("states","state_plan_sha256"),("traffic","traffic_plan_sha256")):
            if hashlib.sha256(json.dumps(p[k],sort_keys=True).encode()).hexdigest()!=r[h]:
                raise ValueError("Input payload schedule changed")
        width=4 if r["field"]=="one" else 0
        payload=bytes.fromhex(r["field_hex"])
        if len(payload)!=width or r["field_bytes"]!=width:
            raise ValueError("Field width disagrees with assigned arm")
        field=int.from_bytes(payload,"little") if payload else None
        if field is not None and field>p["chosen_read"]:
            raise ValueError("Future sample")
        gold=evaluate(r)
        plain=mark(scores(p),gold)
        seen=mark(scores(p,field),gold)
        use=p["policy"]=="latest" and p["phase_distance_ns"]<=1_000_000
        select=p["field"]==("one" if use else "none")
        sums[p["policy"]+".baseline_in_"+p["field"]][plain]+=1
        if width:
            sums[p["policy"]+".one"][seen]+=1
            sums[p["policy"]+".changes"][plain+">"+seen]+=1
        if select:
            sums[p["policy"]+".selective"][seen]+=1
            sums["total.selective"][seen]+=1
            sums["selected_arms"][p["field"]]+=1
        details[p["run_id"]]=dict(policy=plain,augmented=seen,selected=select,gold=gold["verdict"],
                                  status=gold["status"],phase_ns=p["phase_distance_ns"],field=field)
    if sum(sums["selected_arms"].values())!=96:
        raise ValueError("Incomplete deployment")
    report=dict(groups=sums,details=details,sha256={n:hashlib.sha256((directory/n).read_bytes()).hexdigest()
                for n in ("trace.csv","plan.jsonl","raw.jsonl")})
    (directory/"audit.json").write_text(json.dumps(report,indent=1)+"\n")
    print(json.dumps(sums))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("prepare","score"))
    p.add_argument("directory",type=Path)
    p.add_argument("--ulog",type=Path)
    a=p.parse_args()
    if a.action=="prepare":
        prepare(a.ulog,a.directory)
    else:
        score(a.directory)
