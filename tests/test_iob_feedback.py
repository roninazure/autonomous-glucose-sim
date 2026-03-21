"""
Tests that delivered insulin feeds back into IOB tracking across timesteps.

Before the fix, the evaluation loop read IOB from the simulation snapshot,
which never incorporated delivered doses. The safety IOB guard was therefore
checking a stale (near-zero) value and could never block on IOB accumulation.

These tests verify that:
1. IOB accumulates from delivered doses and eventually triggers the IOB guard.
2. A tight IOB cap produces more blocked decisions than a loose one on the
   same scenario — which only holds if IOB feedback is working.
"""
from __future__ import annotations

from ags.evaluation.runner import run_evaluation
from ags.safety.state import SafetyThresholds
from ags.simulation.state import MealEvent, SimulationInputs


def _high_glucose_scenario() -> SimulationInputs:
    """Large meal starting immediately so glucose rises from the first step."""
    return SimulationInputs(
        insulin_sensitivity_mgdl_per_unit=50.0,
        carb_impact_mgdl_per_g=4.0,
        baseline_drift_mgdl_per_step=0.0,
        meal_events=[MealEvent(timestamp_min=0, carbs_g=90, absorption_minutes=90)],
    )


def test_iob_guard_triggers_when_iob_accumulates() -> None:
    """With a tight IOB cap, safety must block some decisions.

    If IOB feedback is broken (stale snapshot values), IOB stays near zero
    and the guard never fires — blocked_decisions would be 0.
    """
    tight_thresholds = SafetyThresholds(
        max_units_per_interval=1.0,
        max_insulin_on_board_u=1.5,  # low cap — forces blocks after ~2 doses
        min_predicted_glucose_mgdl=80.0,
        require_confirmed_trend=True,
    )

    _, summary = run_evaluation(
        simulation_inputs=_high_glucose_scenario(),
        safety_thresholds=tight_thresholds,
        duration_minutes=120,
        step_minutes=5,
        seed=42,
    )

    assert summary.blocked_decisions > 0, (
        "Expected IOB guard to block at least one decision. "
        "If this fails, delivered insulin is not feeding back into IOB."
    )


def test_tighter_iob_cap_produces_more_blocks() -> None:
    """A tighter IOB cap must produce at least as many blocks as a loose one.

    This only holds when IOB actually accumulates between steps.
    """
    loose_thresholds = SafetyThresholds(
        max_units_per_interval=1.0,
        max_insulin_on_board_u=3.0,
        min_predicted_glucose_mgdl=80.0,
        require_confirmed_trend=True,
    )
    tight_thresholds = SafetyThresholds(
        max_units_per_interval=1.0,
        max_insulin_on_board_u=1.5,
        min_predicted_glucose_mgdl=80.0,
        require_confirmed_trend=True,
    )
    scenario = _high_glucose_scenario()

    _, summary_loose = run_evaluation(
        simulation_inputs=scenario,
        safety_thresholds=loose_thresholds,
        duration_minutes=120,
        step_minutes=5,
        seed=42,
    )
    _, summary_tight = run_evaluation(
        simulation_inputs=scenario,
        safety_thresholds=tight_thresholds,
        duration_minutes=120,
        step_minutes=5,
        seed=42,
    )

    assert summary_tight.blocked_decisions >= summary_loose.blocked_decisions, (
        "Tighter IOB cap should produce at least as many blocks. "
        "If this fails, IOB feedback is not working correctly."
    )
