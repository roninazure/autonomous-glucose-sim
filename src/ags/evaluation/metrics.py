from __future__ import annotations

from ags.evaluation.state import RunSummary, TimestepRecord


def summarize_run(records: list[TimestepRecord]) -> RunSummary:
    time_in_range_steps = sum(1 for r in records if 70.0 <= r.cgm_glucose_mgdl <= 180.0)
    time_above_range_steps = sum(1 for r in records if r.cgm_glucose_mgdl > 180.0)
    time_below_range_steps = sum(1 for r in records if r.cgm_glucose_mgdl < 70.0)

    total_insulin_delivered_u = round(sum(r.pump_delivered_units for r in records), 4)

    blocked_decisions = sum(1 for r in records if r.safety_status == "blocked")
    clipped_decisions = sum(1 for r in records if r.safety_status == "clipped")
    allowed_decisions = sum(1 for r in records if r.safety_status == "allowed")

    return RunSummary(
        total_timesteps=len(records),
        time_in_range_steps=time_in_range_steps,
        time_above_range_steps=time_above_range_steps,
        time_below_range_steps=time_below_range_steps,
        total_insulin_delivered_u=total_insulin_delivered_u,
        blocked_decisions=blocked_decisions,
        clipped_decisions=clipped_decisions,
        allowed_decisions=allowed_decisions,
    )
