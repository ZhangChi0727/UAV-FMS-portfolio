"""Compare blinded nominal predictions with exact actual-trajectory labels."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import struct

from design import predict, scores, windows
from field_cost import summarize_pairs
from reference import evaluate


def records(path):
    with path.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def mark(predicted, gold):
    if gold["status"]!="VERIFIED":
        return "no_reference"
    if predicted=="UNRESOLVED":
        return "abstain"
    if predicted==gold["verdict"]:
        return "correct"
    return "false_pass" if predicted=="SAT" else "false_reject"


def run(directory):
    root=Path(__file__).resolve().parent
    freeze=json.loads((directory/"freeze.json").read_text())
    for name,expected in freeze.items():
        path=directory/Path(name).name if name.startswith("evidence/") else root/name
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError(f"changed frozen input {name}")
    hashes={}
    all_raw=[]
    details={}
    groups=defaultdict(lambda:defaultdict(Counter))
    source_windows={}
    candidate_count,selected=windows(root/"trace.csv")
    for session in (1,2):
        paths=[directory/f"{prefix}{session}.jsonl" for prefix in ("plan","raw")]
        plist,raw=map(records,paths)
        if len(plist)!=192 or len(raw)!=192:
            raise ValueError("Incomplete acquisition, retain and investigate")
        for path in paths:
            hashes[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
        for plan,row in zip(plist,raw,strict=True):
            pid=plan["pair_id"]
            rep,window,policy=pid.split("-")
            if rep!=str(session) or plan["policy"]!=policy:
                raise ValueError(pid)
            if any(plan[k]!=v for k,v in selected[int(window)].items()):
                raise ValueError("Phase/burst selection differs from frozen rule")
            if any(plan[k]!=row.get(k) for k in plan if k not in ("states","traffic")):
                raise ValueError("Unpaired raw record")
            for tag in ("states","traffic"):
                digest=hashlib.sha256(json.dumps(plan[tag],sort_keys=True).encode()).hexdigest()
                if digest!=row["state_plan_sha256" if tag=="states" else "traffic_plan_sha256"]:
                    raise ValueError("send trace mismatch")
            count=len(plan["states"])+len(plan["traffic"])
            if not(row["subscription_ready"] and row["integrity"] and row["sent"]==row["received"]==count):
                raise ValueError("incomplete or corrupted network stream")
            all_raw.append(row)
            gold=evaluate(row)
            prediction=scores(plan)
            blind=scores(dict(plan,policy="latest"))
            width=row["field_bytes"]
            if width!=(4 if row["field"]=="one" else 0) or len(bytes.fromhex(row["field_hex"]))!=width:
                raise ValueError("wrong field accounting")
            extra=None
            if width:
                value,=struct.unpack("<I",bytes.fromhex(row["field_hex"]))
                if value>plan["chosen_read"]:
                    raise ValueError("logged a future sample")
                extra=scores(plan,value)
            key=row["run_id"]
            if key in details:
                raise ValueError("duplicate run")
            src=dict(phase_distance_ns=plan["phase_distance_ns"],peak_1ms=plan["peak_1ms"],
                     origin_us=plan["origin_us"],unit_ns=plan["unit_ns"],chosen_read=plan["chosen_read"],
                     n_state=len(plan["states"]),n_traffic=len(plan["traffic"]),
                     bg_bytes=plan["source_background_bytes"])
            source_windows[window]=src
            details[key]=dict(gold=gold["verdict"],reference_status=gold["status"],margin=gold.get("margin"),
                              reasons=gold["reasons"],nominal_paths=predict(plan),policy=prediction,
                              extra=extra,blind_latest=blind)
            status=mark(prediction,gold)
            labels=("all",policy,f"session{rep}.{policy}",f"{policy}.near{int(src['phase_distance_ns']<=1_000_000)}",
                    f"{policy}.burst{int(src['peak_1ms']>=3)}",f"{policy}.chosen{src['chosen_read']}")
            for tag in labels:
                part=groups[tag]
                part["policy_"+row["field"]][status]+=1
                part["latest_only_"+row["field"]][mark(blind,gold)]+=1
                part["gold_"+row["field"]][str(gold["verdict"])]+=1
                if extra is not None:
                    out=mark(extra,gold)
                    part["one_field"][out]+=1
                    part["changes"][status+">"+out]+=1
    cost=summarize_pairs(all_raw)
    for pair in cost["detail"]:
        pid=pair["pair_id"]
        a,b=[details[pid+"-"+arm] for arm in ("none","one")]
        key="no_reference" if None in (a["gold"],b["gold"]) else str(a["gold"]!=b["gold"])
        for tag in ("all",pair["policy"]):
            groups[tag]["matched_verdict_difference"][key]+=1
    if len(source_windows)!=48 or cost["pairs"]!=192:
        raise ValueError("replication grid incomplete")
    return dict(candidates=candidate_count,windows=source_windows,hashes=hashes,groups=groups,
                cost=cost,details=details)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("directory",type=Path)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    report=run(args.directory)
    args.output.write_text(json.dumps(report,indent=1)+"\n")
    print(json.dumps({k:report["groups"][k] for k in ("all","fifo","latest")}))
