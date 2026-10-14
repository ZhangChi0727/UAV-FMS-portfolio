"""Emit reviewable G2-B controller component evidence.

The artifact is deliberately a component-level numerical trace.  It records
the module/build identity, approved configuration identities, independent
one-step oracles, paired-command timing, and rejection atomicity.  It does not
claim G3 closed-loop performance, HIL, board execution, or flight evidence.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from fractions import Fraction
import hashlib
import importlib
import importlib.util
import json
import math
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any
import warnings
import xml.etree.ElementTree as ET


ABS_TOL = 1e-12


S0_CASE_NODES: dict[str, tuple[str, ...]] = {
    "B-ATT-01": ("b0_controller::attitude_error_axes_and_small_angle",),
    "B-ATT-02": ("b0_controller::attitude_error_nonidentity_multiaxis",),
    "B-ATT-03": ("b0_controller::attitude_error_antipodes_and_half_turn",),
    "B-RATE-01": ("b0_controller::outer_loop_and_rate_clamp",),
    "B-RATE-02": ("b0_controller::rate_pid_terms",),
    "B-DERIV-01": ("b0_controller::measurement_derivative_filter",),
    "B-DERIV-02": ("b0_controller::derivative_first_step_and_reset",),
    "B-LIMIT-01": ("b0_controller::torque_limit_boundaries",),
    "B-LIMIT-02": ("b0_controller::torque_command_atomic_bundle",),
    "B-AW-01": ("b0_controller::antiwindup_conditional_integration",),
    "B-AW-02": ("b0_controller::antiwindup_backcalculation_terms",),
    "B-AW-03": ("b0_controller::antiwindup_bounds_and_release",),
    "B-PAIR-01": ("b0_controller::paired_feedback_three_ticks",),
    "B-PAIR-02": ("b0_controller::paired_feedback_rejections",),
    "B-TIME-01": (
        "b0_controller::time_grid_and_dt_rejections",
        "b0_controller::integer_grid_remains_stable_beyond_prior_drift_failure",
        "python/tests/test_binding.py::test_step_rejects_nonreal_bool_and_lossy_dt_atomically_then_retries",
    ),
    "B-TIME-02": ("b0_controller::retry_and_missed_tick_recovery",),
    "B-INVALID-01": (
        "b0_controller::invalid_numeric_inputs",
        "python/tests/test_binding.py::test_binding_rejects_wrong_shape_type_and_nonfinite",
        "python/tests/test_binding.py::test_scalar_binding_rejects_nonreal_bool_and_lossy_coercion_atomically",
        "python/tests/test_binding.py::test_vector_binding_rejects_nonreal_bool_and_lossy_elements_atomically",
        "python/tests/test_binding.py::test_step_rejects_nonreal_bool_and_lossy_dt_atomically_then_retries",
        "python/tests/test_binding.py::test_contract_error_exposes_stable_reason_and_atomic_retry",
        "python/tests/test_binding.py::test_invalid_output_feedback_is_atomic",
        "python/tests/test_adapter.py::test_command_validity_is_explicit_bool_and_true",
        "python/tests/test_adapter.py::test_estimate_validity_wrong_type_is_rejected",
        "python/tests/test_adapter.py::test_missing_frozen_field_is_atomic_and_valid_retry_succeeds",
        "python/tests/test_adapter.py::test_adapter_rejects_nonreal_bool_and_lossy_scalars_without_state_change",
    ),
    "B-INVALID-02": (
        "python/tests/test_binding.py::test_integer_bounds_and_input_copy",
        "python/tests/test_adapter.py::test_reset_epoch_type_and_range_are_not_coerced",
    ),
    "B-RESET-01": ("b0_controller::reset_clears_all_controller_state",),
    "B-RESET-02": ("b0_controller::reset_epoch_and_replay_rejections",),
    "B-BIND-01": (
        "python/tests/test_binding.py::test_cpp_python_parity_and_module_identity",
        "python/tests/test_binding.py::test_complete_diagnostics_and_snapshot_are_read_only_copies",
        "python/tests/test_binding.py::test_contract_error_exposes_stable_reason_and_atomic_retry",
        "python/tests/test_binding.py::test_scalar_binding_accepts_losslessly_representable_real_scalars",
    ),
    "B-BIND-02": (
        "python/tests/test_adapter.py::test_real_g2a_g1_adapter_and_actuator_consumption",
    ),
    "B-DETECT-01": (
        "b0_controller::mutation::attitude_feedback_sign_reversed",
        "b0_controller::mutation::antiwindup_backcalculation_sign_reversed",
    ),
    "B-DETECT-02": (
        "b0_controller::mutation::antiwindup_disabled",
        "b0_controller::mutation::lag_uses_current_limited",
    ),
    "B-CONFIG-01": (
        "python/tests/test_config.py::test_actual_approved_config_and_authoritative_g0_load",
        "python/tests/test_config.py::test_line_endings_and_authoritative_validation",
    ),
    "B-CONFIG-02": (
        "python/tests/test_config.py::test_configuration_fail_closed_for_g0",
        "python/tests/test_config.py::test_configuration_fail_closed_for_implementation_config",
    ),
}


MUTATION_ORACLES: dict[str, str] = {
    "b0_controller::mutation::attitude_feedback_sign_reversed": (
        "attitude_error_axes_and_small_angle"
    ),
    "b0_controller::mutation::antiwindup_backcalculation_sign_reversed": (
        "antiwindup_backcalculation_terms"
    ),
    "b0_controller::mutation::antiwindup_disabled": (
        "antiwindup_backcalculation_terms"
    ),
    "b0_controller::mutation::lag_uses_current_limited": (
        "antiwindup_backcalculation_terms"
    ),
}


def _case_contract(
    kind: str,
    *,
    input_keys: tuple[str, ...] = (),
    units: tuple[str, ...] = (),
    labels: tuple[str, ...] = (),
    expected_values: tuple[float, ...] = (),
    expected_value_keys: tuple[str, ...] = (),
    actual_value_keys: tuple[str, ...] = (),
) -> dict[str, Any]:
    contract: dict[str, Any] = {
        "kind": kind,
        "input_keys": input_keys,
        "units": units,
    }
    if labels:
        contract["labels"] = labels
    if expected_values:
        contract["expected_values"] = expected_values
    if expected_value_keys:
        contract["expected_value_keys"] = expected_value_keys
    if actual_value_keys:
        contract["actual_value_keys"] = actual_value_keys
    return contract


def _build_s0_case_manifest() -> dict[str, dict[str, dict[str, Any]]]:
    """Return the independent, closed list of raw cases required by every S0 row."""

    manifest: dict[str, dict[str, dict[str, Any]]] = {
        row_id: {} for row_id in S0_CASE_NODES
    }

    def add(
        row_id: str,
        case_ids: tuple[str, ...],
        kind: str,
        *,
        input_keys: tuple[str, ...] = (),
        units: tuple[str, ...] = (),
        labels: tuple[str, ...] = (),
        expected_values: tuple[float, ...] = (),
        expected_value_keys: tuple[str, ...] = (),
        actual_value_keys: tuple[str, ...] = (),
    ) -> None:
        if not units:
            if kind == "rejection_atomic":
                units = ("contract reason", "controller state snapshot")
            elif kind == "binding_rejection_atomic":
                units = ("Python exception", "warning count", "state snapshot")
        contract = _case_contract(
            kind,
            input_keys=input_keys,
            units=units,
            labels=labels,
            expected_values=expected_values,
            expected_value_keys=expected_value_keys,
            actual_value_keys=actual_value_keys,
        )
        for case_id in case_ids:
            if case_id in manifest[row_id]:
                raise RuntimeError(f"duplicate S0 case contract: {row_id}/{case_id}")
            manifest[row_id][case_id] = contract

    torque_axes = tuple(f"requested_torque_axis_{axis}" for axis in range(3))
    attitude_axis_cases = tuple(
        f"axis-{axis}-angle-{sign * magnitude:.12g}"
        for axis in range(3)
        for magnitude in (1e-8, 0.1)
        for sign in (-1.0, 1.0)
    )
    add(
        "B-ATT-01",
        attitude_axis_cases,
        "numeric",
        input_keys=("axis", "angle_rad"),
        units=("N m",) * 3,
        labels=torque_axes,
    )
    add(
        "B-ATT-02",
        ("nonidentity-multiaxis",),
        "numeric",
        input_keys=("q_nb_command", "q_nb_estimate"),
        units=("N m",) * 3,
        labels=torque_axes,
    )
    add(
        "B-ATT-03",
        tuple(f"half-turn-axis-{axis}-antipode" for axis in range(3)),
        "numeric",
        input_keys=("q", "minus_q"),
        units=("N m",) * 6,
        labels=tuple(f"q_requested_axis_{axis}" for axis in range(3))
        + tuple(f"minus_q_requested_axis_{axis}" for axis in range(3)),
    )
    add(
        "B-ATT-03",
        ("mixed-half-turn-signs-and-values",),
        "numeric",
        input_keys=("q_nb_command", "q_nb_estimate"),
        units=("N m",) * 3,
        labels=torque_axes,
        expected_values=(0.16, -0.16, 0.09),
    )

    add(
        "B-RATE-01",
        tuple(f"outer-clamp-{value:+.2f}" for value in (-0.3, 0.3, -0.25, 0.25)),
        "numeric",
        input_keys=("q_x", "rate_limit_rad_s"),
        units=("N m",),
        labels=("requested_torque_x",),
    )
    add(
        "B-RATE-02",
        ("proportional-only",),
        "numeric",
        input_keys=("kd", "ki", "kp", "omega_x_rad_s"),
        units=("N m",) * 4,
        labels=("P", "I_before", "D", "request"),
    )
    add(
        "B-RATE-02",
        ("integral-only",),
        "numeric",
        input_keys=("dt_s", "ki", "omega_x_rad_s"),
        units=("N m",) * 4,
        labels=("P", "I_before", "D", "request"),
    )
    add(
        "B-RATE-02",
        ("derivative-only",),
        "numeric",
        input_keys=("dt_s", "kd", "omega_x_rad_s"),
        units=("N m",) * 4,
        labels=("P", "I_before", "D", "request"),
    )
    add(
        "B-DERIV-01",
        ("constant-step-command-only-trajectory",),
        "numeric",
        input_keys=("alpha", "command_step_at_tick", "rates_rad_s"),
        units=("rad s^-2",) * 4,
        labels=tuple(f"D_filtered_tick_{tick}" for tick in range(1, 5)),
    )
    add(
        "B-DERIV-02",
        ("first-step-history-reset",),
        "numeric",
        input_keys=("rates_rad_s", "reset_before_sample"),
        units=("rad s^-2",) * 3,
        labels=("raw_first", "raw_second", "raw_after_reset"),
    )

    limit_cases = tuple(
        f"axis-{axis}-{sign:+.0f}-{location}"
        for axis in range(3)
        for sign in (-1.0, 1.0)
        for location in ("below", "exact", "beyond")
    )
    add(
        "B-LIMIT-01",
        limit_cases,
        "numeric",
        input_keys=("axis", "limit_Nm", "request_Nm"),
        units=("N m", "N m", "boolean"),
        labels=("request", "limited", "saturated_as_0_or_1"),
    )
    add(
        "B-LIMIT-02",
        ("same-tick-command-diagnostic-bundle",),
        "numeric",
        input_keys=("epoch_id", "request_x_Nm", "timestamp_s"),
        units=("N m", "N m", "N m", "N m", "boolean", "boolean", "s"),
        labels=(
            "output_request_x",
            "diagnostic_request_x",
            "output_limited_x",
            "diagnostic_limited_x",
            "output_saturated_x",
            "diagnostic_saturated_x",
            "output_timestamp",
        ),
    )

    add(
        "B-AW-01",
        ("push-exit-opposite-push",),
        "numeric",
        input_keys=("ki", "omega_x_rad_s", "torque_limit_Nm"),
        units=("boolean", "N m s^-1", "N m") * 3,
        labels=tuple(
            f"tick{tick}_{field}"
            for tick in range(1, 4)
            for field in ("saturated", "conditional_rate", "integral_after")
        ),
    )
    add(
        "B-AW-02",
        ("limit-only", "lag-only", "limit-and-lag"),
        "numeric",
        input_keys=(
            "actual_Nm",
            "held_limited_Nm",
            "kaw_lag_per_s",
            "kaw_limit_per_s",
            "limited_Nm",
            "request_Nm",
        ),
        units=("N m s^-1", "N m s^-1", "N m"),
        labels=("limit_rate", "lag_rate", "integral_after"),
    )
    aw_release_labels = (
        "tick1_saturated",
        "tick1_limit_rate",
        "tick1_lag_rate",
        "tick1_integral_after",
        "tick2_saturated",
        "tick2_conditional_rate",
        "tick2_integral_after",
        "tick3_saturated",
        "tick3_conditional_rate",
        "tick3_limit_rate",
        "tick3_lag_rate",
        "tick3_integral_after",
        "tick4_saturated",
        "tick4_conditional_rate",
        "tick4_limit_rate",
        "tick4_lag_rate",
        "tick4_integral_after",
    )
    add(
        "B-AW-03",
        tuple(
            f"axis-{axis}-sign-{sign:+.0f}-saturate-release"
            for axis in range(3)
            for sign in (-1.0, 1.0)
        ),
        "numeric",
        input_keys=("axis", "saturation_rate_rad_s", "release_rate_rad_s"),
        units=(
            "boolean",
            "N m s^-1",
            "N m s^-1",
            "N m",
            "boolean",
            "N m s^-1",
            "N m",
            "boolean",
            "N m s^-1",
            "N m s^-1",
            "N m s^-1",
            "N m",
            "boolean",
            "N m s^-1",
            "N m s^-1",
            "N m s^-1",
            "N m",
        ),
        labels=aw_release_labels,
    )

    add(
        "B-PAIR-01",
        ("three-consecutive-due-ticks",),
        "numeric",
        input_keys=("actual_torque_x_Nm", "command_angle_x_rad", "omega_x_rad_s"),
        units=("s", "s", "s", "N m", "N m", "N m"),
        labels=(
            "pair_timestamp_tick1",
            "pair_timestamp_tick2",
            "pair_timestamp_tick3",
            "request_tick1",
            "request_tick2",
            "request_tick3",
        ),
    )
    add(
        "B-PAIR-02",
        (
            "superseded-reset-command",
            "unknown-command-timestamp",
            "future-command-timestamp",
            "old-epoch",
            "fake-limited-value",
            "fake-saturation-status",
            "out-of-limit-actual",
        ),
        "rejection_atomic",
        input_keys=("feedback", "timestamp_s"),
    )
    add(
        "B-PAIR-02",
        ("nonfinite-actual-binding-boundary",),
        "exact",
        input_keys=("actual_torque_body_Nm",),
        units=("binding exception and controller snapshot",),
    )

    add(
        "B-TIME-01",
        ("off-grid-3.004", "off-grid-3.006"),
        "rejection_atomic",
        input_keys=("expected_timestamp_s", "timestamp_s"),
    )
    add(
        "B-TIME-01",
        ("invalid-dt-zero", "invalid-dt-negative"),
        "rejection_atomic",
        input_keys=("dt_class", "expected_period_s"),
    )
    add(
        "B-TIME-01",
        (
            "nonfinite-dt-nan-binding-boundary",
            "nonfinite-dt-inf-binding-boundary",
        ),
        "binding_rejection_atomic",
        input_keys=("dt_class", "expected_period_s"),
    )
    add(
        "B-TIME-01",
        (
            "strict-dt-bool-binding-boundary",
            "strict-dt-complex-binding-boundary",
            "strict-dt-nonexact-rational-binding-boundary",
            "strict-dt-lossy-integer-binding-boundary",
        ),
        "binding_rejection_atomic",
        input_keys=("dt_class", "dt_repr"),
    )
    add(
        "B-TIME-01",
        ("strict-dt-valid-same-tick-retry",),
        "exact",
        input_keys=("rejected_dt_class", "retry_dt_s"),
        units=("controller state snapshot",),
    )
    add(
        "B-TIME-01",
        ("integer-grid-4000-tick-summary",),
        "numeric",
        input_keys=("tick_count", "period_s", "origin_s"),
        units=("s", "tick", "s"),
        labels=("final_timestamp", "snapshot_tick_index", "expected_next_timestamp"),
    )
    add(
        "B-TIME-01",
        ("unrepresentable-huge-epoch-origin",),
        "rejection_atomic",
        input_keys=("controller_period_s", "epoch_timestamp_s"),
    )
    add(
        "B-TIME-02",
        ("invalid-then-same-tick-retry",),
        "rejection_atomic",
        input_keys=("estimate_valid", "timestamp_s"),
    )
    add(
        "B-TIME-02",
        ("duplicate", "early", "missed-tick-requires-reset"),
        "rejection_atomic",
        input_keys=("expected_timestamp_s", "timestamp_s"),
    )
    add(
        "B-TIME-02",
        ("corrected-retry-equals-clean-twin", "next-due-tick-equals-clean-twin"),
        "exact",
        input_keys=("timestamp_s",),
        units=("controller state snapshot",),
    )

    add(
        "B-INVALID-01",
        (
            "command-valid-false",
            "estimate-valid-false",
            "zero-command-quaternion",
            "nonunit-command-quaternion",
            "out-of-limit-feedback",
        ),
        "rejection_atomic",
        input_keys=("mutation",),
    )
    add(
        "B-INVALID-01",
        ("derived-overflow",),
        "rejection_atomic",
        input_keys=("attitude_kp_x", "rate_kp_x"),
    )
    add(
        "B-INVALID-01",
        tuple(f"binding-setter-rejection-{index}" for index in range(13)),
        "binding_rejection_atomic",
        input_keys=("type", "attribute", "value_repr"),
    )
    add(
        "B-INVALID-01",
        tuple(
            f"adapter-strict-{field}"
            for field in (
                "command-timestamp",
                "estimate-timestamp",
                "dt",
                "command-quaternion",
                "estimate-rate",
                "feedback-torque",
            )
        ),
        "binding_rejection_atomic",
        input_keys=("adapter_entry", "value_type", "value_repr"),
    )
    add(
        "B-INVALID-02",
        (f"int64-bound-{2**63 - 1}", f"int64-bound-{-(2**63)}"),
        "exact",
        input_keys=("assigned_epoch_id",),
        units=("signed int64 epoch",),
    )
    add(
        "B-INVALID-02",
        (f"out-of-int64-{2**63}", f"out-of-int64-{-(2**63) - 1}"),
        "exact",
        input_keys=("assigned_epoch_id",),
        units=("boolean",),
    )
    add(
        "B-INVALID-02",
        ("caller-and-output-list-mutation-isolated",),
        "exact",
        input_keys=("mutated_caller_value", "mutated_returned_value"),
        units=("scalar-first quaternion",),
    )

    snapshot_keys = (
        "reset",
        "epoch_id",
        "tick_index",
        "epoch_origin_s",
        "expected_timestamp_s",
        "integral_Nm",
        "derivative_filtered_rad_s2",
        "previous_rate_rad_s",
        "has_previous_rate",
        "expected_held_command",
        "last_diagnostics",
    )
    add(
        "B-RESET-01",
        ("nonzero-state-then-complete-reset",),
        "exact",
        input_keys=("before_reset", "new_epoch_id", "reset_timestamp_s"),
        units=("complete reset output and controller state",),
        expected_value_keys=("reset_output", "state"),
        actual_value_keys=("reset_output", "state"),
    )
    add(
        "B-RESET-02",
        ("duplicate-epoch", "lower-epoch", "equal-last-step-time"),
        "rejection_atomic",
        input_keys=("epoch_id", "timestamp_s"),
    )
    add(
        "B-RESET-02",
        ("prior-epoch-feedback-replay",),
        "rejection_atomic",
        input_keys=("active_epoch", "feedback_epoch"),
    )

    add(
        "B-BIND-01",
        ("cpp-python-binding-parity",),
        "numeric",
        input_keys=("q_nb_command", "q_nb_estimate", "module_path"),
        units=("N m", "s", "epoch", "boolean"),
        labels=("requested_torque_x", "timestamp", "epoch_id", "diagnostics_accepted"),
    )
    diagnostic_fields = (
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
    )
    add(
        "B-BIND-01",
        ("approved-diagnostics-all-numeric-fields",),
        "numeric",
        input_keys=("angle_rad", "dt_s", "initial_integral_Nm"),
        units=tuple(
            unit
            for field in diagnostic_fields
            for unit in (
                (
                    "rad s^-1"
                    if field == "rate_error_rad_s"
                    else "rad s^-2"
                    if field in {"derivative_raw_rad_s2", "derivative_filtered_rad_s2"}
                    else "N m s^-1"
                    if field.endswith("_rate_Nm_s")
                    else "boolean"
                    if field == "saturated"
                    else "N m"
                ),
            )
            for _axis in range(3)
        )
        + ("epoch", "tick"),
        labels=tuple(
            f"{field}[{axis}]" for field in diagnostic_fields for axis in range(3)
        )
        + ("epoch_id", "tick_index"),
    )
    add(
        "B-BIND-01",
        ("approved-diagnostics-status-fields",),
        "exact",
        input_keys=("accepted_step_timestamp_s",),
        units=("diagnostic status",),
        expected_value_keys=("accepted", "reason"),
        actual_value_keys=("accepted", "reason"),
    )
    add(
        "B-BIND-01",
        ("diagnostics-and-snapshots-are-copies",),
        "exact",
        input_keys=("mutated_output_copy_x", "mutated_snapshot_copy_x"),
        units=("controller state snapshot",),
        expected_value_keys=snapshot_keys,
        actual_value_keys=snapshot_keys,
    )
    add(
        "B-BIND-01",
        ("lossless-real-scalar-acceptance",),
        "numeric",
        input_keys=("values",),
        units=("s",) * 8,
        labels=tuple(f"accepted_value_{index}" for index in range(8)),
    )
    add(
        "B-BIND-02",
        ("real-g2a-estimate-g1-feedback-and-actuator-consumption",),
        "exact",
        input_keys=("estimate_type", "feedback_type"),
        units=("interface identity and seconds",),
        expected_value_keys=(
            "reset_is_g1_torque_command",
            "output_is_g1_torque_command",
            "consumed_command_timestamp_s",
        ),
        actual_value_keys=(
            "reset_is_g1_torque_command",
            "output_is_g1_torque_command",
            "consumed_command_timestamp_s",
        ),
    )

    for row_id in ("B-DETECT-01", "B-DETECT-02"):
        add(
            row_id,
            tuple(node.rsplit("::", 1)[-1] for node in S0_CASE_NODES[row_id]),
            "exact",
            input_keys=("mutation_node", "unchanged_oracle_node"),
            units=("mutation detection outcome",),
        )
    add(
        "B-CONFIG-01",
        ("authoritative-load-lf", "authoritative-load-crlf", "authoritative-load-cr"),
        "numeric",
        input_keys=("line_ending",),
        units=("s", "N m", "s^-1"),
        labels=("controller_period", "torque_limit_x", "kaw_limit_x"),
    )
    add(
        "B-CONFIG-02",
        (
            "g0-missing",
            "g0-changed",
            "g0-wrong-version",
            "g0-bad-gain",
            "implementation-missing",
            "implementation-changed",
            "implementation-wrong-version",
            "implementation-bad-tolerance",
        ),
        "exact",
        input_keys=("authority", "mutation"),
        units=("exception type and message",),
        expected_value_keys=("exception_type", "message"),
        actual_value_keys=("exception_type", "message"),
    )

    if set(manifest) != set(S0_CASE_NODES) or any(
        not cases for cases in manifest.values()
    ):
        raise RuntimeError("incomplete S0 case manifest")
    return manifest


S0_CASE_MANIFEST = _build_s0_case_manifest()


def _numeric_sample(
    case_id: str,
    input_value: dict[str, Any],
    labels: list[str],
    expected: list[float],
    actual: list[float],
    units: list[str],
    *,
    absolute_tolerance: float = ABS_TOL,
    relative_tolerance: float = 0.0,
) -> dict[str, Any]:
    errors = [abs(float(a) - float(e)) for a, e in zip(actual, expected)]
    result = len(actual) == len(expected) == len(labels) == len(units) and all(
        math.isclose(
            float(a),
            float(e),
            rel_tol=relative_tolerance,
            abs_tol=absolute_tolerance,
        )
        for a, e in zip(actual, expected)
    )
    return {
        "case_id": case_id,
        "input": input_value,
        "independent_expected": {"labels": labels, "values": expected},
        "actual": {"values": actual},
        "units": units,
        "absolute_tolerance": absolute_tolerance,
        "relative_tolerance": relative_tolerance,
        "comparison": {
            "kind": "numeric",
            "max_absolute_error": max(errors, default=0.0),
            "result": result,
        },
    }


def _exact_sample(
    case_id: str,
    input_value: dict[str, Any],
    expected: Any,
    actual: Any,
    unit: str,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "input": input_value,
        "independent_expected": {"value": expected},
        "actual": {"value": actual},
        "units": [unit],
        "absolute_tolerance": 0.0,
        "relative_tolerance": 0.0,
        "comparison": {"kind": "exact", "result": actual == expected},
    }


def _rejection_sample(
    case_id: str,
    input_value: dict[str, Any],
    expected_reason: str,
    actual_reason: str | None,
    snapshot_before: dict[str, Any],
    snapshot_after: dict[str, Any],
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "input": input_value,
        "independent_expected": {
            "reason": expected_reason,
            "state_change": "none",
        },
        "actual": {
            "reason": actual_reason,
            "snapshot_before": snapshot_before,
            "snapshot_after": snapshot_after,
        },
        "units": ["contract reason", "controller state snapshot"],
        "absolute_tolerance": 0.0,
        "relative_tolerance": 0.0,
        "comparison": {
            "kind": "rejection_atomic",
            "result": actual_reason == expected_reason
            and snapshot_before == snapshot_after,
        },
    }


def _binding_rejection_sample(
    case_id: str,
    input_value: dict[str, Any],
    expected_exception_type: str,
    expected_message: str,
    controller,
    callable_,
) -> dict[str, Any]:
    return _exception_rejection_sample(
        case_id,
        input_value,
        expected_exception_type,
        expected_message,
        lambda: controller.snapshot(),
        callable_,
    )


def _exception_rejection_sample(
    case_id: str,
    input_value: dict[str, Any],
    expected_exception_type: str,
    expected_message: str,
    snapshot_getter,
    callable_,
) -> dict[str, Any]:
    snapshot_before = _plain(snapshot_getter())
    actual_type = None
    actual_message = None
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            callable_()
        except (TypeError, ValueError, OverflowError) as exc:
            actual_type = type(exc).__name__
            actual_message = str(exc)
    snapshot_after = _plain(snapshot_getter())
    result = (
        actual_type == expected_exception_type
        and actual_message == expected_message
        and not caught
        and snapshot_before == snapshot_after
    )
    return {
        "case_id": case_id,
        "input": input_value,
        "independent_expected": {
            "exception_type": expected_exception_type,
            "message": expected_message,
            "warning_count": 0,
            "state_change": "none",
        },
        "actual": {
            "exception_type": actual_type,
            "message": actual_message,
            "warning_count": len(caught),
            "snapshot_before": snapshot_before,
            "snapshot_after": snapshot_after,
        },
        "units": ["Python exception", "warning count", "state snapshot"],
        "absolute_tolerance": 0.0,
        "relative_tolerance": 0.0,
        "comparison": {"kind": "binding_rejection_atomic", "result": result},
    }


def _caught_reason(module, callable_) -> str | None:
    try:
        callable_()
    except module.ControllerContractError as exc:
        reason = getattr(exc, "reason", None)
        return reason() if callable(reason) else reason
    return None


def _pytest_node(classname: str, name: str) -> str:
    module_name = classname.rsplit(".", 1)[-1]
    function_name = name.split("[", 1)[0]
    return f"python/tests/{module_name}.py::{function_name}"


def _junit_execution(path: Path, kind: str) -> dict[str, Any]:
    if not path.is_file():
        raise RuntimeError(f"missing {kind} JUnit evidence: {path}")
    root = ET.parse(path).getroot()
    grouped: dict[str, list[dict[str, Any]]] = {}
    for case in root.iter("testcase"):
        raw_name = case.get("name", "")
        classname = case.get("classname", "")
        node = raw_name if kind == "ctest" else _pytest_node(classname, raw_name)
        status = "pass"
        for candidate in ("failure", "error", "skipped"):
            if case.find(candidate) is not None:
                status = candidate
                break
        output = "".join(
            element.text or ""
            for tag in ("system-out", "system-err", "failure", "error")
            for element in case.findall(tag)
        )
        grouped.setdefault(node, []).append(
            {
                "collected_name": raw_name,
                "classname": classname,
                "status": status,
                "time_s": float(case.get("time", "0") or 0.0),
                "output": output[-12000:],
            }
        )
    nodes: dict[str, Any] = {}
    for node, invocations in sorted(grouped.items()):
        nodes[node] = {
            "status": (
                "pass"
                if invocations and all(row["status"] == "pass" for row in invocations)
                else "fail"
            ),
            "invocation_count": len(invocations),
            "duration_s": sum(row["time_s"] for row in invocations),
            "collected_cases": [row["collected_name"] for row in invocations],
            "output": "\n".join(row["output"] for row in invocations)[-12000:],
        }
    return {
        "kind": kind,
        "path": path.name,
        "sha256": _sha256(path),
        "size_bytes": path.stat().st_size,
        "collected_testcases": sum(len(rows) for rows in grouped.values()),
        "nodes": nodes,
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=repo, text=True, stderr=subprocess.DEVNULL
    ).strip()


def _command_version(command: list[str]) -> str:
    try:
        output = subprocess.check_output(
            command, text=True, stderr=subprocess.STDOUT
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        return f"unavailable: {type(exc).__name__}"
    return output.splitlines()[0] if output else "unavailable: empty output"


def _execution_identity(source_commit: str) -> dict[str, Any]:
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return {
            "context": "github_actions",
            "checked_out_source_commit": source_commit,
            "run_id": os.environ.get("GITHUB_RUN_ID"),
            "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
            "event_name": os.environ.get("GITHUB_EVENT_NAME"),
            "github_sha_metadata": os.environ.get("GITHUB_SHA"),
            "github_ref_metadata": os.environ.get("GITHUB_REF"),
            "github_head_ref": os.environ.get("GITHUB_HEAD_REF") or None,
            "repository": os.environ.get("GITHUB_REPOSITORY"),
            "workflow_ref": os.environ.get("GITHUB_WORKFLOW_REF"),
            "identity_note": "checked_out_source_commit is authoritative for artifact bytes; github_sha_metadata is retained separately and may name the pull-request merge ref",
        }
    return {
        "context": "local",
        "checked_out_source_commit": source_commit,
        "run_id": None,
        "run_attempt": None,
        "event_name": None,
        "github_sha_metadata": None,
        "github_ref_metadata": None,
        "github_head_ref": None,
        "repository": None,
        "workflow_ref": None,
        "identity_note": "local generation has no GitHub Actions run identity",
    }


def _cmake_cache_entries(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="strict").splitlines():
        if not line or line.startswith(("#", "//")) or "=" not in line:
            continue
        key_and_type, value = line.split("=", 1)
        key = key_and_type.split(":", 1)[0]
        entries[key] = value
    return entries


def _validated_build_layout(
    module_dir: Path,
    build_dir: Path,
    build_type: str,
    repo: Path,
    source_subdirectory: Path,
) -> dict[str, str]:
    """Bind the imported module, cache and declared configuration to one build."""

    module_dir = module_dir.resolve()
    build_dir = build_dir.resolve()
    repo = repo.resolve()
    expected_module_dir = (build_dir / source_subdirectory).resolve()
    if module_dir != expected_module_dir:
        raise RuntimeError(
            "controller module directory does not belong to declared build: "
            f"{module_dir} != {expected_module_dir}"
        )

    cache = build_dir / "CMakeCache.txt"
    if not cache.is_file():
        raise RuntimeError(f"declared build has no CMake cache: {cache}")
    entries = _cmake_cache_entries(cache)
    cached_build_type = entries.get("CMAKE_BUILD_TYPE")
    if cached_build_type != build_type:
        raise RuntimeError(
            "declared build type differs from CMake cache: "
            f"{build_type} != {cached_build_type!r}"
        )

    def exact_cached_path(key: str, expected: Path, label: str) -> None:
        value = entries.get(key)
        if not value:
            raise RuntimeError(f"CMake cache lacks {label}")
        cached = Path(value)
        if not cached.is_absolute() or cached.resolve() != expected.resolve():
            raise RuntimeError(
                f"CMake cache {label} differs from declared path: "
                f"{value!r} != {expected}"
            )

    exact_cached_path("CMAKE_CACHEFILE_DIR", build_dir, "build directory")
    exact_cached_path("CMAKE_HOME_DIRECTORY", repo, "source directory")
    return entries


def _display_path(path: Path, repo: Path) -> str:
    path = path.resolve()
    try:
        return str(path.relative_to(repo.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _catch2_identity(cache_entries: dict[str, str], repo: Path) -> dict[str, Any]:
    pinned_revision = "b5373dadca40b7edc8570cf9470b9b1cb1934d40"
    source_value = cache_entries.get("Catch2_SOURCE_DIR", "")
    source = Path(source_value) if source_value else None
    if source is not None and source.is_dir():
        revision = _git(source, "rev-parse", "HEAD")
        cmake_text = (source / "CMakeLists.txt").read_text(encoding="utf-8")
        match = re.search(
            r"project\(\s*Catch2\b.*?\bVERSION\s+([0-9]+(?:\.[0-9]+)+)",
            cmake_text,
            flags=re.DOTALL,
        )
        if match is None:
            raise RuntimeError("cannot identify fetched Catch2 version")
        identity = {
            "mode": "fetched_pinned_revision",
            "version": match.group(1),
            "source_directory": _display_path(source, repo),
            "git_revision": revision,
            "required_git_revision": pinned_revision,
        }
        if identity["version"] != "3.5.4" or revision != pinned_revision:
            raise RuntimeError(f"unexpected fetched Catch2 identity: {identity}")
        return identity

    cmake_dir_value = cache_entries.get("Catch2_DIR", "")
    if not cmake_dir_value or cmake_dir_value.endswith("-NOTFOUND"):
        raise RuntimeError("CMake cache has no resolved Catch2 source or package")
    cmake_dir = Path(cmake_dir_value)
    version_file = cmake_dir / "Catch2ConfigVersion.cmake"
    text = version_file.read_text(encoding="utf-8")
    match = re.search(r"set\(PACKAGE_VERSION\s+\"([^\"]+)\"\)", text)
    if match is None or match.group(1) != "3.5.4":
        raise RuntimeError("installed Catch2 identity is not exact version 3.5.4")
    return {
        "mode": "installed_exact_package",
        "version": match.group(1),
        "cmake_directory": _display_path(cmake_dir, repo),
        "config_version_sha256": _sha256(version_file),
        "required_git_revision": None,
    }


def _build_identity(
    module_dir: Path,
    module_path: Path,
    build_dir: Path,
    build_type: str,
    repo: Path,
    cache_entries: dict[str, str],
) -> dict[str, Any]:
    cache = build_dir / "CMakeCache.txt"
    entries = cache_entries
    try:
        module_path.resolve().relative_to(module_dir.resolve())
    except ValueError as exc:
        raise RuntimeError(
            f"loaded controller module is outside declared module directory: {module_path}"
        ) from exc
    compiler = entries.get("CMAKE_CXX_COMPILER")
    python_executable = entries.get("_Python3_EXECUTABLE") or entries.get(
        "Python3_EXECUTABLE"
    )
    pybind_dir = entries.get("pybind11_DIR")
    if not compiler or not python_executable or not pybind_dir:
        raise RuntimeError("CMake cache lacks compiler, Python, or pybind11 identity")
    pybind_version = _command_version(
        [python_executable, "-c", "import pybind11; print(pybind11.__version__)"]
    )
    if pybind_version != "2.13.6":
        raise RuntimeError(f"unexpected pybind11 version: {pybind_version}")
    configured_python = Path(python_executable).resolve()
    generator_python = Path(sys.executable).resolve()
    if configured_python != generator_python:
        raise RuntimeError(
            "evidence generator Python differs from CMake Python: "
            f"{generator_python} != {configured_python}"
        )
    return {
        "build_type": build_type,
        "cmake_build_type": entries["CMAKE_BUILD_TYPE"],
        "build_directory": _display_path(build_dir, repo),
        "cmake_cache_directory": _display_path(
            Path(entries["CMAKE_CACHEFILE_DIR"]), repo
        ),
        "cmake_home_directory": _display_path(
            Path(entries["CMAKE_HOME_DIRECTORY"]), repo
        ),
        "module_directory": _display_path(module_dir, repo),
        "module_path": _display_path(module_path, repo),
        "module_sha256": _sha256(module_path),
        "cmake_cache_sha256": _sha256(cache),
        "python": sys.version.split()[0],
        "python_executable": _display_path(configured_python, repo),
        "generator_python_executable": _display_path(generator_python, repo),
        "cmake_python_matches_generator": True,
        "python_implementation": platform.python_implementation(),
        "python_abi": getattr(sys.implementation, "cache_tag", "unknown"),
        "platform": platform.platform(),
        "cmake": _command_version(["cmake", "--version"]),
        "cxx_compiler": _display_path(Path(compiler), repo),
        "cxx": _command_version([compiler, "--version"]),
        "pybind11": {
            "version": pybind_version,
            "cmake_directory": _display_path(Path(pybind_dir), repo),
        },
        "catch2": _catch2_identity(entries, repo),
    }


def _plain(value: Any) -> Any:
    """Copy pybind values into JSON data without retaining live references."""

    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    fields = (
        "id",
        "reset",
        "accepted",
        "reason",
        "epoch_id",
        "tick_index",
        "epoch_origin_s",
        "expected_timestamp_s",
        "integral_Nm",
        "derivative_filtered_rad_s2",
        "previous_rate_rad_s",
        "has_previous_rate",
        "expected_held_command",
        "last_diagnostics",
        "requested_torque_body_Nm",
        "limited_torque_body_Nm",
        "saturated",
        "q_nb",
        "omega_b_rad_s",
        "valid",
        "actual_torque_body_Nm",
        "command_timestamp_s",
        "timestamp_s",
        "rate_error_rad_s",
        "derivative_raw_rad_s2",
        "proportional_Nm",
        "integral_before_Nm",
        "derivative_Nm",
        "conditional_integral_rate_Nm_s",
        "limit_backcalculation_rate_Nm_s",
        "lag_backcalculation_rate_Nm_s",
        "integral_after_Nm",
        "requested_Nm",
        "limited_Nm",
    )
    result = {
        name: _plain(getattr(value, name))
        for name in fields
        if hasattr(value, name)
    }
    if result:
        return result
    raise TypeError(f"cannot serialize evidence value of type {type(value).__name__}")


def _parameters(module):
    track = Path(__file__).resolve().parent
    sys.path.insert(0, str(track / "python"))
    from controller import load_controller_parameters

    return load_controller_parameters(module=module, track=track)


def _reset(module, controller, epoch_id: int = 7, timestamp_s: float = 12.0):
    epoch = module.ResetEpoch()
    epoch.id = epoch_id
    epoch.timestamp_s = timestamp_s
    return controller.reset(module.ControllerInitialState(), epoch)


def _inputs(module, timestamp_s: float, held, *, epoch_id: int = 7):
    command = module.AttitudeCommand()
    command.q_nb = [1.0, 0.0, 0.0, 0.0]
    command.timestamp_s = timestamp_s
    command.valid = True
    command.epoch_id = epoch_id

    estimate = module.StateEstimate()
    estimate.q_nb = [1.0, 0.0, 0.0, 0.0]
    estimate.omega_b_rad_s = [0.0, 0.0, 0.0]
    estimate.timestamp_s = timestamp_s
    estimate.valid = True
    estimate.epoch_id = epoch_id

    feedback = module.ActuatorFeedback()
    feedback.actual_torque_body_Nm = [0.0, 0.0, 0.0]
    feedback.limited_torque_body_Nm = list(held.limited_torque_body_Nm)
    feedback.saturated = list(held.saturated)
    feedback.timestamp_s = timestamp_s
    feedback.command_timestamp_s = held.timestamp_s
    feedback.epoch_id = epoch_id
    return command, estimate, feedback


def _max_abs_error(actual, expected) -> float:
    return max(abs(float(a) - float(e)) for a, e in zip(actual, expected))


def _attitude_sign_probe(module, parameters) -> dict[str, Any]:
    controller = module.CascadedController(parameters)
    held = _reset(module, controller)
    command, estimate, feedback = _inputs(module, 12.005, held)
    angle = 0.1
    command.q_nb = [math.cos(angle / 2.0), math.sin(angle / 2.0), 0.0, 0.0]
    output = controller.step(command, estimate, feedback, parameters.controller_period_s)
    diagnostics = controller.last_diagnostics()
    expected_rate = parameters.attitude_kp[0] * 2.0 * math.sin(angle / 2.0)
    expected_request = parameters.rate_kp[0] * expected_rate
    expected = [expected_request, 0.0, 0.0]
    return {
        "input": {
            "q_nb_command": list(command.q_nb),
            "q_nb_estimate": list(estimate.q_nb),
            "omega_b_rad_s": list(estimate.omega_b_rad_s),
            "timestamp_s": command.timestamp_s,
        },
        "independent_oracle": {
            "attitude_error_vector": [2.0 * math.sin(angle / 2.0), 0.0, 0.0],
            "rate_target_rad_s": [expected_rate, 0.0, 0.0],
            "requested_torque_body_Nm": expected,
            "absolute_tolerance": ABS_TOL,
            "relative_tolerance": 0.0,
        },
        "actual": _plain(output),
        "diagnostics": _plain(diagnostics),
        "max_request_abs_error_Nm": _max_abs_error(
            output.requested_torque_body_Nm, expected
        ),
    }


def _antiwindup_probe(module, parameters) -> dict[str, Any]:
    controller = module.CascadedController(parameters)
    held = _reset(module, controller)
    command, estimate, feedback = _inputs(module, 12.005, held)
    # Identity attitude produces a zero outer-loop target.  A negative measured
    # body rate makes positive rate error large enough to saturate the x request.
    estimate.omega_b_rad_s = [-6.0, 0.0, 0.0]
    output = controller.step(command, estimate, feedback, parameters.controller_period_s)
    diagnostics = controller.last_diagnostics()
    rate_error = 6.0
    request = parameters.rate_kp[0] * rate_error
    limited = parameters.torque_limit_Nm[0]
    conditional_ki = 0.0  # positive error would push farther into positive saturation
    limit_backcalc = parameters.kaw_limit_per_s[0] * (limited - request)
    lag_backcalc = 0.0
    integral_after = parameters.controller_period_s * (
        conditional_ki + limit_backcalc + lag_backcalc
    )
    independent = {
        "rate_error_rad_s": [rate_error, 0.0, 0.0],
        "proportional_Nm": [request, 0.0, 0.0],
        "conditional_integral_rate_Nm_s": [conditional_ki, 0.0, 0.0],
        "limit_backcalculation_rate_Nm_s": [limit_backcalc, 0.0, 0.0],
        "lag_backcalculation_rate_Nm_s": [lag_backcalc, 0.0, 0.0],
        "integral_after_Nm": [integral_after, 0.0, 0.0],
        "request_Nm": [request, 0.0, 0.0],
        "limited_Nm": [limited, 0.0, 0.0],
        "saturated": [True, False, False],
        "absolute_tolerance": ABS_TOL,
        "relative_tolerance": 0.0,
    }
    return {
        "input": {
            "omega_b_rad_s": list(estimate.omega_b_rad_s),
            "held_command": _plain(held),
            "actual_torque_body_Nm": list(feedback.actual_torque_body_Nm),
            "dt_s": parameters.controller_period_s,
        },
        "independent_oracle": independent,
        "actual": _plain(output),
        "diagnostics": _plain(diagnostics),
        "errors": {
            "request_Nm": abs(output.requested_torque_body_Nm[0] - request),
            "limited_Nm": abs(output.limited_torque_body_Nm[0] - limited),
            "integral_after_Nm": abs(
                diagnostics.integral_after_Nm[0] - integral_after
            ),
            "limit_backcalculation_rate_Nm_s": abs(
                diagnostics.limit_backcalculation_rate_Nm_s[0] - limit_backcalc
            ),
        },
    }


def _paired_timing_probe(module, parameters) -> dict[str, Any]:
    controller = module.CascadedController(parameters)
    held = _reset(module, controller)
    trace = []
    for tick in range(1, 4):
        timestamp = 12.0 + tick * parameters.controller_period_s
        command, estimate, feedback = _inputs(module, timestamp, held)
        feedback.actual_torque_body_Nm = list(held.limited_torque_body_Nm)
        output = controller.step(
            command, estimate, feedback, parameters.controller_period_s
        )
        trace.append(
            {
                "tick_index": tick,
                "current_timestamp_s": timestamp,
                "paired_command_timestamp_s": feedback.command_timestamp_s,
                "feedback_limited_torque_body_Nm": list(
                    feedback.limited_torque_body_Nm
                ),
                "output": _plain(output),
                "diagnostics": _plain(controller.last_diagnostics()),
            }
        )
        held = output
    expected_times = [12.0 + tick * parameters.controller_period_s for tick in range(4)]
    return {
        "trace": trace,
        "independent_expected_publication_times_s": expected_times,
        "each_feedback_pairs_previous_publication": all(
            abs(row["paired_command_timestamp_s"] - expected_times[index]) <= ABS_TOL
            for index, row in enumerate(trace)
        ),
    }


def _atomic_rejection_probe(module, parameters) -> dict[str, Any]:
    controller = module.CascadedController(parameters)
    held = _reset(module, controller)
    command, estimate, feedback = _inputs(module, 12.005, held)
    before = _plain(controller.snapshot())
    estimate.valid = False
    reason = None
    try:
        controller.step(command, estimate, feedback, parameters.controller_period_s)
    except module.ControllerContractError as exc:
        reason = getattr(exc, "reason", None)
        if callable(reason):
            reason = reason()
        reason = reason or str(exc).split(":", 1)[0]
    else:
        raise RuntimeError("invalid estimate was accepted")
    after = _plain(controller.snapshot())
    estimate.valid = True
    retry = controller.step(command, estimate, feedback, parameters.controller_period_s)
    return {
        "invalid_input": {"estimate_valid": False, "timestamp_s": 12.005},
        "stable_reason": reason,
        "snapshot_before": before,
        "snapshot_after": after,
        "snapshot_unchanged": before == after,
        "corrected_same_tick_retry": _plain(retry),
    }


_PARAMETER_VECTOR_FIELDS = (
    "attitude_kp",
    "rate_kp",
    "rate_ki",
    "rate_kd",
    "integral_limit_Nm",
    "rate_limit_rad_s",
    "torque_limit_Nm",
    "kaw_limit_per_s",
    "kaw_lag_per_s",
)
_PARAMETER_SCALAR_FIELDS = (
    "derivative_time_constant_s",
    "controller_period_s",
    "timestamp_tolerance_s",
    "quaternion_norm_tolerance",
)


def _copy_parameters(module, source, **overrides):
    result = module.ControllerParameters()
    for field in _PARAMETER_VECTOR_FIELDS:
        setattr(result, field, list(overrides.get(field, getattr(source, field))))
    for field in _PARAMETER_SCALAR_FIELDS:
        setattr(result, field, float(overrides.get(field, getattr(source, field))))
    return result


def _case_row(row_id: str, samples: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "row_id": row_id,
        "nodes": list(S0_CASE_NODES[row_id]),
        "samples": samples,
        "result": all(sample["comparison"]["result"] for sample in samples),
    }


def _axis_angle(axis: int, angle: float) -> list[float]:
    result = [math.cos(angle / 2.0), 0.0, 0.0, 0.0]
    result[axis + 1] = math.sin(angle / 2.0)
    return result


def _hamilton(left: list[float], right: list[float]) -> list[float]:
    return [
        left[0] * right[0]
        - left[1] * right[1]
        - left[2] * right[2]
        - left[3] * right[3],
        left[0] * right[1]
        + left[1] * right[0]
        + left[2] * right[3]
        - left[3] * right[2],
        left[0] * right[2]
        - left[1] * right[3]
        + left[2] * right[0]
        + left[3] * right[1],
        left[0] * right[3]
        + left[1] * right[2]
        - left[2] * right[1]
        + left[3] * right[0],
    ]


def _canonical_error(estimated: list[float], commanded: list[float]) -> list[float]:
    error = _hamilton(
        [estimated[0], -estimated[1], -estimated[2], -estimated[3]],
        commanded,
    )
    negate = error[0] < 0.0
    if error[0] == 0.0:
        first = next((value for value in error[1:] if value != 0.0), 0.0)
        negate = first < 0.0
    return [-value for value in error] if negate else error


def _attitude_case_rows(module, parameters) -> list[dict[str, Any]]:
    axis_samples = []
    for axis in range(3):
        for magnitude in (1e-8, 0.1):
            for sign in (-1.0, 1.0):
                angle = sign * magnitude
                controller = module.CascadedController(parameters)
                held = _reset(module, controller, 0, 0.0)
                command, estimate, feedback = _inputs(module, 0.005, held, epoch_id=0)
                command.q_nb = _axis_angle(axis, angle)
                output = controller.step(
                    command, estimate, feedback, parameters.controller_period_s
                )
                expected = [0.0, 0.0, 0.0]
                expected[axis] = (
                    parameters.rate_kp[axis]
                    * parameters.attitude_kp[axis]
                    * 2.0
                    * math.sin(angle / 2.0)
                )
                axis_samples.append(
                    _numeric_sample(
                        f"axis-{axis}-angle-{angle:.12g}",
                        {"axis": axis, "angle_rad": angle},
                        [f"requested_torque_axis_{index}" for index in range(3)],
                        expected,
                        list(output.requested_torque_body_Nm),
                        ["N m"] * 3,
                    )
                )

    inverse_root_two = 1.0 / math.sqrt(2.0)
    estimated = [
        math.cos(0.2),
        inverse_root_two * math.sin(0.2),
        inverse_root_two * math.sin(0.2),
        0.0,
    ]
    commanded = [
        math.cos(0.3),
        0.0,
        inverse_root_two * math.sin(0.3),
        inverse_root_two * math.sin(0.3),
    ]
    error = _canonical_error(estimated, commanded)
    controller = module.CascadedController(parameters)
    held = _reset(module, controller, 0, 0.0)
    command, estimate, feedback = _inputs(module, 0.005, held, epoch_id=0)
    command.q_nb = commanded
    estimate.q_nb = estimated
    output = controller.step(command, estimate, feedback, parameters.controller_period_s)
    expected = []
    for axis in range(3):
        target = max(
            -parameters.rate_limit_rad_s[axis],
            min(
                parameters.rate_limit_rad_s[axis],
                parameters.attitude_kp[axis] * 2.0 * error[axis + 1],
            ),
        )
        expected.append(parameters.rate_kp[axis] * target)
    multiaxis = _numeric_sample(
        "nonidentity-multiaxis",
        {"q_nb_command": commanded, "q_nb_estimate": estimated},
        [f"requested_torque_axis_{axis}" for axis in range(3)],
        expected,
        list(output.requested_torque_body_Nm),
        ["N m"] * 3,
    )

    half_turn_samples = []
    for axis in range(3):
        positive = [0.0, 0.0, 0.0, 0.0]
        positive[axis + 1] = 1.0
        antipode = [-value for value in positive]
        outputs = []
        for quaternion in (positive, antipode):
            controller = module.CascadedController(parameters)
            held = _reset(module, controller, 0, 0.0)
            command, estimate, feedback = _inputs(module, 0.005, held, epoch_id=0)
            command.q_nb = quaternion
            outputs.append(
                list(
                    controller.step(
                        command,
                        estimate,
                        feedback,
                        parameters.controller_period_s,
                    ).requested_torque_body_Nm
                )
            )
        expected = [0.0, 0.0, 0.0]
        rate_target = min(
            parameters.rate_limit_rad_s[axis],
            2.0 * parameters.attitude_kp[axis],
        )
        expected[axis] = parameters.rate_kp[axis] * rate_target
        half_turn_samples.append(
            _numeric_sample(
                f"half-turn-axis-{axis}-antipode",
                {"q": positive, "minus_q": antipode},
                [
                    *(f"q_requested_axis_{index}" for index in range(3)),
                    *(f"minus_q_requested_axis_{index}" for index in range(3)),
                ],
                expected + expected,
                outputs[0] + outputs[1],
                ["N m"] * 6,
            )
        )
    inverse_root_three = 1.0 / math.sqrt(3.0)
    mixed = [0.0, inverse_root_three, -inverse_root_three, inverse_root_three]
    controller = module.CascadedController(parameters)
    held = _reset(module, controller, 0, 0.0)
    command, estimate, feedback = _inputs(module, 0.005, held, epoch_id=0)
    command.q_nb = mixed
    output = controller.step(command, estimate, feedback, parameters.controller_period_s)
    mixed_expected = []
    for axis in range(3):
        rate_target = max(
            -parameters.rate_limit_rad_s[axis],
            min(
                parameters.rate_limit_rad_s[axis],
                parameters.attitude_kp[axis] * 2.0 * mixed[axis + 1],
            ),
        )
        mixed_expected.append(parameters.rate_kp[axis] * rate_target)
    half_turn_samples.append(
        _numeric_sample(
            "mixed-half-turn-signs-and-values",
            {"q_nb_command": mixed, "q_nb_estimate": [1.0, 0.0, 0.0, 0.0]},
            [f"requested_torque_axis_{axis}" for axis in range(3)],
            mixed_expected,
            list(output.requested_torque_body_Nm),
            ["N m"] * 3,
        )
    )
    return [
        _case_row("B-ATT-01", axis_samples),
        _case_row("B-ATT-02", [multiaxis]),
        _case_row("B-ATT-03", half_turn_samples),
    ]


def _rate_derivative_case_rows(module, parameters) -> list[dict[str, Any]]:
    isolated = _copy_parameters(
        module,
        parameters,
        attitude_kp=[0.0, 0.0, 0.0],
        rate_kp=[0.0, 0.0, 0.0],
        rate_ki=[0.0, 0.0, 0.0],
        rate_kd=[0.0, 0.0, 0.0],
        torque_limit_Nm=[10.0, 10.0, 10.0],
        kaw_limit_per_s=[0.0, 0.0, 0.0],
        kaw_lag_per_s=[0.0, 0.0, 0.0],
    )
    clamp_parameters = _copy_parameters(
        module,
        isolated,
        attitude_kp=[1.0, 1.0, 1.0],
        rate_kp=[1.0, 1.0, 1.0],
        rate_limit_rad_s=[0.5, 0.5, 0.5],
    )
    clamp_samples = []
    for component in (-0.3, 0.3, -0.25, 0.25):
        controller = module.CascadedController(clamp_parameters)
        held = _reset(module, controller, 0, 0.0)
        command, estimate, feedback = _inputs(module, 0.005, held, epoch_id=0)
        command.q_nb = [math.sqrt(1.0 - component * component), component, 0.0, 0.0]
        output = controller.step(command, estimate, feedback, 0.005)
        expected = max(-0.5, min(0.5, 2.0 * component))
        clamp_samples.append(
            _numeric_sample(
                f"outer-clamp-{component:+.2f}",
                {"q_x": component, "rate_limit_rad_s": 0.5},
                ["requested_torque_x"],
                [expected],
                [output.requested_torque_body_Nm[0]],
                ["N m"],
            )
        )

    pid_samples = []
    p = _copy_parameters(module, isolated, rate_kp=[2.0, 0.0, 0.0])
    controller = module.CascadedController(p)
    held = _reset(module, controller, 0, 0.0)
    command, estimate, feedback = _inputs(module, 0.005, held, epoch_id=0)
    estimate.omega_b_rad_s = [0.1, 0.0, 0.0]
    output = controller.step(command, estimate, feedback, 0.005)
    diagnostics = controller.last_diagnostics()
    pid_samples.append(
        _numeric_sample(
            "proportional-only",
            {"omega_x_rad_s": 0.1, "kp": 2.0, "ki": 0.0, "kd": 0.0},
            ["P", "I_before", "D", "request"],
            [-0.2, 0.0, 0.0, -0.2],
            [
                diagnostics.proportional_Nm[0],
                diagnostics.integral_before_Nm[0],
                diagnostics.derivative_Nm[0],
                output.requested_torque_body_Nm[0],
            ],
            ["N m"] * 4,
        )
    )
    p = _copy_parameters(module, isolated, rate_ki=[3.0, 0.0, 0.0])
    controller = module.CascadedController(p)
    held = _reset(module, controller, 0, 0.0)
    command, estimate, feedback = _inputs(module, 0.005, held, epoch_id=0)
    estimate.omega_b_rad_s = [0.1, 0.0, 0.0]
    held = controller.step(command, estimate, feedback, 0.005)
    command, estimate, feedback = _inputs(module, 0.010, held, epoch_id=0)
    estimate.omega_b_rad_s = [0.1, 0.0, 0.0]
    output = controller.step(command, estimate, feedback, 0.005)
    diagnostics = controller.last_diagnostics()
    pid_samples.append(
        _numeric_sample(
            "integral-only",
            {"omega_x_rad_s": [0.1, 0.1], "ki": 3.0, "dt_s": 0.005},
            ["P", "I_before", "D", "request"],
            [0.0, -0.0015, 0.0, -0.0015],
            [
                diagnostics.proportional_Nm[0],
                diagnostics.integral_before_Nm[0],
                diagnostics.derivative_Nm[0],
                output.requested_torque_body_Nm[0],
            ],
            ["N m"] * 4,
        )
    )
    p = _copy_parameters(module, isolated, rate_kd=[0.5, 0.0, 0.0])
    controller = module.CascadedController(p)
    held = _reset(module, controller, 0, 0.0)
    command, estimate, feedback = _inputs(module, 0.005, held, epoch_id=0)
    estimate.omega_b_rad_s = [0.1, 0.0, 0.0]
    held = controller.step(command, estimate, feedback, 0.005)
    command, estimate, feedback = _inputs(module, 0.010, held, epoch_id=0)
    estimate.omega_b_rad_s = [0.2, 0.0, 0.0]
    output = controller.step(command, estimate, feedback, 0.005)
    diagnostics = controller.last_diagnostics()
    raw = (0.2 - 0.1) / 0.005
    filtered = (0.005 / 0.025) * raw
    pid_samples.append(
        _numeric_sample(
            "derivative-only",
            {"omega_x_rad_s": [0.1, 0.2], "kd": 0.5, "dt_s": 0.005},
            ["P", "I_before", "D", "request"],
            [0.0, 0.0, -0.5 * filtered, -0.5 * filtered],
            [
                diagnostics.proportional_Nm[0],
                diagnostics.integral_before_Nm[0],
                diagnostics.derivative_Nm[0],
                output.requested_torque_body_Nm[0],
            ],
            ["N m"] * 4,
        )
    )

    derivative_parameters = _copy_parameters(
        module,
        isolated,
        rate_kd=[1.0, 1.0, 1.0],
        torque_limit_Nm=[100.0, 100.0, 100.0],
    )
    controller = module.CascadedController(derivative_parameters)
    held = _reset(module, controller, 0, 0.0)
    filtered_actual = []
    rates = [0.1, 0.1, 0.2, 0.2]
    commands = [[1.0, 0.0, 0.0, 0.0]] * 3 + [_axis_angle(0, 0.1)]
    for tick, (rate, quaternion) in enumerate(zip(rates, commands), start=1):
        timestamp = tick * 0.005
        command, estimate, feedback = _inputs(module, timestamp, held, epoch_id=0)
        command.q_nb = quaternion
        estimate.omega_b_rad_s = [rate, 0.0, 0.0]
        held = controller.step(command, estimate, feedback, 0.005)
        diagnostics = controller.last_diagnostics()
        filtered_actual.append(diagnostics.derivative_filtered_rad_s2[0])
    derivative_filter = _numeric_sample(
        "constant-step-command-only-trajectory",
        {"rates_rad_s": rates, "command_step_at_tick": 4, "alpha": 0.2},
        [f"D_filtered_tick_{tick}" for tick in range(1, 5)],
        [0.0, 0.0, 4.0, 3.2],
        filtered_actual,
        ["rad s^-2"] * 4,
    )

    controller = module.CascadedController(parameters)
    held = _reset(module, controller, 0, 0.0)
    raw_actual = []
    for tick, rate in enumerate((0.4, 0.8), start=1):
        timestamp = tick * 0.005
        command, estimate, feedback = _inputs(module, timestamp, held, epoch_id=0)
        estimate.omega_b_rad_s = [rate, 0.0, 0.0]
        held = controller.step(command, estimate, feedback, 0.005)
        raw_actual.append(controller.last_diagnostics().derivative_raw_rad_s2[0])
    held = _reset(module, controller, 1, 0.020)
    command, estimate, feedback = _inputs(module, 0.025, held, epoch_id=1)
    estimate.omega_b_rad_s = [0.8, 0.0, 0.0]
    controller.step(command, estimate, feedback, 0.005)
    raw_actual.append(controller.last_diagnostics().derivative_raw_rad_s2[0])
    first_step = _numeric_sample(
        "first-step-history-reset",
        {"rates_rad_s": [0.4, 0.8, 0.8], "reset_before_sample": [True, False, True]},
        ["raw_first", "raw_second", "raw_after_reset"],
        [0.0, 80.0, 0.0],
        raw_actual,
        ["rad s^-2"] * 3,
    )
    return [
        _case_row("B-RATE-01", clamp_samples),
        _case_row("B-RATE-02", pid_samples),
        _case_row("B-DERIV-01", [derivative_filter]),
        _case_row("B-DERIV-02", [first_step]),
    ]


def _limit_case_rows(module, parameters) -> list[dict[str, Any]]:
    p = _copy_parameters(
        module,
        parameters,
        attitude_kp=[1.0, 1.0, 1.0],
        rate_kp=[1.0, 1.0, 1.0],
        rate_ki=[0.0, 0.0, 0.0],
        rate_kd=[0.0, 0.0, 0.0],
        rate_limit_rad_s=[1.0, 1.0, 1.0],
    )
    samples = []
    for axis in range(3):
        limit = p.torque_limit_Nm[axis]
        for sign in (-1.0, 1.0):
            exact = sign * limit
            values = (
                (math.nextafter(exact, 0.0), False, "below"),
                (exact, False, "exact"),
                (math.nextafter(exact, math.copysign(math.inf, sign)), True, "beyond"),
            )
            for request, saturated, location in values:
                controller = module.CascadedController(p)
                held = _reset(module, controller, 0, 0.0)
                command, estimate, feedback = _inputs(module, 0.005, held, epoch_id=0)
                component = request / 2.0
                quaternion = [math.sqrt(1.0 - component * component), 0.0, 0.0, 0.0]
                quaternion[axis + 1] = component
                command.q_nb = quaternion
                output = controller.step(command, estimate, feedback, 0.005)
                limited = max(-limit, min(limit, request))
                samples.append(
                    _numeric_sample(
                        f"axis-{axis}-{sign:+.0f}-{location}",
                        {"axis": axis, "request_Nm": request, "limit_Nm": limit},
                        ["request", "limited", "saturated_as_0_or_1"],
                        [request, limited, float(saturated)],
                        [
                            output.requested_torque_body_Nm[axis],
                            output.limited_torque_body_Nm[axis],
                            float(output.saturated[axis]),
                        ],
                        ["N m", "N m", "boolean"],
                    )
                )
    controller = module.CascadedController(p)
    held = _reset(module, controller, 0, 0.0)
    command, estimate, feedback = _inputs(module, 0.005, held, epoch_id=0)
    component = 0.4 / 2.0
    command.q_nb = [math.sqrt(1.0 - component * component), component, 0.0, 0.0]
    output = controller.step(command, estimate, feedback, 0.005)
    diagnostics = controller.last_diagnostics()
    bundle = _numeric_sample(
        "same-tick-command-diagnostic-bundle",
        {"timestamp_s": 0.005, "epoch_id": 0, "request_x_Nm": 0.4},
        [
            "output_request_x",
            "diagnostic_request_x",
            "output_limited_x",
            "diagnostic_limited_x",
            "output_saturated_x",
            "diagnostic_saturated_x",
            "output_timestamp",
        ],
        [0.4, 0.4, 0.35, 0.35, 1.0, 1.0, 0.005],
        [
            output.requested_torque_body_Nm[0],
            diagnostics.requested_Nm[0],
            output.limited_torque_body_Nm[0],
            diagnostics.limited_Nm[0],
            float(output.saturated[0]),
            float(diagnostics.saturated[0]),
            output.timestamp_s,
        ],
        ["N m", "N m", "N m", "N m", "boolean", "boolean", "s"],
    )
    return [_case_row("B-LIMIT-01", samples), _case_row("B-LIMIT-02", [bundle])]


def _antiwindup_case_rows(module, parameters) -> list[dict[str, Any]]:
    conditional_parameters = _copy_parameters(
        module,
        parameters,
        attitude_kp=[0.0, 0.0, 0.0],
        rate_kp=[1.0, 1.0, 1.0],
        rate_ki=[2.0, 2.0, 2.0],
        rate_kd=[0.0, 0.0, 0.0],
        torque_limit_Nm=[0.1, 0.1, 0.1],
        kaw_limit_per_s=[0.0, 0.0, 0.0],
        kaw_lag_per_s=[0.0, 0.0, 0.0],
    )
    controller = module.CascadedController(conditional_parameters)
    held = _reset(module, controller, 0, 0.0)
    rates = (-0.2, -0.05, 0.2)
    actual = []
    for tick, rate in enumerate(rates, start=1):
        timestamp = tick * 0.005
        command, estimate, feedback = _inputs(module, timestamp, held, epoch_id=0)
        estimate.omega_b_rad_s = [rate, 0.0, 0.0]
        held = controller.step(command, estimate, feedback, 0.005)
        diagnostics = controller.last_diagnostics()
        actual.extend(
            [
                float(diagnostics.saturated[0]),
                diagnostics.conditional_integral_rate_Nm_s[0],
                diagnostics.integral_after_Nm[0],
            ]
        )
    conditional = _numeric_sample(
        "push-exit-opposite-push",
        {"omega_x_rad_s": list(rates), "ki": 2.0, "torque_limit_Nm": 0.1},
        [
            "tick1_saturated",
            "tick1_conditional_rate",
            "tick1_integral_after",
            "tick2_saturated",
            "tick2_conditional_rate",
            "tick2_integral_after",
            "tick3_saturated",
            "tick3_conditional_rate",
            "tick3_integral_after",
        ],
        [1.0, 0.0, 0.0, 0.0, 0.1, 0.0005, 1.0, 0.0, 0.0005],
        actual,
        ["boolean", "N m s^-1", "N m"] * 3,
    )

    isolated = _copy_parameters(
        module,
        parameters,
        attitude_kp=[0.0, 0.0, 0.0],
        rate_kp=[1.0, 1.0, 1.0],
        rate_ki=[0.0, 0.0, 0.0],
        rate_kd=[0.0, 0.0, 0.0],
        torque_limit_Nm=[0.1, 0.1, 0.1],
    )
    backcalc_samples = []
    for name, kaw_limit, kaw_lag, expected_limit, expected_lag in (
        ("limit-only", 8.0, 0.0, -0.8, 0.0),
        ("lag-only", 0.0, 2.0, 0.0, 0.1),
        ("limit-and-lag", 8.0, 2.0, -0.8, 0.1),
    ):
        p = _copy_parameters(
            module,
            isolated,
            kaw_limit_per_s=[kaw_limit] * 3,
            kaw_lag_per_s=[kaw_lag] * 3,
        )
        controller = module.CascadedController(p)
        held = _reset(module, controller, 0, 0.0)
        command, estimate, feedback = _inputs(module, 0.005, held, epoch_id=0)
        estimate.omega_b_rad_s = [-0.2, 0.0, 0.0]
        feedback.actual_torque_body_Nm = [0.05, 0.0, 0.0]
        controller.step(command, estimate, feedback, 0.005)
        diagnostics = controller.last_diagnostics()
        backcalc_samples.append(
            _numeric_sample(
                name,
                {
                    "request_Nm": 0.2,
                    "limited_Nm": 0.1,
                    "held_limited_Nm": 0.0,
                    "actual_Nm": 0.05,
                    "kaw_limit_per_s": kaw_limit,
                    "kaw_lag_per_s": kaw_lag,
                },
                ["limit_rate", "lag_rate", "integral_after"],
                [expected_limit, expected_lag, 0.005 * (expected_limit + expected_lag)],
                [
                    diagnostics.limit_backcalculation_rate_Nm_s[0],
                    diagnostics.lag_backcalculation_rate_Nm_s[0],
                    diagnostics.integral_after_Nm[0],
                ],
                ["N m s^-1", "N m s^-1", "N m"],
            )
        )

    release_parameters = _copy_parameters(
        module,
        isolated,
        rate_ki=[100.0, 100.0, 100.0],
        integral_limit_Nm=[0.001, 0.001, 0.001],
        kaw_limit_per_s=[8.0, 8.0, 8.0],
        kaw_lag_per_s=[2.0, 2.0, 2.0],
    )
    release_samples = []
    for axis in range(3):
        for sign in (-1.0, 1.0):
            controller = module.CascadedController(release_parameters)
            held = _reset(module, controller, 0, 0.0)
            command, estimate, feedback = _inputs(module, 0.005, held, epoch_id=0)
            rate = [0.0, 0.0, 0.0]
            rate[axis] = -sign * 0.2
            actual_torque = [0.0, 0.0, 0.0]
            actual_torque[axis] = sign * 0.05
            estimate.omega_b_rad_s = rate
            feedback.actual_torque_body_Nm = actual_torque
            held = controller.step(command, estimate, feedback, 0.005)
            first = controller.last_diagnostics()
            command, estimate, feedback = _inputs(module, 0.010, held, epoch_id=0)
            recovery_rate = [0.0, 0.0, 0.0]
            recovery_rate[axis] = -sign * 0.002
            matched = [0.0, 0.0, 0.0]
            matched[axis] = sign * 0.1
            estimate.omega_b_rad_s = recovery_rate
            feedback.actual_torque_body_Nm = matched
            held = controller.step(command, estimate, feedback, 0.005)
            second = controller.last_diagnostics()
            command, estimate, feedback = _inputs(module, 0.015, held, epoch_id=0)
            held_actual = [0.0, 0.0, 0.0]
            held_actual[axis] = sign * 0.001
            feedback.actual_torque_body_Nm = held_actual
            held = controller.step(command, estimate, feedback, 0.005)
            third = controller.last_diagnostics()
            command, estimate, feedback = _inputs(module, 0.020, held, epoch_id=0)
            controller.step(command, estimate, feedback, 0.005)
            fourth = controller.last_diagnostics()
            release_samples.append(
                _numeric_sample(
                    f"axis-{axis}-sign-{sign:+.0f}-saturate-release",
                    {
                        "axis": axis,
                        "saturation_rate_rad_s": rate[axis],
                        "release_rate_rad_s": recovery_rate[axis],
                    },
                    [
                        "tick1_saturated",
                        "tick1_limit_rate",
                        "tick1_lag_rate",
                        "tick1_integral_after",
                        "tick2_saturated",
                        "tick2_conditional_rate",
                        "tick2_integral_after",
                        "tick3_saturated",
                        "tick3_conditional_rate",
                        "tick3_limit_rate",
                        "tick3_lag_rate",
                        "tick3_integral_after",
                        "tick4_saturated",
                        "tick4_conditional_rate",
                        "tick4_limit_rate",
                        "tick4_lag_rate",
                        "tick4_integral_after",
                    ],
                    [
                        1.0,
                        -sign * 0.8,
                        sign * 0.1,
                        -sign * 0.001,
                        0.0,
                        sign * 0.2,
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                    ],
                    [
                        float(first.saturated[axis]),
                        first.limit_backcalculation_rate_Nm_s[axis],
                        first.lag_backcalculation_rate_Nm_s[axis],
                        first.integral_after_Nm[axis],
                        float(second.saturated[axis]),
                        second.conditional_integral_rate_Nm_s[axis],
                        second.integral_after_Nm[axis],
                        float(third.saturated[axis]),
                        third.conditional_integral_rate_Nm_s[axis],
                        third.limit_backcalculation_rate_Nm_s[axis],
                        third.lag_backcalculation_rate_Nm_s[axis],
                        third.integral_after_Nm[axis],
                        float(fourth.saturated[axis]),
                        fourth.conditional_integral_rate_Nm_s[axis],
                        fourth.limit_backcalculation_rate_Nm_s[axis],
                        fourth.lag_backcalculation_rate_Nm_s[axis],
                        fourth.integral_after_Nm[axis],
                    ],
                    [
                        "boolean",
                        "N m s^-1",
                        "N m s^-1",
                        "N m",
                        "boolean",
                        "N m s^-1",
                        "N m",
                        "boolean",
                        "N m s^-1",
                        "N m s^-1",
                        "N m s^-1",
                        "N m",
                        "boolean",
                        "N m s^-1",
                        "N m s^-1",
                        "N m s^-1",
                        "N m",
                    ],
                )
            )
    return [
        _case_row("B-AW-01", [conditional]),
        _case_row("B-AW-02", backcalc_samples),
        _case_row("B-AW-03", release_samples),
    ]


def _pair_case_rows(module, parameters) -> list[dict[str, Any]]:
    controller = module.CascadedController(parameters)
    held = _reset(module, controller, 0, 10.0)
    actual_requests = []
    actual_pair_times = []
    rates = (0.0, 0.1, 0.12)
    applied = (0.0, 0.005, 0.006)
    for tick, (rate, actual_torque) in enumerate(zip(rates, applied), start=1):
        timestamp = 10.0 + tick * 0.005
        command, estimate, feedback = _inputs(module, timestamp, held, epoch_id=0)
        command.q_nb = _axis_angle(0, 0.1)
        estimate.omega_b_rad_s = [rate, 0.0, 0.0]
        feedback.actual_torque_body_Nm = [actual_torque, 0.0, 0.0]
        actual_pair_times.append(feedback.command_timestamp_s)
        held = controller.step(command, estimate, feedback, 0.005)
        actual_requests.append(held.requested_torque_body_Nm[0])
    pairing = _numeric_sample(
        "three-consecutive-due-ticks",
        {
            "command_angle_x_rad": 0.1,
            "omega_x_rad_s": list(rates),
            "actual_torque_x_Nm": list(applied),
        },
        [
            "pair_timestamp_tick1",
            "pair_timestamp_tick2",
            "pair_timestamp_tick3",
            "request_tick1",
            "request_tick2",
            "request_tick3",
        ],
        [
            10.0,
            10.005,
            10.010,
            0.03198666833323413,
            0.008026651668650676,
            0.006186768320734882,
        ],
        actual_pair_times + actual_requests,
        ["s", "s", "s", "N m", "N m", "N m"],
    )

    controller = module.CascadedController(parameters)
    reset_output = _reset(module, controller, 3, 0.0)
    command, estimate, feedback = _inputs(module, 0.005, reset_output, epoch_id=3)
    first = controller.step(command, estimate, feedback, 0.005)
    command, estimate, feedback = _inputs(module, 0.010, first, epoch_id=3)
    second = controller.step(command, estimate, feedback, 0.005)
    variants = []
    baseline = _plain(controller.snapshot())

    def reject(name: str, sample, reason: str) -> None:
        command, estimate, _ = _inputs(module, 0.015, second, epoch_id=3)
        actual_reason = _caught_reason(
            module, lambda: controller.step(command, estimate, sample, 0.005)
        )
        variants.append(
            _rejection_sample(
                name,
                {
                    "feedback": _plain(sample),
                    "timestamp_s": 0.015,
                },
                reason,
                actual_reason,
                baseline,
                _plain(controller.snapshot()),
            )
        )

    _, _, sample = _inputs(module, 0.015, reset_output, epoch_id=3)
    reject("superseded-reset-command", sample, "feedback_command_mismatch")
    _, _, sample = _inputs(module, 0.015, second, epoch_id=3)
    sample.command_timestamp_s = 0.0125
    reject("unknown-command-timestamp", sample, "feedback_command_mismatch")
    _, _, sample = _inputs(module, 0.015, second, epoch_id=3)
    sample.command_timestamp_s = 0.020
    reject("future-command-timestamp", sample, "feedback_command_mismatch")
    _, _, sample = _inputs(module, 0.015, second, epoch_id=3)
    sample.epoch_id = 2
    reject("old-epoch", sample, "epoch_mismatch")
    _, _, sample = _inputs(module, 0.015, second, epoch_id=3)
    sample.limited_torque_body_Nm = [0.01, 0.0, 0.0]
    reject("fake-limited-value", sample, "feedback_command_mismatch")
    _, _, sample = _inputs(module, 0.015, second, epoch_id=3)
    sample.saturated = [True, False, False]
    reject("fake-saturation-status", sample, "feedback_command_mismatch")
    _, _, sample = _inputs(module, 0.015, second, epoch_id=3)
    before = _plain(controller.snapshot())
    setter_error = None
    try:
        sample.actual_torque_body_Nm = [math.nan, 0.0, 0.0]
    except (TypeError, ValueError) as exc:
        setter_error = type(exc).__name__
    variants.append(
        _exact_sample(
            "nonfinite-actual-binding-boundary",
            {"actual_torque_body_Nm": ["NaN", 0.0, 0.0]},
            {"setter_error": "ValueError", "state_unchanged": True},
            {
                "setter_error": setter_error,
                "state_unchanged": before == _plain(controller.snapshot()),
            },
            "binding exception and controller snapshot",
        )
    )
    _, _, sample = _inputs(module, 0.015, second, epoch_id=3)
    sample.actual_torque_body_Nm = [0.351, 0.0, 0.0]
    reject("out-of-limit-actual", sample, "invalid_feedback")
    return [_case_row("B-PAIR-01", [pairing]), _case_row("B-PAIR-02", variants)]


def _time_case_rows(module, parameters) -> list[dict[str, Any]]:
    invalid_samples = []
    for timestamp in (3.004, 3.006):
        controller = module.CascadedController(parameters)
        held = _reset(module, controller, 0, 3.0)
        command, estimate, feedback = _inputs(module, timestamp, held, epoch_id=0)
        before = _plain(controller.snapshot())
        reason = _caught_reason(
            module, lambda: controller.step(command, estimate, feedback, 0.005)
        )
        invalid_samples.append(
            _rejection_sample(
                f"off-grid-{timestamp}",
                {"timestamp_s": timestamp, "expected_timestamp_s": 3.005},
                "unexpected_tick",
                reason,
                before,
                _plain(controller.snapshot()),
            )
        )
    for label, dt in (("zero", 0.0), ("negative", -0.005)):
        controller = module.CascadedController(parameters)
        held = _reset(module, controller, 0, 0.0)
        command, estimate, feedback = _inputs(module, 0.005, held, epoch_id=0)
        before = _plain(controller.snapshot())
        reason = _caught_reason(module, lambda: controller.step(command, estimate, feedback, dt))
        invalid_samples.append(
            _rejection_sample(
                f"invalid-dt-{label}",
                {"dt_class": label, "expected_period_s": 0.005},
                "invalid_dt",
                reason,
                before,
                _plain(controller.snapshot()),
            )
        )
    for label, dt in (("nan", math.nan), ("inf", math.inf)):
        controller = module.CascadedController(parameters)
        held = _reset(module, controller, 0, 0.0)
        command, estimate, feedback = _inputs(module, 0.005, held, epoch_id=0)
        invalid_samples.append(
            _binding_rejection_sample(
                f"nonfinite-dt-{label}-binding-boundary",
                {"dt_class": label, "expected_period_s": 0.005},
                "ValueError",
                "dt_s must be finite",
                controller,
                lambda dt=dt: controller.step(command, estimate, feedback, dt),
            )
        )
    for label, dt, exception_type, message in (
        (
            "bool",
            True,
            "TypeError",
            "dt_s must be a finite real scalar",
        ),
        (
            "complex",
            0.005 + 123.0j,
            "TypeError",
            "dt_s must be a finite real scalar",
        ),
        (
            "nonexact-rational",
            Fraction(1, 3),
            "ValueError",
            "dt_s must be exactly representable as a double",
        ),
        (
            "lossy-integer",
            2**53 + 1,
            "ValueError",
            "dt_s must be exactly representable as a double",
        ),
    ):
        controller = module.CascadedController(parameters)
        held = _reset(module, controller, 0, 0.0)
        command, estimate, feedback = _inputs(module, 0.005, held, epoch_id=0)
        invalid_samples.append(
            _binding_rejection_sample(
                f"strict-dt-{label}-binding-boundary",
                {"dt_class": label, "dt_repr": repr(dt)},
                exception_type,
                message,
                controller,
                lambda dt=dt: controller.step(command, estimate, feedback, dt),
            )
        )
        if label == "bool":
            clean = module.CascadedController(parameters)
            clean_held = _reset(module, clean, 0, 0.0)
            clean_command, clean_estimate, clean_feedback = _inputs(
                module, 0.005, clean_held, epoch_id=0
            )
            controller.step(command, estimate, feedback, 0.005)
            clean.step(clean_command, clean_estimate, clean_feedback, 0.005)
            invalid_samples.append(
                _exact_sample(
                    "strict-dt-valid-same-tick-retry",
                    {"rejected_dt_class": label, "retry_dt_s": 0.005},
                    _plain(clean.snapshot()),
                    _plain(controller.snapshot()),
                    "controller state snapshot",
                )
            )
    controller = module.CascadedController(parameters)
    held = _reset(module, controller, 0, 0.0)
    for tick in range(1, 4001):
        timestamp = tick * 0.005
        command, estimate, feedback = _inputs(module, timestamp, held, epoch_id=0)
        held = controller.step(command, estimate, feedback, 0.005)
    invalid_samples.append(
        _numeric_sample(
            "integer-grid-4000-tick-summary",
            {"tick_count": 4000, "period_s": 0.005, "origin_s": 0.0},
            ["final_timestamp", "snapshot_tick_index", "expected_next_timestamp"],
            [20.0, 4000.0, 20.005],
            [
                held.timestamp_s,
                float(controller.snapshot().tick_index),
                controller.snapshot().expected_timestamp_s,
            ],
            ["s", "tick", "s"],
        )
    )
    huge = module.CascadedController(parameters)
    epoch = module.ResetEpoch()
    epoch.id = 0
    epoch.timestamp_s = 1e16
    before = _plain(huge.snapshot())
    reason = _caught_reason(
        module, lambda: huge.reset(module.ControllerInitialState(), epoch)
    )
    invalid_samples.append(
        _rejection_sample(
            "unrepresentable-huge-epoch-origin",
            {"epoch_timestamp_s": 1e16, "controller_period_s": 0.005},
            "invalid_timestamp",
            reason,
            before,
            _plain(huge.snapshot()),
        )
    )

    tested = module.CascadedController(parameters)
    clean = module.CascadedController(parameters)
    tested_held = _reset(module, tested, 0, 0.0)
    clean_held = _reset(module, clean, 0, 0.0)
    retry_samples = []
    command, estimate, feedback = _inputs(module, 0.005, tested_held, epoch_id=0)
    estimate.valid = False
    before = _plain(tested.snapshot())
    reason = _caught_reason(
        module, lambda: tested.step(command, estimate, feedback, 0.005)
    )
    retry_samples.append(
        _rejection_sample(
            "invalid-then-same-tick-retry",
            {"timestamp_s": 0.005, "estimate_valid": False},
            "invalid_estimate",
            reason,
            before,
            _plain(tested.snapshot()),
        )
    )
    command, estimate, feedback = _inputs(module, 0.005, tested_held, epoch_id=0)
    tested_held = tested.step(command, estimate, feedback, 0.005)
    command, estimate, feedback = _inputs(module, 0.005, clean_held, epoch_id=0)
    clean_held = clean.step(command, estimate, feedback, 0.005)
    retry_samples.append(
        _exact_sample(
            "corrected-retry-equals-clean-twin",
            {"timestamp_s": 0.005},
            _plain(clean.snapshot()),
            _plain(tested.snapshot()),
            "controller state snapshot",
        )
    )
    for label, timestamp in (("duplicate", 0.005), ("early", 0.009)):
        command, estimate, feedback = _inputs(module, timestamp, tested_held, epoch_id=0)
        before = _plain(tested.snapshot())
        reason = _caught_reason(
            module, lambda: tested.step(command, estimate, feedback, 0.005)
        )
        retry_samples.append(
            _rejection_sample(
                label,
                {"timestamp_s": timestamp, "expected_timestamp_s": 0.010},
                "unexpected_tick",
                reason,
                before,
                _plain(tested.snapshot()),
            )
        )
    command, estimate, feedback = _inputs(module, 0.010, tested_held, epoch_id=0)
    tested_held = tested.step(command, estimate, feedback, 0.005)
    command, estimate, feedback = _inputs(module, 0.010, clean_held, epoch_id=0)
    clean_held = clean.step(command, estimate, feedback, 0.005)
    retry_samples.append(
        _exact_sample(
            "next-due-tick-equals-clean-twin",
            {"timestamp_s": 0.010},
            _plain(clean.snapshot()),
            _plain(tested.snapshot()),
            "controller state snapshot",
        )
    )
    command, estimate, feedback = _inputs(module, 0.020, tested_held, epoch_id=0)
    before = _plain(tested.snapshot())
    reason = _caught_reason(
        module, lambda: tested.step(command, estimate, feedback, 0.005)
    )
    retry_samples.append(
        _rejection_sample(
            "missed-tick-requires-reset",
            {"timestamp_s": 0.020, "expected_timestamp_s": 0.015},
            "unexpected_tick",
            reason,
            before,
            _plain(tested.snapshot()),
        )
    )
    return [
        _case_row("B-TIME-01", invalid_samples),
        _case_row("B-TIME-02", retry_samples),
    ]


def _adapter_invalid_samples(module, repo: Path) -> list[dict[str, Any]]:
    simulation_path = repo / "01_simulation"
    estimator_path = repo / "02_estimation/b0"
    for path in (simulation_path, estimator_path):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    from b0 import Actuator, ActuatorInitialState
    from estimator import ResetEpoch as EstimatorResetEpoch

    adapter_path = repo / "03_control/b0/python/controller.py"
    spec = importlib.util.spec_from_file_location(
        "g2b_evidence_invalid_adapter", adapter_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load controller adapter for invalid-input evidence")
    adapter_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapter_module)
    numpy = importlib.import_module("numpy")

    cases = (
        (
            "command-timestamp",
            numpy.complex128(0.005 + 123.0j),
            "ControllerConfigurationError",
            "attitude_command.timestamp_s must be a real scalar",
        ),
        (
            "estimate-timestamp",
            numpy.bool_(True),
            "ControllerConfigurationError",
            "state_estimate.timestamp_s must be a real scalar",
        ),
        (
            "dt",
            Fraction(1, 3),
            "ControllerConfigurationError",
            "dt_s must be exactly representable as a double",
        ),
        (
            "command-quaternion",
            numpy.complex128(1.0 + 2.0j),
            "TypeError",
            "q_nb must be a finite real scalar",
        ),
        (
            "estimate-rate",
            numpy.bool_(True),
            "TypeError",
            "omega_b_rad_s must be a finite real scalar",
        ),
        (
            "feedback-torque",
            numpy.int64(2**53 + 1),
            "ValueError",
            "actual_torque_body_Nm must be exactly representable as a double",
        ),
    )
    samples = []
    for field, invalid_value, expected_exception, expected_message in cases:
        adapter = adapter_module.ControllerAdapter(module)
        reset_command = adapter.reset(EstimatorResetEpoch(0, 0.0))
        actuator = Actuator()
        actuator.reset(ActuatorInitialState(), 0.0)
        feedback = actuator.step_base(reset_command)
        feedback = actuator.step_base(reset_command)

        class MutableCommand:
            q_nb_command = [1.0, 0.0, 0.0, 0.0]
            timestamp_s = 0.005
            valid = True

        class MutableEstimate:
            q_nb_estimate = [1.0, 0.0, 0.0, 0.0]
            omega_b_estimate_rad_s = [0.0, 0.0, 0.0]
            timestamp_s = 0.005
            valid = True

        class MutableFeedback:
            actual_torque_body_Nm = feedback.actual_torque_body_Nm.tolist()
            limited_torque_body_Nm = feedback.limited_torque_body_Nm.tolist()
            saturated = feedback.saturated.tolist()
            timestamp_s = feedback.timestamp_s
            command_timestamp_s = feedback.command_timestamp_s

        command = MutableCommand()
        estimate = MutableEstimate()
        feedback_input = MutableFeedback()
        dt_s = 0.005
        if field == "command-timestamp":
            command.timestamp_s = invalid_value
        elif field == "estimate-timestamp":
            estimate.timestamp_s = invalid_value
        elif field == "dt":
            dt_s = invalid_value
        elif field == "command-quaternion":
            command.q_nb_command[0] = invalid_value
        elif field == "estimate-rate":
            estimate.omega_b_estimate_rad_s[0] = invalid_value
        elif field == "feedback-torque":
            feedback_input.actual_torque_body_Nm[0] = invalid_value

        samples.append(
            _exception_rejection_sample(
                f"adapter-strict-{field}",
                {
                    "adapter_entry": field,
                    "value_type": (
                        f"{type(invalid_value).__module__}."
                        f"{type(invalid_value).__name__}"
                    ),
                    "value_repr": repr(invalid_value),
                },
                expected_exception,
                expected_message,
                lambda adapter=adapter: adapter.core.snapshot(),
                lambda command=command, estimate=estimate, feedback_input=feedback_input, dt_s=dt_s, adapter=adapter: adapter.step(
                    command, estimate, feedback_input, dt_s
                ),
            )
        )
    return samples


def _invalid_case_rows(module, parameters, repo: Path) -> list[dict[str, Any]]:
    controller = module.CascadedController(parameters)
    held = _reset(module, controller, 0, 0.0)
    invalid_samples = []

    def reject_core(case_id: str, mutate, expected_reason: str) -> None:
        command, estimate, feedback = _inputs(module, 0.005, held, epoch_id=0)
        mutate(command, estimate, feedback)
        before = _plain(controller.snapshot())
        reason = _caught_reason(
            module, lambda: controller.step(command, estimate, feedback, 0.005)
        )
        invalid_samples.append(
            _rejection_sample(
                case_id,
                {"mutation": case_id},
                expected_reason,
                reason,
                before,
                _plain(controller.snapshot()),
            )
        )

    reject_core("command-valid-false", lambda q, _s, _f: setattr(q, "valid", False), "invalid_command")
    reject_core("estimate-valid-false", lambda _q, s, _f: setattr(s, "valid", False), "invalid_estimate")
    reject_core("zero-command-quaternion", lambda q, _s, _f: setattr(q, "q_nb", [0.0] * 4), "nonunit_quaternion")
    reject_core("nonunit-command-quaternion", lambda q, _s, _f: setattr(q, "q_nb", [2.0, 0.0, 0.0, 0.0]), "nonunit_quaternion")
    reject_core("out-of-limit-feedback", lambda _q, _s, f: setattr(f, "actual_torque_body_Nm", [0.36, 0.0, 0.0]), "invalid_feedback")

    setter_cases = (
        (
            module.AttitudeCommand,
            "q_nb",
            [1.0, 0.0, 0.0],
            "ValueError",
            "q_nb has the wrong length",
        ),
        (
            module.AttitudeCommand,
            "q_nb",
            [1.0, 0.0, 0.0, True],
            "TypeError",
            "q_nb must be a finite real scalar",
        ),
        (
            module.AttitudeCommand,
            "q_nb",
            [1.0 + 2.0j, 0.0, 0.0, 0.0],
            "TypeError",
            "q_nb must be a finite real scalar",
        ),
        (
            module.AttitudeCommand,
            "q_nb",
            [Fraction(1, 3), 0.0, 0.0, 0.0],
            "ValueError",
            "q_nb must be exactly representable as a double",
        ),
        (
            module.AttitudeCommand,
            "timestamp_s",
            "0.005",
            "TypeError",
            "timestamp_s must be a finite real scalar",
        ),
        (
            module.AttitudeCommand,
            "valid",
            1,
            "TypeError",
            "valid must be bool",
        ),
        (
            module.ResetEpoch,
            "timestamp_s",
            True,
            "TypeError",
            "timestamp_s must be a finite real scalar",
        ),
        (
            module.ResetEpoch,
            "timestamp_s",
            0.005 + 123.0j,
            "TypeError",
            "timestamp_s must be a finite real scalar",
        ),
        (
            module.ResetEpoch,
            "timestamp_s",
            Fraction(1, 3),
            "ValueError",
            "timestamp_s must be exactly representable as a double",
        ),
        (
            module.ResetEpoch,
            "timestamp_s",
            2**53 + 1,
            "ValueError",
            "timestamp_s must be exactly representable as a double",
        ),
        (
            module.StateEstimate,
            "omega_b_rad_s",
            [0.0, 0.0],
            "ValueError",
            "omega_b_rad_s has the wrong length",
        ),
        (
            module.StateEstimate,
            "omega_b_rad_s",
            [math.inf, 0.0, 0.0],
            "ValueError",
            "omega_b_rad_s must be finite",
        ),
        (
            module.ActuatorFeedback,
            "saturated",
            [False, 0, False],
            "TypeError",
            "saturated must be bool",
        ),
    )
    for index, (
        factory,
        attribute,
        value,
        expected_exception,
        expected_message,
    ) in enumerate(setter_cases):
        instance = factory()
        invalid_samples.append(
            _exception_rejection_sample(
                f"binding-setter-rejection-{index}",
                {"type": factory.__name__, "attribute": attribute, "value_repr": repr(value)},
                expected_exception,
                expected_message,
                lambda instance=instance: instance,
                lambda instance=instance, attribute=attribute, value=value: setattr(
                    instance, attribute, value
                ),
            )
        )

    invalid_samples.extend(_adapter_invalid_samples(module, repo))

    overflow_parameters = _copy_parameters(
        module,
        parameters,
        attitude_kp=[1e308, 1.0, 1.0],
        rate_kp=[1e308, 1.0, 1.0],
        rate_limit_rad_s=[1e308, 1.0, 1.0],
        torque_limit_Nm=[1e308, 1.0, 1.0],
    )
    overflow = module.CascadedController(overflow_parameters)
    overflow_held = _reset(module, overflow, 0, 0.0)
    command, estimate, feedback = _inputs(module, 0.005, overflow_held, epoch_id=0)
    command.q_nb = _axis_angle(0, 0.1)
    before = _plain(overflow.snapshot())
    reason = _caught_reason(
        module, lambda: overflow.step(command, estimate, feedback, 0.005)
    )
    invalid_samples.append(
        _rejection_sample(
            "derived-overflow",
            {"attitude_kp_x": 1e308, "rate_kp_x": 1e308},
            "derived_overflow",
            reason,
            before,
            _plain(overflow.snapshot()),
        )
    )

    bounds_samples = []
    epoch = module.ResetEpoch()
    for value in (2**63 - 1, -(2**63)):
        epoch.id = value
        bounds_samples.append(
            _exact_sample(
                f"int64-bound-{value}",
                {"assigned_epoch_id": str(value)},
                value,
                epoch.id,
                "signed int64 epoch",
            )
        )
    for value in (2**63, -(2**63) - 1):
        caught = None
        try:
            epoch.id = value
        except (TypeError, OverflowError) as exc:
            caught = type(exc).__name__
        bounds_samples.append(
            _exact_sample(
                f"out-of-int64-{value}",
                {"assigned_epoch_id": str(value)},
                True,
                caught in {"TypeError", "OverflowError"},
                "boolean",
            )
        )
    command = module.AttitudeCommand()
    source = [1.0, 0.0, 0.0, 0.0]
    command.q_nb = source
    source[0] = 0.0
    returned = command.q_nb
    returned[0] = 0.0
    bounds_samples.append(
        _exact_sample(
            "caller-and-output-list-mutation-isolated",
            {"mutated_caller_value": source, "mutated_returned_value": returned},
            [1.0, 0.0, 0.0, 0.0],
            list(command.q_nb),
            "scalar-first quaternion",
        )
    )
    return [
        _case_row("B-INVALID-01", invalid_samples),
        _case_row("B-INVALID-02", bounds_samples),
    ]


def _reset_case_rows(module, parameters) -> list[dict[str, Any]]:
    controller = module.CascadedController(parameters)
    held = _reset(module, controller, 0, 0.0)
    for tick, rate in enumerate((0.2, 0.4), start=1):
        timestamp = tick * 0.005
        command, estimate, feedback = _inputs(module, timestamp, held, epoch_id=0)
        command.q_nb = _axis_angle(0, 0.1)
        estimate.omega_b_rad_s = [rate, 0.0, 0.0]
        feedback.actual_torque_body_Nm = [tick * 0.01, 0.0, 0.0]
        held = controller.step(command, estimate, feedback, 0.005)
    before = _plain(controller.snapshot())
    reset_output = _reset(module, controller, 1, 0.015)
    after = _plain(controller.snapshot())
    zero_vector = [0.0, 0.0, 0.0]
    false_flags = [False, False, False]
    expected_reset_output = {
        "epoch_id": 1,
        "requested_torque_body_Nm": zero_vector,
        "limited_torque_body_Nm": zero_vector,
        "saturated": false_flags,
        "timestamp_s": 0.015,
    }
    expected_reset_diagnostics = {
        "accepted": False,
        "reason": "",
        "epoch_id": 0,
        "tick_index": 0,
        "saturated": false_flags,
        "rate_error_rad_s": zero_vector,
        "derivative_raw_rad_s2": zero_vector,
        "derivative_filtered_rad_s2": zero_vector,
        "proportional_Nm": zero_vector,
        "integral_before_Nm": zero_vector,
        "derivative_Nm": zero_vector,
        "conditional_integral_rate_Nm_s": zero_vector,
        "limit_backcalculation_rate_Nm_s": zero_vector,
        "lag_backcalculation_rate_Nm_s": zero_vector,
        "integral_after_Nm": zero_vector,
        "requested_Nm": zero_vector,
        "limited_Nm": zero_vector,
    }
    expected_reset_state = {
        "reset": True,
        "epoch_id": 1,
        "tick_index": 0,
        "epoch_origin_s": 0.015,
        "expected_timestamp_s": 0.020,
        "integral_Nm": zero_vector,
        "derivative_filtered_rad_s2": zero_vector,
        "previous_rate_rad_s": zero_vector,
        "has_previous_rate": False,
        "expected_held_command": expected_reset_output,
        "last_diagnostics": expected_reset_diagnostics,
    }
    clear_sample = _exact_sample(
        "nonzero-state-then-complete-reset",
        {"before_reset": before, "new_epoch_id": 1, "reset_timestamp_s": 0.015},
        {"reset_output": expected_reset_output, "state": expected_reset_state},
        {"reset_output": _plain(reset_output), "state": after},
        "complete reset output and controller state",
    )

    controller = module.CascadedController(parameters)
    old_reset = _reset(module, controller, 4, 1.0)
    command, estimate, feedback = _inputs(module, 1.005, old_reset, epoch_id=4)
    first = controller.step(command, estimate, feedback, 0.005)
    rejection_samples = []
    for case_id, epoch_id, timestamp, expected_reason in (
        ("duplicate-epoch", 4, 1.010, "invalid_epoch"),
        ("lower-epoch", 3, 1.010, "invalid_epoch"),
        ("equal-last-step-time", 5, 1.005, "invalid_timestamp"),
    ):
        epoch = module.ResetEpoch()
        epoch.id = epoch_id
        epoch.timestamp_s = timestamp
        before = _plain(controller.snapshot())
        reason = _caught_reason(
            module, lambda epoch=epoch: controller.reset(module.ControllerInitialState(), epoch)
        )
        rejection_samples.append(
            _rejection_sample(
                case_id,
                {"epoch_id": epoch_id, "timestamp_s": timestamp},
                expected_reason,
                reason,
                before,
                _plain(controller.snapshot()),
            )
        )
    new_reset = _reset(module, controller, 5, 1.010)
    command, estimate, replay = _inputs(module, 1.015, first, epoch_id=5)
    replay.epoch_id = 4
    before = _plain(controller.snapshot())
    reason = _caught_reason(
        module, lambda: controller.step(command, estimate, replay, 0.005)
    )
    rejection_samples.append(
        _rejection_sample(
            "prior-epoch-feedback-replay",
            {"active_epoch": new_reset.epoch_id, "feedback_epoch": replay.epoch_id},
            "epoch_mismatch",
            reason,
            before,
            _plain(controller.snapshot()),
        )
    )
    return [
        _case_row("B-RESET-01", [clear_sample]),
        _case_row("B-RESET-02", rejection_samples),
    ]


def _binding_case_rows(module, parameters, repo: Path) -> list[dict[str, Any]]:
    controller = module.CascadedController(parameters)
    held = _reset(module, controller, 7, 10.0)
    command, estimate, feedback = _inputs(module, 10.005, held, epoch_id=7)
    angle = 0.1
    command.q_nb = _axis_angle(0, angle)
    output = controller.step(command, estimate, feedback, 0.005)
    diagnostics = controller.last_diagnostics()
    expected_request = 0.08 * 4.0 * 2.0 * math.sin(angle / 2.0)
    parity = _numeric_sample(
        "cpp-python-binding-parity",
        {
            "q_nb_command": list(command.q_nb),
            "q_nb_estimate": list(estimate.q_nb),
            "module_path": str(Path(module.__file__).resolve()),
        },
        ["requested_torque_x", "timestamp", "epoch_id", "diagnostics_accepted"],
        [expected_request, 10.005, 7.0, 1.0],
        [
            output.requested_torque_body_Nm[0],
            output.timestamp_s,
            float(output.epoch_id),
            float(diagnostics.accepted),
        ],
        ["N m", "s", "epoch", "boolean"],
    )
    expected_rate_error = [
        min(
            parameters.rate_limit_rad_s[0],
            parameters.attitude_kp[0] * 2.0 * math.sin(angle / 2.0),
        ),
        0.0,
        0.0,
    ]
    expected_proportional = [
        parameters.rate_kp[axis] * expected_rate_error[axis]
        for axis in range(3)
    ]
    expected_conditional_rate = [
        parameters.rate_ki[axis] * expected_rate_error[axis]
        for axis in range(3)
    ]
    expected_integral_after = [
        parameters.controller_period_s * expected_conditional_rate[axis]
        for axis in range(3)
    ]
    zero_vector = [0.0, 0.0, 0.0]
    expected_diagnostic_vectors = {
        "rate_error_rad_s": expected_rate_error,
        "derivative_raw_rad_s2": zero_vector,
        "derivative_filtered_rad_s2": zero_vector,
        "proportional_Nm": expected_proportional,
        "integral_before_Nm": zero_vector,
        "derivative_Nm": zero_vector,
        "conditional_integral_rate_Nm_s": expected_conditional_rate,
        "limit_backcalculation_rate_Nm_s": zero_vector,
        "lag_backcalculation_rate_Nm_s": zero_vector,
        "integral_after_Nm": expected_integral_after,
        "requested_Nm": expected_proportional,
        "limited_Nm": expected_proportional,
        "saturated": [0.0, 0.0, 0.0],
    }
    diagnostic_units = {
        "rate_error_rad_s": "rad s^-1",
        "derivative_raw_rad_s2": "rad s^-2",
        "derivative_filtered_rad_s2": "rad s^-2",
        "proportional_Nm": "N m",
        "integral_before_Nm": "N m",
        "derivative_Nm": "N m",
        "conditional_integral_rate_Nm_s": "N m s^-1",
        "limit_backcalculation_rate_Nm_s": "N m s^-1",
        "lag_backcalculation_rate_Nm_s": "N m s^-1",
        "integral_after_Nm": "N m",
        "requested_Nm": "N m",
        "limited_Nm": "N m",
        "saturated": "boolean",
    }
    diagnostic_labels = []
    diagnostic_expected = []
    diagnostic_actual = []
    diagnostic_value_units = []
    for field, expected_values in expected_diagnostic_vectors.items():
        actual_values = getattr(diagnostics, field)
        for axis in range(3):
            diagnostic_labels.append(f"{field}[{axis}]")
            diagnostic_expected.append(expected_values[axis])
            diagnostic_actual.append(float(actual_values[axis]))
            diagnostic_value_units.append(diagnostic_units[field])
    diagnostic_labels.extend(("epoch_id", "tick_index"))
    diagnostic_expected.extend((7.0, 1.0))
    diagnostic_actual.extend((float(diagnostics.epoch_id), float(diagnostics.tick_index)))
    diagnostic_value_units.extend(("epoch", "tick"))
    complete_diagnostics_numeric = _numeric_sample(
        "approved-diagnostics-all-numeric-fields",
        {
            "angle_rad": angle,
            "dt_s": parameters.controller_period_s,
            "initial_integral_Nm": zero_vector,
        },
        diagnostic_labels,
        diagnostic_expected,
        diagnostic_actual,
        diagnostic_value_units,
    )
    complete_diagnostics_status = _exact_sample(
        "approved-diagnostics-status-fields",
        {"accepted_step_timestamp_s": output.timestamp_s},
        {"accepted": True, "reason": "accepted"},
        {"accepted": diagnostics.accepted, "reason": diagnostics.reason},
        "diagnostic status",
    )
    before = _plain(controller.snapshot())
    copied = controller.snapshot().integral_Nm
    copied[0] = 999.0
    returned = output.limited_torque_body_Nm
    returned[0] = 999.0
    copy_isolation = _exact_sample(
        "diagnostics-and-snapshots-are-copies",
        {"mutated_snapshot_copy_x": 999.0, "mutated_output_copy_x": 999.0},
        before,
        _plain(controller.snapshot()),
        "controller state snapshot",
    )

    numpy = importlib.import_module("numpy")
    lossless_values = (
        0,
        1,
        -1,
        0.125,
        numpy.int64(7),
        numpy.float32(0.125),
        numpy.float64(0.125),
        Fraction(1, 2),
    )
    lossless_actual = []
    for value in lossless_values:
        epoch = module.ResetEpoch()
        epoch.timestamp_s = value
        lossless_actual.append(epoch.timestamp_s)
    lossless = _numeric_sample(
        "lossless-real-scalar-acceptance",
        {
            "values": [
                {
                    "type": f"{type(value).__module__}.{type(value).__name__}",
                    "repr": repr(value),
                }
                for value in lossless_values
            ]
        },
        [f"accepted_value_{index}" for index in range(len(lossless_values))],
        [float(value) for value in lossless_values],
        lossless_actual,
        ["s"] * len(lossless_values),
    )

    simulation_path = repo / "01_simulation"
    estimator_path = repo / "02_estimation/b0"
    for path in (simulation_path, estimator_path):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    from b0 import Actuator, ActuatorInitialState, TorqueCommand
    from estimator import ResetEpoch as EstimatorResetEpoch
    from estimator import StateEstimate as EstimatorStateEstimate

    adapter_path = repo / "03_control/b0/python/controller.py"
    spec = importlib.util.spec_from_file_location("g2b_evidence_adapter", adapter_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load controller adapter for evidence")
    adapter_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapter_module)
    adapter = adapter_module.ControllerAdapter()
    reset_command = adapter.reset(EstimatorResetEpoch(0, 0.0))
    actuator = Actuator()
    actuator.reset(ActuatorInitialState(), 0.0)
    feedback = actuator.step_base(reset_command)
    feedback = actuator.step_base(reset_command)

    class Command:
        q_nb_command = (1.0, 0.0, 0.0, 0.0)
        timestamp_s = 0.005
        valid = True

    estimate = EstimatorStateEstimate((1, 0, 0, 0), (0, 0, 0), 0.005, True)
    output = adapter.step(Command(), estimate, feedback, 0.005)
    consumed = actuator.step_base(output)
    adapter_sample = _exact_sample(
        "real-g2a-estimate-g1-feedback-and-actuator-consumption",
        {
            "estimate_type": f"{type(estimate).__module__}.{type(estimate).__name__}",
            "feedback_type": f"{type(feedback).__module__}.{type(feedback).__name__}",
        },
        {
            "reset_is_g1_torque_command": True,
            "output_is_g1_torque_command": True,
            "consumed_command_timestamp_s": output.timestamp_s,
        },
        {
            "reset_is_g1_torque_command": isinstance(reset_command, TorqueCommand),
            "output_is_g1_torque_command": isinstance(output, TorqueCommand),
            "consumed_command_timestamp_s": consumed.command_timestamp_s,
        },
        "interface identity and seconds",
    )
    return [
        _case_row(
            "B-BIND-01",
            [
                parity,
                complete_diagnostics_numeric,
                complete_diagnostics_status,
                copy_isolation,
                lossless,
            ],
        ),
        _case_row("B-BIND-02", [adapter_sample]),
    ]


def _write_json(path: Path, document: dict[str, Any], newline: str = "\n") -> None:
    text = json.dumps(document, indent=2) + "\n"
    path.write_bytes(text.replace("\n", newline).encode("utf-8"))


def _canonical_lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _configuration_fixture(repo: Path, temporary_repo: Path, newline: str = "\n") -> Path:
    track = repo / "03_control/b0"
    temporary_track = temporary_repo / "03_control/b0"
    (temporary_track / "configs").mkdir(parents=True)
    (temporary_repo / "05_integration/b0/configs").mkdir(parents=True)
    (temporary_repo / "systems_engineering/reports/b0").mkdir(parents=True)
    for name in ("b0_g2_controller.v1.json", "b0_g2_controller_approval.v1.json"):
        shutil.copy2(track / "configs" / name, temporary_track / "configs" / name)
    shutil.copy2(
        repo / "05_integration/b0/validate_config.py",
        temporary_repo / "05_integration/b0/validate_config.py",
    )
    shutil.copy2(
        repo / "systems_engineering/reports/b0/g0_approval_decision.md",
        temporary_repo / "systems_engineering/reports/b0/g0_approval_decision.md",
    )
    normalized = _canonical_lf(
        (repo / "05_integration/b0/configs/b0_g0_contract.v2.json").read_bytes()
    )
    (temporary_repo / "05_integration/b0/configs/b0_g0_contract.v2.json").write_bytes(
        normalized.replace(b"\n", newline.encode("utf-8"))
    )
    return temporary_track


def _approve_fixture(temporary_track: Path) -> None:
    design_path = temporary_track / "configs/b0_g2_controller.v1.json"
    approval_path = temporary_track / "configs/b0_g2_controller_approval.v1.json"
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    approval["approved_config_canonical_lf_sha256"] = hashlib.sha256(
        _canonical_lf(design_path.read_bytes())
    ).hexdigest()
    _write_json(approval_path, approval)


def _configuration_case_rows(module, repo: Path) -> list[dict[str, Any]]:
    adapter = sys.modules["controller"]
    line_samples = []
    with tempfile.TemporaryDirectory(prefix="g2b-evidence-config-") as root:
        root_path = Path(root)
        for name, newline in (("lf", "\n"), ("crlf", "\r\n"), ("cr", "\r")):
            temporary_repo = root_path / name
            temporary_track = _configuration_fixture(repo, temporary_repo, newline)
            loaded = adapter.load_controller_parameters(module=module, track=temporary_track)
            line_samples.append(
                _numeric_sample(
                    f"authoritative-load-{name}",
                    {"line_ending": name},
                    ["controller_period", "torque_limit_x", "kaw_limit_x"],
                    [0.005, 0.35, 8.0],
                    [
                        loaded.controller_period_s,
                        loaded.torque_limit_Nm[0],
                        loaded.kaw_limit_per_s[0],
                    ],
                    ["s", "N m", "s^-1"],
                )
            )

        fail_samples = []
        cases = (
            ("g0-missing", "g0", "missing"),
            ("g0-changed", "g0", "changed"),
            ("g0-wrong-version", "g0", "wrong_version"),
            ("g0-bad-gain", "g0", "bad_gain"),
            ("implementation-missing", "implementation", "missing"),
            ("implementation-changed", "implementation", "changed"),
            ("implementation-wrong-version", "implementation", "wrong_version"),
            ("implementation-bad-tolerance", "implementation", "bad_tolerance"),
        )
        for case_id, authority, mutation in cases:
            temporary_repo = root_path / case_id
            temporary_track = _configuration_fixture(repo, temporary_repo)
            design_path = temporary_track / "configs/b0_g2_controller.v1.json"
            g0_path = temporary_repo / "05_integration/b0/configs/b0_g0_contract.v2.json"
            target = g0_path if authority == "g0" else design_path
            if mutation == "missing":
                target.unlink()
            elif mutation == "changed":
                target.write_bytes(target.read_bytes() + b" ")
            elif authority == "g0":
                document = json.loads(g0_path.read_text(encoding="utf-8"))
                if mutation == "wrong_version":
                    document["schema_version"] = "b0-g0-contract/v999"
                else:
                    document["controller_contract"]["rate_pid"]["kp"]["initial"][0] = -1.0
                _write_json(g0_path, document)
                design = json.loads(design_path.read_text(encoding="utf-8"))
                design["authority"]["g0_canonical_lf_sha256"] = hashlib.sha256(
                    _canonical_lf(g0_path.read_bytes())
                ).hexdigest()
                _write_json(design_path, design)
                _approve_fixture(temporary_track)
            else:
                design = json.loads(design_path.read_text(encoding="utf-8"))
                if mutation == "wrong_version":
                    design["schema_version"] = "999"
                else:
                    design["numeric_policy"]["timestamp_absolute_tolerance_s"] = -1.0
                _write_json(design_path, design)
                _approve_fixture(temporary_track)
            actual_type = None
            actual_message = None
            try:
                adapter.load_controller_parameters(module=module, track=temporary_track)
            except adapter.ControllerConfigurationError as exc:
                actual_type = type(exc).__name__
                actual_message = str(exc)
            if case_id == "g0-missing":
                expected_message = f"cannot read G0 contract: {g0_path}"
            elif case_id == "g0-changed":
                expected_message = "G0 canonical digest mismatch"
            elif case_id in {"g0-wrong-version", "g0-bad-gain"}:
                expected_message = "authoritative G0 validation failed"
            elif case_id == "implementation-missing":
                missing = FileNotFoundError(
                    2, "No such file or directory", str(design_path)
                )
                expected_message = f"cannot load {design_path}: {missing}"
            elif case_id == "implementation-changed":
                expected_message = (
                    "implementation configuration is not the approved S0 byte identity"
                )
            elif case_id == "implementation-wrong-version":
                expected_message = "unsupported implementation configuration identity"
            else:
                expected_message = "loaded controller parameters are invalid"
            sample = _exact_sample(
                case_id,
                {"authority": authority, "mutation": mutation},
                {
                    "exception_type": "ControllerConfigurationError",
                    "message": expected_message,
                },
                {"exception_type": actual_type, "message": actual_message},
                "exception type and message",
            )
            fail_samples.append(sample)
    return [
        _case_row("B-CONFIG-01", line_samples),
        _case_row("B-CONFIG-02", fail_samples),
    ]


def _mutation_case_rows(executions: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row_id in ("B-DETECT-01", "B-DETECT-02"):
        samples = []
        for node in S0_CASE_NODES[row_id]:
            record = executions[node]
            expected_test = MUTATION_ORACLES[node]
            sample = _exact_sample(
                node.rsplit("::", 1)[-1],
                {"mutation_node": node, "unchanged_oracle_node": expected_test},
                True,
                record["status"] == "pass"
                and "detected subject mutation" in record["output"],
                "mutation detection outcome",
            )
            sample["actual"]["execution"] = record
            samples.append(sample)
        rows.append(_case_row(row_id, samples))
    return rows


def _attach_node_executions(
    rows: list[dict[str, Any]], sources: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    available: dict[str, dict[str, Any]] = {}
    for source in sources:
        for node, record in source["nodes"].items():
            if node in available:
                raise RuntimeError(f"duplicate executed node across JUnit sources: {node}")
            available[node] = {"source_kind": source["kind"], **deepcopy(record)}
    for row in rows:
        row["node_executions"] = []
        for node in row["nodes"]:
            if node not in available:
                raise RuntimeError(f"S0 row {row['row_id']} node was not collected: {node}")
            row["node_executions"].append({"node": node, **deepcopy(available[node])})
    return available


def _case_traces(
    module,
    parameters,
    repo: Path,
    ctest_junit: Path,
    pytest_junit: Path,
) -> dict[str, Any]:
    execution_sources = [
        _junit_execution(ctest_junit, "ctest"),
        _junit_execution(pytest_junit, "pytest"),
    ]
    rows = [
        *_attitude_case_rows(module, parameters),
        *_rate_derivative_case_rows(module, parameters),
        *_limit_case_rows(module, parameters),
        *_antiwindup_case_rows(module, parameters),
        *_pair_case_rows(module, parameters),
        *_time_case_rows(module, parameters),
        *_invalid_case_rows(module, parameters, repo),
        *_reset_case_rows(module, parameters),
        *_binding_case_rows(module, parameters, repo),
        *_configuration_case_rows(module, repo),
    ]
    available = _attach_node_executions(rows, execution_sources)
    rows.extend(_mutation_case_rows(available))
    _attach_node_executions(rows[-2:], execution_sources)
    rows.sort(key=lambda row: row["row_id"])
    matrix_path = repo / "systems_engineering/reports/b0/g2b_s0_controller_verification_matrix.md"
    return {
        "matrix_path": str(matrix_path.relative_to(repo)).replace("\\", "/"),
        "matrix_sha256": _sha256(matrix_path),
        "execution_sources": execution_sources,
        "rows": rows,
        "all_rows_pass": all(row["result"] for row in rows),
    }


def build_evidence(
    module_dir: Path,
    build_dir: Path,
    build_type: str,
    ctest_junit: Path,
    pytest_junit: Path,
) -> dict[str, Any]:
    track = Path(__file__).resolve().parent
    repo = track.parents[1]
    module_dir = module_dir.resolve()
    build_dir = build_dir.resolve()
    cache_entries = _validated_build_layout(
        module_dir,
        build_dir,
        build_type,
        repo,
        track.relative_to(repo),
    )
    sys.path.insert(0, str(module_dir))
    module = importlib.import_module("b0_controller")
    module_path = Path(module.__file__).resolve()
    if module_dir not in module_path.parents:
        raise RuntimeError(f"loaded stale controller module outside build: {module_path}")
    parameters = _parameters(module)

    attitude = _attitude_sign_probe(module, parameters)
    antiwindup = _antiwindup_probe(module, parameters)
    pairing = _paired_timing_probe(module, parameters)
    rejection = _atomic_rejection_probe(module, parameters)
    case_traces = _case_traces(
        module,
        parameters,
        repo,
        ctest_junit.resolve(),
        pytest_junit.resolve(),
    )

    config = track / "configs/b0_g2_controller.v1.json"
    approval = track / "configs/b0_g2_controller_approval.v1.json"
    g0 = repo / "05_integration/b0/configs/b0_g0_contract.v2.json"
    validator = repo / "05_integration/b0/validate_config.py"
    source_commit = _git(repo, "rev-parse", "HEAD")
    criteria = {
        "attitude_request_absolute_error_le_1e_12": attitude[
            "max_request_abs_error_Nm"
        ]
        <= ABS_TOL,
        "saturation_request_absolute_error_le_1e_12": antiwindup["errors"][
            "request_Nm"
        ]
        <= ABS_TOL,
        "saturation_limit_absolute_error_le_1e_12": antiwindup["errors"][
            "limited_Nm"
        ]
        <= ABS_TOL,
        "antiwindup_integral_absolute_error_le_1e_12": antiwindup["errors"][
            "integral_after_Nm"
        ]
        <= ABS_TOL,
        "antiwindup_limit_term_absolute_error_le_1e_12": antiwindup["errors"][
            "limit_backcalculation_rate_Nm_s"
        ]
        <= ABS_TOL,
        "paired_feedback_uses_previous_publication": pairing[
            "each_feedback_pairs_previous_publication"
        ],
        "invalid_input_rejection_is_atomic": rejection["snapshot_unchanged"],
        "corrected_retry_publishes_due_tick": abs(
            rejection["corrected_same_tick_retry"]["timestamp_s"] - 12.005
        )
        <= ABS_TOL,
        "complete_s0_case_traces_pass": case_traces["all_rows_pass"],
    }
    evidence = {
        "schema_version": "b0-g2b-controller-evidence/v2",
        "source_commit": source_commit,
        "component": "B0 G2-B cascaded attitude/body-rate controller",
        "execution_identity": _execution_identity(source_commit),
        "claim_boundary": {
            "level": "module_component",
            "g3_closed_loop_performance": False,
            "sil": False,
            "hil": False,
            "board_execution": False,
            "flight": False,
        },
        "build": _build_identity(
            module_dir,
            module_path,
            build_dir,
            build_type,
            repo,
            cache_entries,
        ),
        "configuration": {
            "implementation_path": str(config.relative_to(repo)).replace("\\", "/"),
            "implementation_sha256": _sha256(config),
            "approval_path": str(approval.relative_to(repo)).replace("\\", "/"),
            "approval_sha256": _sha256(approval),
            "g0_path": str(g0.relative_to(repo)).replace("\\", "/"),
            "g0_sha256": _sha256(g0),
            "validator_path": str(validator.relative_to(repo)).replace("\\", "/"),
            "validator_sha256": _sha256(validator),
        },
        "observations": {
            "attitude_sign_and_cascade": attitude,
            "saturation_and_limit_backcalculation": antiwindup,
            "paired_three_tick_timing": pairing,
            "atomic_invalid_measurement_rejection": rejection,
        },
        "case_traces": case_traces,
        "criteria": criteria,
        "all_selected_component_criteria_pass": all(criteria.values()),
        "limitations": [
            "The bounded case traces retain raw component inputs, independent expectations, actual production-module values and the exact JUnit nodes for all 26 S0 rows; they are component evidence, not an independent verification platform.",
            "The artifact does not measure G3 recovery time, overshoot, yaw drift, cross-axis performance, or scenario acceptance.",
            "No plant truth is provided to the controller inputs.",
            "A pending PA review is not evidence acceptance.",
        ],
    }
    validate_evidence(
        evidence,
        junit_paths={"ctest": ctest_junit.resolve(), "pytest": pytest_junit.resolve()},
        matrix_path=(
            repo
            / "systems_engineering/reports/b0/g2b_s0_controller_verification_matrix.md"
        ),
    )
    return evidence


def validate_evidence(
    evidence: dict[str, Any],
    *,
    junit_paths: dict[str, Path],
    matrix_path: Path,
) -> None:
    """Fail closed when an artifact omits a review-critical identity or trace."""

    def need(condition: bool, message: str) -> None:
        if not condition:
            raise ValueError(f"invalid G2-B evidence: {message}")

    need(
        evidence.get("schema_version") == "b0-g2b-controller-evidence/v2",
        "schema version",
    )
    source_commit = evidence.get("source_commit")
    need(
        isinstance(source_commit, str)
        and re.fullmatch(r"[0-9a-f]{40}", source_commit) is not None,
        "source commit",
    )
    need(set(source_commit) != {"0"}, "source commit cannot be all zero")
    execution = evidence.get("execution_identity")
    need(isinstance(execution, dict), "execution identity")
    need(
        execution.get("checked_out_source_commit") == source_commit,
        "execution/source commit mismatch",
    )
    need(
        execution.get("context") in {"local", "github_actions"},
        "execution context",
    )
    if execution["context"] == "github_actions":
        need(
            isinstance(execution.get("run_id"), str)
            and execution["run_id"].isdigit(),
            "Actions run ID",
        )
        need(bool(execution.get("event_name")), "Actions event")
        need(
            isinstance(execution.get("github_sha_metadata"), str)
            and re.fullmatch(
                r"[0-9a-f]{40}", execution["github_sha_metadata"]
            )
            is not None,
            "Actions metadata SHA",
        )
    build = evidence.get("build")
    need(isinstance(build, dict), "build identity")
    for field in (
        "build_type",
        "cmake_build_type",
        "build_directory",
        "cmake_cache_directory",
        "cmake_home_directory",
        "module_directory",
        "module_path",
        "module_sha256",
        "cmake_cache_sha256",
        "python",
        "python_executable",
        "generator_python_executable",
        "python_abi",
        "cmake",
        "cxx_compiler",
        "cxx",
    ):
        need(bool(build.get(field)), f"build.{field}")
    need(build["build_type"] in {"Debug", "Release"}, "build type")
    need(
        build["cmake_build_type"] == build["build_type"],
        "declared/CMake build type mismatch",
    )
    need(
        build["cmake_cache_directory"] == build["build_directory"],
        "declared/CMake build directory mismatch",
    )
    need(build["cmake_home_directory"] == ".", "CMake source directory")
    declared_build = PurePosixPath(str(build["build_directory"]).replace("\\", "/"))
    declared_module = PurePosixPath(
        str(build["module_directory"]).replace("\\", "/")
    )
    declared_module_path = PurePosixPath(
        str(build["module_path"]).replace("\\", "/")
    )
    need(
        declared_module == declared_build / "03_control/b0",
        "module/build directory mismatch",
    )
    try:
        module_relative = declared_module_path.relative_to(declared_module)
    except ValueError:
        module_relative = None
    need(
        module_relative is not None and bool(module_relative.parts),
        "module path outside declared module directory",
    )
    need(build.get("cmake_python_matches_generator") is True, "Python ABI owner")
    need(
        re.fullmatch(r"[0-9a-f]{64}", build["module_sha256"]) is not None,
        "module digest",
    )
    need(
        re.fullmatch(r"[0-9a-f]{64}", build["cmake_cache_sha256"])
        is not None,
        "CMake cache digest",
    )
    pybind = build.get("pybind11")
    need(
        isinstance(pybind, dict)
        and pybind.get("version") == "2.13.6"
        and bool(pybind.get("cmake_directory")),
        "actual pybind11 identity",
    )
    catch2 = build.get("catch2")
    need(
        isinstance(catch2, dict) and catch2.get("version") == "3.5.4",
        "actual Catch2 version",
    )
    if catch2.get("mode") == "fetched_pinned_revision":
        need(
            catch2.get("git_revision")
            == "b5373dadca40b7edc8570cf9470b9b1cb1934d40"
            and bool(catch2.get("source_directory")),
            "fetched Catch2 revision/source",
        )
    elif catch2.get("mode") == "installed_exact_package":
        need(
            bool(catch2.get("cmake_directory"))
            and re.fullmatch(
                r"[0-9a-f]{64}", catch2.get("config_version_sha256", "")
            )
            is not None,
            "installed Catch2 package identity",
        )
    else:
        need(False, "Catch2 resolution mode")

    configuration = evidence.get("configuration")
    need(isinstance(configuration, dict), "configuration identity")
    for field in (
        "implementation_path",
        "implementation_sha256",
        "approval_path",
        "approval_sha256",
        "g0_path",
        "g0_sha256",
        "validator_path",
        "validator_sha256",
    ):
        need(bool(configuration.get(field)), f"configuration.{field}")
    for field in (
        "implementation_sha256",
        "approval_sha256",
        "g0_sha256",
        "validator_sha256",
    ):
        need(
            re.fullmatch(r"[0-9a-f]{64}", configuration[field]) is not None,
            f"configuration.{field} digest",
        )

    observations = evidence.get("observations")
    need(isinstance(observations, dict), "observations")
    for field in (
        "attitude_sign_and_cascade",
        "saturation_and_limit_backcalculation",
        "paired_three_tick_timing",
        "atomic_invalid_measurement_rejection",
    ):
        need(field in observations, f"observations.{field}")

    attitude = observations["attitude_sign_and_cascade"]
    need(isinstance(attitude, dict), "attitude observation")
    for field in (
        "input",
        "independent_oracle",
        "actual",
        "diagnostics",
        "max_request_abs_error_Nm",
    ):
        need(field in attitude, f"attitude observation.{field}")
    need(attitude["diagnostics"].get("accepted") is True, "attitude accepted")
    need(attitude["diagnostics"].get("reason") == "accepted", "attitude reason")

    antiwindup = observations["saturation_and_limit_backcalculation"]
    need(isinstance(antiwindup, dict), "anti-windup observation")
    for field in ("input", "independent_oracle", "actual", "diagnostics", "errors"):
        need(field in antiwindup, f"anti-windup observation.{field}")
    for field in (
        "accepted",
        "reason",
        "proportional_Nm",
        "integral_before_Nm",
        "derivative_Nm",
        "conditional_integral_rate_Nm_s",
        "limit_backcalculation_rate_Nm_s",
        "lag_backcalculation_rate_Nm_s",
        "integral_after_Nm",
        "requested_Nm",
        "limited_Nm",
    ):
        need(field in antiwindup["diagnostics"], f"anti-windup diagnostics.{field}")
    need(antiwindup["diagnostics"]["accepted"] is True, "anti-windup accepted")
    need(antiwindup["diagnostics"]["reason"] == "accepted", "anti-windup reason")
    for field in (
        "requested_torque_body_Nm",
        "limited_torque_body_Nm",
        "saturated",
        "timestamp_s",
    ):
        need(field in antiwindup["actual"], f"anti-windup actual.{field}")

    timing = observations["paired_three_tick_timing"]
    need(isinstance(timing, dict), "paired timing observation")
    trace = timing.get("trace")
    need(isinstance(trace, list) and len(trace) == 3, "three-tick pairing trace")
    for index, row in enumerate(trace, start=1):
        need(isinstance(row, dict), f"pairing trace row {index}")
        for field in (
            "tick_index",
            "current_timestamp_s",
            "paired_command_timestamp_s",
            "feedback_limited_torque_body_Nm",
            "output",
            "diagnostics",
        ):
            need(field in row, f"pairing trace row {index}.{field}")
        need(row["diagnostics"].get("accepted") is True, f"pairing trace row {index} accepted")
        need(row["diagnostics"].get("reason") == "accepted", f"pairing trace row {index} reason")
    need(
        isinstance(timing.get("independent_expected_publication_times_s"), list)
        and len(timing["independent_expected_publication_times_s"]) == 4,
        "paired timing independent publication times",
    )
    need(
        timing.get("each_feedback_pairs_previous_publication") is True,
        "paired timing result",
    )

    rejection = observations["atomic_invalid_measurement_rejection"]
    need(isinstance(rejection, dict), "atomic rejection observation")
    for field in (
        "invalid_input",
        "stable_reason",
        "snapshot_before",
        "snapshot_after",
        "snapshot_unchanged",
        "corrected_same_tick_retry",
    ):
        need(field in rejection, f"atomic rejection.{field}")
    need(bool(rejection["stable_reason"]), "atomic rejection stable reason")
    need(rejection["snapshot_unchanged"] is True, "atomic rejection snapshot equality")

    case_traces = evidence.get("case_traces")
    need(isinstance(case_traces, dict), "case traces")
    need(
        case_traces.get("matrix_path")
        == "systems_engineering/reports/b0/g2b_s0_controller_verification_matrix.md",
        "case trace matrix path",
    )
    need(
        re.fullmatch(r"[0-9a-f]{64}", case_traces.get("matrix_sha256", ""))
        is not None,
        "case trace matrix digest",
    )
    resolved_matrix_path = Path(matrix_path).resolve()
    need(resolved_matrix_path.is_file(), "case trace matrix bytes exist")
    need(
        resolved_matrix_path.as_posix().endswith(case_traces["matrix_path"]),
        "case trace matrix byte path",
    )
    need(
        _sha256(resolved_matrix_path) == case_traces["matrix_sha256"],
        "case trace matrix byte digest match",
    )
    execution_sources = case_traces.get("execution_sources")
    need(
        isinstance(execution_sources, list) and len(execution_sources) == 2,
        "case trace execution sources",
    )
    need(
        {source.get("kind") for source in execution_sources} == {"ctest", "pytest"},
        "case trace execution source kinds",
    )
    build_suffix = str(build["build_type"]).lower()
    expected_junit_names = {
        "ctest": f"ctest-{build_suffix}.xml",
        "pytest": f"pytest-{build_suffix}.xml",
    }
    need(set(junit_paths) == {"ctest", "pytest"}, "complete JUnit byte sources")
    for source in execution_sources:
        kind = source["kind"]
        need(
            source.get("path") == expected_junit_names[kind],
            f"{kind} JUnit path",
        )
        digest = source.get("sha256", "")
        need(
            re.fullmatch(r"[0-9a-f]{64}", digest) is not None
            and set(digest) != {"0"},
            f"{kind} JUnit digest",
        )
        need(
            isinstance(source.get("size_bytes"), int) and source["size_bytes"] > 0,
            f"{kind} JUnit byte size",
        )
        need(
            isinstance(source.get("collected_testcases"), int)
            and source["collected_testcases"] > 0,
            f"{kind} collected testcases",
        )
        nodes = source.get("nodes")
        need(isinstance(nodes, dict) and nodes, f"{kind} nodes")
        invocation_total = 0
        for node, record in nodes.items():
            need(isinstance(node, str) and node, f"{kind} JUnit node name")
            need(isinstance(record, dict), f"JUnit node {node} record")
            need(record.get("status") == "pass", f"JUnit node {node} result")
            invocation_count = record.get("invocation_count")
            collected_cases = record.get("collected_cases")
            need(
                isinstance(invocation_count, int) and invocation_count > 0,
                f"JUnit node {node} invocation count",
            )
            need(
                isinstance(collected_cases, list)
                and len(collected_cases) == invocation_count
                and all(isinstance(name, str) and name for name in collected_cases),
                f"JUnit node {node} collected cases",
            )
            duration = record.get("duration_s")
            need(
                isinstance(duration, (int, float))
                and not isinstance(duration, bool)
                and math.isfinite(float(duration))
                and duration >= 0.0,
                f"JUnit node {node} duration",
            )
            need(isinstance(record.get("output"), str), f"JUnit node {node} output")
            invocation_total += invocation_count
        need(
            source["collected_testcases"] == invocation_total,
            f"{kind} collected testcase count",
        )
        junit_path = Path(junit_paths[kind]).resolve()
        need(junit_path.is_file(), f"{kind} JUnit bytes exist")
        need(junit_path.name == source["path"], f"{kind} JUnit byte path")
        need(
            junit_path.stat().st_size == source["size_bytes"],
            f"{kind} JUnit byte size match",
        )
        need(_sha256(junit_path) == digest, f"{kind} JUnit byte digest match")
        try:
            parsed_source = _junit_execution(junit_path, kind)
        except (ET.ParseError, OSError, RuntimeError, TypeError, ValueError) as exc:
            raise ValueError(
                f"invalid G2-B evidence: {kind} JUnit bytes parse"
            ) from exc
        need(
            parsed_source == source,
            f"{kind} JUnit parsed content match",
        )
    executed_nodes: dict[str, dict[str, Any]] = {}
    for source in execution_sources:
        for node, record in source["nodes"].items():
            need(
                node not in executed_nodes,
                f"duplicate JUnit node across execution sources: {node}",
            )
            need(isinstance(record, dict), f"JUnit node {node} record")
            executed_nodes[node] = {
                "node": node,
                "source_kind": source["kind"],
                **record,
            }

    rows = case_traces.get("rows")
    need(isinstance(rows, list), "case trace rows")
    need(len(rows) == len(S0_CASE_NODES), "all 26 S0 rows exactly once")
    row_ids = [row.get("row_id") for row in rows if isinstance(row, dict)]
    need(
        len(row_ids) == len(rows) and set(row_ids) == set(S0_CASE_NODES),
        "complete S0 row IDs",
    )
    need(len(row_ids) == len(set(row_ids)), "duplicate S0 row ID")
    for row in rows:
        row_id = row["row_id"]
        need(
            row.get("nodes") == list(S0_CASE_NODES[row_id]),
            f"{row_id} exact controlled nodes",
        )
        node_executions = row.get("node_executions")
        need(
            isinstance(node_executions, list)
            and [record.get("node") for record in node_executions] == row["nodes"],
            f"{row_id} node executions",
        )
        for record in node_executions:
            node = record["node"]
            need(
                executed_nodes.get(node) == record,
                f"{row_id} node {node} detached from JUnit source",
            )
            need(
                record.get("source_kind") in {"ctest", "pytest"},
                f"{row_id} node {node} source",
            )
            need(record.get("status") == "pass", f"{row_id} node {node} result")
            need(
                isinstance(record.get("invocation_count"), int)
                and record["invocation_count"] > 0,
                f"{row_id} node {node} invocation count",
            )
            need(
                isinstance(record.get("collected_cases"), list)
                and record["collected_cases"],
                f"{row_id} node {node} collected cases",
            )
        samples = row.get("samples")
        need(isinstance(samples, list) and samples, f"{row_id} samples")
        row_manifest = S0_CASE_MANIFEST[row_id]
        sample_results = []
        case_ids = []
        for sample in samples:
            need(isinstance(sample, dict), f"{row_id} sample structure")
            case_id = sample.get("case_id")
            need(isinstance(case_id, str) and case_id, f"{row_id} sample case ID")
            need(case_id in row_manifest, f"{row_id}/{case_id} declared case")
            case_contract = row_manifest[case_id]
            case_ids.append(case_id)
            need(isinstance(sample.get("input"), dict), f"{row_id}/{case_id} input")
            need(bool(sample["input"]), f"{row_id}/{case_id} nonempty input")
            need(
                bool(case_contract["input_keys"])
                and set(case_contract["input_keys"]) == set(sample["input"]),
                f"{row_id}/{case_id} exact contracted input fields",
            )
            expected = sample.get("independent_expected")
            actual = sample.get("actual")
            units = sample.get("units")
            need(isinstance(expected, dict), f"{row_id}/{case_id} expected")
            need(isinstance(actual, dict), f"{row_id}/{case_id} actual")
            need(
                isinstance(units, list)
                and units
                and all(isinstance(unit, str) and unit for unit in units),
                f"{row_id}/{case_id} units",
            )
            need(
                units == list(case_contract["units"]),
                f"{row_id}/{case_id} contracted units",
            )
            absolute = sample.get("absolute_tolerance")
            relative = sample.get("relative_tolerance")
            need(
                isinstance(absolute, (int, float))
                and math.isfinite(float(absolute))
                and absolute >= 0.0,
                f"{row_id}/{case_id} absolute tolerance",
            )
            need(
                isinstance(relative, (int, float))
                and math.isfinite(float(relative))
                and relative >= 0.0,
                f"{row_id}/{case_id} relative tolerance",
            )
            comparison = sample.get("comparison")
            need(isinstance(comparison, dict), f"{row_id}/{case_id} comparison")
            kind = comparison.get("kind")
            need(
                kind == case_contract["kind"],
                f"{row_id}/{case_id} contracted comparison kind",
            )
            if kind == "numeric":
                labels = expected.get("labels")
                expected_values = expected.get("values")
                actual_values = actual.get("values")
                need(
                    isinstance(labels, list)
                    and isinstance(expected_values, list)
                    and isinstance(actual_values, list)
                    and len(labels)
                    == len(expected_values)
                    == len(actual_values)
                    == len(units)
                    and len(labels) > 0,
                    f"{row_id}/{case_id} numeric dimensions",
                )
                need(
                    all(isinstance(label, str) and label for label in labels),
                    f"{row_id}/{case_id} numeric labels",
                )
                need(
                    labels == list(case_contract["labels"]),
                    f"{row_id}/{case_id} contracted numeric labels",
                )
                contracted_expected = case_contract.get("expected_values")
                if contracted_expected is not None:
                    need(
                        len(expected_values) == len(contracted_expected)
                        and all(
                            math.isclose(
                                float(value),
                                float(contracted),
                                rel_tol=0.0,
                                abs_tol=ABS_TOL,
                            )
                            for value, contracted in zip(
                                expected_values, contracted_expected
                            )
                        ),
                        f"{row_id}/{case_id} contracted numeric oracle",
                    )
                need(
                    0.0 <= float(absolute) <= ABS_TOL and float(relative) == 0.0,
                    f"{row_id}/{case_id} bounded numeric tolerance",
                )
                need(
                    all(
                        isinstance(value, (int, float))
                        and not isinstance(value, bool)
                        and math.isfinite(float(value))
                        for value in [*expected_values, *actual_values]
                    ),
                    f"{row_id}/{case_id} finite numeric values",
                )
                errors = [
                    abs(float(actual_value) - float(expected_value))
                    for actual_value, expected_value in zip(
                        actual_values, expected_values
                    )
                ]
                recalculated = all(
                    math.isclose(
                        float(actual_value),
                        float(expected_value),
                        rel_tol=float(relative),
                        abs_tol=float(absolute),
                    )
                    for actual_value, expected_value in zip(
                        actual_values, expected_values
                    )
                )
                need(
                    comparison.get("max_absolute_error") == max(errors, default=0.0),
                    f"{row_id}/{case_id} numeric error calculation",
                )
            elif kind == "exact":
                need("value" in expected, f"{row_id}/{case_id} exact expected value")
                need("value" in actual, f"{row_id}/{case_id} exact actual value")
                need(absolute == 0.0 and relative == 0.0, f"{row_id}/{case_id} exact tolerance")
                expected_value_keys = case_contract.get("expected_value_keys", ())
                if expected_value_keys:
                    need(
                        isinstance(expected["value"], dict)
                        and set(expected_value_keys) <= set(expected["value"]),
                        f"{row_id}/{case_id} contracted expected value fields",
                    )
                actual_value_keys = case_contract.get("actual_value_keys", ())
                if actual_value_keys:
                    need(
                        isinstance(actual["value"], dict)
                        and set(actual_value_keys) <= set(actual["value"]),
                        f"{row_id}/{case_id} contracted actual value fields",
                    )
                recalculated = actual["value"] == expected["value"]
            elif kind == "rejection_atomic":
                need(bool(expected.get("reason")), f"{row_id}/{case_id} rejection reason")
                need(
                    expected.get("state_change") == "none",
                    f"{row_id}/{case_id} rejection state oracle",
                )
                for field in ("reason", "snapshot_before", "snapshot_after"):
                    need(field in actual, f"{row_id}/{case_id} rejection actual {field}")
                need(absolute == 0.0 and relative == 0.0, f"{row_id}/{case_id} rejection tolerance")
                recalculated = (
                    actual["reason"] == expected["reason"]
                    and actual["snapshot_before"] == actual["snapshot_after"]
                )
            elif kind == "binding_rejection_atomic":
                for field in ("exception_type", "message"):
                    need(
                        isinstance(expected.get(field), str) and expected[field],
                        f"{row_id}/{case_id} binding rejection expected {field}",
                    )
                    need(
                        isinstance(actual.get(field), str) and actual[field],
                        f"{row_id}/{case_id} binding rejection actual {field}",
                    )
                need(
                    expected.get("warning_count") == 0,
                    f"{row_id}/{case_id} binding rejection warning oracle",
                )
                need(
                    isinstance(actual.get("warning_count"), int)
                    and actual["warning_count"] >= 0,
                    f"{row_id}/{case_id} binding rejection actual warning count",
                )
                need(
                    expected.get("state_change") == "none",
                    f"{row_id}/{case_id} binding rejection state oracle",
                )
                for field in ("snapshot_before", "snapshot_after"):
                    need(
                        field in actual,
                        f"{row_id}/{case_id} binding rejection actual {field}",
                    )
                need(
                    absolute == 0.0 and relative == 0.0,
                    f"{row_id}/{case_id} binding rejection tolerance",
                )
                recalculated = (
                    actual["exception_type"] == expected["exception_type"]
                    and actual["message"] == expected["message"]
                    and actual["warning_count"] == expected["warning_count"]
                    and actual["snapshot_before"] == actual["snapshot_after"]
                )
            else:
                need(False, f"{row_id}/{case_id} comparison kind")
                recalculated = False
            need(
                comparison.get("result") is recalculated,
                f"{row_id}/{case_id} comparison result",
            )
            need(recalculated, f"{row_id}/{case_id} failed comparison")
            if row_id == "B-ATT-03" and case_id == "mixed-half-turn-signs-and-values":
                inverse_root_three = 1.0 / math.sqrt(3.0)
                need(
                    sample["input"]["q_nb_estimate"] == [1.0, 0.0, 0.0, 0.0]
                    and len(sample["input"]["q_nb_command"]) == 4
                    and all(
                        math.isclose(
                            float(value),
                            target,
                            rel_tol=0.0,
                            abs_tol=ABS_TOL,
                        )
                        for value, target in zip(
                            sample["input"]["q_nb_command"],
                            [
                                0.0,
                                inverse_root_three,
                                -inverse_root_three,
                                inverse_root_three,
                            ],
                        )
                    ),
                    f"{row_id}/{case_id} approved mixed-axis input",
                )
            if row_id == "B-AW-03":
                match = re.fullmatch(
                    r"axis-([0-2])-sign-([+-]1)-saturate-release", case_id
                )
                need(match is not None, f"{row_id}/{case_id} contracted case identity")
                axis = int(match.group(1))
                sign = int(match.group(2))
                need(
                    sample["input"]
                    == {
                        "axis": axis,
                        "saturation_rate_rad_s": -0.2 * sign,
                        "release_rate_rad_s": -0.002 * sign,
                    },
                    f"{row_id}/{case_id} approved release input",
                )
                approved_release_oracle = [
                    1.0,
                    -0.8 * sign,
                    0.1 * sign,
                    -0.001 * sign,
                    0.0,
                    0.2 * sign,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0,
                ]
                need(
                    len(expected["values"]) == len(approved_release_oracle)
                    and all(
                        math.isclose(
                            float(value), target, rel_tol=0.0, abs_tol=ABS_TOL
                        )
                        for value, target in zip(
                            expected["values"], approved_release_oracle
                        )
                    ),
                    f"{row_id}/{case_id} approved release oracle",
                )
            if row_id == "B-RESET-01":
                snapshot_fields = {
                    "reset",
                    "epoch_id",
                    "tick_index",
                    "epoch_origin_s",
                    "expected_timestamp_s",
                    "integral_Nm",
                    "derivative_filtered_rad_s2",
                    "previous_rate_rad_s",
                    "has_previous_rate",
                    "expected_held_command",
                    "last_diagnostics",
                }
                command_fields = {
                    "epoch_id",
                    "requested_torque_body_Nm",
                    "limited_torque_body_Nm",
                    "saturated",
                    "timestamp_s",
                }
                diagnostic_fields = {
                    "accepted",
                    "reason",
                    "epoch_id",
                    "tick_index",
                    "saturated",
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
                }
                before_reset = sample["input"].get("before_reset")
                need(
                    sample["input"].get("new_epoch_id") == 1
                    and sample["input"].get("reset_timestamp_s") == 0.015,
                    f"{row_id}/{case_id} approved reset input",
                )
                need(
                    isinstance(before_reset, dict)
                    and snapshot_fields <= set(before_reset),
                    f"{row_id}/{case_id} complete pre-reset state",
                )
                need(
                    before_reset["has_previous_rate"] is True
                    and any(abs(float(value)) > ABS_TOL for value in before_reset["integral_Nm"])
                    and any(
                        abs(float(value)) > ABS_TOL
                        for value in before_reset["derivative_filtered_rad_s2"]
                    )
                    and any(
                        abs(float(value)) > ABS_TOL
                        for value in before_reset["previous_rate_rad_s"]
                    ),
                    f"{row_id}/{case_id} established pre-reset history",
                )
                for side, payload in (
                    ("expected", expected["value"]),
                    ("actual", actual["value"]),
                ):
                    reset_output = payload.get("reset_output")
                    state = payload.get("state")
                    need(
                        isinstance(reset_output, dict)
                        and command_fields <= set(reset_output),
                        f"{row_id}/{case_id} {side} reset output fields",
                    )
                    need(
                        isinstance(state, dict) and snapshot_fields <= set(state),
                        f"{row_id}/{case_id} {side} reset state fields",
                    )
                    need(
                        isinstance(state.get("expected_held_command"), dict)
                        and command_fields <= set(state["expected_held_command"]),
                        f"{row_id}/{case_id} {side} held command fields",
                    )
                    need(
                        isinstance(state.get("last_diagnostics"), dict)
                        and diagnostic_fields <= set(state["last_diagnostics"]),
                        f"{row_id}/{case_id} {side} diagnostics fields",
                    )
                    zero_vector = [0.0, 0.0, 0.0]
                    false_vector = [False, False, False]
                    approved_reset_output = {
                        "epoch_id": 1,
                        "requested_torque_body_Nm": zero_vector,
                        "limited_torque_body_Nm": zero_vector,
                        "saturated": false_vector,
                        "timestamp_s": 0.015,
                    }
                    approved_diagnostics = {
                        "accepted": False,
                        "reason": "",
                        "epoch_id": 0,
                        "tick_index": 0,
                        "saturated": false_vector,
                        "rate_error_rad_s": zero_vector,
                        "derivative_raw_rad_s2": zero_vector,
                        "derivative_filtered_rad_s2": zero_vector,
                        "proportional_Nm": zero_vector,
                        "integral_before_Nm": zero_vector,
                        "derivative_Nm": zero_vector,
                        "conditional_integral_rate_Nm_s": zero_vector,
                        "limit_backcalculation_rate_Nm_s": zero_vector,
                        "lag_backcalculation_rate_Nm_s": zero_vector,
                        "integral_after_Nm": zero_vector,
                        "requested_Nm": zero_vector,
                        "limited_Nm": zero_vector,
                    }
                    approved_state = {
                        "reset": True,
                        "epoch_id": 1,
                        "tick_index": 0,
                        "epoch_origin_s": 0.015,
                        "expected_timestamp_s": 0.02,
                        "integral_Nm": zero_vector,
                        "derivative_filtered_rad_s2": zero_vector,
                        "previous_rate_rad_s": zero_vector,
                        "has_previous_rate": False,
                        "expected_held_command": approved_reset_output,
                        "last_diagnostics": approved_diagnostics,
                    }
                    need(
                        reset_output == approved_reset_output
                        and state == approved_state,
                        f"{row_id}/{case_id} {side} approved reset semantics",
                    )
            if row_id == "B-BIND-01" and case_id == "approved-diagnostics-status-fields":
                need(
                    expected.get("value") == {"accepted": True, "reason": "accepted"},
                    f"{row_id}/{case_id} approved diagnostic status",
                )
            if row_id == "B-CONFIG-02":
                expected_failure = expected["value"]
                need(
                    expected_failure.get("exception_type")
                    == "ControllerConfigurationError",
                    f"{row_id}/{case_id} configuration exception type",
                )
                message = expected_failure.get("message")
                need(
                    isinstance(message, str) and message,
                    f"{row_id}/{case_id} configuration exception message",
                )
                exact_messages = {
                    "g0-changed": "G0 canonical digest mismatch",
                    "g0-wrong-version": "authoritative G0 validation failed",
                    "g0-bad-gain": "authoritative G0 validation failed",
                    "implementation-changed": (
                        "implementation configuration is not the approved S0 byte identity"
                    ),
                    "implementation-wrong-version": (
                        "unsupported implementation configuration identity"
                    ),
                    "implementation-bad-tolerance": (
                        "loaded controller parameters are invalid"
                    ),
                }
                if case_id == "g0-missing":
                    need(
                        message.startswith("cannot read G0 contract: ")
                        and message.endswith("b0_g0_contract.v2.json"),
                        f"{row_id}/{case_id} exact failure reason",
                    )
                elif case_id == "implementation-missing":
                    need(
                        message.startswith("cannot load ")
                        and "b0_g2_controller.v1.json" in message,
                        f"{row_id}/{case_id} exact failure reason",
                    )
                else:
                    need(
                        message == exact_messages[case_id],
                        f"{row_id}/{case_id} exact failure reason",
                    )
            if row_id in {"B-DETECT-01", "B-DETECT-02"}:
                mutation_node = sample["input"].get("mutation_node")
                oracle_node = sample["input"].get("unchanged_oracle_node")
                need(
                    mutation_node in MUTATION_ORACLES
                    and case_id == mutation_node.rsplit("::", 1)[-1],
                    f"{row_id}/{case_id} mutation identity",
                )
                need(
                    oracle_node == MUTATION_ORACLES[mutation_node],
                    f"{row_id}/{case_id} unchanged oracle identity",
                )
                execution = actual.get("execution")
                controlled_execution = executed_nodes[mutation_node]
                expected_execution = {
                    key: value
                    for key, value in controlled_execution.items()
                    if key != "node"
                }
                need(
                    execution == expected_execution,
                    f"{row_id}/{case_id} mutation execution binding",
                )
                # Some CTest/JUnit versions truncate the wrapper's trailing
                # oracle name.  Exact node-to-oracle identity is already fixed
                # above by MUTATION_ORACLES; the output must retain the stable
                # positive-detection marker.
                marker = "detected subject mutation"
                need(
                    marker in execution["output"],
                    f"{row_id}/{case_id} mutation detection marker",
                )
                need(
                    expected.get("value") is True and actual.get("value") is True,
                    f"{row_id}/{case_id} mutation detection result",
                )
            sample_results.append(recalculated)
        need(len(case_ids) == len(set(case_ids)), f"{row_id} duplicate case ID")
        need(
            len(case_ids) == len(row_manifest) and set(case_ids) == set(row_manifest),
            f"{row_id} exact required cases",
        )
        need(row.get("result") is all(sample_results), f"{row_id} aggregate result")
        need(row["result"] is True, f"{row_id} failed row")
    need(case_traces.get("all_rows_pass") is True, "case trace aggregate result")

    criteria = evidence.get("criteria")
    need(
        isinstance(criteria, dict)
        and criteria
        and all(isinstance(value, bool) for value in criteria.values()),
        "boolean criteria",
    )
    required_criteria = {
        "attitude_request_absolute_error_le_1e_12",
        "saturation_request_absolute_error_le_1e_12",
        "saturation_limit_absolute_error_le_1e_12",
        "antiwindup_integral_absolute_error_le_1e_12",
        "antiwindup_limit_term_absolute_error_le_1e_12",
        "paired_feedback_uses_previous_publication",
        "invalid_input_rejection_is_atomic",
        "corrected_retry_publishes_due_tick",
        "complete_s0_case_traces_pass",
    }
    need(required_criteria <= set(criteria), "required component criteria")
    need(all(criteria.values()), "selected component criterion failed")
    need(
        evidence.get("all_selected_component_criteria_pass") is True,
        "aggregate criterion",
    )
    boundary = evidence.get("claim_boundary")
    need(
        isinstance(boundary, dict)
        and boundary.get("level") == "module_component"
        and all(
            boundary.get(field) is False
            for field in (
                "g3_closed_loop_performance",
                "sil",
                "hil",
                "board_execution",
                "flight",
            )
        ),
        "claim boundary",
    )
    need(bool(evidence.get("limitations")), "limitations")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--module-dir", type=Path, required=True)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--build-type", choices=("Debug", "Release"), required=True)
    parser.add_argument("--ctest-junit", type=Path, required=True)
    parser.add_argument("--pytest-junit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evidence = build_evidence(
        args.module_dir,
        args.build_dir,
        args.build_type,
        args.ctest_junit,
        args.pytest_junit,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if not evidence["all_selected_component_criteria_pass"]:
        raise SystemExit("G2-B evidence criterion failed")


if __name__ == "__main__":
    main()
