from __future__ import annotations

from ags.controller.state import ControllerInputs, ExcursionSignal


def detect_excursion(
    inputs: ControllerInputs,
    rise_threshold_mgdl: float = 5.0,
    fall_threshold_mgdl: float = -5.0,
) -> ExcursionSignal:
    glucose_delta = inputs.current_glucose_mgdl - inputs.previous_glucose_mgdl

    return ExcursionSignal(
        glucose_delta_mgdl=glucose_delta,
        rising=glucose_delta >= rise_threshold_mgdl,
        falling=glucose_delta <= fall_threshold_mgdl,
    )
