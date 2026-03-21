from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ControllerInputs:
    current_glucose_mgdl: float
    previous_glucose_mgdl: float
    insulin_on_board_u: float
    target_glucose_mgdl: float = 110.0
    correction_factor_mgdl_per_unit: float = 50.0
    # Recent CGM history (oldest → newest, including current reading).
    # When populated with 3+ readings, the predictor uses exponential
    # smoothing over the recent trend instead of naive linear extrapolation.
    glucose_history: list[float] = field(default_factory=list)
    # Minimum glucose delta (mg/dL per step) required before the controller
    # fires any correction. Filters out noise-driven micro-excursions.
    min_excursion_delta_mgdl: float = 0.0
    # Fraction of the calculated correction to deliver as a microbolus.
    # 1.0 = full correction; 0.25 = quarter-dose microbolus strategy.
    microbolus_fraction: float = 1.0


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
