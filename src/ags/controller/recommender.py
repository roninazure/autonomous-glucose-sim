"""Cause-aware correction recommender.

Two dosing paths:

SWARM Auto-Bolus (swarm_bolus=True) — Jason's ACC + ROC driven algorithm
    Dose = U_base × (1 + a·ROC + b·ACC) × f(G) × f(IOB)

    f(G)  — glucose level scaling:  <120→0.5, 120–140→1.0, 140–160→1.5,
                                     160–180→2.0, ≥180→2.5
    f(IOB) — IOB dampening:         <1U→1.0, 1–2U→0.7, ≥2U→0.4

    Early meal push: ×1.5 multiplier for the first 20–45 min post-detection.
    Late-phase maintenance: 0.075 U when G=140–160, ROC flat, IOB low.

    Pre-bolus on meal ONSET is retained — fires once per meal event to
    cover the leading edge of carb absorption before the micro-bolus loop.

Legacy path (swarm_bolus=False) — correction-fraction approach
    Preserved for backward-compatibility with existing unit tests.
    MEAL (ONSET)    — pre-bolus (40% of carb impact)
    MEAL (PEAK)     — RoR-tiered micro-bolus: 25–100% of correction
    BASAL DRIFT     — 25%-fraction micro-bolus
    REBOUND         — 10%-fraction touch
    FLAT / standard — excursion/ISF × fraction
"""
from __future__ import annotations

from ags.controller.state import (
    ControllerInputs,
    CorrectionRecommendation,
    ExcursionSignal,
    GlucosePrediction,
)
from ags.detection.state import GlucoseCause, GlucoseDynamicsClassification

# ── SWARM dosing helpers ──────────────────────────────────────────────────────

def _glucose_scale(glucose_mgdl: float) -> float:
    """f(G): scale micro-bolus aggressiveness based on current glucose level."""
    if glucose_mgdl < 120:
        return 0.5
    elif glucose_mgdl < 140:
        return 1.0
    elif glucose_mgdl < 160:
        return 1.5
    elif glucose_mgdl < 180:
        return 2.0
    else:
        return 2.5


def _iob_scale(iob_u: float, bp1: float = 2.0, bp2: float = 4.0) -> float:
    """f(IOB): graduated dampening — avoids stacking, not a hard cut-off.

    Breakpoints are configurable so the algorithm stays aggressive through
    the full meal absorption before backing off.
    """
    if iob_u < bp1:
        return 1.0
    elif iob_u < bp2:
        return 0.7
    else:
        return 0.4


def _swarm_micro_bolus(
    roc: float,
    acc: float,
    glucose: float,
    iob: float,
    u_base: float = 0.15,
    a: float = 3.0,
    b: float = 25.0,
    max_pulse: float = 0.75,
    iob_bp1: float = 2.0,
    iob_bp2: float = 4.0,
    early_push: bool = False,
    early_push_mult: float = 2.5,
) -> tuple[float, str]:
    """Compute SWARM micro-bolus dose and reason string.

    Formula: Dose = U_base × (1 + a·ROC + b·ACC) × f(G) × f(IOB)
    Clamped to [0, max_pulse] per pulse.
    """
    f_g   = _glucose_scale(glucose)
    f_iob = _iob_scale(iob, bp1=iob_bp1, bp2=iob_bp2)
    raw   = u_base * (1.0 + a * roc + b * acc) * f_g * f_iob

    push_label = ""
    if early_push and raw > 0:
        raw *= early_push_mult
        push_label = " | EARLY PUSH ×1.5"

    dose = max(0.0, min(max_pulse, raw))

    reason = (
        f"SWARM micro-bolus | "
        f"ROC {roc:+.2f} mg/dL/min | ACC {acc:+.4f} mg/dL/min² | "
        f"f(G={glucose:.0f})={f_g} | f(IOB={iob:.2f}U)={f_iob} | "
        f"raw={raw:.3f}→{dose:.3f} U{push_label}"
    )
    return dose, reason


# ── Legacy ISF / RoR helpers (preserved for non-SWARM path) ──────────────────

_ROR_ISF_TIERS: list[tuple[float, float, str]] = [
    (3.0, 30.0, "aggressive spike → resistant (ISF 30)"),
    (2.0, 40.0, "rapid rise → moderate resistance (ISF 40)"),
    (1.0, 50.0, "moderate rise → standard (ISF 50)"),
    (0.5, 65.0, "slow rise → somewhat sensitive (ISF 65)"),
    (0.0, 85.0, "flat/minimal → highly sensitive (ISF 85)"),
]


def _isf_from_ror(rate_mgdl_per_min: float) -> tuple[float, str]:
    for min_rate, isf, label in _ROR_ISF_TIERS:
        if rate_mgdl_per_min >= min_rate:
            return isf, label
    return 85.0, "flat/minimal → highly sensitive (ISF 85)"


def _refine_isf_from_observations(
    base_isf: float,
    observations: list[tuple[float, float]],
    max_obs: int = 12,
) -> float:
    valid = [
        (units, drop)
        for units, drop in observations[-max_obs:]
        if units > 0.05 and drop > 0
    ]
    if not valid:
        return base_isf

    alpha = 0.35
    observed_isf = valid[0][1] / valid[0][0]
    for units, drop in valid[1:]:
        observed_isf = alpha * (drop / units) + (1 - alpha) * observed_isf

    return round(0.6 * base_isf + 0.4 * observed_isf, 1)


def _compute_microbolus_fraction(
    rate_mgdl_per_min: float,
    acceleration_mgdl_per_min2: float = 0.0,
) -> float:
    if rate_mgdl_per_min < 1.0:
        base = 0.0
    elif rate_mgdl_per_min < 2.0:
        base = 0.25
    elif rate_mgdl_per_min < 3.0:
        base = 0.50
    else:
        base = 1.0

    if acceleration_mgdl_per_min2 > 0.05:
        modifier = 1.25
    elif acceleration_mgdl_per_min2 < -0.05:
        modifier = 0.75
    else:
        modifier = 1.0

    return min(1.0, base * modifier)


def _ror_to_microbolus_fraction(rate_mgdl_per_min: float) -> float:
    """Legacy wrapper — ROR-only fraction (no acceleration context)."""
    return _compute_microbolus_fraction(rate_mgdl_per_min, acceleration_mgdl_per_min2=0.0)


def _prebolus_units(estimated_carbs_g: float, effective_isf: float, fraction: float = 0.60) -> float:
    carb_impact_mgdl = estimated_carbs_g * 4.0
    return max(0.0, (carb_impact_mgdl * fraction) / effective_isf)


# ── Main entry point ──────────────────────────────────────────────────────────

def recommend_correction(
    inputs: ControllerInputs,
    prediction: GlucosePrediction,
    signal: ExcursionSignal | None = None,
    classification: GlucoseDynamicsClassification | None = None,
) -> CorrectionRecommendation:

    # ── SWARM Auto-Bolus path ─────────────────────────────────────────────────
    if inputs.swarm_bolus and signal is not None:
        glucose = inputs.current_glucose_mgdl
        roc     = signal.rate_mgdl_per_min
        acc     = signal.acceleration_mgdl_per_min2
        iob     = inputs.insulin_on_board_u

        # ── Meal onset pre-bolus (one-time, retained even in SWARM mode) ─────
        if classification is not None:
            cause = classification.cause
            meal  = classification.meal_signal
            if cause in (GlucoseCause.MEAL, GlucoseCause.MIXED):
                if (
                    meal is not None
                    and meal.recommend_prebolus
                    and meal.estimated_carbs_g > 0
                    and not inputs.prebolus_already_fired
                ):
                    base_isf, isf_label = _isf_from_ror(roc)
                    effective_isf = _refine_isf_from_observations(
                        base_isf, inputs.isf_observations
                    )
                    pre_units = _prebolus_units(meal.estimated_carbs_g, effective_isf)
                    return CorrectionRecommendation(
                        recommended_units=pre_units,
                        reason=(
                            f"SWARM pre-bolus | meal ONSET | "
                            f"~{meal.estimated_carbs_g:.0f}g | "
                            f"conf {meal.confidence:.0%} | ISF {effective_isf:.0f}"
                        ),
                    )

        # ── Late-phase maintenance ────────────────────────────────────────────
        # G in configured range, ROC flat, IOB low → proactive maintenance pulse
        # (safety arming gate also grants a late-phase exception for this)
        late_phase = (
            inputs.swarm_late_phase_glucose_min <= glucose <= inputs.swarm_late_phase_glucose_max
            and abs(roc) < inputs.swarm_late_phase_roc_threshold
            and roc >= 0.0  # never maintain-dose into a falling glucose
            and iob < inputs.swarm_late_phase_iob_max
        )
        if late_phase:
            return CorrectionRecommendation(
                recommended_units=inputs.swarm_late_phase_dose_u,
                reason=(
                    f"SWARM late-phase maintenance | "
                    f"G={glucose:.0f} mg/dL | ROC={roc:+.2f} | IOB={iob:.2f} U"
                ),
            )

        # ── Glucose floor: don't micro-bolus near target ─────────────────────
        # Use a lower floor only when a substantial carb meal has been confirmed
        # (estimated_carbs_g > 10) — hormonal rises (dawn, exercise) should
        # NOT trigger the lower floor as they'll cause over-dosing.
        # Pre-bolus and late-phase maintenance are always exempt from this gate.
        meal_active = (
            classification is not None
            and classification.meal_signal is not None
            and classification.meal_signal.detected
            and classification.meal_signal.estimated_carbs_g > 10.0
        )
        active_floor = (
            inputs.swarm_min_glucose_during_meal
            if meal_active
            else inputs.swarm_min_glucose_for_microbolus
        )
        if glucose < active_floor:
            return CorrectionRecommendation(
                recommended_units=0.0,
                reason=(
                    f"SWARM micro-bolus suppressed | "
                    f"G={glucose:.0f} < floor {active_floor:.0f} mg/dL"
                ),
            )

        # ── Standard SWARM micro-bolus ────────────────────────────────────────
        early_push = (
            inputs.swarm_early_push_min_minutes
            <= inputs.minutes_since_meal_detected
            <= inputs.swarm_early_push_max_minutes
        )

        dose, reason = _swarm_micro_bolus(
            roc=roc,
            acc=acc,
            glucose=glucose,
            iob=iob,
            u_base=inputs.swarm_u_base,
            a=inputs.swarm_a_roc,
            b=inputs.swarm_b_acc,
            max_pulse=inputs.swarm_max_pulse_u,
            iob_bp1=inputs.swarm_iob_scale_bp1,
            iob_bp2=inputs.swarm_iob_scale_bp2,
            early_push=early_push,
            early_push_mult=inputs.swarm_early_push_multiplier,
        )
        return CorrectionRecommendation(recommended_units=dose, reason=reason)

    # Non-SWARM path: system is proactive-only (ROC + ACC driven via swarm_bolus=True).
    # Return no recommendation when called without SWARM mode active.
    return CorrectionRecommendation(
        recommended_units=0.0,
        reason="no proactive recommendation — enable swarm_bolus for autonomous dosing",
    )
