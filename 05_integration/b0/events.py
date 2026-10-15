"""Pure, fail-closed adapters for approved B0 G3 scenario events."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

import numpy as np


class EventContractError(ValueError):
    """Raised when an event set or adapter input violates the frozen contract."""


@dataclass(frozen=True)
class ActiveEvents:
    command_q_nb: np.ndarray
    external_torque_body_Nm: np.ndarray
    imu_bias: Mapping[str, Any] | None
    specific_force_body_m_s2: np.ndarray
    invalid_event: Mapping[str, Any] | None
    reset_event: Mapping[str, Any] | None
    event_ids: tuple[str, ...]


def _qx(angle: float) -> np.ndarray:
    return np.array([math.cos(angle / 2.0), math.sin(angle / 2.0), 0.0, 0.0])


def _qy(angle: float) -> np.ndarray:
    return np.array([math.cos(angle / 2.0), 0.0, math.sin(angle / 2.0), 0.0])


def _qz(angle: float) -> np.ndarray:
    return np.array([math.cos(angle / 2.0), 0.0, 0.0, math.sin(angle / 2.0)])


def _multiply(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    lw, lx, ly, lz = left
    rw, rx, ry, rz = right
    return np.array(
        [
            lw * rw - lx * rx - ly * ry - lz * rz,
            lw * rx + lx * rw + ly * rz - lz * ry,
            lw * ry - lx * rz + ly * rw + lz * rx,
            lw * rz + lx * ry - ly * rx + lz * rw,
        ]
    )


def _vector(event: Mapping[str, Any], field: str) -> np.ndarray:
    value = np.asarray(event[field], dtype=np.float64)
    if value.shape != (3,) or not np.all(np.isfinite(value)):
        raise EventContractError(f"{event.get('id', '<unknown>')}.{field} must be finite length three")
    return value


class EventSchedule:
    """Validated declaration-order schedule with half-open endpoints."""

    _KNOWN_TYPES = {
        "command_step",
        "external_torque",
        "imu_bias",
        "specific_force_disturbance",
        "invalid_input",
        "reset",
    }

    def __init__(self, events: Iterable[Mapping[str, Any]]) -> None:
        self._events = tuple(dict(event) for event in events)
        previous_start = -1
        seen_ids: set[str] = set()
        for event in self._events:
            try:
                event_id = event["id"]
                event_type = event["type"]
                start = event["start_tick"]
                end = event["end_tick"]
            except KeyError as exc:
                raise EventContractError(f"event missing field: {exc}") from exc
            if not isinstance(event_id, str) or not event_id or event_id in seen_ids:
                raise EventContractError("event IDs must be unique non-empty strings")
            if event_type not in self._KNOWN_TYPES:
                raise EventContractError(f"unsupported event type: {event_type}")
            if any(isinstance(value, bool) or not isinstance(value, int) for value in (start, end)):
                raise EventContractError(f"{event_id} endpoints must be integers")
            if start < 0 or end <= start:
                raise EventContractError(f"{event_id} requires 0 <= start_tick < end_tick")
            if start < previous_start:
                raise EventContractError("events must be declared in nondecreasing start order")
            previous_start = start
            seen_ids.add(event_id)
            self._validate_payload(event)
        for index, left in enumerate(self._events):
            for right in self._events[index + 1 :]:
                if max(left["start_tick"], right["start_tick"]) < min(
                    left["end_tick"], right["end_tick"]
                ):
                    raise EventContractError(
                        f"overlap is not approved: {left['id']} and {right['id']}"
                    )

    @staticmethod
    def _validate_payload(event: Mapping[str, Any]) -> None:
        event_type = event["type"]
        if event_type == "command_step":
            if event.get("axis") not in {"x", "y", "z"}:
                raise EventContractError("command_step axis must be x, y or z")
            value = event.get("value_rad")
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise EventContractError("command_step value_rad must be finite")
            if event.get("post_event_action") != "return_axis_to_zero":
                raise EventContractError("command_step must return its axis to zero")
        elif event_type == "external_torque":
            _vector(event, "vector_Nm")
        elif event_type == "imu_bias":
            _vector(event, "gyro_bias_rad_s")
            _vector(event, "accelerometer_bias_m_s2")
            if event.get("application") != "replace_nominal_bias":
                raise EventContractError("imu_bias must replace the nominal bias")
        elif event_type == "specific_force_disturbance":
            _vector(event, "vector_m_s2")
            if event.get("application") != "additive_to_nominal_specific_force":
                raise EventContractError("specific-force disturbance must be additive")
        elif event_type == "invalid_input":
            if event.get("invalid_kind") not in {"negative_dt", "stale_timestamp"}:
                raise EventContractError("unsupported invalid input kind")
        elif event_type == "reset" and event.get("target") != "all_components":
            raise EventContractError("reset target must be all_components")

    def active_at(self, global_tick: int) -> ActiveEvents:
        if isinstance(global_tick, bool) or not isinstance(global_tick, int) or global_tick < 0:
            raise EventContractError("global_tick must be a non-negative integer")
        active = tuple(
            event
            for event in self._events
            if event["start_tick"] <= global_tick < event["end_tick"]
        )
        axes = {"x": 0.0, "y": 0.0, "z": 0.0}
        external = np.zeros(3)
        force = np.zeros(3)
        bias = None
        invalid = None
        reset = None
        for event in active:
            event_type = event["type"]
            if event_type == "command_step":
                axes[event["axis"]] = float(event["value_rad"])
            elif event_type == "external_torque":
                external = _vector(event, "vector_Nm")
            elif event_type == "imu_bias":
                bias = event
            elif event_type == "specific_force_disturbance":
                force = _vector(event, "vector_m_s2")
            elif event_type == "invalid_input":
                invalid = event
            elif event_type == "reset":
                reset = event
        command = _multiply(_multiply(_qx(axes["x"]), _qy(axes["y"])), _qz(axes["z"]))
        return ActiveEvents(
            command_q_nb=command,
            external_torque_body_Nm=external,
            imu_bias=bias,
            specific_force_body_m_s2=force,
            invalid_event=invalid,
            reset_event=reset,
            event_ids=tuple(event["id"] for event in active),
        )

    @staticmethod
    def adapt_measurement(
        raw_gyro_b_rad_s: Any,
        raw_specific_force_b_m_s2: Any,
        active: ActiveEvents,
        nominal_gyro_bias_rad_s: Any,
        nominal_accelerometer_bias_m_s2: Any,
    ) -> tuple[np.ndarray, np.ndarray]:
        gyro = np.asarray(raw_gyro_b_rad_s, dtype=np.float64).copy()
        force = np.asarray(raw_specific_force_b_m_s2, dtype=np.float64).copy()
        if gyro.shape != (3,) or force.shape != (3,):
            raise EventContractError("raw IMU values must be length three")
        if active.imu_bias is not None:
            gyro = (
                gyro
                - np.asarray(nominal_gyro_bias_rad_s, dtype=np.float64)
                + _vector(active.imu_bias, "gyro_bias_rad_s")
            )
            force = (
                force
                - np.asarray(nominal_accelerometer_bias_m_s2, dtype=np.float64)
                + _vector(active.imu_bias, "accelerometer_bias_m_s2")
            )
        force += active.specific_force_body_m_s2
        return gyro, force


__all__ = ["ActiveEvents", "EventContractError", "EventSchedule"]
