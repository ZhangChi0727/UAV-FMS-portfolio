"""Generate calibration or both balanced main plans. No verdicts enter planning."""
import argparse
import csv
import json
import random
import statistics
from pathlib import Path


UNIT = 15_000_000
FAR = 3_000_000
SEED = 20261104
HEADER = "run_id pair_id arm lead1_ns lead2_ns unit_ns".split()


def write(path, rows):
    if path.exists():
        raise FileExistsError(path)
    with path.open("w", newline="", encoding="ascii") as handle:
        out = csv.writer(handle, lineterminator="\n")
        out.writerow(HEADER)
        out.writerows(rows)


def calibration(directory):
    rng = random.Random(SEED)
    rows = []
    for block in range(12):
        modes = ["off", "light", "stress"]
        rng.shuffle(modes)
        for mode in modes:
            pair = f"cal-{block:02d}"
            rows.append((f"{pair}-{mode}", pair, mode, FAR, FAR, UNIT))
    write(directory/"calibration_plan.csv", rows)


def main_plans(directory):
    with (directory/"calibration_raw.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    timings = {}
    for arm in ("off", "light", "stress"):
        trials = [row for row in rows if row["arm"] == arm]
        if len(trials) != 12:
            raise ValueError("Incomplete calibration")
        spans = [int(row[f"work{i}_hi_ns"])-int(row[f"work{i}_lo_ns"])
                 for row in trials[2:] for i in (1, 2)]
        timings[arm] = statistics.median(spans)
    near = {mode: min(UNIT//10, max(1, round((timings[mode]-timings["off"])/2)))
            for mode in ("light", "stress")}
    for session in (1, 2):
        rng = random.Random(SEED+session)
        schedule = []
        for block in range(4):
            conditions = [(load, scene) for load in near
                          for scene in ("first", "second", "both", "early", "late", "sham")]
            rng.shuffle(conditions)
            for load, scene in conditions:
                n = near[load]
                lead = {"first": (n,FAR), "second": (FAR,n), "both": (n,n),
                        "early": (FAR,FAR), "late": (-FAR,FAR), "sham": (n,FAR)}[scene]
                pair = f"{session}-{block}-{load}-{scene}"
                arms = [("A","off"), ("B","off" if scene=="sham" else load)]
                # Alternate within each condition, reversing the starting side in session 2.
                if (block+session) % 2:
                    arms.reverse()
                schedule.extend((f"{pair}-{label}", pair, mode, *lead, UNIT)
                                for label,mode in arms)
        write(directory/f"main{session}_plan.csv", schedule)
    info = dict(seed=SEED, median_elapsed_ns=timings, near_ns=near, far_ns=FAR)
    print(json.dumps(info))
    (directory/"calibration_settings.json").write_text(json.dumps(info,indent=2)+"\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("calibration", "main"))
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    args.directory.mkdir(exist_ok=True, parents=True)
    (calibration if args.stage == "calibration" else main_plans)(args.directory)
