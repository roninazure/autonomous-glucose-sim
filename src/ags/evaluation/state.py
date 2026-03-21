from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TimestepRecord:
    timestamp_min: int
    true_glucose_mgdl: float
    cgm_glucose_mgdl: float
    recommended_units: float
    safety_status: str
    safety_final_units: float
    pump_delivered_units: float
    insulin_on_board_u: float = 0.0


@dataclass
class RunSummary:
    total_timesteps: int
    time_in_range_steps: int
    time_above_range_steps: int
    time_below_range_steps: int
    time_above_250_steps: int
    percent_time_in_range: float
    average_cgm_glucose_mgdl: float
    peak_cgm_glucose_mgdl: float
    glucose_variability_sd_mgdl: float
    total_recommended_insulin_u: float
    total_insulin_delivered_u: float
    blocked_decisions: int
    clipped_decisions: int
    allowed_decisions: int
