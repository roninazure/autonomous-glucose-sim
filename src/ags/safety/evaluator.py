from __future__ import annotations

from dataclasses import replace as _dc_replace

from ags.safety.rules import (
    apply_arming_gate,
    apply_hypoglycemia_guard,
    apply_iob_guard,
    apply_max_interval_cap,
    apply_no_dose_guard,
    apply_swarm_interval_caps,
    apply_trend_confirmation_guard,
)
from ags.safety.state import (
    ArmingState,
    SafetyDecision,
    SafetyInputs,
    SafetyThresholds,
    SuspendState,
)


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

    interval_decision = apply_swarm_interval_caps(inputs, thresholds)
    if interval_decision is not None:
        if not interval_decision.allowed:
            # Rolling window exhausted — block entirely
            return interval_decision
        # Rolling window clipped the dose — apply per-pulse cap on top
        return apply_max_interval_cap(
            _dc_replace(inputs, recommended_units=interval_decision.final_units),
            thresholds,
        )

    return apply_max_interval_cap(inputs, thresholds)


def evaluate_safety_stateful(
    inputs: SafetyInputs,
    thresholds: SafetyThresholds,
    suspend_state: SuspendState,
    arming_state: ArmingState | None = None,
) -> tuple[SafetyDecision, SuspendState, ArmingState]:
    """Stateful safety evaluation with hypo suspend/resume and arming gate.

    Gate order:
      0. Arming gate (monitor → armed → firing) — when arming_state provided
      1. Hypo suspension check
      2–6. Stateless gates: no_dose, trend, hypo_guard, IOB, interval_cap

    Pass ``arming_state=None`` (default) to skip the arming gate entirely —
    existing unit tests use this path to test suspension in isolation.

    Returns (decision, new_suspend_state, new_arming_state).
    """
    # ── Gate 0: arming gate (only when caller manages arming state) ───────────
    # Pass arming_state=None to skip this gate entirely (used by unit tests
    # that focus on suspension logic in isolation).
    if arming_state is not None:
        arming_decision, new_arming = apply_arming_gate(inputs, thresholds, arming_state)
        if arming_decision is not None:
            return arming_decision, suspend_state, new_arming
    else:
        new_arming = ArmingState(phase="aggressive")

    # ── Gate 1: hypo suspension check ─────────────────────────────────────────
    resume_threshold = (
        thresholds.min_predicted_glucose_mgdl + thresholds.hypo_resume_margin_mgdl
    )

    if suspend_state.is_suspended:
        _RESUME_EPSILON = 0.01  # mg/dL — guard floating-point boundary
        can_resume = (
            inputs.trend_confirmed
            and inputs.predicted_glucose_mgdl >= resume_threshold - _RESUME_EPSILON
        )
        if can_resume:
            new_suspend = SuspendState(is_suspended=False, steps_suspended=0, suspend_reason="")
            # On resume, run normal stateless evaluation
            decision = evaluate_safety(inputs, thresholds)
            # Reset arming — system must re-confirm rise after hypo recovery
            resumed_arming = ArmingState(phase="idle", steps_in_phase=0,
                                         baseline_glucose_mgdl=0.0)
            return decision, new_suspend, resumed_arming
        else:
            new_suspend = SuspendState(
                is_suspended=True,
                steps_suspended=suspend_state.steps_suspended + 1,
                suspend_reason=suspend_state.suspend_reason,
            )
            return SafetyDecision(
                status="blocked",
                allowed=False,
                final_units=0.0,
                reason=f"hypo suspension active — step {new_suspend.steps_suspended} "
                       f"(resume when predicted ≥ {resume_threshold:.0f} mg/dL and rising)",
            ), new_suspend, new_arming

    # ── Gates 2–6: stateless evaluation ───────────────────────────────────────
    decision = evaluate_safety(inputs, thresholds)

    # If the hypo guard blocked delivery, enter suspension and reset arming
    if not decision.allowed and "predicted glucose below" in decision.reason:
        new_suspend = SuspendState(
            is_suspended=True,
            steps_suspended=1,
            suspend_reason=decision.reason,
        )
        reset_arming = ArmingState(phase="monitoring", steps_in_phase=0,
                                   baseline_glucose_mgdl=0.0)
        return decision, new_suspend, reset_arming

    return decision, SuspendState(is_suspended=False), new_arming
