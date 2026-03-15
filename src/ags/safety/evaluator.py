from __future__ import annotations

from ags.safety.rules import (
    apply_hypoglycemia_guard,
    apply_iob_guard,
    apply_max_interval_cap,
    apply_no_dose_guard,
    apply_trend_confirmation_guard,
)
from ags.safety.state import SafetyDecision, SafetyInputs, SafetyThresholds


def evaluate_safety(
    inputs: SafetyInputs,
    thresholds: SafetyThresholds | None = None,
) -> SafetyDecision:
    thresholds = thresholds or SafetyThresholds()

    no_dose_decision = apply_no_dose_guard(inputs)
    if no_dose_decision is not None:
        return no_dose_decision

    trend_decision = apply_trend_confirmation_guard(inputs, thresholds)
    if trend_decision is not None:
        return trend_decision

    hypo_decision = apply_hypoglycemia_guard(inputs, thresholds)
    if hypo_decision is not None:
        return hypo_decision

    iob_decision = apply_iob_guard(inputs, thresholds)
    if iob_decision is not None:
        return iob_decision

    return apply_max_interval_cap(inputs, thresholds)
