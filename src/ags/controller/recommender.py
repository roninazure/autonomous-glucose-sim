from __future__ import annotations

from ags.controller.state import ControllerInputs, CorrectionRecommendation, GlucosePrediction


def recommend_correction(
    inputs: ControllerInputs,
    prediction: GlucosePrediction,
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
    recommended_units = full_correction * inputs.microbolus_fraction

    reason = "predicted glucose above target"
    if inputs.microbolus_fraction < 1.0:
        reason += f" (microbolus {inputs.microbolus_fraction:.0%})"

    return CorrectionRecommendation(
        recommended_units=recommended_units,
        reason=reason,
    )
