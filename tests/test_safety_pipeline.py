from ags.controller.state import ControllerInputs
from ags.safety.pipeline import run_controller_with_safety
from ags.safety.state import SafetyThresholds


def test_run_controller_with_safety_allows_recommendation() -> None:
    # G=140 (above SWARM floor 130), rising at 1 mg/dL/min → SWARM produces 0.9 U < max 1.0 U
    controller_inputs = ControllerInputs(
        current_glucose_mgdl=140.0,
        previous_glucose_mgdl=135.0,
        insulin_on_board_u=0.5,
        swarm_bolus=True,
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

    assert signal.glucose_delta_mgdl == 5.0
    assert prediction.predicted_glucose_mgdl == 170.0
    assert recommendation.recommended_units == pytest.approx(0.9, abs=1e-9)
    assert safety_decision.status == "allowed"
    assert safety_decision.allowed is True
    assert safety_decision.final_units == pytest.approx(0.9, abs=1e-9)
    assert safety_decision.reason == "recommendation allowed"


def test_run_controller_with_safety_clips_recommendation() -> None:
    # G=150, rising at 2 mg/dL/min → SWARM produces 1.0 U (capped at max_pulse) > max_interval 0.5 U
    controller_inputs = ControllerInputs(
        current_glucose_mgdl=150.0,
        previous_glucose_mgdl=140.0,
        insulin_on_board_u=0.5,
        swarm_bolus=True,
    )

    safety_thresholds = SafetyThresholds(
        max_units_per_interval=0.5,
        max_insulin_on_board_u=3.0,
        min_predicted_glucose_mgdl=80.0,
    )

    signal, prediction, recommendation, safety_decision = run_controller_with_safety(
        controller_inputs=controller_inputs,
        safety_thresholds=safety_thresholds,
    )

    assert signal.glucose_delta_mgdl == 10.0
    assert prediction.predicted_glucose_mgdl == 210.0
    assert recommendation.recommended_units == 1.0
    assert safety_decision.status == "clipped"
    assert safety_decision.allowed is True
    assert safety_decision.final_units == 0.5
    assert safety_decision.reason == "recommendation clipped to max units per interval"


def test_run_controller_with_safety_blocks_high_iob() -> None:
    # G=150, rising → SWARM produces 0.63 U but IOB=3.5 >= max_iob=3.0 → blocked
    controller_inputs = ControllerInputs(
        current_glucose_mgdl=150.0,
        previous_glucose_mgdl=140.0,
        insulin_on_board_u=3.5,
        swarm_bolus=True,
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
    assert recommendation.recommended_units == pytest.approx(0.63, abs=0.01)
    assert safety_decision.status == "blocked"
    assert safety_decision.allowed is False
    assert safety_decision.final_units == 0.0
    assert safety_decision.reason == "insulin on board exceeds safety threshold"


def test_run_controller_with_safety_blocks_low_predicted_glucose() -> None:
    # G=140, rising → SWARM produces 1.0 U but predicted=200 < min_predicted=250 → blocked
    controller_inputs = ControllerInputs(
        current_glucose_mgdl=140.0,
        previous_glucose_mgdl=130.0,
        insulin_on_board_u=0.0,
        swarm_bolus=True,
    )

    safety_thresholds = SafetyThresholds(
        max_units_per_interval=2.0,
        max_insulin_on_board_u=3.0,
        min_predicted_glucose_mgdl=250.0,
    )

    signal, prediction, recommendation, safety_decision = run_controller_with_safety(
        controller_inputs=controller_inputs,
        safety_thresholds=safety_thresholds,
    )

    assert signal.glucose_delta_mgdl == 10.0
    assert prediction.predicted_glucose_mgdl == 200.0
    assert recommendation.recommended_units == 1.0
    assert safety_decision.status == "blocked"
    assert safety_decision.allowed is False
    assert safety_decision.final_units == 0.0
    assert safety_decision.reason == "predicted glucose below safety threshold"


import pytest
