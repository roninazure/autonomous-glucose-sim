from __future__ import annotations

from ags.simulation.state import MealEvent, SimulationInputs


def baseline_meal_scenario() -> SimulationInputs:
    return SimulationInputs(
        insulin_sensitivity_mgdl_per_unit=50.0,
        carb_impact_mgdl_per_g=3.0,
        baseline_drift_mgdl_per_step=0.0,
        meal_events=[
            MealEvent(timestamp_min=30, carbs_g=45.0, absorption_minutes=120),
        ],
    )
