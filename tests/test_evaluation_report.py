"""Tests for the validation report generator."""
from __future__ import annotations

from ags.evaluation.report import generate_report
from ags.evaluation.state import RunSummary
from ags.pump.state import PumpConfig
from ags.safety.state import SafetyThresholds


def _summary(
    tir_pct: float = 80.0,
    peak: float = 220.0,
    below_70: int = 0,
    sd: float = 25.0,
) -> RunSummary:
    return RunSummary(
        total_timesteps=36,
        time_in_range_steps=int(36 * tir_pct / 100),
        time_above_range_steps=36 - int(36 * tir_pct / 100),
        time_below_range_steps=below_70,
        time_above_250_steps=0,
        percent_time_in_range=tir_pct,
        average_cgm_glucose_mgdl=130.0,
        peak_cgm_glucose_mgdl=peak,
        glucose_variability_sd_mgdl=sd,
        total_recommended_insulin_u=2.0,
        total_insulin_delivered_u=1.8,
        blocked_decisions=3,
        clipped_decisions=1,
        allowed_decisions=32,
        time_suspended_steps=2,
    )


def _make_report(**kwargs) -> dict:
    return generate_report(
        scenario_name="Baseline Meal",
        summary=_summary(**kwargs),
        duration_minutes=180,
        step_minutes=5,
        safety_thresholds=SafetyThresholds(),
        pump_config=PumpConfig(),
    )


# ── Structure ─────────────────────────────────────────────────────────────────

def test_report_has_required_top_level_keys():
    report = _make_report()
    for key in ("report_version", "generated_at", "scenario", "simulation_params",
                "safety_config", "pump_config", "metrics", "verdicts", "targets", "standard"):
        assert key in report, f"missing key: {key}"


def test_report_scenario_name():
    report = _make_report()
    assert report["scenario"] == "Baseline Meal"


def test_report_metrics_include_suspended_steps():
    report = _make_report()
    assert "time_suspended_steps" in report["metrics"]
    assert report["metrics"]["time_suspended_steps"] == 2


def test_report_metrics_match_summary():
    report = _make_report(tir_pct=80.0, peak=220.0)
    assert report["metrics"]["time_in_range_pct"] == 80.0
    assert report["metrics"]["peak_cgm_mgdl"] == 220.0


# ── Verdicts ──────────────────────────────────────────────────────────────────

def test_overall_pass_when_all_targets_met():
    report = _make_report(tir_pct=75.0, peak=200.0, below_70=0, sd=30.0)
    assert report["verdicts"]["tir_pass"]
    assert report["verdicts"]["peak_pass"]
    assert report["verdicts"]["hypo_pass"]
    assert report["verdicts"]["overall_pass"]


def test_overall_fail_when_tir_low():
    report = _make_report(tir_pct=60.0, peak=200.0, below_70=0)
    assert not report["verdicts"]["tir_pass"]
    assert not report["verdicts"]["overall_pass"]


def test_overall_fail_when_hypo_present():
    report = _make_report(tir_pct=75.0, peak=200.0, below_70=2)
    assert not report["verdicts"]["hypo_pass"]
    assert not report["verdicts"]["overall_pass"]


def test_overall_fail_when_peak_too_high():
    report = _make_report(tir_pct=75.0, peak=260.0, below_70=0)
    assert not report["verdicts"]["peak_pass"]
    assert not report["verdicts"]["overall_pass"]


def test_variability_pass_independent_of_overall():
    """SD can fail without failing overall_pass (advisory, not hard gate)."""
    report = _make_report(tir_pct=75.0, peak=200.0, below_70=0, sd=40.0)
    assert not report["verdicts"]["variability_pass"]
    assert report["verdicts"]["overall_pass"]  # overall still passes


# ── Safety and pump config serialised ────────────────────────────────────────

def test_safety_config_in_report():
    report = _make_report()
    sc = report["safety_config"]
    assert "max_units_per_interval" in sc
    assert "max_iob_u" in sc
    assert "min_predicted_glucose_mgdl" in sc
    assert "hypo_resume_margin_mgdl" in sc


def test_pump_config_in_report():
    report = _make_report()
    assert "dose_increment_u" in report["pump_config"]
    assert "max_units_per_interval" in report["pump_config"]


# ── JSON serialisable ─────────────────────────────────────────────────────────

def test_report_is_json_serialisable():
    import json
    report = _make_report()
    serialised = json.dumps(report)
    restored = json.loads(serialised)
    assert restored["verdicts"]["overall_pass"] == report["verdicts"]["overall_pass"]
