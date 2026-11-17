"""Score all held-out quartets using the frozen predictor and sparse gold projection."""
import argparse
import csv
import hashlib
import json
import struct
from collections import Counter, defaultdict
from pathlib import Path

from plan import estimate
from reference import compare_diagnostic, evaluate
from rules import FROZEN_SHA256, scores


def read(p):
    with p.open(newline="") as f:
        return list(csv.DictReader(f))


def checksum_entry(byte):
    for _ in range(8):
        byte = (byte >> 1) ^ (0x8408 if byte & 1 else 0)
    return byte


TABLE = tuple(map(checksum_entry,range(256)))


def frames(row):
    """Check native bytes + post-run digest via independent wire packing and CRC."""
    sequence = 0
    for i in (1,2):
        batch = int(row[f"batch{i}"]) if row["arm"] == "log" else 0
        payload = struct.pack("<I6f",int(row[f"s{i}_ns"])//1_000_000,float(row[f"s{i}"]),
                              0,0,0,0,0).rstrip(b"\0") or b"\0"
        digest = 14695981039346656037 if batch else 0
        for _ in range(batch):
            body = bytes((len(payload),0,0,sequence,1,1,30,0,0)) + payload
            crc=0xFFFF
            for byte in body+b"\x27":
                crc=(crc>>8)^TABLE[(crc^byte)&255]
            frame = b"\xfd"+body+struct.pack("<H",crc)
            for byte in frame:
                digest=((digest^byte)*1099511628211)&0xffffffffffffffff
            sequence=(sequence+1)%256
        if (digest,int(row[f"bytes{i}"]))!=(int(row[f"digest{i}"]),batch*(12+len(payload))):
            raise ValueError(f"Frame verification failed: {row['run_id']}, sample {i}")


def load(directory):
    hashes, quartets = {}, {}
    freeze = json.loads((directory/"freeze.json").read_text())
    package=Path(__file__).resolve().parent
    for name, expected in freeze.items():
        src = directory/"cal_plan.csv" if name=="evidence/cal_plan.csv" else package/name
        if hashlib.sha256(src.read_bytes()).hexdigest()!=expected:
            raise ValueError(f"Freeze violation: {name}")
    for stage in ("cal","main1","main2"):
        paths=[directory/f"{stage}_{k}.csv" for k in ("plan","raw")]
        for p in paths:
            hashes[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
        plist, raw=map(read,paths)
        if len(raw)!=(96 if stage=="cal" else 224):
            raise ValueError("Unexpected run count")
        for plan,row in zip(plist,raw,strict=True):
            if any(row[k]!=v for k,v in plan.items()):
                raise ValueError("Input or ordering differs from plan")
            frames(row)
            detailed=[int(row[f"{k}{i}_{side}_ns"]) for i in (1,2) for k in ("read","pub","work")
                      for side in ("lo","hi")]
            if row["reference"]=="lean" and set(detailed)!={-1}:
                raise ValueError("Lean capture contains fine timestamps")
            if row["reference"]=="timed":
                if min(detailed)<0 or int(row["clock_guard_ns"])<(10**9+int(row["qpc_frequency_hz"])-1)//int(row["qpc_frequency_hz"])+1:
                    raise ValueError("Missing timing data or invalid clock guard")
                for i in (1,2):
                    times = [int(row[f"{k}{i}_{edge}_ns"]) for k in ("work","pub") for edge in ("lo","hi")]
                    if times!=sorted(times) or int(row[f"read{i}_lo_ns"])>int(row[f"read{i}_hi_ns"]):
                        raise ValueError("Invalid timestamp interval")
            if stage!="cal":
                q=quartets.setdefault(row["pair_id"],{})
                side=row["run_id"].split("-")[-1]
                if side in q:
                    raise ValueError("Duplicate arm")
                q[side]=row
    return hashes, quartets


def mark(predicted, gold):
    if gold["status"]!="VERIFIED":
        return "no_reference"
    if predicted=="UNRESOLVED":
        return "abstain"
    if predicted==gold["verdict"]:
        return "correct"
    return "false_pass" if predicted=="SAT" else "false_reject"


def run(directory):
    hashes, quartets=load(directory)
    calibration=estimate(directory)
    if calibration!=json.loads((directory/"calibrated.json").read_text()):
        raise ValueError("Changed calibration")
    groups=defaultdict(lambda:defaultdict(Counter))
    records={}
    for key,q in quartets.items():
        if set(q)!={"AT","AL","BT","BL"}:
            raise ValueError(key)
        session,rep,policy,n,shape=key.split("-")
        if any(q[s]["arm"]!=("log" if s[0]=="B" else "off") or q[s]["reference"]!=("timed" if s[1]=="T" else "lean")
               or q[s]["policy"]!=policy or q[s]["batch1"]!=n or q[s]["batch2"]!=n for s in q):
            raise ValueError("Bad arm assignment")
        if any(len({r[k] for r in q.values()})!=1 for k in ("lead1_ns","lead2_ns","unit_ns","pair_id")):
            raise ValueError("Unpaired inputs")
        gold = evaluate(q["BL"])
        pred=scores(q["AT"],calibration[f"{policy}.{n}"]["extra_ns"],q["BL"])
        outcomes={k:mark(pred[k],gold) for k in ("gap","policy","one","two")}
        diagnostics={}
        for arm in ("A","B"):
            d=compare_diagnostic(q[arm+"L"],q[arm+"T"])
            if not d["matched"]:
                raise ValueError("Reference diagnostic unmatched")
            diagnostics[arm]=dict(flip=d["flip"], lean=d["lean"]["verdict"], timed=d["timed"]["verdict"],
                                  lean_status=d["lean"]["status"],timed_status=d["timed"]["status"])
        for label in ("all",policy,f"{policy}.batch{n}",f"{policy}.{shape}",f"session{session}"):
            for k,status in outcomes.items():
                groups[label][k][status]+=1
            for arm,d in diagnostics.items():
                groups[label]["reference_"+arm][str(d["flip"])]+=1
            for field in ("policy","one","two"):
                groups[label]["change_"+field][outcomes["gap"]+">"+outcomes[field]]+=1
        records[key]=dict(gold=gold,predictions=pred,outcomes=outcomes,diagnostics=diagnostics,
                          source_ids=[int(q["BL"]["seq1"]),int(q["BL"]["seq2"])])
    if len(records)!=112:
        raise ValueError("Incomplete design")
    return dict(input_sha256=hashes,frozen_function=FROZEN_SHA256,calibration=calibration,
                groups=groups,records=records)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("directory",type=Path)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    report=run(args.directory)
    args.output.write_text(json.dumps(report,indent=1)+"\n")
    print(json.dumps({k:report["groups"][k] for k in ("all","shared","split")}))
