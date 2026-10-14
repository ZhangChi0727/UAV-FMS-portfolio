"""Require one predeclared Catch2 numeric test to detect a compiled subject mutant."""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: expect_mutation_detected.py <test-executable> <test-name>")
        return 2
    executable, test_name = sys.argv[1:]
    completed = subprocess.run(
        [executable, test_name, "--reporter", "console", "--abort"],
        check=False,
        capture_output=True,
        text=True,
    )
    output = completed.stdout + completed.stderr
    print(output, end="")
    if completed.returncode != 1:
        print(
            f"mutation detection requires Catch2 assertion-failure exit 1; "
            f"received {completed.returncode}",
            file=sys.stderr,
        )
        return 1
    if test_name not in output or "FAILED" not in output:
        print(
            "mutation process failed without the predeclared numeric node reporting failure",
            file=sys.stderr,
        )
        return 1
    print(f"detected subject mutation with unchanged oracle node: {test_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
