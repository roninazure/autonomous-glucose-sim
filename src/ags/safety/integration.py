from __future__ import annotations

from ags.controller.state import CorrectionRecommendation, ExcursionSignal, GlucosePrediction
from ags.safety.state import SafetyInputs


def build_safety_inputs(
    recommendation: CorrectionRecommendation,
    prediction: GlucosePrediction,
    signal: ExcursionSignal,
    insulin_on_board_u: float,
    current_glucose_mgdl: float = 0.0,
) -> SafetyInputs:
    return SafetyInputs(
        recommended_units=recommendation.recommended_units,
        predicted_glucose_mgdl=prediction.predicted_glucose_mgdl,
        insulin_on_board_u=insulin_on_board_u,
        trend_confirmed=signal.rising,
        rate_mgdl_per_min=signal.rate_mgdl_per_min,
        acceleration_mgdl_per_min2=signal.acceleration_mgdl_per_min2,
        current_glucose_mgdl=current_glucose_mgdl,
    )
