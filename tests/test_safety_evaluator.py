from ags.safety.evaluator import evaluate_safety
from ags.safety.state import SafetyInputs, SafetyThresholds


def test_evaluate_safety_clips_excessive_recommendation() -> None:
    inputs = SafetyInputs(
        recommended_units=2.0,
        predicted_glucose_mgdl=210.0,
        insulin_on_board_u=0.5,
    )
    thresholds = SafetyThresholds(
        max_units_per_interval=1.0,
        max_insulin_on_board_u=3.0,
        min_predicted_glucose_mgdl=80.0,
    )

    decision = evaluate_safety(inputs, thresholds)

    assert decision.status == "clipped"
    assert decision.allowed is True
    assert decision.final_units == 1.0
    assert decision.reason == "recommendation clipped to max units per interval"


def test_evaluate_safety_blocks_low_predicted_glucose() -> None:
    inputs = SafetyInputs(
        recommended_units=1.0,
        predicted_glucose_mgdl=75.0,
        insulin_on_board_u=0.5,
    )

    decision = evaluate_safety(inputs)

    assert decision.status == "blocked"
    assert decision.allowed is False
    assert decision.final_units == 0.0
    assert decision.reason == "predicted glucose below safety threshold"


def test_evaluate_safety_blocks_high_iob() -> None:
    inputs = SafetyInputs(
        recommended_units=1.0,
        predicted_glucose_mgdl=180.0,
        insulin_on_board_u=3.5,
    )

    decision = evaluate_safety(inputs)

    assert decision.status == "blocked"
    assert decision.allowed is False
    assert decision.final_units == 0.0
    assert decision.reason == "insulin on board exceeds safety threshold"
