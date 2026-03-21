from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SafetyInputs:
    recommended_units: float
    predicted_glucose_mgdl: float
    insulin_on_board_u: float
    trend_confirmed: bool = True


@dataclass
class SafetyThresholds:
    max_units_per_interval: float = 1.0
    max_insulin_on_board_u: float = 3.0
    min_predicted_glucose_mgdl: float = 80.0
    require_confirmed_trend: bool = True
    # Glucose must rise this many mg/dL above the hypo threshold before
    # a suspension is lifted — prevents immediate re-dosing at the boundary.
    hypo_resume_margin_mgdl: float = 10.0


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
