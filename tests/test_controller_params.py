"""
Tests that target_glucose_mgdl and correction_factor_mgdl_per_unit passed to
run_evaluation() flow through to the controller.
"""
from __future__ import annotations

from ags.evaluation.runner import run_evaluation
from ags.simulation.scenarios import baseline_meal_scenario


def test_higher_target_delivers_less_insulin() -> None:
    """Raising the target glucose should make the controller less aggressive.

    With target=180 the controller sees current glucose as closer to (or below)
    target and recommends smaller corrections, delivering less total insulin
    than with target=110 on an identical scenario.
    """
    scenario = baseline_meal_scenario()

    _, summary_tight = run_evaluation(
        simulation_inputs=scenario,
        duration_minutes=180,
        step_minutes=5,
        seed=42,
        target_glucose_mgdl=110.0,
    )
    _, summary_loose = run_evaluation(
        simulation_inputs=scenario,
        duration_minutes=180,
        step_minutes=5,
        seed=42,
        target_glucose_mgdl=180.0,
    )

    assert summary_tight.total_insulin_delivered_u > summary_loose.total_insulin_delivered_u, (
        "Lower target should result in more total insulin delivered. "
        "If this fails, target_glucose_mgdl is not reaching the controller."
    )


def test_weaker_correction_factor_recommends_more_insulin() -> None:
    """A smaller correction factor means each unit corrects less glucose,
    so the controller must recommend more units for the same excursion.

    We compare total_recommended_insulin_u (raw controller output) rather
    than total_insulin_delivered_u to avoid the safety IOB cap masking the
    difference when both scenarios hit the cap equally.
    """
    scenario = baseline_meal_scenario()

    _, summary_weak = run_evaluation(
        simulation_inputs=scenario,
        duration_minutes=180,
        step_minutes=5,
        seed=42,
        correction_factor_mgdl_per_unit=30.0,  # 1U corrects only 30 mg/dL → more units needed
    )
    _, summary_strong = run_evaluation(
        simulation_inputs=scenario,
        duration_minutes=180,
        step_minutes=5,
        seed=42,
        correction_factor_mgdl_per_unit=80.0,  # 1U corrects 80 mg/dL → fewer units needed
    )

    assert summary_weak.total_recommended_insulin_u > summary_strong.total_recommended_insulin_u, (
        "Weaker correction factor should produce higher total recommended insulin. "
        "If this fails, correction_factor_mgdl_per_unit is not reaching the controller."
    )
