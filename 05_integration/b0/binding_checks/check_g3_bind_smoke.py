"""Offline pytest admission of one sealed G3-A real-component record.

The real component batch is executed once by ``g3a_evidence_driver.py``. This
node consumes the retained bytes and consumer authority; it never imports the
DUT, constructs a component, samples randomness, or reruns the driver.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any


BINDING_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(BINDING_ROOT))

from check_g3a_runtime import check_runtime_record_bytes  # noqa: E402
from g3a_authority import load_consumer_authority  # noqa: E402
from g3a_independent_checks import (  # noqa: E402
    check_record_set,
    make_data_diagnostics,
)


def _required_path(name: str) -> Path:
    value = os.environ.get(name)
    if not value:
        raise AssertionError(f"missing required environment variable: {name}")
    path = Path(value)
    if not path.is_absolute():
        raise AssertionError(f"{name} must be an absolute path")
    return path


def _write_report(path: Path, value: dict[str, Any]) -> None:
    payload = json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8") + b"\n"
    with path.open("xb") as stream:
        stream.write(payload)


def _write_bytes(path: Path, value: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(value)


def test_sealed_g3a_record_passes_author_and_independent_checks() -> None:
    raw_path = _required_path("B0_G3A_RAW")
    authority_path = _required_path("B0_G3A_CONSUMER_AUTHORITY")
    authority_sha256 = os.environ.get("B0_G3A_CONSUMER_AUTHORITY_SHA256")
    if not authority_sha256:
        raise AssertionError("missing B0_G3A_CONSUMER_AUTHORITY_SHA256")

    raw_bytes = raw_path.read_bytes()
    author_report = check_runtime_record_bytes(
        raw_bytes,
        source=str(raw_path.resolve()),
        transport_path=authority_path,
    )
    _write_report(_required_path("B0_G3A_AUTHOR_REPORT"), author_report)
    assert author_report["consumer_authority_sha256"] == authority_sha256.lower(), {
        "reason": "consumer_authority_digest_mismatch",
        "expected": authority_sha256.lower(),
        "actual": author_report["consumer_authority_sha256"],
    }
    assert author_report["status"] == "pass", author_report

    assert hashlib.sha256(raw_bytes).hexdigest() == author_report["raw_sha256"]
    authority = load_consumer_authority(authority_path, authority_sha256)
    independent_report = check_record_set(raw_bytes, authority)
    _write_report(
        _required_path("B0_G3A_INDEPENDENT_REPORT"), independent_report
    )
    assert independent_report["status"] == "pass", independent_report

    diagnostics_root = _required_path("B0_G3A_DIAGNOSTICS_ROOT")
    diagnostics_root.mkdir(exist_ok=False)
    diagnostics = make_data_diagnostics(raw_bytes, authority)
    assert len(diagnostics) == 13
    summary: list[dict[str, Any]] = []
    for item in diagnostics:
        diagnostic_id = item["diagnostic_id"]
        diagnostic_dir = diagnostics_root / diagnostic_id
        diagnostic_dir.mkdir(exist_ok=False)
        diagnostic_raw = item["raw_bytes"]
        _write_bytes(diagnostic_dir / "raw.json", diagnostic_raw)
        metadata = {key: value for key, value in item.items() if key != "raw_bytes"}
        _write_report(diagnostic_dir / "metadata.json", metadata)
        diagnostic_authority = dict(authority)
        diagnostic_authority["transport"] = item["transport"]
        report = check_record_set(diagnostic_raw, diagnostic_authority)
        _write_report(diagnostic_dir / "report.json", report)
        expected_reason = item["expected_reason"]
        expected_status = "pass" if diagnostic_id == "legal_control" else "reject"
        assert report["status"] == expected_status, report
        assert report["reason"] == expected_reason, report
        summary.append(
            {
                "diagnostic_id": diagnostic_id,
                "raw_sha256": item["raw_sha256"],
                "expected_reason": expected_reason,
                "actual_status": report["status"],
                "actual_reason": report["reason"],
            }
        )
    _write_report(
        diagnostics_root / "summary.json",
        {"status": "pass", "diagnostics": summary},
    )
