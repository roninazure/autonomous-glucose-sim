from __future__ import annotations

from ags.controller.state import (
    ControllerInputs,
    CorrectionRecommendation,
    ExcursionSignal,
    GlucosePrediction,
)


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


def recommend_correction(
    inputs: ControllerInputs,
    prediction: GlucosePrediction,
    signal: ExcursionSignal | None = None,
) -> CorrectionRecommendation:
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

    full_correction = max(0.0, excursion_above_target / inputs.correction_factor_mgdl_per_unit)

    # Determine micro-bolus fraction — either dynamic (RoR-tiered) or fixed.
    if inputs.ror_tiered_microbolus and signal is not None:
        fraction = _ror_to_microbolus_fraction(signal.rate_mgdl_per_min)
        tier_label = f"RoR-tiered {signal.rate_mgdl_per_min:+.1f} mg/dL/min → {fraction:.0%}"
    else:
        fraction = inputs.microbolus_fraction
        tier_label = None

    recommended_units = full_correction * fraction

    reason = "predicted glucose above target"
    if tier_label:
        reason += f" ({tier_label})"
    elif fraction < 1.0:
        reason += f" (microbolus {fraction:.0%})"

    return CorrectionRecommendation(
        recommended_units=recommended_units,
        reason=reason,
    )
