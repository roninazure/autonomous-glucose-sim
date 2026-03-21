"""Per-decision explanation state for the autonomous dosing controller.

A ``DecisionExplanation`` captures every intermediate value produced during
one timestep of the controller-safety-pump pipeline, plus a human-readable
narrative sentence.  It is designed so that an endocrinologist (or a
regulatory reviewer) can audit the system's reasoning at any point in a run
without needing to understand the underlying code.
"""
from __future__ import annotations

from dataclasses import dataclass


# ── Gate identifiers ──────────────────────────────────────────────────────────
#
# Each safety gate has a short stable identifier used for filtering and
# colour-coding in the dashboard.  The identifier is independent of the exact
# reason string (which can change) to keep downstream code stable.

GATE_NO_DOSE = "no_dose"
GATE_TREND_CONFIRMATION = "trend_confirmation"
GATE_HYPO_GUARD = "hypo_guard"
GATE_IOB_GUARD = "iob_guard"
GATE_MAX_INTERVAL_CAP = "max_interval_cap"
GATE_ALLOWED = "allowed"
GATE_SUSPENSION = "suspension"


def gate_from_reason(reason: str, is_suspended: bool) -> str:
    """Map a ``SafetyDecision.reason`` string to a stable gate identifier.

    The mapping is based on substring matching against the canonical reason
    strings produced by ``ags.safety.rules``.  Falls back to ``GATE_ALLOWED``
    if no pattern matches.
    """
    if is_suspended or "hypo suspension active" in reason:
        return GATE_SUSPENSION
    if "no positive recommendation" in reason:
        return GATE_NO_DOSE
    if "trend not confirmed" in reason:
        return GATE_TREND_CONFIRMATION
    if "predicted glucose below" in reason:
        return GATE_HYPO_GUARD
    if "insulin on board exceeds" in reason:
        return GATE_IOB_GUARD
    if "clipped" in reason:
        return GATE_MAX_INTERVAL_CAP
    return GATE_ALLOWED


# ── Gate display metadata ─────────────────────────────────────────────────────

GATE_LABELS: dict[str, str] = {
    GATE_NO_DOSE:            "No dose needed",
    GATE_TREND_CONFIRMATION: "Trend not yet confirmed",
    GATE_HYPO_GUARD:         "Hypoglycaemia risk — withheld",
    GATE_IOB_GUARD:          "Active insulin too high — withheld",
    GATE_MAX_INTERVAL_CAP:   "Dose capped at safety limit",
    GATE_ALLOWED:            "Approved ✓",
    GATE_SUSPENSION:         "Dosing suspended",
}

GATE_COLOURS: dict[str, str] = {
    GATE_NO_DOSE:            "#888888",
    GATE_TREND_CONFIRMATION: "#ffaa00",
    GATE_HYPO_GUARD:         "#ff4444",
    GATE_IOB_GUARD:          "#ff8800",
    GATE_MAX_INTERVAL_CAP:   "#ffdd00",
    GATE_ALLOWED:            "#39ff14",
    GATE_SUSPENSION:         "#ff0055",
}


# ── Core dataclass ────────────────────────────────────────────────────────────

@dataclass
class DecisionExplanation:
    """Full explainability record for one controller-safety-pump timestep.

    Fields are grouped by pipeline stage:
      CGM context → Controller → Safety gate → Delivery → Narrative
    """
    # ── Timing ─────────────────────────────────────────────────────────────
    timestamp_min: int

    # ── CGM context ────────────────────────────────────────────────────────
    cgm_mgdl: float
    trend_arrow: str              # "↑" | "↓" | "→"
    trend_rate_mgdl_per_min: float
    """Observed rate of change in mg/dL per minute (raw 1-step delta / step)."""

    # ── 30-minute prediction ───────────────────────────────────────────────
    predicted_glucose_mgdl: float
    prediction_horizon_min: int

    # ── IOB at decision time ───────────────────────────────────────────────
    iob_u: float

    # ── Controller output ──────────────────────────────────────────────────
    recommended_units: float
    controller_reason: str

    # ── Safety gate ────────────────────────────────────────────────────────
    safety_gate: str              # one of the GATE_* constants above
    safety_reason: str            # raw reason string from SafetyDecision
    safety_status: str            # "allowed" | "blocked" | "clipped"

    # ── Pump delivery ──────────────────────────────────────────────────────
    safety_final_units: float
    delivered_units: float

    # ── Suspension state ───────────────────────────────────────────────────
    is_suspended: bool
    suspension_step: int
    """0 = not suspended; N = N-th consecutive step of an active suspension."""

    # ── Human-readable summary ─────────────────────────────────────────────
    narrative: str
    """Plain-English one-liner produced by ``ags.explainability.narrative``."""
