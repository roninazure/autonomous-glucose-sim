from __future__ import annotations

from ags.safety.state import SafetyDecision, SafetyInputs, SafetyThresholds


def apply_no_dose_guard(
    inputs: SafetyInputs,
) -> SafetyDecision | None:
    if inputs.recommended_units <= 0:
        return SafetyDecision(
            allowed=False,
            final_units=0.0,
            reason="no positive recommendation to deliver",
        )
    return None


def apply_hypoglycemia_guard(
    inputs: SafetyInputs,
    thresholds: SafetyThresholds,
) -> SafetyDecision | None:
    if inputs.predicted_glucose_mgdl < thresholds.min_predicted_glucose_mgdl:
        return SafetyDecision(
            allowed=False,
            final_units=0.0,
            reason="predicted glucose below safety threshold",
        )
    return None


def apply_iob_guard(
    inputs: SafetyInputs,
    thresholds: SafetyThresholds,
) -> SafetyDecision | None:
    if inputs.insulin_on_board_u >= thresholds.max_insulin_on_board_u:
        return SafetyDecision(
            allowed=False,
            final_units=0.0,
            reason="insulin on board exceeds safety threshold",
        )
    return None


def apply_max_interval_cap(
    inputs: SafetyInputs,
    thresholds: SafetyThresholds,
) -> SafetyDecision:
    final_units = min(inputs.recommended_units, thresholds.max_units_per_interval)

    if final_units < inputs.recommended_units:
        return SafetyDecision(
            allowed=True,
            final_units=final_units,
            reason="recommendation clipped to max units per interval",
        )

    return SafetyDecision(
        allowed=True,
        final_units=final_units,
        reason="recommendation allowed",
    )
