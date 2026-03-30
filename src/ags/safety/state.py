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
    # Current CGM reading (used by arming gate)
    current_glucose_mgdl: float = 0.0
    # Rolling delivery totals for SWARM interval caps
    delivered_last_30min_u: float = 0.0
    delivered_last_2hr_u: float = 0.0
    # Minutes since meal was first detected (for early meal push multiplier)
    minutes_since_meal_detected: float = 0.0


@dataclass
class SafetyThresholds:
    max_units_per_interval: float = 1.0           # per-pulse cap (matches swarm_max_pulse_u)
    max_insulin_on_board_u: float = 5.0          # hard IOB ceiling
    min_predicted_glucose_mgdl: float = 95.0     # predict at 30 min — block earlier
    require_confirmed_trend: bool = False   # arming gate supersedes this in SWARM mode
    hypo_resume_margin_mgdl: float = 10.0

    # ── SWARM Auto-Bolus state machine thresholds ─────────────────────────────
    # State 1 — Idle: ROC ≤ this AND ACC ≤ 0 → block
    swarm_idle_roc_max: float = 0.3
    # State 2 — Rising: confirmed entry conditions
    swarm_rising_roc_min: float = 0.3            # ROC ≥ this for swarm_rising_steps → rising
    swarm_rising_steps: int = 1                  # arm on first rising step (was 2)
    swarm_rising_roc_with_acc: float = 0.2       # ROC ≥ this with ACC > 0 → rising immediately
    # State 3 — Aggressive: higher-intensity dosing
    swarm_aggressive_roc_min: float = 0.5        # ROC ≥ this → aggressive (was 1.0)
    swarm_aggressive_glucose_min: float = 120.0  # G ≥ this with ROC ≥ below → aggressive
    swarm_aggressive_roc_with_glucose: float = 0.3  # (was 0.6)
    # State 4 — Hold: suspend all dosing
    swarm_hold_roc_max: float = -0.5             # ROC ≤ this → hold
    swarm_hold_drop_fast: float = 2.0            # drop > this mg/dL/min → hold
    swarm_hold_glucose_low: float = 100.0        # G ≤ this with any negative ROC → hold

    # ── SWARM dosing formula: Dose = U_base × (1 + a·ROC + b·ACC) × f(G) × f(IOB) ──
    swarm_u_base: float = 0.15                   # base pulse size (U) — was 0.09
    swarm_a_roc: float = 3.0                     # ROC coefficient — was 1.0
    swarm_b_acc: float = 25.0                    # ACC coefficient — was 10.0
    swarm_max_pulse_u: float = 1.0               # per-pulse ceiling
    # IOB scale breakpoints — dose dampens at these IOB levels.
    # Wider bands than the old hardcoded (1U, 2U) so the algorithm stays
    # aggressive long enough to prevent the post-prandial rise.
    swarm_iob_scale_bp1: float = 1.5             # <bp1 → 1.0×
    swarm_iob_scale_bp2: float = 3.0             # <bp2 → 0.7×, ≥bp2 → 0.4×

    # ── SWARM interval delivery caps ─────────────────────────────────────────
    swarm_max_per_30min_u: float = 3.5           # max delivered over rolling 30-min window
    swarm_max_per_2hr_u: float = 6.0            # max delivered over rolling 2-hr window

    # ── SWARM early meal push ─────────────────────────────────────────────────
    swarm_early_push_multiplier: float = 2.5     # dose multiplier during early window (was 1.5)
    swarm_early_push_min_minutes: float = 5.0    # window start (min after detection) — was 20
    swarm_early_push_max_minutes: float = 75.0   # window end — was 45

    # ── SWARM late-phase maintenance ──────────────────────────────────────────
    swarm_late_phase_glucose_min: float = 125.0  # G range for maintenance pulses (was 140)
    swarm_late_phase_glucose_max: float = 175.0  # (was 160)
    swarm_late_phase_roc_threshold: float = 0.2  # |ROC| < this → considered flat
    swarm_late_phase_iob_max: float = 1.5        # IOB must be below this to pulse (was 0.5)
    swarm_late_phase_dose_u: float = 0.125       # maintenance pulse size (was 0.075)

    # ── Micro-bolus glucose floor ─────────────────────────────────────────────
    # Main SWARM micro-bolus only fires when current glucose is at or above
    # this value.  Pre-bolus on meal ONSET and late-phase maintenance pulses
    # are exempt.  Prevents over-dosing CGM noise at euglycaemic glucose.
    swarm_min_glucose_for_microbolus: float = 130.0   # floor when no meal active
    swarm_min_glucose_during_meal: float = 120.0      # lower floor once meal is confirmed

    # ── Predictive safety check ───────────────────────────────────────────────
    # Predicted_G = G + ROC × horizon — if below this floor, no dose
    swarm_predict_horizon_min: float = 15.0      # look-ahead in minutes
    swarm_predict_floor_mgdl: float = 90.0       # no-dose floor for prediction


@dataclass
class SafetyDecision:
    status: str
    allowed: bool
    final_units: float
    reason: str


@dataclass
class SuspendState:
    """Tracks whether the safety layer has entered an active hypo suspension."""
    is_suspended: bool = False
    steps_suspended: int = 0
    suspend_reason: str = ""


@dataclass
class ArmingState:
    """4-state SWARM machine: idle → rising → aggressive → hold.

    State transitions (Jason's ACC + ROC driven spec):
      IDLE:       ROC ≤ 0.3 AND ACC ≤ 0          — block, no dose
      RISING:     ROC ≥ 0.3 (1 step)              — allow priming micro-boluses
                  OR ROC ≥ 0.2 with ACC > 0        — allow immediately
      AGGRESSIVE: ROC ≥ 0.5                         — allow scaled micro-boluses
                  OR G ≥ 120 with ROC ≥ 0.3
      HOLD:       ROC ≤ −0.5 OR drop > 2 mg/dL/min — block, suspend
                  OR G ≤ 100 with any negative ROC

    Late-phase exception: G 125–175, |ROC| < 0.2, IOB < 1.5U → allow
    maintenance pulses regardless of state.
    """
    phase: str = "idle"              # "idle" | "rising" | "aggressive" | "hold"
    steps_in_phase: int = 0
    baseline_glucose_mgdl: float = 0.0
