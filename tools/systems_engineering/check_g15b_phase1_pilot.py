"""Fail-closed checks for the non-authoritative G1.5-B structured pilot."""

from __future__ import annotations

import argparse
from pathlib import Path

from g15b_pilot.build_pilot_views import check_outputs, render_outputs
from g15b_pilot.pilot_contract import PilotError, load_validated_pilot


def check_pilot(repo_root: Path) -> None:
    """Check schema, source locators, AST-backed model links, and projections."""

    contract, model = load_validated_pilot(repo_root)
    check_outputs(render_outputs(contract, model))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args(argv)
    try:
        check_pilot(args.repo_root.resolve())
    except PilotError as exc:
        parser.error(str(exc))
    print("G1.5-B structured phase-one pilot check passed (5 non-authoritative records)")
    return 0


if __name__ == "__main__":  # pragma: no cover - command-line entry point
    raise SystemExit(main())
