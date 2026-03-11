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

    recommended_units = max(0.0, excursion_above_target / inputs.correction_factor_mgdl_per_unit)

    return CorrectionRecommendation(
        recommended_units=recommended_units,
        reason="predicted glucose above target",
    )
