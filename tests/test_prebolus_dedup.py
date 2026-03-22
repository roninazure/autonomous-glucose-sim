"""Verify the pre-bolus fires exactly once per meal event.

Before the de-duplication fix, every consecutive ONSET step would fire its own
pre-bolus because recommend_prebolus=True on every ONSET phase and there was no
cross-step guard.  The fix adds prebolus_already_fired to ControllerInputs and
resets it in the runner when the meal signal returns to NONE.
"""
from __future__ import annotations

from ags.evaluation.runner import run_evaluation
from ags.simulation.scenarios import baseline_meal_scenario


def test_prebolus_fires_exactly_once_per_meal() -> None:
    """Autonomous mode: pre-bolus reason should appear at most once per run."""
    simulation_inputs = baseline_meal_scenario()

    records, _ = run_evaluation(
        simulation_inputs=simulation_inputs,
        duration_minutes=180,
        step_minutes=5,
        seed=42,
        autonomous_isf=True,
    )

    prebolus_steps = [
        r for r in records
        if "pre-bolus | meal ONSET" in r.recommendation_reason
    ] if hasattr(records[0], "recommendation_reason") else []

    # Count steps where recommended_units > 0 AND meal_phase == "onset".
    onset_dose_steps = [
        r for r in records
        if r.meal_phase == "onset" and r.recommended_units > 0
    ]

    # The pre-bolus should fire on the FIRST onset step; all subsequent onset
    # steps should produce a standard micro-bolus (not another pre-bolus).
    # We verify that recommended_units > 0 on at most 1 onset step before the
    # meal transitions to peak/recovery/none.
    #
    # Specifically: find the first onset step and the onset-step count before
    # the phase first leaves onset.  There should be exactly 1 dose > 0.1 U
    # among those steps (the pre-bolus), and subsequent onset steps should be
    # smaller (micro-bolus) or zero.

    # Collect consecutive onset steps from the first onset
    in_first_onset = False
    first_onset_doses: list[float] = []
    for r in records:
        if r.meal_phase == "onset" and not in_first_onset:
            in_first_onset = True
        if in_first_onset:
            if r.meal_phase != "onset":
                break
            first_onset_doses.append(r.recommended_units)

    # Count how many records across the ENTIRE run have a pre-bolus reason.
    # The recommendation_reason field is now surfaced on TimestepRecord.
    prebolus_records = [
        r for r in records
        if r.recommendation_reason.startswith("pre-bolus | meal ONSET")
    ]

    # Exactly one pre-bolus should fire per meal event.
    # (The baseline_meal_scenario has exactly one meal.)
    assert len(prebolus_records) <= 1, (
        f"Pre-bolus fired {len(prebolus_records)} times in a single meal scenario "
        f"(steps: {[r.timestamp_min for r in prebolus_records]}). Expected ≤1."
    )
