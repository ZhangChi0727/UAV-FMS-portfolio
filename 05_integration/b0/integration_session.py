"""Epoch-owning session boundary for the approved B0 G3-A evidence run.

The session is deliberately thin.  It orders the already accepted G1/G2
components, owns runner-side envelopes and lifecycle state, and exposes the
rejection points needed by the G3-A evidence contract.  It does not duplicate
any plant, sensor, estimator, or controller algorithm.

This module has no import-time construction or execution.  Runtime modules and
message factories are injected by the caller so the existing track-specific
loaders remain the only authority for their concrete types.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
import hashlib
import json
import math
import numbers
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence

import numpy as np


class SessionContractError(RuntimeError):
    """Fail-closed session error with a stable evidence reason."""

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        self._failure_frontier: Mapping[str, Any] | None = None
        message = reason if not detail else f"{reason}: {detail}"
        super().__init__(message)

    @property
    def failure_frontier(self) -> Mapping[str, Any] | None:
        """Read-only facts retained at the first interrupted transaction."""

        return self._failure_frontier

    def _bind_failure_frontier(self, value: Mapping[str, Any]) -> None:
        if self._failure_frontier is None:
            self._failure_frontier = value


class SessionLifecycle(str, Enum):
    NEW = "new"
    ACTIVE = "active"
    NEEDS_RESET = "needs_reset"
    TERMINAL_INCONCLUSIVE = "terminal_inconclusive"


FAULT_CONTROLLER_NEGATIVE_DT = "controller_negative_dt"
FAULT_ESTIMATOR_STALE_TIMESTAMP = "estimator_stale_timestamp"
FAULT_CONTROLLER_UNEXPECTED_TICK = "controller_unexpected_tick"
_FAULTS = {
    FAULT_CONTROLLER_NEGATIVE_DT,
    FAULT_ESTIMATOR_STALE_TIMESTAMP,
    FAULT_CONTROLLER_UNEXPECTED_TICK,
}


def _nonnegative_integer(value: Any, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Integral):
        raise SessionContractError(
            "invalid_session_argument", f"{name} must be an integer"
        )
    result = int(value)
    if result < 0:
        raise SessionContractError(
            "invalid_session_argument", f"{name} must be non-negative"
        )
    return result


def _finite_float(value: Any, name: str) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Real):
        raise SessionContractError(
            "invalid_session_argument", f"{name} must be a finite scalar"
        )
    result = float(value)
    if not math.isfinite(result):
        raise SessionContractError(
            "invalid_session_argument", f"{name} must be a finite scalar"
        )
    return result


def _sha256(value: Any, name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdefABCDEF" for character in value)
    ):
        raise SessionContractError(
            "invalid_session_argument", f"{name} must be a SHA-256 hex digest"
        )
    return value.lower()


def _plain_event_value(value: Any, name: str) -> Any:
    """Detach an event table into the driver's finite JSON value domain."""

    if value is None or isinstance(value, str):
        return value
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (numbers.Integral, np.integer)):
        return int(value)
    if isinstance(value, (numbers.Real, np.floating)):
        converted = float(value)
        if not math.isfinite(converted):
            raise SessionContractError(
                "event_definition_invalid", f"{name} contains a non-finite float"
            )
        return converted
    if isinstance(value, np.ndarray):
        return _plain_event_value(value.tolist(), name)
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise SessionContractError(
                "event_definition_invalid", f"{name} keys must be strings"
            )
        return {
            key: _plain_event_value(value[key], f"{name}.{key}")
            for key in sorted(value)
        }
    if isinstance(value, (tuple, list)):
        return [
            _plain_event_value(item, f"{name}[{index}]")
            for index, item in enumerate(value)
        ]
    raise SessionContractError(
        "event_definition_invalid",
        f"{name} contains unsupported {type(value).__name__}",
    )


def _event_definition_sha256(value: Any) -> str:
    plain = _plain_event_value(value, "event_schedule._events")
    payload = json.dumps(
        plain,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _deep_freeze_event_value(value: Any) -> Any:
    """Turn a detached JSON event value into a transitively immutable value."""

    if isinstance(value, dict):
        return MappingProxyType(
            {key: _deep_freeze_event_value(item) for key, item in value.items()}
        )
    if isinstance(value, list):
        return tuple(_deep_freeze_event_value(item) for item in value)
    return value


class _FrozenAttributeView:
    """Immutable attribute facade used only by retained failure-frontier wires."""

    __slots__ = ("_values",)

    def __init__(self, values: Mapping[str, Any]) -> None:
        object.__setattr__(self, "_values", MappingProxyType(dict(values)))

    def __getattr__(self, name: str) -> Any:
        try:
            return self._values[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value: Any) -> None:
        del name, value
        raise TypeError("failure-frontier payloads are immutable")


def _freeze_frontier_value(value: Any) -> Any:
    """Detach aliases and recursively freeze the retained failure journal."""

    if value is None or isinstance(value, (str, bool, int, float, Enum)):
        return value
    if isinstance(value, (np.bool_, np.integer, np.floating)):
        return value.item()
    if isinstance(value, np.ndarray):
        return _freeze_frontier_value(value.tolist())
    if isinstance(value, Mapping):
        return MappingProxyType(
            {
                key: _freeze_frontier_value(item)
                for key, item in value.items()
            }
        )
    if isinstance(value, (tuple, list)):
        return tuple(_freeze_frontier_value(item) for item in value)
    if is_dataclass(value):
        return _FrozenAttributeView(
            {
                field.name: _freeze_frontier_value(
                    getattr(value, field.name)
                )
                for field in fields(value)
            }
        )
    namespace = getattr(value, "__dict__", None)
    if isinstance(namespace, dict):
        return _FrozenAttributeView(
            {
                str(name): _freeze_frontier_value(item)
                for name, item in namespace.items()
            }
        )
    try:
        rendered = repr(value)
    except Exception:
        rendered = f"<{type(value).__name__}>"
    return _FrozenAttributeView(
        {"type": type(value).__name__, "representation": rendered}
    )


def _lifecycle_result(
    *,
    actor_id: str | None = None,
    parameter_object_ref: str | None = None,
    snapshot_ref: str | None = None,
    capture_id: str | None = None,
    resolved_config_path: str | None = None,
    source_bytes_sha256: str | None = None,
    document_sha256: str | None = None,
) -> Mapping[str, Any]:
    """Build the fixed lifecycle-return binding required by the evidence spec."""

    return {
        "actor_id": actor_id,
        "parameter_object_ref": parameter_object_ref,
        "snapshot_ref": snapshot_ref,
        "capture_id": capture_id,
        "resolved_config_path": resolved_config_path,
        "source_bytes_sha256": source_bytes_sha256,
        "document_sha256": document_sha256,
    }


def _vector(value: Any, length: int, name: str) -> np.ndarray:
    try:
        result = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise SessionContractError(
            "invalid_session_argument",
            f"{name} must be a finite length-{length} vector",
        ) from exc
    if result.shape != (length,) or not np.all(np.isfinite(result)):
        raise SessionContractError(
            "invalid_session_argument",
            f"{name} must be a finite length-{length} vector",
        )
    return result.copy()


def float64_hex(value: Any) -> str:
    """Return Python's canonical finite binary64 spelling.

    In particular, zero is ``0x0.0p+0`` (or its signed form).  Padding zero to
    thirteen fractional digits would produce a parseable but non-canonical
    spelling and would undermine the independent raw-data checks.
    """

    converted = _finite_float(value, "float64")
    return converted.hex()


def canonical_snapshot_value(value: Any) -> Any:
    """Return a detached, deterministic JSON value for functional snapshots.

    Every floating-point value uses canonical ``float.hex()`` spelling.  Object
    representations, addresses, NaN and infinity are rejected rather than
    becoming evidence.  This conversion is also used before atomicity equality.
    """

    if value is None or isinstance(value, str):
        return value
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (numbers.Integral, np.integer)):
        return int(value)
    if isinstance(value, (numbers.Real, np.floating)):
        converted = float(value)
        if not math.isfinite(converted):
            raise SessionContractError(
                "snapshot_not_canonical", "snapshot contains a non-finite float"
            )
        return float64_hex(converted)
    if isinstance(value, np.ndarray):
        return canonical_snapshot_value(value.tolist())
    if isinstance(value, Mapping):
        converted: dict[str, Any] = {}
        keys = tuple(value.keys())
        if any(not isinstance(key, str) for key in keys):
            raise SessionContractError(
                "snapshot_not_canonical", "snapshot mapping keys must be strings"
            )
        for key in sorted(keys):
            converted[key] = canonical_snapshot_value(value[key])
        return converted
    if isinstance(value, (tuple, list)):
        return [canonical_snapshot_value(item) for item in value]
    if isinstance(value, Enum):
        return canonical_snapshot_value(value.value)
    if is_dataclass(value):
        return canonical_snapshot_value(
            {field.name: getattr(value, field.name) for field in fields(value)}
        )
    raise SessionContractError(
        "snapshot_not_canonical",
        f"unsupported snapshot value type {type(value).__name__}",
    )


def canonical_snapshot_bytes(value: Any) -> bytes:
    """Encode a canonical functional snapshot without aliases or repr output."""

    return json.dumps(
        canonical_snapshot_value(value),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


@dataclass(frozen=True)
class ResetEpochView:
    """Minimal reset object accepted by the existing ControllerAdapter."""

    id: int
    timestamp_s: float


@dataclass(frozen=True)
class EpochEnvelope:
    """Immutable runner ownership metadata around an existing public message."""

    envelope_id: str
    role: str
    epoch_id: int
    global_tick: int
    local_tick: int
    phase: int
    producer: str
    producer_operation_id: str | None
    parent_ids: tuple[str, ...]
    payload: Any

    def __post_init__(self) -> None:
        if not isinstance(self.envelope_id, str) or not self.envelope_id:
            raise SessionContractError(
                "invalid_envelope", "envelope_id must be a non-empty string"
            )
        if not isinstance(self.role, str) or not self.role:
            raise SessionContractError("invalid_envelope", "role must be non-empty")
        _nonnegative_integer(self.epoch_id, "epoch_id")
        _nonnegative_integer(self.global_tick, "global_tick")
        _nonnegative_integer(self.local_tick, "local_tick")
        phase = _nonnegative_integer(self.phase, "phase")
        if phase > 6:
            raise SessionContractError("invalid_envelope", "phase must be in [0, 6]")
        if not isinstance(self.producer, str) or not self.producer:
            raise SessionContractError("invalid_envelope", "producer must be non-empty")
        if self.producer_operation_id is not None and (
            not isinstance(self.producer_operation_id, str)
            or not self.producer_operation_id
        ):
            raise SessionContractError(
                "invalid_envelope", "producer_operation_id must be null or non-empty"
            )
        if not isinstance(self.parent_ids, tuple) or any(
            not isinstance(item, str) or not item for item in self.parent_ids
        ):
            raise SessionContractError(
                "invalid_envelope", "parent_ids must be a tuple of non-empty IDs"
            )


@dataclass(frozen=True)
class LifecycleCallToken:
    """Opaque token for one actual delegated lifecycle call.

    Tokens and the recorder's stack are audit-only.  Neither is consulted by
    the scheduler, provenance guard, or any component algorithm.
    """

    call_id: str
    parent_call_id: str | None
    profile_id: str | None
    operation_id: str | None
    owner: str
    method: str
    callsite: str
    actor_id: str | None
    core_use: str | None


class LifecycleRecorder:
    """Append-only enter/return/exception observations for real lifecycle calls.

    The same recorder can be shared by the batch driver, transparent loader /
    constructor wrappers, and an :class:`IntegrationSession`.  This permits
    constructor and nested controller-core calls to retain their real parent
    call without deriving a count from the number of profiles later.
    """

    def __init__(self, *, id_prefix: str = "g3a") -> None:
        if not isinstance(id_prefix, str) or not id_prefix:
            raise SessionContractError(
                "invalid_lifecycle_argument", "id_prefix must be non-empty"
            )
        self._id_prefix = id_prefix
        self._call_sequence = 0
        self._observation_sequence = 0
        self._stack: list[LifecycleCallToken] = []
        self._observations: list[Mapping[str, Any]] = []

    @staticmethod
    def _optional_id(value: Any, name: str) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str) or not value:
            raise SessionContractError(
                "invalid_lifecycle_argument", f"{name} must be null or non-empty"
            )
        return value

    @staticmethod
    def _required_id(value: Any, name: str) -> str:
        if not isinstance(value, str) or not value:
            raise SessionContractError(
                "invalid_lifecycle_argument", f"{name} must be non-empty"
            )
        return value

    @staticmethod
    def _detached(value: Any) -> Any:
        return json.loads(canonical_snapshot_bytes(value))

    def _append(
        self,
        token: LifecycleCallToken,
        *,
        event: str,
        arguments: Mapping[str, Any] | None,
        result: Mapping[str, Any] | None,
        exception: Mapping[str, Any] | None,
    ) -> None:
        self._observations.append(
            {
                "observation_index": self._observation_sequence,
                "call_id": token.call_id,
                "parent_call_id": token.parent_call_id,
                "profile_id": token.profile_id,
                "operation_id": token.operation_id,
                "owner": token.owner,
                "method": token.method,
                "event": event,
                "callsite": token.callsite,
                "actor_id": token.actor_id,
                "core_use": token.core_use,
                "arguments": (
                    None if arguments is None else self._detached(arguments)
                ),
                "result": None if result is None else self._detached(result),
                "exception": (
                    None if exception is None else self._detached(exception)
                ),
            }
        )
        self._observation_sequence += 1

    def _require_active(self, token: LifecycleCallToken) -> None:
        if not self._stack or self._stack[-1] != token:
            raise SessionContractError(
                "lifecycle_nesting_mismatch", token.call_id
            )

    def begin(
        self,
        *,
        profile_id: str | None,
        operation_id: str | None,
        owner: str,
        method: str,
        callsite: str,
        actor_id: str | None,
        core_use: str | None,
        arguments: Mapping[str, Any],
    ) -> LifecycleCallToken:
        """Record entry immediately before the actual delegated call."""

        profile = self._optional_id(profile_id, "profile_id")
        operation = self._optional_id(operation_id, "operation_id")
        owner_id = self._required_id(owner, "owner")
        method_id = self._required_id(method, "method")
        site = self._required_id(callsite, "callsite")
        actor = self._optional_id(actor_id, "actor_id")
        use = self._optional_id(core_use, "core_use")
        if not isinstance(arguments, Mapping):
            raise SessionContractError(
                "invalid_lifecycle_argument", "arguments must be a mapping"
            )
        detached_arguments = self._detached(arguments)
        self._call_sequence += 1
        parent_token = self._stack[-1] if self._stack else None
        if parent_token is not None:
            if profile is None:
                profile = parent_token.profile_id
            if operation is None:
                operation = parent_token.operation_id
        parent = None if parent_token is None else parent_token.call_id
        token = LifecycleCallToken(
            call_id=f"{self._id_prefix}/call/{self._call_sequence}",
            parent_call_id=parent,
            profile_id=profile,
            operation_id=operation,
            owner=owner_id,
            method=method_id,
            callsite=site,
            actor_id=actor,
            core_use=use,
        )
        self._stack.append(token)
        self._append(
            token,
            event="enter",
            arguments=detached_arguments,
            result=None,
            exception=None,
        )
        return token

    def _close(self, token: LifecycleCallToken) -> None:
        self._require_active(token)
        self._stack.pop()

    def returned(
        self, token: LifecycleCallToken, *, result: Mapping[str, Any]
    ) -> None:
        """Record the return immediately after the actual delegate returns."""

        if not isinstance(result, Mapping):
            raise SessionContractError(
                "invalid_lifecycle_argument", "result must be a mapping"
            )
        detached_result = self._detached(result)
        self._require_active(token)
        self._append(
            token,
            event="return",
            arguments=None,
            result=detached_result,
            exception=None,
        )
        self._close(token)

    def raised(self, token: LifecycleCallToken, exc: BaseException) -> None:
        """Record an actual delegated exception without changing its type."""

        reason = getattr(exc, "reason", None)
        self._require_active(token)
        self._append(
            token,
            event="exception",
            arguments=None,
            result=None,
            exception={
                "type": type(exc).__name__,
                "reason": reason if isinstance(reason, str) and reason else None,
                "message": str(exc),
            },
        )
        self._close(token)

    @property
    def observations(self) -> tuple[Mapping[str, Any], ...]:
        """Return detached observations; callers cannot mutate recorder state."""

        return tuple(self._detached(item) for item in self._observations)

    @property
    def active_call_id(self) -> str | None:
        return None if not self._stack else self._stack[-1].call_id

    @property
    def current_context(self) -> Mapping[str, Any] | None:
        """Return the active audit context without exposing the mutable stack."""

        if not self._stack:
            return None
        token = self._stack[-1]
        return MappingProxyType(
            {
                "call_id": token.call_id,
                "profile_id": token.profile_id,
                "operation_id": token.operation_id,
            }
        )


@dataclass(frozen=True)
class GuardProbe:
    """One expected runner-guard rejection at a real consumption site."""

    probe_id: str
    kind: str
    envelope: EpochEnvelope
    expected_role: str
    consumer: str
    expected_reason: str
    original_legal_id: str | None = None
    source_truth_id: str | None = None
    source_field: str | None = None
    target_field: str | None = None
    derivation_site: str | None = None


@dataclass(frozen=True)
class TickDirective:
    """Predeclared probes, capture, and at most one invalid component call."""

    fault: str | None = None
    preflight_probes: tuple[GuardProbe, ...] = ()
    pre_estimator_probes: tuple[GuardProbe, ...] = ()
    pre_controller_probes: tuple[GuardProbe, ...] = ()
    truth_estimator_probe_id: str | None = None
    truth_controller_probe_id: str | None = None
    required_after_imu_snapshot_id: str | None = None

    def __post_init__(self) -> None:
        if self.fault is not None and self.fault not in _FAULTS:
            raise SessionContractError("unknown_fault", str(self.fault))
        for value in (
            self.preflight_probes,
            self.pre_estimator_probes,
            self.pre_controller_probes,
        ):
            if not isinstance(value, tuple) or any(
                not isinstance(item, GuardProbe) for item in value
            ):
                raise SessionContractError(
                    "invalid_session_argument", "probe collections must be tuples"
                )
        for name, value in (
            ("truth_estimator_probe_id", self.truth_estimator_probe_id),
            ("truth_controller_probe_id", self.truth_controller_probe_id),
            (
                "required_after_imu_snapshot_id",
                self.required_after_imu_snapshot_id,
            ),
        ):
            if value is not None and (not isinstance(value, str) or not value):
                raise SessionContractError(
                    "invalid_session_argument", f"{name} must be null or non-empty"
                )


@dataclass(frozen=True)
class ObserverCapture:
    """One observer result captured at its actual transaction frontier."""

    snapshot_id: str
    capture_id: str
    phase: int
    functional_state: Mapping[str, Any]


@dataclass(frozen=True)
class BoundaryResult:
    """One reset or ordinary boundary, before evidence-schema materialization."""

    profile_id: str
    global_tick: int
    epoch_id: int
    epoch_origin_tick: int
    local_tick: int
    epoch_origin_s: float
    timestamp_s: float
    boundary_kind: str
    event_ids: tuple[str, ...]
    held_before_id: str | None
    published_after_id: str | None
    operations: tuple[Mapping[str, Any], ...]
    guards: tuple[Mapping[str, Any], ...]
    probes: tuple[Mapping[str, Any], ...]
    wires: tuple[EpochEnvelope, ...]
    required_after_imu_capture: ObserverCapture | None = None


_ALLOWED_PRODUCERS: Mapping[tuple[str, str], frozenset[str]] = MappingProxyType(
    {
        ("feedback", "plant"): frozenset({"actuator_reset", "actuator"}),
        ("held_torque", "actuator"): frozenset(
            {"controller_reset", "controller"}
        ),
        ("sensor_truth", "imu"): frozenset({"plant_truth_boundary"}),
        ("imu", "measurement_adapter"): frozenset({"imu"}),
        ("imu", "estimator"): frozenset(
            {"measurement_adapter", "sealed_replay", "fault_injector"}
        ),
        ("estimate", "controller"): frozenset(
            {"estimator", "sealed_replay", "fault_injector"}
        ),
        ("attitude_command", "controller"): frozenset(
            {"command_sampler", "sealed_replay", "fault_injector"}
        ),
        ("feedback", "controller"): frozenset(
            {"actuator_reset", "actuator", "sealed_replay"}
        ),
    }
)

_EXPECTED_INPUT_ROLES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "plant": ("feedback",),
        "actuator": ("held_torque",),
        "imu": ("sensor_truth",),
        "measurement_adapter": ("imu",),
        "estimator": ("imu",),
        "controller": ("attitude_command", "estimate", "feedback"),
    }
)


@dataclass(frozen=True)
class GuardedInput:
    """One immutable role/envelope binding in a real consumer input bundle."""

    role: str
    envelope: EpochEnvelope

    def __post_init__(self) -> None:
        if not isinstance(self.role, str) or not self.role:
            raise SessionContractError(
                "invalid_guard_bundle", "role must be non-empty"
            )
        if not isinstance(self.envelope, EpochEnvelope):
            raise SessionContractError(
                "invalid_guard_bundle", "envelope must be EpochEnvelope"
            )


def guard_envelope(
    envelope: EpochEnvelope,
    *,
    active_epoch_id: int,
    expected_role: str,
    consumer: str,
) -> None:
    """Apply the one shared epoch/provenance guard used by live and replay paths."""

    current_epoch = _nonnegative_integer(active_epoch_id, "active_epoch_id")
    if envelope.role != expected_role:
        raise SessionContractError("role_mismatch")
    if envelope.epoch_id != current_epoch:
        raise SessionContractError("stale_epoch")
    if envelope.producer == "evaluator_truth":
        raise SessionContractError("truth_dependency_forbidden")
    if envelope.producer not in _ALLOWED_PRODUCERS.get(
        (expected_role, consumer), frozenset()
    ):
        raise SessionContractError("forbidden_provenance_edge")


def guard_input_bundle(
    inputs: tuple[GuardedInput, ...],
    *,
    active_epoch_id: int,
    consumer: str,
) -> None:
    """Guard exactly one immutable bundle immediately before its consumer.

    The required roles and their order are fixed by the consumer.  This keeps a
    controller attempt from being represented by three unrelated guard calls,
    and prevents a probe from replacing one candidate while silently omitting
    the other legal inputs in that same attempted bundle.
    """

    if not isinstance(inputs, tuple) or any(
        not isinstance(item, GuardedInput) for item in inputs
    ):
        raise SessionContractError(
            "invalid_guard_bundle", "inputs must be a tuple of GuardedInput"
        )
    expected = _EXPECTED_INPUT_ROLES.get(consumer)
    if expected is None:
        raise SessionContractError(
            "invalid_guard_bundle", f"unknown consumer {consumer!r}"
        )
    actual = tuple(item.role for item in inputs)
    if actual != expected:
        raise SessionContractError(
            "invalid_guard_bundle",
            f"{consumer} requires roles {expected!r}, got {actual!r}",
        )
    for item in inputs:
        guard_envelope(
            item.envelope,
            active_epoch_id=active_epoch_id,
            expected_role=item.role,
            consumer=consumer,
        )


_COMPONENT_COUNTERS = (
    "plant_reset_attempts",
    "actuator_reset_attempts",
    "imu_reset_attempts",
    "estimator_reset_attempts",
    "controller_reset_attempts",
    "plant_step_attempts",
    "actuator_step_attempts",
    "imu_sample_attempts",
    "estimator_process_attempts",
    "estimator_process_accepted",
    "estimator_process_rejected",
    "controller_step_attempts",
    "controller_step_accepted",
    "controller_step_rejected",
)

_FRONTIER_PAYLOAD_FIELDS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "plant_state": ("q_nb", "omega_b_rad_s", "timestamp_s"),
        "sensor_truth": (
            "q_nb",
            "omega_b_rad_s",
            "acceleration_n_m_s2",
        ),
        "held_torque": (
            "requested_torque_body_Nm",
            "limited_torque_body_Nm",
            "timestamp_s",
            "saturated",
        ),
        "feedback": (
            "actual_torque_body_Nm",
            "limited_torque_body_Nm",
            "saturated",
            "timestamp_s",
            "command_timestamp_s",
        ),
        "imu": (
            "timestamp_s",
            "gyro_b_rad_s",
            "specific_force_b_m_s2",
            "valid",
        ),
        "estimate": (
            "q_nb_estimate",
            "omega_b_estimate_rad_s",
            "timestamp_s",
            "valid",
        ),
        "attitude_command": ("q_nb_command", "timestamp_s", "valid"),
        "estimator_diagnostics": (
            "accepted",
            "reason",
            "correction_eligible",
            "correction_applied",
            "correction_capped",
            "elapsed_periods",
            "missing_periods",
            "gap_approximated",
        ),
        "controller_diagnostics": (
            "accepted",
            "reason",
            "rate_error_rad_s",
            "derivative_raw_rad_s2",
            "derivative_filtered_rad_s2",
            "proportional_Nm",
            "integral_before_Nm",
            "derivative_Nm",
            "conditional_integral_rate_Nm_s",
            "limit_backcalculation_rate_Nm_s",
            "lag_backcalculation_rate_Nm_s",
            "integral_after_Nm",
            "requested_Nm",
            "limited_Nm",
            "saturated",
            "epoch_id",
            "tick_index",
        ),
    }
)


class IntegrationSession:
    """Order the five real components and reject stale/prohibited envelopes."""

    def __init__(
        self,
        *,
        profile_id: str,
        scheduler: Any,
        event_schedule: Any,
        simulation: Any,
        estimator_types: Any,
        g1_parameters: Any,
        plant: Any,
        actuator: Any,
        imu: Any,
        estimator: Any,
        controller: Any,
        command_factory: Callable[[Any, float, bool], Any],
        actor_ids: Mapping[str, str],
        observer_manifest_sha256: str,
        configuration_bindings: Mapping[str, str],
        seed: int,
        plant_q_nb: Any,
        plant_omega_b_rad_s: Any,
        estimator_q_nb: Any,
        estimator_omega_b_rad_s: Any,
        actuator_actual_torque_body_Nm: Any,
        initial_epoch_id: int = 0,
        scenario_origin_s: float = 0.0,
        snapshotter: Callable[["IntegrationSession"], Mapping[str, Any]] | None = None,
        lifecycle_recorder: LifecycleRecorder | None = None,
    ) -> None:
        if not isinstance(profile_id, str) or not profile_id:
            raise SessionContractError(
                "invalid_session_argument", "profile_id must be non-empty"
            )
        if not callable(command_factory):
            raise SessionContractError(
                "invalid_session_argument", "command_factory must be callable"
            )
        if snapshotter is not None and not callable(snapshotter):
            raise SessionContractError(
                "invalid_session_argument", "snapshotter must be callable"
            )
        required_actor_roles = {
            "plant",
            "actuator",
            "imu",
            "estimator",
            "controller",
            "observer",
        }
        if not isinstance(actor_ids, Mapping) or set(actor_ids) != required_actor_roles:
            raise SessionContractError(
                "invalid_session_argument",
                f"actor_ids must contain exactly {sorted(required_actor_roles)!r}",
            )
        normalized_actor_ids: dict[str, str] = {}
        for role in sorted(required_actor_roles):
            actor_id = actor_ids[role]
            if not isinstance(actor_id, str) or not actor_id:
                raise SessionContractError(
                    "invalid_session_argument",
                    f"actor_ids[{role!r}] must be non-empty",
                )
            normalized_actor_ids[role] = actor_id
        if len(set(normalized_actor_ids.values())) != len(normalized_actor_ids):
            raise SessionContractError(
                "invalid_session_argument", "actor IDs must be unique"
            )
        required_configuration_bindings = {
            "scheduler_definition_sha256",
            "event_definition_sha256",
            "parameter_binding_sha256",
        }
        if (
            not isinstance(configuration_bindings, Mapping)
            or set(configuration_bindings) != required_configuration_bindings
        ):
            raise SessionContractError(
                "invalid_session_argument",
                "configuration_bindings must contain exactly "
                f"{sorted(required_configuration_bindings)!r}",
            )
        normalized_bindings = {
            name: _sha256(configuration_bindings[name], name)
            for name in sorted(required_configuration_bindings)
        }
        event_table = getattr(event_schedule, "_events", None)
        if not isinstance(event_table, (tuple, list)):
            raise SessionContractError(
                "event_definition_invalid",
                "event_schedule._events must expose the validated event table",
            )
        plain_event_table = _plain_event_value(
            event_table, "event_schedule._events"
        )
        observed_event_sha256 = _event_definition_sha256(plain_event_table)
        if observed_event_sha256 != normalized_bindings["event_definition_sha256"]:
            raise SessionContractError(
                "event_definition_mismatch",
                "event_schedule._events does not match event_definition_sha256",
            )
        frozen_event_table = _deep_freeze_event_value(plain_event_table)
        try:
            event_schedule._events = frozen_event_table
        except Exception as exc:
            raise SessionContractError(
                "event_definition_not_freezable",
                "event_schedule._events cannot be bound immutably",
            ) from exc
        if getattr(event_schedule, "_events", None) is not frozen_event_table:
            raise SessionContractError(
                "event_definition_not_freezable",
                "event_schedule did not retain the immutable event table",
            )
        if lifecycle_recorder is not None and not isinstance(
            lifecycle_recorder, LifecycleRecorder
        ):
            raise SessionContractError(
                "invalid_session_argument",
                "lifecycle_recorder must be LifecycleRecorder",
            )
        self.profile_id = profile_id
        self.scheduler = scheduler
        self.event_schedule = event_schedule
        self._event_table = frozen_event_table
        self.simulation = simulation
        self.estimator_types = estimator_types
        self.g1_parameters = g1_parameters
        self.plant = plant
        self.actuator = actuator
        self.imu = imu
        self.estimator = estimator
        self.controller = controller
        self.command_factory = command_factory
        self._actor_ids = MappingProxyType(normalized_actor_ids)
        self._observer_manifest_sha256 = _sha256(
            observer_manifest_sha256, "observer_manifest_sha256"
        )
        self._configuration_bindings = MappingProxyType(normalized_bindings)
        self._lifecycle_recorder = lifecycle_recorder or LifecycleRecorder()
        self.seed = _nonnegative_integer(seed, "seed")
        self._initial_epoch_id = _nonnegative_integer(
            initial_epoch_id, "initial_epoch_id"
        )
        self._scenario_origin_s = _finite_float(
            scenario_origin_s, "scenario_origin_s"
        )
        self._plant_q_nb = _vector(plant_q_nb, 4, "plant_q_nb")
        self._plant_omega = _vector(
            plant_omega_b_rad_s, 3, "plant_omega_b_rad_s"
        )
        self._estimator_q_nb = _vector(estimator_q_nb, 4, "estimator_q_nb")
        self._estimator_omega = _vector(
            estimator_omega_b_rad_s, 3, "estimator_omega_b_rad_s"
        )
        self._actuator_actual = _vector(
            actuator_actual_torque_body_Nm,
            3,
            "actuator_actual_torque_body_Nm",
        )
        self._snapshotter = snapshotter
        self._lifecycle = SessionLifecycle.NEW
        self._epoch_id: int | None = None
        self._epoch_origin_tick: int | None = None
        self._epoch_origin_s: float | None = None
        self._next_global_tick = 0
        self._last_completed_global_tick: int | None = None
        self._phase_cursor = 0
        self._envelope_sequence = 0
        self._held: EpochEnvelope | None = None
        self._feedback: EpochEnvelope | None = None
        self._last_raw_sample: EpochEnvelope | None = None
        self._last_sample: EpochEnvelope | None = None
        self._last_estimate: EpochEnvelope | None = None
        self._last_command: EpochEnvelope | None = None
        self._last_plant_state: EpochEnvelope | None = None
        self._last_truth: EpochEnvelope | None = None
        self._last_event_ids: tuple[str, ...] = ()
        self._last_event_state: Mapping[str, Any] | None = None
        self._pending_publication: EpochEnvelope | None = None
        self._pending_inputs: tuple[EpochEnvelope, ...] = ()
        self._pending_event_state: Mapping[str, Any] | None = None
        self._call_counts = {name: 0 for name in _COMPONENT_COUNTERS}
        self._failure_frontier: Mapping[str, Any] | None = None

    @property
    def lifecycle(self) -> SessionLifecycle:
        return self._lifecycle

    @property
    def epoch_id(self) -> int:
        if self._epoch_id is None:
            raise SessionContractError("session_not_reset")
        return self._epoch_id

    @property
    def epoch_origin_tick(self) -> int:
        if self._epoch_origin_tick is None:
            raise SessionContractError("session_not_reset")
        return self._epoch_origin_tick

    @property
    def epoch_origin_s(self) -> float:
        if self._epoch_origin_s is None:
            raise SessionContractError("session_not_reset")
        return self._epoch_origin_s

    @property
    def next_global_tick(self) -> int:
        return self._next_global_tick

    @property
    def held_envelope(self) -> EpochEnvelope:
        if self._held is None:
            raise SessionContractError("session_not_reset")
        return self._held

    @property
    def feedback_envelope(self) -> EpochEnvelope:
        if self._feedback is None:
            raise SessionContractError("session_not_reset")
        return self._feedback

    @property
    def last_sample_envelope(self) -> EpochEnvelope | None:
        return self._last_sample

    @property
    def last_estimate_envelope(self) -> EpochEnvelope | None:
        return self._last_estimate

    @property
    def last_command_envelope(self) -> EpochEnvelope | None:
        return self._last_command

    @property
    def call_counts(self) -> Mapping[str, int]:
        """Immediate component-call audit used by zero-call guard assertions.

        These counters are not the authoritative batch denominator.  Raw
        evidence derives reset/setup counts from lifecycle observations and
        ordinary component attempts from their ordered operation records.
        """

        return MappingProxyType(dict(self._call_counts))

    @property
    def failure_frontier(self) -> Mapping[str, Any] | None:
        """Read-only facts retained at the first interrupted transaction."""

        return self._failure_frontier

    @property
    def actor_ids(self) -> Mapping[str, str]:
        return self._actor_ids

    @property
    def lifecycle_observations(self) -> tuple[Mapping[str, Any], ...]:
        return self._lifecycle_recorder.observations

    def bind_snapshotter(
        self, snapshotter: Callable[["IntegrationSession"], Mapping[str, Any]]
    ) -> None:
        """Bind the version-specific read-only observer before the first reset."""

        if self._lifecycle is not SessionLifecycle.NEW:
            raise SessionContractError(
                "observer_binding_closed", "snapshotter must be bound before reset"
            )
        if not callable(snapshotter):
            raise SessionContractError(
                "invalid_session_argument", "snapshotter must be callable"
            )
        self._snapshotter = snapshotter

    def _increment(self, name: str) -> None:
        self._call_counts[name] += 1

    def _terminal(self, reason: str, detail: str = "") -> None:
        self._lifecycle = SessionLifecycle.TERMINAL_INCONCLUSIVE
        raise SessionContractError(reason, detail)

    def _raise_terminal_inconclusive(self) -> None:
        """Reject a later call while retaining the first failure frontier."""

        error = SessionContractError("terminal_inconclusive")
        if self._failure_frontier is not None:
            error._bind_failure_frontier(self._failure_frontier)
        raise error

    def _assert_event_schedule_binding(self) -> None:
        """Reject replacement of the deeply frozen, digest-bound event table."""

        if getattr(self.event_schedule, "_events", None) is not self._event_table:
            raise SessionContractError(
                "event_definition_mismatch",
                "event_schedule._events was replaced after immutable binding",
            )

    def _operation_id(self, global_tick: int, phase: int, label: str) -> str:
        return f"{self.profile_id}/g{global_tick}/p{phase}/{label}"

    def _new_envelope(
        self,
        *,
        role: str,
        payload: Any,
        global_tick: int,
        local_tick: int,
        phase: int,
        producer: str,
        producer_operation_id: str | None,
        parent_ids: Sequence[str] = (),
    ) -> EpochEnvelope:
        self._envelope_sequence += 1
        envelope_id = (
            f"{self.profile_id}/e{self.epoch_id}/g{global_tick}/p{phase}/"
            f"{role}/{self._envelope_sequence}"
        )
        return EpochEnvelope(
            envelope_id=envelope_id,
            role=role,
            epoch_id=self.epoch_id,
            global_tick=global_tick,
            local_tick=local_tick,
            phase=phase,
            producer=producer,
            producer_operation_id=producer_operation_id,
            parent_ids=tuple(parent_ids),
            payload=payload,
        )

    @staticmethod
    def _payload_value(role: str, payload: Any) -> Any:
        """Detach the actual public value for a wire or lifecycle result."""

        if role == "held_torque":
            value = {
                "requested_torque_body_Nm": payload.requested_torque_body_Nm,
                "limited_torque_body_Nm": payload.limited_torque_body_Nm,
                "saturated": payload.saturated,
                "timestamp_s": payload.timestamp_s,
            }
        elif role == "feedback":
            value = {
                "actual_torque_body_Nm": payload.actual_torque_body_Nm,
                "limited_torque_body_Nm": payload.limited_torque_body_Nm,
                "saturated": payload.saturated,
                "timestamp_s": payload.timestamp_s,
                "command_timestamp_s": payload.command_timestamp_s,
            }
        elif role == "imu":
            value = {
                "gyro_rad_s": payload.gyro_b_rad_s,
                "specific_force_m_s2": payload.specific_force_b_m_s2,
                "timestamp_s": payload.timestamp_s,
                "valid": payload.valid,
            }
        elif role == "estimate":
            value = {
                "q_nb": payload.q_nb_estimate,
                "omega_b_rad_s": payload.omega_b_estimate_rad_s,
                "timestamp_s": payload.timestamp_s,
                "valid": payload.valid,
            }
        elif role == "attitude_command":
            value = {
                "q_nb": payload.q_nb_command,
                "timestamp_s": payload.timestamp_s,
                "valid": payload.valid,
            }
        elif role == "plant_state":
            value = {
                "q_nb": payload.q_nb,
                "omega_b_rad_s": payload.omega_b_rad_s,
                "timestamp_s": payload.timestamp_s,
            }
        elif role == "sensor_truth":
            value = {
                "q_nb": payload.q_nb,
                "omega_b_rad_s": payload.omega_b_rad_s,
                "translational_acceleration_n_m_s2": payload.acceleration_n_m_s2,
            }
        elif role == "imu_state":
            value = {
                "reset_epoch_s": payload.reset_epoch_s,
                "last_sample_timestamp_s": payload.last_sample_timestamp_s,
                "samples_emitted": payload.samples_emitted,
                "rng_seed": payload.rng_seed,
            }
        elif role in {"estimator_diagnostics", "controller_diagnostics"}:
            value = payload
        else:
            value = payload
        return value

    @staticmethod
    def _payload_state(envelope: EpochEnvelope | None) -> Any:
        if envelope is None:
            return None
        value = IntegrationSession._payload_value(envelope.role, envelope.payload)
        kind_by_role = {
            "plant_state": "plant_state",
            "sensor_truth": "sensor_truth",
            "held_torque": "torque_command",
            "feedback": "feedback",
            "imu": "imu",
            "estimate": "estimate",
            "attitude_command": "attitude_command",
            "estimator_diagnostics": "estimator_diagnostics",
            "controller_diagnostics": "controller_diagnostics",
        }
        producer_field = envelope.role
        if envelope.role == "held_torque":
            producer_field = "torque_command"
        elif envelope.role == "imu":
            producer_field = (
                "raw_imu" if envelope.producer == "imu" else "adapted_imu"
            )
        return {
            "wire_id": envelope.envelope_id,
            "kind": kind_by_role[envelope.role],
            "role": envelope.role,
            "producer": envelope.producer,
            "parent_ids": envelope.parent_ids,
            "epoch_id": envelope.epoch_id,
            "global_tick": envelope.global_tick,
            "local_tick": envelope.local_tick,
            "phase": envelope.phase,
            "producer_operation_id": envelope.producer_operation_id,
            "producer_field": producer_field,
            "payload": value,
        }

    def _lifecycle_call(
        self,
        *,
        operation_id: str,
        owner: str,
        method: str,
        callsite: str,
        arguments: Mapping[str, Any],
        call: Callable[[], Any],
    ) -> tuple[Any, str]:
        """Surround one real reset/capture delegate with lifecycle records."""

        token = self._lifecycle_recorder.begin(
            profile_id=self.profile_id,
            operation_id=operation_id,
            owner=owner,
            method=method,
            callsite=callsite,
            actor_id=self._actor_ids[owner],
            core_use=None,
            arguments=arguments,
        )
        try:
            result = call()
        except Exception as exc:
            self._lifecycle_recorder.raised(token, exc)
            raise
        self._lifecycle_recorder.returned(
            token,
            result=_lifecycle_result(actor_id=self._actor_ids[owner]),
        )
        return result, token.call_id

    def functional_state(self) -> Mapping[str, Any]:
        """Return session-owned functional state; audit counters are excluded."""

        self._assert_event_schedule_binding()
        return {
            "lifecycle": self._lifecycle.value,
            "needs_reset": self._lifecycle is SessionLifecycle.NEEDS_RESET,
            "epoch_id": self._epoch_id,
            "epoch_origin_tick": self._epoch_origin_tick,
            "epoch_origin_s": self._epoch_origin_s,
            "next_global_tick": self._next_global_tick,
            "last_completed_global_tick": self._last_completed_global_tick,
            "phase_cursor": self._phase_cursor,
            "envelope_sequence": self._envelope_sequence,
            "held": self._payload_state(self._held),
            "feedback": self._payload_state(self._feedback),
            "last_raw_sample": self._payload_state(self._last_raw_sample),
            "last_sample": self._payload_state(self._last_sample),
            "last_estimate": self._payload_state(self._last_estimate),
            "last_command": self._payload_state(self._last_command),
            "last_plant_state": self._payload_state(self._last_plant_state),
            "last_truth": self._payload_state(self._last_truth),
            "last_event_ids": self._last_event_ids,
            "last_event_state": self._last_event_state,
            "pending_publication": self._payload_state(self._pending_publication),
            "pending_inputs": tuple(
                self._payload_state(envelope) for envelope in self._pending_inputs
            ),
            "pending_event_state": self._pending_event_state,
            "configuration_values": {
                "seed": self.seed,
                "initial_epoch_id": self._initial_epoch_id,
                "scenario_origin_s": self._scenario_origin_s,
                "plant_q_nb": self._plant_q_nb,
                "plant_omega_b_rad_s": self._plant_omega,
                "estimator_q_nb": self._estimator_q_nb,
                "estimator_omega_b_rad_s": self._estimator_omega,
                "actuator_actual_torque_body_Nm": self._actuator_actual,
                **self._configuration_bindings,
            },
        }

    @staticmethod
    def _event_state(active: Any) -> Mapping[str, Any]:
        bias = getattr(active, "imu_bias", None)
        return {
            "event_ids": tuple(getattr(active, "event_ids", ())),
            "command_q_nb": np.asarray(active.command_q_nb, dtype=np.float64).copy(),
            "external_torque_body_Nm": np.asarray(
                active.external_torque_body_Nm, dtype=np.float64
            ).copy(),
            "imu_bias": None if bias is None else dict(bias),
            "specific_force_body_m_s2": np.asarray(
                active.specific_force_body_m_s2, dtype=np.float64
            ).copy(),
            "invalid_event": (
                None
                if getattr(active, "invalid_event", None) is None
                else dict(active.invalid_event)
            ),
            "reset_event": (
                None
                if getattr(active, "reset_event", None) is None
                else dict(active.reset_event)
            ),
        }

    def capture_state(
        self, snapshot_id: str, capture_id: str | None = None
    ) -> Any:
        """Capture one detached functional snapshot through the bound observer.

        Capture identities are audit-only and deliberately absent from the
        returned functional value, so exact comparisons cannot fail merely
        because they are distinct observer events.
        """

        if not isinstance(snapshot_id, str) or not snapshot_id:
            raise SessionContractError(
                "invalid_session_argument", "snapshot_id must be non-empty"
            )
        actual_capture_id = (
            f"{snapshot_id}/capture" if capture_id is None else capture_id
        )
        if not isinstance(actual_capture_id, str) or not actual_capture_id:
            raise SessionContractError(
                "invalid_session_argument", "capture_id must be non-empty"
            )
        if self._snapshotter is None:
            raise SessionContractError(
                "observer_required", "capture_state requires the bound full observer"
            )

        token = self._lifecycle_recorder.begin(
            profile_id=self.profile_id,
            operation_id=snapshot_id,
            owner="observer",
            method="capture_snapshot",
            callsite="integration_session.capture_state.snapshotter",
            actor_id=self._actor_ids["observer"],
            core_use=None,
            arguments={
                "kind": "observer",
                "snapshot_id": snapshot_id,
                "capture_id": actual_capture_id,
                "observer_manifest_sha256": self._observer_manifest_sha256,
            },
        )
        try:
            observed = self._snapshotter(self)
            required_sections = {
                "session",
                "plant",
                "actuator",
                "imu",
                "estimator",
                "controller",
            }
            if not isinstance(observed, Mapping) or set(observed) != required_sections:
                raise SessionContractError(
                    "observer_snapshot_invalid",
                    f"observer must return exactly {sorted(required_sections)!r}",
                )
            captured = canonical_snapshot_value(observed)
        except Exception as exc:
            self._lifecycle_recorder.raised(token, exc)
            raise
        self._lifecycle_recorder.returned(
            token,
            result=_lifecycle_result(
                actor_id=self._actor_ids["observer"],
                snapshot_ref=snapshot_id,
                capture_id=actual_capture_id,
            ),
        )
        return captured

    @staticmethod
    def _assert_same_snapshot(before: Any, after: Any, context: str) -> None:
        if canonical_snapshot_bytes(before) != canonical_snapshot_bytes(after):
            raise SessionContractError(
                "rejection_mutated_state", f"{context} changed functional state"
            )

    @staticmethod
    def _assert_needs_reset_transition(before: Any, after: Any, context: str) -> None:
        """Allow exactly the declared ACTIVE -> NEEDS_RESET session transition."""

        before_copy = json.loads(canonical_snapshot_bytes(before))
        after_copy = json.loads(canonical_snapshot_bytes(after))
        try:
            before_session = before_copy["session"]
            after_session = after_copy["session"]
        except (KeyError, TypeError) as exc:
            raise SessionContractError(
                "observer_missing_session_state", context
            ) from exc
        transition_found = False
        if "lifecycle" in before_session or "lifecycle" in after_session:
            if (
                before_session.get("lifecycle") != SessionLifecycle.ACTIVE.value
                or after_session.get("lifecycle")
                != SessionLifecycle.NEEDS_RESET.value
            ):
                raise SessionContractError(
                    "needs_reset_transition_mismatch", context
                )
            before_session["lifecycle"] = SessionLifecycle.ACTIVE.value
            after_session["lifecycle"] = SessionLifecycle.ACTIVE.value
            transition_found = True
        if "needs_reset" in before_session or "needs_reset" in after_session:
            if (
                before_session.get("needs_reset") is not False
                or after_session.get("needs_reset") is not True
            ):
                raise SessionContractError(
                    "needs_reset_transition_mismatch", context
                )
            before_session["needs_reset"] = False
            after_session["needs_reset"] = False
            transition_found = True
        if not transition_found:
            raise SessionContractError(
                "observer_missing_needs_reset", context
            )
        IntegrationSession._assert_same_snapshot(before_copy, after_copy, context)

    def _component_counts(self) -> dict[str, int]:
        return {name: self._call_counts[name] for name in _COMPONENT_COUNTERS}

    @staticmethod
    def _readonly_records(
        records: Sequence[Mapping[str, Any]],
    ) -> tuple[Mapping[str, Any], ...]:
        frozen = tuple(_freeze_frontier_value(record) for record in records)
        if any(not isinstance(record, Mapping) for record in frozen):
            raise SessionContractError(
                "failure_frontier_not_freezable",
                "failure journal records must be mappings",
            )
        return frozen

    @staticmethod
    def _freeze_frontier_envelope(envelope: EpochEnvelope) -> EpochEnvelope:
        fields_for_role = _FRONTIER_PAYLOAD_FIELDS.get(envelope.role)
        if fields_for_role is None:
            raise SessionContractError(
                "failure_frontier_not_freezable",
                f"unsupported retained wire role {envelope.role!r}",
            )
        payload_values: dict[str, Any] = {}
        for field_name in fields_for_role:
            try:
                field_value = getattr(envelope.payload, field_name)
            except AttributeError as exc:
                raise SessionContractError(
                    "failure_frontier_not_freezable",
                    f"{envelope.role} lacks {field_name}",
                ) from exc
            payload_values[field_name] = _freeze_frontier_value(field_value)
        return EpochEnvelope(
            envelope_id=envelope.envelope_id,
            role=envelope.role,
            epoch_id=envelope.epoch_id,
            global_tick=envelope.global_tick,
            local_tick=envelope.local_tick,
            phase=envelope.phase,
            producer=envelope.producer,
            producer_operation_id=envelope.producer_operation_id,
            parent_ids=tuple(envelope.parent_ids),
            payload=_FrozenAttributeView(payload_values),
        )

    def _interrupt_transaction(
        self,
        exc: Exception,
        *,
        fallback_reason: str,
        global_tick: int,
        epoch_id: int,
        epoch_origin_tick: int,
        local_tick: int,
        epoch_origin_s: float,
        timestamp_s: float,
        boundary_kind: str,
        event_ids: Sequence[str],
        held_before_id: str | None,
        published_after_id: str | None,
        operations: Sequence[Mapping[str, Any]],
        guards: Sequence[Mapping[str, Any]],
        probes: Sequence[Mapping[str, Any]],
        wires: Sequence[EpochEnvelope],
        required_after_imu_capture: ObserverCapture | None = None,
    ) -> SessionContractError:
        """Terminate once and retain only facts already observed at failure.

        This path deliberately performs no observer capture or component call.
        A secondary recording failure therefore cannot replace the original
        exception or manufacture state beyond the actual failure frontier.
        """

        self._lifecycle = SessionLifecycle.TERMINAL_INCONCLUSIVE
        original_reason = getattr(exc, "reason", None)
        if not isinstance(original_reason, str) or not original_reason:
            original_reason = None
        try:
            original_message = str(exc)
        except Exception:
            original_message = f"<{type(exc).__name__}>"
        original_detail = getattr(exc, "detail", None)
        if not isinstance(original_detail, str):
            original_detail = original_message
        original_exception = MappingProxyType(
            {
                "type": type(exc).__name__,
                "reason": original_reason,
                "detail": original_detail,
                "message": original_message,
            }
        )
        if self._failure_frontier is None:
            fixed_frontier = {
                "profile_id": self.profile_id,
                "global_tick": global_tick,
                "epoch_id": epoch_id,
                "epoch_origin_tick": epoch_origin_tick,
                "local_tick": local_tick,
                "epoch_origin_s": epoch_origin_s,
                "timestamp_s": timestamp_s,
                "boundary_kind": boundary_kind,
                "event_ids": tuple(event_ids),
                "held_before_id": held_before_id,
                "published_after_id": published_after_id,
                "component_call_counts": MappingProxyType(
                    self._component_counts()
                ),
                "original_exception": original_exception,
                "lifecycle_state": self._lifecycle.value,
                "phase_cursor": self._phase_cursor,
                "termination_status": (
                    SessionLifecycle.TERMINAL_INCONCLUSIVE.value
                ),
                # This is the already-returned phase-3 observation, not a
                # request to invoke the observer while handling a failure.
                "required_after_imu_capture": required_after_imu_capture,
            }
            retention_status = "complete"
            missing_observations: tuple[str, ...] = ()
            retention_exception: Mapping[str, Any] | None = None
            try:
                retained_facts = {
                    "operations": self._readonly_records(operations),
                    "guards": self._readonly_records(guards),
                    "probes": self._readonly_records(probes),
                    "wires": tuple(
                        self._freeze_frontier_envelope(wire)
                        for wire in wires
                    ),
                }
            except Exception as retention_error:
                # Frontier retention is secondary to the component/observer
                # failure.  Never replace that first cause with a serializer
                # or payload-introspection error.
                try:
                    exc.add_note(
                        "failure-frontier retention was incomplete: "
                        f"{type(retention_error).__name__}: "
                        f"{retention_error}"
                    )
                except Exception:
                    pass
                retention_status = "incomplete"
                missing_observations = (
                    "operations",
                    "guards",
                    "probes",
                    "wires",
                )
                try:
                    retention_message = str(retention_error)
                except Exception:
                    retention_message = f"<{type(retention_error).__name__}>"
                retention_exception = MappingProxyType(
                    {
                        "type": type(retention_error).__name__,
                        "reason": getattr(retention_error, "reason", None),
                        "message": retention_message,
                    }
                )
                retained_facts = {
                    "operations": (),
                    "guards": (),
                    "probes": (),
                    "wires": (),
                }
            self._failure_frontier = MappingProxyType(
                {
                    **fixed_frontier,
                    **retained_facts,
                    "retention_status": retention_status,
                    "missing_observations": missing_observations,
                    "retention_exception": retention_exception,
                }
            )
        if isinstance(exc, SessionContractError):
            error = exc
        else:
            detail = f"{type(exc).__name__}: {original_message}"
            error = SessionContractError(
                original_reason or fallback_reason,
                detail,
            )
        error._bind_failure_frontier(self._failure_frontier)
        return error

    @staticmethod
    def _count_delta(
        before: Mapping[str, int], after: Mapping[str, int]
    ) -> dict[str, int]:
        return {name: after[name] - before[name] for name in before}

    @staticmethod
    def _guarded_inputs(
        consumer: str,
        by_role: Mapping[str, EpochEnvelope],
    ) -> tuple[GuardedInput, ...]:
        expected = _EXPECTED_INPUT_ROLES.get(consumer)
        if expected is None or set(by_role) != set(expected):
            raise SessionContractError(
                "invalid_guard_bundle",
                f"{consumer} requires exactly {_EXPECTED_INPUT_ROLES.get(consumer)!r}",
            )
        return tuple(GuardedInput(role, by_role[role]) for role in expected)

    def _guard_inputs(
        self,
        by_role: Mapping[str, EpochEnvelope],
        *,
        consumer: str,
        global_tick: int,
        phase: int,
        operation_id: str,
        guard_log: list[Mapping[str, Any]],
        candidate_role: str | None = None,
    ) -> str:
        bundle = self._guarded_inputs(consumer, by_role)
        if candidate_role is not None and candidate_role not in by_role:
            raise SessionContractError(
                "invalid_guard_bundle", f"missing candidate role {candidate_role!r}"
            )
        reason = "accepted"
        accepted = True
        try:
            guard_input_bundle(
                bundle,
                active_epoch_id=self.epoch_id,
                consumer=consumer,
            )
        except SessionContractError as exc:
            accepted = False
            reason = exc.reason
        guard_id = f"{operation_id}/guard/{len(guard_log) + 1}"
        candidate = None if candidate_role is None else by_role[candidate_role]
        guard_log.append(
            {
                "guard_id": guard_id,
                "site": f"{consumer}.consume.input_bundle",
                "global_tick": global_tick,
                "phase": phase,
                "consumer_operation_id": operation_id,
                "checked_refs": {
                    item.role: item.envelope.envelope_id for item in bundle
                },
                "candidate_id": (
                    None if candidate is None else candidate.envelope_id
                ),
                "role": "input_bundle" if candidate_role is None else candidate_role,
                "producer": None if candidate is None else candidate.producer,
                "accepted": accepted,
                "reason": reason,
            }
        )
        if not accepted:
            raise SessionContractError(reason)
        return guard_id

    def _run_probes(
        self,
        probes: tuple[GuardProbe, ...],
        *,
        global_tick: int,
        phase: int,
        operation_id: str,
        guard_log: list[Mapping[str, Any]],
        probe_log: list[Mapping[str, Any]],
        legal_by_role: Mapping[str, EpochEnvelope],
    ) -> None:
        for probe in probes:
            legal = legal_by_role.get(probe.expected_role)
            original_legal_id = (
                probe.original_legal_id
                if probe.original_legal_id is not None
                else (None if legal is None else legal.envelope_id)
            )
            if original_legal_id is None:
                self._terminal(
                    "probe_missing_legal_reference", probe.probe_id
                )
            probe_inputs = dict(legal_by_role)
            probe_inputs[probe.expected_role] = probe.envelope
            before_snapshot_id = f"{probe.probe_id}/before"
            before_capture_id = f"{before_snapshot_id}/capture"
            before_state = self.capture_state(
                before_snapshot_id, before_capture_id
            )
            before_counts = self._component_counts()
            try:
                guard_ref = self._guard_inputs(
                    probe_inputs,
                    consumer=probe.consumer,
                    global_tick=global_tick,
                    phase=phase,
                    operation_id=operation_id,
                    guard_log=guard_log,
                    candidate_role=probe.expected_role,
                )
            except SessionContractError as exc:
                if exc.reason != probe.expected_reason:
                    self._terminal(
                        "probe_reason_mismatch",
                        f"{probe.probe_id}: expected {probe.expected_reason}, "
                        f"got {exc.reason}",
                    )
                after_snapshot_id = f"{probe.probe_id}/after"
                after_capture_id = f"{after_snapshot_id}/capture"
                probe_record: dict[str, Any] = {
                    "probe_id": probe.probe_id,
                    "kind": probe.kind,
                    "global_tick": global_tick,
                    "phase": phase,
                    "consumer_operation_id": operation_id,
                    "role": probe.expected_role,
                    "candidate_id": probe.envelope.envelope_id,
                    "original_legal_id": original_legal_id,
                    "source_truth_id": probe.source_truth_id,
                    "source_field": probe.source_field,
                    "target_field": probe.target_field,
                    "derivation_site": probe.derivation_site,
                    "guard_ref": guard_log[-1]["guard_id"],
                    "guard_site": f"{probe.consumer}.consume.input_bundle",
                    "checked_refs": {
                        role: envelope.envelope_id
                        for role, envelope in probe_inputs.items()
                    },
                    "accepted": False,
                    "reason": exc.reason,
                    "before_snapshot_id": before_snapshot_id,
                    "before_capture_id": before_capture_id,
                    "after_snapshot_id": after_snapshot_id,
                    "after_capture_id": after_capture_id,
                    "before_snapshot": before_state,
                    "component_call_delta": self._count_delta(
                        before_counts, self._component_counts()
                    ),
                }
                probe_log.append(probe_record)
                after_state = self.capture_state(
                    after_snapshot_id, after_capture_id
                )
                after_counts = self._component_counts()
                try:
                    self._assert_same_snapshot(
                        before_state, after_state, probe.probe_id
                    )
                except SessionContractError as mutation:
                    self._terminal(mutation.reason, mutation.detail)
                delta = self._count_delta(before_counts, after_counts)
                if any(delta.values()):
                    self._terminal(
                        "probe_called_component", f"{probe.probe_id}: {delta}"
                    )
                probe_record["after_snapshot"] = after_state
                probe_record["component_call_delta"] = delta
                continue
            del guard_ref
            self._terminal("probe_not_rejected", probe.probe_id)

    @staticmethod
    def _exception_reason(exc: BaseException) -> str:
        reason = getattr(exc, "reason", None)
        if isinstance(reason, str) and reason:
            return reason
        message = str(exc)
        return message.split(":", 1)[0] if message else type(exc).__name__

    def _validate_fault_event(self, active: Any, directive: TickDirective) -> None:
        event = getattr(active, "invalid_event", None)
        invalid_kind = None if event is None else event.get("invalid_kind")
        required = {
            "negative_dt": FAULT_CONTROLLER_NEGATIVE_DT,
            "stale_timestamp": FAULT_ESTIMATOR_STALE_TIMESTAMP,
        }
        if invalid_kind is not None and directive.fault != required.get(invalid_kind):
            self._terminal(
                "invalid_event_not_exercised",
                f"event {invalid_kind!r} requires its declared component call",
            )
        if directive.fault in {
            FAULT_CONTROLLER_NEGATIVE_DT,
            FAULT_ESTIMATOR_STALE_TIMESTAMP,
        } and invalid_kind is None:
            self._terminal(
                "fault_without_declared_event", str(directive.fault)
            )

    @staticmethod
    def _same_actuator_feedback(left: Any, right: Any) -> bool:
        """Compare the inner ``step`` return with the outer anchored return."""

        try:
            return bool(
                np.array_equal(
                    left.actual_torque_body_Nm,
                    right.actual_torque_body_Nm,
                )
                and np.array_equal(
                    left.limited_torque_body_Nm,
                    right.limited_torque_body_Nm,
                )
                and np.array_equal(left.saturated, right.saturated)
                and abs(float(left.timestamp_s) - float(right.timestamp_s))
                <= 1.0e-12
                and abs(
                    float(left.command_timestamp_s)
                    - float(right.command_timestamp_s)
                )
                <= 1.0e-12
            )
        except (AttributeError, TypeError, ValueError, OverflowError):
            return False

    def _observed_actuator_step_base(
        self,
        command: EpochEnvelope,
        *,
        operation_id: str,
        operations: list[Mapping[str, Any]],
    ) -> tuple[Any, dict[str, Any]]:
        """Transparently journal the real ``step_base -> self.step`` call.

        The production component exposes no hook for this delegated call.  A
        per-invocation instance wrapper is therefore installed only while the
        real ``step_base`` executes, forwards the exact arguments once, and is
        restored before this method returns.  No delegate record is inferred
        from the outer return.
        """

        actor_namespace = getattr(self.actuator, "__dict__", None)
        if not isinstance(actor_namespace, dict):
            raise SessionContractError(
                "actuator_delegate_unobservable",
                "actuator instance does not expose a replaceable step method",
            )
        original_step = getattr(self.actuator, "step", None)
        if not callable(original_step):
            raise SessionContractError(
                "actuator_delegate_unobservable",
                "actuator.step is not callable",
            )
        had_instance_step = "step" in actor_namespace
        previous_instance_step = actor_namespace.get("step")
        delegate_operation_id = f"{operation_id}/delegate-step"
        invocation_count = 0
        delegate_operation: dict[str, Any] | None = None
        delegate_result: Any = None

        def observed_step(*args: Any, **kwargs: Any) -> Any:
            nonlocal invocation_count, delegate_operation, delegate_result
            invocation_count += 1
            if invocation_count != 1:
                raise SessionContractError(
                    "actuator_delegate_count_mismatch",
                    f"{operation_id} invoked actuator.step more than once",
                )
            if len(args) != 2 or kwargs or args[0] is not command.payload:
                delegate_operation = {
                    "operation_id": delegate_operation_id,
                    "owner": "actuator",
                    "method": "step",
                    "phase": 2,
                    "attempt_kind": "normal",
                    "inputs": {"torque_command": command.envelope_id},
                    "outputs": {},
                    "scalar_inputs": {},
                    "reset_inputs": None,
                    "accepted": False,
                    "reason": "actuator_delegate_shape_changed",
                    "guard_ref": None,
                }
                operations.append(delegate_operation)
                raise SessionContractError(
                    "actuator_delegate_shape_changed",
                    "step_base did not delegate the original command and dt",
                )
            delegate_operation = {
                "operation_id": delegate_operation_id,
                "owner": "actuator",
                "method": "step",
                "phase": 2,
                "attempt_kind": "normal",
                "inputs": {"torque_command": command.envelope_id},
                "outputs": {},
                "scalar_inputs": {"dt_s": args[1]},
                "reset_inputs": None,
                "accepted": False,
                "reason": "delegate_call_incomplete",
                "guard_ref": None,
            }
            operations.append(delegate_operation)
            try:
                delegate_result = original_step(*args, **kwargs)
            except Exception as exc:
                delegate_operation["reason"] = self._exception_reason(exc)
                raise
            delegate_operation["scalar_inputs"] = {
                "dt_s": _finite_float(args[1], "actuator_delegate.dt_s")
            }
            delegate_operation["accepted"] = True
            delegate_operation["reason"] = "accepted"
            return delegate_result

        try:
            setattr(self.actuator, "step", observed_step)
        except Exception as exc:
            raise SessionContractError(
                "actuator_delegate_unobservable",
                "actuator.step cannot be wrapped transparently",
            ) from exc
        try:
            outer_result = self.actuator.step_base(command.payload)
        except Exception:
            try:
                if had_instance_step:
                    setattr(self.actuator, "step", previous_instance_step)
                else:
                    delattr(self.actuator, "step")
            except Exception:
                # Preserve the actual component/delegate exception as the
                # primary failure; the session is terminal after it escapes.
                pass
            raise
        if had_instance_step:
            setattr(self.actuator, "step", previous_instance_step)
        else:
            delattr(self.actuator, "step")
        if invocation_count != 1 or delegate_operation is None:
            raise SessionContractError(
                "actuator_delegate_count_mismatch",
                f"{operation_id} did not invoke actuator.step exactly once",
            )
        if not delegate_operation["accepted"]:
            raise SessionContractError(
                "actuator_delegate_incomplete", operation_id
            )
        if not self._same_actuator_feedback(delegate_result, outer_result):
            raise SessionContractError(
                "actuator_delegate_output_mismatch",
                "inner step and outer step_base returned different feedback",
            )
        return outer_result, delegate_operation

    def reset(self, global_tick: int, *, reason: str) -> BoundaryResult:
        """Perform one controller-first reset-only boundary.

        A partial reset is terminal and is never followed by another component
        call in this session instance.
        """

        tick = _nonnegative_integer(global_tick, "global_tick")
        if self._lifecycle is SessionLifecycle.TERMINAL_INCONCLUSIVE:
            self._raise_terminal_inconclusive()
        if (
            self._lifecycle is not SessionLifecycle.NEW
            and tick != self._next_global_tick
        ):
            raise SessionContractError(
                "unexpected_boundary",
                f"reset {tick} does not match next boundary {self._next_global_tick}",
            )
        self._assert_event_schedule_binding()
        active = self.event_schedule.active_at(tick)
        if self._lifecycle is SessionLifecycle.ACTIVE and getattr(
            active, "reset_event", None
        ) is None:
            raise SessionContractError(
                "undeclared_reset", "active-session reset requires a reset event"
            )
        if (
            self._lifecycle is SessionLifecycle.NEEDS_RESET
            and reason != "needs_reset_recovery"
        ):
            raise SessionContractError(
                "invalid_reset_reason", "needs-reset recovery must be explicit"
            )
        active_event_ids = tuple(getattr(active, "event_ids", ()))
        active_event_state = self._event_state(active)

        next_epoch = (
            self._initial_epoch_id
            if self._epoch_id is None
            else self._epoch_id + 1
        )
        origin_s = self._scenario_origin_s + tick * self.scheduler.base_period_s
        previous_held_id = None if self._held is None else self._held.envelope_id
        self._epoch_id = next_epoch
        self._epoch_origin_tick = tick
        self._epoch_origin_s = origin_s
        self._phase_cursor = 0
        self._held = None
        self._feedback = None
        self._last_raw_sample = None
        self._last_sample = None
        self._last_estimate = None
        self._last_command = None
        self._last_plant_state = None
        self._last_truth = None
        self._last_event_ids = ()
        self._last_event_state = None
        self._pending_publication = None
        self._pending_inputs = ()
        self._pending_event_state = None
        operations: list[Mapping[str, Any]] = []
        wires: list[EpochEnvelope] = []
        published_after_id: str | None = None
        try:
            controller_op = self._operation_id(tick, 0, "controller-reset")
            controller_reset_inputs = {
                "kind": "reset",
                "actor": "controller",
                "reset_epoch": {"id": next_epoch, "timestamp_s": origin_s},
            }
            controller_operation: dict[str, Any] = {
                "operation_id": controller_op,
                "owner": "controller",
                "method": "reset",
                "phase": 0,
                "attempt_kind": "reset",
                "inputs": {},
                "outputs": {},
                "scalar_inputs": {},
                "reset_inputs": controller_reset_inputs,
                "accepted": False,
                "reason": "component_call_incomplete",
                "guard_ref": None,
            }
            operations.append(controller_operation)
            self._increment("controller_reset_attempts")
            try:
                reset_command, _ = self._lifecycle_call(
                    operation_id=controller_op,
                    owner="controller",
                    method="reset",
                    callsite="integration_session.reset.controller",
                    arguments=controller_reset_inputs,
                    call=lambda: self.controller.reset(
                        ResetEpochView(next_epoch, origin_s)
                    ),
                )
            except Exception as exc:
                controller_operation["reason"] = self._exception_reason(exc)
                raise
            held = self._new_envelope(
                role="held_torque",
                payload=reset_command,
                global_tick=tick,
                local_tick=0,
                phase=0,
                producer="controller_reset",
                producer_operation_id=controller_op,
            )
            wires.append(held)
            published_after_id = held.envelope_id
            controller_operation["outputs"] = {
                "torque_command": held.envelope_id
            }
            controller_operation["accepted"] = True
            controller_operation["reason"] = "accepted"

            actuator_op = self._operation_id(tick, 0, "actuator-reset")
            actuator_initial = self.simulation.ActuatorInitialState(
                actual_torque_body_Nm=self._actuator_actual,
                held_limited_torque_body_Nm=reset_command.limited_torque_body_Nm,
                held_command_timestamp_s=reset_command.timestamp_s,
                held_saturated=reset_command.saturated,
                held_requested_torque_body_Nm=reset_command.requested_torque_body_Nm,
            )
            actuator_reset_inputs = {
                "kind": "reset",
                "actor": "actuator",
                "initial_state": {
                    "actual_torque_body_Nm": actuator_initial.actual_torque_body_Nm,
                    "held_limited_torque_body_Nm": (
                        actuator_initial.held_limited_torque_body_Nm
                    ),
                    "held_requested_torque_body_Nm": (
                        actuator_initial.held_requested_torque_body_Nm
                    ),
                    "held_saturated": actuator_initial.held_saturated,
                    "held_command_timestamp_s": (
                        actuator_initial.held_command_timestamp_s
                    ),
                },
                "reset_epoch_s": origin_s,
                "reset_command_ref": held.envelope_id,
            }
            actuator_operation: dict[str, Any] = {
                "operation_id": actuator_op,
                "owner": "actuator",
                "method": "reset",
                "phase": 0,
                "attempt_kind": "reset",
                "inputs": {"torque_command": held.envelope_id},
                "outputs": {},
                "scalar_inputs": {},
                "reset_inputs": actuator_reset_inputs,
                "accepted": False,
                "reason": "component_call_incomplete",
                "guard_ref": None,
            }
            operations.append(actuator_operation)
            self._increment("actuator_reset_attempts")
            try:
                feedback_payload, _ = self._lifecycle_call(
                    operation_id=actuator_op,
                    owner="actuator",
                    method="reset",
                    callsite="integration_session.reset.actuator",
                    arguments=actuator_reset_inputs,
                    call=lambda: self.actuator.reset(actuator_initial, origin_s),
                )
            except Exception as exc:
                actuator_operation["reason"] = self._exception_reason(exc)
                raise
            feedback = self._new_envelope(
                role="feedback",
                payload=feedback_payload,
                global_tick=tick,
                local_tick=0,
                phase=0,
                producer="actuator_reset",
                producer_operation_id=actuator_op,
                parent_ids=(held.envelope_id,),
            )
            wires.append(feedback)
            actuator_operation["outputs"] = {
                "feedback": feedback.envelope_id
            }
            actuator_operation["accepted"] = True
            actuator_operation["reason"] = "accepted"

            plant_op = self._operation_id(tick, 0, "plant-reset")
            plant_initial = self.simulation.PlantInitialState(
                self._plant_q_nb, self._plant_omega
            )
            plant_reset_inputs = {
                "kind": "reset",
                "actor": "plant",
                "initial_state": {
                    "q_nb": plant_initial.q_nb,
                    "omega_b_rad_s": plant_initial.omega_b_rad_s,
                },
                "reset_epoch_s": origin_s,
            }
            plant_operation: dict[str, Any] = {
                "operation_id": plant_op,
                "owner": "plant",
                "method": "reset",
                "phase": 0,
                "attempt_kind": "reset",
                "inputs": {},
                "outputs": {},
                "scalar_inputs": {},
                "reset_inputs": plant_reset_inputs,
                "accepted": False,
                "reason": "component_call_incomplete",
                "guard_ref": None,
            }
            operations.append(plant_operation)
            self._increment("plant_reset_attempts")
            try:
                plant_payload, _ = self._lifecycle_call(
                    operation_id=plant_op,
                    owner="plant",
                    method="reset",
                    callsite="integration_session.reset.plant",
                    arguments=plant_reset_inputs,
                    call=lambda: self.plant.reset(plant_initial, origin_s),
                )
            except Exception as exc:
                plant_operation["reason"] = self._exception_reason(exc)
                raise
            plant_state = self._new_envelope(
                role="plant_state",
                payload=plant_payload,
                global_tick=tick,
                local_tick=0,
                phase=0,
                producer="plant_reset",
                producer_operation_id=plant_op,
            )
            wires.append(plant_state)
            plant_operation["outputs"] = {
                "plant_state": plant_state.envelope_id
            }
            plant_operation["accepted"] = True
            plant_operation["reason"] = "accepted"

            imu_op = self._operation_id(tick, 0, "imu-reset")
            imu_initial = self.simulation.IMUInitialState()
            imu_reset_inputs = {
                "kind": "reset",
                "actor": "imu",
                "initial_state": {},
                "reset_epoch_s": origin_s,
                "rng_seed": self.seed,
            }
            imu_operation: dict[str, Any] = {
                "operation_id": imu_op,
                "owner": "imu",
                "method": "reset",
                "phase": 0,
                "attempt_kind": "reset",
                "inputs": {},
                "outputs": {},
                "scalar_inputs": {},
                "reset_inputs": imu_reset_inputs,
                "accepted": False,
                "reason": "component_call_incomplete",
                "guard_ref": None,
            }
            operations.append(imu_operation)
            self._increment("imu_reset_attempts")
            try:
                self._lifecycle_call(
                    operation_id=imu_op,
                    owner="imu",
                    method="reset",
                    callsite="integration_session.reset.imu",
                    arguments=imu_reset_inputs,
                    call=lambda: self.imu.reset(imu_initial, origin_s, self.seed),
                )
            except Exception as exc:
                imu_operation["reason"] = self._exception_reason(exc)
                raise
            imu_operation["accepted"] = True
            imu_operation["reason"] = "accepted"

            estimator_op = self._operation_id(tick, 0, "estimator-reset")
            estimator_initial = self.estimator_types.EstimatorInitialState(
                self._estimator_q_nb, self._estimator_omega
            )
            estimator_epoch = self.estimator_types.ResetEpoch(next_epoch, origin_s)
            estimator_reset_inputs = {
                "kind": "reset",
                "actor": "estimator",
                "initial_state": {
                    "q_nb": estimator_initial.q_nb,
                    "omega_b_rad_s": estimator_initial.omega_b_rad_s,
                },
                "reset_epoch": {
                    "id": estimator_epoch.id,
                    "timestamp_s": estimator_epoch.timestamp_s,
                },
                "rng_seed": self.seed,
            }
            estimator_operation: dict[str, Any] = {
                "operation_id": estimator_op,
                "owner": "estimator",
                "method": "reset",
                "phase": 0,
                "attempt_kind": "reset",
                "inputs": {},
                "outputs": {},
                "scalar_inputs": {},
                "reset_inputs": estimator_reset_inputs,
                "accepted": False,
                "reason": "component_call_incomplete",
                "guard_ref": None,
            }
            operations.append(estimator_operation)
            self._increment("estimator_reset_attempts")
            try:
                estimate_payload, _ = self._lifecycle_call(
                    operation_id=estimator_op,
                    owner="estimator",
                    method="reset",
                    callsite="integration_session.reset.estimator",
                    arguments=estimator_reset_inputs,
                    call=lambda: self.estimator.reset(
                        estimator_initial,
                        estimator_epoch,
                        self.seed,
                    ),
                )
            except Exception as exc:
                estimator_operation["reason"] = self._exception_reason(exc)
                raise
            estimate = self._new_envelope(
                role="estimate",
                payload=estimate_payload,
                global_tick=tick,
                local_tick=0,
                phase=0,
                producer="estimator_reset",
                producer_operation_id=estimator_op,
            )
            wires.append(estimate)
            estimator_operation["outputs"] = {
                "estimate": estimate.envelope_id
            }
            estimator_operation["accepted"] = True
            estimator_operation["reason"] = "accepted"
        except Exception as exc:
            error = self._interrupt_transaction(
                exc,
                fallback_reason="partial_reset",
                global_tick=tick,
                epoch_id=next_epoch,
                epoch_origin_tick=tick,
                local_tick=0,
                epoch_origin_s=origin_s,
                timestamp_s=origin_s,
                boundary_kind="reset",
                event_ids=active_event_ids,
                held_before_id=previous_held_id,
                published_after_id=published_after_id,
                operations=operations,
                guards=(),
                probes=(),
                wires=wires,
            )
            if error is exc:
                raise
            raise error from exc

        try:
            self._held = held
            self._feedback = feedback
            self._last_estimate = estimate
            self._last_plant_state = plant_state
            self._last_event_ids = active_event_ids
            self._last_event_state = active_event_state
            self._last_completed_global_tick = tick
            self._next_global_tick = tick + 1
            self._lifecycle = SessionLifecycle.ACTIVE
            return BoundaryResult(
                profile_id=self.profile_id,
                global_tick=tick,
                epoch_id=next_epoch,
                epoch_origin_tick=tick,
                local_tick=0,
                epoch_origin_s=origin_s,
                timestamp_s=origin_s,
                boundary_kind="reset",
                event_ids=self._last_event_ids,
                held_before_id=previous_held_id,
                published_after_id=published_after_id,
                operations=tuple(operations),
                guards=(),
                probes=(),
                wires=tuple(wires),
            )
        except Exception as exc:
            error = self._interrupt_transaction(
                exc,
                fallback_reason="partial_reset",
                global_tick=tick,
                epoch_id=next_epoch,
                epoch_origin_tick=tick,
                local_tick=0,
                epoch_origin_s=origin_s,
                timestamp_s=origin_s,
                boundary_kind="reset",
                event_ids=active_event_ids,
                held_before_id=previous_held_id,
                published_after_id=published_after_id,
                operations=operations,
                guards=(),
                probes=(),
                wires=wires,
            )
            if error is exc:
                raise
            raise error from exc

    def _record_component_rejection(
        self,
        *,
        owner: str,
        call: Callable[[], Any],
        expected_reason: str,
        global_tick: int,
        phase: int,
        operation_id: str,
        inputs: Mapping[str, str],
        scalar_inputs: Mapping[str, Any],
        guard_inputs: Mapping[str, EpochEnvelope],
        guard_log: list[Mapping[str, Any]],
        operations: list[Mapping[str, Any]],
        transition_to_needs_reset: bool = False,
    ) -> None:
        before_snapshot_id = f"{operation_id}/before"
        before_capture_id = f"{before_snapshot_id}/capture"
        before = self.capture_state(before_snapshot_id, before_capture_id)
        attempt_counter = (
            "estimator_process_attempts"
            if owner == "estimator"
            else "controller_step_attempts"
        )
        rejected_counter = (
            "estimator_process_rejected"
            if owner == "estimator"
            else "controller_step_rejected"
        )
        guard_ref = self._guard_inputs(
            guard_inputs,
            consumer=owner,
            global_tick=global_tick,
            phase=phase,
            operation_id=operation_id,
            guard_log=guard_log,
        )
        after_snapshot_id = f"{operation_id}/after"
        after_capture_id = f"{after_snapshot_id}/capture"
        operation_record: dict[str, Any] = {
            "operation_id": operation_id,
            "owner": owner,
            "method": "process" if owner == "estimator" else "step",
            "phase": phase,
            "attempt_kind": "injected_invalid",
            "inputs": dict(inputs),
            "outputs": {},
            "scalar_inputs": dict(scalar_inputs),
            "reset_inputs": None,
            "accepted": False,
            "reason": "component_call_incomplete",
            "guard_ref": guard_ref,
            "before_snapshot_id": before_snapshot_id,
            "before_capture_id": before_capture_id,
            "after_snapshot_id": after_snapshot_id,
            "after_capture_id": after_capture_id,
            "before_snapshot": before,
            "session_transition": (
                "active_to_needs_reset"
                if transition_to_needs_reset
                else None
            ),
        }
        # Retain the actual attempt before entering the component.  If the
        # component raises an unexpected exception, the interrupted frontier
        # must still distinguish "attempted and failed" from "never called".
        operations.append(operation_record)
        self._increment(attempt_counter)
        actual_reason: str | None = None
        component_exception: Exception | None = None
        try:
            result = call()
            if owner == "estimator" and not result.diagnostics.accepted:
                actual_reason = str(result.diagnostics.reason)
            else:
                operation_record["reason"] = "invalid_call_accepted"
                self._terminal("invalid_call_accepted", operation_id)
        except SessionContractError as exc:
            operation_record["reason"] = self._exception_reason(exc)
            raise
        except Exception as exc:
            component_exception = exc
            actual_reason = self._exception_reason(exc)
        operation_record["reason"] = actual_reason
        if actual_reason != expected_reason:
            # Preserve an unexpected DUT exception as the transaction's first
            # cause.  Manufacturing an ``invalid_reason_mismatch`` exception
            # here would erase its concrete type/reason/message before the
            # outer interrupted-transaction journal can retain it.
            if component_exception is not None:
                raise component_exception
            self._terminal(
                "invalid_reason_mismatch",
                f"{operation_id}: expected {expected_reason!r}, got {actual_reason!r}",
            )
        self._increment(rejected_counter)
        if transition_to_needs_reset:
            self._lifecycle = SessionLifecycle.NEEDS_RESET
        after = self.capture_state(after_snapshot_id, after_capture_id)
        operation_record["after_snapshot"] = after
        try:
            if transition_to_needs_reset:
                self._assert_needs_reset_transition(before, after, operation_id)
            else:
                self._assert_same_snapshot(before, after, operation_id)
        except SessionContractError as exc:
            self._terminal(exc.reason, exc.detail)

    def advance(
        self, global_tick: int, *, directive: TickDirective | None = None
    ) -> BoundaryResult:
        """Advance one ordinary global boundary in fixed P/A/I/E/C order."""

        tick = _nonnegative_integer(global_tick, "global_tick")
        if self._lifecycle is SessionLifecycle.NEEDS_RESET:
            raise SessionContractError("needs_reset")
        if self._lifecycle is SessionLifecycle.TERMINAL_INCONCLUSIVE:
            self._raise_terminal_inconclusive()
        if self._lifecycle is not SessionLifecycle.ACTIVE:
            raise SessionContractError("session_not_reset")
        if tick != self._next_global_tick:
            raise SessionContractError(
                "unexpected_boundary",
                "ordinary "
                f"{tick} does not match next boundary {self._next_global_tick}",
            )
        directive = directive or TickDirective()
        if (
            directive.fault is not None
            or directive.preflight_probes
            or directive.pre_estimator_probes
            or directive.pre_controller_probes
            or directive.truth_estimator_probe_id is not None
            or directive.truth_controller_probe_id is not None
            or directive.required_after_imu_snapshot_id is not None
        ) and self._snapshotter is None:
            raise SessionContractError(
                "observer_required",
                "faults, probes, and requested captures require the full observer",
            )
        local_tick = tick - self.epoch_origin_tick
        if local_tick <= 0:
            self._terminal("invalid_local_tick", str(local_tick))
        due = self.scheduler.boundary(local_tick, self.epoch_origin_s)
        if due.local_tick != local_tick:
            self._terminal("scheduler_identity_mismatch")
        if not due.plant_due or not due.actuator_due:
            self._terminal("missing_base_due")
        periodic_flags = (due.imu_due, due.estimator_due, due.controller_due)
        if any(periodic_flags) and not all(periodic_flags):
            self._terminal("misaligned_periodic_due")
        self._assert_event_schedule_binding()
        active = self.event_schedule.active_at(tick)
        if getattr(active, "reset_event", None) is not None:
            raise SessionContractError("reset_boundary_requires_reset")
        self._validate_fault_event(active, directive)
        if directive.fault is not None and not all(periodic_flags):
            self._terminal("fault_not_on_due_boundary", directive.fault)
        if (
            directive.required_after_imu_snapshot_id is not None
            and not all(periodic_flags)
        ):
            self._terminal(
                "required_after_imu_capture_not_on_due_boundary",
                directive.required_after_imu_snapshot_id,
            )
        active_event_ids = tuple(getattr(active, "event_ids", ()))
        active_event_state = self._event_state(active)

        operations: list[Mapping[str, Any]] = []
        guards: list[Mapping[str, Any]] = []
        probes: list[Mapping[str, Any]] = []
        wires: list[EpochEnvelope] = []
        held_before = self.held_envelope
        feedback_before = self.feedback_envelope
        published: EpochEnvelope | None = None
        required_after_imu_capture: ObserverCapture | None = None
        self._pending_event_state = active_event_state
        self._phase_cursor = 1

        def interrupted_error(exc: Exception) -> SessionContractError:
            return self._interrupt_transaction(
                exc,
                fallback_reason="component_failure",
                global_tick=tick,
                epoch_id=self.epoch_id,
                epoch_origin_tick=self.epoch_origin_tick,
                local_tick=local_tick,
                epoch_origin_s=self.epoch_origin_s,
                timestamp_s=due.timestamp_s,
                boundary_kind="ordinary",
                event_ids=active_event_ids,
                held_before_id=held_before.envelope_id,
                published_after_id=(
                    None if published is None else published.envelope_id
                ),
                operations=operations,
                guards=guards,
                probes=probes,
                wires=wires,
                required_after_imu_capture=required_after_imu_capture,
            )

        try:
            plant_op = self._operation_id(tick, 1, "plant-step")
            plant_guard_ref = self._guard_inputs(
                {"feedback": feedback_before},
                consumer="plant",
                global_tick=tick,
                phase=1,
                operation_id=plant_op,
                guard_log=guards,
            )
            external = _vector(
                active.external_torque_body_Nm,
                3,
                "external_torque_body_Nm",
            )
            total_torque = feedback_before.payload.actual_torque_body_Nm + external
            plant_operation: dict[str, Any] = {
                "operation_id": plant_op,
                "owner": "plant",
                "method": "step_base",
                "phase": 1,
                "attempt_kind": "normal",
                "inputs": {"feedback": feedback_before.envelope_id},
                "outputs": {},
                "scalar_inputs": {
                    "dt_s": self.scheduler.base_period_s,
                    "external_torque_body_Nm": external,
                    "total_plant_torque_body_Nm": total_torque,
                    "interval_start_tick": tick - 1,
                    "interval_end_tick": tick,
                },
                "reset_inputs": None,
                "accepted": False,
                "reason": "component_call_incomplete",
                "guard_ref": plant_guard_ref,
            }
            operations.append(plant_operation)
            self._increment("plant_step_attempts")
            try:
                plant_payload = self.plant.step_base(total_torque)
            except Exception as exc:
                plant_operation["reason"] = self._exception_reason(exc)
                raise
            plant_state = self._new_envelope(
                role="plant_state",
                payload=plant_payload,
                global_tick=tick,
                local_tick=local_tick,
                phase=1,
                producer="plant",
                producer_operation_id=plant_op,
                parent_ids=(feedback_before.envelope_id,),
            )
            wires.append(plant_state)
            self._pending_inputs = (plant_state,)
            plant_operation["outputs"] = {
                "plant_state": plant_state.envelope_id
            }
            plant_operation["accepted"] = True
            plant_operation["reason"] = "accepted"

            self._phase_cursor = 2
            actuator_op = self._operation_id(tick, 2, "actuator-step")
            self._run_probes(
                directive.preflight_probes,
                global_tick=tick,
                phase=2,
                operation_id=actuator_op,
                guard_log=guards,
                probe_log=probes,
                legal_by_role={"held_torque": held_before},
            )
            actuator_guard_ref = self._guard_inputs(
                {"held_torque": held_before},
                consumer="actuator",
                global_tick=tick,
                phase=2,
                operation_id=actuator_op,
                guard_log=guards,
            )
            actuator_operation: dict[str, Any] = {
                "operation_id": actuator_op,
                "owner": "actuator",
                "method": "step_base",
                "phase": 2,
                "attempt_kind": "normal",
                "inputs": {"torque_command": held_before.envelope_id},
                "outputs": {},
                "scalar_inputs": {
                    "dt_s": self.scheduler.base_period_s,
                    "interval_start_tick": tick - 1,
                    "interval_end_tick": tick,
                },
                "reset_inputs": None,
                "accepted": False,
                "reason": "component_call_incomplete",
                "guard_ref": actuator_guard_ref,
            }
            operations.append(actuator_operation)
            self._increment("actuator_step_attempts")
            try:
                feedback_payload, delegate_operation = (
                    self._observed_actuator_step_base(
                        held_before,
                        operation_id=actuator_op,
                        operations=operations,
                    )
                )
            except Exception as exc:
                actuator_operation["reason"] = self._exception_reason(exc)
                raise
            feedback = self._new_envelope(
                role="feedback",
                payload=feedback_payload,
                global_tick=tick,
                local_tick=local_tick,
                phase=2,
                producer="actuator",
                producer_operation_id=actuator_op,
                parent_ids=(held_before.envelope_id,),
            )
            wires.append(feedback)
            self._pending_inputs = (*self._pending_inputs, feedback)
            delegate_operation["outputs"] = {
                "feedback": feedback.envelope_id
            }
            actuator_operation["outputs"] = {
                "feedback": feedback.envelope_id
            }
            actuator_operation["accepted"] = True
            actuator_operation["reason"] = "accepted"
        except Exception as exc:
            error = interrupted_error(exc)
            if error is exc:
                raise
            raise error from exc

        if all(periodic_flags):
            try:
                self._phase_cursor = 3
                imu_op = self._operation_id(tick, 3, "imu-sample")
                truth_payload = self.simulation.SensorTruth(
                    plant_payload.q_nb,
                    plant_payload.omega_b_rad_s,
                    np.zeros(3, dtype=np.float64),
                )
                truth = self._new_envelope(
                    role="sensor_truth",
                    payload=truth_payload,
                    global_tick=tick,
                    local_tick=local_tick,
                    phase=3,
                    producer="plant_truth_boundary",
                    producer_operation_id=imu_op,
                    parent_ids=(plant_state.envelope_id,),
                )
                # The real IMU input exists before either its guard or sample
                # can fail.  Retain it immediately so the failure frontier can
                # resolve the operation's consumed reference without inventing
                # a sample output.
                wires.append(truth)
                self._pending_inputs = (*self._pending_inputs, truth)
                imu_guard_ref = self._guard_inputs(
                    {"sensor_truth": truth},
                    consumer="imu",
                    global_tick=tick,
                    phase=3,
                    operation_id=imu_op,
                    guard_log=guards,
                )
                imu_operation: dict[str, Any] = {
                    "operation_id": imu_op,
                    "owner": "imu",
                    "method": "sample",
                    "phase": 3,
                    "attempt_kind": "normal",
                    "inputs": {"sensor_truth": truth.envelope_id},
                    "outputs": {},
                    "scalar_inputs": {
                        "timestamp_s": due.timestamp_s,
                        "translational_acceleration_n_m_s2": (
                            truth_payload.acceleration_n_m_s2
                        ),
                    },
                    "reset_inputs": None,
                    "accepted": False,
                    "reason": "component_call_incomplete",
                    "guard_ref": imu_guard_ref,
                }
                operations.append(imu_operation)
                self._increment("imu_sample_attempts")
                try:
                    raw_payload = self.imu.sample(
                        truth_payload, due.timestamp_s
                    )
                except Exception as exc:
                    imu_operation["reason"] = self._exception_reason(exc)
                    raise
                raw_sample = self._new_envelope(
                    role="imu",
                    payload=raw_payload,
                    global_tick=tick,
                    local_tick=local_tick,
                    phase=3,
                    producer="imu",
                    producer_operation_id=imu_op,
                    parent_ids=(truth.envelope_id,),
                )
                wires.append(raw_sample)
                self._pending_inputs = (*self._pending_inputs, raw_sample)
                imu_operation["outputs"] = {
                    "raw_imu": raw_sample.envelope_id
                }
                imu_operation["accepted"] = True
                imu_operation["reason"] = "accepted"

                if directive.required_after_imu_snapshot_id is not None:
                    required_snapshot_id = (
                        directive.required_after_imu_snapshot_id
                    )
                    required_capture_id = f"{required_snapshot_id}/capture"
                    captured = self.capture_state(
                        required_snapshot_id, required_capture_id
                    )
                    required_after_imu_capture = ObserverCapture(
                        snapshot_id=required_snapshot_id,
                        capture_id=required_capture_id,
                        phase=3,
                        functional_state=_freeze_frontier_value(captured),
                    )

                adapter_op = self._operation_id(tick, 3, "measurement-adapter")
                adapter_guard_ref = self._guard_inputs(
                    {"imu": raw_sample},
                    consumer="measurement_adapter",
                    global_tick=tick,
                    phase=3,
                    operation_id=adapter_op,
                    guard_log=guards,
                )
                adapter_operation: dict[str, Any] = {
                    "operation_id": adapter_op,
                    "owner": "measurement_adapter",
                    "method": "adapt_measurement",
                    "phase": 3,
                    "attempt_kind": "normal",
                    "inputs": {"raw_imu": raw_sample.envelope_id},
                    "outputs": {},
                    "scalar_inputs": {},
                    "reset_inputs": None,
                    "accepted": False,
                    "reason": "component_call_incomplete",
                    "guard_ref": adapter_guard_ref,
                }
                operations.append(adapter_operation)
                try:
                    self._assert_event_schedule_binding()
                    gyro, force = self.event_schedule.adapt_measurement(
                        raw_payload.gyro_b_rad_s,
                        raw_payload.specific_force_b_m_s2,
                        active,
                        self.g1_parameters.gyro_bias_rad_s,
                        self.g1_parameters.accelerometer_bias_m_s2,
                    )
                except Exception as exc:
                    adapter_operation["reason"] = self._exception_reason(exc)
                    raise
                adapted_payload = self.simulation.IMUSample(
                    raw_payload.timestamp_s, gyro, force, raw_payload.valid
                )
                sample = self._new_envelope(
                    role="imu",
                    payload=adapted_payload,
                    global_tick=tick,
                    local_tick=local_tick,
                    phase=3,
                    producer="measurement_adapter",
                    producer_operation_id=adapter_op,
                    parent_ids=(raw_sample.envelope_id,),
                )
                wires.append(sample)
                self._pending_inputs = (*self._pending_inputs, sample)
                adapter_operation["outputs"] = {
                    "adapted_imu": sample.envelope_id
                }
                adapter_operation["accepted"] = True
                adapter_operation["reason"] = "accepted"

                self._phase_cursor = 4
                estimator_op = self._operation_id(tick, 4, "estimator-process")
                derived_estimator_probes: tuple[GuardProbe, ...] = ()
                if directive.truth_estimator_probe_id is not None:
                    contaminated_sample_payload = self.simulation.IMUSample(
                        sample.payload.timestamp_s,
                        truth.payload.omega_b_rad_s,
                        sample.payload.specific_force_b_m_s2,
                        sample.payload.valid,
                    )
                    contaminated_sample = self._new_envelope(
                        role="imu",
                        payload=contaminated_sample_payload,
                        global_tick=tick,
                        local_tick=local_tick,
                        phase=4,
                        producer="evaluator_truth",
                        producer_operation_id=None,
                        parent_ids=(truth.envelope_id, sample.envelope_id),
                    )
                    wires.append(contaminated_sample)
                    derived_estimator_probes = (
                        GuardProbe(
                            probe_id=directive.truth_estimator_probe_id,
                            kind="truth_negative",
                            envelope=contaminated_sample,
                            expected_role="imu",
                            consumer="estimator",
                            expected_reason="truth_dependency_forbidden",
                            original_legal_id=sample.envelope_id,
                            source_truth_id=truth.envelope_id,
                            source_field="sensor_truth.omega_b_rad_s",
                            target_field="imu.gyro_rad_s",
                            derivation_site=(
                                "integration_session.phase4."
                                "derive_imu_gyro_from_evaluator_truth"
                            ),
                        ),
                    )
                self._run_probes(
                    (*directive.pre_estimator_probes, *derived_estimator_probes),
                    global_tick=tick,
                    phase=4,
                    operation_id=estimator_op,
                    guard_log=guards,
                    probe_log=probes,
                    legal_by_role={"imu": sample},
                )
                if directive.fault == FAULT_ESTIMATOR_STALE_TIMESTAMP:
                    if self._last_sample is None:
                        self._terminal("stale_fixture_unavailable")
                    invalid_estimator_op = self._operation_id(
                        tick, 4, "estimator-stale-timestamp"
                    )
                    stale_payload = self.simulation.IMUSample(
                        self._last_sample.payload.timestamp_s,
                        sample.payload.gyro_b_rad_s,
                        sample.payload.specific_force_b_m_s2,
                        sample.payload.valid,
                    )
                    stale = self._new_envelope(
                        role="imu",
                        payload=stale_payload,
                        global_tick=tick,
                        local_tick=local_tick,
                        phase=4,
                        producer="fault_injector",
                        producer_operation_id=invalid_estimator_op,
                        parent_ids=(sample.envelope_id, self._last_sample.envelope_id),
                    )
                    wires.append(stale)
                    self._record_component_rejection(
                        owner="estimator",
                        call=lambda: self.estimator.process(stale_payload),
                        expected_reason="imu sample timestamp is duplicate or stale",
                        global_tick=tick,
                        phase=4,
                        operation_id=invalid_estimator_op,
                        inputs={"adapted_imu": stale.envelope_id},
                        scalar_inputs={},
                        guard_inputs={"imu": stale},
                        guard_log=guards,
                        operations=operations,
                    )
                    estimator_guard_ref = self._guard_inputs(
                        {"imu": sample},
                        consumer="estimator",
                        global_tick=tick,
                        phase=4,
                        operation_id=estimator_op,
                        guard_log=guards,
                    )
                    estimator_attempt_kind = "same_tick_correction"
                else:
                    estimator_guard_ref = self._guard_inputs(
                        {"imu": sample},
                        consumer="estimator",
                        global_tick=tick,
                        phase=4,
                        operation_id=estimator_op,
                        guard_log=guards,
                    )
                    estimator_attempt_kind = "normal"
                estimator_operation: dict[str, Any] = {
                    "operation_id": estimator_op,
                    "owner": "estimator",
                    "method": "process",
                    "phase": 4,
                    "attempt_kind": estimator_attempt_kind,
                    "inputs": {"adapted_imu": sample.envelope_id},
                    "outputs": {},
                    "scalar_inputs": {},
                    "reset_inputs": None,
                    "accepted": False,
                    "reason": "component_call_incomplete",
                    "guard_ref": estimator_guard_ref,
                }
                operations.append(estimator_operation)
                self._increment("estimator_process_attempts")
                try:
                    estimator_result = self.estimator.process(sample.payload)
                except Exception as exc:
                    estimator_operation["reason"] = self._exception_reason(exc)
                    raise
                if not estimator_result.diagnostics.accepted:
                    self._increment("estimator_process_rejected")
                    estimator_operation["reason"] = str(
                        estimator_result.diagnostics.reason
                    )
                    self._terminal(
                        "unexpected_estimator_rejection",
                        str(estimator_result.diagnostics.reason),
                    )
                self._increment("estimator_process_accepted")
                estimate = self._new_envelope(
                    role="estimate",
                    payload=estimator_result.estimate,
                    global_tick=tick,
                    local_tick=local_tick,
                    phase=4,
                    producer="estimator",
                    producer_operation_id=estimator_op,
                    parent_ids=(sample.envelope_id,),
                )
                estimator_diagnostics = self._new_envelope(
                    role="estimator_diagnostics",
                    payload=estimator_result.diagnostics,
                    global_tick=tick,
                    local_tick=local_tick,
                    phase=4,
                    producer="estimator",
                    producer_operation_id=estimator_op,
                    parent_ids=(sample.envelope_id,),
                )
                wires.extend((estimate, estimator_diagnostics))
                self._pending_inputs = (
                    *self._pending_inputs,
                    estimate,
                    estimator_diagnostics,
                )
                estimator_operation["outputs"] = {
                    "estimate": estimate.envelope_id,
                    "estimator_diagnostics": estimator_diagnostics.envelope_id,
                }
                estimator_operation["accepted"] = True
                estimator_operation["reason"] = "accepted"

                self._phase_cursor = 5
                controller_op = self._operation_id(tick, 5, "controller-step")
                command_payload = self.command_factory(
                    active.command_q_nb, due.timestamp_s, True
                )
                command = self._new_envelope(
                    role="attitude_command",
                    payload=command_payload,
                    global_tick=tick,
                    local_tick=local_tick,
                    phase=5,
                    producer="command_sampler",
                    producer_operation_id=None,
                    parent_ids=(),
                )
                wires.append(command)
                self._pending_inputs = (*self._pending_inputs, command)
                derived_controller_probes: tuple[GuardProbe, ...] = ()
                if directive.truth_controller_probe_id is not None:
                    contaminated_estimate_payload = self.estimator_types.StateEstimate(
                        truth.payload.q_nb,
                        estimate.payload.omega_b_estimate_rad_s,
                        estimate.payload.timestamp_s,
                        estimate.payload.valid,
                    )
                    contaminated_estimate = self._new_envelope(
                        role="estimate",
                        payload=contaminated_estimate_payload,
                        global_tick=tick,
                        local_tick=local_tick,
                        phase=5,
                        producer="evaluator_truth",
                        producer_operation_id=None,
                        parent_ids=(truth.envelope_id, estimate.envelope_id),
                    )
                    wires.append(contaminated_estimate)
                    derived_controller_probes = (
                        GuardProbe(
                            probe_id=directive.truth_controller_probe_id,
                            kind="truth_negative",
                            envelope=contaminated_estimate,
                            expected_role="estimate",
                            consumer="controller",
                            expected_reason="truth_dependency_forbidden",
                            original_legal_id=estimate.envelope_id,
                            source_truth_id=truth.envelope_id,
                            source_field="sensor_truth.q_nb",
                            target_field="estimate.q_nb",
                            derivation_site=(
                                "integration_session.phase5."
                                "derive_estimate_q_from_evaluator_truth"
                            ),
                        ),
                    )
                self._run_probes(
                    (*directive.pre_controller_probes, *derived_controller_probes),
                    global_tick=tick,
                    phase=5,
                    operation_id=controller_op,
                    guard_log=guards,
                    probe_log=probes,
                    legal_by_role={
                        "feedback": feedback,
                        "estimate": estimate,
                        "attitude_command": command,
                    },
                )
                controller_inputs = {
                    "attitude_command": command,
                    "estimate": estimate,
                    "feedback": feedback,
                }
                controller_period = (
                    self.scheduler.controller_every_ticks
                    * self.scheduler.base_period_s
                )
                controller_attempt_kind = "normal"
                skip_normal_controller = False
                controller_guard_ref: str | None = None
                if directive.fault == FAULT_CONTROLLER_NEGATIVE_DT:
                    invalid_controller_op = self._operation_id(
                        tick, 5, "controller-negative-dt"
                    )
                    self._record_component_rejection(
                        owner="controller",
                        call=lambda: self.controller.step(
                            command.payload,
                            estimate.payload,
                            feedback.payload,
                            -controller_period,
                        ),
                        expected_reason="invalid_dt",
                        global_tick=tick,
                        phase=5,
                        operation_id=invalid_controller_op,
                        inputs={
                            "attitude_command": command.envelope_id,
                            "estimate": estimate.envelope_id,
                            "feedback": feedback.envelope_id,
                        },
                        scalar_inputs={"dt_s": -controller_period},
                        guard_inputs=controller_inputs,
                        guard_log=guards,
                        operations=operations,
                    )
                    controller_guard_ref = self._guard_inputs(
                        controller_inputs,
                        consumer="controller",
                        global_tick=tick,
                        phase=5,
                        operation_id=controller_op,
                        guard_log=guards,
                    )
                    controller_attempt_kind = "same_tick_correction"
                elif directive.fault == FAULT_CONTROLLER_UNEXPECTED_TICK:
                    invalid_controller_op = self._operation_id(
                        tick, 5, "controller-unexpected-tick"
                    )
                    future_command_payload = self.command_factory(
                        active.command_q_nb,
                        due.timestamp_s + controller_period,
                        True,
                    )
                    future_command = self._new_envelope(
                        role="attitude_command",
                        payload=future_command_payload,
                        global_tick=tick,
                        local_tick=local_tick,
                        phase=5,
                        producer="fault_injector",
                        producer_operation_id=None,
                        parent_ids=(command.envelope_id,),
                    )
                    wires.append(future_command)
                    invalid_controller_inputs = {
                        "attitude_command": future_command,
                        "estimate": estimate,
                        "feedback": feedback,
                    }
                    self._record_component_rejection(
                        owner="controller",
                        call=lambda: self.controller.step(
                            future_command.payload,
                            estimate.payload,
                            feedback.payload,
                            controller_period,
                        ),
                        expected_reason="unexpected_tick",
                        global_tick=tick,
                        phase=5,
                        operation_id=invalid_controller_op,
                        inputs={
                            "attitude_command": future_command.envelope_id,
                            "estimate": estimate.envelope_id,
                            "feedback": feedback.envelope_id,
                        },
                        scalar_inputs={"dt_s": controller_period},
                        guard_inputs=invalid_controller_inputs,
                        guard_log=guards,
                        operations=operations,
                        transition_to_needs_reset=True,
                    )
                    skip_normal_controller = True
                else:
                    controller_guard_ref = self._guard_inputs(
                        controller_inputs,
                        consumer="controller",
                        global_tick=tick,
                        phase=5,
                        operation_id=controller_op,
                        guard_log=guards,
                    )
                if not skip_normal_controller:
                    if controller_guard_ref is None:
                        self._terminal("missing_guard_ref", controller_op)
                    controller_operation: dict[str, Any] = {
                        "operation_id": controller_op,
                        "owner": "controller",
                        "method": "step",
                        "phase": 5,
                        "attempt_kind": controller_attempt_kind,
                        "inputs": {
                            "attitude_command": command.envelope_id,
                            "estimate": estimate.envelope_id,
                            "feedback": feedback.envelope_id,
                        },
                        "outputs": {},
                        "scalar_inputs": {"dt_s": controller_period},
                        "reset_inputs": None,
                        "accepted": False,
                        "reason": "component_call_incomplete",
                        "guard_ref": controller_guard_ref,
                    }
                    operations.append(controller_operation)
                    self._increment("controller_step_attempts")
                    try:
                        output_payload = self.controller.step(
                            command.payload,
                            estimate.payload,
                            feedback.payload,
                            controller_period,
                        )
                    except Exception as exc:
                        controller_operation["reason"] = (
                            self._exception_reason(exc)
                        )
                        raise
                    self._increment("controller_step_accepted")
                    controller_operation["accepted"] = True
                    controller_operation["reason"] = "accepted"
                    output = self._new_envelope(
                        role="held_torque",
                        payload=output_payload,
                        global_tick=tick,
                        local_tick=local_tick,
                        phase=5,
                        producer="controller",
                        producer_operation_id=controller_op,
                        parent_ids=(
                            command.envelope_id,
                            estimate.envelope_id,
                            feedback.envelope_id,
                        ),
                    )
                    wires.append(output)
                    controller_outputs: dict[str, str] = {
                        "torque_command": output.envelope_id
                    }
                    controller_operation["outputs"] = controller_outputs
                    diagnostics_getter = getattr(
                        getattr(self.controller, "core", None),
                        "last_diagnostics",
                        None,
                    )
                    if callable(diagnostics_getter):
                        diagnostics = self._new_envelope(
                            role="controller_diagnostics",
                            payload=diagnostics_getter(),
                            global_tick=tick,
                            local_tick=local_tick,
                            phase=5,
                            producer="controller",
                            producer_operation_id=controller_op,
                            parent_ids=(output.envelope_id,),
                        )
                        wires.append(diagnostics)
                        controller_outputs[
                            "controller_diagnostics"
                        ] = diagnostics.envelope_id
                    self._phase_cursor = 6
                    publish_op = self._operation_id(tick, 6, "publish")
                    self._pending_publication = output
                    published = output
                    operations.append(
                        {
                            "operation_id": publish_op,
                            "owner": "session",
                            "method": "publish",
                            "phase": 6,
                            "attempt_kind": "publication",
                            "inputs": {"torque_command": output.envelope_id},
                            "outputs": {"torque_command": output.envelope_id},
                            "scalar_inputs": {},
                            "reset_inputs": None,
                            "accepted": True,
                            "reason": "accepted",
                            "guard_ref": None,
                        }
                    )
            except Exception as exc:
                error = interrupted_error(exc)
                if error is exc:
                    raise
                raise error from exc

        try:
            self._feedback = feedback
            self._last_plant_state = plant_state
            self._last_event_ids = active_event_ids
            self._last_event_state = active_event_state
            if all(periodic_flags):
                self._last_raw_sample = raw_sample
                self._last_sample = sample
                self._last_estimate = estimate
                self._last_command = command
                self._last_truth = truth
                if published is not None:
                    self._held = published
            self._pending_publication = None
            self._pending_inputs = ()
            self._pending_event_state = None
            self._last_completed_global_tick = tick
            self._next_global_tick = tick + 1
            return BoundaryResult(
                profile_id=self.profile_id,
                global_tick=tick,
                epoch_id=self.epoch_id,
                epoch_origin_tick=self.epoch_origin_tick,
                local_tick=local_tick,
                epoch_origin_s=self.epoch_origin_s,
                timestamp_s=due.timestamp_s,
                boundary_kind="ordinary",
                event_ids=active_event_ids,
                held_before_id=held_before.envelope_id,
                published_after_id=(
                    None if published is None else published.envelope_id
                ),
                operations=tuple(operations),
                guards=tuple(guards),
                probes=tuple(probes),
                wires=tuple(wires),
                required_after_imu_capture=required_after_imu_capture,
            )
        except Exception as exc:
            error = interrupted_error(exc)
            if error is exc:
                raise
            raise error from exc


__all__ = [
    "BoundaryResult",
    "EpochEnvelope",
    "FAULT_CONTROLLER_NEGATIVE_DT",
    "FAULT_CONTROLLER_UNEXPECTED_TICK",
    "FAULT_ESTIMATOR_STALE_TIMESTAMP",
    "GuardedInput",
    "GuardProbe",
    "IntegrationSession",
    "LifecycleCallToken",
    "LifecycleRecorder",
    "ObserverCapture",
    "ResetEpochView",
    "SessionContractError",
    "SessionLifecycle",
    "TickDirective",
    "canonical_snapshot_bytes",
    "canonical_snapshot_value",
    "float64_hex",
    "guard_envelope",
    "guard_input_bundle",
]
