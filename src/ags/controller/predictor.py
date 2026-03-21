from __future__ import annotations

from ags.controller.state import ControllerInputs, ExcursionSignal, GlucosePrediction

# Smoothing factor for exponential smoothing of glucose deltas.
# α=0.4 weights recent readings more heavily while dampening noise spikes.
_ALPHA = 0.4


def _smoothed_rate_mgdl_per_step(history: list[float]) -> float:
    """Return an exponentially smoothed rate of change (mg/dL per step).

    Applies EWM over consecutive deltas in ``history`` (oldest → newest).
    With α=0.4 a single noise spike carries only ~14% weight three steps later,
    versus 100% in the naive single-delta approach.
    """
    deltas = [history[i] - history[i - 1] for i in range(1, len(history))]
    smoothed = deltas[0]
    for d in deltas[1:]:
        smoothed = _ALPHA * d + (1 - _ALPHA) * smoothed
    return smoothed


def predict_glucose(
    inputs: ControllerInputs,
    signal: ExcursionSignal,
    prediction_horizon_minutes: int = 30,
    step_minutes: int = 5,
) -> GlucosePrediction:
    steps_ahead = max(1, prediction_horizon_minutes // step_minutes)

    if len(inputs.glucose_history) >= 3:
        # Exponential smoothing over recent CGM trend — dampens noise spikes
        # that would otherwise cause the naive linear approach to over- or
        # under-react on the next prediction horizon.
        rate = _smoothed_rate_mgdl_per_step(inputs.glucose_history)
    else:
        # Fall back to single-step delta when history is too short.
        rate = signal.glucose_delta_mgdl

    predicted_glucose = inputs.current_glucose_mgdl + (rate * steps_ahead)

    return GlucosePrediction(
        predicted_glucose_mgdl=predicted_glucose,
        prediction_horizon_minutes=prediction_horizon_minutes,
    )
