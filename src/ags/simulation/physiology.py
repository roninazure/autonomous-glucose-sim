from __future__ import annotations

from ags.simulation.insulin import (
    advance_insulin_compartments,
    insulin_glucose_effect_mgdl,
    insulin_on_board,
)
from ags.simulation.state import MealEvent, SimulationInputs, SimulationSnapshot


def meal_carbs_active_at_step(
    meal: MealEvent,
    current_time_min: int,
    step_minutes: int = 5,
) -> float:
    elapsed = current_time_min - meal.timestamp_min
    if elapsed < 0 or elapsed >= meal.absorption_minutes:
        return 0.0

    steps_total = max(1, meal.absorption_minutes // step_minutes)
    return meal.carbs_g / steps_total


def compute_active_meal_carbs(
    current_time_min: int,
    inputs: SimulationInputs,
    step_minutes: int = 5,
) -> float:
    return sum(
        meal_carbs_active_at_step(meal, current_time_min, step_minutes)
        for meal in inputs.meal_events
    )


def advance_physiology(
    snapshot: SimulationSnapshot,
    inputs: SimulationInputs,
    step_minutes: int = 5,
) -> SimulationSnapshot:
    next_time = snapshot.timestamp_min + step_minutes

    active_meal_carbs = compute_active_meal_carbs(
        current_time_min=next_time,
        inputs=inputs,
        step_minutes=step_minutes,
    )

    meal_glucose_effect = active_meal_carbs * inputs.carb_impact_mgdl_per_g

    # Glucose effect comes from the active (interstitial) pool, x2.
    insulin_effect = insulin_glucose_effect_mgdl(
        x2=snapshot.insulin_compartment2_u,
        step_minutes=step_minutes,
        peak_minutes=inputs.insulin_peak_minutes,
        insulin_sensitivity_mgdl_per_unit=inputs.insulin_sensitivity_mgdl_per_unit,
    )

    glucose_delta = (
        meal_glucose_effect
        - insulin_effect
        + inputs.baseline_drift_mgdl_per_step
    )

    next_true_glucose = max(40.0, snapshot.true_glucose_mgdl + glucose_delta)

    # Advance the 2-compartment PK/PD state. No new dose is injected here;
    # the engine adds delivered insulin via the snapshot before calling this.
    x1_next, x2_next = advance_insulin_compartments(
        x1=snapshot.insulin_compartment1_u,
        x2=snapshot.insulin_compartment2_u,
        dose_u=0.0,  # doses are injected externally via delivered_insulin_u
        step_minutes=step_minutes,
        peak_minutes=inputs.insulin_peak_minutes,
    )

    return SimulationSnapshot(
        timestamp_min=next_time,
        true_glucose_mgdl=next_true_glucose,
        cgm_glucose_mgdl=next_true_glucose,
        insulin_on_board_u=insulin_on_board(x1_next, x2_next),
        insulin_compartment1_u=x1_next,
        insulin_compartment2_u=x2_next,
        active_meal_carbs_g=active_meal_carbs,
        delivered_insulin_u=snapshot.delivered_insulin_u,
        glucose_delta_mgdl=glucose_delta,
    )
