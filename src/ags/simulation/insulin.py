from __future__ import annotations

import math


def advance_insulin_compartments(
    x1: float,
    x2: float,
    dose_u: float,
    step_minutes: float,
    peak_minutes: float,
) -> tuple[float, float]:
    """Advance the 2-compartment PK/PD insulin model by one timestep.

    Models rapid-acting insulin as a gamma(2, τ) activity curve, which
    matches the rise-then-fall shape seen clinically.  The two compartments
    are:
        x1 — subcutaneous depot (decays into x2)
        x2 — interstitial / active pool (drives glucose effect)

    Exact discrete update derived from the matrix exponential of:
        dx1/dt = -x1/τ
        dx2/dt =  x1/τ - x2/τ

    The new dose is added to x1 at the start of the step (bolus injection).

    Args:
        x1: Current subcutaneous depot (units).
        x2: Current active interstitial pool (units).
        dose_u: Insulin delivered this step (units).
        step_minutes: Duration of the timestep (minutes).
        peak_minutes: Time to peak insulin activity (τ, minutes).
                      75 ≈ NovoLog/Aspart; 65 ≈ Humalog; 55 ≈ Fiasp.

    Returns:
        (x1_next, x2_next) after one timestep.
    """
    k = math.exp(-step_minutes / peak_minutes)
    transfer = (step_minutes / peak_minutes) * k

    x1_with_dose = x1 + dose_u
    x1_next = max(0.0, k * x1_with_dose)
    x2_next = max(0.0, transfer * x1_with_dose + k * x2)

    return x1_next, x2_next


def insulin_glucose_effect_mgdl(
    x2: float,
    step_minutes: float,
    peak_minutes: float,
    insulin_sensitivity_mgdl_per_unit: float,
) -> float:
    """Glucose lowering (mg/dL) produced by the active insulin pool this step.

    Effect rate = x2 / τ, integrated over the step duration.

    Args:
        x2: Active interstitial insulin pool (units).
        step_minutes: Duration of the timestep (minutes).
        peak_minutes: Time to peak insulin activity (τ, minutes).
        insulin_sensitivity_mgdl_per_unit: ISF (mg/dL per unit).

    Returns:
        Glucose decrease in mg/dL for this step.
    """
    return x2 * (step_minutes / peak_minutes) * insulin_sensitivity_mgdl_per_unit


def insulin_on_board(x1: float, x2: float) -> float:
    """Total insulin on board: sum of both compartments."""
    return x1 + x2
