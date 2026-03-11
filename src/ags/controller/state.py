from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ControllerInputs:
    current_glucose_mgdl: float
    previous_glucose_mgdl: float
    insulin_on_board_u: float
    target_glucose_mgdl: float = 110.0
    correction_factor_mgdl_per_unit: float = 50.0


@dataclass
class ExcursionSignal:
    glucose_delta_mgdl: float
    rising: bool
    falling: bool


@dataclass
class GlucosePrediction:
    predicted_glucose_mgdl: float
    prediction_horizon_minutes: int


@dataclass
class CorrectionRecommendation:
    recommended_units: float
    reason: str
