from __future__ import annotations

from ags.controller.state import ControllerInputs, ExcursionSignal


def detect_excursion(
    inputs: ControllerInputs,
    rise_threshold_mgdl_per_min: float = 1.0,
    fall_threshold_mgdl_per_min: float = -1.0,
) -> ExcursionSignal:
    """Detect glucose trend direction and compute rate of change.

    Thresholds are expressed in mg/dL **per minute** so that the detector
    behaves consistently regardless of whether the loop runs at 1-min
    (FreeStyle Libre) or 5-min (Dexcom G6/G7) cadence.

    Args:
        inputs: Controller inputs including current/previous CGM values and
            the loop step_minutes used to normalise the per-step delta.
        rise_threshold_mgdl_per_min: Rate above which glucose is flagged
            as rising.  Default 1.0 mg/dL/min ≈ 5 mg/dL over 5 minutes.
        fall_threshold_mgdl_per_min: Rate below which glucose is flagged
            as falling (supply as a negative value).
    """
    glucose_delta = inputs.current_glucose_mgdl - inputs.previous_glucose_mgdl
    step = max(1, inputs.step_minutes)
    rate_mgdl_per_min = glucose_delta / step

    # Compute acceleration (second derivative) when at least 3 readings are
    # available in glucose_history.  Acceleration > 0 means glucose is rising
    # faster (spike still building); < 0 means decelerating (peak approaching).
    acceleration_mgdl_per_min2 = 0.0
    history = inputs.glucose_history
    if len(history) >= 3:
        prev_rate = (history[-2] - history[-3]) / step
        acceleration_mgdl_per_min2 = (rate_mgdl_per_min - prev_rate) / step

    return ExcursionSignal(
        glucose_delta_mgdl=glucose_delta,
        rate_mgdl_per_min=rate_mgdl_per_min,
        rising=rate_mgdl_per_min >= rise_threshold_mgdl_per_min,
        falling=rate_mgdl_per_min <= fall_threshold_mgdl_per_min,
        acceleration_mgdl_per_min2=acceleration_mgdl_per_min2,
    )
