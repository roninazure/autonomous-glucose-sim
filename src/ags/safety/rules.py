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
      1. No-meal IOB ceiling — IOB ≥ limit with no active meal → block
      2. HOLD  — any hold condition → block immediately, reset state
      3. Late-phase exception — G 125–175, flat, IOB low → allow maintenance
      4. AGGRESSIVE — high ROC or high glucose + moderate ROC → allow
      5. RISING — confirmed ROC ≥ 0.2 (1 step) or ROC ≥ 0.2 + ACC > 0 → allow
      6. IDLE  — default → block
    """
    rate    = inputs.rate_mgdl_per_min
    accel   = inputs.acceleration_mgdl_per_min2
    glucose = inputs.current_glucose_mgdl
    iob     = inputs.insulin_on_board_u
    t       = thresholds

    # ── Priority 1: No-meal IOB ceiling ──────────────────────────────────────
    # When no food is actively absorbing (onset/peak phase not detected),
    # block new doses if IOB exceeds the no-meal ceiling.  This prevents
    # re-arming for brief glucose rebounds after a fast-absorbing food (e.g.
    # OJ) finishes while residual IOB is still substantial.
    if not inputs.meal_active and iob >= t.swarm_no_meal_max_iob_u:
        return SafetyDecision(
            status="blocked", allowed=False, final_units=0.0,
            reason=(
                f"no active meal — IOB {iob:.2f}U ≥ no-meal ceiling "
                f"{t.swarm_no_meal_max_iob_u:.1f}U"
            ),
        ), ArmingState(phase="hold", steps_in_phase=0, baseline_glucose_mgdl=0.0)

    # ── Priority 2: HOLD — suspend all dosing ────────────────────────────────
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

    # ── Priority 3: Late-phase maintenance exception ─────────────────────────
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


def _dynamic_iob_ceiling(
    roc: float,
    acc: float,
    jerk: float,
    thresholds: SafetyThresholds,
) -> float:
    """Compute a derivative-driven IOB ceiling.

    Ceiling rises with positive ROC (1st), positive ACC (2nd), and positive
    JERK (3rd) — allowing more IOB when glucose is accelerating upward.

    Negative ACC (glucose decelerating — absorption peak approaching) LOWERS
    the ceiling using a separate, stronger scale.  This automatically adapts
    to absorption speed:
      - Fast food (OJ, juice): steep deceleration → ceiling collapses quickly
        once the IOB is already substantial → blocks over-delivery
      - Slow food (mixed meal): mild deceleration when IOB is still low → dose
        passes the IOB guard and continues to build appropriately

    Clamped between dynamic_iob_min_ceiling_u and max_insulin_on_board_u.
    """
    roc_contrib  = thresholds.dynamic_iob_roc_scale  * max(0.0, roc)
    # Positive ACC raises ceiling; negative ACC lowers it (separate scale)
    if acc >= 0:
        acc_contrib = thresholds.dynamic_iob_acc_scale * acc
        # Jerk only counts when glucose is still accelerating upward.
        # When ACC < 0 (decelerating — meal peak approaching), the recovery
        # from a steep negative ACC creates a large spurious positive jerk that
        # would otherwise overwhelm the neg-ACC penalty.  Suppress it.
        jerk_contrib = thresholds.dynamic_iob_jerk_scale * max(0.0, jerk)
    else:
        acc_contrib  = thresholds.dynamic_iob_neg_acc_scale * acc  # negative → subtracts
        jerk_contrib = 0.0  # jerk suppressed during deceleration phase
    ceiling = thresholds.dynamic_iob_base_u + roc_contrib + acc_contrib + jerk_contrib
    return max(
        thresholds.dynamic_iob_min_ceiling_u,
        min(ceiling, thresholds.max_insulin_on_board_u),
    )


def apply_iob_guard(
    inputs: SafetyInputs,
    thresholds: SafetyThresholds,
) -> SafetyDecision | None:
    if thresholds.dynamic_iob_enabled:
        ceiling = _dynamic_iob_ceiling(
            roc=inputs.rate_mgdl_per_min,
            acc=inputs.acceleration_mgdl_per_min2,
            jerk=inputs.jerk_mgdl_per_min3,
            thresholds=thresholds,
        )
    else:
        ceiling = thresholds.max_insulin_on_board_u

    if inputs.insulin_on_board_u >= ceiling:
        return SafetyDecision(
            status="blocked",
            allowed=False,
            final_units=0.0,
            reason=(
                f"insulin on board exceeds safety threshold"
                if not thresholds.dynamic_iob_enabled
                else f"IOB {inputs.insulin_on_board_u:.2f}U ≥ dynamic ceiling "
                     f"{ceiling:.2f}U (ROC {inputs.rate_mgdl_per_min:+.2f} "
                     f"ACC {inputs.acceleration_mgdl_per_min2:+.4f} "
                     f"JERK {inputs.jerk_mgdl_per_min3:+.5f})"
            ),
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
