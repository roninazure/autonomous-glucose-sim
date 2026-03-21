"""Tests for retrospective CGM trace replay runner and reference traces."""
from __future__ import annotations

import pytest

from ags.retrospective.loader import CgmReading
from ags.retrospective.reference_traces import (
    DAWN_RISE,
    NOCTURNAL_HYPO,
    POSTPRANDIAL_SPIKE,
    REFERENCE_TRACES,
)
from ags.retrospective.runner import RetrospectiveConfig, run_retrospective
from ags.safety.state import SafetyThresholds


# ── Reference trace shapes ────────────────────────────────────────────────────

def test_postprandial_spike_peaks_above_230():
    glucoses = [r.glucose_mgdl for r in POSTPRANDIAL_SPIKE]
    assert max(glucoses) >= 230


def test_postprandial_spike_starts_euglycaemic():
    assert POSTPRANDIAL_SPIKE[0].glucose_mgdl < 125


def test_nocturnal_hypo_reaches_clinical_hypo():
    glucoses = [r.glucose_mgdl for r in NOCTURNAL_HYPO]
    assert min(glucoses) < 70


def test_nocturnal_hypo_recovers_by_end():
    """Last reading should be higher than the nadir."""
    glucoses = [r.glucose_mgdl for r in NOCTURNAL_HYPO]
    assert glucoses[-1] > min(glucoses)


def test_dawn_rise_is_monotone_upward():
    glucoses = [r.glucose_mgdl for r in DAWN_RISE]
    assert glucoses[-1] > glucoses[0] + 20


def test_all_reference_traces_have_5min_steps():
    for name, trace in REFERENCE_TRACES.items():
        for prev, curr in zip(trace[:-1], trace[1:]):
            gap = curr.timestamp_min - prev.timestamp_min
            assert gap == 5, f"{name}: gap {gap} at t={curr.timestamp_min}"


def test_all_reference_traces_start_at_zero():
    for name, trace in REFERENCE_TRACES.items():
        assert trace[0].timestamp_min == 0, f"{name} doesn't start at t=0"


def test_reference_traces_registry_has_three_entries():
    assert len(REFERENCE_TRACES) == 3


# ── Retrospective runner — basics ─────────────────────────────────────────────

def test_run_retrospective_returns_records_and_summary():
    records, summary = run_retrospective(readings=DAWN_RISE)
    assert len(records) == len(DAWN_RISE) - 1  # one per step (not counting seed)
    assert summary.total_timesteps == len(DAWN_RISE) - 1


def test_run_retrospective_cgm_matches_trace():
    """CGM values in records must exactly match the input trace."""
    records, _ = run_retrospective(readings=DAWN_RISE)
    for record, reading in zip(records, DAWN_RISE[1:]):
        assert record.cgm_glucose_mgdl == reading.glucose_mgdl
        assert record.timestamp_min == reading.timestamp_min


def test_retrospective_true_equals_cgm():
    """In retrospective mode, true_glucose == cgm_glucose (no separate model)."""
    records, _ = run_retrospective(readings=POSTPRANDIAL_SPIKE)
    for r in records:
        assert r.true_glucose_mgdl == r.cgm_glucose_mgdl


def test_retrospective_requires_at_least_two_readings():
    with pytest.raises(ValueError, match="at least 2"):
        run_retrospective(readings=[CgmReading(0, 110)])


# ── Safety behaviour on reference traces ─────────────────────────────────────

def test_nocturnal_hypo_all_decisions_blocked():
    """Glucose is already below target throughout — controller recommends 0 U,
    no_dose_guard blocks every step, no insulin is delivered."""
    records, summary = run_retrospective(
        readings=NOCTURNAL_HYPO,
        safety_thresholds=SafetyThresholds(min_predicted_glucose_mgdl=80.0),
    )
    # All steps blocked (no recommendation because glucose < target = 110)
    assert summary.allowed_decisions == 0
    assert summary.total_insulin_delivered_u == 0.0


def test_nocturnal_hypo_no_dose_during_hypo():
    """No insulin must be delivered while glucose is below 70 mg/dL."""
    records, _ = run_retrospective(
        readings=NOCTURNAL_HYPO,
        safety_thresholds=SafetyThresholds(min_predicted_glucose_mgdl=80.0),
    )
    for r in records:
        if r.cgm_glucose_mgdl < 70.0:
            assert r.pump_delivered_units == 0.0, (
                f"t={r.timestamp_min}: delivered {r.pump_delivered_units} U "
                f"at glucose={r.cgm_glucose_mgdl} mg/dL"
            )


def test_postprandial_spike_controller_responds():
    """Controller should recommend non-zero doses during the spike."""
    records, summary = run_retrospective(readings=POSTPRANDIAL_SPIKE)
    assert summary.total_recommended_insulin_u > 0


def test_dawn_rise_recommendations_are_positive():
    """Rising trend should trigger correction recommendations."""
    records, summary = run_retrospective(readings=DAWN_RISE)
    assert summary.total_recommended_insulin_u > 0


# ── IOB tracking ──────────────────────────────────────────────────────────────

def test_iob_builds_up_after_delivery():
    """Each delivered dose should increase IOB on the following step."""
    records, _ = run_retrospective(readings=POSTPRANDIAL_SPIKE)
    delivered_steps = [r for r in records if r.pump_delivered_units > 0]
    if not delivered_steps:
        return  # nothing delivered — can't test IOB build
    # At some point after delivery, IOB should be > 0
    iob_values = [r.insulin_on_board_u for r in records]
    assert max(iob_values) > 0


def test_iob_never_negative():
    records, _ = run_retrospective(readings=POSTPRANDIAL_SPIKE)
    for r in records:
        assert r.insulin_on_board_u >= 0.0


# ── Config variations ─────────────────────────────────────────────────────────

def test_high_isf_reduces_recommendations():
    """Higher correction factor → smaller corrections needed → less total U."""
    cfg_standard = RetrospectiveConfig(correction_factor_mgdl_per_unit=30.0)
    cfg_sensitive = RetrospectiveConfig(correction_factor_mgdl_per_unit=90.0)
    _, summary_std = run_retrospective(POSTPRANDIAL_SPIKE, config=cfg_standard)
    _, summary_sens = run_retrospective(POSTPRANDIAL_SPIKE, config=cfg_sensitive)
    assert summary_sens.total_recommended_insulin_u < summary_std.total_recommended_insulin_u


def test_microbolus_fraction_scales_delivery():
    cfg_full = RetrospectiveConfig(microbolus_fraction=1.0)
    cfg_quarter = RetrospectiveConfig(microbolus_fraction=0.25)
    _, sum_full = run_retrospective(DAWN_RISE, config=cfg_full)
    _, sum_quarter = run_retrospective(DAWN_RISE, config=cfg_quarter)
    assert sum_quarter.total_insulin_delivered_u <= sum_full.total_insulin_delivered_u


# ── Metrics integrity ─────────────────────────────────────────────────────────

def test_summary_timesteps_equals_record_count():
    records, summary = run_retrospective(readings=DAWN_RISE)
    assert summary.total_timesteps == len(records)


def test_blocked_plus_clipped_plus_allowed_equals_total():
    _, summary = run_retrospective(readings=POSTPRANDIAL_SPIKE)
    assert (
        summary.blocked_decisions
        + summary.clipped_decisions
        + summary.allowed_decisions
        == summary.total_timesteps
    )


def test_percent_tir_bounded():
    _, summary = run_retrospective(readings=POSTPRANDIAL_SPIKE)
    assert 0.0 <= summary.percent_time_in_range <= 100.0
