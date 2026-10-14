from __future__ import annotations

from pathlib import Path
import re


REPO = Path(__file__).resolve().parents[3]
MATRIX = REPO / "systems_engineering/reports/b0/g2b_s0_controller_verification_matrix.md"
CPP_TESTS = REPO / "03_control/b0/tests/test_controller.cpp"
CONTROLLER_CMAKE = REPO / "03_control/b0/CMakeLists.txt"


EXPECTED_ROWS = {
    "B-ATT-01",
    "B-ATT-02",
    "B-ATT-03",
    "B-RATE-01",
    "B-RATE-02",
    "B-DERIV-01",
    "B-DERIV-02",
    "B-LIMIT-01",
    "B-LIMIT-02",
    "B-AW-01",
    "B-AW-02",
    "B-AW-03",
    "B-PAIR-01",
    "B-PAIR-02",
    "B-TIME-01",
    "B-TIME-02",
    "B-INVALID-01",
    "B-INVALID-02",
    "B-RESET-01",
    "B-RESET-02",
    "B-BIND-01",
    "B-BIND-02",
    "B-DETECT-01",
    "B-DETECT-02",
    "B-CONFIG-01",
    "B-CONFIG-02",
}


def test_s0_matrix_rows_and_cpp_nodes_resolve_to_collected_names():
    matrix = MATRIX.read_text(encoding="utf-8")
    source = CPP_TESTS.read_text(encoding="utf-8")
    row_ids = set(re.findall(r"^\| (B-[A-Z]+-[0-9]+) \|", matrix, flags=re.MULTILINE))
    assert row_ids == EXPECTED_ROWS

    declared_cpp = set(re.findall(r"`b0_controller::(?!mutation::)([a-z0-9_]+)`", matrix))
    implemented_cpp = set(re.findall(r'TEST_CASE\("([a-z0-9_]+)"', source))
    assert declared_cpp == implemented_cpp


def test_s0_matrix_mutation_nodes_resolve_to_compiled_subjects():
    matrix = MATRIX.read_text(encoding="utf-8")
    cmake = CONTROLLER_CMAKE.read_text(encoding="utf-8")
    declared = set(re.findall(r"`b0_controller::mutation::([a-z0-9_]+)`", matrix))
    implemented = set(
        re.findall(r"b0_add_subject_mutation\(\s*([a-z0-9_]+)", cmake)
    )
    assert declared == implemented
    assert len(implemented) == 4


def test_s0_matrix_python_nodes_resolve_to_real_test_functions():
    matrix = MATRIX.read_text(encoding="utf-8")
    declared = set(
        re.findall(
            r"(?:`)?python/tests/(test_[a-z0-9_]+\.py)::(test_[a-z0-9_]+)(?:`)?",
            matrix,
        )
    )
    assert declared
    implemented = set()
    for path in (REPO / "03_control/b0/python/tests").glob("test_*.py"):
        source = path.read_text(encoding="utf-8")
        implemented.update(
            (path.name, function)
            for function in re.findall(r"^def (test_[a-z0-9_]+)\(", source, re.MULTILINE)
        )
    assert declared == implemented
    for relative, function in declared:
        path = REPO / "03_control/b0/python/tests" / relative
        assert path.is_file(), f"missing matrix test file: {relative}"
        source = path.read_text(encoding="utf-8")
        assert re.search(rf"^def {re.escape(function)}\(", source, flags=re.MULTILINE), (
            f"missing matrix test function: {relative}::{function}"
        )
