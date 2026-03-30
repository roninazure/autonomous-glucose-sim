from __future__ import annotations

from ags.safety.state import ArmingState, SafetyDecision, SafetyInputs, SafetyThresholds


def apply_arming_gate(
    inputs: SafetyInputs,
    thresholds: SafetyThresholds,
    state: ArmingState,
) -> tuple[SafetyDecision | None, ArmingState]:
    """Gate 0: SWARM 4-state arming machine (idle → rising → aggressive → hold).

    Returns (None, new_state) when dosing is allowed (rising or aggressive phase,
    or late-phase maintenance exception).  Returns a blocked SafetyDecision when
    in idle or hold phase.

    Priority order:
      1. HOLD  — any hold condition → block immediately, reset state
      2. Late-phase exception — G 140–160, flat, IOB low → allow maintenance
      3. AGGRESSIVE — high ROC or high glucose + moderate ROC → allow
      4. RISING — confirmed ROC ≥ 0.5 (2 steps) or ROC ≥ 0.4 + ACC > 0 → allow
      5. IDLE  — default → block
    """
    rate    = inputs.rate_mgdl_per_min
    accel   = inputs.acceleration_mgdl_per_min2
    glucose = inputs.current_glucose_mgdl
    iob     = inputs.insulin_on_board_u
    t       = thresholds

    # ── Priority 1: HOLD — suspend all dosing ────────────────────────────────
    steep_fall  = rate <= t.swarm_hold_roc_max                         # ROC ≤ −0.5
    fast_drop   = rate < -t.swarm_hold_drop_fast                       # drop > 2 mg/dL/min
    low_falling = (glucose <= t.swarm_hold_glucose_low and rate < 0)   # G ≤ 100 & falling

    if steep_fall or fast_drop or low_falling:
        if fast_drop:
            reason = f"SWARM hold — rapid drop {abs(rate):.2f} mg/dL/min > {t.swarm_hold_drop_fast}"
        elif low_falling:
            reason = f"SWARM hold — glucose {glucose:.0f} ≤ {t.swarm_hold_glucose_low} and falling"
        else:
            reason = f"SWARM hold — ROC {rate:.2f} ≤ {t.swarm_hold_roc_max} mg/dL/min"
        return SafetyDecision(
            status="blocked", allowed=False, final_units=0.0, reason=reason,
        ), ArmingState(phase="hold", steps_in_phase=0, baseline_glucose_mgdl=0.0)

    # ── Priority 2: Late-phase maintenance exception ─────────────────────────
    # G 140–160, ROC flat (|ROC| < 0.2), IOB low — allow maintenance pulses
    # even when idle, to handle the fat/protein delayed rise.
    late_phase = (
        t.swarm_late_phase_glucose_min <= glucose <= t.swarm_late_phase_glucose_max
        and abs(rate) < t.swarm_late_phase_roc_threshold
        and iob < t.swarm_late_phase_iob_max
    )
    if late_phase:
        return None, ArmingState(
            phase="rising",
            steps_in_phase=state.steps_in_phase + 1,
            baseline_glucose_mgdl=state.baseline_glucose_mgdl or glucose,
        )

    # ── Priority 3: AGGRESSIVE ────────────────────────────────────────────────
    # ROC ≥ 1.0, OR G ≥ 130 with ROC ≥ 0.6
    is_aggressive = (
        rate >= t.swarm_aggressive_roc_min
        or (glucose >= t.swarm_aggressive_glucose_min
            and rate >= t.swarm_aggressive_roc_with_glucose)
    )
    if is_aggressive:
        return None, ArmingState(
            phase="aggressive",
            steps_in_phase=state.steps_in_phase + 1,
            baseline_glucose_mgdl=state.baseline_glucose_mgdl or glucose,
        )

    # ── Priority 4: RISING ────────────────────────────────────────────────────
    # Immediate: ROC ≥ 0.4 with ACC > 0
    if rate >= t.swarm_rising_roc_with_acc and accel > 0:
        return None, ArmingState(
            phase="rising", steps_in_phase=1,
            baseline_glucose_mgdl=state.baseline_glucose_mgdl or glucose,
        )

    # Confirmed: ROC ≥ 0.5 for ≥ 2 consecutive steps
    if rate >= t.swarm_rising_roc_min:
        prev_rising = state.phase in ("rising", "aggressive")
        new_steps = (state.steps_in_phase + 1) if prev_rising else 1
        if new_steps >= t.swarm_rising_steps:
            return None, ArmingState(
                phase="rising", steps_in_phase=new_steps,
                baseline_glucose_mgdl=state.baseline_glucose_mgdl or glucose,
            )
        # First step at threshold — accumulate, not yet confirmed
        return SafetyDecision(
            status="blocked", allowed=False, final_units=0.0,
            reason=f"SWARM rising — confirming: {new_steps}/{t.swarm_rising_steps} steps "
                   f"at ROC {rate:.2f} mg/dL/min",
        ), ArmingState(
            phase="rising", steps_in_phase=new_steps,
            baseline_glucose_mgdl=state.baseline_glucose_mgdl or glucose,
        )

    # ── Priority 5: IDLE — default ───────────────────────────────────────────
    return SafetyDecision(
        status="blocked", allowed=False, final_units=0.0,
        reason=f"SWARM idle — ROC {rate:.2f} mg/dL/min below rising threshold",
    ), ArmingState(phase="idle", steps_in_phase=0, baseline_glucose_mgdl=0.0)


def apply_swarm_interval_caps(
    inputs: SafetyInputs,
    thresholds: SafetyThresholds,
) -> SafetyDecision | None:
    """Clip delivery to rolling 30-min and 2-hr window caps.

    Returns None when within limits (pass-through), or a clipped/blocked
    SafetyDecision when the rolling window cap would be exceeded.
    """
    requested = inputs.recommended_units
    if requested <= 0:
        return None

    # How much headroom remains in each window?
    headroom_30min = max(0.0, thresholds.swarm_max_per_30min_u - inputs.delivered_last_30min_u)
    headroom_2hr   = max(0.0, thresholds.swarm_max_per_2hr_u   - inputs.delivered_last_2hr_u)
    headroom       = min(headroom_30min, headroom_2hr)

    if headroom <= 0:
        window = "30-min" if headroom_30min <= 0 else "2-hr"
        return SafetyDecision(
            status="blocked", allowed=False, final_units=0.0,
            reason=f"SWARM interval cap — {window} window exhausted",
        )

    if requested > headroom:
        return SafetyDecision(
            status="clipped", allowed=True, final_units=round(headroom, 4),
            reason=f"SWARM interval cap — clipped {requested:.3f}→{headroom:.3f} U "
                   f"(30min used {inputs.delivered_last_30min_u:.2f}/{thresholds.swarm_max_per_30min_u}, "
                   f"2hr used {inputs.delivered_last_2hr_u:.2f}/{thresholds.swarm_max_per_2hr_u})",
        )

    return None


def apply_no_dose_guard(
    inputs: SafetyInputs,
) -> SafetyDecision | None:
    if inputs.recommended_units <= 0:
        return SafetyDecision(
            status="blocked",
            allowed=False,
            final_units=0.0,
            reason="no positive recommendation to deliver",
        )
    return None


def apply_trend_confirmation_guard(
    inputs: SafetyInputs,
    thresholds: SafetyThresholds,
) -> SafetyDecision | None:
    if thresholds.require_confirmed_trend and not inputs.trend_confirmed:
        return SafetyDecision(
            status="blocked",
            allowed=False,
            final_units=0.0,
            reason="trend not confirmed for dosing",
        )
    return None


def apply_hypoglycemia_guard(
    inputs: SafetyInputs,
    thresholds: SafetyThresholds,
) -> SafetyDecision | None:
    if inputs.predicted_glucose_mgdl < thresholds.min_predicted_glucose_mgdl:
        return SafetyDecision(
            status="blocked",
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
            status="blocked",
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
            status="clipped",
            allowed=True,
            final_units=final_units,
            reason="recommendation clipped to max units per interval",
        )

    return SafetyDecision(
        status="allowed",
        allowed=True,
        final_units=final_units,
        reason="recommendation allowed",
    )
