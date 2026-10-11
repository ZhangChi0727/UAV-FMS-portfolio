"""Scalar-first Hamilton quaternion utilities for the B0 NED/FRD model."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

try:
    from .contract import ContractValidationError, _vector
except ImportError:  # pragma: no cover - supports direct track execution
    from contract import ContractValidationError, _vector


def _normalizable(value: Any, name: str = "quaternion") -> np.ndarray:
    quaternion = _vector(value, 4, name)
    norm = float(np.linalg.norm(quaternion))
    if not math.isfinite(norm) or norm <= 0.0:
        raise ContractValidationError(f"{name} must have a finite non-zero norm")
    return quaternion / norm


def normalize_quaternion(quaternion: Any) -> np.ndarray:
    """Return a normalized scalar-first quaternion ``[w, x, y, z]``."""

    return _normalizable(quaternion)


def quaternion_multiply(left: Any, right: Any) -> np.ndarray:
    """Hamilton product using scalar-first quaternion ordering."""

    q_left = _vector(left, 4, "left quaternion")
    q_right = _vector(right, 4, "right quaternion")
    w0, x0, y0, z0 = q_left
    w1, x1, y1, z1 = q_right
    return np.array(
        [
            w0 * w1 - x0 * x1 - y0 * y1 - z0 * z1,
            w0 * x1 + x0 * w1 + y0 * z1 - z0 * y1,
            w0 * y1 - x0 * z1 + y0 * w1 + z0 * x1,
            w0 * z1 + x0 * y1 - y0 * x1 + z0 * w1,
        ],
        dtype=np.float64,
    )


def quaternion_conjugate(quaternion: Any) -> np.ndarray:
    q = _normalizable(quaternion)
    return np.array([q[0], -q[1], -q[2], -q[3]], dtype=np.float64)


def quaternion_inverse(quaternion: Any) -> np.ndarray:
    """Return the inverse of a finite non-zero quaternion."""

    q = _normalizable(quaternion)
    return quaternion_conjugate(q)


def rotate_body_to_ned(quaternion_nb: Any, vector_body: Any) -> np.ndarray:
    """Rotate a body/FRD vector into NED using ``q_nb``."""

    q = _normalizable(quaternion_nb, "q_nb")
    vector = _vector(vector_body, 3, "vector_body")
    rotated = quaternion_multiply(quaternion_multiply(q, [0.0, *vector]), quaternion_conjugate(q))
    return rotated[1:]


def rotate_ned_to_body(quaternion_nb: Any, vector_ned: Any) -> np.ndarray:
    """Rotate a NED vector into body/FRD using ``q_nb``."""

    q = _normalizable(quaternion_nb, "q_nb")
    vector = _vector(vector_ned, 3, "vector_ned")
    rotated = quaternion_multiply(quaternion_multiply(quaternion_conjugate(q), [0.0, *vector]), q)
    return rotated[1:]


def quaternion_distance_rad(reference: Any, actual: Any) -> float:
    """Return the sign-invariant shortest rotation distance in radians."""

    q_delta = quaternion_multiply(quaternion_inverse(reference), _normalizable(actual, "actual quaternion"))
    q_delta = _normalizable(q_delta, "delta quaternion")
    return float(2.0 * math.atan2(np.linalg.norm(q_delta[1:]), abs(float(q_delta[0]))))


def quaternion_from_axis_angle(axis: Any, angle_rad: float) -> np.ndarray:
    axis_vector = _vector(axis, 3, "axis")
    axis_norm = float(np.linalg.norm(axis_vector))
    if axis_norm <= 0.0 or not math.isfinite(axis_norm):
        raise ContractValidationError("axis must have a finite non-zero norm")
    if not math.isfinite(float(angle_rad)):
        raise ContractValidationError("angle_rad must be finite")
    half_angle = 0.5 * float(angle_rad)
    return np.array(
        [math.cos(half_angle), *(axis_vector / axis_norm * math.sin(half_angle))],
        dtype=np.float64,
    )


__all__ = [
    "normalize_quaternion",
    "quaternion_conjugate",
    "quaternion_distance_rad",
    "quaternion_from_axis_angle",
    "quaternion_inverse",
    "quaternion_multiply",
    "rotate_body_to_ned",
    "rotate_ned_to_body",
]
