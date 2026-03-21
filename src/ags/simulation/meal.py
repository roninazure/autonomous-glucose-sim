from __future__ import annotations

import math

from ags.simulation.state import MealEvent


def meal_appearance_rate_g(
    meal: MealEvent,
    elapsed_min: float,
    step_minutes: float,
) -> float:
    """Carbs (g) appearing in the bloodstream this timestep via gut absorption.

    Uses a gamma(2, τ) absorption curve — the same distribution used for
    the insulin PK/PD model — which produces a physiologically realistic
    rise-then-fall shape:

        appearance_rate(t) = (t / τ²) · exp(−t / τ)

    where τ = absorption_minutes / 5, chosen so that 95% of carbs are
    absorbed by absorption_minutes.

    Peak carb appearance occurs at t = τ:
        τ = absorption_minutes / 5
        e.g. absorption_minutes=120 → τ=24 min  (mixed meal)
             absorption_minutes= 60 → τ=12 min  (high-GI, e.g. juice)
             absorption_minutes=180 → τ=36 min  (low-GI, e.g. lentils)

    The total carbs appearing over all time equals meal.carbs_g exactly
    (mass conserving, by the normalisation of the gamma PDF).

    Args:
        meal: The meal event providing carbs_g and absorption_minutes.
        elapsed_min: Minutes since the meal started (must be > 0 to absorb).
        step_minutes: Duration of the current timestep (minutes).

    Returns:
        Grams of carbohydrate appearing this step.
    """
    if elapsed_min <= 0.0:
        return 0.0

    tau = meal.absorption_minutes / 5.0
    rate_per_min = (elapsed_min / tau**2) * math.exp(-elapsed_min / tau)
    return meal.carbs_g * rate_per_min * step_minutes


def compute_active_meal_carbs_g(
    current_time_min: int,
    meal_events: list[MealEvent],
    step_minutes: float,
) -> float:
    """Total carbs appearing this step from all active meal events."""
    return sum(
        meal_appearance_rate_g(
            meal=meal,
            elapsed_min=current_time_min - meal.timestamp_min,
            step_minutes=step_minutes,
        )
        for meal in meal_events
    )
