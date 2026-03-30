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


def _iob_scale(iob_u: float) -> float:
    """f(IOB): graduated dampening — avoids stacking, not a hard cut-off."""
    if iob_u < 1.0:
        return 1.0
    elif iob_u < 2.0:
        return 0.7
    else:
        return 0.4


def _swarm_micro_bolus(
    roc: float,
    acc: float,
    glucose: float,
    iob: float,
    u_base: float = 0.09,
    a: float = 1.0,
    b: float = 10.0,
    max_pulse: float = 0.5,
    early_push: bool = False,
    early_push_mult: float = 1.5,
) -> tuple[float, str]:
    """Compute SWARM micro-bolus dose and reason string.

    Formula: Dose = U_base × (1 + a·ROC + b·ACC) × f(G) × f(IOB)
    Clamped to [0, max_pulse] per pulse.
    """
    f_g   = _glucose_scale(glucose)
    f_iob = _iob_scale(iob)
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


def _prebolus_units(estimated_carbs_g: float, effective_isf: float) -> float:
    carb_impact_mgdl = estimated_carbs_g * 4.0
    return max(0.0, (carb_impact_mgdl * 0.40) / effective_isf)


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
        # G 140–160, ROC flat, IOB low → proactive maintenance pulse
        # (safety arming gate also grants a late-phase exception for this)
        late_phase = (
            140.0 <= glucose <= 160.0
            and abs(roc) < 0.2
            and iob < 0.5
        )
        if late_phase:
            return CorrectionRecommendation(
                recommended_units=0.075,
                reason=(
                    f"SWARM late-phase maintenance | "
                    f"G={glucose:.0f} mg/dL | ROC={roc:+.2f} | IOB={iob:.2f} U"
                ),
            )

        # ── Standard SWARM micro-bolus ────────────────────────────────────────
        early_push = (
            inputs.swarm_early_push_min_minutes
            <= inputs.minutes_since_meal_detected
            <= inputs.swarm_early_push_max_minutes
        ) if hasattr(inputs, "swarm_early_push_min_minutes") else (
            20.0 <= inputs.minutes_since_meal_detected <= 45.0
        )

        dose, reason = _swarm_micro_bolus(
            roc=roc,
            acc=acc,
            glucose=glucose,
            iob=iob,
            early_push=early_push,
        )
        return CorrectionRecommendation(recommended_units=dose, reason=reason)

    # ── Legacy autonomous-ISF path ────────────────────────────────────────────
    if inputs.autonomous_isf and classification is not None:
        cause = classification.cause
        rate = (
            signal.rate_mgdl_per_min
            if signal is not None
            else (classification.meal_signal.smoothed_rate_mgdl_per_min
                  if classification.meal_signal else 0.0)
        )
        base_isf, isf_label = _isf_from_ror(rate)
        effective_isf = _refine_isf_from_observations(base_isf, inputs.isf_observations)

        meal = classification.meal_signal
        if cause in (GlucoseCause.MEAL, GlucoseCause.MIXED):
            if (
                meal is not None
                and meal.recommend_prebolus
                and meal.estimated_carbs_g > 0
                and not inputs.prebolus_already_fired
            ):
                pre_units = _prebolus_units(meal.estimated_carbs_g, effective_isf)
                return CorrectionRecommendation(
                    recommended_units=pre_units,
                    reason=(
                        f"pre-bolus | meal ONSET | "
                        f"~{meal.estimated_carbs_g:.0f}g | "
                        f"conf {meal.confidence:.0%} | "
                        f"ISF {effective_isf:.0f} [{isf_label}]"
                    ),
                )

        if cause == GlucoseCause.BASAL_DRIFT:
            drift = classification.basal_signal
            excursion = prediction.predicted_glucose_mgdl - inputs.target_glucose_mgdl
            if excursion <= 0 or drift is None:
                return CorrectionRecommendation(
                    recommended_units=0.0,
                    reason="basal drift detected but predicted glucose at or below target",
                )
            full_correction = excursion / effective_isf
            basal_dose = full_correction * 0.25
            return CorrectionRecommendation(
                recommended_units=basal_dose,
                reason=(
                    f"basal drift correction | {drift.drift_type.value} | "
                    f"rate {drift.sustained_rate_mgdl_per_min:+.2f} mg/dL/min | "
                    f"linearity {drift.linearity_score:.0%} | "
                    f"ISF {effective_isf:.0f} [{isf_label}] | "
                    f"micro-dose 25%"
                ),
            )

        if cause == GlucoseCause.REBOUND:
            excursion = prediction.predicted_glucose_mgdl - inputs.target_glucose_mgdl
            if excursion <= 0:
                return CorrectionRecommendation(
                    recommended_units=0.0,
                    reason="rebound detected but predicted glucose at or below target",
                )
            full_correction = excursion / effective_isf
            return CorrectionRecommendation(
                recommended_units=full_correction * 0.10,
                reason=(
                    f"rebound correction (post-hypo) | "
                    f"ISF {effective_isf:.0f} | micro-dose 10% — monitor"
                ),
            )

    # ── Standard path ─────────────────────────────────────────────────────────
    excursion_above_target = prediction.predicted_glucose_mgdl - inputs.target_glucose_mgdl

    if excursion_above_target <= 0:
        return CorrectionRecommendation(
            recommended_units=0.0,
            reason="predicted glucose at or below target",
        )

    current_delta = inputs.current_glucose_mgdl - inputs.previous_glucose_mgdl
    if abs(current_delta) < inputs.min_excursion_delta_mgdl:
        return CorrectionRecommendation(
            recommended_units=0.0,
            reason=f"delta {current_delta:.1f} mg/dL below min excursion threshold",
        )

    if inputs.autonomous_isf and signal is not None:
        base_isf, isf_label = _isf_from_ror(signal.rate_mgdl_per_min)
        effective_isf = _refine_isf_from_observations(base_isf, inputs.isf_observations)
        isf_note = f"autonomous ISF {effective_isf:.0f} [{isf_label}]"
    else:
        effective_isf = inputs.correction_factor_mgdl_per_unit
        isf_note = None

    full_correction = max(0.0, excursion_above_target / effective_isf)

    if inputs.autonomous_isf and signal is not None:
        accel = signal.acceleration_mgdl_per_min2
        fraction = _compute_microbolus_fraction(signal.rate_mgdl_per_min, accel)
        tier_label = (
            f"RoR {signal.rate_mgdl_per_min:+.1f} mg/dL/min "
            f"accel {accel:+.3f} mg/dL/min² → δ={fraction:.0%}"
        )
    elif inputs.ror_tiered_microbolus and signal is not None:
        accel = signal.acceleration_mgdl_per_min2
        fraction = _compute_microbolus_fraction(signal.rate_mgdl_per_min, accel)
        tier_label = (
            f"RoR {signal.rate_mgdl_per_min:+.1f} mg/dL/min "
            f"accel {accel:+.3f} mg/dL/min² → δ={fraction:.0%}"
        )
    else:
        fraction = inputs.microbolus_fraction
        tier_label = None

    recommended_units = full_correction * fraction

    reason = "predicted glucose above target"
    if isf_note:
        reason += f" ({isf_note})"
    if tier_label:
        reason += f" ({tier_label})"
    elif fraction < 1.0:
        reason += f" (microbolus {fraction:.0%})"

    return CorrectionRecommendation(
        recommended_units=recommended_units,
        reason=reason,
    )
