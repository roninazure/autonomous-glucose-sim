from __future__ import annotations

from ags.controller.pipeline import run_controller
from ags.controller.state import ControllerInputs


def main() -> None:
    inputs = ControllerInputs(
        current_glucose_mgdl=150.0,
        previous_glucose_mgdl=140.0,
        insulin_on_board_u=0.0,
        target_glucose_mgdl=110.0,
        correction_factor_mgdl_per_unit=50.0,
    )

    signal, prediction, recommendation = run_controller(inputs)

    print("Controller demo")
    print("=" * 20)
    print(f"Current glucose: {inputs.current_glucose_mgdl:.2f} mg/dL")
    print(f"Previous glucose: {inputs.previous_glucose_mgdl:.2f} mg/dL")
    print(f"Glucose delta: {signal.glucose_delta_mgdl:.2f} mg/dL")
    print(f"Rising: {signal.rising}")
    print(f"Falling: {signal.falling}")
    print(f"Predicted glucose ({prediction.prediction_horizon_minutes} min): {prediction.predicted_glucose_mgdl:.2f} mg/dL")
    print(f"Recommended correction: {recommendation.recommended_units:.2f} U")
    print(f"Reason: {recommendation.reason}")


if __name__ == "__main__":
    main()
