"""Create calibration and untouched evaluation schedules; no gold/predictions used."""
import argparse
import csv
from fractions import Fraction as F
from itertools import product
import json
from pathlib import Path
import random
from statistics import median

SEED = 2026110403
UNIT, FAR, CAL = 15_000_000, 900_000, 3_000_000
FIELDS = "run_id pair_id arm policy lead1_ns lead2_ns unit_ns batch1 batch2 reference".split()
POLICIES = ("shared", "split")
BATCHES = (8, 256)


def write(dir_, stem, rows):
    with (dir_/f"{stem}_plan.csv").open("x",encoding="ascii",newline="") as f:
        out = csv.writer(f,lineterminator="\n")
        out.writerow(FIELDS)
        out.writerows(rows)


def calibration(dir_):
    rng = random.Random(SEED)
    rows = []
    for rep in range(12):
        cells = list(product(POLICIES,BATCHES,("off","log")))
        rng.shuffle(cells)
        for policy,n,arm in cells:
            key = f"cal-{rep}-{policy}-{n}"
            rows.append((f"{key}-{arm}",key,arm,policy,CAL,CAL,UNIT,n,n,"timed"))
    write(dir_, "cal", rows)


def estimate(dir_):
    with (dir_/"cal_raw.csv").open(newline="") as f:
        rows = list(csv.DictReader(f))
    with (dir_/"cal_plan.csv").open(newline="") as f:
        for plan,row in zip(csv.DictReader(f),rows,strict=True):
            if any(row[k] != plan[k] for k in plan):
                raise ValueError("Calibration differs from assigned input")
    out = {}
    for policy,n in product(POLICIES,BATCHES):
        medians = {}
        for arm in ("off","log"):
            arms = [r for r in rows if r["policy"]==policy and int(r["batch1"])==n and r["arm"]==arm]
            if len(arms)!=12:
                raise ValueError("Incomplete calibration")
            durations = [int(r[f"work{i}_hi_ns"])-int(r[f"work{i}_lo_ns"])
                         for r in arms[2:] for i in (1,2)]
            if min(durations) < 0:
                raise ValueError("Absent calibration work brackets")
            medians[arm] = median(durations)
        extra = medians["log"]-medians["off"]
        if extra<=0 or extra>=FAR/3:
            raise ValueError(f"Unusable calibration at {policy}/{n}: {extra}")
        out[f"{policy}.{n}"] = dict(medians=medians,extra_ns=extra)
    return out


def main_plans(dir_):
    cal = estimate(dir_)
    (dir_/"calibrated.json").write_text(json.dumps(cal,indent=2)+"\n")
    shapes = {"early":(None,None),"late":("late",None),"firstlow":(F(7,20),None),
              "firsthigh":(F(33,20),None),"secondlow":(None,F(13,20)),
              "both":(F(4,5),F(5,4)),"tie":(0,None)}
    # Matched four-arm blocks; each side occupies each position once over two processes.
    base_order = ("AT","BL","AL","BT")
    for session in (1,2):
        rng = random.Random(SEED+session)
        rows = []
        for rep in (0,1):
            cells = list(product(POLICIES,BATCHES,shapes))
            rng.shuffle(cells)
            for policy,n,shape in cells:
                extra = cal[f"{policy}.{n}"]["extra_ns"]
                leads = tuple(FAR if x is None else -FAR if x=="late" else round(x*extra)
                              for x in shapes[shape])
                key = f"{session}-{rep}-{policy}-{n}-{shape}"
                k=(session-1)*2+rep
                for side in base_order[k:]+base_order[:k]:
                    arm = "off" if side[0]=="A" else "log"
                    mode = "lean" if side[1]=="L" else "timed"
                    rows.append((f"{key}-{side}",key,arm,policy,*leads,UNIT,n,n,mode))
        write(dir_,f"main{session}",rows)
    print(json.dumps(cal))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("stage", choices=["cal","main"])
    p.add_argument("directory", type=Path)
    a=p.parse_args()
    a.directory.mkdir(exist_ok=True,parents=True)
    (calibration if a.stage=="cal" else main_plans)(a.directory)
