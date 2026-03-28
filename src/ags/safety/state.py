from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SafetyInputs:
    recommended_units: float
    predicted_glucose_mgdl: float
    insulin_on_board_u: float
    trend_confirmed: bool = True
    # Rate of rise and acceleration from the excursion detector
    rate_mgdl_per_min: float = 0.0
    acceleration_mgdl_per_min2: float = 0.0
    # Current CGM reading (used by arming gate for cumulative rise tracking)
    current_glucose_mgdl: float = 0.0


@dataclass
class SafetyThresholds:
    max_units_per_interval: float = 1.0
    max_insulin_on_board_u: float = 3.0
    min_predicted_glucose_mgdl: float = 80.0
    require_confirmed_trend: bool = True
    # Glucose must rise this many mg/dL above the hypo threshold before
    # a suspension is lifted — prevents immediate re-dosing at the boundary.
    hypo_resume_margin_mgdl: float = 10.0
    # ── Arming gate parameters (doctor-specified) ─────────────────────────────
    # Slope bands in mg/dL/min that control the monitor→arm→fire state machine.
    arm_slope_monitor_mgdl_per_min: float = 0.3   # below this: hold, no dose
    arm_slope_arm_mgdl_per_min: float = 0.5        # ≥ this for arm_steps_to_arm: arm
    arm_slope_fire_mgdl_per_min: float = 0.7       # ≥ this for arm_steps_to_fire: fire
    arm_steps_to_arm: int = 1                      # steps at ≥0.5 before arming (1 = 5 min)
    arm_steps_to_fire: int = 2                     # steps at ≥0.7 before firing (2 = 10 min)
    arm_cumulative_rise_mgdl: float = 5.0          # OR cumulative rise triggers fire early
    arm_drop_stop_mgdl_per_min: float = 3.0        # rapid drop rate that forces immediate hold


@dataclass
class SafetyDecision:
    status: str
    allowed: bool
    final_units: float
    reason: str


@dataclass
class SuspendState:
    """Tracks whether the safety layer has entered an active hypo suspension.

    Unlike the stateless per-step hypo guard (which blocks one step at a time
    independently), a suspension persists across timesteps until glucose
    recovers above ``min_predicted_glucose + hypo_resume_margin``.  This
    prevents the common failure mode where the system allows a dose at t=50,
    blocks at t=55, then allows again at t=60 while glucose is still falling.
    """
    is_suspended: bool = False
    steps_suspended: int = 0
    suspend_reason: str = ""


@dataclass
class ArmingState:
    """3-state machine: monitoring → armed → firing.

    The arming gate prevents dosing until the glucose rise has been confirmed
    as sustained, per the doctor-specified protocol:
      - MONITORING: slope 0.3–0.5 mg/dL/min, no dose
      - ARMED:      slope ≥ 0.5 for arm_steps_to_arm steps, no dose yet
      - FIRING:     slope ≥ 0.7 for arm_steps_to_fire steps OR cumulative
                    rise ≥ arm_cumulative_rise_mgdl, dose allowed
    Resets to MONITORING when: slope < 0.3, rapid drop, or acceleration
    reverses while firing.
    """
    phase: str = "monitoring"           # "monitoring" | "armed" | "firing"
    steps_in_phase: int = 0
    baseline_glucose_mgdl: float = 0.0  # glucose at arming time (cumulative rise ref)
