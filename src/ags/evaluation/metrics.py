from __future__ import annotations

import math

from ags.evaluation.state import RunSummary, TimestepRecord


def summarize_run(records: list[TimestepRecord]) -> RunSummary:
    total_timesteps = len(records)

    time_in_range_steps = sum(1 for r in records if 70.0 <= r.cgm_glucose_mgdl <= 180.0)
    time_above_range_steps = sum(1 for r in records if r.cgm_glucose_mgdl > 180.0)
    time_below_range_steps = sum(1 for r in records if r.cgm_glucose_mgdl < 70.0)
    time_above_250_steps = sum(1 for r in records if r.cgm_glucose_mgdl > 250.0)

    percent_time_in_range = round(
        (time_in_range_steps / total_timesteps) * 100.0, 2
    ) if total_timesteps else 0.0

    average_cgm_glucose_mgdl = round(
        sum(r.cgm_glucose_mgdl for r in records) / total_timesteps, 2
    ) if total_timesteps else 0.0

    peak_cgm_glucose_mgdl = round(
        max((r.cgm_glucose_mgdl for r in records), default=0.0), 2
    )

    if total_timesteps:
        mean = sum(r.cgm_glucose_mgdl for r in records) / total_timesteps
        variance = sum((r.cgm_glucose_mgdl - mean) ** 2 for r in records) / total_timesteps
        glucose_variability_sd_mgdl = round(math.sqrt(variance), 2)
    else:
        glucose_variability_sd_mgdl = 0.0

    total_recommended_insulin_u = round(
        sum(r.recommended_units for r in records), 4
    )
    total_insulin_delivered_u = round(
        sum(r.pump_delivered_units for r in records), 4
    )

    blocked_decisions = sum(1 for r in records if r.safety_status == "blocked")
    clipped_decisions = sum(1 for r in records if r.safety_status == "clipped")
    allowed_decisions = sum(1 for r in records if r.safety_status == "allowed")

    return RunSummary(
        total_timesteps=total_timesteps,
        time_in_range_steps=time_in_range_steps,
        time_above_range_steps=time_above_range_steps,
        time_below_range_steps=time_below_range_steps,
        time_above_250_steps=time_above_250_steps,
        percent_time_in_range=percent_time_in_range,
        average_cgm_glucose_mgdl=average_cgm_glucose_mgdl,
        peak_cgm_glucose_mgdl=peak_cgm_glucose_mgdl,
        glucose_variability_sd_mgdl=glucose_variability_sd_mgdl,
        total_recommended_insulin_u=total_recommended_insulin_u,
        total_insulin_delivered_u=total_insulin_delivered_u,
        blocked_decisions=blocked_decisions,
        clipped_decisions=clipped_decisions,
        allowed_decisions=allowed_decisions,
    )
