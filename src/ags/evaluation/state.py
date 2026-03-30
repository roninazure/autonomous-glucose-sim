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
    is_suspended: bool = False
    # Extended tail from a dual-wave bolus delivered this step (0 if not active)
    dual_wave_extended_units: float = 0.0
    # Observed rate of rise at this timestep in mg/dL/min
    rate_mgdl_per_min: float = 0.0
    # Autonomous glucose dynamics classification
    meal_detected: bool = False
    meal_phase: str = "none"
    meal_estimated_carbs_g: float = 0.0
    meal_confidence: float = 0.0
    basal_drift_detected: bool = False
    basal_drift_type: str = "none"
    basal_drift_rate_mgdl_per_min: float = 0.0
    basal_drift_linearity: float = 0.0
    glucose_cause: str = "flat"       # GlucoseCause enum value
    # SWARM arming gate phase at this timestep ("idle" | "rising" | "aggressive" | "hold")
    arming_phase: str = "idle"
    # Rolling delivery sums used by the interval caps — recorded so that the
    # annotator can reproduce safety decisions without re-tracking delivery history.
    delivered_last_30min_u: float = 0.0
    delivered_last_2hr_u: float = 0.0
    # Human-readable reason string from the recommender — useful for debugging
    # and for tracking when the online ISF estimate is influencing decisions.
    recommendation_reason: str = ""
    # Number of observed dose→response pairs used by the online ISF learner at
    # this timestep.  Starts at 0 and grows as 60-min post-dose windows mature.
    isf_observation_count: int = 0


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
    time_suspended_steps: int = 0
