from __future__ import annotations

from ags.controller.state import CorrectionRecommendation, ExcursionSignal, GlucosePrediction
from ags.safety.state import SafetyInputs


def build_safety_inputs(
    recommendation: CorrectionRecommendation,
    prediction: GlucosePrediction,
    signal: ExcursionSignal,
    insulin_on_board_u: float,
) -> SafetyInputs:
    return SafetyInputs(
        recommended_units=recommendation.recommended_units,
        predicted_glucose_mgdl=prediction.predicted_glucose_mgdl,
        insulin_on_board_u=insulin_on_board_u,
        trend_confirmed=signal.rising,
    )
