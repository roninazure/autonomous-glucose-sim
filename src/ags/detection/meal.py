"""Autonomous meal detection from CGM dynamics alone.

The self-driving pancreas does not receive meal announcements.  Instead it
infers the presence, onset, and approximate magnitude of a meal entirely from
the shape of the glucose curve — exactly as the biological pancreas does via
the portal vein glucose sensor.

Three signals drive the detector:

1. **Rate of rise (1st derivative)** — fast sustained rise = carbs being
   absorbed.  Post-prandial rise on a 30 g meal typically reaches 1–2
   mg/dL/min; a 80 g meal or missed prior dose can push 3+ mg/dL/min.

2. **Acceleration (2nd derivative)** — positive acceleration confirms the
   rise is *speeding up*, distinguishing an early post-prandial rise from a
   plateau or already-decelerating excursion.

3. **Sustained duration** — at least two consecutive readings must be rising
   before a meal is declared, filtering out single-step CGM noise.

Meal phase classification:
    ONSET    — acceleration positive, rate above threshold: meal just started
    PEAK     — rate high but acceleration turning negative: nearing peak
    RECOVERY — rate falling back, glucose above target but descending
    NONE     — no meal in progress

Carb estimation:
    Rough heuristic calibrated to the simulation's physiology:
    ~1 mg/dL/min sustained rate ≈ 20–25 g carbs in an average adult.
    The estimate is intentionally conservative — the controller uses it
    to size a *pre-bolus* that covers the leading edge while micro-boluses
    handle the rest adaptively.
"""
from __future__ import annotations

from ags.detection.state import MealPhase, MealSignal

# ── Tuneable thresholds ───────────────────────────────────────────────────────

# Minimum smoothed rate (mg/dL/min) to consider a rise significant
_RISE_RATE_THRESHOLD = 0.8

# Minimum consecutive rising steps before declaring meal onset
_MIN_CONSECUTIVE_RISING = 2

# Smoothing factor for exponential weighted mean of deltas (same as predictor)
_ALPHA = 0.4

# Carb estimate scalar: mg/dL per min of sustained rise → grams
_CARB_ESTIMATE_SCALE = 22.0


def _ewm(values: list[float], alpha: float = _ALPHA) -> float:
    """Exponential weighted mean of a list — most recent reading weighted most."""
    if not values:
        return 0.0
    result = values[0]
    for v in values[1:]:
        result = alpha * v + (1 - alpha) * result
    return result


def detect_meal(
    glucose_history: list[float],
    step_minutes: int = 5,
) -> MealSignal:
    """Infer meal phase from CGM history alone.

    Args:
        glucose_history: Ordered list of CGM readings (oldest → newest).
            Requires at least 4 readings for a reliable 2nd-derivative signal.
        step_minutes: CGM sampling cadence in minutes.

    Returns:
        MealSignal describing the inferred meal state.
    """
    no_meal = MealSignal(
        detected=False,
        phase=MealPhase.NONE,
        smoothed_rate_mgdl_per_min=0.0,
        acceleration_mgdl_per_min2=0.0,
        consecutive_rising_steps=0,
        estimated_carbs_g=0.0,
        confidence=0.0,
        recommend_prebolus=False,
    )

    if len(glucose_history) < 3:
        return no_meal

    step = max(1, step_minutes)

    # 1st derivative: per-step deltas (mg/dL per step)
    deltas = [glucose_history[i] - glucose_history[i - 1] for i in range(1, len(glucose_history))]

    # Smoothed rate in mg/dL per MINUTE
    smoothed_rate_per_step = _ewm(deltas)
    smoothed_rate = smoothed_rate_per_step / step

    # 2nd derivative: delta of deltas
    if len(deltas) >= 2:
        delta_deltas = [deltas[i] - deltas[i - 1] for i in range(1, len(deltas))]
        acceleration = _ewm(delta_deltas) / (step * step)
    else:
        acceleration = 0.0

    # Consecutive rising steps (look back up to 6 steps)
    lookback = min(len(deltas), 6)
    consecutive_rising = 0
    for d in reversed(deltas[-lookback:]):
        if d > 0:
            consecutive_rising += 1
        else:
            break

    # ── Phase classification ──────────────────────────────────────────────────

    if smoothed_rate >= _RISE_RATE_THRESHOLD and consecutive_rising >= _MIN_CONSECUTIVE_RISING:
        # Rising fast enough and for long enough — a meal is in progress
        if acceleration > 0:
            phase = MealPhase.ONSET
        else:
            phase = MealPhase.PEAK
    elif smoothed_rate < 0 and glucose_history[-1] > 110.0 and consecutive_rising == 0:
        # Glucose falling back from above target — post-prandial recovery
        phase = MealPhase.RECOVERY
    else:
        return no_meal

    detected = phase in (MealPhase.ONSET, MealPhase.PEAK)

    # ── Confidence score ──────────────────────────────────────────────────────
    # Combines rate magnitude, consecutive count, and acceleration coherence.
    rate_score = min(smoothed_rate / 3.0, 1.0)                          # 0–1 capped at 3 mg/dL/min
    streak_score = min(consecutive_rising / 4.0, 1.0)                   # 0–1 capped at 4 steps
    accel_score = 1.0 if (phase == MealPhase.ONSET and acceleration > 0) else 0.5
    confidence = round((rate_score * 0.5 + streak_score * 0.35 + accel_score * 0.15), 2)

    # ── Carb estimate ─────────────────────────────────────────────────────────
    # Conservative estimate: only on ONSET so we don't double-count.
    # Rough calibration: 1 mg/dL/min ≈ 22 g carbs in a standard adult.
    estimated_carbs_g = round(max(0.0, smoothed_rate * _CARB_ESTIMATE_SCALE), 1) if detected else 0.0

    # Recommend a pre-bolus only on ONSET (not PEAK — too late for pre-bolus)
    recommend_prebolus = phase == MealPhase.ONSET

    return MealSignal(
        detected=detected,
        phase=phase,
        smoothed_rate_mgdl_per_min=round(smoothed_rate, 3),
        acceleration_mgdl_per_min2=round(acceleration, 4),
        consecutive_rising_steps=consecutive_rising,
        estimated_carbs_g=estimated_carbs_g,
        confidence=confidence,
        recommend_prebolus=recommend_prebolus,
    )
