from ags.safety.evaluator import evaluate_safety
from ags.safety.state import SafetyInputs


def test_evaluate_safety_blocks_zero_recommendation() -> None:
    inputs = SafetyInputs(
        recommended_units=0.0,
        predicted_glucose_mgdl=150.0,
        insulin_on_board_u=0.5,
    )

    decision = evaluate_safety(inputs)

    assert decision.allowed is False
    assert decision.final_units == 0.0
    assert decision.reason == "no positive recommendation to deliver"
