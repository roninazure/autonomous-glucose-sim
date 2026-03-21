"""
Tests for the 2-compartment PK/PD insulin model.

Key physiological properties verified:
1. Mass conservation — 1 unit eventually lowers glucose by exactly 1 × ISF.
2. Peak activity — x2 (active pool) peaks near peak_minutes.
3. Monotone IOB decay — IOB is non-increasing once dosing stops.
4. Non-negativity — compartments never go below zero.
"""
from __future__ import annotations

import math

import pytest

from ags.simulation.insulin import (
    advance_insulin_compartments,
    insulin_glucose_effect_mgdl,
    insulin_on_board,
)


# ---------------------------------------------------------------------------
# Basic mechanics
# ---------------------------------------------------------------------------


def test_no_dose_no_iob() -> None:
    x1, x2 = advance_insulin_compartments(
        x1=0.0, x2=0.0, dose_u=0.0, step_minutes=5, peak_minutes=75
    )
    assert x1 == 0.0
    assert x2 == 0.0
    assert insulin_on_board(x1, x2) == 0.0


def test_dose_enters_x1() -> None:
    """A fresh dose appears immediately in x1, not x2."""
    x1, x2 = advance_insulin_compartments(
        x1=0.0, x2=0.0, dose_u=1.0, step_minutes=5, peak_minutes=75
    )
    assert x1 > 0.0
    assert x2 > 0.0  # some transfer happens within the step
    assert x1 > x2   # most is still in depot for a 5-min step


def test_compartments_never_negative() -> None:
    x1, x2 = advance_insulin_compartments(
        x1=-0.1, x2=-0.5, dose_u=0.0, step_minutes=5, peak_minutes=75
    )
    assert x1 >= 0.0
    assert x2 >= 0.0


def test_no_effect_when_x2_is_zero() -> None:
    effect = insulin_glucose_effect_mgdl(
        x2=0.0, step_minutes=5, peak_minutes=75,
        insulin_sensitivity_mgdl_per_unit=50.0,
    )
    assert effect == 0.0


# ---------------------------------------------------------------------------
# Mass conservation: total glucose effect == ISF × dose
# ---------------------------------------------------------------------------


def test_total_glucose_effect_equals_isf_times_dose() -> None:
    """All delivered insulin must eventually lower glucose by ISF × dose."""
    isf = 50.0
    dose = 1.0
    step = 5
    peak = 75

    x1, x2 = 0.0, 0.0
    # Inject on step 0, then run for 12 hours (144 steps) with no new doses.
    x1, x2 = advance_insulin_compartments(x1, x2, dose_u=dose, step_minutes=step, peak_minutes=peak)

    total_effect = 0.0
    for _ in range(144):
        total_effect += insulin_glucose_effect_mgdl(x2, step, peak, isf)
        x1, x2 = advance_insulin_compartments(x1, x2, dose_u=0.0, step_minutes=step, peak_minutes=peak)

    assert math.isclose(total_effect, isf * dose, rel_tol=0.02), (
        f"Expected total effect ≈ {isf * dose} mg/dL, got {total_effect:.3f}"
    )


# ---------------------------------------------------------------------------
# Peak activity near peak_minutes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("peak_minutes", [55, 65, 75])
def test_x2_peaks_near_peak_minutes(peak_minutes: int) -> None:
    """The active pool (x2) should reach its maximum around peak_minutes."""
    step = 5
    x1, x2 = 0.0, 0.0
    x1, x2 = advance_insulin_compartments(x1, x2, dose_u=1.0, step_minutes=step, peak_minutes=peak_minutes)

    peak_x2 = 0.0
    peak_time = 0

    for t_step in range(1, 60):  # simulate 5 hours
        x2_prev = x2
        x1, x2 = advance_insulin_compartments(x1, x2, dose_u=0.0, step_minutes=step, peak_minutes=peak_minutes)
        if x2_prev > peak_x2:
            peak_x2 = x2_prev
            peak_time = t_step * step

    # Peak should be within ±2 steps (10 min) of the specified peak_minutes.
    assert abs(peak_time - peak_minutes) <= 10, (
        f"Expected x2 peak near {peak_minutes} min, observed near {peak_time} min"
    )


# ---------------------------------------------------------------------------
# IOB monotone decay after a single dose
# ---------------------------------------------------------------------------


def test_iob_monotonically_decreases_after_dose() -> None:
    """Once dosing stops, IOB must never increase."""
    step = 5
    peak = 75
    x1, x2 = advance_insulin_compartments(0.0, 0.0, dose_u=1.0, step_minutes=step, peak_minutes=peak)

    prev_iob = insulin_on_board(x1, x2)
    for _ in range(60):
        x1, x2 = advance_insulin_compartments(x1, x2, dose_u=0.0, step_minutes=step, peak_minutes=peak)
        iob = insulin_on_board(x1, x2)
        assert iob <= prev_iob + 1e-9, f"IOB increased: {prev_iob:.4f} → {iob:.4f}"
        prev_iob = iob
