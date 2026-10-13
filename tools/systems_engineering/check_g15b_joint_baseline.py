"""Fail-closed check for the B0 G1.5-B joint-baseline D2 candidate."""

from __future__ import annotations

import argparse
from pathlib import Path

from g15b_joint_baseline import BaselineValidationError, validate_baseline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args(argv)
    try:
        counts = validate_baseline(args.repo_root.resolve())
    except BaselineValidationError as exc:
        parser.error(str(exc))
    print(
        "G1.5-B joint baseline check passed "
        f"({counts['requirements']} requirements, {counts['model_elements']} model elements, "
        f"{counts['verifications']} planned verifications; no execution claims)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
