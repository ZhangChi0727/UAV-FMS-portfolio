"""Derive a corrected immutable headroom summary from a sealed diagnostic."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    payload = args.input.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != args.expected_sha256:
        raise ValueError("sealed diagnostic hash mismatch")
    source = json.loads(payload)
    limits = [0.35, 0.35, 0.2]
    minimum = source["request_min_Nm"]
    maximum = source["request_max_Nm"]
    derived = {
        "schema_version": "b0-g3-reachability-derived-summary/v1",
        "source_path": args.input.name,
        "source_sha256": digest,
        "source_commit": source["source_commit"],
        "scenario_id": source["scenario_id"],
        "seed": source["seed"],
        "acceptance_seed_exposed": True,
        "torque_limits_Nm": limits,
        "request_min_Nm": minimum,
        "request_max_Nm": maximum,
        "negative_limit_headroom_Nm": [
            minimum[index] + limits[index] for index in range(3)
        ],
        "positive_limit_headroom_Nm": [
            limits[index] - maximum[index] for index in range(3)
        ],
        "saturation_union_duration_s": source["saturation_union_duration_s"],
        "reachability_status": source["reachability_status"],
        "note": "Positive headroom means the request remained inside the corresponding signed limit. The source file is unchanged.",
    }
    rendered = json.dumps(derived, indent=2, sort_keys=True) + "\n"
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(rendered)
    print(hashlib.sha256(rendered.encode("utf-8")).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
