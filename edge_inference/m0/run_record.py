"""M0: run records, canonical hashing and event-log normalisation.

Requirements covered:
- EDG-REQ-0003: model identifier, precision, library versions and device identifier per run.
- EDG-REQ-0007: normalised event-log comparison; wall-clock time and run identifiers are
  removed before hashing and stored separately as run metadata.
- EDG-REQ-0008: code revision, configuration, seed, host identifier, raw artifact location
  and analysis command per result record.
- EDG-REQ-0009: only development-host measurements are accepted, because no edge hardware
  record exists in this project.

Interface (all pure functions, no I/O except write_run_record):
    canonical_json(obj) -> bytes
    sha256_hex(data) -> str
    config_hash(config) -> str
    validate_run_record(record) -> None          # raises RunRecordError
    build_run_record(**fields) -> dict           # validated record
    normalise_event_log(events) -> list[dict]
    event_log_hash(events) -> str
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Mapping

HOST_TYPE_DEVELOPMENT = "development-host"
ALLOWED_HOST_TYPES = frozenset({HOST_TYPE_DEVELOPMENT})

# Fields that identify a run or record time, not its content (EDG-REQ-0007).
NORMALISED_DROP_KEYS = frozenset({"wall_clock_s", "run_id"})

REQUIRED_FIELDS = (
    # EDG-REQ-0003
    "model_id",
    "precision",
    "library_versions",
    "device_id",
    # EDG-REQ-0008
    "code_revision",
    "config_hash",
    "seed",
    "host_id",
    "host_type",
    "raw_artifact_location",
    "analysis_command",
)


class RunRecordError(ValueError):
    """Raised when a run record is incomplete or violates a stated rule."""


def canonical_json(obj: Any) -> bytes:
    """Serialise to a canonical byte form: sorted keys, no extra whitespace, no NaN."""
    text = json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return text.encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def config_hash(config: Mapping[str, Any]) -> str:
    """Hash of a configuration. Equal content gives equal hash regardless of key order."""
    return sha256_hex(canonical_json(dict(config)))


def validate_run_record(record: Mapping[str, Any]) -> None:
    """Check that every required field is present, non-empty and consistent."""
    missing = [name for name in REQUIRED_FIELDS if name not in record]
    if missing:
        raise RunRecordError(f"missing required fields: {', '.join(missing)}")

    empty = [name for name in REQUIRED_FIELDS if record[name] in (None, "", {}, [])]
    if empty:
        raise RunRecordError(f"empty required fields: {', '.join(empty)}")

    if record["host_type"] not in ALLOWED_HOST_TYPES:
        raise RunRecordError(
            f"host_type {record['host_type']!r} is not allowed without a hardware record"
        )

    if not isinstance(record["seed"], int) or isinstance(record["seed"], bool):
        raise RunRecordError("seed must be an integer")


def build_run_record(**fields: Any) -> dict[str, Any]:
    """Create a validated run record from keyword fields."""
    record = dict(fields)
    validate_run_record(record)
    return record


def normalise_event_log(events: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Remove wall-clock and run-identifier keys from each event (EDG-REQ-0007).

    Only the named keys are removed. Any other difference, including a changed order of
    events, changes the normalised log and its hash.
    """
    return [
        {key: value for key, value in event.items() if key not in NORMALISED_DROP_KEYS}
        for event in events
    ]


def event_log_hash(events: Iterable[Mapping[str, Any]]) -> str:
    return sha256_hex(canonical_json(normalise_event_log(events)))
