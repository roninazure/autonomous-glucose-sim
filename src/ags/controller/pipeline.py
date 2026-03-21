from __future__ import annotations

from ags.controller.detector import detect_excursion
from ags.controller.predictor import predict_glucose
from ags.controller.recommender import recommend_correction
from ags.controller.state import ControllerInputs, CorrectionRecommendation, ExcursionSignal, GlucosePrediction
from ags.detection.classifier import classify_glucose_dynamics
from ags.detection.state import GlucoseDynamicsClassification


def run_controller(
    inputs: ControllerInputs,
) -> tuple[ExcursionSignal, GlucosePrediction, CorrectionRecommendation, GlucoseDynamicsClassification | None]:
    signal = detect_excursion(inputs)

    # Full glucose dynamics classification — runs whenever history is available.
    # Determines whether any rise is meal-driven, basal drift, rebound, or mixed.
    # The recommender uses this to choose the appropriate dosing strategy.
    classification: GlucoseDynamicsClassification | None = None
    if len(inputs.glucose_history) >= 3:
        classification = classify_glucose_dynamics(
            inputs.glucose_history,
            step_minutes=inputs.step_minutes,
        )
        if inputs.autonomous_isf and classification is not None:
            # Attach meal signal so pre-bolus logic in recommender can fire
            inputs.meal_signal = classification.meal_signal

    prediction = predict_glucose(inputs, signal, step_minutes=inputs.step_minutes)
    recommendation = recommend_correction(inputs, prediction, signal=signal, classification=classification)
    return signal, prediction, recommendation, classification
