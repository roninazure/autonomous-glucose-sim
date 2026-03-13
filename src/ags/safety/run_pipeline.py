from __future__ import annotations

from ags.controller.state import ControllerInputs
from ags.safety.pipeline import run_controller_with_safety
from ags.safety.state import SafetyThresholds


def main() -> None:
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

    print("Controller + Safety demo")
    print("=" * 28)
    print(f"Current glucose: {controller_inputs.current_glucose_mgdl:.2f} mg/dL")
    print(f"Previous glucose: {controller_inputs.previous_glucose_mgdl:.2f} mg/dL")
    print(f"Glucose delta: {signal.glucose_delta_mgdl:.2f} mg/dL")
    print(f"Predicted glucose: {prediction.predicted_glucose_mgdl:.2f} mg/dL")
    print(f"Controller recommendation: {recommendation.recommended_units:.2f} U")
    print(f"Safety allowed: {safety_decision.allowed}")
    print(f"Safety final units: {safety_decision.final_units:.2f} U")
    print(f"Safety reason: {safety_decision.reason}")


if __name__ == "__main__":
    main()
