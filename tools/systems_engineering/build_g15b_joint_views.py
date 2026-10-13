"""Write or check deterministic human-readable projections of the B0 source."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from g15b_joint_baseline import render_markdown, render_strictdoc


def outputs(repo: Path) -> dict[Path, str]:
    req = json.loads((repo / "systems_engineering/requirements/b0_requirements.json").read_text(encoding="utf-8"))
    ver = json.loads((repo / "systems_engineering/verification/b0_verification_specifications.json").read_text(encoding="utf-8"))
    root = repo / "systems_engineering/requirements/generated"
    return {
        root / "b0_requirements.md": render_markdown(req, ver),
        root / "b0_requirements.sdoc": render_strictdoc(req),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args(argv)
    drift: list[str] = []
    for path, content in outputs(args.repo_root.resolve()).items():
        expected = content.rstrip() + "\n"
        if args.write:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(expected, encoding="utf-8", newline="\n")
        elif not path.is_file() or path.read_text(encoding="utf-8") != expected:
            drift.append(str(path))
    if drift:
        parser.error("generated projection drift: " + ", ".join(drift))
    print("G1.5-B projections written" if args.write else "G1.5-B projections are current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
