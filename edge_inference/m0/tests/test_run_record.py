"""Tests for M0 run records, hashing and event-log normalisation."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from run_record import (  # noqa: E402
    ALLOWED_HOST_TYPES,
    REQUIRED_FIELDS,
    RunRecordError,
    build_run_record,
    canonical_json,
    config_hash,
    event_log_hash,
    normalise_event_log,
    sha256_hex,
    validate_run_record,
)


def _complete_fields(**overrides):
    fields = {
        "model_id": "example/model-small",
        "precision": "fp16",
        "library_versions": {"torch": "2.5.1", "python": "3.11.5"},
        "device_id": "NVIDIA GeForce RTX 4060 Laptop GPU",
        "code_revision": "8115043",
        "config_hash": config_hash({"batch": 1, "max_new_tokens": 64}),
        "seed": 2026,
        "host_id": "dev-pc-01",
        "host_type": "development-host",
        "raw_artifact_location": "results/raw/run_0001.jsonl",
        "analysis_command": "python analyse.py results/raw/run_0001.jsonl",
    }
    fields.update(overrides)
    return fields


# --- EDG-REQ-0003 / 0008: required fields -------------------------------------------

def test_complete_record_is_accepted():
    record = build_run_record(**_complete_fields())
    assert record["seed"] == 2026


@pytest.mark.parametrize("name", REQUIRED_FIELDS)
def test_each_required_field_is_enforced(name):
    fields = _complete_fields()
    del fields[name]
    with pytest.raises(RunRecordError, match=name):
        build_run_record(**fields)


@pytest.mark.parametrize("name", REQUIRED_FIELDS)
def test_empty_required_field_is_rejected(name):
    fields = _complete_fields(**{name: ""})
    with pytest.raises(RunRecordError, match="empty"):
        build_run_record(**fields)


def test_empty_library_versions_mapping_is_rejected():
    with pytest.raises(RunRecordError, match="library_versions"):
        build_run_record(**_complete_fields(library_versions={}))


# --- EDG-REQ-0009: host labelling ----------------------------------------------------

def test_only_development_host_is_allowed():
    assert ALLOWED_HOST_TYPES == frozenset({"development-host"})


@pytest.mark.parametrize("host_type", ["edge-device", "onboard", "flight"])
def test_non_development_host_is_rejected(host_type):
    with pytest.raises(RunRecordError, match="host_type"):
        build_run_record(**_complete_fields(host_type=host_type))


def test_seed_must_be_integer():
    with pytest.raises(RunRecordError, match="seed"):
        build_run_record(**_complete_fields(seed="2026"))


def test_bool_is_not_accepted_as_seed():
    with pytest.raises(RunRecordError, match="seed"):
        build_run_record(**_complete_fields(seed=True))


# --- Canonical hashing ----------------------------------------------------------------

def test_config_hash_ignores_key_order():
    a = {"batch": 1, "max_new_tokens": 64, "precision": "fp16"}
    b = {"precision": "fp16", "max_new_tokens": 64, "batch": 1}
    assert config_hash(a) == config_hash(b)


def test_config_hash_changes_with_value():
    assert config_hash({"batch": 1}) != config_hash({"batch": 2})


def test_canonical_json_rejects_nan():
    with pytest.raises(ValueError):
        canonical_json({"x": math.nan})


def test_sha256_matches_known_vector():
    assert sha256_hex(b"abc") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


# --- EDG-REQ-0007: normalisation ------------------------------------------------------

def _events():
    return [
        {"run_id": "r1", "wall_clock_s": 10.001, "event": "submit", "request": 1},
        {"run_id": "r1", "wall_clock_s": 10.250, "event": "complete", "request": 1},
    ]


def test_wall_clock_and_run_id_do_not_change_hash():
    original = _events()
    rerun = [
        {"run_id": "r2", "wall_clock_s": 99.5, "event": "submit", "request": 1},
        {"run_id": "r2", "wall_clock_s": 99.9, "event": "complete", "request": 1},
    ]
    assert event_log_hash(original) == event_log_hash(rerun)


def test_content_change_changes_hash():
    original = _events()
    changed = _events()
    changed[1]["event"] = "discard"
    assert event_log_hash(original) != event_log_hash(changed)


def test_reordered_events_change_hash():
    original = _events()
    assert event_log_hash(original) != event_log_hash(list(reversed(original)))


def test_normalise_keeps_content_keys_only():
    normalised = normalise_event_log(_events())
    assert normalised == [
        {"event": "submit", "request": 1},
        {"event": "complete", "request": 1},
    ]


def test_normalise_does_not_mutate_input():
    events = _events()
    normalise_event_log(events)
    assert "run_id" in events[0]


# --- validate_run_record directly ------------------------------------------------------

def test_validate_accepts_a_built_record():
    validate_run_record(build_run_record(**_complete_fields()))
