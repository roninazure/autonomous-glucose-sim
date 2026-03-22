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


def dawn_phenomenon_scenario() -> SimulationInputs:
    """Gradual glucose rise from 3–7 AM driven by cortisol/growth hormone.

    No meal event. Positive baseline drift simulates the liver dumping glucose.
    The controller must detect the slow rise and intervene without a meal bolus
    trigger — a common failure mode in rule-based systems.
    """
    return SimulationInputs(
        insulin_sensitivity_mgdl_per_unit=55.0,
        carb_impact_mgdl_per_g=3.0,
        baseline_drift_mgdl_per_step=0.8,  # ~10 mg/dL rise per hour
        meal_events=[],
    )


def sustained_basal_deficit_scenario() -> SimulationInputs:
    """Slow linear glucose rise from chronically insufficient background insulin.

    Unlike the dawn_phenomenon_scenario (which targets the overnight cortisol
    window), this scenario models a patient whose basal rate is simply too low
    throughout the day — a common programming error after a pump site change or
    a weight gain without dose adjustment.

    Drift rate: 1.5 mg/dL per 5-min step = 0.30 mg/dL/min ≈ 18 mg/dL/hour.
    This sits comfortably inside the basal drift detector's rate band
    (0.08–0.70 mg/dL/min) and produces a highly linear curve (R² → 1.0),
    making it the canonical test case for the BASAL_DRIFT detection path.

    Expected controller behaviour:
      - No meal detected (no MealEvent)
      - GlucoseCause.BASAL_DRIFT once 30 min of history has accumulated
      - Small 25%-fraction micro-boluses accumulating to counteract the drift
      - Glucose stabilises well below what it would reach with no controller
    """
    return SimulationInputs(
        insulin_sensitivity_mgdl_per_unit=55.0,
        carb_impact_mgdl_per_g=3.0,
        baseline_drift_mgdl_per_step=1.5,   # 0.30 mg/dL/min steady rise
        meal_events=[],
    )


def exercise_hypoglycemia_scenario() -> SimulationInputs:
    """Aerobic exercise driving glucose down while residual IOB is present.

    Negative drift models elevated glucose uptake by working muscle.
    ISF is heightened (insulin more effective during exercise).
    The safety layer's hypo guard must prevent the controller from
    compounding the drop with additional doses.
    """
    return SimulationInputs(
        insulin_sensitivity_mgdl_per_unit=80.0,  # exercise amplifies insulin sensitivity
        carb_impact_mgdl_per_g=3.0,
        baseline_drift_mgdl_per_step=-1.2,  # ~14 mg/dL drop per hour
        meal_events=[],
    )


def missed_bolus_scenario() -> SimulationInputs:
    """Large meal eaten with no pre-meal bolus.

    The autonomous system encounters a steep post-prandial spike and must
    decide how aggressively to correct retroactively. Tests whether the
    controller recovers TIR after a delayed start, and whether the safety
    layer prevents over-correction stacking.
    """
    return SimulationInputs(
        insulin_sensitivity_mgdl_per_unit=50.0,
        carb_impact_mgdl_per_g=3.5,  # slightly aggressive carb impact
        baseline_drift_mgdl_per_step=0.0,
        meal_events=[
            MealEvent(timestamp_min=10, carbs_g=75.0, absorption_minutes=120),
        ],
    )


def late_correction_scenario() -> SimulationInputs:
    """Meal bolus delivered 45 minutes after eating starts.

    Models the common real-world mistake of forgetting to bolus at meal start.
    By t=45 glucose is already rising steeply; the delayed correction creates
    an insulin-glucose timing mismatch that can cause post-correction hypoglycemia.
    """
    return SimulationInputs(
        insulin_sensitivity_mgdl_per_unit=50.0,
        carb_impact_mgdl_per_g=3.0,
        baseline_drift_mgdl_per_step=0.0,
        meal_events=[
            MealEvent(timestamp_min=5, carbs_g=60.0, absorption_minutes=100),
            # Second small snack compounds the challenge
            MealEvent(timestamp_min=90, carbs_g=20.0, absorption_minutes=60),
        ],
    )
