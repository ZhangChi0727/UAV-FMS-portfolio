"""Native StrictDoc checks for the isolated G1.5-B phase-one trial."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[4]
PILOT_DIRECTORY = REPO_ROOT / "tools/systems_engineering/g15b_pilot/strictdoc"
CUSTOM_GRAMMAR_PROBE = PILOT_DIRECTORY / "custom_grammar_probe.sdoc"
PILOT_KEYS = (
    "PILOT-ONLY-NEED-01",
    "PILOT-ONLY-INTERFACE-02",
    "PILOT-ONLY-ACCEPTANCE-03",
    "PILOT-ONLY-LEGACY-04",
    "PILOT-ONLY-G2-05",
)
EXPECTED_PARENTS = {
    "PILOT-ONLY-INTERFACE-02": "PILOT-ONLY-NEED-01",
    "PILOT-ONLY-ACCEPTANCE-03": "PILOT-ONLY-NEED-01",
    "PILOT-ONLY-LEGACY-04": "PILOT-ONLY-NEED-01",
    "PILOT-ONLY-G2-05": "PILOT-ONLY-INTERFACE-02",
}


def strictdoc_command() -> str:
    command = Path(sys.executable).with_name("strictdoc")
    assert command.is_file(), "strictdoc must be installed in the isolated pilot environment"
    return str(command)


def export(source: Path, output: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            strictdoc_command(),
            "export",
            "--config",
            str(source / "strictdoc_config.py"),
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
    assert "Generated review projection; edit pilot_structure.json" in html
    assert "Git branch:" in html
    assert "@GIT_VERSION" not in html


def test_fixed_version_accepts_and_renders_declared_custom_field(tmp_path: Path) -> None:
    """Retain the exact positive counterexample to the former fixed-field claim."""
    source = tmp_path / "custom-grammar"
    source.mkdir()
    shutil.copy2(CUSTOM_GRAMMAR_PROBE, source / CUSTOM_GRAMMAR_PROBE.name)
    shutil.copy2(PILOT_DIRECTORY / "strictdoc_config.py", source / "strictdoc_config.py")
    shutil.copy2(PILOT_DIRECTORY / "presentation.css", source / "presentation.css")
    result = export(source, tmp_path / "custom-html")
    assert result.returncode == 0, result.stderr or result.stdout
    html = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (tmp_path / "custom-html").rglob("*.html")
    )
    assert "ACCEPTANCE" in html
    assert "reader and native HTML exporter accept and render" in html


def test_native_export_copies_the_source_owned_presentation_asset(tmp_path: Path) -> None:
    result = export(PILOT_DIRECTORY, tmp_path / "html")
    assert result.returncode == 0, result.stderr or result.stdout
    document = next((tmp_path / "html").rglob("b0_phase1_pilot.html"))
    copied_css = document.parents[1] / "_static" / "custom.css"
    source_css = PILOT_DIRECTORY / "presentation.css"
    assert 'href="../_static/custom.css"' in document.read_text(encoding="utf-8")
    assert copied_css.read_text(encoding="utf-8") == source_css.read_text(encoding="utf-8")
    assert '.layout_tree' in source_css.read_text(encoding="utf-8")
    assert 'structured review projection' in source_css.read_text(encoding="utf-8")
    assert 'data-field-label="statement"' in source_css.read_text(encoding="utf-8")


def test_native_export_has_record_navigation_and_parent_links(tmp_path: Path) -> None:
    result = export(PILOT_DIRECTORY, tmp_path / "html")
    assert result.returncode == 0, result.stderr or result.stdout
    document = next((tmp_path / "html").rglob("b0_phase1_pilot.html"))
    html = document.read_text(encoding="utf-8")
    toc_start = html.index('data-testid="toc-list"')
    navigation = html[toc_start : html.index("</turbo-frame>", toc_start)]
    for key in PILOT_KEYS:
        assert f'href="#{key}"' in navigation
        assert f'data-uid="{key}"' in html
    for child, parent in EXPECTED_PARENTS.items():
        start = html.index(f'data-uid="{child}"')
        end = html.find('data-uid="', start + 1)
        record = html[start:] if end == -1 else html[start:end]
        assert 'data-field-label="parent relations"' in record
        assert f'class="requirement__link-parent" href="#{parent}"' in record
        assert f'>{parent}</span>' in record


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
