from ags.safety.evaluator import evaluate_safety
from ags.safety.state import SafetyInputs, SafetyThresholds


def test_evaluate_safety_blocks_when_trend_not_confirmed() -> None:
    inputs = SafetyInputs(
        recommended_units=0.5,
        predicted_glucose_mgdl=150.0,
        insulin_on_board_u=0.5,
        trend_confirmed=False,
    )
    thresholds = SafetyThresholds(
        max_units_per_interval=1.0,
        max_insulin_on_board_u=3.0,
        min_predicted_glucose_mgdl=80.0,
        require_confirmed_trend=True,
    )

    decision = evaluate_safety(inputs, thresholds)

    assert decision.status == "blocked"
    assert decision.allowed is False
    assert decision.final_units == 0.0
    assert decision.reason == "trend not confirmed for dosing"


def test_evaluate_safety_allows_when_trend_requirement_disabled() -> None:
    inputs = SafetyInputs(
        recommended_units=0.5,
        predicted_glucose_mgdl=150.0,
        insulin_on_board_u=0.5,
        trend_confirmed=False,
    )
    thresholds = SafetyThresholds(
        max_units_per_interval=1.0,
        max_insulin_on_board_u=3.0,
        min_predicted_glucose_mgdl=80.0,
        require_confirmed_trend=False,
    )

    decision = evaluate_safety(inputs, thresholds)

    assert decision.status == "allowed"
    assert decision.allowed is True
    assert decision.final_units == 0.5
    assert decision.reason == "recommendation allowed"
