"""Native StrictDoc checks for the isolated G1.5-B phase-one trial."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[4]
PILOT_DIRECTORY = REPO_ROOT / "tools/systems_engineering/g15b_pilot/strictdoc"


def strictdoc_command() -> str:
    command = Path(sys.executable).with_name("strictdoc")
    assert command.is_file(), "strictdoc must be installed in the isolated pilot environment"
    return str(command)


def export(source: Path, output: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            strictdoc_command(),
            "export",
            "--formats=html",
            "--output-dir",
            str(output),
            "--no-parallelization",
            str(source),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_native_export_generates_readable_html(tmp_path: Path) -> None:
    result = export(PILOT_DIRECTORY, tmp_path / "html")
    assert result.returncode == 0, result.stderr or result.stdout
    html = "\n".join(path.read_text(encoding="utf-8") for path in (tmp_path / "html").rglob("*.html"))
    assert "PILOT-ONLY-G2-05" in html
    assert "planned/not_run" in html
    assert "Git branch:" in html
    assert "@GIT_VERSION" not in html


def test_native_duplicate_uid_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "duplicate"
    shutil.copytree(PILOT_DIRECTORY, source)
    pilot = source / "b0_phase1_pilot.sdoc"
    pilot.write_text(
        pilot.read_text(encoding="utf-8").replace(
            "UID: PILOT-ONLY-G2-05", "UID: PILOT-ONLY-NEED-01"
        ),
        encoding="utf-8",
    )
    result = export(source, tmp_path / "html")
    assert result.returncode != 0, "StrictDoc accepted a duplicate temporary UID"


def test_native_missing_parent_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "missing-parent"
    shutil.copytree(PILOT_DIRECTORY, source)
    pilot = source / "b0_phase1_pilot.sdoc"
    pilot.write_text(
        pilot.read_text(encoding="utf-8").replace(
            "VALUE: PILOT-ONLY-INTERFACE-02", "VALUE: PILOT-ONLY-MISSING-99"
        ),
        encoding="utf-8",
    )
    result = export(source, tmp_path / "html")
    assert result.returncode != 0, "StrictDoc accepted a missing parent reference"
