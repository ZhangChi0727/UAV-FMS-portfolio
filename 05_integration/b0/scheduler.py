"""Integer-tick scheduling primitives for the approved B0 G3 loop."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


class ScheduleContractError(ValueError):
    """Raised when a schedule does not match the approved G0 timing contract."""


@dataclass(frozen=True)
class TickSchedule:
    """One epoch-local base boundary and its component due flags."""

    local_tick: int
    timestamp_s: float
    plant_due: bool
    actuator_due: bool
    imu_due: bool
    estimator_due: bool
    controller_due: bool


@dataclass(frozen=True)
class IntegerScheduler:
    """Derive all timestamps and due decisions from integer local ticks."""

    base_period_s: float
    plant_every_ticks: int
    actuator_every_ticks: int
    imu_every_ticks: int
    estimator_every_ticks: int
    controller_every_ticks: int

    @classmethod
    def from_contract(cls, contract: Mapping[str, Any]) -> "IntegerScheduler":
        try:
            timing = contract["timing"]
            schedules = timing["schedules"]
            scheduler = cls(
                base_period_s=float(timing["base_period_s"]),
                plant_every_ticks=int(schedules["plant_every_ticks"]),
                actuator_every_ticks=int(schedules["actuator_every_ticks"]),
                imu_every_ticks=int(schedules["imu_every_ticks"]),
                estimator_every_ticks=int(schedules["estimator_every_ticks"]),
                controller_every_ticks=int(schedules["controller_every_ticks"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ScheduleContractError(f"invalid G0 timing field: {exc}") from exc
        scheduler.validate()
        return scheduler

    def validate(self) -> None:
        if self.base_period_s <= 0.0:
            raise ScheduleContractError("base_period_s must be positive")
        periods = (
            self.plant_every_ticks,
            self.actuator_every_ticks,
            self.imu_every_ticks,
            self.estimator_every_ticks,
            self.controller_every_ticks,
        )
        if any(isinstance(period, bool) or period <= 0 for period in periods):
            raise ScheduleContractError("component periods must be positive integers")
        if self.plant_every_ticks != 1 or self.actuator_every_ticks != 1:
            raise ScheduleContractError("G3 requires plant and actuator on every base tick")
        if not (
            self.imu_every_ticks
            == self.estimator_every_ticks
            == self.controller_every_ticks
        ):
            raise ScheduleContractError(
                "IMU, estimator and controller periods must be identical"
            )

    def boundary(self, local_tick: int, epoch_origin_s: float = 0.0) -> TickSchedule:
        if isinstance(local_tick, bool) or not isinstance(local_tick, int):
            raise ScheduleContractError("local_tick must be an integer")
        if local_tick < 0:
            raise ScheduleContractError("local_tick must be non-negative")
        timestamp = float(epoch_origin_s) + local_tick * self.base_period_s
        if local_tick == 0:
            return TickSchedule(local_tick, timestamp, False, False, False, False, False)

        def due(period: int) -> bool:
            return local_tick % period == 0

        return TickSchedule(
            local_tick=local_tick,
            timestamp_s=timestamp,
            plant_due=due(self.plant_every_ticks),
            actuator_due=due(self.actuator_every_ticks),
            imu_due=due(self.imu_every_ticks),
            estimator_due=due(self.estimator_every_ticks),
            controller_due=due(self.controller_every_ticks),
        )


__all__ = ["IntegerScheduler", "ScheduleContractError", "TickSchedule"]
