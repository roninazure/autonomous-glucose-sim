"""Plain-English narrative generator for per-step controller decisions.

``build_narrative`` takes a ``DecisionExplanation`` and returns a single
sentence that summarises what happened at that timestep in terms a clinician
can understand without reading source code.

Design goals:
  - Always mention current CGM, trend, and predicted glucose.
  - Name the specific safety gate that fired, not just "blocked".
  - Convey the quantitative reason (threshold values where relevant).
  - Stay under ~160 characters so it fits comfortably in a dashboard cell.
"""
from __future__ import annotations

from ags.explainability.state import (
    GATE_ALLOWED,
    GATE_HYPO_GUARD,
    GATE_IOB_GUARD,
    GATE_MAX_INTERVAL_CAP,
    GATE_NO_DOSE,
    GATE_SUSPENSION,
    GATE_TREND_CONFIRMATION,
    DecisionExplanation,
)


def build_narrative(exp: DecisionExplanation) -> str:
    """Return a plain-English one-liner describing this timestep's decision."""
    cgm    = f"{exp.cgm_mgdl:.0f}"
    pred   = f"{exp.predicted_glucose_mgdl:.0f}"
    rate   = exp.trend_rate_mgdl_per_min
    iob    = exp.iob_u
    rec    = exp.recommended_units
    deliv  = exp.delivered_units
    arrow  = exp.trend_arrow
    hr     = exp.prediction_horizon_min

    gate = exp.safety_gate

    # ── No dose because controller said 0 ─────────────────────────────────
    if gate == GATE_NO_DOSE:
        if "at or below target" in exp.controller_reason:
            return (
                f"CGM {cgm} mg/dL ({arrow} {rate:+.1f}/min) → "
                f"pred {pred} mg/dL at t+{hr} — "
                f"no correction needed (glucose ≤ target)."
            )
        return (
            f"CGM {cgm} mg/dL ({arrow} {rate:+.1f}/min) → "
            f"pred {pred} mg/dL at t+{hr} — "
            f"no correction: {exp.controller_reason}."
        )

    # ── Trend unconfirmed ──────────────────────────────────────────────────
    if gate == GATE_TREND_CONFIRMATION:
        return (
            f"CGM {cgm} mg/dL ({arrow} {rate:+.1f}/min), "
            f"rec {rec:.2f} U — BLOCKED: rising trend not yet confirmed "
            f"(single-step rise, awaiting continuation)."
        )

    # ── Hypo guard ─────────────────────────────────────────────────────────
    if gate == GATE_HYPO_GUARD:
        return (
            f"CGM {cgm} mg/dL ({arrow} {rate:+.1f}/min) → "
            f"pred {pred} mg/dL at t+{hr} — "
            f"BLOCKED by hypo guard (predicted glucose below safety threshold)."
        )

    # ── Active hypo suspension ─────────────────────────────────────────────
    if gate == GATE_SUSPENSION:
        step_n = exp.suspension_step
        return (
            f"CGM {cgm} mg/dL ({arrow} {rate:+.1f}/min) → "
            f"pred {pred} mg/dL — "
            f"SUSPENSION step {step_n}: no delivery until "
            f"predicted glucose recovers and trend is confirmed rising."
        )

    # ── IOB guard ──────────────────────────────────────────────────────────
    if gate == GATE_IOB_GUARD:
        return (
            f"CGM {cgm} mg/dL ({arrow} {rate:+.1f}/min), "
            f"IOB {iob:.2f} U — "
            f"BLOCKED by IOB guard: active insulin too high to safely stack."
        )

    # ── Clipped by max-interval cap ────────────────────────────────────────
    if gate == GATE_MAX_INTERVAL_CAP:
        return (
            f"CGM {cgm} mg/dL ({arrow} {rate:+.1f}/min) → "
            f"pred {pred} mg/dL at t+{hr} — "
            f"rec {rec:.2f} U clipped to {deliv:.2f} U (max-interval safety cap)."
        )

    # ── Allowed ────────────────────────────────────────────────────────────
    if gate == GATE_ALLOWED:
        if deliv > 0:
            return (
                f"CGM {cgm} mg/dL ({arrow} {rate:+.1f}/min) → "
                f"pred {pred} mg/dL at t+{hr} — "
                f"delivered {deliv:.2f} U (full recommendation: {rec:.2f} U)."
            )
        return (
            f"CGM {cgm} mg/dL ({arrow} {rate:+.1f}/min) → "
            f"pred {pred} mg/dL at t+{hr} — "
            f"recommendation allowed but pump delivered 0 U."
        )

    # ── Fallback ───────────────────────────────────────────────────────────
    return (
        f"CGM {cgm} mg/dL → pred {pred} mg/dL at t+{hr} | "
        f"rec {rec:.2f} U → {deliv:.2f} U delivered ({exp.safety_status})."
    )
