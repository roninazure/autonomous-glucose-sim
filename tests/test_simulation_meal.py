"""
Tests for the gamma(2, τ) gut absorption model.

Key physiological properties verified:
1. Zero appearance before meal starts.
2. Mass conservation — total carbs appearing == meal.carbs_g.
3. Peak appearance near τ = absorption_minutes / 5.
4. Appearance decreases monotonically after peak.
5. Multiple concurrent meals are summed correctly.
"""
from __future__ import annotations

import math

import pytest

from ags.simulation.meal import compute_active_meal_carbs_g, meal_appearance_rate_g
from ags.simulation.state import MealEvent


# ---------------------------------------------------------------------------
# Zero before meal starts
# ---------------------------------------------------------------------------


def test_no_appearance_before_meal_start() -> None:
    meal = MealEvent(timestamp_min=30, carbs_g=45.0, absorption_minutes=120)
    assert meal_appearance_rate_g(meal, elapsed_min=0.0, step_minutes=5) == 0.0
    assert meal_appearance_rate_g(meal, elapsed_min=-5.0, step_minutes=5) == 0.0


# ---------------------------------------------------------------------------
# Mass conservation: total carbs == carbs_g
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("absorption_minutes,carbs_g", [
    (60,  30.0),   # high-GI
    (120, 45.0),   # mixed meal
    (180, 60.0),   # low-GI
])
def test_total_carbs_equal_meal_carbs(absorption_minutes: int, carbs_g: float) -> None:
    """Summing appearance over 12 hours must recover carbs_g within 2%."""
    meal = MealEvent(timestamp_min=0, carbs_g=carbs_g, absorption_minutes=absorption_minutes)
    step = 5
    total = sum(
        meal_appearance_rate_g(meal, elapsed_min=t, step_minutes=step)
        for t in range(step, 12 * 60 + step, step)
    )
    assert math.isclose(total, carbs_g, rel_tol=0.02), (
        f"Expected ≈ {carbs_g} g, got {total:.3f} g "
        f"(absorption_minutes={absorption_minutes})"
    )


# ---------------------------------------------------------------------------
# Peak timing: appearance peaks near τ = absorption_minutes / 5
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("absorption_minutes", [60, 120, 180])
def test_peak_appearance_near_tau(absorption_minutes: int) -> None:
    """Peak carb appearance should occur within ±10 min of τ."""
    tau = absorption_minutes / 5
    meal = MealEvent(timestamp_min=0, carbs_g=45.0, absorption_minutes=absorption_minutes)
    step = 5

    peak_rate = 0.0
    peak_time = 0
    for t in range(step, 6 * 60 + step, step):
        rate = meal_appearance_rate_g(meal, elapsed_min=t, step_minutes=step)
        if rate > peak_rate:
            peak_rate = rate
            peak_time = t

    assert abs(peak_time - tau) <= 10, (
        f"Expected peak near τ={tau:.0f} min, found near {peak_time} min "
        f"(absorption_minutes={absorption_minutes})"
    )


# ---------------------------------------------------------------------------
# Monotone decrease after peak
# ---------------------------------------------------------------------------


def test_appearance_decreases_after_peak() -> None:
    """After the gamma peak, carb appearance rate must not increase."""
    meal = MealEvent(timestamp_min=0, carbs_g=45.0, absorption_minutes=120)
    tau = 120 / 5  # = 24 min
    step = 5

    # Evaluate from just past the peak onward.
    start = int(tau) + step
    rates = [
        meal_appearance_rate_g(meal, elapsed_min=t, step_minutes=step)
        for t in range(start, 6 * 60, step)
    ]

    for i in range(len(rates) - 1):
        assert rates[i] >= rates[i + 1] - 1e-9, (
            f"Appearance rate increased at step {i}: {rates[i]:.4f} → {rates[i+1]:.4f}"
        )


# ---------------------------------------------------------------------------
# Multiple concurrent meals are summed
# ---------------------------------------------------------------------------


def test_multiple_meals_are_additive() -> None:
    """Two identical meals at the same time should double the appearance."""
    meal = MealEvent(timestamp_min=0, carbs_g=45.0, absorption_minutes=120)
    step = 5

    single = compute_active_meal_carbs_g(
        current_time_min=30,
        meal_events=[meal],
        step_minutes=step,
    )
    double = compute_active_meal_carbs_g(
        current_time_min=30,
        meal_events=[meal, meal],
        step_minutes=step,
    )

    assert math.isclose(double, 2 * single, rel_tol=1e-9)


def test_staggered_meals_do_not_interact() -> None:
    """A meal that hasn't started contributes zero to current appearance."""
    active = MealEvent(timestamp_min=0, carbs_g=45.0, absorption_minutes=120)
    future = MealEvent(timestamp_min=60, carbs_g=45.0, absorption_minutes=120)

    at_t30_single = compute_active_meal_carbs_g(
        current_time_min=30, meal_events=[active], step_minutes=5
    )
    at_t30_with_future = compute_active_meal_carbs_g(
        current_time_min=30, meal_events=[active, future], step_minutes=5
    )

    assert math.isclose(at_t30_single, at_t30_with_future, rel_tol=1e-9)
