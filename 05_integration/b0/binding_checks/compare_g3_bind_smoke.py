"""Compare sealed G3-BIND outputs from independent Debug and Release loops."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


TRACK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRACK_ROOT))

from runner import compare_g3_bind_results  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--debug", type=Path, required=True)
    parser.add_argument("--release", type=Path, required=True)
    args = parser.parse_args(argv)
    debug = json.loads(args.debug.read_text(encoding="utf-8"))
    release = json.loads(args.release.read_text(encoding="utf-8"))
    compare_g3_bind_results(debug, release)
    print("G3-BIND Debug/Release independent-loop comparison passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
