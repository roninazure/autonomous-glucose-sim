from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PumpConfig:
    dose_increment_u: float = 0.05
    max_units_per_interval: float = 1.0


@dataclass
class PumpRequest:
    requested_units: float


@dataclass
class PumpResult:
    delivered_units: float
    clipped: bool
    rounded: bool
    reason: str
