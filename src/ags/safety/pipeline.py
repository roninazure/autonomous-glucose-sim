from __future__ import annotations

from ags.controller.pipeline import run_controller
from ags.controller.state import ControllerInputs, CorrectionRecommendation, ExcursionSignal, GlucosePrediction
from ags.safety.evaluator import evaluate_safety
from ags.safety.integration import build_safety_inputs
from ags.safety.state import SafetyDecision, SafetyThresholds


def run_controller_with_safety(
    controller_inputs: ControllerInputs,
    safety_thresholds: SafetyThresholds | None = None,
) -> tuple[ExcursionSignal, GlucosePrediction, CorrectionRecommendation, SafetyDecision]:
    signal, prediction, recommendation, _meal_signal = run_controller(controller_inputs)

    safety_inputs = build_safety_inputs(
        recommendation=recommendation,
        prediction=prediction,
        signal=signal,
        insulin_on_board_u=controller_inputs.insulin_on_board_u,
    )

    safety_decision = evaluate_safety(safety_inputs, safety_thresholds)
    return signal, prediction, recommendation, safety_decision
