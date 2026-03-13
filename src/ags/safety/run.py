from __future__ import annotations

from ags.safety.evaluator import evaluate_safety
from ags.safety.state import SafetyInputs, SafetyThresholds


def main() -> None:
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

    print("Safety demo")
    print("=" * 20)
    print(f"Recommended units: {inputs.recommended_units:.2f} U")
    print(f"Predicted glucose: {inputs.predicted_glucose_mgdl:.2f} mg/dL")
    print(f"Insulin on board: {inputs.insulin_on_board_u:.2f} U")
    print(f"Allowed: {decision.allowed}")
    print(f"Final units: {decision.final_units:.2f} U")
    print(f"Reason: {decision.reason}")


if __name__ == "__main__":
    main()
