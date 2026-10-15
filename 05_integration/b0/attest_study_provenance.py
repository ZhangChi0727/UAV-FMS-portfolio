"""Create a post-execution provenance erratum without changing sealed run bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runner import (
    ACCEPTANCE_SEED_HISTORY,
    BEHAVIOR_CLOSURE_PATHS,
    CONTROLLER_BUILD_INPUT_PATHS,
    REPO_ROOT,
)


class AttestationError(ValueError):
    """Raised when a sealed provenance chain cannot be verified."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AttestationError(f"expected JSON object: {path}")
    return value


def _git_bytes(commit: str, relative_path: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"{commit}:{relative_path}"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    ).stdout


def _git_checkout_bytes(commit: str, relative_path: str) -> bytes:
    return subprocess.run(
        [
            "git",
            "cat-file",
            "--filters",
            f"--path={relative_path}",
            f"{commit}:{relative_path}",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    ).stdout


def _canonical_lf(value: bytes) -> bytes:
    return value.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _candidate_link(candidate_directory: Path, source_commit: str) -> dict[str, Any]:
    start_path = candidate_directory / "run-start.json"
    result_path = candidate_directory / "tuning-result.json"
    final_path = candidate_directory / "run-final.json"
    start = _load(start_path)
    result = _load(result_path)
    final = _load(final_path)
    start_hash = _sha256(start_path)
    result_hash = _sha256(result_path)
    final_hash = _sha256(final_path)
    if start.get("source_commit") != source_commit:
        raise AttestationError("candidate start source commit mismatch")
    if result.get("source_commit") != source_commit:
        raise AttestationError("candidate result source commit mismatch")
    if final.get("source_commit") != source_commit:
        raise AttestationError("candidate final source commit mismatch")
    if final.get("seed_exposure_start_sha256") != start_hash:
        raise AttestationError("candidate final does not bind its start record")
    if final.get("result_sha256") != result_hash:
        raise AttestationError("candidate final does not bind its result")
    if start.get("acceptance_seed_exposed") is not False:
        raise AttestationError("legacy tuning marker changed unexpectedly")
    return {
        "candidate_id": candidate_directory.name,
        "start_sha256": start_hash,
        "result_sha256": result_hash,
        "final_sha256": final_hash,
        "legacy_acceptance_seed_exposed": False,
        "corrected_acceptance_seed_executed_this_run": False,
        "corrected_acceptance_seed_previously_exposed": True,
        "corrected_acceptance_seed_exposure_cumulative": True,
        "recorded_module_path": start["module_path"],
        "recorded_module_sha256": start["module_sha256"],
        "recorded_authority": start["authority"],
    }


def build_attestation(study_root: Path, exposure_root: Path) -> dict[str, Any]:
    """Verify sealed links and reconstruct omitted source identities after execution."""

    summary_path = study_root / "study-summary.json"
    summary = _load(summary_path)
    source_commit = str(summary["source_commit"])
    candidate_directories = sorted(path for path in study_root.iterdir() if path.is_dir())
    if len(candidate_directories) != 7:
        raise AttestationError("expected the seven predeclared candidate directories")
    candidate_links = [
        _candidate_link(path, source_commit) for path in candidate_directories
    ]
    summary_hash = _sha256(summary_path)
    for expected, actual in zip(summary["candidate_results"], candidate_links, strict=True):
        if expected["candidate_id"] != actual["candidate_id"]:
            raise AttestationError("summary candidate order does not match sealed runs")
        if expected["result_sha256"] != actual["result_sha256"]:
            raise AttestationError("summary does not bind a candidate result")

    exposure_start = exposure_root / "seed-exposure-start.json"
    exposure_result = exposure_root / "reachability-result.json"
    exposure_final = exposure_root / "seed-exposure-final.json"
    exposure_links = {
        "source_commit": ACCEPTANCE_SEED_HISTORY["exposure_source_commit"],
        "start_sha256": _sha256(exposure_start),
        "result_sha256": _sha256(exposure_result),
        "final_sha256": _sha256(exposure_final),
    }
    for key, history_key in (
        ("start_sha256", "exposure_start_sha256"),
        ("result_sha256", "exposure_result_sha256"),
        ("final_sha256", "exposure_final_sha256"),
    ):
        if exposure_links[key] != ACCEPTANCE_SEED_HISTORY[history_key]:
            raise AttestationError(f"historical acceptance exposure {key} mismatch")

    recorded_files = {
        item["path"]: item["sha256"]
        for item in candidate_links[0]["recorded_authority"]["files"]
    }
    closure = []
    for relative_path in BEHAVIOR_CLOSURE_PATHS:
        source_bytes = _git_bytes(source_commit, relative_path)
        source_checkout_bytes = _git_checkout_bytes(source_commit, relative_path)
        live_bytes = (REPO_ROOT / relative_path).read_bytes()
        source_sha256 = hashlib.sha256(source_bytes).hexdigest()
        source_checkout_sha256 = hashlib.sha256(source_checkout_bytes).hexdigest()
        source_canonical_lf_sha256 = hashlib.sha256(
            _canonical_lf(source_bytes)
        ).hexdigest()
        live_sha256 = hashlib.sha256(live_bytes).hexdigest()
        live_canonical_lf_sha256 = hashlib.sha256(
            _canonical_lf(live_bytes)
        ).hexdigest()
        recorded_sha256 = recorded_files.get(relative_path)
        source_raw_variants = {source_sha256, source_checkout_sha256}
        if recorded_sha256 is not None and recorded_sha256 not in source_raw_variants:
            raise AttestationError(
                f"execution-time hash does not match source commit: {relative_path}"
            )
        closure.append(
            {
                "path": relative_path,
                "source_commit_blob_sha256": source_sha256,
                "source_commit_checkout_sha256": source_checkout_sha256,
                "source_commit_canonical_lf_sha256": source_canonical_lf_sha256,
                "execution_time_hash_recorded": recorded_sha256 is not None,
                "execution_time_recorded_sha256": recorded_sha256,
                "attestation_live_sha256": live_sha256,
                "attestation_live_canonical_lf_sha256": live_canonical_lf_sha256,
                "attestation_live_matches_study_source": (
                    live_sha256 in source_raw_variants
                    or live_canonical_lf_sha256 == source_canonical_lf_sha256
                ),
            }
        )

    module_hashes = {item["recorded_module_sha256"] for item in candidate_links}
    module_paths = {item["recorded_module_path"] for item in candidate_links}
    if len(module_hashes) != 1 or len(module_paths) != 1:
        raise AttestationError("candidate module identity is not stable")
    module_path = Path(next(iter(module_paths)))
    if not module_path.is_file():
        raise AttestationError("recorded controller module is no longer locally available")
    recorded_module_sha256 = next(iter(module_hashes))
    live_module_sha256 = _sha256(module_path)
    if live_module_sha256 != recorded_module_sha256:
        raise AttestationError("live controller module no longer matches recorded hash")

    cache_path = REPO_ROOT / "build/b0-controller/debug/CMakeCache.txt"
    return {
        "schema_version": "b0-g3-study-provenance-erratum/v1",
        "classification": (
            "post_execution_attestation_negative_feasibility_finding_"
            "formal_evidence_incomplete"
        ),
        "captured_after_execution": True,
        "attested_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "attestation_checkout_head": _git_head(),
        "study_source_commit": source_commit,
        "study_summary_sha256": summary_hash,
        "acceptance_seed_executed_this_study": False,
        "acceptance_seed_previously_exposed": True,
        "acceptance_seed_exposure_cumulative": True,
        "historical_acceptance_seed_exposure": exposure_links,
        "legacy_field_erratum": (
            "acceptance_seed_exposed=false in the sealed tuning v1 records meant "
            "not executed in that run; it must not be interpreted as clearing the "
            "earlier seed-2026100906 exposure"
        ),
        "candidate_links": [
            {key: value for key, value in item.items() if key != "recorded_authority"}
            for item in candidate_links
        ],
        "behavior_closure": {
            "path_count": len(closure),
            "execution_time_recorded_count": sum(
                item["execution_time_hash_recorded"] for item in closure
            ),
            "post_execution_reconstructed_count": sum(
                not item["execution_time_hash_recorded"] for item in closure
            ),
            "files": closure,
        },
        "build_attestation": {
            "captured_after_execution": True,
            "recorded_module_path": str(module_path),
            "recorded_module_sha256": recorded_module_sha256,
            "attestation_live_module_sha256": live_module_sha256,
            "live_module_matches_all_sealed_candidates": True,
            "controller_build_input_paths": list(CONTROLLER_BUILD_INPUT_PATHS),
            "cmake_cache_path": str(cache_path),
            "cmake_cache_sha256": _sha256(cache_path),
            "limitation": (
                "The module hash was captured during every run, but the full build-input "
                "closure and CMake cache were reconstructed or observed after execution."
            ),
        },
        "formal_study_evidence_complete": False,
        "permitted_use": (
            "locally useful bounded negative feasibility finding; not parameter or "
            "scenario acceptance"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--study-root", required=True, type=Path)
    parser.add_argument("--exposure-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    value = build_attestation(args.study_root.resolve(), args.exposure_root.resolve())
    rendered = json.dumps(value, indent=2, sort_keys=True) + "\n"
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(rendered)
    print(f"wrote {args.output} sha256={hashlib.sha256(rendered.encode()).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
