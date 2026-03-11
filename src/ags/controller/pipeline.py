from __future__ import annotations

from ags.controller.detector import detect_excursion
from ags.controller.predictor import predict_glucose
from ags.controller.recommender import recommend_correction
from ags.controller.state import ControllerInputs, CorrectionRecommendation, ExcursionSignal, GlucosePrediction


def run_controller(
    inputs: ControllerInputs,
) -> tuple[ExcursionSignal, GlucosePrediction, CorrectionRecommendation]:
    signal = detect_excursion(inputs)
    prediction = predict_glucose(inputs, signal)
    recommendation = recommend_correction(inputs, prediction)
    return signal, prediction, recommendation
