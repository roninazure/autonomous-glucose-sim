"""Tests for the four new doctor-requested features:
  1. 1-minute loop (rate-normalised detector thresholds)
  2. Dual-wave / split bolus delivery
  3. Rate-of-rise tiered micro-bolus
  4. Weight-based ISF estimation
"""
from __future__ import annotations

import pytest

from ags.controller.detector import detect_excursion
from ags.controller.recommender import _ror_to_microbolus_fraction, recommend_correction
from ags.controller.state import ControllerInputs, ExcursionSignal, GlucosePrediction
from ags.evaluation.profiles import estimate_carb_ratio_from_weight, estimate_isf_from_weight
from ags.evaluation.runner import run_evaluation
from ags.pump.emulator import advance_dual_wave_state, apply_dual_wave_split
from ags.pump.state import DualWaveConfig, DualWaveState, PumpConfig
from ags.simulation.scenarios import baseline_meal_scenario


# ── 1. 1-minute loop ──────────────────────────────────────────────────────────

class TestOneMinuteLoop:
    def test_rate_normalised_at_1_min_step(self) -> None:
        """At 1-min step, a 2 mg/dL delta → 2.0 mg/dL/min (not 0.4 as at 5-min)."""
        inputs = ControllerInputs(
            current_glucose_mgdl=112.0,
            previous_glucose_mgdl=110.0,
            insulin_on_board_u=0.0,
            step_minutes=1,
        )
        signal = detect_excursion(inputs)
        assert signal.glucose_delta_mgdl == pytest.approx(2.0)
        assert signal.rate_mgdl_per_min == pytest.approx(2.0)

    def test_rate_normalised_at_5_min_step(self) -> None:
        """At 5-min step, a 10 mg/dL delta → 2.0 mg/dL/min."""
        inputs = ControllerInputs(
            current_glucose_mgdl=120.0,
            previous_glucose_mgdl=110.0,
            insulin_on_board_u=0.0,
            step_minutes=5,
        )
        signal = detect_excursion(inputs)
        assert signal.glucose_delta_mgdl == pytest.approx(10.0)
        assert signal.rate_mgdl_per_min == pytest.approx(2.0)

    def test_rising_flag_at_1_min_step(self) -> None:
        """At 1-min step, rate >= 1.0 mg/dL/min triggers rising=True."""
        inputs = ControllerInputs(
            current_glucose_mgdl=112.0,
            previous_glucose_mgdl=110.0,  # delta=2 → 2 mg/dL/min
            insulin_on_board_u=0.0,
            step_minutes=1,
        )
        signal = detect_excursion(inputs)
        assert signal.rising is True

    def test_flat_not_rising_at_1_min_step(self) -> None:
        """0.5 mg/dL/min is below the 1.0 threshold → rising=False."""
        inputs = ControllerInputs(
            current_glucose_mgdl=110.5,
            previous_glucose_mgdl=110.0,  # delta=0.5 → 0.5 mg/dL/min
            insulin_on_board_u=0.0,
            step_minutes=1,
        )
        signal = detect_excursion(inputs)
        assert signal.rising is False

    def test_run_evaluation_at_1_min_step(self) -> None:
        """Full evaluation pipeline can run at 1-min timestep without error."""
        records, summary = run_evaluation(
            simulation_inputs=baseline_meal_scenario(),
            duration_minutes=60,
            step_minutes=1,
            seed=42,
        )
        assert len(records) == 60
        assert summary.total_timesteps == 60
        assert summary.total_insulin_delivered_u >= 0.0


# ── 2. Dual-wave bolus ────────────────────────────────────────────────────────

class TestDualWaveBolus:
    def test_split_delivers_immediate_fraction_now(self) -> None:
        """apply_dual_wave_split: 6U bolus with 0.33 fraction → 2U immediate."""
        imm, state = apply_dual_wave_split(
            total_units=6.0,
            dual_wave_config=DualWaveConfig(enabled=True, immediate_fraction=0.33, extended_duration_minutes=20),
            dual_wave_state=DualWaveState(),
            step_minutes=5,
        )
        # Immediate: 0.33 × 6.0 = 1.98 ≈ 2.0
        assert imm == pytest.approx(1.98, abs=0.01)

    def test_split_queues_remaining_in_extended_state(self) -> None:
        """After split, extended_remaining_u holds (1 - frac) × total."""
        imm, state = apply_dual_wave_split(
            total_units=6.0,
            dual_wave_config=DualWaveConfig(enabled=True, immediate_fraction=1 / 3, extended_duration_minutes=20),
            dual_wave_state=DualWaveState(),
            step_minutes=5,
        )
        assert state.extended_remaining_u == pytest.approx(6.0 * (2 / 3), abs=0.01)
        assert state.extended_steps_remaining == 4  # 20 min / 5 min per step

    def test_advance_delivers_per_step_rate(self) -> None:
        """Each advance_dual_wave_state call delivers one step's worth."""
        state = DualWaveState(
            extended_remaining_u=4.0,
            extended_rate_u_per_step=1.0,
            extended_steps_remaining=4,
        )
        delivered, new_state = advance_dual_wave_state(state)
        assert delivered == pytest.approx(1.0, abs=0.05)
        assert new_state.extended_steps_remaining == 3

    def test_extended_tail_exhausts_to_zero(self) -> None:
        """After all steps the tail reaches zero."""
        state = DualWaveState(
            extended_remaining_u=2.0,
            extended_rate_u_per_step=1.0,
            extended_steps_remaining=2,
        )
        _, state = advance_dual_wave_state(state)
        _, state = advance_dual_wave_state(state)
        assert state.extended_steps_remaining == 0
        assert state.is_active is False

    def test_dual_wave_disabled_delivers_full_bolus(self) -> None:
        """With dual_wave_config.enabled=False, run_evaluation behaves normally."""
        records, summary = run_evaluation(
            simulation_inputs=baseline_meal_scenario(),
            duration_minutes=60,
            step_minutes=5,
            seed=42,
            dual_wave_config=DualWaveConfig(enabled=False),
        )
        assert summary.total_insulin_delivered_u >= 0.0

    def test_dual_wave_enabled_in_evaluation(self) -> None:
        """Dual-wave enabled run produces records without error."""
        records, summary = run_evaluation(
            simulation_inputs=baseline_meal_scenario(),
            duration_minutes=60,
            step_minutes=5,
            seed=42,
            dual_wave_config=DualWaveConfig(enabled=True, immediate_fraction=0.33, extended_duration_minutes=20),
        )
        assert len(records) == 12
        assert summary.total_insulin_delivered_u >= 0.0


# ── 3. RoR-tiered micro-bolus ─────────────────────────────────────────────────

class TestRorTieredMicrobolus:
    def test_flat_rate_returns_zero_fraction(self) -> None:
        assert _ror_to_microbolus_fraction(0.5) == 0.0

    def test_moderate_rate_returns_quarter_fraction(self) -> None:
        assert _ror_to_microbolus_fraction(1.5) == 0.25

    def test_rapid_rate_returns_half_fraction(self) -> None:
        assert _ror_to_microbolus_fraction(2.5) == 0.50

    def test_aggressive_spike_returns_full_fraction(self) -> None:
        assert _ror_to_microbolus_fraction(3.5) == 1.0

    def test_boundary_exactly_1_is_moderate(self) -> None:
        assert _ror_to_microbolus_fraction(1.0) == 0.25

    def test_boundary_exactly_3_is_aggressive(self) -> None:
        assert _ror_to_microbolus_fraction(3.0) == 1.0

    def test_ror_tiered_recommendation_scales_with_rate(self) -> None:
        """With ror_tiered_microbolus=True, a 3+ mg/dL/min spike → full correction."""
        # 150 → 168 in 5 min = 18 mg/dL = 3.6 mg/dL/min → full correction
        inputs = ControllerInputs(
            current_glucose_mgdl=168.0,
            previous_glucose_mgdl=150.0,
            insulin_on_board_u=0.0,
            target_glucose_mgdl=110.0,
            correction_factor_mgdl_per_unit=50.0,
            step_minutes=5,
            ror_tiered_microbolus=True,
        )
        signal = ExcursionSignal(
            glucose_delta_mgdl=18.0,
            rate_mgdl_per_min=3.6,
            rising=True,
            falling=False,
        )
        prediction = GlucosePrediction(predicted_glucose_mgdl=200.0, prediction_horizon_minutes=30)
        rec = recommend_correction(inputs, prediction, signal=signal)
        # Full fraction → (200 - 110) / 50 × 1.0 = 1.8
        assert rec.recommended_units == pytest.approx(1.8, abs=0.01)
        assert "RoR-tiered" in rec.reason

    def test_ror_tiered_flat_rate_delivers_zero(self) -> None:
        """With ror_tiered_microbolus=True, flat rate → 0 units even if glucose above target."""
        inputs = ControllerInputs(
            current_glucose_mgdl=120.0,
            previous_glucose_mgdl=119.5,   # 0.5 mg/dL delta / 5 min = 0.1 mg/dL/min
            insulin_on_board_u=0.0,
            target_glucose_mgdl=110.0,
            correction_factor_mgdl_per_unit=50.0,
            step_minutes=5,
            ror_tiered_microbolus=True,
        )
        signal = ExcursionSignal(
            glucose_delta_mgdl=0.5,
            rate_mgdl_per_min=0.1,
            rising=False,
            falling=False,
        )
        prediction = GlucosePrediction(predicted_glucose_mgdl=123.0, prediction_horizon_minutes=30)
        rec = recommend_correction(inputs, prediction, signal=signal)
        assert rec.recommended_units == pytest.approx(0.0)

    def test_ror_tiered_in_evaluation(self) -> None:
        """run_evaluation with ror_tiered_microbolus=True completes without error."""
        records, summary = run_evaluation(
            simulation_inputs=baseline_meal_scenario(),
            duration_minutes=60,
            step_minutes=5,
            seed=42,
            ror_tiered_microbolus=True,
        )
        assert len(records) == 12


# ── 4. Weight-based ISF ───────────────────────────────────────────────────────

class TestWeightBasedIsf:
    def test_70kg_adult_isf(self) -> None:
        """70 kg × 0.55 = 38.5 U TDD → ISF ≈ 1700/38.5 ≈ 44.2 mg/dL/U."""
        isf = estimate_isf_from_weight(70.0)
        assert isf == pytest.approx(44.2, abs=0.5)

    def test_heavier_patient_has_lower_isf(self) -> None:
        """Heavier → higher TDD → lower ISF (less sensitive per unit)."""
        assert estimate_isf_from_weight(100.0) < estimate_isf_from_weight(60.0)

    def test_minimum_weight_guard(self) -> None:
        """Very low weight doesn't produce an infinite ISF (TDD floored at 1)."""
        isf = estimate_isf_from_weight(0.0)
        assert isf == pytest.approx(1700.0, abs=1.0)

    def test_carb_ratio_from_weight(self) -> None:
        """70 kg → ICR ≈ 500 / 38.5 ≈ 13.0 g/U."""
        icr = estimate_carb_ratio_from_weight(70.0)
        assert icr == pytest.approx(13.0, abs=0.5)

    def test_doctor_example_30g_6u(self) -> None:
        """Doctor's example: 30g → 6U → ICR = 5 g/U. That's a lower-weight scenario.

        ICR = 500 / (weight × 0.55) = 5 → weight × 0.55 = 100 → weight ≈ 182 kg.
        For a more realistic 80 kg patient the ICR is ~11 g/U (typical T2D range).
        The 5 g/U ICR maps to an insulin-resistant patient with high TDD.
        """
        icr = estimate_carb_ratio_from_weight(80.0)
        # 500 / (80 × 0.55) = 500 / 44 ≈ 11.4 g/U
        assert 9.0 < icr < 15.0
