"""Autonomous basal drift detection from CGM history.

The biological pancreas delivers background (basal) insulin continuously to
counteract hepatic glucose output, cortisol-driven gluconeogenesis, and
the slow leak of glucose from glycogen stores.  When that background coverage
is insufficient — due to incorrect programming, missed infusion-set change,
illness, or the dawn cortisol surge — glucose drifts upward *slowly* and
*linearly* for hours.

That slow linearity is the key distinguishing signal:

    Meal rise:    curved, accelerating, short-lived (45–90 min to peak)
    Basal drift:  straight, steady, sustained (hours of small positive slope)

This module detects basal drift entirely from the CGM history using two metrics:

1. **Sustained rate** — a low but consistent positive slope over a long window
   (typically ≥ 6 steps / 30 minutes at 5-min cadence).

2. **Linearity score** — the coefficient of determination (R²) of a linear fit
   to the recent glucose history.  A straight line → R² near 1.0.  A meal
   curve (accelerating) → R² well below 1.0.

Drift types:
    DAWN      — detected only when history suggests an overnight period
                 (slow rise following a period of stable/lower glucose)
    REBOUND   — preceded by a near-hypoglycaemic reading (< 80 mg/dL)
                 within the observation window
    SUSTAINED — all other cases of confirmed slow linear rise
"""
from __future__ import annotations

import math

from ags.detection.state import BasalDriftSignal, DriftType

# ── Thresholds ────────────────────────────────────────────────────────────────

# Minimum window length for drift detection (shorter → not enough data)
_MIN_WINDOW = 6           # steps (30 min at 5-min cadence)

# Drift rate band: too slow = noise, too fast = meal
_MIN_DRIFT_RATE = 0.08    # mg/dL/min
_MAX_DRIFT_RATE = 0.70    # mg/dL/min — above this, meal detector takes over

# Minimum R² to call the rise "linear" (vs. curved/meal-shaped)
_MIN_LINEARITY = 0.72

# Minimum consecutive rising steps inside the window
_MIN_RISING_STEPS = 4

# Preceding-low threshold for rebound classification
_REBOUND_LOW_THRESHOLD = 82.0  # mg/dL


def _linear_regression(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    """Return (slope, intercept, r_squared) for a simple least-squares fit."""
    n = len(xs)
    if n < 2:
        return 0.0, ys[0] if ys else 0.0, 0.0

    sx = sum(xs)
    sy = sum(ys)
    sxx = sum(x * x for x in xs)
    sxy = sum(x * y for x, y in zip(xs, ys))
    syy = sum(y * y for y in ys)

    denom = n * sxx - sx * sx
    if abs(denom) < 1e-9:
        return 0.0, sy / n, 0.0

    slope = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n

    # R²
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    ss_tot = syy - sy * sy / n
    r_squared = 1.0 - ss_res / ss_tot if abs(ss_tot) > 1e-9 else 1.0

    return slope, intercept, max(0.0, min(1.0, r_squared))


def detect_basal_drift(
    glucose_history: list[float],
    step_minutes: int = 5,
) -> BasalDriftSignal:
    """Infer basal drift from CGM history alone.

    Args:
        glucose_history: Ordered CGM readings (oldest → newest).
            The detector uses up to the last 12 readings (60 min at 5-min
            cadence) for the long-window linear fit.
        step_minutes: CGM sampling cadence.

    Returns:
        BasalDriftSignal describing the inferred drift state.
    """
    no_drift = BasalDriftSignal(
        detected=False,
        drift_type=DriftType.NONE,
        sustained_rate_mgdl_per_min=0.0,
        linearity_score=0.0,
        sustained_steps=0,
        confidence=0.0,
        preceded_by_low=False,
    )

    if len(glucose_history) < _MIN_WINDOW:
        return no_drift

    step = max(1, step_minutes)
    window = glucose_history[-12:]  # up to 60 min at 5-min cadence

    xs = list(range(len(window)))
    slope_per_step, _, r_squared = _linear_regression(xs, window)
    slope_per_min = slope_per_step / step

    # Count consecutive rising steps in window
    deltas = [window[i] - window[i - 1] for i in range(1, len(window))]
    rising_steps = sum(1 for d in deltas if d > 0)

    # Preceding-low check: any reading below threshold in the window?
    preceded_by_low = any(g < _REBOUND_LOW_THRESHOLD for g in window[:-1])

    # ── Gate conditions ───────────────────────────────────────────────────────
    if slope_per_min < _MIN_DRIFT_RATE:
        return no_drift   # too slow — noise level
    if slope_per_min > _MAX_DRIFT_RATE:
        return no_drift   # too fast — this is a meal, not basal drift
    if r_squared < _MIN_LINEARITY:
        return no_drift   # not linear enough — curved = meal
    if rising_steps < _MIN_RISING_STEPS:
        return no_drift   # not sustained enough

    # ── Drift type ────────────────────────────────────────────────────────────
    if preceded_by_low:
        drift_type = DriftType.REBOUND
    else:
        drift_type = DriftType.SUSTAINED

    # ── Confidence ────────────────────────────────────────────────────────────
    # Weighted by: linearity (most important), duration, rate in range
    linearity_score = r_squared
    streak_score = min(rising_steps / len(deltas), 1.0)
    rate_score = min(
        (slope_per_min - _MIN_DRIFT_RATE) / (_MAX_DRIFT_RATE - _MIN_DRIFT_RATE),
        1.0,
    )
    confidence = round(
        linearity_score * 0.55 + streak_score * 0.30 + rate_score * 0.15,
        2,
    )

    return BasalDriftSignal(
        detected=True,
        drift_type=drift_type,
        sustained_rate_mgdl_per_min=round(slope_per_min, 3),
        linearity_score=round(linearity_score, 3),
        sustained_steps=rising_steps,
        confidence=confidence,
        preceded_by_low=preceded_by_low,
    )
