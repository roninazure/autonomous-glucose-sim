from __future__ import annotations

from ags.safety.rules import (
    apply_hypoglycemia_guard,
    apply_iob_guard,
    apply_max_interval_cap,
)
from ags.safety.state import SafetyDecision, SafetyInputs, SafetyThresholds


def evaluate_safety(
    inputs: SafetyInputs,
    thresholds: SafetyThresholds | None = None,
) -> SafetyDecision:
    thresholds = thresholds or SafetyThresholds()

    hypo_decision = apply_hypoglycemia_guard(inputs, thresholds)
    if hypo_decision is not None:
        return hypo_decision

    iob_decision = apply_iob_guard(inputs, thresholds)
    if iob_decision is not None:
        return iob_decision

    return apply_max_interval_cap(inputs, thresholds)
