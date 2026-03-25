from __future__ import annotations

from ags.simulation.insulin import (
    advance_insulin_compartments,
    insulin_glucose_effect_mgdl,
    insulin_on_board,
)
from ags.simulation.meal import compute_active_meal_carbs_g
from ags.simulation.state import SimulationInputs, SimulationSnapshot


def advance_physiology(
    snapshot: SimulationSnapshot,
    inputs: SimulationInputs,
    step_minutes: int = 5,
    delivered_dose_u: float = 0.0,
) -> SimulationSnapshot:
    """Advance physiology by one step.

    Args:
        snapshot: Current physiological state.
        inputs: Patient/scenario parameters.
        step_minutes: CGM cadence in minutes.
        delivered_dose_u: Insulin delivered by the pump THIS step.
            In open-loop simulation this is always 0 (pre-computed trajectory).
            In closed-loop operation the controller's delivery is passed here
            so that insulin actually enters the PK/PD model and changes the
            glucose trajectory — the core of the artificial pancreas loop.
    """
    next_time = snapshot.timestamp_min + step_minutes

    peak_minutes = inputs.effective_peak_minutes()

    # Carbs appearing in blood this step via gamma(2, τ) gut absorption.
    active_meal_carbs = compute_active_meal_carbs_g(
        current_time_min=next_time,
        meal_events=inputs.meal_events,
        step_minutes=step_minutes,
    )

    meal_glucose_effect = active_meal_carbs * inputs.carb_impact_mgdl_per_g

    # Glucose effect comes from the active (interstitial) insulin pool, x2.
    insulin_effect = insulin_glucose_effect_mgdl(
        x2=snapshot.insulin_compartment2_u,
        step_minutes=step_minutes,
        peak_minutes=peak_minutes,
        insulin_sensitivity_mgdl_per_unit=inputs.insulin_sensitivity_mgdl_per_unit,
    )

    glucose_delta = (
        meal_glucose_effect
        - insulin_effect
        + inputs.baseline_drift_mgdl_per_step
    )

    next_true_glucose = max(40.0, snapshot.true_glucose_mgdl + glucose_delta)

    x1_next, x2_next = advance_insulin_compartments(
        x1=snapshot.insulin_compartment1_u,
        x2=snapshot.insulin_compartment2_u,
        dose_u=delivered_dose_u,
        step_minutes=step_minutes,
        peak_minutes=peak_minutes,
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
