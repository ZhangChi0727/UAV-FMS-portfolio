"""Positive control only. Compare like schedules, never pool with natural observations."""
from collections import Counter,defaultdict
import hashlib
import json
from pathlib import Path
from score import rows, delayed,gold_ref,label,scores,use_field


def main():
    root=Path(__file__).resolve().parent
    d=root/"service"
    for name,h in json.loads((d/"freeze.json").read_text()).items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=h:
            raise ValueError("Positive control changed")
    natural=json.loads((root/"evidence/audit.json").read_text())["rows"]
    groups=defaultdict(Counter)
    details={}
    hashes={}
    for session in (1,2):
        pp,rr=[d/f"{k}{session}.jsonl" for k in ("plan","raw")]
        hashes[rr.name]=hashlib.sha256(rr.read_bytes()).hexdigest()
        for p,r in zip(rows(pp),rows(rr),strict=True):
            if any(r.get(k)!=v for k,v in p.items() if k not in ("states","traffic")):
                raise ValueError("Plan mismatched")
            if not (r["integrity"] and r["subscription_ready"] and
                    r["received"]==r["sent"]==len(p["states"])+len(p["traffic"])):
                raise ValueError("Delivery incomplete")
            if use_field(p) or p["phase_distance_ns"]<=1_000_000:
                raise ValueError("Positive control outside scope")
            g=gold_ref.evaluate(r)
            b=bytes.fromhex(r["field_hex"])
            if len(b)!=(4 if p["field"]=="one" else 0) or len(b)!=r["field_bytes"]:
                raise ValueError("Invalid field")
            f=int.from_bytes(b,"little") if b else None
            if f is not None and f>p["chosen_read"]:
                raise ValueError("Future sample")
            base=scores(p); aug=scores(p,f)
            l=delayed(p,r); rid=p["run_id"]
            if rid in details:
                raise ValueError("Duplicate run")
            comparison=label(base,g)
            group=groups[p["field"]]
            group["all"]+=1
            group[comparison]+=1
            group["any_late"]+=int(any(x["late"] for x in l))
            group["generation_missing"]+=int(any(x["all_missing"] for x in l))
            group["post_submission"]+=int(any(x["post_submission"] for x in l))
            group["publisher_late"]+=int(any(x["late_publisher"] for x in l))
            group["changed_from_same_natural_run_id"]+=int(g["verdict"]!=natural[rid]["gold"])
            if b:
                group["extra_"+label(aug,g)]+=1
            details[rid]=dict(gold=g["verdict"],status=g["status"],margin=g.get("margin"),base=base,aug=aug,
                              field=f,regular=natural[rid]["gold"],distance_ns=p["phase_distance_ns"],late=l)
    if groups["none"]["all"]!=24 or groups["one"]["all"]!=24:
        raise ValueError("Incomplete positive control")
    (d/"audit.json").write_text(json.dumps(dict(groups=groups,hashes=hashes,rows=details),indent=1)+"\n")
    print(dict(groups))


if __name__=="__main__":
    main()
