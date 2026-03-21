"""Tests for stateful hypo suspend/resume logic."""
from __future__ import annotations

from ags.safety.evaluator import evaluate_safety_stateful
from ags.safety.state import SafetyDecision, SafetyInputs, SafetyThresholds, SuspendState


def _inputs(predicted: float, iob: float = 0.0, trend: bool = True, recommended: float = 0.5) -> SafetyInputs:
    return SafetyInputs(
        recommended_units=recommended,
        predicted_glucose_mgdl=predicted,
        insulin_on_board_u=iob,
        trend_confirmed=trend,
    )


def _thresholds() -> SafetyThresholds:
    return SafetyThresholds(
        max_units_per_interval=1.0,
        max_insulin_on_board_u=3.0,
        min_predicted_glucose_mgdl=80.0,
        require_confirmed_trend=False,
        hypo_resume_margin_mgdl=10.0,
    )


# ── Suspension entry ─────────────────────────────────────────────────────────

def test_enters_suspension_on_hypo_trigger():
    decision, state = evaluate_safety_stateful(
        inputs=_inputs(predicted=75.0),  # below 80 threshold
        thresholds=_thresholds(),
        suspend_state=SuspendState(),
    )
    assert not decision.allowed
    assert state.is_suspended
    assert state.steps_suspended == 1


def test_does_not_enter_suspension_for_non_hypo_block():
    """IOB block should not trigger suspension."""
    inputs = _inputs(predicted=120.0, iob=4.0)  # IOB block, not hypo
    decision, state = evaluate_safety_stateful(
        inputs=inputs,
        thresholds=_thresholds(),
        suspend_state=SuspendState(),
    )
    assert not decision.allowed
    assert not state.is_suspended


# ── Suspension persistence ────────────────────────────────────────────────────

def test_suspension_persists_while_glucose_low():
    """Even if recommendation is 0 (no pressure), suspension holds when glucose still low."""
    active_suspend = SuspendState(is_suspended=True, steps_suspended=1, suspend_reason="hypo")
    # Glucose still below resume threshold (80 + 10 = 90), not rising
    decision, state = evaluate_safety_stateful(
        inputs=_inputs(predicted=82.0, trend=False),
        thresholds=_thresholds(),
        suspend_state=active_suspend,
    )
    assert not decision.allowed
    assert state.is_suspended
    assert state.steps_suspended == 2
    assert "suspension active" in decision.reason


def test_suspension_step_counter_increments():
    state = SuspendState(is_suspended=True, steps_suspended=3, suspend_reason="hypo")
    _, new_state = evaluate_safety_stateful(
        inputs=_inputs(predicted=75.0, trend=False),
        thresholds=_thresholds(),
        suspend_state=state,
    )
    assert new_state.steps_suspended == 4


# ── Suspension resume ─────────────────────────────────────────────────────────

def test_resumes_when_glucose_recovers_and_rising():
    """Suspension lifts when predicted glucose > threshold + margin AND trend rising."""
    state = SuspendState(is_suspended=True, steps_suspended=3, suspend_reason="hypo")
    # Resume threshold = 80 + 10 = 90; predicted=95 and rising
    decision, new_state = evaluate_safety_stateful(
        inputs=_inputs(predicted=95.0, trend=True),
        thresholds=_thresholds(),
        suspend_state=state,
    )
    assert not new_state.is_suspended
    assert new_state.steps_suspended == 0


def test_does_not_resume_if_not_rising():
    """Recovery above threshold but trend not confirmed → stay suspended."""
    state = SuspendState(is_suspended=True, steps_suspended=2, suspend_reason="hypo")
    _, new_state = evaluate_safety_stateful(
        inputs=_inputs(predicted=95.0, trend=False),  # not rising
        thresholds=_thresholds(),
        suspend_state=state,
    )
    assert new_state.is_suspended


def test_does_not_resume_below_margin():
    """Glucose above threshold but below threshold + margin → stay suspended."""
    state = SuspendState(is_suspended=True, steps_suspended=2, suspend_reason="hypo")
    # threshold=80, margin=10 → resume needs ≥90; predicted=85 is not enough
    _, new_state = evaluate_safety_stateful(
        inputs=_inputs(predicted=85.0, trend=True),
        thresholds=_thresholds(),
        suspend_state=state,
    )
    assert new_state.is_suspended


# ── Post-resume behaviour ─────────────────────────────────────────────────────

def test_after_resume_normal_evaluation_resumes():
    """After lifting suspension, the step that triggers resume runs normal evaluation."""
    state = SuspendState(is_suspended=True, steps_suspended=2, suspend_reason="hypo")
    decision, new_state = evaluate_safety_stateful(
        inputs=_inputs(predicted=100.0, trend=True, recommended=0.3),
        thresholds=_thresholds(),
        suspend_state=state,
    )
    assert not new_state.is_suspended
    # Normal evaluation should allow (predicted=100, no IOB issue)
    assert decision.allowed


# ── Full exercise scenario end-to-end ────────────────────────────────────────

def test_suspension_across_multiple_steps():
    """Simulate 5 consecutive falling steps then recovery."""
    thresholds = _thresholds()
    state = SuspendState()
    decisions = []

    glucose_sequence = [75.0, 72.0, 70.0, 75.0, 82.0, 95.0]  # fall then rise
    trends =           [False, False, False, False, True, True]

    for predicted, rising in zip(glucose_sequence, trends):
        inp = _inputs(predicted=predicted, trend=rising)
        decision, state = evaluate_safety_stateful(inp, thresholds, state)
        decisions.append(decision.allowed)

    # Steps 0-4: all blocked (hypo or suspension)
    assert not any(decisions[:5])
    # Step 5: glucose=95 (≥90), rising → suspension lifts and dose allowed
    assert decisions[5]
