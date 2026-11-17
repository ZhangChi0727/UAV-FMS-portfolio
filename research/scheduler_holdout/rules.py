"""Frozen old predictor and pre-specified additional-information comparators."""
import ast
import hashlib
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1]/"paired_scheduler"/"analyze.py"
FROZEN_SHA256 = "7e013f4781ee13800d9f0aa428e87233b171820dc596e7fa205bf58573f841f3"
text = SOURCE.read_text(encoding="utf-8")
node = next(n for n in ast.parse(text).body if getattr(n, "name", None) == "gap_prediction")
snippet = ast.get_source_segment(text, node)
if hashlib.sha256(snippet.encode()).hexdigest() != FROZEN_SHA256:
    raise RuntimeError("Original gap predictor changed since the freeze")
scope = {}
exec(compile(snippet, str(SOURCE), "exec"), scope)
gap_prediction = scope["gap_prediction"]


def classify(reads):
    if "old" in reads:
        return "VIOL"
    return "SAT" if all(read == "new" for read in reads) else "UNRESOLVED"


def decisions(bare, extra):
    reads, distances = [], []
    guard = int(bare["clock_guard_ns"])
    for i in (1, 2):
        lo = int(bare[f"read{i}_lo_ns"])-int(bare[f"pub{i}_hi_ns"])
        hi = int(bare[f"read{i}_hi_ns"])-int(bare[f"pub{i}_lo_ns"])
        reads.append("new" if lo > extra + guard else "old" if hi < extra - guard else "unresolved")
        distances.append(abs((lo+hi)/2-extra))
    if classify(reads) != gap_prediction(bare,extra):
        raise ValueError("Read-level expansion disagrees with frozen rule")
    return reads, distances.index(min(distances))+1


def scores(bare, extra, sidecar):
    """Only consumed IDs from B enter the supplementary rules, never B commands/times."""
    reads, i = decisions(bare, extra)
    baseline = gap_prediction(bare,extra)
    one = reads.copy()
    one[i-1] = "new" if int(sidecar[f"seq{i}"]) == i else "old"
    both = ["new" if int(sidecar[f"seq{j}"]) == j else "old" for j in (1,2)]
    policy = baseline
    if bare["policy"] == "shared":
        policy = classify(["new" if int(bare[f"lead{j}_ns"]) >= 0 else "old" for j in (1,2)])
    return dict(gap=baseline, policy=policy, one=classify(one), two=classify(both), selected_read=i)
