from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SafetyInputs:
    recommended_units: float
    predicted_glucose_mgdl: float
    insulin_on_board_u: float


@dataclass
class SafetyThresholds:
    max_units_per_interval: float = 1.0
    max_insulin_on_board_u: float = 3.0
    min_predicted_glucose_mgdl: float = 80.0


@dataclass
class SafetyDecision:
    status: str
    allowed: bool
    final_units: float
    reason: str
