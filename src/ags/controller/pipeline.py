from __future__ import annotations

from ags.controller.detector import detect_excursion
from ags.controller.predictor import predict_glucose
from ags.controller.recommender import recommend_correction
from ags.controller.state import ControllerInputs, CorrectionRecommendation, ExcursionSignal, GlucosePrediction
from ags.detection.meal import detect_meal
from ags.detection.state import MealSignal


def run_controller(
    inputs: ControllerInputs,
) -> tuple[ExcursionSignal, GlucosePrediction, CorrectionRecommendation, MealSignal | None]:
    signal = detect_excursion(inputs)

    # Autonomous meal detection — runs whenever glucose_history is populated,
    # regardless of whether autonomous_isf is enabled, so callers always get
    # the meal signal for annotation even in manual mode.
    meal_signal: MealSignal | None = None
    if len(inputs.glucose_history) >= 3:
        meal_signal = detect_meal(inputs.glucose_history, step_minutes=inputs.step_minutes)
        # Attach to inputs so the recommender can act on ONSET pre-bolus
        if inputs.autonomous_isf:
            inputs.meal_signal = meal_signal

    prediction = predict_glucose(inputs, signal, step_minutes=inputs.step_minutes)
    recommendation = recommend_correction(inputs, prediction, signal=signal)
    return signal, prediction, recommendation, meal_signal
