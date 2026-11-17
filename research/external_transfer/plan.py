"""Primary natural replay and two outcome-blind challenge strata."""
import argparse
import bisect
import csv
import hashlib
import json
from pathlib import Path
import random

from rule import old, scores

SEED=2026110405


def take(items,n):
    if len(items)<=n:
        return items.copy()
    return [items[i*(len(items)-1)//(n-1)] for i in range(n)]


def candidates(events, pub, read):
    times=[t for t,topic,_ in events if topic==read]
    alltimes=[t for t,_,_ in events]
    last_end=alltimes[0]
    out=[]
    for t,next_t in zip(times,times[1:]):
        u=next_t-t
        start=t-2*u
        end=start+4*u
        if u<=0 or start<last_end or end>alltimes[-1]:
            continue
        last_end=end
        use=events[bisect.bisect_left(alltimes,start):bisect.bisect_left(alltimes,end)]
        releases=[((tm-start)*1000,topic,size) for tm,topic,size in use]
        states=[dict(offset_ns=dt,seq=1 if dt<2500*u else 2)
                for dt,topic,_ in releases if topic==pub and dt>=1000*u]
        traffic=[dict(offset_ns=dt,size_bytes=size) for dt,topic,size in releases if topic not in (read,pub)]
        dist=[min((abs(m["offset_ns"]-k*u*1000) for m in states),default=4*u*1000) for k in (2,3)]
        marks=sorted(m["offset_ns"] for m in states+traffic)
        out.append(dict(origin_us=start,unit_ns=u*1000,states=states,traffic=traffic,
                        chosen_read=dist.index(min(dist))+1,phase_distance_ns=min(dist),
                        peak_1ms=old.burst_peak(marks),source_background_bytes=sum(m["size_bytes"] for m in traffic)))
    return out


def design(events, pub, read, alt):
    representative=candidates(events,pub,read)
    main=take(representative,48)
    output=[dict(**w,stratum="primary",pub_proxy=pub,read_proxy=read) for w in main]
    by_stratum={"primary_population":len(representative),"primary_n":len(main)}
    used={w["origin_us"] for w in main}
    for name, candidate_read in [("primary",read),("alternate",alt)]:
        if not candidate_read:
            continue
        population=candidates(events,pub,candidate_read)
        remaining=[w for w in population if w["origin_us"] not in used]
        for filter_name in ("fifo_sat","far_latest_sat"):
            if filter_name=="fifo_sat":
                pool=[w for w in remaining if scores(dict(w,policy="fifo"))=="SAT"]
            else:
                pool=[w for w in remaining if w["phase_distance_ns"]>1_000_000 and scores(dict(w,policy="latest"))=="SAT"]
            # Within a profile and across strata, use a window only once.
            pool=[w for w in pool if w["origin_us"] not in used]
            picks=take(pool,12)
            key=name+"_"+filter_name
            by_stratum[key+"_eligible_after_exclusion"]=len(pool)
            by_stratum[key+"_n"]=len(picks)
            used.update(w["origin_us"] for w in picks)
            output.extend(dict(**w,stratum=key,pub_proxy=pub,read_proxy=candidate_read) for w in picks)
    return output,by_stratum


def generate(source,directory,pub,read,alt):
    with source.open(newline="") as f:
        raw=list(csv.DictReader(f))
    events=sorted(((int(r["timestamp_us"]),r["topic"],int(r["ulog_payload_bytes"])) for r in raw),key=lambda e:e[0])
    if not all(t in {e[1] for e in events} for t in (pub,read)):
        raise ValueError("Required source topic absent")
    plans,summary=design(events,pub,read,alt)
    if not plans:
        raise ValueError("No feasible windows")
    directory.mkdir(parents=True,exist_ok=True)
    meta=dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),pub=pub,read=read,
              alternate=alt,counts=summary)
    for session in (1,2):
        cells=[(i,pol) for i in range(len(plans)) for pol in ("fifo","latest")]
        random.Random(SEED+session).shuffle(cells)
        path=directory/f"plan{session}.jsonl"
        with path.open("x",encoding="utf-8",newline="\n") as f:
            for i,policy in cells:
                pid=f"{session}-{i:03d}-{policy}"
                arms=("none","one") if (i+session+(policy=="fifo"))%2 else ("one","none")
                for arm in arms:
                    row=dict(**plans[i],pair_id=pid,run_id=pid+"-"+arm,policy=policy,field=arm)
                    f.write(json.dumps(row,separators=(",",":"))+"\n")
        meta[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
    (directory/"plan_meta.json").write_text(json.dumps(meta,indent=2)+"\n")
    print(json.dumps(meta))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source",type=Path)
    parser.add_argument("directory",type=Path)
    parser.add_argument("--pub",required=True)
    parser.add_argument("--read",required=True)
    parser.add_argument("--alt",default="")
    a=parser.parse_args()
    generate(a.source,a.directory,a.pub,a.read,a.alt)
