from __future__ import annotations

from ags.controller.state import CorrectionRecommendation, ExcursionSignal, GlucosePrediction
from ags.safety.state import SafetyInputs


def build_safety_inputs(
    recommendation: CorrectionRecommendation,
    prediction: GlucosePrediction,
    signal: ExcursionSignal,
    insulin_on_board_u: float,
    current_glucose_mgdl: float = 0.0,
    delivered_last_30min_u: float = 0.0,
    delivered_last_2hr_u: float = 0.0,
    minutes_since_meal_detected: float = 0.0,
    correction_factor_mgdl_per_unit: float = 50.0,
) -> SafetyInputs:
    # IOB-aware pessimistic prediction: applied only in SWARM / closed-loop mode
    # (identified by the caller tracking rolling delivery windows) AND only when
    # IOB is high enough to pose an over-delivery risk (> 4 U).
    # Below this threshold the normal IOB cap and arming gate are sufficient.
    # Above it the ROC predictor is blind to accumulated insulin, so we subtract
    # the expected 30-min effect (60 % of IOB × ISF) to block further dosing.
    _IOB_DECAY_FRACTION_30MIN = 0.60
    _IOB_APPLY_THRESHOLD_U = 4.5
    if delivered_last_2hr_u > 0.0 and insulin_on_board_u > _IOB_APPLY_THRESHOLD_U:
        iob_adjusted = (
            prediction.predicted_glucose_mgdl
            - insulin_on_board_u * _IOB_DECAY_FRACTION_30MIN * correction_factor_mgdl_per_unit
        )
        effective_predicted = min(prediction.predicted_glucose_mgdl, iob_adjusted)
    else:
        effective_predicted = prediction.predicted_glucose_mgdl

    return SafetyInputs(
        recommended_units=recommendation.recommended_units,
        predicted_glucose_mgdl=effective_predicted,
        insulin_on_board_u=insulin_on_board_u,
        trend_confirmed=signal.rising,
        rate_mgdl_per_min=signal.rate_mgdl_per_min,
        acceleration_mgdl_per_min2=signal.acceleration_mgdl_per_min2,
        current_glucose_mgdl=current_glucose_mgdl,
        delivered_last_30min_u=delivered_last_30min_u,
        delivered_last_2hr_u=delivered_last_2hr_u,
        minutes_since_meal_detected=minutes_since_meal_detected,
    )
