from __future__ import annotations

from ags.controller.state import (
    ControllerInputs,
    CorrectionRecommendation,
    ExcursionSignal,
    GlucosePrediction,
)

# ── Autonomous ISF estimation ─────────────────────────────────────────────────

# RoR → ISF lookup: steeper spike signals insulin resistance (lower ISF =
# patient needs more insulin per mg/dL of correction).
_ROR_ISF_TIERS: list[tuple[float, float, str]] = [
    # (min_rate_mgdl_per_min, effective_isf, label)
    (3.0, 30.0, "aggressive spike → resistant (ISF 30)"),
    (2.0, 40.0, "rapid rise → moderate resistance (ISF 40)"),
    (1.0, 50.0, "moderate rise → standard (ISF 50)"),
    (0.5, 65.0, "slow rise → somewhat sensitive (ISF 65)"),
    (0.0, 85.0, "flat/minimal → highly sensitive (ISF 85)"),
]


def _isf_from_ror(rate_mgdl_per_min: float) -> tuple[float, str]:
    """Estimate effective ISF from observed rate of glucose rise.

    Faster spike → patient is more insulin resistant → lower ISF (system
    delivers more insulin per unit of excursion above target).

    Returns (isf_mgdl_per_unit, reason_label).
    """
    for min_rate, isf, label in _ROR_ISF_TIERS:
        if rate_mgdl_per_min >= min_rate:
            return isf, label
    return 85.0, "flat/minimal → highly sensitive (ISF 85)"


def _refine_isf_from_observations(
    base_isf: float,
    observations: list[tuple[float, float]],
    max_obs: int = 12,
) -> float:
    """Blend base RoR-estimated ISF with observed dose→response evidence.

    Each observation is (delivered_units, observed_glucose_drop_mgdl).
    A simple exponential-weighted average gives more weight to recent data.
    Falls back to base_isf when the observation window is empty or unreliable.
    """
    valid = [
        (units, drop)
        for units, drop in observations[-max_obs:]
        if units > 0.05 and drop > 0
    ]
    if not valid:
        return base_isf

    alpha = 0.35  # weight on most recent observation
    observed_isf = valid[0][1] / valid[0][0]
    for units, drop in valid[1:]:
        observed_isf = alpha * (drop / units) + (1 - alpha) * observed_isf

    # Blend: 40% learned, 60% RoR-based — prevents runaway on noisy data.
    return round(0.6 * base_isf + 0.4 * observed_isf, 1)


def _ror_to_microbolus_fraction(rate_mgdl_per_min: float) -> float:
    """Map rate of rise to a micro-bolus fraction (doctor's tiered thresholds).

    Typical post-prandial rise on 30g carbs runs ~1–2 mg/dL/min; an
    aggressive spike after a large meal or missed dose can reach 3+.

    Tiers:
        < 1.0  mg/dL/min — flat / noise → no micro-bolus pressure (0.0)
        1–2    mg/dL/min — moderate rise → 0.25 of full correction
        2–3    mg/dL/min — rapid rise    → 0.50 of full correction
        ≥ 3.0  mg/dL/min — aggressive   → 1.0  (full correction)
    """
    if rate_mgdl_per_min < 1.0:
        return 0.0
    elif rate_mgdl_per_min < 2.0:
        return 0.25
    elif rate_mgdl_per_min < 3.0:
        return 0.50
    else:
        return 1.0


def _prebolus_units(estimated_carbs_g: float, effective_isf: float) -> float:
    """Size a pre-bolus from meal onset carb estimate.

    The pre-bolus covers the *leading edge* of the meal — roughly 40% of the
    estimated carb load, expressed in insulin units.  The remaining 60% is
    handled by the adaptive micro-bolus loop as glucose continues to rise.

    Conservative by design: it is safer to under-dose and correct than to
    stack insulin on an estimate that turns out to be wrong.

    Formula:
        carb_impact ≈ estimated_carbs_g × 4 mg/dL per g (rough physiology)
        pre_dose = (carb_impact × 0.40) / effective_isf
    """
    carb_impact_mgdl = estimated_carbs_g * 4.0
    return max(0.0, (carb_impact_mgdl * 0.40) / effective_isf)


def recommend_correction(
    inputs: ControllerInputs,
    prediction: GlucosePrediction,
    signal: ExcursionSignal | None = None,
) -> CorrectionRecommendation:
    # ── Autonomous pre-bolus on meal ONSET ───────────────────────────────────
    # If the meal detector has flagged ONSET, fire a pre-bolus immediately —
    # before the glucose excursion shows up in the prediction horizon.  This
    # mirrors the biological pancreas's first-phase insulin response: rapid
    # secretion triggered by the earliest glucose rise signal.
    meal = inputs.meal_signal
    if (
        inputs.autonomous_isf
        and meal is not None
        and meal.recommend_prebolus
        and meal.estimated_carbs_g > 0
    ):
        base_isf, isf_label = _isf_from_ror(
            signal.rate_mgdl_per_min if signal is not None else meal.smoothed_rate_mgdl_per_min
        )
        effective_isf = _refine_isf_from_observations(base_isf, inputs.isf_observations)
        pre_units = _prebolus_units(meal.estimated_carbs_g, effective_isf)
        return CorrectionRecommendation(
            recommended_units=pre_units,
            reason=(
                f"autonomous pre-bolus: meal ONSET detected | "
                f"~{meal.estimated_carbs_g:.0f}g estimated | "
                f"confidence {meal.confidence:.0%} | "
                f"ISF {effective_isf:.0f} [{isf_label}]"
            ),
        )

    excursion_above_target = prediction.predicted_glucose_mgdl - inputs.target_glucose_mgdl

    if excursion_above_target <= 0:
        return CorrectionRecommendation(
            recommended_units=0.0,
            reason="predicted glucose at or below target",
        )

    # Suppress correction if the glucose trend is too small to act on —
    # avoids chasing sensor noise when glucose is near but above target.
    current_delta = inputs.current_glucose_mgdl - inputs.previous_glucose_mgdl
    if abs(current_delta) < inputs.min_excursion_delta_mgdl:
        return CorrectionRecommendation(
            recommended_units=0.0,
            reason=f"delta {current_delta:.1f} mg/dL below min excursion threshold",
        )

    # ── ISF: autonomous (RoR-derived) or fixed ───────────────────────────────
    if inputs.autonomous_isf and signal is not None:
        base_isf, isf_label = _isf_from_ror(signal.rate_mgdl_per_min)
        effective_isf = _refine_isf_from_observations(base_isf, inputs.isf_observations)
        isf_note = f"autonomous ISF {effective_isf:.0f} [{isf_label}]"
    else:
        effective_isf = inputs.correction_factor_mgdl_per_unit
        isf_note = None

    full_correction = max(0.0, excursion_above_target / effective_isf)

    # Determine micro-bolus fraction — either dynamic (RoR-tiered) or fixed.
    # In autonomous mode the RoR already sized the dose, so we always use 1.0
    # for aggressive spikes and the standard tier table otherwise.
    if inputs.autonomous_isf and signal is not None:
        fraction = _ror_to_microbolus_fraction(signal.rate_mgdl_per_min)
        # Fast spikes already get a lower ISF (larger dose) — apply fraction on
        # top so the system still micro-doses rather than front-loading.
        tier_label = f"RoR-tiered {signal.rate_mgdl_per_min:+.1f} mg/dL/min → {fraction:.0%}"
    elif inputs.ror_tiered_microbolus and signal is not None:
        fraction = _ror_to_microbolus_fraction(signal.rate_mgdl_per_min)
        tier_label = f"RoR-tiered {signal.rate_mgdl_per_min:+.1f} mg/dL/min → {fraction:.0%}"
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
