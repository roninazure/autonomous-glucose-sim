"""Tests for exponential smoothing in the glucose predictor."""
from __future__ import annotations

import pytest

from ags.controller.predictor import predict_glucose, _smoothed_rate_mgdl_per_step
from ags.controller.detector import detect_excursion
from ags.controller.state import ControllerInputs


def _make_inputs(current: float, previous: float, history: list[float] | None = None) -> ControllerInputs:
    return ControllerInputs(
        current_glucose_mgdl=current,
        previous_glucose_mgdl=previous,
        insulin_on_board_u=0.0,
        glucose_history=history or [],
    )


# ── Smoothing function unit tests ────────────────────────────────────────────

def test_smoothed_rate_steady_rise():
    """Constant +5 mg/dL per step → smoothed rate converges to 5.0."""
    history = [100.0, 105.0, 110.0, 115.0, 120.0]
    rate = _smoothed_rate_mgdl_per_step(history)
    assert abs(rate - 5.0) < 0.5


def test_smoothed_rate_single_spike_dampened():
    """One outlier spike followed by flat trend should not dominate the rate."""
    # Steady rise then a big jump then flat
    history = [100.0, 102.0, 104.0, 120.0, 105.0]
    rate = _smoothed_rate_mgdl_per_step(history)
    # If we used only the last delta: 105 - 120 = -15.  Smoothed should be far less extreme.
    assert rate > -15.0, "Smoothing should dampen the single-step spike"


def test_smoothed_rate_steady_fall():
    history = [120.0, 115.0, 110.0, 105.0, 100.0]
    rate = _smoothed_rate_mgdl_per_step(history)
    assert abs(rate - (-5.0)) < 0.5


# ── predict_glucose fallback (short history) ─────────────────────────────────

def test_predict_falls_back_to_linear_with_short_history():
    """With < 3 readings, prediction should equal naive linear extrapolation."""
    inputs = _make_inputs(current=120.0, previous=110.0, history=[110.0, 120.0])
    signal = detect_excursion(inputs)
    pred = predict_glucose(inputs, signal, prediction_horizon_minutes=30, step_minutes=5)
    # Linear: 120 + (10 * 6 steps) = 180
    assert pred.predicted_glucose_mgdl == pytest.approx(180.0)


def test_predict_uses_smoothing_with_sufficient_history():
    """With 5 readings of steady +5 mg/dL/step, smoothed ≈ linear — same result."""
    history = [90.0, 95.0, 100.0, 105.0, 110.0]
    inputs = _make_inputs(current=110.0, previous=105.0, history=history)
    signal = detect_excursion(inputs)
    pred = predict_glucose(inputs, signal, prediction_horizon_minutes=30, step_minutes=5)
    # Steady rise: smoothed rate ≈ 5.0 → predicted = 110 + 5*6 = 140
    assert abs(pred.predicted_glucose_mgdl - 140.0) < 1.0


def test_predict_dampens_noise_spike():
    """A noisy last reading should not dominate the prediction."""
    # Steady +2 trend, then sudden +20 noise spike
    history = [100.0, 102.0, 104.0, 106.0, 126.0]
    inputs = _make_inputs(current=126.0, previous=106.0, history=history)
    signal = detect_excursion(inputs)
    pred_smooth = predict_glucose(inputs, signal, prediction_horizon_minutes=30, step_minutes=5)

    # Compare to naive linear (no history)
    inputs_naive = _make_inputs(current=126.0, previous=106.0, history=[])
    signal_naive = detect_excursion(inputs_naive)
    pred_naive = predict_glucose(inputs_naive, signal_naive, prediction_horizon_minutes=30, step_minutes=5)

    # Smoothed prediction should be lower than naive because the spike is dampened
    assert pred_smooth.predicted_glucose_mgdl < pred_naive.predicted_glucose_mgdl


def test_predict_horizon_stored_correctly():
    inputs = _make_inputs(current=120.0, previous=110.0)
    signal = detect_excursion(inputs)
    pred = predict_glucose(inputs, signal, prediction_horizon_minutes=45, step_minutes=5)
    assert pred.prediction_horizon_minutes == 45


# ── Controller config field tests ────────────────────────────────────────────

def test_min_excursion_delta_suppresses_small_delta():
    from ags.controller.recommender import recommend_correction
    from ags.controller.state import GlucosePrediction

    inputs = ControllerInputs(
        current_glucose_mgdl=115.0,
        previous_glucose_mgdl=113.0,  # delta = 2.0
        insulin_on_board_u=0.0,
        target_glucose_mgdl=110.0,
        correction_factor_mgdl_per_unit=50.0,
        min_excursion_delta_mgdl=5.0,  # threshold above the actual delta
    )
    prediction = GlucosePrediction(predicted_glucose_mgdl=130.0, prediction_horizon_minutes=30)
    rec = recommend_correction(inputs, prediction)
    assert rec.recommended_units == 0.0
    assert "threshold" in rec.reason


def test_min_excursion_delta_allows_large_delta():
    from ags.controller.recommender import recommend_correction
    from ags.controller.state import GlucosePrediction

    inputs = ControllerInputs(
        current_glucose_mgdl=125.0,
        previous_glucose_mgdl=110.0,  # delta = 15.0
        insulin_on_board_u=0.0,
        target_glucose_mgdl=110.0,
        correction_factor_mgdl_per_unit=50.0,
        min_excursion_delta_mgdl=5.0,
    )
    prediction = GlucosePrediction(predicted_glucose_mgdl=160.0, prediction_horizon_minutes=30)
    rec = recommend_correction(inputs, prediction)
    assert rec.recommended_units > 0.0


def test_microbolus_fraction_scales_dose():
    from ags.controller.recommender import recommend_correction
    from ags.controller.state import GlucosePrediction

    base_inputs = ControllerInputs(
        current_glucose_mgdl=140.0,
        previous_glucose_mgdl=130.0,
        insulin_on_board_u=0.0,
        target_glucose_mgdl=110.0,
        correction_factor_mgdl_per_unit=50.0,
        microbolus_fraction=1.0,
    )
    micro_inputs = ControllerInputs(
        current_glucose_mgdl=140.0,
        previous_glucose_mgdl=130.0,
        insulin_on_board_u=0.0,
        target_glucose_mgdl=110.0,
        correction_factor_mgdl_per_unit=50.0,
        microbolus_fraction=0.25,
    )
    prediction = GlucosePrediction(predicted_glucose_mgdl=160.0, prediction_horizon_minutes=30)

    full = recommend_correction(base_inputs, prediction)
    micro = recommend_correction(micro_inputs, prediction)

    assert pytest.approx(micro.recommended_units, rel=1e-4) == full.recommended_units * 0.25
    assert "microbolus" in micro.reason
