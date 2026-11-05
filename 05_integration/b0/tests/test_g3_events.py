"""Independent endpoint and ownership checks for G3 event adapters."""

from __future__ import annotations

import numpy as np
import pytest

from events import EventContractError, EventSchedule


def _command_event() -> dict:
    return {
        "id": "step_x",
        "type": "command_step",
        "axis": "x",
        "value_rad": 0.2,
        "start_tick": 10,
        "end_tick": 20,
        "post_event_action": "return_axis_to_zero",
    }


def test_event_endpoints_are_half_open_and_command_returns_to_zero() -> None:
    schedule = EventSchedule([_command_event()])
    assert schedule.active_at(9).event_ids == ()
    assert schedule.active_at(10).event_ids == ("step_x",)
    assert schedule.active_at(19).event_ids == ("step_x",)
    assert schedule.active_at(20).event_ids == ()
    assert schedule.active_at(10).command_q_nb[1] > 0.0
    assert np.array_equal(schedule.active_at(20).command_q_nb, [1.0, 0.0, 0.0, 0.0])


def test_schedule_rejects_declaration_reordering_and_every_overlap() -> None:
    later = _command_event()
    later.update(id="later", start_tick=30, end_tick=40)
    with pytest.raises(EventContractError, match="nondecreasing"):
        EventSchedule([later, _command_event()])
    torque = {
        "id": "torque",
        "type": "external_torque",
        "vector_Nm": [0.1, 0.0, 0.0],
        "start_tick": 15,
        "end_tick": 16,
    }
    with pytest.raises(EventContractError, match="overlap is not approved"):
        EventSchedule([_command_event(), torque])


def test_external_torque_and_measurement_events_have_separate_owners() -> None:
    events = [
        {
            "id": "torque",
            "type": "external_torque",
            "vector_Nm": [0.1, -0.2, 0.3],
            "start_tick": 2,
            "end_tick": 4,
        },
        {
            "id": "bias",
            "type": "imu_bias",
            "gyro_bias_rad_s": [0.4, 0.5, 0.6],
            "accelerometer_bias_m_s2": [0.7, 0.8, 0.9],
            "application": "replace_nominal_bias",
            "start_tick": 5,
            "end_tick": 7,
        },
        {
            "id": "force",
            "type": "specific_force_disturbance",
            "vector_m_s2": [2.0, 0.0, 0.0],
            "application": "additive_to_nominal_specific_force",
            "start_tick": 8,
            "end_tick": 10,
        },
    ]
    schedule = EventSchedule(events)
    assert np.array_equal(schedule.active_at(2).external_torque_body_Nm, [0.1, -0.2, 0.3])
    raw_gyro = np.array([1.1, 2.2, 3.3])
    raw_force = np.array([4.4, 5.5, 6.6])
    gyro, force = schedule.adapt_measurement(
        raw_gyro,
        raw_force,
        schedule.active_at(5),
        [0.1, 0.2, 0.3],
        [0.4, 0.5, 0.6],
    )
    assert np.allclose(gyro, [1.4, 2.5, 3.6])
    assert np.allclose(force, [4.7, 5.8, 6.9])
    disturbed_gyro, disturbed_force = schedule.adapt_measurement(
        raw_gyro,
        raw_force,
        schedule.active_at(8),
        [0.1, 0.2, 0.3],
        [0.4, 0.5, 0.6],
    )
    assert np.array_equal(disturbed_gyro, raw_gyro)
    assert np.array_equal(disturbed_force, raw_force + [2.0, 0.0, 0.0])


def test_invalid_and_reset_events_preserve_explicit_ownership() -> None:
    invalid = {
        "id": "bad_dt",
        "type": "invalid_input",
        "invalid_kind": "negative_dt",
        "start_tick": 4,
        "end_tick": 5,
    }
    reset = {
        "id": "reset",
        "type": "reset",
        "target": "all_components",
        "start_tick": 8,
        "end_tick": 9,
    }
    schedule = EventSchedule([invalid, reset])
    assert schedule.active_at(4).invalid_event["id"] == "bad_dt"
    assert schedule.active_at(4).reset_event is None
    assert schedule.active_at(8).reset_event["id"] == "reset"
    assert schedule.active_at(8).invalid_event is None
