"""Fake-only contract tests for the G3-A epoch-owning integration session.

These tests intentionally construct no production component, extension module,
configuration loader, random generator, or scenario runner.  Their purpose is
to pin the session's ordering, lifecycle, guard, and snapshot mechanics before
the separately authorized real-component evidence batch.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from types import MappingProxyType, SimpleNamespace
from typing import Any, Mapping

import numpy as np
import pytest

import g3a_evidence_driver as evidence_driver
from integration_session import (
    EpochEnvelope,
    FAULT_CONTROLLER_NEGATIVE_DT,
    FAULT_CONTROLLER_UNEXPECTED_TICK,
    FAULT_ESTIMATOR_STALE_TIMESTAMP,
    GuardProbe,
    IntegrationSession,
    LifecycleRecorder,
    SessionContractError,
    SessionLifecycle,
    TickDirective,
    canonical_snapshot_bytes,
    canonical_snapshot_value,
    float64_hex,
    guard_envelope,
)


IDENTITY = np.array([1.0, 0.0, 0.0, 0.0])
ZERO3 = np.zeros(3)
INITIAL_ACTUAL = np.array([0.003, -0.004, 0.005])
DUMMY_SHA = "a" * 64
REQUIRED_OPERATION_FIELDS = {
    "operation_id",
    "owner",
    "method",
    "phase",
    "attempt_kind",
    "inputs",
    "outputs",
    "scalar_inputs",
    "reset_inputs",
    "accepted",
    "reason",
    "guard_ref",
}


@dataclass(frozen=True)
class FakePlantInitialState:
    q_nb: np.ndarray
    omega_b_rad_s: np.ndarray


@dataclass(frozen=True)
class FakePlantState:
    q_nb: np.ndarray
    omega_b_rad_s: np.ndarray
    timestamp_s: float


@dataclass(frozen=True)
class FakeTorqueCommand:
    requested_torque_body_Nm: np.ndarray
    limited_torque_body_Nm: np.ndarray
    timestamp_s: float
    saturated: np.ndarray


@dataclass(frozen=True)
class FakeActuatorInitialState:
    actual_torque_body_Nm: np.ndarray
    held_limited_torque_body_Nm: np.ndarray
    held_command_timestamp_s: float
    held_saturated: np.ndarray
    held_requested_torque_body_Nm: np.ndarray


@dataclass(frozen=True)
class FakeFeedback:
    actual_torque_body_Nm: np.ndarray
    limited_torque_body_Nm: np.ndarray
    saturated: np.ndarray
    timestamp_s: float
    command_timestamp_s: float


@dataclass(frozen=True)
class FakeIMUInitialState:
    pass


@dataclass(frozen=True)
class FakeTruth:
    q_nb: np.ndarray
    omega_b_rad_s: np.ndarray
    acceleration_n_m_s2: np.ndarray


@dataclass(frozen=True)
class FakeIMUSample:
    timestamp_s: float
    gyro_b_rad_s: np.ndarray
    specific_force_b_m_s2: np.ndarray
    valid: bool


@dataclass(frozen=True)
class FakeEstimatorInitialState:
    q_nb: np.ndarray
    omega_b_rad_s: np.ndarray


@dataclass(frozen=True)
class FakeResetEpoch:
    id: int
    timestamp_s: float


@dataclass(frozen=True)
class FakeEstimate:
    q_nb_estimate: np.ndarray
    omega_b_estimate_rad_s: np.ndarray
    timestamp_s: float
    valid: bool = True


@dataclass(frozen=True)
class FakeDiagnostics:
    accepted: bool
    reason: str
    correction_eligible: bool = False
    correction_applied: bool = False
    correction_capped: bool = False
    elapsed_periods: int = 1
    missing_periods: int = 0
    gap_approximated: bool = False


@dataclass(frozen=True)
class FakeCommand:
    q_nb_command: np.ndarray
    timestamp_s: float
    valid: bool


class FakeControllerError(ValueError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"{reason}: fake rejection")


class FakeScheduler:
    base_period_s = 0.0025
    controller_every_ticks = 2

    @staticmethod
    def boundary(local_tick: int, epoch_origin_s: float) -> Any:
        due = local_tick > 0 and local_tick % 2 == 0
        return SimpleNamespace(
            local_tick=local_tick,
            timestamp_s=epoch_origin_s + local_tick * 0.0025,
            plant_due=local_tick > 0,
            actuator_due=local_tick > 0,
            imu_due=due,
            estimator_due=due,
            controller_due=due,
        )


class FakeEvents:
    def __init__(
        self,
        *,
        reset_ticks: tuple[int, ...] = (),
        invalid_by_tick: dict[int, str] | None = None,
        event_records: tuple[Mapping[str, Any], ...] = (),
    ) -> None:
        events = [dict(event) for event in event_records]
        events.extend(
            {
                "id": f"invalid-{tick}",
                "type": "invalid_input",
                "start_tick": tick,
                "end_tick": tick + 1,
                "invalid_kind": invalid_kind,
            }
            for tick, invalid_kind in (invalid_by_tick or {}).items()
        )
        events.extend(
            {
                "id": f"reset-{tick}",
                "type": "reset",
                "start_tick": tick,
                "end_tick": tick + 1,
                "target": "all_components",
            }
            for tick in reset_ticks
        )
        self._events = tuple(
            sorted(events, key=lambda event: (event["start_tick"], event["id"]))
        )

    def active_at(self, global_tick: int) -> Any:
        active = tuple(
            event
            for event in self._events
            if event["start_tick"] <= global_tick < event["end_tick"]
        )
        external = ZERO3.copy()
        force = ZERO3.copy()
        bias = None
        invalid = None
        reset = None
        for event in active:
            if event["type"] == "external_torque":
                external = np.asarray(event["vector_Nm"], dtype=np.float64)
            elif event["type"] == "specific_force_disturbance":
                force = np.asarray(event["vector_m_s2"], dtype=np.float64)
            elif event["type"] == "imu_bias":
                bias = event
            elif event["type"] == "invalid_input":
                invalid = event
            elif event["type"] == "reset":
                reset = event
        return SimpleNamespace(
            command_q_nb=IDENTITY.copy(),
            external_torque_body_Nm=external.copy(),
            imu_bias=bias,
            specific_force_body_m_s2=force.copy(),
            invalid_event=invalid,
            reset_event=reset,
            event_ids=tuple(event["id"] for event in active),
        )

    @staticmethod
    def adapt_measurement(
        raw_gyro_b_rad_s: Any,
        raw_specific_force_b_m_s2: Any,
        active: Any,
        nominal_gyro_bias_rad_s: Any,
        nominal_accelerometer_bias_m_s2: Any,
    ) -> tuple[np.ndarray, np.ndarray]:
        del nominal_gyro_bias_rad_s, nominal_accelerometer_bias_m_s2
        return (
            np.asarray(raw_gyro_b_rad_s).copy(),
            np.asarray(raw_specific_force_b_m_s2).copy()
            + active.specific_force_body_m_s2,
        )


class FakePlant:
    def __init__(self) -> None:
        self.reset_calls = 0
        self.step_calls = 0
        self.local_tick = 0
        self.origin = 0.0
        self.state: FakePlantState | None = None

    def reset(
        self, initial: FakePlantInitialState, timestamp_s: float
    ) -> FakePlantState:
        self.reset_calls += 1
        self.local_tick = 0
        self.origin = timestamp_s
        self.state = FakePlantState(
            np.asarray(initial.q_nb).copy(),
            np.asarray(initial.omega_b_rad_s).copy(),
            timestamp_s,
        )
        return self.state

    def step_base(self, torque: Any) -> FakePlantState:
        self.step_calls += 1
        self.local_tick += 1
        assert self.state is not None
        self.state = FakePlantState(
            self.state.q_nb.copy(),
            self.state.omega_b_rad_s + np.asarray(torque) * 0.0025,
            self.origin + self.local_tick * 0.0025,
        )
        return self.state

    def snapshot(self) -> dict[str, Any]:
        return {
            "reset_calls": self.reset_calls,
            "step_calls": self.step_calls,
            "local_tick": self.local_tick,
            "origin": self.origin,
            "state": self.state,
        }


class FakeActuator:
    def __init__(
        self,
        *,
        fail_reset: bool = False,
        fail_inner_step: bool = False,
    ) -> None:
        self.fail_reset = fail_reset
        self.fail_inner_step = fail_inner_step
        self.reset_calls = 0
        self.step_calls = 0
        self.delegate_step_calls = 0
        self.timestamp = 0.0
        self.feedback: FakeFeedback | None = None

    def reset(
        self, initial: FakeActuatorInitialState, timestamp_s: float
    ) -> FakeFeedback:
        self.reset_calls += 1
        if self.fail_reset:
            raise RuntimeError("deliberate partial-reset fixture")
        self.step_calls = 0
        self.delegate_step_calls = 0
        self.timestamp = timestamp_s
        self.feedback = FakeFeedback(
            np.asarray(initial.actual_torque_body_Nm).copy(),
            np.asarray(initial.held_limited_torque_body_Nm).copy(),
            np.asarray(initial.held_saturated).copy(),
            timestamp_s,
            initial.held_command_timestamp_s,
        )
        return self.feedback

    def step(self, command: FakeTorqueCommand, dt_s: float) -> FakeFeedback:
        self.delegate_step_calls += 1
        if self.fail_inner_step:
            raise RuntimeError("deliberate inner actuator failure")
        self.timestamp += dt_s
        self.feedback = FakeFeedback(
            np.asarray(command.limited_torque_body_Nm).copy(),
            np.asarray(command.limited_torque_body_Nm).copy(),
            np.asarray(command.saturated).copy(),
            self.timestamp,
            command.timestamp_s,
        )
        return self.feedback

    def step_base(self, command: FakeTorqueCommand) -> FakeFeedback:
        self.step_calls += 1
        return self.step(command, 0.0025)

    def snapshot(self) -> dict[str, Any]:
        return {
            "reset_calls": self.reset_calls,
            "step_calls": self.step_calls,
            "delegate_step_calls": self.delegate_step_calls,
            "timestamp": self.timestamp,
            "feedback": self.feedback,
        }


class FakeIMU:
    def __init__(self, *, fail_sample: bool = False) -> None:
        self.reset_calls = 0
        self.sample_calls = 0
        self.seed = 0
        self.last_timestamp: float | None = None
        self.fail_sample = fail_sample

    def reset(
        self, initial: FakeIMUInitialState, timestamp_s: float, seed: int
    ) -> None:
        del initial, timestamp_s
        self.reset_calls += 1
        self.sample_calls = 0
        self.seed = seed
        self.last_timestamp = None

    def sample(self, truth: FakeTruth, timestamp_s: float) -> FakeIMUSample:
        self.sample_calls += 1
        self.last_timestamp = timestamp_s
        if self.fail_sample:
            raise RuntimeError("deliberate IMU sample failure")
        return FakeIMUSample(
            timestamp_s,
            np.asarray(truth.omega_b_rad_s)
            + np.array([self.sample_calls, 0.0, 0.0]),
            np.array([0.0, 0.0, -9.81]),
            True,
        )

    def snapshot(self) -> dict[str, Any]:
        return {
            "reset_calls": self.reset_calls,
            "sample_calls": self.sample_calls,
            "seed": self.seed,
            "last_timestamp": self.last_timestamp,
        }


class FakeEstimator:
    def __init__(
        self,
        *,
        fail_process: bool = False,
        mutate_on_stale_rejection: bool = False,
    ) -> None:
        self.reset_calls = 0
        self.process_calls = 0
        self.last_timestamp = 0.0
        self.epoch_id = -1
        self.estimate: FakeEstimate | None = None
        self.fail_process = fail_process
        self.mutate_on_stale_rejection = mutate_on_stale_rejection

    def reset(
        self,
        initial: FakeEstimatorInitialState,
        epoch: FakeResetEpoch,
        seed: int,
    ) -> FakeEstimate:
        del seed
        self.reset_calls += 1
        self.process_calls = 0
        self.epoch_id = epoch.id
        self.last_timestamp = epoch.timestamp_s
        self.estimate = FakeEstimate(
            np.asarray(initial.q_nb).copy(),
            np.asarray(initial.omega_b_rad_s).copy(),
            epoch.timestamp_s,
        )
        return self.estimate

    def process(self, sample: FakeIMUSample) -> Any:
        if sample.timestamp_s <= self.last_timestamp:
            if self.mutate_on_stale_rejection:
                self.process_calls += 1
            return SimpleNamespace(
                estimate=self.estimate,
                diagnostics=FakeDiagnostics(
                    False, "imu sample timestamp is duplicate or stale"
                ),
            )
        self.process_calls += 1
        if self.fail_process:
            raise RuntimeError("deliberate estimator process failure")
        self.last_timestamp = sample.timestamp_s
        self.estimate = FakeEstimate(
            IDENTITY.copy(), sample.gyro_b_rad_s.copy(), sample.timestamp_s
        )
        return SimpleNamespace(
            estimate=self.estimate,
            diagnostics=FakeDiagnostics(True, "accepted"),
        )

    def snapshot(self) -> dict[str, Any]:
        return {
            "reset_calls": self.reset_calls,
            "process_calls": self.process_calls,
            "last_timestamp": self.last_timestamp,
            "epoch_id": self.epoch_id,
            "estimate": self.estimate,
        }


class FakeCore:
    def __init__(self, controller: "FakeController") -> None:
        self.controller = controller

    def last_diagnostics(self) -> FakeDiagnostics:
        return FakeDiagnostics(True, "accepted")


class FakeController:
    def __init__(self) -> None:
        self.reset_calls = 0
        self.step_calls = 0
        self.rejected_calls = 0
        self.expected_timestamp = 0.0
        self.epoch_id = -1
        self.held: FakeTorqueCommand | None = None
        self.core = FakeCore(self)

    def reset(self, epoch: Any) -> FakeTorqueCommand:
        self.reset_calls += 1
        self.step_calls = 0
        self.epoch_id = epoch.id
        self.expected_timestamp = epoch.timestamp_s + 0.005
        self.held = FakeTorqueCommand(
            ZERO3.copy(), ZERO3.copy(), epoch.timestamp_s, np.zeros(3, dtype=bool)
        )
        return self.held

    def step(
        self,
        command: FakeCommand,
        estimate: FakeEstimate,
        feedback: FakeFeedback,
        dt_s: float,
    ) -> FakeTorqueCommand:
        del estimate, feedback
        if dt_s != 0.005:
            self.rejected_calls += 1
            raise FakeControllerError("invalid_dt")
        if command.timestamp_s != self.expected_timestamp:
            self.rejected_calls += 1
            raise FakeControllerError("unexpected_tick")
        self.step_calls += 1
        value = np.full(3, 0.01 * self.step_calls)
        self.held = FakeTorqueCommand(
            value, value.copy(), command.timestamp_s, np.zeros(3, dtype=bool)
        )
        self.expected_timestamp += 0.005
        return self.held

    def snapshot(self) -> dict[str, Any]:
        return {
            "reset_calls": self.reset_calls,
            "step_calls": self.step_calls,
            "expected_timestamp": self.expected_timestamp,
            "epoch_id": self.epoch_id,
            "held": self.held,
        }


@dataclass
class FakeBundle:
    session: IntegrationSession
    event_schedule: FakeEvents
    plant: FakePlant
    actuator: FakeActuator
    imu: FakeIMU
    estimator: FakeEstimator
    controller: FakeController
    lifecycle_recorder: LifecycleRecorder


def _json_value_digest(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _make_bundle(
    *,
    reset_ticks: tuple[int, ...] = (),
    invalid_by_tick: dict[int, str] | None = None,
    fail_actuator_reset: bool = False,
    fail_actuator_inner_step: bool = False,
    fail_imu_sample: bool = False,
    fail_estimator_process: bool = False,
    mutate_estimator_on_stale_rejection: bool = False,
    bind_snapshotter: bool = True,
    event_schedule: FakeEvents | None = None,
    observer_omit_section_at_phase: int | None = None,
) -> FakeBundle:
    simulation = SimpleNamespace(
        PlantInitialState=FakePlantInitialState,
        ActuatorInitialState=FakeActuatorInitialState,
        IMUInitialState=FakeIMUInitialState,
        SensorTruth=FakeTruth,
        IMUSample=FakeIMUSample,
    )
    estimator_types = SimpleNamespace(
        EstimatorInitialState=FakeEstimatorInitialState,
        ResetEpoch=FakeResetEpoch,
        StateEstimate=FakeEstimate,
    )
    parameters = SimpleNamespace(
        gyro_bias_rad_s=ZERO3.copy(),
        accelerometer_bias_m_s2=ZERO3.copy(),
    )
    plant = FakePlant()
    actuator = FakeActuator(
        fail_reset=fail_actuator_reset,
        fail_inner_step=fail_actuator_inner_step,
    )
    imu = FakeIMU(fail_sample=fail_imu_sample)
    estimator = FakeEstimator(
        fail_process=fail_estimator_process,
        mutate_on_stale_rejection=mutate_estimator_on_stale_rejection,
    )
    controller = FakeController()
    lifecycle_recorder = LifecycleRecorder(id_prefix="fake-g3a")
    events = (
        FakeEvents(reset_ticks=reset_ticks, invalid_by_tick=invalid_by_tick)
        if event_schedule is None
        else event_schedule
    )
    event_definition_sha256 = _json_value_digest(list(events._events))
    session = IntegrationSession(
        profile_id="S",
        scheduler=FakeScheduler(),
        event_schedule=events,
        simulation=simulation,
        estimator_types=estimator_types,
        g1_parameters=parameters,
        plant=plant,
        actuator=actuator,
        imu=imu,
        estimator=estimator,
        controller=controller,
        command_factory=lambda q, timestamp, valid: FakeCommand(
            np.asarray(q).copy(), timestamp, valid
        ),
        actor_ids={
            "plant": "S/actor/plant",
            "actuator": "S/actor/actuator",
            "imu": "S/actor/imu",
            "estimator": "S/actor/estimator",
            "controller": "S/actor/controller",
            "observer": "S/actor/observer",
        },
        observer_manifest_sha256=DUMMY_SHA,
        configuration_bindings={
            "scheduler_definition_sha256": "b" * 64,
            "event_definition_sha256": event_definition_sha256,
            "parameter_binding_sha256": "d" * 64,
        },
        seed=2026100900,
        plant_q_nb=IDENTITY,
        plant_omega_b_rad_s=ZERO3,
        estimator_q_nb=IDENTITY,
        estimator_omega_b_rad_s=ZERO3,
        actuator_actual_torque_body_Nm=INITIAL_ACTUAL,
        lifecycle_recorder=lifecycle_recorder,
    )

    def snapshotter(active: IntegrationSession) -> dict[str, Any]:
        state = active.functional_state()
        captured = {
            "session": state,
            "plant": plant.snapshot(),
            "actuator": actuator.snapshot(),
            "imu": imu.snapshot(),
            "estimator": estimator.snapshot(),
            "controller": controller.snapshot(),
        }
        if observer_omit_section_at_phase == state["phase_cursor"]:
            captured.pop("controller")
        return captured

    if bind_snapshotter:
        session.bind_snapshotter(snapshotter)
    return FakeBundle(
        session,
        events,
        plant,
        actuator,
        imu,
        estimator,
        controller,
        lifecycle_recorder,
    )


def _old_probe(
    probe_id: str,
    envelope: EpochEnvelope,
    role: str,
    consumer: str,
) -> GuardProbe:
    return GuardProbe(
        probe_id=probe_id,
        kind="old_epoch",
        envelope=envelope,
        expected_role=role,
        consumer=consumer,
        expected_reason="stale_epoch",
    )


def _assert_operation_shape(operations: tuple[Any, ...]) -> None:
    assert all(REQUIRED_OPERATION_FIELDS <= set(operation) for operation in operations)


def _assert_operation_guard_refs(boundary: Any) -> None:
    guarded = [
        operation
        for operation in boundary.operations
        if operation["attempt_kind"] not in {"reset", "publication"}
        and not (
            operation["owner"] == "actuator"
            and operation["method"] == "step"
        )
    ]
    guard_refs = [operation["guard_ref"] for operation in guarded]
    assert all(isinstance(reference, str) and reference for reference in guard_refs)
    assert len(guard_refs) == len(set(guard_refs))
    for operation in guarded:
        matching = [
            guard
            for guard in boundary.guards
            if guard["guard_id"] == operation["guard_ref"]
        ]
        assert len(matching) == 1
        assert matching[0]["accepted"] is True
        assert matching[0]["consumer_operation_id"] == operation["operation_id"]


def test_reset_is_controller_first_and_ordinary_phase_order_holds_publication() -> None:
    bundle = _make_bundle()
    reset = bundle.session.reset(0, reason="startup")
    _assert_operation_shape(reset.operations)
    assert [operation["owner"] for operation in reset.operations] == [
        "controller",
        "actuator",
        "plant",
        "imu",
        "estimator",
    ]
    assert all(
        operation["reset_inputs"]["kind"] == "reset"
        for operation in reset.operations
    )
    assert [operation["reset_inputs"]["actor"] for operation in reset.operations] == [
        "controller",
        "actuator",
        "plant",
        "imu",
        "estimator",
    ]
    observations = bundle.session.lifecycle_observations
    assert [item["observation_index"] for item in observations] == list(range(10))
    enter_observations = [item for item in observations if item["event"] == "enter"]
    assert [item["owner"] for item in enter_observations] == [
        "controller",
        "actuator",
        "plant",
        "imu",
        "estimator",
    ]
    for operation, observation in zip(
        reset.operations, enter_observations, strict=True
    ):
        assert operation["operation_id"] == observation["operation_id"]
        assert canonical_snapshot_bytes(
            operation["reset_inputs"]
        ) == canonical_snapshot_bytes(observation["arguments"])
    return_observations = [
        item for item in observations if item["event"] == "return"
    ]
    assert all(
        set(item["result"])
        == {
            "actor_id",
            "parameter_object_ref",
            "snapshot_ref",
            "capture_id",
            "resolved_config_path",
            "source_bytes_sha256",
            "document_sha256",
        }
        for item in return_observations
    )
    assert [item["result"]["actor_id"] for item in return_observations] == [
        "S/actor/controller",
        "S/actor/actuator",
        "S/actor/plant",
        "S/actor/imu",
        "S/actor/estimator",
    ]
    actuator_reset = reset.operations[1]["reset_inputs"]
    assert set(actuator_reset["initial_state"]) == {
        "actual_torque_body_Nm",
        "held_limited_torque_body_Nm",
        "held_requested_torque_body_Nm",
        "held_saturated",
        "held_command_timestamp_s",
    }
    assert actuator_reset["reset_command_ref"] == reset.operations[0]["outputs"][
        "torque_command"
    ]
    assert np.array_equal(
        actuator_reset["initial_state"]["actual_torque_body_Nm"],
        INITIAL_ACTUAL,
    )
    assert not np.array_equal(
        actuator_reset["initial_state"]["actual_torque_body_Nm"],
        actuator_reset["initial_state"]["held_limited_torque_body_Nm"],
    )
    reset_held = bundle.session.held_envelope.envelope_id

    first = bundle.session.advance(1)
    _assert_operation_shape(first.operations)
    _assert_operation_guard_refs(first)
    assert [operation["owner"] for operation in first.operations] == [
        "plant",
        "actuator",
        "actuator",
    ]
    assert [operation["method"] for operation in first.operations] == [
        "step_base",
        "step_base",
        "step",
    ]
    assert first.published_after_id is None
    assert bundle.session.held_envelope.envelope_id == reset_held

    second = bundle.session.advance(2)
    _assert_operation_shape(second.operations)
    _assert_operation_guard_refs(second)
    assert [operation["owner"] for operation in second.operations] == [
        "plant",
        "actuator",
        "actuator",
        "imu",
        "measurement_adapter",
        "estimator",
        "controller",
        "session",
    ]
    assert second.published_after_id == bundle.session.held_envelope.envelope_id
    sampled_command = next(
        wire
        for wire in second.wires
        if wire.role == "attitude_command"
        and wire.producer == "command_sampler"
    )
    assert sampled_command.producer_operation_id is None
    assert sampled_command.parent_ids == ()
    assert bundle.session.call_counts["plant_step_attempts"] == 2
    assert bundle.session.call_counts["actuator_step_attempts"] == 2
    assert bundle.actuator.step_calls == 2
    assert bundle.actuator.delegate_step_calls == 2
    delegates = [
        operation
        for boundary in (first, second)
        for operation in boundary.operations
        if operation["owner"] == "actuator"
        and operation["method"] == "step"
    ]
    assert len(delegates) == 2
    assert all(operation["guard_ref"] is None for operation in delegates)
    assert bundle.session.call_counts["imu_sample_attempts"] == 1
    assert bundle.session.call_counts["estimator_process_accepted"] == 1
    assert bundle.session.call_counts["controller_step_accepted"] == 1


def test_required_after_imu_capture_precedes_adapter_estimator_and_controller(
) -> None:
    bundle = _make_bundle()
    bundle.session.reset(0, reason="startup")
    bundle.session.advance(1)

    result = bundle.session.advance(
        2,
        directive=TickDirective(
            required_after_imu_snapshot_id="S/g2/required"
        ),
    )

    capture = result.required_after_imu_capture
    assert capture is not None
    assert capture.snapshot_id == "S/g2/required"
    assert capture.capture_id == "S/g2/required/capture"
    assert capture.phase == 3
    assert capture.functional_state["session"]["phase_cursor"] == 3
    assert [
        item["role"]
        for item in capture.functional_state["session"]["pending_inputs"]
    ] == ["plant_state", "feedback", "sensor_truth", "imu"]
    assert capture.functional_state["imu"]["sample_calls"] == 1
    assert capture.functional_state["estimator"]["process_calls"] == 0
    assert capture.functional_state["controller"]["step_calls"] == 0
    assert bundle.estimator.process_calls == 1
    assert bundle.controller.step_calls == 1
    with pytest.raises(TypeError):
        capture.functional_state["session"]["phase_cursor"] = 6

    observer_returns = [
        item
        for item in bundle.session.lifecycle_observations
        if item["owner"] == "observer"
        and item["method"] == "capture_snapshot"
        and item["event"] == "return"
    ]
    assert len(observer_returns) == 1
    assert observer_returns[0]["result"]["snapshot_ref"] == capture.snapshot_id
    assert observer_returns[0]["result"]["capture_id"] == capture.capture_id


def test_imu_failure_frontier_retains_actual_truth_input_without_raw_output() -> None:
    bundle = _make_bundle(fail_imu_sample=True)
    bundle.session.reset(0, reason="startup")
    bundle.session.advance(1)

    with pytest.raises(SessionContractError) as caught:
        bundle.session.advance(
            2,
            directive=TickDirective(
                required_after_imu_snapshot_id="S/g2/required"
            ),
        )

    assert caught.value.reason == "component_failure"
    frontier = caught.value.failure_frontier
    assert frontier is bundle.session.failure_frontier
    assert frontier is not None
    imu_operation = next(
        operation
        for operation in frontier["operations"]
        if operation["owner"] == "imu" and operation["method"] == "sample"
    )
    truth_wires = [
        wire for wire in frontier["wires"] if wire.role == "sensor_truth"
    ]
    assert len(truth_wires) == 1
    assert imu_operation["inputs"]["sensor_truth"] == (
        truth_wires[0].envelope_id
    )
    assert imu_operation["accepted"] is False
    assert imu_operation["outputs"] == {}
    assert imu_operation["reason"] == "deliberate IMU sample failure"
    assert all(
        not (wire.role == "imu" and wire.producer == "imu")
        for wire in frontier["wires"]
    )
    assert bundle.imu.sample_calls == 1
    assert bundle.estimator.process_calls == 0
    assert bundle.controller.step_calls == 0
    assert bundle.session.call_counts["imu_sample_attempts"] == 1
    assert not any(
        item["owner"] == "observer"
        and item["method"] == "capture_snapshot"
        for item in bundle.session.lifecycle_observations
    )


def test_phase3_capture_survives_later_estimator_failure_without_reentry() -> None:
    bundle = _make_bundle(fail_estimator_process=True)
    bundle.session.reset(0, reason="startup")
    bundle.session.advance(1)

    with pytest.raises(SessionContractError) as caught:
        bundle.session.advance(
            2,
            directive=TickDirective(
                required_after_imu_snapshot_id="S/g2/required"
            ),
        )

    assert caught.value.reason == "component_failure"
    frontier = caught.value.failure_frontier
    assert frontier is bundle.session.failure_frontier
    assert frontier is not None
    assert frontier["retention_status"] == "complete"
    assert frontier["missing_observations"] == ()
    assert frontier["retention_exception"] is None
    assert frontier["original_exception"] == {
        "type": "RuntimeError",
        "reason": None,
        "detail": "deliberate estimator process failure",
        "message": "deliberate estimator process failure",
    }
    estimator_operation = next(
        operation
        for operation in frontier["operations"]
        if operation["owner"] == "estimator"
        and operation["method"] == "process"
    )
    assert estimator_operation["accepted"] is False
    assert estimator_operation["reason"] == (
        "deliberate estimator process failure"
    )
    capture = frontier["required_after_imu_capture"]
    assert capture is not None
    assert capture.snapshot_id == "S/g2/required"
    assert capture.capture_id == "S/g2/required/capture"
    assert capture.phase == 3
    assert capture.functional_state["session"]["phase_cursor"] == 3
    assert capture.functional_state["imu"]["sample_calls"] == 1
    assert capture.functional_state["estimator"]["process_calls"] == 0
    assert capture.functional_state["controller"]["step_calls"] == 0
    assert bundle.imu.sample_calls == 1
    assert bundle.estimator.process_calls == 1
    assert bundle.controller.step_calls == 0
    observer_returns = [
        item
        for item in bundle.session.lifecycle_observations
        if item["owner"] == "observer"
        and item["method"] == "capture_snapshot"
        and item["event"] == "return"
    ]
    assert len(observer_returns) == 1

    counts = dict(bundle.session.call_counts)
    with pytest.raises(SessionContractError) as terminal:
        bundle.session.advance(2)
    assert terminal.value.reason == "terminal_inconclusive"
    assert terminal.value.failure_frontier is frontier
    assert dict(bundle.session.call_counts) == counts
    assert len(
        [
            item
            for item in bundle.session.lifecycle_observations
            if item["owner"] == "observer"
            and item["method"] == "capture_snapshot"
            and item["event"] == "return"
        ]
    ) == 1


def test_five_real_old_epoch_roles_reject_then_legal_inputs_continue() -> None:
    bundle = _make_bundle(reset_ticks=(3,))
    bundle.session.reset(0, reason="startup")
    bundle.session.advance(1)
    bundle.session.advance(2)
    old_held = bundle.session.held_envelope
    old_feedback = bundle.session.feedback_envelope
    old_sample = bundle.session.last_sample_envelope
    old_estimate = bundle.session.last_estimate_envelope
    old_command = bundle.session.last_command_envelope
    assert (
        old_sample is not None
        and old_estimate is not None
        and old_command is not None
    )

    bundle.session.reset(3, reason="scheduled_reset")
    tick4 = bundle.session.advance(
        4,
        directive=TickDirective(
            preflight_probes=(
                _old_probe("old-held", old_held, "held_torque", "actuator"),
            )
        ),
    )
    tick5 = bundle.session.advance(
        5,
        directive=TickDirective(
            pre_estimator_probes=(
                _old_probe("old-imu", old_sample, "imu", "estimator"),
            ),
            pre_controller_probes=(
                _old_probe("old-feedback", old_feedback, "feedback", "controller"),
                _old_probe("old-estimate", old_estimate, "estimate", "controller"),
                _old_probe(
                    "old-command", old_command, "attitude_command", "controller"
                ),
            ),
        ),
    )
    all_probes = (*tick4.probes, *tick5.probes)
    _assert_operation_guard_refs(tick4)
    _assert_operation_guard_refs(tick5)
    assert [probe["probe_id"] for probe in all_probes] == [
        "old-held",
        "old-imu",
        "old-feedback",
        "old-estimate",
        "old-command",
    ]
    assert {probe["reason"] for probe in all_probes} == {"stale_epoch"}
    assert all(probe["original_legal_id"] is not None for probe in all_probes)
    assert all(not any(probe["component_call_delta"].values()) for probe in all_probes)
    assert all(
        probe["before_capture_id"] == f'{probe["before_snapshot_id"]}/capture'
        and probe["after_capture_id"] == f'{probe["after_snapshot_id"]}/capture'
        for probe in all_probes
    )
    assert [guard["consumer_operation_id"] for guard in tick4.guards] == [
        tick4.operations[0]["operation_id"],
        tick4.operations[1]["operation_id"],
        tick4.operations[1]["operation_id"],
    ]
    assert [guard["accepted"] for guard in tick4.guards] == [True, False, True]
    assert tick4.probes[0]["before_snapshot"]["plant"]["step_calls"] == 3
    controller_probe_refs = [
        probe["checked_refs"]
        for probe in tick5.probes
        if probe["role"] in {"feedback", "estimate", "attitude_command"}
    ]
    assert all(
        set(refs) == {"attitude_command", "estimate", "feedback"}
        for refs in controller_probe_refs
    )
    assert bundle.session.lifecycle is SessionLifecycle.ACTIVE
    assert bundle.session.call_counts["plant_step_attempts"] == 4


def test_truth_derived_estimator_and_controller_candidates_use_shared_guard() -> None:
    bundle = _make_bundle()
    bundle.session.reset(0, reason="startup")
    bundle.session.advance(1)
    result = bundle.session.advance(
        2,
        directive=TickDirective(
            truth_estimator_probe_id="N-E",
            truth_controller_probe_id="N-C",
        ),
    )
    _assert_operation_shape(result.operations)
    _assert_operation_guard_refs(result)
    assert [probe["reason"] for probe in result.probes] == [
        "truth_dependency_forbidden",
        "truth_dependency_forbidden",
    ]
    assert bundle.session.call_counts["estimator_process_accepted"] == 1
    assert bundle.session.call_counts["controller_step_accepted"] == 1
    assert set(result.probes[0]["checked_refs"]) == {"imu"}
    assert set(result.probes[1]["checked_refs"]) == {
        "attitude_command",
        "estimate",
        "feedback",
    }
    n_e = next(
        wire
        for wire in result.wires
        if wire.envelope_id == result.probes[0]["candidate_id"]
    )
    n_c = next(
        wire
        for wire in result.wires
        if wire.envelope_id == result.probes[1]["candidate_id"]
    )
    truth = next(wire for wire in result.wires if wire.role == "sensor_truth")
    legal_imu = next(
        wire
        for wire in result.wires
        if wire.role == "imu" and wire.producer == "measurement_adapter"
    )
    legal_estimate = next(
        wire
        for wire in result.wires
        if wire.role == "estimate" and wire.producer == "estimator"
    )
    assert np.array_equal(n_e.payload.gyro_b_rad_s, truth.payload.omega_b_rad_s)
    assert np.array_equal(
        n_e.payload.specific_force_b_m_s2,
        legal_imu.payload.specific_force_b_m_s2,
    )
    assert np.array_equal(n_c.payload.q_nb_estimate, truth.payload.q_nb)
    assert np.array_equal(
        n_c.payload.omega_b_estimate_rad_s,
        legal_estimate.payload.omega_b_estimate_rad_s,
    )


def test_negative_dt_and_stale_timestamp_reject_without_state_then_retry_once() -> None:
    bundle = _make_bundle(
        invalid_by_tick={2: "negative_dt", 4: "stale_timestamp"}
    )
    bundle.session.reset(0, reason="startup")
    bundle.session.advance(1)
    negative = bundle.session.advance(
        2, directive=TickDirective(fault=FAULT_CONTROLLER_NEGATIVE_DT)
    )
    bundle.session.advance(3)
    stale = bundle.session.advance(
        4, directive=TickDirective(fault=FAULT_ESTIMATOR_STALE_TIMESTAMP)
    )
    _assert_operation_shape(negative.operations)
    _assert_operation_shape(stale.operations)
    _assert_operation_guard_refs(negative)
    _assert_operation_guard_refs(stale)
    rejected = [
        operation
        for operation in (*negative.operations, *stale.operations)
        if not operation["accepted"]
    ]
    assert [operation["reason"] for operation in rejected] == [
        "invalid_dt",
        "imu sample timestamp is duplicate or stale",
    ]
    assert all(
        operation["before_capture_id"]
        == f'{operation["before_snapshot_id"]}/capture'
        and operation["after_capture_id"]
        == f'{operation["after_snapshot_id"]}/capture'
        for operation in rejected
    )
    assert all(
        canonical_snapshot_bytes(operation["before_snapshot"])
        == canonical_snapshot_bytes(operation["after_snapshot"])
        for operation in rejected
    )
    assert sum(
        operation["attempt_kind"] == "same_tick_correction"
        for operation in negative.operations
    ) == 1
    assert sum(
        operation["attempt_kind"] == "same_tick_correction"
        for operation in stale.operations
    ) == 1
    assert len(
        [
            operation
            for operation in stale.operations
            if operation["owner"] == "imu" and operation["method"] == "sample"
        ]
    ) == 1
    assert bundle.imu.sample_calls == 2
    assert bundle.session.call_counts["imu_sample_attempts"] == 2
    assert bundle.session.call_counts["controller_step_attempts"] == 3
    assert bundle.session.call_counts["controller_step_accepted"] == 2
    assert bundle.session.call_counts["controller_step_rejected"] == 1
    assert bundle.session.call_counts["estimator_process_attempts"] == 3
    assert bundle.session.call_counts["estimator_process_accepted"] == 2
    assert bundle.session.call_counts["estimator_process_rejected"] == 1
    for result, owner in ((negative, "controller"), (stale, "estimator")):
        attempts = [
            operation
            for operation in result.operations
            if operation["owner"] == owner
        ]
        assert len(attempts) == 2
        for operation in attempts:
            matching_guards = [
                guard
                for guard in result.guards
                if guard["consumer_operation_id"] == operation["operation_id"]
            ]
            assert len(matching_guards) == 1
            assert matching_guards[0]["accepted"] is True
            assert operation["guard_ref"] == matching_guards[0]["guard_id"]
        assert attempts[0]["operation_id"] != attempts[1]["operation_id"]
    assert bundle.session.lifecycle is SessionLifecycle.ACTIVE


def test_fake_estimator_stale_rejection_preserves_complete_snapshot() -> None:
    estimator = FakeEstimator()
    estimator.reset(
        FakeEstimatorInitialState(IDENTITY.copy(), ZERO3.copy()),
        FakeResetEpoch(0, 0.0),
        2026100900,
    )
    before = estimator.snapshot()
    result = estimator.process(
        FakeIMUSample(0.0, ZERO3.copy(), ZERO3.copy(), True)
    )
    after = estimator.snapshot()
    assert result.diagnostics == FakeDiagnostics(
        False, "imu sample timestamp is duplicate or stale"
    )
    assert canonical_snapshot_bytes(before) == canonical_snapshot_bytes(after)


def test_mutating_fake_stale_rejection_is_terminal_without_correction_or_resample(
) -> None:
    bundle = _make_bundle(
        invalid_by_tick={4: "stale_timestamp"},
        mutate_estimator_on_stale_rejection=True,
    )
    bundle.session.reset(0, reason="startup")
    bundle.session.advance(1)
    bundle.session.advance(2)
    bundle.session.advance(3)

    with pytest.raises(SessionContractError) as caught:
        bundle.session.advance(
            4,
            directive=TickDirective(fault=FAULT_ESTIMATOR_STALE_TIMESTAMP),
        )

    assert caught.value.reason == "rejection_mutated_state"
    frontier = caught.value.failure_frontier
    assert frontier is bundle.session.failure_frontier
    assert frontier is not None
    estimator_operations = [
        operation
        for operation in frontier["operations"]
        if operation["owner"] == "estimator"
        and operation["method"] == "process"
    ]
    assert len(estimator_operations) == 1
    assert estimator_operations[0]["attempt_kind"] == "injected_invalid"
    assert not any(
        operation["attempt_kind"] == "same_tick_correction"
        for operation in frontier["operations"]
    )
    assert len(
        [
            operation
            for operation in frontier["operations"]
            if operation["owner"] == "imu" and operation["method"] == "sample"
        ]
    ) == 1
    assert bundle.imu.sample_calls == 2
    assert bundle.estimator.process_calls == 2
    assert bundle.session.call_counts["imu_sample_attempts"] == 2
    assert bundle.session.call_counts["estimator_process_attempts"] == 2
    assert bundle.session.call_counts["estimator_process_accepted"] == 1
    assert bundle.session.call_counts["estimator_process_rejected"] == 1
    assert bundle.session.lifecycle is SessionLifecycle.TERMINAL_INCONCLUSIVE


def test_invalid_path_unexpected_dut_exception_retains_first_cause_once() -> None:
    bundle = _make_bundle(invalid_by_tick={2: "negative_dt"})
    bundle.session.reset(0, reason="startup")
    bundle.session.advance(1)
    invocations: list[float] = []

    def unexpected_step(
        command: FakeCommand,
        estimate: FakeEstimate,
        feedback: FakeFeedback,
        dt_s: float,
    ) -> FakeTorqueCommand:
        del command, estimate, feedback
        invocations.append(dt_s)
        raise FakeControllerError("unexpected_internal_failure")

    bundle.controller.step = unexpected_step  # type: ignore[method-assign]
    with pytest.raises(SessionContractError) as caught:
        bundle.session.advance(
            2,
            directive=TickDirective(fault=FAULT_CONTROLLER_NEGATIVE_DT),
        )

    assert caught.value.reason == "unexpected_internal_failure"
    frontier = caught.value.failure_frontier
    assert frontier is bundle.session.failure_frontier
    assert frontier is not None
    assert frontier["termination_status"] == "terminal_inconclusive"
    assert frontier["original_exception"] == {
        "type": "FakeControllerError",
        "reason": "unexpected_internal_failure",
        "detail": "unexpected_internal_failure: fake rejection",
        "message": "unexpected_internal_failure: fake rejection",
    }
    invalid_attempts = [
        operation
        for operation in frontier["operations"]
        if operation["attempt_kind"] == "injected_invalid"
    ]
    assert len(invalid_attempts) == 1
    assert invalid_attempts[0]["accepted"] is False
    assert invalid_attempts[0]["reason"] == "unexpected_internal_failure"
    assert invocations == [-0.005]
    assert bundle.session.call_counts["controller_step_attempts"] == 1
    assert bundle.session.call_counts["controller_step_rejected"] == 0

    counts = dict(bundle.session.call_counts)
    with pytest.raises(SessionContractError) as terminal:
        bundle.session.advance(2)
    assert terminal.value.reason == "terminal_inconclusive"
    assert terminal.value.failure_frontier is frontier
    assert dict(bundle.session.call_counts) == counts
    assert invocations == [-0.005]


def test_unexpected_tick_enters_needs_reset_before_any_next_boundary_call() -> None:
    bundle = _make_bundle()
    bundle.session.reset(0, reason="startup")
    bundle.session.advance(1)
    result = bundle.session.advance(
        2, directive=TickDirective(fault=FAULT_CONTROLLER_UNEXPECTED_TICK)
    )
    _assert_operation_shape(result.operations)
    _assert_operation_guard_refs(result)
    rejected = [
        operation for operation in result.operations if not operation["accepted"]
    ]
    assert len(rejected) == 1
    assert rejected[0]["reason"] == "unexpected_tick"
    assert rejected[0]["session_transition"] == "active_to_needs_reset"
    matching_guards = [
        guard
        for guard in result.guards
        if guard["consumer_operation_id"] == rejected[0]["operation_id"]
    ]
    assert len(matching_guards) == 1
    assert rejected[0]["guard_ref"] == matching_guards[0]["guard_id"]
    assert set(matching_guards[0]["checked_refs"]) == {
        "attitude_command",
        "estimate",
        "feedback",
    }
    assert result.published_after_id is None
    injected_command = next(
        wire
        for wire in result.wires
        if wire.role == "attitude_command"
        and wire.producer == "fault_injector"
    )
    legal_command = next(
        wire
        for wire in result.wires
        if wire.role == "attitude_command"
        and wire.producer == "command_sampler"
    )
    assert injected_command.producer_operation_id is None
    assert injected_command.parent_ids == (legal_command.envelope_id,)
    assert bundle.session.lifecycle is SessionLifecycle.NEEDS_RESET
    counts = dict(bundle.session.call_counts)
    with pytest.raises(SessionContractError) as caught:
        bundle.session.advance(3)
    assert caught.value.reason == "needs_reset"
    assert dict(bundle.session.call_counts) == counts

    reset = bundle.session.reset(3, reason="needs_reset_recovery")
    assert [operation["owner"] for operation in reset.operations] == [
        "controller",
        "actuator",
        "plant",
        "imu",
        "estimator",
    ]
    bundle.session.advance(4)
    recovered = bundle.session.advance(5)
    assert recovered.local_tick == 2
    assert recovered.published_after_id is not None
    assert bundle.session.epoch_id == 1
    assert bundle.session.lifecycle is SessionLifecycle.ACTIVE


def test_partial_reset_is_terminal_and_does_not_call_later_reset_participants() -> None:
    bundle = _make_bundle(fail_actuator_reset=True)
    with pytest.raises(SessionContractError) as caught:
        bundle.session.reset(0, reason="startup")
    assert caught.value.reason == "partial_reset"
    assert caught.value.failure_frontier is bundle.session.failure_frontier
    assert caught.value.failure_frontier is not None
    assert caught.value.failure_frontier["original_exception"] == {
        "type": "RuntimeError",
        "reason": None,
        "detail": "deliberate partial-reset fixture",
        "message": "deliberate partial-reset fixture",
    }
    assert [
        (
            operation["owner"],
            operation["accepted"],
            operation["reason"],
        )
        for operation in caught.value.failure_frontier["operations"]
    ] == [
        ("controller", True, "accepted"),
        ("actuator", False, "deliberate partial-reset fixture"),
    ]
    assert bundle.session.lifecycle is SessionLifecycle.TERMINAL_INCONCLUSIVE
    assert bundle.controller.reset_calls == 1
    assert bundle.actuator.reset_calls == 1
    assert bundle.plant.reset_calls == 0
    assert bundle.imu.reset_calls == 0
    assert bundle.estimator.reset_calls == 0
    assert bundle.lifecycle_recorder.current_context is None
    actuator_events = [
        item
        for item in bundle.session.lifecycle_observations
        if item["owner"] == "actuator"
    ]
    assert [item["event"] for item in actuator_events] == ["enter", "exception"]
    assert actuator_events[-1]["exception"]["type"] == "RuntimeError"
    with pytest.raises(SessionContractError) as terminal:
        bundle.session.reset(0, reason="startup")
    assert terminal.value.reason == "terminal_inconclusive"
    assert terminal.value.failure_frontier is caught.value.failure_frontier


def test_partial_advance_observer_failure_is_terminal_with_first_cause_frontier() -> None:
    bundle = _make_bundle(observer_omit_section_at_phase=2)
    bundle.session.reset(0, reason="startup")
    probe = GuardProbe(
        probe_id="phase2-observer-failure",
        kind="old_epoch",
        envelope=bundle.session.held_envelope,
        expected_role="held_torque",
        consumer="actuator",
        expected_reason="stale_epoch",
    )
    with pytest.raises(SessionContractError) as caught:
        bundle.session.advance(
            1,
            directive=TickDirective(preflight_probes=(probe,)),
        )
    assert caught.value.reason == "observer_snapshot_invalid"
    frontier = caught.value.failure_frontier
    assert frontier is bundle.session.failure_frontier
    assert frontier is not None
    assert set(frontier) == {
        "profile_id",
        "global_tick",
        "epoch_id",
        "epoch_origin_tick",
        "local_tick",
        "epoch_origin_s",
        "timestamp_s",
        "boundary_kind",
        "event_ids",
        "held_before_id",
        "published_after_id",
        "operations",
        "guards",
        "probes",
        "wires",
        "component_call_counts",
        "original_exception",
        "lifecycle_state",
        "phase_cursor",
        "termination_status",
        "required_after_imu_capture",
        "retention_status",
        "missing_observations",
        "retention_exception",
    }
    assert frontier["global_tick"] == 1
    assert frontier["phase_cursor"] == 2
    assert frontier["lifecycle_state"] == "terminal_inconclusive"
    assert frontier["termination_status"] == "terminal_inconclusive"
    assert [operation["owner"] for operation in frontier["operations"]] == [
        "plant"
    ]
    assert [wire.role for wire in frontier["wires"]] == ["plant_state"]
    assert len(frontier["guards"]) == 1
    assert frontier["probes"] == ()
    assert frontier["component_call_counts"]["plant_step_attempts"] == 1
    assert frontier["component_call_counts"]["actuator_step_attempts"] == 0
    assert frontier["original_exception"]["type"] == "SessionContractError"
    assert frontier["original_exception"]["reason"] == (
        "observer_snapshot_invalid"
    )
    with pytest.raises(TypeError):
        frontier["operations"][0]["inputs"]["feedback"] = "mutated"
    with pytest.raises(TypeError):
        frontier["operations"][0]["scalar_inputs"][
            "external_torque_body_Nm"
        ][0] = 99.0
    with pytest.raises(TypeError):
        frontier["wires"][0].payload.q_nb[0] = 0.0
    assert frontier["wires"][0].payload.q_nb is not bundle.plant.state.q_nb
    assert bundle.session.lifecycle is SessionLifecycle.TERMINAL_INCONCLUSIVE
    counts = dict(bundle.session.call_counts)
    component_counts = (
        bundle.plant.step_calls,
        bundle.actuator.step_calls,
        bundle.imu.sample_calls,
        bundle.estimator.process_calls,
        bundle.controller.step_calls,
    )
    with pytest.raises(SessionContractError) as terminal:
        bundle.session.advance(1)
    assert terminal.value.reason == "terminal_inconclusive"
    assert terminal.value.failure_frontier is frontier
    assert dict(bundle.session.call_counts) == counts
    assert component_counts == (
        bundle.plant.step_calls,
        bundle.actuator.step_calls,
        bundle.imu.sample_calls,
        bundle.estimator.process_calls,
        bundle.controller.step_calls,
    )


def test_real_actuator_delegate_exception_is_retained_without_second_call() -> None:
    bundle = _make_bundle(fail_actuator_inner_step=True)
    bundle.session.reset(0, reason="startup")
    with pytest.raises(SessionContractError) as caught:
        bundle.session.advance(1)
    assert caught.value.reason == "component_failure"
    frontier = caught.value.failure_frontier
    assert frontier is bundle.session.failure_frontier
    assert frontier is not None
    assert [
        (operation["owner"], operation["method"], operation["accepted"])
        for operation in frontier["operations"]
    ] == [
        ("plant", "step_base", True),
        ("actuator", "step_base", False),
        ("actuator", "step", False),
    ]
    assert frontier["operations"][-1]["reason"] == (
        "deliberate inner actuator failure"
    )
    assert frontier["original_exception"] == {
        "type": "RuntimeError",
        "reason": None,
        "detail": "deliberate inner actuator failure",
        "message": "deliberate inner actuator failure",
    }
    assert bundle.actuator.step_calls == 1
    assert bundle.actuator.delegate_step_calls == 1
    counts = dict(bundle.session.call_counts)
    with pytest.raises(SessionContractError) as terminal:
        bundle.session.advance(1)
    assert terminal.value.reason == "terminal_inconclusive"
    assert terminal.value.failure_frontier is frontier
    assert bundle.actuator.step_calls == 1
    assert bundle.actuator.delegate_step_calls == 1
    assert dict(bundle.session.call_counts) == counts


def test_reset_restarts_local_clock_without_erasing_plant_audit_count() -> None:
    bundle = _make_bundle(reset_ticks=(3,))
    bundle.session.reset(0, reason="startup")
    bundle.session.advance(1)
    bundle.session.advance(2)
    assert bundle.plant.step_calls == 2
    bundle.session.reset(3, reason="scheduled_reset")
    assert bundle.plant.step_calls == 2
    assert bundle.plant.local_tick == 0

    tick4 = bundle.session.advance(4)
    tick5 = bundle.session.advance(5)
    assert bundle.plant.step_calls == 4
    assert bundle.plant.local_tick == 2

    def output_wire(boundary: Any, owner: str, method: str, field: str) -> Any:
        operation = next(
            item
            for item in boundary.operations
            if item["owner"] == owner and item["method"] == method
        )
        reference = operation["outputs"][field]
        return next(
            wire for wire in boundary.wires if wire.envelope_id == reference
        )

    origin = 3 * FakeScheduler.base_period_s
    tick4_time = origin + FakeScheduler.base_period_s
    assert output_wire(
        tick4, "plant", "step_base", "plant_state"
    ).payload.timestamp_s == pytest.approx(tick4_time, rel=0.0, abs=1.0e-15)
    assert output_wire(
        tick4, "actuator", "step_base", "feedback"
    ).payload.timestamp_s == pytest.approx(tick4_time, rel=0.0, abs=1.0e-15)

    tick5_time = origin + 2 * FakeScheduler.base_period_s
    due_outputs = (
        ("plant", "step_base", "plant_state"),
        ("actuator", "step_base", "feedback"),
        ("imu", "sample", "raw_imu"),
        ("estimator", "process", "estimate"),
        ("controller", "step", "torque_command"),
    )
    for owner, method, field in due_outputs:
        assert output_wire(
            tick5, owner, method, field
        ).payload.timestamp_s == pytest.approx(
            tick5_time, rel=0.0, abs=1.0e-15
        )


def test_event_table_is_digest_bound_deeply_frozen_and_replacement_rejected() -> None:
    source_vector = [0.1, -0.2, 0.3]
    schedule = FakeEvents(
        event_records=(
            {
                "id": "external-1",
                "type": "external_torque",
                "start_tick": 1,
                "end_tick": 2,
                "vector_Nm": source_vector,
            },
        )
    )
    expected_digest = _json_value_digest(list(schedule._events))
    bundle = _make_bundle(event_schedule=schedule)
    assert isinstance(schedule._events, tuple)
    with pytest.raises(TypeError):
        schedule._events[0]["id"] = "mutated"
    with pytest.raises(TypeError):
        schedule._events[0]["vector_Nm"][0] = 9.0
    source_vector[0] = 9.0
    assert schedule._events[0]["vector_Nm"] == (0.1, -0.2, 0.3)
    assert (
        bundle.session.functional_state()["configuration_values"][
            "event_definition_sha256"
        ]
        == expected_digest
    )

    bundle.session.reset(0, reason="startup")
    tick1 = bundle.session.advance(1)
    plant_operation = next(
        operation
        for operation in tick1.operations
        if operation["owner"] == "plant"
    )
    assert np.array_equal(
        plant_operation["scalar_inputs"]["external_torque_body_Nm"],
        np.array([0.1, -0.2, 0.3]),
    )
    counts = dict(bundle.session.call_counts)
    schedule._events = ()
    with pytest.raises(SessionContractError) as replaced:
        bundle.session.advance(2)
    assert replaced.value.reason == "event_definition_mismatch"
    assert replaced.value.failure_frontier is None
    assert bundle.session.lifecycle is SessionLifecycle.ACTIVE
    assert dict(bundle.session.call_counts) == counts


def test_public_guard_has_stale_precedence_and_allows_sealed_replay() -> None:
    stale_truth = EpochEnvelope(
        "old-truth",
        "imu",
        0,
        2,
        2,
        4,
        "evaluator_truth",
        None,
        (),
        FakeIMUSample(0.005, ZERO3.copy(), ZERO3.copy(), True),
    )
    with pytest.raises(SessionContractError) as stale:
        guard_envelope(
            stale_truth,
            active_epoch_id=1,
            expected_role="imu",
            consumer="estimator",
        )
    assert stale.value.reason == "stale_epoch"

    replay = EpochEnvelope(
        "replay",
        "imu",
        1,
        1002,
        2,
        4,
        "sealed_replay",
        None,
        (),
        FakeIMUSample(2.505, ZERO3.copy(), ZERO3.copy(), True),
    )
    guard_envelope(
        replay,
        active_epoch_id=1,
        expected_role="imu",
        consumer="estimator",
    )


def test_canonical_snapshot_uses_sorted_float_hex_and_rejects_nonfinite() -> None:
    assert float64_hex(0.0) == "0x0.0p+0"
    first = canonical_snapshot_bytes({"z": np.array([-0.0, 1.0]), "a": 2})
    second = canonical_snapshot_bytes({"a": 2, "z": [-0.0, 1.0]})
    assert first == second
    assert first == (
        b'{"a":2,"z":["-0x0.0p+0",'
        b'"0x1.0000000000000p+0"]}'
    )
    with pytest.raises(SessionContractError) as caught:
        canonical_snapshot_bytes({"bad": float("nan")})
    assert caught.value.reason == "snapshot_not_canonical"


def test_lifecycle_nested_context_inherits_parent_profile_and_operation() -> None:
    recorder = LifecycleRecorder(id_prefix="nested")
    empty_result = {
        "actor_id": None,
        "parameter_object_ref": None,
        "snapshot_ref": None,
        "capture_id": None,
        "resolved_config_path": None,
        "source_bytes_sha256": None,
        "document_sha256": None,
    }
    parent = recorder.begin(
        profile_id="S",
        operation_id="S/setup/controller-adapter",
        owner="controller",
        method="constructor",
        callsite="test.controller_adapter_constructor",
        actor_id="S/actor/controller",
        core_use=None,
        arguments={
            "kind": "constructor",
            "mode": "controller_module",
            "parameter_object_ref": None,
            "module_sha256": DUMMY_SHA,
        },
    )
    child = recorder.begin(
        profile_id=None,
        operation_id=None,
        owner="controller_core",
        method="constructor",
        callsite="test.controller_core_constructor",
        actor_id="S/actor/controller-core",
        core_use="production",
        arguments={
            "kind": "constructor",
            "mode": "explicit_parameters",
            "parameter_object_ref": "S/parameters/controller",
            "module_sha256": DUMMY_SHA,
        },
    )
    assert recorder.current_context == {
        "call_id": child.call_id,
        "profile_id": "S",
        "operation_id": "S/setup/controller-adapter",
    }
    recorder.returned(child, result=empty_result)
    assert recorder.current_context == {
        "call_id": parent.call_id,
        "profile_id": "S",
        "operation_id": "S/setup/controller-adapter",
    }
    recorder.returned(parent, result=empty_result)
    observations = recorder.observations
    assert [item["observation_index"] for item in observations] == [0, 1, 2, 3]
    assert observations[1]["parent_call_id"] == parent.call_id
    assert observations[1]["profile_id"] == "S"
    assert observations[1]["operation_id"] == "S/setup/controller-adapter"
    assert recorder.current_context is None


def test_capture_state_records_schema_shaped_observer_lifecycle_binding() -> None:
    bundle = _make_bundle()
    bundle.session.reset(0, reason="startup")
    captured = bundle.session.capture_state(
        "S/snapshot/manual", "S/capture/manual"
    )
    assert set(captured) == {
        "session",
        "plant",
        "actuator",
        "imu",
        "estimator",
        "controller",
    }
    enter, returned = bundle.session.lifecycle_observations[-2:]
    assert enter["event"] == "enter"
    assert enter["arguments"] == {
        "kind": "observer",
        "snapshot_id": "S/snapshot/manual",
        "capture_id": "S/capture/manual",
        "observer_manifest_sha256": DUMMY_SHA,
    }
    assert returned["event"] == "return"
    assert returned["result"] == {
        "actor_id": "S/actor/observer",
        "parameter_object_ref": None,
        "snapshot_ref": "S/snapshot/manual",
        "capture_id": "S/capture/manual",
        "resolved_config_path": None,
        "source_bytes_sha256": None,
        "document_sha256": None,
    }


def test_capture_state_fails_closed_without_bound_full_observer() -> None:
    bundle = _make_bundle(bind_snapshotter=False)
    bundle.session.reset(0, reason="startup")
    with pytest.raises(SessionContractError) as caught:
        bundle.session.capture_state("S/snapshot/unbound")
    assert caught.value.reason == "observer_required"
    assert len(bundle.session.lifecycle_observations) == 10


def test_functional_state_has_complete_finite_session_snapshot_shape() -> None:
    bundle = _make_bundle()
    bundle.session.reset(0, reason="startup")
    state = bundle.session.functional_state()
    assert set(state) == {
        "lifecycle",
        "needs_reset",
        "epoch_id",
        "epoch_origin_tick",
        "epoch_origin_s",
        "next_global_tick",
        "last_completed_global_tick",
        "phase_cursor",
        "envelope_sequence",
        "held",
        "feedback",
        "last_raw_sample",
        "last_sample",
        "last_estimate",
        "last_command",
        "last_plant_state",
        "last_truth",
        "last_event_ids",
        "last_event_state",
        "pending_publication",
        "pending_inputs",
        "pending_event_state",
        "configuration_values",
    }
    assert set(state["configuration_values"]) == {
        "seed",
        "initial_epoch_id",
        "scenario_origin_s",
        "plant_q_nb",
        "plant_omega_b_rad_s",
        "estimator_q_nb",
        "estimator_omega_b_rad_s",
        "actuator_actual_torque_body_Nm",
        "scheduler_definition_sha256",
        "event_definition_sha256",
        "parameter_binding_sha256",
    }
    assert state["held"]["kind"] == "torque_command"
    assert state["held"]["wire_id"] == bundle.session.held_envelope.envelope_id


def test_copy_and_rejection_snapshot_equality_remains_bit_exact_for_q() -> None:
    # The independent checker's separately recomputed-q tolerance is a
    # different policy; session-owned copy/rejection preservation stays exact.
    exact = {"session": {"q_nb": [1.0, 0.0, 0.0, 0.0]}}
    mutated_copy = {
        "session": {"q_nb": [1.0 + 1.0e-13, 0.0, 0.0, 0.0]}
    }
    assert canonical_snapshot_bytes(exact) != canonical_snapshot_bytes(mutated_copy)
    with pytest.raises(SessionContractError) as caught:
        IntegrationSession._assert_same_snapshot(exact, mutated_copy, "q-copy")
    assert caught.value.reason == "rejection_mutated_state"


def test_driver_component_count_snapshot_accepts_readonly_session_mapping() -> None:
    session_counts = {
        key: index
        for index, key in enumerate(evidence_driver._SESSION_COUNTER_TO_EVIDENCE)
    }
    session = SimpleNamespace(call_counts=MappingProxyType(session_counts))
    lifecycle = [
        {
            "profile_id": "S",
            "event": "return",
            "method": "constructor",
            "owner": "plant",
        },
        {
            "profile_id": "other",
            "event": "return",
            "method": "constructor",
            "owner": "actuator",
        },
        {
            "profile_id": "S",
            "event": "enter",
            "method": "constructor",
            "owner": "imu",
        },
    ]

    actual = evidence_driver._component_count_snapshot(
        session,
        profile_id="S",
        lifecycle=lifecycle,
    )
    expected = {
        "plant_step_base": 5,
        "actuator_step_base": 6,
        "imu_sample": 7,
        "estimator_process": 8,
        "estimator_accepted": 9,
        "estimator_rejected": 10,
        "controller_step": 11,
        "controller_accepted": 12,
        "controller_rejected": 13,
        "plant_reset": 0,
        "actuator_reset": 1,
        "imu_reset": 2,
        "estimator_reset": 3,
        "controller_reset": 4,
        "plant_constructor": 1,
        "actuator_constructor": 0,
        "imu_constructor": 0,
        "estimator_constructor": 0,
        "controller_adapter_constructor": 0,
        "controller_core_constructor": 0,
    }
    assert actual == expected
    assert len(actual) == 20


def test_driver_component_count_snapshot_rejects_invalid_readonly_counters() -> None:
    valid = {
        key: 0 for key in evidence_driver._SESSION_COUNTER_TO_EVIDENCE
    }
    invalid_cases = []
    missing = dict(valid)
    missing.pop(next(iter(missing)))
    invalid_cases.append((missing, "session_counter_keys_mismatch"))
    extra = {**valid, "unexpected_counter": 0}
    invalid_cases.append((extra, "session_counter_keys_mismatch"))
    boolean = dict(valid)
    boolean[next(iter(boolean))] = True
    invalid_cases.append((boolean, "session_counter_value_invalid"))
    negative = dict(valid)
    negative[next(iter(negative))] = -1
    invalid_cases.append((negative, "session_counter_value_invalid"))

    for values, reason in invalid_cases:
        session = SimpleNamespace(call_counts=MappingProxyType(values))
        with pytest.raises(evidence_driver.EvidenceDriverError, match=reason):
            evidence_driver._component_count_snapshot(
                session,
                profile_id="S",
                lifecycle=(),
            )


def test_driver_failure_materializers_detach_recursive_readonly_mappings() -> None:
    def recursive_proxy(value: Any) -> Any:
        if isinstance(value, dict):
            return MappingProxyType(
                {key: recursive_proxy(item) for key, item in value.items()}
            )
        if isinstance(value, list):
            return tuple(recursive_proxy(item) for item in value)
        return value

    session_delta = {
        key: 0 for key in evidence_driver._SESSION_COUNTER_TO_EVIDENCE
    }
    snapshot = {"session": {"phase_cursor": 4, "nested": {"value": 1}}}
    probe = {
        "probe_id": "failure-probe",
        "kind": "stale_timestamp",
        "global_tick": 7,
        "phase": 4,
        "consumer_operation_id": "operation",
        "role": "imu",
        "checked_refs": {},
        "candidate_id": "candidate",
        "original_legal_id": "legal",
        "source_truth_id": None,
        "source_field": None,
        "target_field": None,
        "derivation_site": None,
        "guard_site": "estimator.consume.input_bundle",
        "accepted": False,
        "reason": "stale",
        "before_snapshot_id": "probe/before",
        "before_capture_id": "probe/before/capture",
        "after_snapshot_id": "probe/after",
        "after_capture_id": "probe/after/capture",
        "before_snapshot": snapshot,
        "after_snapshot": snapshot,
        "component_call_delta": session_delta,
    }
    operation = {
        "operation_id": "operation",
        "owner": "estimator",
        "method": "process",
        "phase": 4,
        "attempt_kind": "injected_invalid",
        "inputs": {"adapted_imu": "candidate"},
        "outputs": {},
        "scalar_inputs": {"nested": {"value": 1}},
        "reset_inputs": None,
        "accepted": False,
        "reason": "stale",
        "guard_ref": "guard",
        "before_snapshot_id": "operation/before",
        "before_capture_id": "operation/before/capture",
        "after_snapshot_id": "operation/after",
        "after_capture_id": "operation/after/capture",
        "before_snapshot": snapshot,
        "after_snapshot": snapshot,
    }
    lifecycle = (
        {
            "profile_id": "S",
            "owner": "observer",
            "method": "capture_snapshot",
            "event": "return",
            "observation_index": 1,
            "result": {"capture_id": "probe/before/capture"},
        },
        {
            "profile_id": "S",
            "owner": "observer",
            "method": "capture_snapshot",
            "event": "return",
            "observation_index": 2,
            "result": {"capture_id": "probe/after/capture"},
        },
    )

    primary = RuntimeError("primary failure")
    observed_frontier = {
        "profile_id": "S",
        "global_tick": 7,
        "epoch_id": 2,
        "epoch_origin_tick": 6,
        "local_tick": 1,
        "epoch_origin_s": 0.06,
        "timestamp_s": 0.07,
        "boundary_kind": "ordinary",
        "event_ids": ["event"],
        "held_before_id": "held/previous",
        "published_after_id": None,
        "operations": [operation],
        "guards": [],
        "probes": [probe],
        "wires": [],
        "component_call_counts": session_delta,
        "original_exception": evidence_driver._exception_observation(primary),
        "lifecycle_state": SessionLifecycle.TERMINAL_INCONCLUSIVE.value,
        "phase_cursor": 4,
        "termination_status": SessionLifecycle.TERMINAL_INCONCLUSIVE.value,
        "required_after_imu_capture": None,
        "retention_status": "complete",
        "missing_observations": [],
        "retention_exception": None,
    }

    def retain(raw_frontier: Mapping[str, Any]) -> dict[str, Any]:
        record = evidence_driver._ProfileRecord.__new__(
            evidence_driver._ProfileRecord
        )
        record.profile = {"profile_id": "S"}
        record.canonicalize = canonical_snapshot_value
        record.snapshots = evidence_driver._SnapshotStore()
        record.wires = []
        record.wire_by_id = {}
        record.failure_frontiers = []
        record.retention_failures = []
        record.retain_failure_frontier(
            primary,
            lifecycle=lifecycle,
            capture_site="driver.test",
            observed_frontier=raw_frontier,
        )
        return {
            "failure_frontiers": record.failure_frontiers,
            "snapshots": record.snapshots.values,
        }

    readonly_frontier = recursive_proxy(observed_frontier)
    readonly_probe = readonly_frontier["probes"][0]
    frontier_before = canonical_snapshot_bytes(readonly_frontier)
    from_dict = retain(observed_frontier)
    from_readonly = retain(readonly_frontier)

    assert from_readonly == from_dict
    assert from_readonly["failure_frontiers"][0]["published_after_ref"] == (
        "held/previous"
    )
    assert from_readonly["failure_frontiers"][0]["original_exception"] == (
        evidence_driver._exception_observation(primary)
    )
    assert isinstance(json.dumps(from_readonly, sort_keys=True), str)
    assert canonical_snapshot_bytes(readonly_frontier) == frontier_before
    with pytest.raises(
        evidence_driver.EvidenceDriverError, match="field_type_mismatch"
    ):
        evidence_driver._require_mapping(readonly_probe, "wire")
