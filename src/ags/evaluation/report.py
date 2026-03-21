"""Validation report generator.

Produces a structured, JSON-serialisable audit record for a completed
simulation run.  Each report includes all parameters used, full clinical
metrics, and an explicit pass/fail verdict against published ADA/EASD targets.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ags.evaluation.state import RunSummary
from ags.pump.state import PumpConfig
from ags.safety.state import SafetyThresholds

# ── Published ADA/EASD clinical targets ──────────────────────────────────────
_TIR_TARGET_PCT = 70.0        # time-in-range ≥ 70 %
_PEAK_TARGET_MGDL = 250.0     # peak CGM < 250 mg/dL (no severe hyper)
_SD_TARGET_MGDL = 36.0        # glucose variability SD < 36 mg/dL
_HYPO_TARGET_STEPS = 0        # zero steps below 70 mg/dL


def generate_report(
    scenario_name: str,
    summary: RunSummary,
    duration_minutes: int,
    step_minutes: int,
    safety_thresholds: SafetyThresholds,
    pump_config: PumpConfig,
    target_glucose_mgdl: float = 110.0,
    correction_factor_mgdl_per_unit: float = 50.0,
    min_excursion_delta_mgdl: float = 0.0,
    microbolus_fraction: float = 1.0,
) -> dict:
    """Return a JSON-serialisable validation report dict.

    Pass/fail verdicts are evaluated against ADA/EASD targets.
    ``overall_pass`` requires TIR, peak, and hypo targets all met.
    """
    tir_pass = summary.percent_time_in_range >= _TIR_TARGET_PCT
    peak_pass = summary.peak_cgm_glucose_mgdl < _PEAK_TARGET_MGDL
    hypo_pass = summary.time_below_range_steps == _HYPO_TARGET_STEPS
    sd_pass = summary.glucose_variability_sd_mgdl < _SD_TARGET_MGDL
    overall_pass = tir_pass and peak_pass and hypo_pass

    return {
        "report_version": "1.0",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scenario": scenario_name,
        "simulation_params": {
            "duration_minutes": duration_minutes,
            "step_minutes": step_minutes,
            "target_glucose_mgdl": target_glucose_mgdl,
            "correction_factor_mgdl_per_unit": correction_factor_mgdl_per_unit,
            "min_excursion_delta_mgdl": min_excursion_delta_mgdl,
            "microbolus_fraction": microbolus_fraction,
        },
        "safety_config": {
            "max_units_per_interval": safety_thresholds.max_units_per_interval,
            "max_iob_u": safety_thresholds.max_insulin_on_board_u,
            "min_predicted_glucose_mgdl": safety_thresholds.min_predicted_glucose_mgdl,
            "require_confirmed_trend": safety_thresholds.require_confirmed_trend,
            "hypo_resume_margin_mgdl": safety_thresholds.hypo_resume_margin_mgdl,
        },
        "pump_config": {
            "dose_increment_u": pump_config.dose_increment_u,
            "max_units_per_interval": pump_config.max_units_per_interval,
        },
        "metrics": {
            "total_timesteps": summary.total_timesteps,
            "time_in_range_pct": summary.percent_time_in_range,
            "average_cgm_mgdl": summary.average_cgm_glucose_mgdl,
            "peak_cgm_mgdl": summary.peak_cgm_glucose_mgdl,
            "glucose_sd_mgdl": summary.glucose_variability_sd_mgdl,
            "time_above_180_steps": summary.time_above_range_steps,
            "time_above_250_steps": summary.time_above_250_steps,
            "time_below_70_steps": summary.time_below_range_steps,
            "time_suspended_steps": summary.time_suspended_steps,
            "total_insulin_recommended_u": summary.total_recommended_insulin_u,
            "total_insulin_delivered_u": summary.total_insulin_delivered_u,
            "blocked_decisions": summary.blocked_decisions,
            "clipped_decisions": summary.clipped_decisions,
            "allowed_decisions": summary.allowed_decisions,
        },
        "verdicts": {
            "tir_pass": tir_pass,
            "peak_pass": peak_pass,
            "hypo_pass": hypo_pass,
            "variability_pass": sd_pass,
            "overall_pass": overall_pass,
        },
        "targets": {
            "tir": f">= {_TIR_TARGET_PCT}%",
            "peak": f"< {_PEAK_TARGET_MGDL} mg/dL",
            "hypo": f"{_HYPO_TARGET_STEPS} steps below 70 mg/dL",
            "glucose_sd": f"< {_SD_TARGET_MGDL} mg/dL",
        },
        "standard": "ADA/EASD Time-in-Range targets (Battelino et al. 2019)",
    }
