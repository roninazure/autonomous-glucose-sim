from __future__ import annotations

from ags.controller.state import ControllerInputs, ExcursionSignal, GlucosePrediction


def predict_glucose(
    inputs: ControllerInputs,
    signal: ExcursionSignal,
    prediction_horizon_minutes: int = 30,
    step_minutes: int = 5,
) -> GlucosePrediction:
    steps_ahead = max(1, prediction_horizon_minutes // step_minutes)
    predicted_glucose = inputs.current_glucose_mgdl + (signal.glucose_delta_mgdl * steps_ahead)

    return GlucosePrediction(
        predicted_glucose_mgdl=predicted_glucose,
        prediction_horizon_minutes=prediction_horizon_minutes,
    )
