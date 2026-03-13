from ags.controller.state import ControllerInputs
from ags.safety.pipeline import run_controller_with_safety
from ags.safety.state import SafetyThresholds


def test_run_controller_with_safety_clips_recommendation() -> None:
    controller_inputs = ControllerInputs(
        current_glucose_mgdl=150.0,
        previous_glucose_mgdl=140.0,
        insulin_on_board_u=0.5,
        target_glucose_mgdl=110.0,
        correction_factor_mgdl_per_unit=50.0,
    )

    safety_thresholds = SafetyThresholds(
        max_units_per_interval=1.0,
        max_insulin_on_board_u=3.0,
        min_predicted_glucose_mgdl=80.0,
    )

    signal, prediction, recommendation, safety_decision = run_controller_with_safety(
        controller_inputs=controller_inputs,
        safety_thresholds=safety_thresholds,
    )

    assert signal.glucose_delta_mgdl == 10.0
    assert prediction.predicted_glucose_mgdl == 210.0
    assert recommendation.recommended_units == 2.0
    assert safety_decision.status == "clipped"
    assert safety_decision.allowed is True
    assert safety_decision.final_units == 1.0
    assert safety_decision.reason == "recommendation clipped to max units per interval"


def test_run_controller_with_safety_blocks_high_iob() -> None:
    controller_inputs = ControllerInputs(
        current_glucose_mgdl=150.0,
        previous_glucose_mgdl=140.0,
        insulin_on_board_u=3.5,
        target_glucose_mgdl=110.0,
        correction_factor_mgdl_per_unit=50.0,
    )

    safety_thresholds = SafetyThresholds(
        max_units_per_interval=1.0,
        max_insulin_on_board_u=3.0,
        min_predicted_glucose_mgdl=80.0,
    )

    signal, prediction, recommendation, safety_decision = run_controller_with_safety(
        controller_inputs=controller_inputs,
        safety_thresholds=safety_thresholds,
    )

    assert signal.glucose_delta_mgdl == 10.0
    assert prediction.predicted_glucose_mgdl == 210.0
    assert recommendation.recommended_units == 2.0
    assert safety_decision.status == "blocked"
    assert safety_decision.allowed is False
    assert safety_decision.final_units == 0.0
    assert safety_decision.reason == "insulin on board exceeds safety threshold"
