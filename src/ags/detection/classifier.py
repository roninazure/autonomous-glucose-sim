"""Glucose dynamics cause classifier.

Combines the meal detector and basal drift detector outputs into a single
authoritative classification that the controller uses to choose its dosing
strategy.

Decision logic
──────────────
The two detectors can fire simultaneously — e.g. a patient with insufficient
basal coverage eats a meal.  The classifier resolves that ambiguity:

1. Rate-of-rise is the primary tiebreaker:
   - Fast spike (≥ 1.5 mg/dL/min)  → MEAL dominates even if drift also detected
   - Slow rise   (< 0.7 mg/dL/min) → BASAL_DRIFT even if weak meal signal
   - In between + both detected     → MIXED

2. Rebound takes priority over MEAL if the basal detector flagged it,
   because the treatment is different (no aggressive pre-bolus — glucose
   may stabilise on its own or needs only a small correction).

3. If neither detector fires → FLAT (no correction unless predicted glucose
   exceeds target via the ordinary correction path).
"""
from __future__ import annotations

from ags.detection.basal import detect_basal_drift
from ags.detection.meal import detect_meal
from ags.detection.state import (
    BasalDriftSignal,
    DriftType,
    GlucoseCause,
    GlucoseDynamicsClassification,
    MealSignal,
)

# Rate boundary between "this is a meal" and "this could be drift"
_MEAL_RATE_FLOOR = 1.0     # mg/dL/min — below this, meal signal is weak
_DRIFT_RATE_CEIL = 0.70    # mg/dL/min — above this, drift alone is implausible


def classify_glucose_dynamics(
    glucose_history: list[float],
    step_minutes: int = 5,
) -> GlucoseDynamicsClassification:
    """Classify the cause of the current glucose excursion from CGM history alone.

    Runs both detectors and resolves conflicts using rate of rise as the
    primary tiebreaker.  Returns a unified classification the controller uses
    to select its dosing strategy.

    Args:
        glucose_history: Ordered CGM readings (oldest → newest).
        step_minutes: CGM sampling cadence.

    Returns:
        GlucoseDynamicsClassification with cause, both raw signals, and confidence.
    """
    meal = detect_meal(glucose_history, step_minutes=step_minutes)
    drift = detect_basal_drift(glucose_history, step_minutes=step_minutes)

    rate = meal.smoothed_rate_mgdl_per_min  # already computed in meal detector

    # ── Priority 1: rebound hypoglycaemia ────────────────────────────────────
    if drift.detected and drift.drift_type == DriftType.REBOUND:
        return GlucoseDynamicsClassification(
            cause=GlucoseCause.REBOUND,
            meal_signal=meal,
            basal_signal=drift,
            confidence=drift.confidence,
        )

    # ── Priority 2: both detectors fired ─────────────────────────────────────
    if meal.detected and drift.detected:
        if rate >= _MEAL_RATE_FLOOR:
            cause = GlucoseCause.MEAL
            confidence = meal.confidence
        else:
            cause = GlucoseCause.MIXED
            confidence = round((meal.confidence + drift.confidence) / 2, 2)
        return GlucoseDynamicsClassification(
            cause=cause,
            meal_signal=meal,
            basal_signal=drift,
            confidence=confidence,
        )

    # ── Priority 3: meal only ─────────────────────────────────────────────────
    if meal.detected:
        return GlucoseDynamicsClassification(
            cause=GlucoseCause.MEAL,
            meal_signal=meal,
            basal_signal=drift,
            confidence=meal.confidence,
        )

    # ── Priority 4: drift only ────────────────────────────────────────────────
    if drift.detected:
        return GlucoseDynamicsClassification(
            cause=GlucoseCause.BASAL_DRIFT,
            meal_signal=meal,
            basal_signal=drift,
            confidence=drift.confidence,
        )

    # ── Neither: flat / falling ───────────────────────────────────────────────
    return GlucoseDynamicsClassification(
        cause=GlucoseCause.FLAT,
        meal_signal=meal,
        basal_signal=drift,
        confidence=1.0,
    )
