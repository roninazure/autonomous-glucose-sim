"""Tests for the per-step explainability pipeline.

Covers state helpers, narrative generation, and the annotator's ability to
faithfully reconstruct controller decisions from a list of TimestepRecords.
"""
from __future__ import annotations

import pytest

from ags.evaluation.runner import run_evaluation
from ags.explainability.annotator import annotate_run
from ags.explainability.narrative import build_narrative
from ags.explainability.state import (
    GATE_ALLOWED,
    GATE_HYPO_GUARD,
    GATE_IOB_GUARD,
    GATE_MAX_INTERVAL_CAP,
    GATE_NO_DOSE,
    GATE_SUSPENSION,
    GATE_TREND_CONFIRMATION,
    GATE_COLOURS,
    GATE_LABELS,
    DecisionExplanation,
    gate_from_reason,
)
from ags.retrospective.loader import CgmReading
from ags.retrospective.reference_traces import DAWN_RISE, NOCTURNAL_HYPO, POSTPRANDIAL_SPIKE
from ags.retrospective.runner import RetrospectiveConfig, run_retrospective
from ags.safety.state import SafetyThresholds
from ags.simulation.scenarios import baseline_meal_scenario


# ── gate_from_reason ─────────────────────────────────────────────────────────

class TestGateFromReason:
    def test_no_dose(self):
        assert gate_from_reason("no positive recommendation to deliver", False) == GATE_NO_DOSE

    def test_trend_confirmation(self):
        assert gate_from_reason("trend not confirmed for dosing", False) == GATE_TREND_CONFIRMATION

    def test_hypo_guard(self):
        assert gate_from_reason("predicted glucose below safety threshold", False) == GATE_HYPO_GUARD

    def test_iob_guard(self):
        assert gate_from_reason("insulin on board exceeds safety threshold", False) == GATE_IOB_GUARD

    def test_max_interval_cap(self):
        assert gate_from_reason("recommendation clipped to max units per interval", False) == GATE_MAX_INTERVAL_CAP

    def test_allowed(self):
        assert gate_from_reason("recommendation allowed", False) == GATE_ALLOWED

    def test_suspension_flag_overrides(self):
        """If is_suspended=True the gate must be SUSPENSION regardless of reason."""
        assert gate_from_reason("recommendation allowed", True) == GATE_SUSPENSION

    def test_suspension_via_reason(self):
        assert gate_from_reason("hypo suspension active — step 3", False) == GATE_SUSPENSION


class TestGateMetadata:
    def test_all_gates_have_labels(self):
        gates = [GATE_NO_DOSE, GATE_TREND_CONFIRMATION, GATE_HYPO_GUARD,
                 GATE_IOB_GUARD, GATE_MAX_INTERVAL_CAP, GATE_ALLOWED, GATE_SUSPENSION]
        for g in gates:
            assert g in GATE_LABELS, f"Missing label for gate {g!r}"

    def test_all_gates_have_colours(self):
        gates = [GATE_NO_DOSE, GATE_TREND_CONFIRMATION, GATE_HYPO_GUARD,
                 GATE_IOB_GUARD, GATE_MAX_INTERVAL_CAP, GATE_ALLOWED, GATE_SUSPENSION]
        for g in gates:
            assert g in GATE_COLOURS, f"Missing colour for gate {g!r}"
            assert GATE_COLOURS[g].startswith("#"), f"Colour for {g!r} must be a hex string"


# ── narrative ─────────────────────────────────────────────────────────────────

def _make_exp(**overrides) -> DecisionExplanation:
    defaults = dict(
        timestamp_min=10,
        cgm_mgdl=140.0,
        trend_arrow="↑",
        trend_rate_mgdl_per_min=1.2,
        predicted_glucose_mgdl=176.0,
        prediction_horizon_min=30,
        iob_u=0.1,
        recommended_units=0.52,
        controller_reason="predicted glucose above target",
        safety_gate=GATE_ALLOWED,
        safety_reason="recommendation allowed",
        safety_status="allowed",
        safety_final_units=0.52,
        delivered_units=0.52,
        is_suspended=False,
        suspension_step=0,
        narrative="",
    )
    defaults.update(overrides)
    return DecisionExplanation(**defaults)


class TestBuildNarrative:
    def test_allowed_mentions_cgm(self):
        exp = _make_exp(safety_gate=GATE_ALLOWED)
        n = build_narrative(exp)
        assert "140" in n

    def test_allowed_mentions_delivered(self):
        exp = _make_exp(safety_gate=GATE_ALLOWED, delivered_units=0.52)
        n = build_narrative(exp)
        assert "0.52" in n

    def test_no_dose_mentions_target(self):
        exp = _make_exp(
            safety_gate=GATE_NO_DOSE,
            controller_reason="predicted glucose at or below target",
            recommended_units=0.0,
            delivered_units=0.0,
        )
        n = build_narrative(exp)
        assert "target" in n.lower()

    def test_hypo_guard_mentions_blocked(self):
        exp = _make_exp(
            safety_gate=GATE_HYPO_GUARD,
            cgm_mgdl=62.0,
            trend_arrow="↓",
            trend_rate_mgdl_per_min=-0.8,
            predicted_glucose_mgdl=50.0,
            delivered_units=0.0,
        )
        n = build_narrative(exp)
        assert "BLOCKED" in n

    def test_suspension_mentions_step(self):
        exp = _make_exp(
            safety_gate=GATE_SUSPENSION,
            is_suspended=True,
            suspension_step=3,
            delivered_units=0.0,
        )
        n = build_narrative(exp)
        assert "SUSPENSION" in n
        assert "3" in n

    def test_clipped_mentions_cap(self):
        exp = _make_exp(
            safety_gate=GATE_MAX_INTERVAL_CAP,
            recommended_units=1.5,
            safety_final_units=1.0,
            delivered_units=1.0,
        )
        n = build_narrative(exp)
        assert "clipped" in n.lower() or "cap" in n.lower()

    def test_iob_guard_mentions_iob(self):
        exp = _make_exp(
            safety_gate=GATE_IOB_GUARD,
            iob_u=3.2,
            delivered_units=0.0,
        )
        n = build_narrative(exp)
        assert "IOB" in n or "insulin on board" in n.lower()

    def test_trend_unconfirmed_narrative(self):
        exp = _make_exp(
            safety_gate=GATE_TREND_CONFIRMATION,
            delivered_units=0.0,
        )
        n = build_narrative(exp)
        assert "BLOCKED" in n or "not" in n.lower()

    def test_narrative_is_nonempty(self):
        for gate in [GATE_NO_DOSE, GATE_TREND_CONFIRMATION, GATE_HYPO_GUARD,
                     GATE_IOB_GUARD, GATE_MAX_INTERVAL_CAP, GATE_ALLOWED, GATE_SUSPENSION]:
            exp = _make_exp(safety_gate=gate)
            n = build_narrative(exp)
            assert len(n) > 20, f"Narrative too short for gate {gate!r}: {n!r}"


# ── annotator ─────────────────────────────────────────────────────────────────

class TestAnnotateRun:
    def test_returns_one_per_record(self):
        records, _ = run_retrospective(readings=DAWN_RISE)
        exps = annotate_run(records, seed_glucose_mgdl=DAWN_RISE[0].glucose_mgdl)
        assert len(exps) == len(records)

    def test_timestamps_match_records(self):
        records, _ = run_retrospective(readings=DAWN_RISE)
        exps = annotate_run(records, seed_glucose_mgdl=DAWN_RISE[0].glucose_mgdl)
        for r, e in zip(records, exps):
            assert e.timestamp_min == r.timestamp_min

    def test_cgm_matches_records(self):
        records, _ = run_retrospective(readings=POSTPRANDIAL_SPIKE)
        exps = annotate_run(records, seed_glucose_mgdl=POSTPRANDIAL_SPIKE[0].glucose_mgdl)
        for r, e in zip(records, exps):
            assert e.cgm_mgdl == r.cgm_glucose_mgdl

    def test_empty_records_returns_empty(self):
        exps = annotate_run([])
        assert exps == []

    def test_narrative_nonempty_for_all_steps(self):
        records, _ = run_retrospective(readings=DAWN_RISE)
        exps = annotate_run(records, seed_glucose_mgdl=DAWN_RISE[0].glucose_mgdl)
        for e in exps:
            assert e.narrative, f"Empty narrative at t={e.timestamp_min}"

    def test_trend_arrows_are_valid(self):
        records, _ = run_retrospective(readings=POSTPRANDIAL_SPIKE)
        exps = annotate_run(records, seed_glucose_mgdl=POSTPRANDIAL_SPIKE[0].glucose_mgdl)
        for e in exps:
            assert e.trend_arrow in ("↑", "↓", "→"), f"Invalid arrow: {e.trend_arrow!r}"

    def test_safety_gate_is_valid(self):
        valid_gates = {
            GATE_NO_DOSE, GATE_TREND_CONFIRMATION, GATE_HYPO_GUARD,
            GATE_IOB_GUARD, GATE_MAX_INTERVAL_CAP, GATE_ALLOWED, GATE_SUSPENSION,
        }
        records, _ = run_retrospective(readings=POSTPRANDIAL_SPIKE)
        exps = annotate_run(records, seed_glucose_mgdl=POSTPRANDIAL_SPIKE[0].glucose_mgdl)
        for e in exps:
            assert e.safety_gate in valid_gates, f"Unknown gate: {e.safety_gate!r}"

    def test_iob_never_negative(self):
        records, _ = run_retrospective(readings=POSTPRANDIAL_SPIKE)
        exps = annotate_run(records, seed_glucose_mgdl=POSTPRANDIAL_SPIKE[0].glucose_mgdl)
        for e in exps:
            assert e.iob_u >= 0.0

    def test_delivery_matches_records(self):
        records, _ = run_retrospective(readings=DAWN_RISE)
        exps = annotate_run(records, seed_glucose_mgdl=DAWN_RISE[0].glucose_mgdl)
        for r, e in zip(records, exps):
            assert e.delivered_units == r.pump_delivered_units

    def test_safety_status_matches_records(self):
        records, _ = run_retrospective(readings=DAWN_RISE)
        exps = annotate_run(records, seed_glucose_mgdl=DAWN_RISE[0].glucose_mgdl, swarm_bolus=True)
        for r, e in zip(records, exps):
            assert e.safety_status == r.safety_status

    def test_rising_trend_on_postprandial_early_phase(self):
        """First half of the spike should produce rising (↑) trend arrows."""
        records, _ = run_retrospective(readings=POSTPRANDIAL_SPIKE)
        exps = annotate_run(records, seed_glucose_mgdl=POSTPRANDIAL_SPIKE[0].glucose_mgdl)
        # Steps between t=10 and t=60 should predominantly show ↑
        rising = [e for e in exps if e.timestamp_min <= 60 and e.timestamp_min >= 10]
        up_count = sum(1 for e in rising if e.trend_arrow == "↑")
        assert up_count >= len(rising) // 2

    def test_falling_rate_on_nocturnal_hypo(self):
        """First half of hypo trace should have negative trend rates.
        The hypo trace drops ~0.5 mg/dL/min — below the ↓ arrow threshold
        (5 mg/dL/step = 1.0/min), so arrows are → but rates are negative."""
        records, _ = run_retrospective(readings=NOCTURNAL_HYPO)
        exps = annotate_run(records, seed_glucose_mgdl=NOCTURNAL_HYPO[0].glucose_mgdl)
        early = [e for e in exps if e.timestamp_min <= 55]
        neg_count = sum(1 for e in early if e.trend_rate_mgdl_per_min < 0)
        assert neg_count >= len(early) // 2

    def test_reconstruction_matches_original_run(self):
        """Annotator decisions should match the actual records' safety_status."""
        records, _ = run_evaluation(
            simulation_inputs=baseline_meal_scenario(),
            duration_minutes=60,
        )
        # Use the first record's CGM as seed so the annotator's arming gate
        # starts with the same delta as the runner (avoids a wrong large
        # negative delta that would incorrectly trigger HOLD).
        exps = annotate_run(records, seed_glucose_mgdl=records[0].cgm_glucose_mgdl)
        for r, e in zip(records, exps):
            assert e.safety_status == r.safety_status, (
                f"t={r.timestamp_min}: original={r.safety_status!r}, "
                f"annotated={e.safety_status!r}"
            )


# ── integration: annotation + narrative coverage ──────────────────────────────

class TestAnnotatorNarrativeCoverage:
    """Ensure that every safety gate produced by real runs generates a valid narrative."""

    def _collect_gates(self, trace, seed_glucose):
        records, _ = run_retrospective(readings=trace)
        return annotate_run(records, seed_glucose_mgdl=seed_glucose)

    def test_postprandial_spike_narratives(self):
        exps = self._collect_gates(POSTPRANDIAL_SPIKE, POSTPRANDIAL_SPIKE[0].glucose_mgdl)
        for e in exps:
            assert len(e.narrative) > 10

    def test_nocturnal_hypo_narratives(self):
        exps = self._collect_gates(NOCTURNAL_HYPO, NOCTURNAL_HYPO[0].glucose_mgdl)
        for e in exps:
            assert len(e.narrative) > 10

    def test_dawn_rise_narratives(self):
        exps = self._collect_gates(DAWN_RISE, DAWN_RISE[0].glucose_mgdl)
        for e in exps:
            assert len(e.narrative) > 10

    def test_suspension_step_increments(self):
        """On nocturnal hypo with aggressive threshold, if suspension fires the
        step counter should increase each step."""
        records, _ = run_retrospective(
            readings=NOCTURNAL_HYPO,
            safety_thresholds=SafetyThresholds(
                min_predicted_glucose_mgdl=100.0,  # very aggressive → likely suspension
            ),
        )
        exps = annotate_run(
            records,
            seed_glucose_mgdl=NOCTURNAL_HYPO[0].glucose_mgdl,
            safety_thresholds=SafetyThresholds(min_predicted_glucose_mgdl=100.0),
        )
        susp_steps = [e.suspension_step for e in exps if e.is_suspended]
        if susp_steps:
            # Steps should increment while suspended
            assert max(susp_steps) > 1
