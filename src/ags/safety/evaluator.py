from __future__ import annotations

from ags.safety.rules import (
    apply_hypoglycemia_guard,
    apply_iob_guard,
    apply_max_interval_cap,
    apply_no_dose_guard,
    apply_trend_confirmation_guard,
)
from ags.safety.state import SafetyDecision, SafetyInputs, SafetyThresholds, SuspendState


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


def evaluate_safety_stateful(
    inputs: SafetyInputs,
    thresholds: SafetyThresholds,
    suspend_state: SuspendState,
) -> tuple[SafetyDecision, SuspendState]:
    """Stateful safety evaluation with hypo suspend/resume logic.

    Unlike ``evaluate_safety``, this function maintains a suspension across
    consecutive timesteps.  Once triggered, the suspension holds until:
      1. Glucose trend is confirmed rising (``trend_confirmed = True``), AND
      2. Predicted glucose > hypo threshold + ``hypo_resume_margin_mgdl``.

    This closes the gap where a stateless per-step guard can alternate
    block/allow/block on consecutive steps while glucose is still falling.
    """
    resume_threshold = (
        thresholds.min_predicted_glucose_mgdl + thresholds.hypo_resume_margin_mgdl
    )

    if suspend_state.is_suspended:
        # Use a small epsilon to guard against floating-point boundary issues
        # where 89.9999999 fails to clear a 90.0 threshold despite being
        # physiologically equivalent. The margin here is clinically negligible.
        _RESUME_EPSILON = 0.01  # mg/dL
        can_resume = (
            inputs.trend_confirmed
            and inputs.predicted_glucose_mgdl >= resume_threshold - _RESUME_EPSILON
        )
        if can_resume:
            new_state = SuspendState(is_suspended=False, steps_suspended=0, suspend_reason="")
            # Resume: run normal stateless evaluation for this step
            return evaluate_safety(inputs, thresholds), new_state
        else:
            new_state = SuspendState(
                is_suspended=True,
                steps_suspended=suspend_state.steps_suspended + 1,
                suspend_reason=suspend_state.suspend_reason,
            )
            return SafetyDecision(
                status="blocked",
                allowed=False,
                final_units=0.0,
                reason=f"hypo suspension active — step {new_state.steps_suspended} "
                       f"(resume when predicted ≥ {resume_threshold:.0f} mg/dL and rising)",
            ), new_state

    # Not suspended — run normal evaluation
    decision = evaluate_safety(inputs, thresholds)

    # If the hypo guard blocked delivery, enter suspension
    if not decision.allowed and "predicted glucose below" in decision.reason:
        new_state = SuspendState(
            is_suspended=True,
            steps_suspended=1,
            suspend_reason=decision.reason,
        )
        return decision, new_state

    return decision, SuspendState(is_suspended=False)
