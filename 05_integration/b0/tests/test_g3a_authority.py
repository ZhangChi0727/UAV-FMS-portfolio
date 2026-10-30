"""Synthetic metadata-only tests; source written but not executed in static phase.

No production loader, component, binding import, simulation or seed is needed.
These tests do not qualify the actual G3-A environment or real lifecycle.
"""

from __future__ import annotations

import ast
import base64
import builtins
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import textwrap
import zlib

import pytest

from binding_checks import g3a_authority as authority


def test_workflow_exact_startup_fixture_mode(tmp_path):
    """Invoke the exact workflow payload; do not maintain a second startup parser."""
    repository = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    workflow_path = os.path.join(repository, ".github", "workflows", "g3a.yml")
    with open(workflow_path, encoding="utf-8", newline="") as source:
        workflow = source.read()
    production_blob = re.findall(
        r'^  G3A_STARTUP_PRODUCTION_ZLIB_BASE64: "([A-Za-z0-9+/=]+)"$',
        workflow,
        flags=re.MULTILINE,
    )
    assert len(production_blob) == 1
    payload = zlib.decompress(base64.b64decode(production_blob[0], validate=True))
    assert len(payload) == 39456
    assert hashlib.sha256(payload).hexdigest() == (
        "0c15f02d71f4ca86372c6211cfdf8c1084beba25ae41ced97b65b53f132dd218"
    )
    fixture_blob = re.findall(
        r'^  G3A_STARTUP_FIXTURES_ZLIB_BASE64: "([A-Za-z0-9+/=]+)"$',
        workflow,
        flags=re.MULTILINE,
    )
    assert len(fixture_blob) == 1
    seal = tmp_path / "startup-fixture-seal.json"
    environment = dict(os.environ)
    environment["G3A_STARTUP_FIXTURES_ZLIB_BASE64"] = fixture_blob[0]
    completed = subprocess.run(
        [sys.executable, "-I", "-B", "-S", "-", "--fixture-mode", str(seal)],
        input=payload,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env=environment,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")
    result = json.loads(completed.stdout)
    assert result == {"fixture_atoms": 79, "passed": 7, "rejected": 72}
    sealed = json.loads(seal.read_bytes())
    assert sealed["schema_version"] == "b0-g3a-startup-fixture-seal/v1"
    assert sealed["fixture_atoms"] == 79
    assert sealed["materialization_failures"] == 0


def _startup_production_namespace():
    repository = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    workflow_path = os.path.join(repository, ".github", "workflows", "g3a.yml")
    with open(workflow_path, encoding="utf-8", newline="") as source:
        workflow = source.read()
    production_blob = re.findall(
        r'^  G3A_STARTUP_PRODUCTION_ZLIB_BASE64: "([A-Za-z0-9+/=]+)"$',
        workflow,
        flags=re.MULTILINE,
    )
    assert len(production_blob) == 1
    payload = zlib.decompress(base64.b64decode(production_blob[0], validate=True))
    assert len(payload) == 39456
    assert hashlib.sha256(payload).hexdigest() == (
        "0c15f02d71f4ca86372c6211cfdf8c1084beba25ae41ced97b65b53f132dd218"
    )
    namespace = {"__name__": "g3a_startup_scan_test", "__file__": "<workflow-production>"}
    exec(compile(payload, "<workflow-production>", "exec"), namespace)
    return namespace


def _gcc_discovery_functions():
    """Extract only the production GCC discovery/admission functions from the workflow."""
    repository = Path(__file__).resolve().parents[3]
    workflow = (repository / ".github" / "workflows" / "g3a.yml").read_text(
        encoding="utf-8"
    )
    step = workflow.index("Assemble current CI environment facts without importing the DUT")
    start = workflow.index("          from __future__ import annotations", step)
    end = workflow.index("\n          PY\n", start)
    production = textwrap.dedent(workflow[start:end])
    parsed = ast.parse(production, filename="<g3a-environment-facts>")
    wanted = {"discover_gcc_subtools", "admit_gcc_subtools"}
    functions = [
        node
        for node in parsed.body
        if isinstance(node, ast.FunctionDef) and node.name in wanted
    ]
    assert {node.name for node in functions} == wanted
    isolated = ast.Module(body=functions, type_ignores=[])
    ast.fix_missing_locations(isolated)
    namespace = {"Path": Path, "hashlib": hashlib, "re": re}
    exec(compile(isolated, "<g3a-gcc-discovery>", "exec"), namespace)
    return namespace["discover_gcc_subtools"], namespace["admit_gcc_subtools"]


class _ScanJournal:
    def __init__(self):
        self.records = []

    def add(self, value):
        self.records.append(value)


def test_startup_live_scan_accepts_53_ordinary_cache_entries(tmp_path):
    production = _startup_production_namespace()
    root = tmp_path / "stdlib"
    cache = root / "__pycache__"
    cache.mkdir(parents=True)
    for index in range(53):
        (cache / f"module_{index:04d}.cpython-311.pyc").write_bytes(b"")
    journal = _ScanJournal()

    production["scan_customization_root"](root, 0, journal)

    assert journal.records == [{
        "label": "customization.0.pycache",
        "status": "enumerated",
        "entries": 53,
        "entry_limit": 4096,
    }]


def test_startup_live_scan_rejects_late_sitecustomize_cache_entry(tmp_path):
    production = _startup_production_namespace()
    root = tmp_path / "stdlib"
    cache = root / "__pycache__"
    cache.mkdir(parents=True)
    for index in range(52):
        (cache / f"module_{index:04d}.cpython-311.pyc").write_bytes(b"")
    dangerous = cache / "sitecustomize.cpython-311.pyc"
    dangerous.write_bytes(b"synthetic-not-executed")
    journal = _ScanJournal()

    with pytest.raises(production["Reject"]) as caught:
        production["scan_customization_root"](root, 0, journal)

    assert caught.value.code == "CUSTOMIZATION_PRESENT_OR_REFUSED"
    assert caught.value.locator == "customization.entry"
    assert journal.records[-1] == {
        "label": "customization.0.sitecustomize.cpython-311.pyc",
        "status": "refused",
        "kind": "regular",
    }


def test_startup_live_scan_rejects_directory_cap_plus_one(tmp_path):
    production = _startup_production_namespace()
    root = tmp_path / "stdlib"
    cache = root / "__pycache__"
    cache.mkdir(parents=True)
    for index in range(4097):
        (cache / f"module_{index:04d}.cpython-311.pyc").write_bytes(b"")
    journal = _ScanJournal()

    with pytest.raises(production["Reject"]) as caught:
        production["scan_customization_root"](root, 0, journal)

    assert caught.value.code == "ACQ_LIMIT_EXCEEDED"
    assert caught.value.locator == "acquisition.entry_count"
    assert journal.records[-1] == {
        "label": "customization.0.pycache",
        "status": "count_exceeded",
        "entries": 4097,
    }


def test_startup_live_scan_rejects_unsafe_cache(tmp_path):
    production = _startup_production_namespace()
    root = tmp_path / "stdlib"
    root.mkdir()
    (root / "__pycache__").write_bytes(b"synthetic-nondirectory")
    journal = _ScanJournal()

    with pytest.raises(production["Reject"]) as caught:
        production["scan_customization_root"](root, 0, journal)

    assert caught.value.code == "CUSTOMIZATION_PRESENT_OR_REFUSED"
    assert caught.value.locator == "customization.entry"
    assert journal.records == [{
        "label": "customization.0.__pycache__",
        "status": "refused",
        "reason": "unsafe_cache",
    }]


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _gcc_fixture(tmp_path, compiler_name="x86_64-linux-gnu-g++-13"):
    compiler = tmp_path / compiler_name
    compiler.write_bytes(b"fixture-compiler")
    library_base = tmp_path / "usr-lib-gcc"
    libexec_base = tmp_path / "usr-libexec-gcc"
    (library_base / "13").mkdir(parents=True)
    (libexec_base / "13").mkdir(parents=True)
    return compiler, library_base, libexec_base


def _write_gcc_fixture(root, name, raw):
    path = root / "13" / name
    path.write_bytes(raw)
    return path


def _selected_by_path(discovery):
    return {item["resolved_path"]: item for item in discovery["selected_files"]}


def test_gcc_subtool_discovery_accepts_legacy_single_root(tmp_path):
    discover, admit = _gcc_discovery_functions()
    compiler, library_base, libexec_base = _gcc_fixture(tmp_path)
    cc1plus = _write_gcc_fixture(library_base, "cc1plus", b"legacy-cc1plus")
    collect2 = _write_gcc_fixture(library_base, "collect2", b"legacy-collect2")
    plugin = _write_gcc_fixture(library_base, "liblto_plugin.so", b"legacy-plugin")

    discovery = discover(compiler, library_base, libexec_base)
    admitted = admit(discovery)

    assert discovery["status"] == "observed_not_admitted"
    assert discovery["gcc_major"] == "13"
    assert len(discovery["candidates"]) == 10
    assert discovery["roots"] == [
        str((library_base / "13").absolute()),
        str((libexec_base / "13").absolute()),
    ]
    selected = _selected_by_path(discovery)
    expected = {
        str(cc1plus.resolve()): ("cc1plus", b"legacy-cc1plus"),
        str(collect2.resolve()): ("collect2", b"legacy-collect2"),
        str(plugin.resolve()): ("liblto_plugin.so", b"legacy-plugin"),
    }
    assert set(selected) == set(expected)
    assert len(admitted) == 3
    for path, (logical_name, raw) in expected.items():
        assert selected[path]["logical_names"] == [logical_name]
        assert selected[path]["bytes"] == len(raw)
        assert selected[path]["sha256"] == _sha(raw)


def test_gcc_subtool_discovery_accepts_split_libexec_layout(tmp_path):
    discover, admit = _gcc_discovery_functions()
    compiler, library_base, libexec_base = _gcc_fixture(tmp_path)
    plugin = _write_gcc_fixture(library_base, "liblto_plugin.so", b"split-plugin")
    cc1plus = _write_gcc_fixture(libexec_base, "cc1plus", b"split-cc1plus")
    collect2 = _write_gcc_fixture(libexec_base, "collect2", b"split-collect2")
    lto1 = _write_gcc_fixture(libexec_base, "lto1", b"split-lto1")

    discovery = discover(compiler, library_base, libexec_base)
    admit(discovery)
    selected = _selected_by_path(discovery)

    assert set(selected) == {
        str(plugin.resolve()),
        str(cc1plus.resolve()),
        str(collect2.resolve()),
        str(lto1.resolve()),
    }
    observed = {
        (item["logical_name"], item["input_path"]): item
        for item in discovery["candidates"]
    }
    assert observed[("cc1plus", str(cc1plus.absolute()))]["is_file"] is True
    assert observed[("collect2", str(collect2.absolute()))]["sha256"] == _sha(
        b"split-collect2"
    )


def test_gcc_subtool_discovery_deduplicates_resolved_aliases(tmp_path):
    discover, admit = _gcc_discovery_functions()
    compiler, library_base, libexec_base = _gcc_fixture(tmp_path)
    _write_gcc_fixture(libexec_base, "cc1plus", b"alias-cc1plus")
    _write_gcc_fixture(libexec_base, "collect2", b"alias-collect2")
    plugin = _write_gcc_fixture(library_base, "liblto_plugin.so", b"alias-plugin")
    plugin_alias = libexec_base / "13" / "liblto_plugin.so"
    plugin_alias.symlink_to(plugin)

    discovery = discover(compiler, library_base, libexec_base)
    admit(discovery)
    selected = _selected_by_path(discovery)
    plugin_record = selected[str(plugin.resolve())]

    assert len(selected) == 3
    assert plugin_record["logical_names"] == [
        "liblto_plugin.so",
        "liblto_plugin.so",
    ]
    assert plugin_record["input_paths"] == [
        str(plugin.absolute()),
        str(plugin_alias.absolute()),
    ]


def test_gcc_subtool_admission_accepts_required_helpers_with_same_target_aliases(
    tmp_path,
):
    discover, admit = _gcc_discovery_functions()
    compiler, library_base, libexec_base = _gcc_fixture(tmp_path)
    cc1plus = tmp_path / "cc1plus-real"
    cc1plus.write_bytes(b"aliased-cc1plus")
    collect2 = tmp_path / "collect2-real"
    collect2.write_bytes(b"aliased-collect2")
    plugin = tmp_path / "plugin-real"
    plugin.write_bytes(b"aliased-plugin")
    for root in (library_base, libexec_base):
        (root / "13" / "cc1plus").symlink_to(cc1plus)
        (root / "13" / "collect2").symlink_to(collect2)
        (root / "13" / "liblto_plugin.so").symlink_to(plugin)

    discovery = discover(compiler, library_base, libexec_base)
    admitted = admit(discovery)
    selected = _selected_by_path(discovery)

    assert set(selected) == {
        str(cc1plus.resolve()),
        str(collect2.resolve()),
        str(plugin.resolve()),
    }
    assert len(admitted) == 3
    assert selected[str(cc1plus.resolve())]["logical_names"] == [
        "cc1plus",
        "cc1plus",
    ]
    assert selected[str(collect2.resolve())]["logical_names"] == [
        "collect2",
        "collect2",
    ]


def test_gcc_subtool_admission_refuses_one_role_with_distinct_resolved_targets(
    tmp_path,
):
    discover, admit = _gcc_discovery_functions()
    compiler, library_base, libexec_base = _gcc_fixture(tmp_path)
    first = _write_gcc_fixture(library_base, "cc1plus", b"first-cc1plus")
    second = _write_gcc_fixture(libexec_base, "cc1plus", b"second-cc1plus")
    _write_gcc_fixture(libexec_base, "collect2", b"one-collect2")

    discovery = discover(compiler, library_base, libexec_base)
    with pytest.raises(RuntimeError, match="missing or ambiguous") as caught:
        admit(discovery)

    diagnostic = str(caught.value)
    assert str(first.resolve()) in diagnostic
    assert str(second.resolve()) in diagnostic


@pytest.mark.parametrize("present", [(), ("cc1plus",), ("collect2",)])
def test_gcc_subtool_admission_refuses_plugin_only_or_missing_required_helper(
    tmp_path, present
):
    discover, admit = _gcc_discovery_functions()
    compiler, library_base, libexec_base = _gcc_fixture(tmp_path)
    _write_gcc_fixture(library_base, "liblto_plugin.so", b"required-plugin")
    for name in present:
        _write_gcc_fixture(libexec_base, name, f"required-{name}".encode("ascii"))

    discovery = discover(compiler, library_base, libexec_base)
    with pytest.raises(RuntimeError, match="required GCC executable helper missing"):
        admit(discovery)


def test_gcc_subtool_admission_refuses_required_helpers_with_one_resolved_file(tmp_path):
    discover, admit = _gcc_discovery_functions()
    compiler, library_base, libexec_base = _gcc_fixture(tmp_path)
    shared = tmp_path / "shared-helper"
    shared.write_bytes(b"shared-required-helper")
    (library_base / "13" / "cc1plus").symlink_to(shared)
    (libexec_base / "13" / "collect2").symlink_to(shared)

    discovery = discover(compiler, library_base, libexec_base)
    with pytest.raises(RuntimeError, match="resolve to the same file"):
        admit(discovery)


def test_gcc_subtool_discovery_refuses_compiler_without_explicit_major(tmp_path):
    discover, _ = _gcc_discovery_functions()
    compiler, library_base, libexec_base = _gcc_fixture(tmp_path, compiler_name="c++")

    with pytest.raises(RuntimeError, match="does not expose an explicit GCC major"):
        discover(compiler, library_base, libexec_base)


def test_gcc_subtool_policy_and_workflow_digest_keep_the_finite_gate():
    repository = Path(__file__).resolve().parents[3]
    policy_path = repository / "05_integration" / "b0" / "configs" / (
        "g3a_authority_policy.v1.json"
    )
    workflow_path = repository / ".github" / "workflows" / "g3a.yml"
    policy_raw = policy_path.read_bytes()
    policy = json.loads(policy_raw)
    rule = policy["environment"]["file_role_rules"]["tool:compiler_subtools"]

    assert rule == {
        "allowed_roots": [
            "/usr/lib/gcc/x86_64-linux-gnu",
            "/usr/libexec/gcc/x86_64-linux-gnu",
        ],
        "allowed_paths": [],
        "min_files": 2,
        "max_files": 12,
    }
    workflow = workflow_path.read_text(encoding="utf-8")
    bound = re.findall(r"^  G3A_POLICY_SHA256: ([0-9a-f]{64})$", workflow, re.MULTILINE)
    assert bound == [hashlib.sha256(policy_raw).hexdigest()]


def _debug_configure_package(workflow: str) -> str:
    start = workflow.index("Materialize debug_configure run body part 1 of 4")
    end = workflow.index(
        "Configure Debug from the explicit disconnected Catch2 source", start
    )
    materializers = workflow[start:end]
    payloads = re.findall(r'payload_b64 = b"([A-Za-z0-9+/=]+)"', materializers)
    descriptors = re.findall(
        r'"([0-9]+)" \\\n\s+"([0-9a-f]{64})" <<\'PY\'', materializers
    )
    assert len(payloads) == len(descriptors) == 4
    parts = []
    for encoded, (expected_length, expected_digest) in zip(
        payloads, descriptors, strict=True
    ):
        part = base64.b64decode(encoded, validate=True)
        assert len(part) == int(expected_length)
        assert len(part) <= 10_000
        assert hashlib.sha256(part).hexdigest() == expected_digest
        parts.append(part)
    package = b"".join(parts)
    executor = workflow[end:]
    identity = re.search(
        r'"debug_configure" \\\n\s+"([0-9]+)" \\\n\s+"([0-9a-f]{64})" \\',
        executor,
    )
    assert identity is not None
    assert len(package) == int(identity.group(1))
    assert hashlib.sha256(package).hexdigest() == identity.group(2)
    assert _debug_configure_executor_materializer_ids(workflow) == [
        "package_debug_configure_part_1",
        "package_debug_configure_part_2",
        "package_debug_configure_part_3",
        "package_debug_configure_part_4",
    ]
    return package.decode("utf-8", errors="strict")


def _debug_configure_executor_materializer_ids(workflow: str) -> list[str]:
    start = workflow.index(
        "Configure Debug from the explicit disconnected Catch2 source"
    )
    end = workflow.index("Materialize debug_build run body part 1 of 3", start)
    executor = workflow[start:end]
    assert '"debug_configure" \\' in executor
    stops = re.findall(
        r'"materializer_step_ids": \[f"package_\{step_id\}_part_\{number\}" '
        r"for number in range\(1, ([0-9]+)\)\]",
        executor,
    )
    assert stops == ["5"]
    return [f"package_debug_configure_part_{number}" for number in range(1, 5)]


def test_debug_configure_derivation_rejects_missing_fourth_materializer_id():
    repository = Path(__file__).resolve().parents[3]
    workflow = (repository / ".github" / "workflows" / "g3a.yml").read_text(
        encoding="utf-8"
    )
    start = workflow.index(
        "Configure Debug from the explicit disconnected Catch2 source"
    )
    end = workflow.index("Materialize debug_build run body part 1 of 3", start)
    executor = workflow[start:end]
    assert executor.count("range(1, 5)") == 1
    mutated_executor = executor.replace("range(1, 5)", "range(1, 4)", 1)
    mutated = workflow[:start] + mutated_executor + workflow[end:]
    with pytest.raises(AssertionError):
        _debug_configure_package(mutated)


def _debug_configure_sources() -> tuple[str, str, str, str]:
    repository = Path(__file__).resolve().parents[3]
    workflow = (repository / ".github" / "workflows" / "g3a.yml").read_text(
        encoding="utf-8"
    )
    script = _debug_configure_package(workflow)

    def heredoc(start_marker: str, end_marker: str) -> str:
        assert script.count(start_marker) == 1
        start = script.index(start_marker) + len(start_marker)
        assert script.count(end_marker, start) == 1
        return script[start:script.index(end_marker, start)]

    directory_guard = heredoc(
        '"${directory_guard_command[@]}" <<\'PY\'\n',
        "\nPY\nroot_command=(",
    )
    environment_guard = heredoc(
        'debug-configure-allowlist-check.log" 2>&1 <<\'PY\'\n',
        "\nPY\nallowlist_check_rc=$?",
    )
    process_checker = heredoc(
        'debug-configure-process-check.log" 2>&1 <<\'PY\'\n',
        "\nPY\nprocess_check_rc=$?",
    )
    return script, directory_guard, environment_guard, process_checker


def _actual_embedded_functions(source: str, names: set[str]) -> dict[str, object]:
    tree = ast.parse(source)
    selected = [
        node
        for node in tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
        or isinstance(node, ast.FunctionDef) and node.name in names
    ]
    found = {node.name for node in selected if isinstance(node, ast.FunctionDef)}
    assert found == names
    namespace: dict[str, object] = {}
    module = ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[]))
    exec(compile(module, "<actual-debug-configure-guard>", "exec"), namespace)
    return namespace


def _build_package_sources(stage: str) -> tuple[str, str, str, str]:
    repository = Path(__file__).resolve().parents[3]
    workflow = (repository / ".github" / "workflows" / "g3a.yml").read_text(
        encoding="utf-8"
    )
    display = stage.replace("_", "-")
    title = "Debug" if stage == "debug_build" else "Release"
    start = workflow.index(f"Materialize {stage} run body part 1 of 3")
    end = workflow.index(f"Build only the {title} production controller module", start)
    materializers = workflow[start:end]
    payloads = re.findall(r'payload_b64 = b"([A-Za-z0-9+/=]+)"', materializers)
    descriptors = re.findall(
        r'"([0-9]+)" \\\n\s+"([0-9a-f]{64})" <<\'PY\'', materializers
    )
    assert len(payloads) == len(descriptors) == 3
    parts = []
    for encoded, (expected_length, expected_digest) in zip(
        payloads, descriptors, strict=True
    ):
        part = base64.b64decode(encoded, validate=True)
        assert len(part) == int(expected_length)
        assert len(part) <= 13_000
        assert hashlib.sha256(part).hexdigest() == expected_digest
        parts.append(part)
    package = b"".join(parts)
    executor = workflow[end:]
    identity = re.search(
        rf'"{stage}" \\\n\s+"([0-9]+)" \\\n\s+"([0-9a-f]{{64}})" \\', executor
    )
    assert identity is not None
    assert len(package) == int(identity.group(1))
    assert hashlib.sha256(package).hexdigest() == identity.group(2)
    script = package.decode("utf-8", errors="strict")

    def heredoc(start_marker: str, end_marker: str) -> str:
        assert script.count(start_marker) == 1
        begin = script.index(start_marker) + len(start_marker)
        assert script.count(end_marker, begin) == 1
        return script[begin:script.index(end_marker, begin)]

    directory_guard = heredoc(
        '"${directory_guard_command[@]}" <<\'PY\'\n', "\nPY\nroot_command=("
    )
    environment_guard = heredoc(
        f'{display}-allowlist-check.log" 2>&1 <<\'PY\'\n',
        "\nPY\nallowlist_check_rc=$?",
    )
    process_checker = heredoc(
        f'{display}-process-check.log" 2>&1 <<\'PY\'\n',
        "\nPY\nprocess_check_rc=$?",
    )
    return script, directory_guard, environment_guard, process_checker


@pytest.mark.parametrize(
    ("stage", "profile_key"),
    [
        ("debug_build", "debug_build_execution_profile"),
        ("release_build", "release_build_execution_profile"),
    ],
)
def test_build_profiles_and_generated_consumers_are_exactly_bound(stage, profile_key):
    script, directory_guard, environment_guard, process_checker = (
        _build_package_sources(stage)
    )
    repository = Path(__file__).resolve().parents[3]
    policy = json.loads(
        (repository / "05_integration" / "b0" / "configs" /
         "g3a_authority_policy.v1.json").read_bytes()
    )["environment"][profile_key]
    display = stage.replace("_", "-")
    assert policy["scope"] == f"{stage}_only"
    assert policy["environment"] == {
        "PATH": "/usr/bin:/bin:$G3A_VENV/bin",
        "HOME": f"$G3A_EVIDENCE_ROOT/{display}-home",
        "PYTHONUSERBASE": f"$G3A_EVIDENCE_ROOT/{display}-python-user-base",
        "ambient_policy": (
            "deexport_all_functions_clear_all_inherited_exports_then_export_only_listed_values"
        ),
        "isolated_directory_policy": (
            "fresh_absent_before_create_ordinary_empty_direct_child_of_evidence_root"
        ),
    }
    assert policy["tracee_task_cap"] == 192
    assert policy["family_exec_caps"] == {
        "cmake": 16,
        "ninja": 8,
        "python": 4,
        "compiler": 16,
        "compiler_subtools": 64,
        "binutils": 64,
        "shell": 32,
        "platform": 4,
    }
    assert policy["launch_environment_validation"] == (
        "derive_expected_HOME_and_PYTHONUSERBASE_from_canonical_evidence_root_and_"
        f"fixed_{stage}_names_then_require_ordinary_nonsymlink_empty_direct_children"
    )
    assert 'admitted_path="/usr/bin:/bin:$G3A_VENV/bin"' in script
    assert 'admitted_path="$G3A_VENV/bin:/usr/bin:/bin"' not in script
    assert f'isolated_home="$G3A_EVIDENCE_ROOT/{display}-home"' in script
    assert (
        f'isolated_python_user_base="$G3A_EVIDENCE_ROOT/{display}-python-user-base"'
        in script
    )
    assert 'export HOME="$isolated_home"' in script
    assert 'export PYTHONUSERBASE="$isolated_python_user_base"' in script
    assert "def validate_launch_environment" in environment_guard
    assert f'evidence_root / "{display}-home"' in environment_guard
    assert f'evidence_root / "{display}-python-user-base"' in environment_guard
    assert "def prepare_isolated_directories" in directory_guard
    assert 'errors.append("one or more network connect attempts were traced")' in (
        process_checker
    )
    assert 'errors.append("unknown or unparsed process event present")' in (
        process_checker
    )


def _build_environment_validator(stage: str):
    _, _, environment_guard, _ = _build_package_sources(stage)
    return _actual_embedded_functions(
        environment_guard, {"validate_launch_environment"}
    )["validate_launch_environment"]


def _expected_build_environment(
    evidence_root: Path, stage: str, executable: str
) -> dict[str, str]:
    display = stage.replace("_", "-")
    return {
        "PATH": "/usr/bin:/bin:" + str(Path(executable).parent),
        "HOME": str(evidence_root / f"{display}-home"),
        "PYTHONUSERBASE": str(evidence_root / f"{display}-python-user-base"),
        "VIRTUAL_ENV": str(Path(executable).parent.parent),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPYCACHEPREFIX": str(evidence_root / "pycache"),
        "PYTHONHASHSEED": "0",
        "LANG": "C",
        "LC_ALL": "C",
        "_": "/usr/bin/timeout",
    }


@pytest.mark.parametrize("stage", ["debug_build", "release_build"])
def test_actual_build_environment_validator_accepts_exact_safe_directories(
    tmp_path, stage
):
    validate = _build_environment_validator(stage)
    evidence_root = tmp_path / stage
    evidence_root.mkdir()
    display = stage.replace("_", "-")
    (evidence_root / f"{display}-home").mkdir()
    (evidence_root / f"{display}-python-user-base").mkdir()
    executable = "/fixture/g3a-venv/bin/python"
    environment = _expected_build_environment(evidence_root, stage, executable)
    assert validate(
        environment,
        executable,
        evidence_root / "environment-facts.json",
    ) == environment


@pytest.mark.parametrize("stage", ["debug_build", "release_build"])
@pytest.mark.parametrize("target_name", ["HOME", "PYTHONUSERBASE"])
@pytest.mark.parametrize("fixture", ["wrong_nonempty", "polluted", "symlink"])
def test_actual_build_environment_validator_rejects_wrong_or_unsafe_directories(
    tmp_path, stage, target_name, fixture
):
    validate = _build_environment_validator(stage)
    evidence_root = tmp_path / stage
    evidence_root.mkdir()
    display = stage.replace("_", "-")
    home = evidence_root / f"{display}-home"
    python_user_base = evidence_root / f"{display}-python-user-base"
    home.mkdir()
    python_user_base.mkdir()
    target_path = home if target_name == "HOME" else python_user_base
    executable = "/fixture/g3a-venv/bin/python"
    environment = _expected_build_environment(evidence_root, stage, executable)
    expected = {
        "wrong_nonempty": "launch_environment_not_exact_admitted_mapping",
        "polluted": "isolated_launch_directory_not_empty",
        "symlink": "isolated_launch_directory_not_ordinary",
    }[fixture]
    if fixture == "wrong_nonempty":
        wrong = tmp_path / f"{stage}-wrong-{target_name.lower()}"
        wrong.mkdir()
        (wrong / "unexpected").write_text("fixture", encoding="utf-8")
        environment[target_name] = str(wrong)
    elif fixture == "polluted":
        (target_path / "unexpected").write_text("fixture", encoding="utf-8")
    else:
        target_path.rmdir()
        target = tmp_path / f"{stage}-{target_name.lower()}-symlink-target"
        target.mkdir()
        target_path.symlink_to(target, target_is_directory=True)
    with pytest.raises(RuntimeError, match=expected):
        validate(
            environment,
            executable,
            evidence_root / "environment-facts.json",
        )


@pytest.mark.parametrize("stage", ["debug_build", "release_build"])
@pytest.mark.parametrize("fixture", ["preexisting", "nonempty", "symlink", "escape"])
def test_build_directory_guards_reject_filesystem_counterexamples(
    tmp_path, stage, fixture
):
    _, directory_guard, _, _ = _build_package_sources(stage)
    prepare = _actual_embedded_functions(
        directory_guard, {"prepare_isolated_directories"}
    )["prepare_isolated_directories"]
    display = stage.replace("_", "-")
    root = tmp_path / display
    root.mkdir()
    candidates = [
        str(root / f"{display}-home"),
        str(root / f"{display}-python-user-base"),
    ]
    first = Path(candidates[0])
    expected = {
        "preexisting": "isolated_directory_preexisting",
        "nonempty": "isolated_directory_nonempty",
        "symlink": "isolated_directory_symlink",
        "escape": "isolated_directory_escape_or_name_mismatch",
    }[fixture]
    if fixture == "preexisting":
        first.mkdir()
    elif fixture == "nonempty":
        first.mkdir()
        (first / "unexpected").write_text("fixture", encoding="utf-8")
    elif fixture == "symlink":
        target = root / "symlink-target"
        target.mkdir()
        first.symlink_to(target, target_is_directory=True)
    else:
        candidates[0] = str(root.parent / "escaped-home")
    with pytest.raises(RuntimeError, match=expected):
        prepare(str(root), candidates)


def _debug_configure_policy() -> dict[str, object]:
    repository = Path(__file__).resolve().parents[3]
    return json.loads(
        (repository / "05_integration" / "b0" / "configs" /
         "g3a_authority_policy.v1.json").read_bytes()
    )["environment"]["debug_configure_execution_profile"]


def test_debug_configure_profile_and_generated_consumer_are_exactly_bound():
    script, directory_guard, environment_guard, process_checker = (
        _debug_configure_sources()
    )
    profile = _debug_configure_policy()
    assert profile["scope"] == "debug_configure_only"
    assert profile["environment"] == {
        "PATH": "/usr/bin:/bin:$G3A_VENV/bin",
        "HOME": "$G3A_EVIDENCE_ROOT/debug-configure-home",
        "PYTHONUSERBASE": "$G3A_EVIDENCE_ROOT/debug-configure-python-user-base",
        "ambient_policy": (
            "deexport_all_functions_clear_all_inherited_exports_then_export_only_listed_values"
        ),
        "isolated_directory_policy": (
            "fresh_absent_before_create_ordinary_empty_direct_child_of_evidence_root"
        ),
    }
    assert profile["absolute_tool_entrypoints"] == {
        "cmake": "$G3A_VENV/bin/cmake",
        "python": "$G3A_VENV/bin/python",
        "ninja": "$G3A_VENV/bin/ninja",
        "compiler": "/usr/bin/c++",
        "supervisor": "/usr/bin/timeout",
        "trace": "/usr/bin/strace",
    }
    assert profile["tracee_task_cap"] == 256
    assert profile["family_exec_caps"] == {
        "cmake": 32,
        "ninja": 16,
        "python": 16,
        "compiler": 16,
        "compiler_subtools": 64,
        "binutils": 64,
        "shell": 32,
        "platform": 8,
    }
    assert 'admitted_path="/usr/bin:/bin:$G3A_VENV/bin"' in script
    assert 'admitted_path="$G3A_VENV/bin:/usr/bin:/bin"' not in script
    assert '  "$G3A_VENV/bin/cmake"' in script
    assert '-DPython3_EXECUTABLE="$G3A_VENV/bin/python"' in script
    assert '-DCMAKE_MAKE_PROGRAM="$G3A_VENV/bin/ninja"' in script
    assert '-DCMAKE_CXX_COMPILER=/usr/bin/c++' in script
    assert "/usr/bin/timeout --signal=TERM --kill-after=10s 120s" in script
    assert "/usr/bin/strace -ff -q -s 4096 -e trace=process,connect" in script
    assert "printf 'cap.tracee_tasks=256\\n'" in script
    assert "printf 'cap.family_exec.python=16\\n'" in script
    assert "cap.family_exec.python=8" not in script
    expected_caps = (
        "cmake=32,ninja=16,python=16,compiler=16,compiler_subtools=64,"
        "binutils=64,shell=32,platform=8"
    )
    assert script.count(expected_caps) == 1
    assert "def prepare_isolated_directories" in directory_guard
    assert "def validate_launch_environment" in environment_guard
    assert 'errors.append("one or more network connect attempts were traced")' in (
        process_checker
    )
    assert 'errors.append("unknown or unparsed process event present")' in (
        process_checker
    )


def _directory_guard_function():
    _, directory_guard, _, _ = _debug_configure_sources()
    return _actual_embedded_functions(
        directory_guard, {"prepare_isolated_directories"}
    )["prepare_isolated_directories"]


def _isolated_candidates(root: Path) -> list[str]:
    return [
        str(root / "debug-configure-home"),
        str(root / "debug-configure-python-user-base"),
    ]


def test_actual_directory_guard_creates_two_fresh_empty_ordinary_directories(tmp_path):
    prepare = _directory_guard_function()
    candidates = _isolated_candidates(tmp_path)
    prepare(str(tmp_path), candidates)
    for text in candidates:
        path = Path(text)
        assert path.is_dir() and not path.is_symlink()
        assert list(path.iterdir()) == []
        assert path.resolve(strict=True).parent == tmp_path.resolve(strict=True)


@pytest.mark.parametrize("fixture", ["preexisting", "nonempty", "symlink", "escape"])
def test_actual_directory_guard_rejects_filesystem_counterexamples(tmp_path, fixture):
    prepare = _directory_guard_function()
    candidates = _isolated_candidates(tmp_path)
    first = Path(candidates[0])
    expected = {
        "preexisting": "isolated_directory_preexisting",
        "nonempty": "isolated_directory_nonempty",
        "symlink": "isolated_directory_symlink",
        "escape": "isolated_directory_escape_or_name_mismatch",
    }[fixture]
    if fixture == "preexisting":
        first.mkdir()
    elif fixture == "nonempty":
        first.mkdir()
        (first / "unexpected").write_text("fixture", encoding="utf-8")
    elif fixture == "symlink":
        target = tmp_path / "symlink-target"
        target.mkdir()
        first.symlink_to(target, target_is_directory=True)
    else:
        candidates[0] = str(tmp_path.parent / "escaped-home")
    with pytest.raises(RuntimeError, match=expected):
        prepare(str(tmp_path), candidates)


def _valid_launch_environment(root: Path, executable: str) -> dict[str, str]:
    return {
        "PATH": "/usr/bin:/bin:" + str(Path(executable).parent),
        "HOME": str(root / "debug-configure-home"),
        "PYTHONUSERBASE": str(root / "debug-configure-python-user-base"),
        "VIRTUAL_ENV": str(Path(executable).parent.parent),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPYCACHEPREFIX": str(root / "pycache"),
        "PYTHONHASHSEED": "0",
        "LANG": "C",
        "LC_ALL": "C",
        "_": "/usr/bin/timeout",
    }


def test_actual_environment_guard_accepts_exact_map_and_rejects_pollution(tmp_path):
    prepare = _directory_guard_function()
    prepare(str(tmp_path), _isolated_candidates(tmp_path))
    _, _, environment_guard, _ = _debug_configure_sources()
    validate = _actual_embedded_functions(
        environment_guard, {"validate_launch_environment"}
    )["validate_launch_environment"]
    executable = str(tmp_path / "venv" / "bin" / "python")
    environment_path = tmp_path / "environment-facts.json"
    environment = _valid_launch_environment(tmp_path, executable)
    assert validate(environment, executable, environment_path) == environment
    polluted = dict(environment, HTTP_PROXY="http://untrusted.invalid")
    with pytest.raises(RuntimeError, match="exact admitted finite mapping"):
        validate(polluted, executable, environment_path)


def _write_nul(path: Path, values: list[str]) -> None:
    path.write_bytes(b"\0".join(value.encode("utf-8") for value in values) + b"\0")


def _run_actual_process_checker(
    tmp_path: Path, *, python_exec_count: int, extra_events: list[str]
) -> tuple[subprocess.CompletedProcess, dict[str, str]]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    _, _, _, checker = _debug_configure_sources()
    timeout_path = Path("/usr/bin/timeout")
    strace_path = Path("/usr/bin/strace")
    timeout_digest = hashlib.sha256(timeout_path.resolve(strict=True).read_bytes()).hexdigest()
    strace_digest = hashlib.sha256(strace_path.resolve(strict=True).read_bytes()).hexdigest()
    trace_dir = tmp_path / "trace"
    commands = tmp_path / "commands"
    trace_dir.mkdir()
    commands.mkdir()
    stage = "debug-configure"
    root_expected = "/fixture/cmake"
    python_target = "/fixture/python"
    digest = "1" * 64
    allowlist = tmp_path / "allowlist.tsv"
    allowlist.write_text(
        "schema=b0-g3a-process-executable-allowlist/v1\n"
        f"cmake\t{root_expected}\t{digest}\n"
        f"python\t{python_target}\t{digest}\n"
        f"supervisor\t{timeout_path}\t{timeout_digest}\n"
        f"trace\t{strace_path}\t{strace_digest}\n",
        encoding="utf-8",
    )
    receipt = commands / f"{stage}.process-receipt.txt"
    authorization = commands / f"{stage}.authorization.txt"
    authorization.write_text(
        "wrapper_family_count.supervisor=1\n"
        "wrapper_family_count.trace=1\n"
        f"wrapper.supervisor.path={timeout_path}\n"
        f"wrapper.supervisor.sha256={timeout_digest}\n"
        f"wrapper.trace.path={strace_path}\n"
        f"wrapper.trace.sha256={strace_digest}\n"
        "trace.selector=process,connect\n"
        "network_connect_policy=reject_and_retain_every_connect_record\n",
        encoding="utf-8",
    )
    root_argv = [root_expected]
    trace_argv = [
        str(strace_path), "-ff", "-q", "-s", "4096", "-e", "trace=process,connect",
        "-o", str(trace_dir / "trace"), "--", *root_argv,
    ]
    command_argv = [
        str(timeout_path), "--signal=TERM", "--kill-after=10s", "120s", *trace_argv,
    ]
    _write_nul(commands / f"{stage}.root.argv.nul", root_argv)
    _write_nul(commands / f"{stage}.wrapper-trace.argv.nul", trace_argv)
    _write_nul(commands / f"{stage}.wrapper-supervisor.argv.nul", command_argv)
    _write_nul(commands / f"{stage}.argv.nul", command_argv)
    workspace = "/synthetic/workspace"
    _write_nul(commands / f"{stage}.cwd.nul", [workspace])
    (commands / f"{stage}.cwd.txt").write_text(workspace + "\n", encoding="utf-8")
    events = [f'execve("{root_expected}", ["cmake"], 0x0) = 0']
    events.extend(
        f'execve("{python_target}", ["python"], 0x0) = 0'
        for _ in range(python_exec_count)
    )
    events.extend(extra_events)
    events.append("+++ exited with 0 +++")
    (trace_dir / "trace.100").write_text("\n".join(events) + "\n", encoding="utf-8")
    caps = (
        "cmake=32,ninja=16,python=16,compiler=16,compiler_subtools=64,"
        "binutils=64,shell=32,platform=8"
    )
    completed = subprocess.run(
        [
            sys.executable, "-I", "-B", "-", stage, "0", str(trace_dir),
            str(allowlist), root_expected, str(receipt), str(authorization),
            workspace, "256", "120s", caps, timeout_digest, strace_digest,
        ],
        input=checker.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=30,
    )
    rows = {}
    if receipt.is_file():
        for line in receipt.read_text(encoding="utf-8").splitlines():
            key, value = line.split("=", 1)
            assert key not in rows
            rows[key] = value
    return completed, rows


def test_actual_process_checker_accepts_python_16_and_rejects_17(tmp_path):
    accepted, accepted_rows = _run_actual_process_checker(
        tmp_path / "accepted", python_exec_count=16, extra_events=[]
    )
    assert accepted.returncode == 0, accepted.stderr.decode(errors="replace")
    assert accepted_rows["family_exec_count.python"] == "16"
    assert accepted_rows["authorization_overrun_count"] == "0"
    assert accepted_rows["gate_status"] == "complete_known_process_tree_zero_connect_receipt"
    rejected, rejected_rows = _run_actual_process_checker(
        tmp_path / "rejected", python_exec_count=17, extra_events=[]
    )
    assert rejected.returncode == 97
    assert rejected_rows["family_exec_count.python"] == "17"
    assert rejected_rows["authorization_overrun_count"] == "1"
    assert "family exec cap exceeded:python" in "\n".join(
        value for key, value in rejected_rows.items() if key.startswith("validation_error.")
    )


@pytest.mark.parametrize(
    ("event", "oracle_key"),
    [
        (
            'connect(3, {sa_family=AF_UNIX, sun_path="/var/run/nscd/socket"}, 110) '
            '= -1 ENOENT (No such file or directory)',
            "connect_failed_result_record_count",
        ),
        (
            'connect(3, {sa_family=AF_INET, sin_port=htons(9)}, 16) '
            '= -1 ECONNREFUSED (Connection refused)',
            "connect_failed_result_record_count",
        ),
        (
            'connect(3, {sa_family=AF_INET, sin_port=htons(9)}, 16) = 0',
            "connect_success_result_record_count",
        ),
    ],
)
def test_actual_process_checker_rejects_every_connect_record(tmp_path, event, oracle_key):
    completed, rows = _run_actual_process_checker(
        tmp_path, python_exec_count=0, extra_events=[event]
    )
    assert completed.returncode == 97
    assert rows["connect_trace_record_count"] == "1"
    assert rows[oracle_key] == "1"
    assert rows["network_connect_gate_status"] == "connect_attempt_present_stop_downstream"


@pytest.mark.parametrize(
    "event",
    [
        'execve("/unknown/tool", ["tool"], 0x0) = -1 ENOENT (No such file or directory)',
        'execve("/home/runner/work/_temp/g3a-venv/bin/as", ["as"], 0x0) '
        '= -1 ENOENT (No such file or directory)',
        'execve("/fixture/python", ["python"], 0x0 <unfinished ...>',
        '<... execve resumed> ) = 0',
    ],
)
def test_actual_process_checker_rejects_unknown_failed_unfinished_and_resumed(
    tmp_path, event
):
    completed, rows = _run_actual_process_checker(
        tmp_path, python_exec_count=0, extra_events=[event]
    )
    assert completed.returncode == 97
    assert int(rows["unknown_or_unparsed_process_event_count"]) >= 1
    assert rows["gate_status"] == "incomplete_or_unknown_stop_downstream"


def _parameter_fixture(tmp_path):
    raw = b'{"synthetic_metadata_fixture":true,"x":-0.0}\n'
    (tmp_path / "fixed.json").write_bytes(raw)
    bindings = []
    vectors = {
        "actuator_limits_Nm", "gravity_n_m_s2", "gyro_noise_std_rad_s", "gyro_bias_rad_s",
        "accelerometer_noise_std_m_s2", "accelerometer_bias_m_s2",
        "attitude_kp", "rate_kp", "rate_ki", "rate_kd", "integral_limit_Nm",
        "rate_limit_rad_s", "torque_limit_Nm", "kaw_limit_per_s", "kaw_lag_per_s",
    }
    for kind, fields in authority.PARAMETER_FIELDS.items():
        for field in sorted(fields):
            if field in {"config_path", "g0_config_path"}:
                value, encoding = "fixed.json", "source_relative_path"
            elif field == "imu_period_ticks":
                value, encoding = 2, "exact_json"
            elif field == "inertia_kg_m2":
                value, encoding = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]], "float64_tree"
            elif field in vectors:
                value, encoding = [0.0, 0.0, 1.0], "float64_tree"
            else:
                value, encoding = 1.0, "float64_tree"
            bindings.append({"component": kind, "field": field, "literal": value,
                             "encoding": encoding, "unit": "synthetic_unit",
                             "source_locator": "synthetic unit fixture, not project parameters"})
    return {"parameter_bindings": bindings, "fixed_files": {"fixed.json": _sha(raw)}}, {"fixed.json": raw}


def _basis_fixture():
    identity = {key: "1" * 64 for key in authority.IDENTITY_KEYS}
    identity.update({"source_commit": "2" * 40, "source_tree": "3" * 40,
                     "controller_module_path": "/synthetic/b0_controller.so",
                     "controller_module_abi": "synthetic-test-only",
                     "build_type": "Debug", "seed": authority.SEED,
                     "classification": authority.CLASSIFICATION})
    artifact = b'{"synthetic_fixture":true}\n'
    return {"authority_version": authority.AUTHORITY_VERSION, "identity": identity,
            "parameter_inputs": {"semantics": "synthetic_test_fixture"},
            "artifact_sha256": {"fixed.json": _sha(artifact)},
            "input_artifact_base64": {"fixed.json": base64.b64encode(artifact).decode("ascii")}}


def test_strict_json_refuses_duplicate_keys_and_nonfinite_constants():
    with pytest.raises(authority.AuthorityError, match="duplicate_json_key"):
        authority._decode(b'{"a":1,"a":2}', "fixture")
    with pytest.raises(authority.AuthorityError, match="nonfinite_json"):
        authority._decode(b'{"a":NaN}', "fixture")


def test_policy_expected_digest_is_checked_before_parsing(tmp_path):
    path = tmp_path / "policy.json"
    path.write_bytes(b"deliberately not JSON")
    with pytest.raises(authority.AuthorityError, match="policy_digest_mismatch"):
        authority._load_policy(path, "0" * 64, tmp_path.resolve())


def test_expected_full_parameter_mapping_preserves_types_and_runtime_root(tmp_path):
    policy, source = _parameter_fixture(tmp_path)
    result = authority.expected_parameters(policy, source, tmp_path.resolve())
    assert result["components"]["plant"] == result["components"]["actuator"]
    assert result["components"]["plant"] == result["components"]["imu"]
    assert result["components"]["plant"]["imu_period_ticks"] == 2
    assert type(result["components"]["plant"]["imu_period_ticks"]) is int
    assert result["components"]["plant"]["config_path"] == str((tmp_path / "fixed.json").resolve())
    assert set(result["components"]["estimator"]) == authority.ESTIMATOR_FIELDS
    assert set(result["components"]["controller"]) == authority.CONTROLLER_FIELDS


def test_expected_parameter_pointer_uses_source_bytes_and_signed_zero(tmp_path):
    policy, source = _parameter_fixture(tmp_path)
    item = next(item for item in policy["parameter_bindings"]
                if item["component"] == "estimator" and item["field"] == "sample_period_s")
    item.pop("literal")
    item.update({"source_path": "fixed.json", "json_pointer": "/x"})
    result = authority.expected_parameters(policy, source, tmp_path.resolve())
    assert result["components"]["estimator"]["sample_period_s"] == "-0x0.0p+0"
    unfixed_raw = b'{"synthetic_unfixed_fixture":true,"x":-0.0}\n'
    source["unfixed.json"] = unfixed_raw
    item["source_path"] = "unfixed.json"
    with pytest.raises(authority.AuthorityError, match="parameter_source_not_fixed"):
        authority.expected_parameters(policy, source, tmp_path.resolve())


def test_missing_or_duplicate_parameter_binding_is_not_ready(tmp_path):
    policy, source = _parameter_fixture(tmp_path)
    first = policy["parameter_bindings"].pop()
    with pytest.raises(authority.AuthorityError, match="incomplete_expected_parameters"):
        authority.expected_parameters(policy, source, tmp_path.resolve())
    policy["parameter_bindings"].extend([first, first])
    with pytest.raises(authority.AuthorityError, match="duplicate_parameter_field"):
        authority.expected_parameters(policy, source, tmp_path.resolve())


def test_wrong_parameter_shape_and_path_escape_are_refused(tmp_path):
    policy, source = _parameter_fixture(tmp_path)
    vector = next(item for item in policy["parameter_bindings"] if item["field"] == "attitude_kp")
    vector["literal"] = 1.0
    with pytest.raises(authority.AuthorityError, match="expected_parameter_shape"):
        authority.expected_parameters(policy, source, tmp_path.resolve())
    with pytest.raises(authority.AuthorityError, match="invalid_source_path"):
        authority._relative("../outside.json")


def test_external_source_fact_digest_and_blob_identity_are_both_needed(tmp_path):
    content = b"synthetic source\n"
    facts = {"schema_version": "b0-g3a-source-facts/v1", "source_commit": "1" * 40,
             "source_tree": "2" * 40,
             "files": {"file.py": hashlib.sha1(b"blob 17\0" + content).hexdigest()}}
    path = tmp_path / "source-facts.json"
    raw = _json(facts)
    path.write_bytes(raw)
    with pytest.raises(authority.AuthorityError, match="external_source_facts_digest_required"):
        authority._source_identity(tmp_path, ["file.py"], {"file.py": content}, None, path, None)
    with pytest.raises(authority.AuthorityError, match="source_facts_digest_mismatch"):
        authority._source_identity(tmp_path, ["file.py"], {"file.py": content}, None, path, "0" * 64)
    with pytest.raises(authority.AuthorityError, match="source_bytes_not_git_blob"):
        authority._source_identity(tmp_path, ["file.py"], {"file.py": content + b"changed"}, None, path, _sha(raw))


def test_role_boundary_duplicate_and_empty_coverage_refused(tmp_path):
    inside = tmp_path / "inside"
    inside.mkdir()
    path = inside / "a.bin"
    path.write_bytes(b"abc")
    record = {"role": "fixture", "path": str(path.resolve()), "bytes": 3, "sha256": _sha(b"abc")}
    section = {"required_file_roles": ["fixture"], "file_role_rules": {"fixture": {
        "allowed_roots": [str(inside.resolve())], "allowed_paths": [], "min_files": 1, "max_files": 2}}}
    observations, captured = authority._fact_files({"files": [record]}, section, {}, "environment")
    assert len(observations) == 1 and tuple(captured.values()) == (b"abc",)
    with pytest.raises(authority.AuthorityError, match="duplicate_fact_path_or_name"):
        authority._fact_files({"files": [record, record]}, section, {}, "environment")
    section["file_role_rules"]["fixture"]["allowed_roots"] = [str((tmp_path / "other").resolve())]
    with pytest.raises(authority.AuthorityError, match="fact_outside_role_boundary"):
        authority._fact_files({"files": [record]}, section, {}, "environment")
    with pytest.raises(authority.AuthorityError, match="fact_files_required"):
        authority._fact_files({"files": []}, section, {}, "environment")


def test_two_distinct_role_roots_can_have_same_basename(tmp_path):
    records = []
    roots = []
    for name in ("launcher", "binary"):
        directory = tmp_path / name
        directory.mkdir()
        path = directory / "cmake"
        path.write_bytes(name.encode("ascii"))
        roots.append(str(directory.resolve()))
        records.append({"role": "tool:cmake", "path": str(path.resolve()),
                        "bytes": len(name), "sha256": _sha(name.encode("ascii"))})
    section = {"required_file_roles": ["tool:cmake"], "file_role_rules": {"tool:cmake": {
        "allowed_roots": roots, "allowed_paths": [], "min_files": 2, "max_files": 2}}}
    observed, _ = authority._fact_files({"files": records}, section, {}, "environment")
    assert len({item["relative_name"] for item in observed}) == 2


def test_ci_pr_uses_event_head_not_synthetic_merge():
    head, merge = "1" * 40, "2" * 40
    event = _json({"repository": {"full_name": "owner/repo"}, "pull_request": {"head": {"sha": head}}})
    policy = {"ci": {"repository": "owner/repo", "allowed_events": ["pull_request", "push"]}}
    result = authority._ci_context(event, "pull_request", "owner/repo", merge, "1", "1", policy, head)
    assert result["event_head"] == head
    with pytest.raises(authority.AuthorityError, match="ci_event_head_mismatch"):
        authority._ci_context(event, "pull_request", "owner/repo", merge, "1", "1", policy, merge)


def test_catch_captured_root_must_equal_explicit_cmake_source(tmp_path):
    root = tmp_path / "catch-source"
    root.mkdir()
    source = root / "CMakeLists.txt"
    source.write_bytes(b"synthetic path-binding fixture, not Catch source")
    records = [{"role": "catch_source", "resolved_path": str(source.resolve())}]
    cache = {"Catch2_DIR": "Catch2_DIR-NOTFOUND", "Catch2_SOURCE_DIR": str(root.resolve()),
             "FETCHCONTENT_SOURCE_DIR_CATCH2": str(root.resolve())}
    result = authority._catch_source_binding(cache, records)
    assert result["source_root"] == str(root.resolve())
    cache["Catch2_DIR"] = str(root.resolve())
    with pytest.raises(authority.AuthorityError, match="installed_catch_branch_not_allowed"):
        authority._catch_source_binding(cache, records)
    cache["Catch2_DIR"] = "Catch2_DIR-NOTFOUND"
    cache["FETCHCONTENT_SOURCE_DIR_CATCH2"] = ""
    with pytest.raises(authority.AuthorityError, match="explicit_catch_source_overlay_required"):
        authority._catch_source_binding(cache, records)
    cache["FETCHCONTENT_SOURCE_DIR_CATCH2"] = str(root.resolve())
    records[0]["resolved_path"] = str((tmp_path / "outside.txt").resolve())
    with pytest.raises(authority.AuthorityError, match="catch_capture_not_consumed_source"):
        authority._catch_source_binding(cache, records)


@pytest.mark.parametrize("key", ["CMAKE_HOME_DIRECTORY", "CMAKE_COMMAND",
                                 "CMAKE_CXX_COMPILER", "CMAKE_MAKE_PROGRAM"])
@pytest.mark.parametrize("invalid_kind", ["missing", "relative", "empty"])
def test_all_four_cache_identity_paths_refuse_missing_relative_or_empty(tmp_path, monkeypatch, key, invalid_kind):
    # Reproduce the vulnerable cwd condition without a configure/build or DUT.
    monkeypatch.chdir(tmp_path)
    cache = {}
    if invalid_kind == "relative":
        cache[key] = "."
    elif invalid_kind == "empty":
        cache[key] = ""
    with pytest.raises(authority.AuthorityError, match="cache_absolute_path_required") as caught:
        authority._absolute_cache_path(cache, key)
    assert caught.value.detail == key


def test_empty_execution_plan_and_boolean_auxiliary_counts_are_refused():
    plan = {"plan_version": "b0-g3a-execution-plan/v1", "lifecycle_callsites": {}, "auxiliary_counts": {}}
    with pytest.raises(authority.AuthorityError, match="execution_plan_empty"):
        authority._execution_plan(plan)
    plan["lifecycle_callsites"] = {"fixture": {"owner": "observer", "method": "capture_snapshot", "parent_site": None}}
    plan["auxiliary_counts"] = {profile: {"fixture": 0} for profile in ("S", "L1", "L2", "O1", "O2", "E", "T1", "T2")}
    plan["auxiliary_counts"]["S"]["fixture"] = True
    with pytest.raises(authority.AuthorityError, match="auxiliary_counter_invalid"):
        authority._execution_plan(plan)


def test_collect_prebuild_needs_no_raw_and_cannot_emit_basis(tmp_path, monkeypatch):
    """Control-flow unit fixture, deliberately not actual environment evidence."""
    source_file = tmp_path / "source.txt"
    source_file.write_bytes(b"synthetic source")
    env_path = tmp_path / "environment-facts.json"
    env_path.write_bytes(b"{}")
    policy_raw = b"synthetic mocked policy"
    policy = {"source_paths": ["source.txt"], "fixed_files": {},
              "work_order": {"path": "source.txt", "sha256": _sha(b"synthetic source")},
              "config_approval_paths": [], "observer_paths": [], "evidence_files": {}}
    monkeypatch.setattr(authority, "_load_policy", lambda *args: (policy, policy_raw, "source.txt"))
    monkeypatch.setattr(authority, "_source_identity", lambda *args: ({"source_commit": "1" * 40,
                                                                     "source_tree": "2" * 40}, None))
    monkeypatch.setattr(authority, "_environment", lambda *args: ({"synthetic": True}, {}))
    monkeypatch.setattr(authority, "expected_parameters", lambda *args: {"synthetic": True})
    original_import = builtins.__import__

    def reject_dut_import(name, *args, **kwargs):
        assert name.split(".")[0] not in {"numpy", "b0_controller", "runner", "plant", "imu", "estimator"}
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", reject_dut_import)
    # Match the mocked policy byte identity check, without supplying any raw.
    source_file.write_bytes(policy_raw)
    policy["work_order"]["sha256"] = _sha(policy_raw)
    output = tmp_path / "new-prebuild"
    state = authority.collect(policy_path=source_file, expected_policy_sha256=_sha(policy_raw),
                              source_root=tmp_path, build_type="Debug", phase="prebuild",
                              environment_facts=env_path, out_dir=output)
    assert state["status"] == "PREBUILD_ONLY" and state["human_f0_accept"] is False
    assert not (output / "authority-basis.json").exists()
    assert (output / "snapshot-index.json").is_file()


def test_transport_does_not_copy_raw_identity_or_modify_basis(tmp_path):
    basis = _basis_fixture()
    basis_path = tmp_path / "basis.json"
    basis_raw = _json(basis) + b"\n"
    basis_path.write_bytes(basis_raw)
    raw_path = tmp_path / "raw.json"
    raw_bytes = b'{"identity":{"source_commit":"untrusted raw claim"}}\n'
    raw_path.write_bytes(raw_bytes)
    output = tmp_path / "consumer.json"
    result = authority.bind_transport(basis_path=basis_path, expected_basis_sha256=_sha(basis_raw),
                                      raw_path=raw_path, locator="synthetic/artifact", output=output)
    consumer = authority.load_consumer_authority(output, result["consumer_authority_sha256"])
    assert consumer["identity"] == basis["identity"]
    assert consumer["transport"]["sha256"] == _sha(raw_bytes)
    assert consumer["input_artifact_bytes"]["fixed.json"] == b'{"synthetic_fixture":true}\n'
    assert basis_path.read_bytes() == basis_raw and raw_path.read_bytes() == raw_bytes
    with pytest.raises(authority.AuthorityError, match="transport_output_not_new"):
        authority.bind_transport(basis_path=basis_path, expected_basis_sha256=_sha(basis_raw),
                                 raw_path=raw_path, locator="same", output=output)


def test_transport_rejects_corrupt_registry_even_when_outer_digest_is_supplied(tmp_path):
    basis = _basis_fixture()
    basis["input_artifact_base64"]["fixed.json"] = base64.b64encode(b"wrong bytes").decode("ascii")
    raw = _json(basis) + b"\n"
    with pytest.raises(authority.AuthorityError, match="artifact_digest_mismatch"):
        authority._admit_basis(raw, _sha(raw))
