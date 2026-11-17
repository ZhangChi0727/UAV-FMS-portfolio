"""Retrospective diagnosis, separated from the frozen predictor and physical gold."""
import argparse
from collections import Counter,defaultdict
import hashlib
import json
from pathlib import Path

from rule import ROOT,module,label,predict,scores,use_field

gold_ref=module(ROOT/"pubsub_transfer/reference.py","previous_reference",
                "0b0eb4f43cb59091c6a9e3b387a33e8aada29f3623af6b906cbb033aadad8b90")


def rows(path):
    with path.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def delayed(p,r):
    diag=r["diagnostics"]
    events=diag["state_events"]
    expected=p["states"]
    if [v["release_ns"] for v in events] != [v["offset_ns"] for v in expected]:
        raise ValueError("State event coverage mismatch")
    for e in events:
        if not (e["release_ns"]<=e["send_lo_ns"]<=e["send_hi_ns"] and
                e["send_lo_ns"]<=e["recv_decoded_ns"]<=e["enqueue_lo_ns"]<=e["enqueue_hi_ns"]):
            raise ValueError("Out-of-order diagnostic clocks")
    proof=[]
    for j,d in enumerate(diag["reads"],1):
        if d["read"]!=j or not d["lo_ns"]<=d["cut_ns"]<=d["hi_ns"]<=r[f"apply{j}_ns"]:
            raise ValueError("Read chronology mismatch")
        guard=r["clock_guard_ns"]
        deadline=(j+1)*p["unit_ns"]
        gen=[e for s,e in zip(expected,events) if s["seq"]==j]
        early=[e for e in gen if e["release_ns"]<deadline]
        late=[e for e in early if e["enqueue_lo_ns"]>d["hi_ns"]+guard]
        none_available=bool(early) and all(e["enqueue_lo_ns"]>d["hi_ns"]+guard for e in gen)
        # sendall return means submission to the local socket, not a broker ACK.
        after_send=[e for e in late if e["send_hi_ns"]+guard<d["lo_ns"]]
        late_pub=[e for e in late if e["send_lo_ns"]>d["hi_ns"]+guard]
        proof.append(dict(read=j, early=len(early), late=len(late), all_missing=none_available,
                          post_submission=len(after_send), late_publisher=len(late_pub),
                          first_late_ordinal=late[0]["ordinal"] if late else None))
    return proof


def run(directory):
    meta=json.loads((directory/"plan_meta.json").read_text())
    freeze=json.loads((directory/"freeze.json").read_text())
    for name,h in freeze.items():
        if hashlib.sha256((ROOT/"external_transfer"/name).read_bytes()).hexdigest()!=h:
            raise ValueError(f"Frozen input differs: {name}")
    table=defaultdict(lambda:defaultdict(Counter))
    detail={}
    hashes={}
    n_windows=0
    for session in (1,2):
        pfile,rfile=[directory/f"{stem}{session}.jsonl" for stem in ("plan","raw")]
        plans,raw=rows(pfile),rows(rfile)
        n_windows=sum(v for k,v in meta["counts"].items() if k.endswith("_n"))
        if len(plans)!=4*n_windows or meta[pfile.name]!=hashlib.sha256(pfile.read_bytes()).hexdigest():
            raise ValueError("Plan changed")
        hashes[rfile.name]=hashlib.sha256(rfile.read_bytes()).hexdigest()
        for p,r in zip(plans,raw,strict=True):
            if any(p[k]!=r.get(k) for k in p if k not in ("traffic","states")):
                raise ValueError("Assigned run differs")
            n=len(p["traffic"])+len(p["states"])
            if not (r["subscription_ready"] and r["integrity"] and r["sent"]==r["received"]==n):
                raise ValueError("Unverified delivery")
            width=4 if p["field"]=="one" else 0
            payload=bytes.fromhex(r["field_hex"])
            if len(payload)!=width or width!=r["field_bytes"]:
                raise ValueError("Unexpected field")
            f=int.from_bytes(payload,"little") if width else None
            if f is not None and f>p["chosen_read"]:
                raise ValueError("Future sample")
            g=gold_ref.evaluate(r)
            base=scores(p)
            aug=scores(p,f)
            m,m_field=label(base,g),label(aug,g)
            selected=(use_field(p)==bool(width))
            far=p["phase_distance_ns"]>1_000_000
            bits=delayed(p,r)
            rid=p["run_id"]
            if rid in detail:
                raise ValueError("Duplicate run ID")
            detail[rid]=dict(stratum=p["stratum"],far=far,phase_ns=p["phase_distance_ns"],
                             selected=selected,read=p["chosen_read"],field=f,base=base,aug=aug,
                             nominal=predict(p),margin=g.get("margin"),gold=g["verdict"],
                             ref_status=g["status"],reasons=g["reasons"],outcome=m_field,
                             late=bits)
            tags=[p["stratum"],p["stratum"]+"."+p["policy"],p["stratum"]+f".session{session}",
                  p["stratum"]+"."+p["policy"]+(".far" if far else ".near"),
                  "challenge" if p["stratum"]!="primary" else "representative"]
            for tag in tags:
                block=table[tag]
                arm=p["field"]
                block["baseline_"+arm][m]+=1
                block["gold_"+arm][str(g["verdict"])]+=1
                if width:
                    block["one"][m_field]+=1
                    block["change"][m+">"+m_field]+=1
                if selected:
                    block["selective"][m_field]+=1
                    block["fields"][arm]+=1
                    block["gold_selected"][str(g["verdict"])]+=1
                    if far:
                        block["far_diagnostics"]["runs"]+=1
                        block["far_diagnostics"]["runs_with_early_release"]+=int(any(x["early"] for x in bits))
                        block["far_diagnostics"]["runs_with_late_packet"]+=int(any(x["late"] for x in bits))
                        block["far_diagnostics"]["runs_with_generation_missing"]+=int(any(x["all_missing"] for x in bits))
                        block["far_diagnostics"]["post_submission"]+=int(any(x["post_submission"] for x in bits))
                        block["far_diagnostics"]["publisher_late"]+=int(any(x["late_publisher"] for x in bits))
    if len(detail)!=n_windows*8:
        raise ValueError("Incomplete sessions")
    return dict(counts=meta["counts"],hashes=hashes,groups=table,rows=detail)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("directory",type=Path)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    out=run(args.directory)
    args.output.write_text(json.dumps(out,indent=1)+"\n")
    print(json.dumps({k:out["groups"][k] for k in ("primary","challenge") if k in out["groups"]}))
