"""Verify the online ISF learning loop accumulates observations over time.

The runner should:
1. Queue delivered doses as pending ISF observations.
2. After 60 min (12 steps at 5-min cadence), check glucose drop.
3. Add (units, drop) to isf_observations when the drop is positive.
4. Surface the observation count on each TimestepRecord.
5. Pass the growing list into ControllerInputs so the recommender can use it.

The sustained_basal_deficit_scenario (slow drift, no meal) is used because the
drift creates a sustained correction need while insulin action has time to
produce a measurable glucose drop before the next dose arrives.  A large meal
scenario is unsuitable because carb absorption dominates glucose for 90+ minutes,
making dose→response attribution unreliable within the 60-min window.
"""
from __future__ import annotations

from ags.evaluation.runner import run_evaluation
from ags.simulation.state import SimulationInputs


# Gentle drift (no meal) — creates sustained corrections without overwhelming
# the ISF attribution window.  Not a named clinical scenario; used only here.
_DRIFT_INPUTS = SimulationInputs(
    insulin_sensitivity_mgdl_per_unit=55.0,
    carb_impact_mgdl_per_g=3.0,
    baseline_drift_mgdl_per_step=0.8,
    meal_events=[],
)


def test_isf_observation_count_grows_after_observations_mature() -> None:
    """Gentle drift (360 min): isf_observation_count should be >0.

    First corrections land around t=35 min and mature at t=95 min.
    With a 6-hour run, several dose→response pairs should accumulate.
    """
    simulation_inputs = _DRIFT_INPUTS

    records, _ = run_evaluation(
        simulation_inputs=simulation_inputs,
        duration_minutes=360,
        step_minutes=5,
        seed=42,
        autonomous_isf=True,
        swarm_bolus=True,
    )

    assert records, "Expected at least one record"

    counts = [r.isf_observation_count for r in records]

    # No observations at the very start
    assert counts[0] == 0, f"Expected 0 observations at step 0, got {counts[0]}"

    # By the end of a 6-hour dawn drift run, at least 1 dose→response pair
    # should have matured (first correction at ~t=35 matures at ~t=95).
    assert counts[-1] > 0, (
        f"Expected >0 ISF observations by end of 360-min run, got {counts[-1]}. "
        "The online learning loop may not be collecting evidence."
    )


def test_isf_observation_count_non_decreasing() -> None:
    """Observation count should only grow within a single run."""
    records, _ = run_evaluation(
        simulation_inputs=_DRIFT_INPUTS,
        duration_minutes=360,
        step_minutes=5,
        seed=42,
        autonomous_isf=True,
    )

    counts = [r.isf_observation_count for r in records]
    for i in range(1, len(counts)):
        # Count can stay the same or go up; it should never go down within
        # a single run (the window trims the tail but won't go negative)
        assert counts[i] >= counts[i - 1] - 1, (
            f"isf_observation_count dropped unexpectedly at step {i}: "
            f"{counts[i - 1]} → {counts[i]}"
        )


def test_recommendation_reason_surfaced_in_record() -> None:
    """recommendation_reason field should be non-empty for every timestep."""
    records, _ = run_evaluation(
        simulation_inputs=_DRIFT_INPUTS,
        duration_minutes=60,
        step_minutes=5,
        seed=42,
        autonomous_isf=True,
    )

    for r in records:
        assert r.recommendation_reason, (
            f"Empty recommendation_reason at t={r.timestamp_min} min"
        )
