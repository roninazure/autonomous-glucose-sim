from ags.controller.pipeline import run_controller
from ags.controller.state import ControllerInputs


def test_run_controller_returns_expected_recommendation_for_rising_glucose() -> None:
    # SWARM mode: G=150 (above floor 130), rising at 2 mg/dL/min → SWARM fires
    inputs = ControllerInputs(
        current_glucose_mgdl=150.0,
        previous_glucose_mgdl=140.0,
        insulin_on_board_u=0.0,
        swarm_bolus=True,
    )

    signal, prediction, recommendation, _classification = run_controller(inputs)

    assert signal.glucose_delta_mgdl == 10.0
    assert signal.rising is True
    assert signal.falling is False
    assert prediction.predicted_glucose_mgdl == 210.0
    assert prediction.prediction_horizon_minutes == 30
    assert recommendation.recommended_units == 1.0  # SWARM: capped at max_pulse=1.0
    assert "SWARM micro-bolus" in recommendation.reason
