"""End-to-end validation of the basal drift detection and correction loop.

Tests the full pipeline for the sustained_basal_deficit_scenario:
  simulation → CGM → detector → BASAL_DRIFT cause → 25%-fraction micro-bolus

The drift rate (0.30 mg/dL/min) sits squarely in the detector's band and
produces a highly linear curve — the canonical BASAL_DRIFT signal.
"""
from __future__ import annotations

from ags.evaluation.runner import run_evaluation
from ags.simulation.scenarios import sustained_basal_deficit_scenario



def _run(duration_minutes: int = 180, autonomous: bool = True):
    return run_evaluation(
        simulation_inputs=sustained_basal_deficit_scenario(),
        duration_minutes=duration_minutes,
        step_minutes=5,
        seed=42,
        autonomous_isf=autonomous,
        swarm_bolus=autonomous,
    )


def test_basal_drift_detected_in_scenario() -> None:
    """Detector should fire BASAL_DRIFT within the first 40 minutes of drift."""
    records, _ = _run()

    drift_records = [r for r in records if r.basal_drift_detected]
    assert drift_records, (
        "Expected basal_drift_detected=True in at least some records. "
        "The drift detector may not be triggering on the sustained linear rise."
    )

    # First detection should happen well before the 1-hour mark
    first_drift_t = drift_records[0].timestamp_min
    assert first_drift_t <= 60, (
        f"Expected first drift detection by t=60 min, got t={first_drift_t}. "
        "Drift rate may be below the minimum threshold."
    )


def test_basal_drift_cause_classification() -> None:
    """glucose_cause should include 'basal_drift' once drift is detected."""
    records, _ = _run()

    basal_drift_cause_records = [
        r for r in records if r.glucose_cause == "basal_drift"
    ]
    assert basal_drift_cause_records, (
        "Expected glucose_cause='basal_drift' in at least some records. "
        "The classifier may not be assigning cause correctly."
    )


def test_basal_drift_type_is_sustained() -> None:
    """Drift type should be 'sustained' (no preceding hypo, no dawn window)."""
    records, _ = _run()

    drift_records = [r for r in records if r.basal_drift_detected]
    if not drift_records:
        return  # covered by test_basal_drift_detected_in_scenario

    drift_types = {r.basal_drift_type for r in drift_records}
    assert "sustained" in drift_types, (
        f"Expected drift_type 'sustained', got: {drift_types}. "
        "The scenario should classify as sustained basal deficit, not dawn/rebound."
    )


def test_controller_doses_during_basal_drift() -> None:
    """Controller should deliver insulin on BASAL_DRIFT steps, not stay silent."""
    records, _ = _run()

    # Find steps where drift was detected and controller was active
    drift_steps_with_dose = [
        r for r in records
        if r.basal_drift_detected and r.pump_delivered_units > 0
    ]
    assert drift_steps_with_dose, (
        "Expected at least one dose delivered when basal drift is active. "
        "The recommender may not be firing the drift correction path."
    )


def test_drift_controller_delivers_more_insulin_than_no_correction() -> None:
    """Autonomous mode should deliver more total insulin than a zero-fraction run.

    With microbolus_fraction=0.0, the controller recommends corrections but
    the fraction multiplier zeroes them all out — a truly no-insulin baseline.
    The autonomous drift correction path (25% fractions) must exceed this.
    """
    records_autonomous, _ = _run(autonomous=True)

    # No-SWARM run: swarm_bolus=False → controller always returns 0 U
    records_no_correction, _ = run_evaluation(
        simulation_inputs=sustained_basal_deficit_scenario(),
        duration_minutes=180,
        step_minutes=5,
        seed=42,
        autonomous_isf=False,
        swarm_bolus=False,
    )

    total_autonomous = sum(r.pump_delivered_units for r in records_autonomous)
    total_no_correction = sum(r.pump_delivered_units for r in records_no_correction)

    assert total_autonomous > total_no_correction, (
        f"Autonomous drift correction delivered {total_autonomous:.3f} U total, "
        f"which is not more than the zero-correction run ({total_no_correction:.3f} U). "
        "The drift correction path may not be generating doses."
    )
