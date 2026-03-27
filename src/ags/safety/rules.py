from __future__ import annotations

from ags.safety.state import ArmingState, SafetyDecision, SafetyInputs, SafetyThresholds


def apply_arming_gate(
    inputs: SafetyInputs,
    thresholds: SafetyThresholds,
    state: ArmingState,
) -> tuple[SafetyDecision | None, ArmingState]:
    """Gate 0: enforce the monitor → armed → firing state machine.

    Returns (None, new_state) when the system is in FIRING phase — meaning
    the caller should continue to the existing safety gates.  Returns a
    blocked SafetyDecision when in MONITORING or ARMED phase.

    Hold conditions (any one resets to MONITORING immediately):
      - slope < arm_slope_monitor_mgdl_per_min (0.3 mg/dL/min)
      - rapid drop > arm_drop_stop_mgdl_per_min (3 mg/dL/min)
      - acceleration reversed (negative) while FIRING
    """
    rate  = inputs.rate_mgdl_per_min
    accel = inputs.acceleration_mgdl_per_min2
    glucose = inputs.current_glucose_mgdl
    t = thresholds

    # ── HOLD conditions — reset to MONITORING immediately ─────────────────────
    rapid_drop = rate < -t.arm_drop_stop_mgdl_per_min
    slope_too_low = rate < t.arm_slope_monitor_mgdl_per_min
    accel_reversed = (state.phase == "firing") and (accel < 0)

    if slope_too_low or rapid_drop or accel_reversed:
        reason = (
            f"arming hold — rapid drop {abs(rate):.2f} mg/dL/min" if rapid_drop
            else f"arming hold — slope {rate:.2f} < {t.arm_slope_monitor_mgdl_per_min} mg/dL/min"
            if slope_too_low
            else "arming hold — acceleration reversed while firing"
        )
        return SafetyDecision(
            status="blocked", allowed=False, final_units=0.0, reason=reason,
        ), ArmingState(phase="monitoring", steps_in_phase=0, baseline_glucose_mgdl=0.0)

    # ── State transitions ──────────────────────────────────────────────────────
    phase = state.phase

    if phase == "monitoring":
        if rate >= t.arm_slope_arm_mgdl_per_min:  # ≥ 0.5
            new_steps = state.steps_in_phase + 1
            if new_steps >= t.arm_steps_to_arm:
                new_state = ArmingState(phase="armed", steps_in_phase=1,
                                        baseline_glucose_mgdl=glucose)
            else:
                new_state = ArmingState(phase="monitoring", steps_in_phase=new_steps,
                                        baseline_glucose_mgdl=0.0)
        else:  # 0.3 ≤ rate < 0.5 — monitor only
            new_state = ArmingState(phase="monitoring", steps_in_phase=0,
                                    baseline_glucose_mgdl=0.0)
        return SafetyDecision(
            status="blocked", allowed=False, final_units=0.0,
            reason=f"arming {new_state.phase} — slope {rate:.2f} mg/dL/min "
                   f"({new_state.steps_in_phase}/{t.arm_steps_to_arm} steps to arm)",
        ), new_state

    elif phase == "armed":
        cumulative_rise = glucose - state.baseline_glucose_mgdl
        new_steps = state.steps_in_phase + 1
        if rate >= t.arm_slope_fire_mgdl_per_min:  # ≥ 0.7
            fire_by_steps = new_steps >= t.arm_steps_to_fire
            fire_by_rise  = cumulative_rise >= t.arm_cumulative_rise_mgdl
            if fire_by_steps or fire_by_rise:
                # Transition to FIRING — pass through to existing gates
                return None, ArmingState(phase="firing", steps_in_phase=1,
                                         baseline_glucose_mgdl=state.baseline_glucose_mgdl)
        if rate < t.arm_slope_arm_mgdl_per_min:  # Lost arming slope
            return SafetyDecision(
                status="blocked", allowed=False, final_units=0.0,
                reason=f"arming disarmed — slope {rate:.2f} dropped below arm threshold",
            ), ArmingState(phase="monitoring", steps_in_phase=0, baseline_glucose_mgdl=0.0)
        # Still armed — accumulate steps
        new_state = ArmingState(phase="armed", steps_in_phase=new_steps,
                                baseline_glucose_mgdl=state.baseline_glucose_mgdl)
        return SafetyDecision(
            status="blocked", allowed=False, final_units=0.0,
            reason=f"arming armed — {new_steps}/{t.arm_steps_to_fire} steps at fire slope, "
                   f"rise={cumulative_rise:.1f}/{t.arm_cumulative_rise_mgdl} mg/dL",
        ), new_state

    else:  # firing
        # Pass through to existing gates
        return None, ArmingState(phase="firing",
                                 steps_in_phase=state.steps_in_phase + 1,
                                 baseline_glucose_mgdl=state.baseline_glucose_mgdl)


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
