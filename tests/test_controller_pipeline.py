from ags.controller.pipeline import run_controller
from ags.controller.state import ControllerInputs


def test_run_controller_returns_expected_recommendation_for_rising_glucose() -> None:
    inputs = ControllerInputs(
        current_glucose_mgdl=150.0,
        previous_glucose_mgdl=140.0,
        insulin_on_board_u=0.0,
        target_glucose_mgdl=110.0,
        correction_factor_mgdl_per_unit=50.0,
    )

    signal, prediction, recommendation, _classification = run_controller(inputs)

    assert signal.glucose_delta_mgdl == 10.0
    assert signal.rising is True
    assert signal.falling is False
    assert prediction.predicted_glucose_mgdl == 210.0
    assert prediction.prediction_horizon_minutes == 30
    assert recommendation.recommended_units == 2.0
    assert recommendation.reason == "predicted glucose above target"
