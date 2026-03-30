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
    max_units_per_interval: float = 0.5          # per-pulse cap (SWARM default 0.5 U)
    max_insulin_on_board_u: float = 3.0
    min_predicted_glucose_mgdl: float = 80.0
    require_confirmed_trend: bool = True
    hypo_resume_margin_mgdl: float = 10.0

    # ── SWARM Auto-Bolus state machine thresholds ─────────────────────────────
    # State 1 — Idle: ROC ≤ this AND ACC ≤ 0 → block
    swarm_idle_roc_max: float = 0.3
    # State 2 — Rising: confirmed entry conditions
    swarm_rising_roc_min: float = 0.5            # ROC ≥ this for swarm_rising_steps → rising
    swarm_rising_steps: int = 2                  # consecutive steps required
    swarm_rising_roc_with_acc: float = 0.4       # ROC ≥ this with ACC > 0 → rising immediately
    # State 3 — Aggressive: higher-intensity dosing
    swarm_aggressive_roc_min: float = 1.0        # ROC ≥ this → aggressive
    swarm_aggressive_glucose_min: float = 130.0  # G ≥ this with ROC ≥ below → aggressive
    swarm_aggressive_roc_with_glucose: float = 0.6
    # State 4 — Hold: suspend all dosing
    swarm_hold_roc_max: float = -0.5             # ROC ≤ this → hold
    swarm_hold_drop_fast: float = 2.0            # drop > this mg/dL/min → hold
    swarm_hold_glucose_low: float = 100.0        # G ≤ this with any negative ROC → hold

    # ── SWARM dosing formula: Dose = U_base × (1 + a·ROC + b·ACC) × f(G) × f(IOB) ──
    swarm_u_base: float = 0.09                   # base pulse size (U)
    swarm_a_roc: float = 1.0                     # ROC coefficient
    swarm_b_acc: float = 10.0                    # ACC coefficient (weighted heavily)

    # ── SWARM interval delivery caps ─────────────────────────────────────────
    swarm_max_per_30min_u: float = 1.4           # max delivered over rolling 30-min window
    swarm_max_per_2hr_u: float = 3.0             # max delivered over rolling 2-hr window

    # ── SWARM early meal push ─────────────────────────────────────────────────
    swarm_early_push_multiplier: float = 1.5     # dose multiplier during early window
    swarm_early_push_min_minutes: float = 20.0   # window start (min after detection)
    swarm_early_push_max_minutes: float = 45.0   # window end

    # ── SWARM late-phase maintenance ──────────────────────────────────────────
    swarm_late_phase_glucose_min: float = 140.0  # G range for maintenance pulses
    swarm_late_phase_glucose_max: float = 160.0
    swarm_late_phase_roc_threshold: float = 0.2  # |ROC| < this → considered flat
    swarm_late_phase_iob_max: float = 0.5        # IOB must be below this to pulse
    swarm_late_phase_dose_u: float = 0.075       # maintenance pulse size

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
      RISING:     ROC ≥ 0.5 for 2 steps            — allow priming micro-boluses
                  OR ROC ≥ 0.4 with ACC > 0        — allow immediately
      AGGRESSIVE: ROC ≥ 1.0                         — allow scaled micro-boluses
                  OR G ≥ 130 with ROC ≥ 0.6
      HOLD:       ROC ≤ −0.5 OR drop > 2 mg/dL/min — block, suspend
                  OR G ≤ 100 with any negative ROC

    Late-phase exception: G 140–160, |ROC| < 0.2, IOB < 0.5U → allow
    maintenance pulses regardless of state.
    """
    phase: str = "idle"              # "idle" | "rising" | "aggressive" | "hold"
    steps_in_phase: int = 0
    baseline_glucose_mgdl: float = 0.0
