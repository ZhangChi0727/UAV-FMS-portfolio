"""Synthetic-only mechanical candidate tests; no dataset access."""
import hashlib
import json
from pathlib import Path
import sys

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dedup  # noqa: E402


def declaration(path, **overrides):
    value = {"algorithm": "dhash64", "hamming_threshold": 0,
             "source_split": "development", "frozen_before_target_scan": True,
             "development_evidence": "synthetic unit-test declaration only"}
    value.update(overrides)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_private_build_root_for_normal_and_nested_worktrees(tmp_path):
    normal = tmp_path / "repo" / "edge_inference" / "m2" / "dedup.py"
    nested = tmp_path / "repo" / "build" / "other-worktree" / "edge_inference" / "m2" / "dedup.py"
    assert dedup.private_build_root(normal) == tmp_path / "repo" / "build"
    assert dedup.private_build_root(nested) == tmp_path / "repo" / "build" / "other-worktree" / "build"


def test_declaration_is_required_frozen_and_development_derived(tmp_path):
    with pytest.raises(FileNotFoundError):
        dedup.load_threshold_declaration(tmp_path / "missing.json")
    for changes in ({"frozen_before_target_scan": False}, {"source_split": "test"},
                    {"hamming_threshold": True}, {"hamming_threshold": 65},
                    {"development_evidence": ""}, {"algorithm": "other"}):
        with pytest.raises(ValueError):
            dedup.load_threshold_declaration(declaration(tmp_path / "threshold.json", **changes))
    path = declaration(tmp_path / "threshold.json")
    _, actual = dedup.load_threshold_declaration(path)
    assert actual == hashlib.sha256(path.read_bytes()).hexdigest()


def test_synthetic_byte_identical_and_phash_candidates_are_not_verdicts(tmp_path):
    a = tmp_path / "a.png"
    Image.new("RGB", (9, 8), "red").save(a)
    (tmp_path / "same.png").write_bytes(a.read_bytes())
    Image.new("RGB", (9, 8), "blue").save(tmp_path / "other.png")
    records = [dedup.fingerprint(path, tmp_path) for path in dedup.image_paths(tmp_path)]
    pairs = list(dedup.candidate_pairs(records, 0))
    assert len(pairs) == 3  # Uniform different-colour images collide under grayscale dHash.
    exact = next(p for p in pairs if {p["left"], p["right"]} == {"a.png", "same.png"})
    assert exact["candidate_reasons"] == ["exact_sha256", "dhash64"]
    assert all(p["status"] == "candidate_unconfirmed" for p in pairs)
    assert any(p["candidate_reasons"] == ["dhash64"] for p in pairs)


def test_undecodable_files_still_report_exact_candidates(tmp_path):
    (tmp_path / "bad1.png").write_bytes(b"not-an-image")
    (tmp_path / "bad2.png").write_bytes(b"not-an-image")
    records = [dedup.fingerprint(path, tmp_path) for path in dedup.image_paths(tmp_path)]
    assert all(record["dhash64"] is None and record["dhash_error"] for record in records)
    result = list(dedup.candidate_pairs(records, 0))
    assert result[0]["candidate_reasons"] == ["exact_sha256"]
    assert result[0]["hamming_distance"] is None


def test_output_must_be_private_and_outside_input_tree(tmp_path, monkeypatch):
    source = tmp_path / "input"
    source.mkdir()
    Image.new("RGB", (9, 8), "red").save(source / "a.png")
    spec = declaration(tmp_path / "threshold.json")
    private = tmp_path / "build"
    private.mkdir()
    monkeypatch.setattr(dedup, "PRIVATE_BUILD", private)
    with pytest.raises(ValueError):
        dedup.run(source, spec, tmp_path / "outside.jsonl")
    # A source under private build still cannot be used as its own output dir.
    monkeypatch.setattr(dedup, "PRIVATE_BUILD", tmp_path)
    with pytest.raises(ValueError):
        dedup.run(source, spec, source / "output.jsonl")
    output = private / "result.jsonl"
    counts = dedup.run(source, spec, output)
    assert counts == {"images": 1, "decode_failures": 0, "candidate_pairs": 0, "candidate_groups": 0}
    original = output.read_bytes()
    with pytest.raises(FileExistsError):
        dedup.run(source, spec, output)
    assert output.read_bytes() == original


def test_hamming_radius_and_decode_unknown():
    records = [{"path": "a", "sha256": "1", "dhash64": "0000000000000000"},
               {"path": "b", "sha256": "2", "dhash64": "0000000000000001"},
               {"path": "c", "sha256": "3", "dhash64": None}]
    assert list(dedup.candidate_pairs(records, 0)) == []
    result = list(dedup.candidate_pairs(records, 1))
    assert len(result) == 1 and result[0]["hamming_distance"] == 1


def test_candidate_group_is_explicitly_unconfirmed(tmp_path, monkeypatch):
    source = tmp_path / "input"
    source.mkdir()
    Image.new("RGB", (9, 8), "red").save(source / "a.png")
    (source / "b.png").write_bytes((source / "a.png").read_bytes())
    private = tmp_path / "build"
    private.mkdir()
    monkeypatch.setattr(dedup, "PRIVATE_BUILD", private)
    output = private / "result.jsonl"
    counts = dedup.run(source, declaration(tmp_path / "threshold.json"), output)
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    group = next(row for row in rows if row["type"] == "candidate_group")
    assert counts["candidate_groups"] == 1
    assert group["members"] == ["a.png", "b.png"]
    assert group["status"] == "candidate_unconfirmed"
