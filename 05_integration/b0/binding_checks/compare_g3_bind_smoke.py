"""Offline comparison of sealed G3-A Debug and Release raw records."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


BINDING_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(BINDING_ROOT))

from g3a_authority import load_consumer_authority  # noqa: E402
from g3a_independent_checks import compare_builds  # noqa: E402


def _write_exclusive(path: Path, value: dict[str, Any]) -> None:
    payload = json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8") + b"\n"
    with path.open("xb") as stream:
        stream.write(payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--debug-raw", type=Path, required=True)
    parser.add_argument("--release-raw", type=Path, required=True)
    parser.add_argument("--debug-authority", type=Path, required=True)
    parser.add_argument("--release-authority", type=Path, required=True)
    parser.add_argument("--debug-authority-sha256", required=True)
    parser.add_argument("--release-authority-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    debug_authority = load_consumer_authority(
        args.debug_authority, args.debug_authority_sha256
    )
    release_authority = load_consumer_authority(
        args.release_authority, args.release_authority_sha256
    )
    report = compare_builds(
        args.debug_raw.read_bytes(),
        args.release_raw.read_bytes(),
        debug_authority,
        release_authority,
    )
    _write_exclusive(args.output, report)
    if report["status"] != "pass":
        print(json.dumps(report, indent=2, sort_keys=True), file=sys.stderr)
        return 1
    print("G3-A sealed Debug/Release comparison passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
