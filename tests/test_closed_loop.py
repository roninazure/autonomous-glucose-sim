"""Verify the closed-loop runner: delivered insulin actually changes glucose.

Before the closed-loop fix, advance_physiology always received dose_u=0.0
regardless of what the controller delivered — the glucose trajectory was
pre-computed and unaffected by any dosing decisions.

After the fix, each step's pump delivery is fed back into advance_physiology
so x1/x2 accumulate and the resulting insulin effect lowers glucose in the
next step.  This is the core artificial pancreas loop.
"""
from __future__ import annotations

from ags.evaluation.runner import run_closed_loop_evaluation
from ags.simulation.engine import run_simulation
from ags.simulation.scenarios import baseline_meal_scenario, sustained_basal_deficit_scenario


def test_closed_loop_reduces_peak_vs_no_treatment() -> None:
    """Autonomous closed-loop should produce a lower glucose peak than zero insulin."""
    scenario = baseline_meal_scenario()

    # No-treatment baseline: run_simulation delivers no insulin ever
    no_tx_snaps = run_simulation(scenario, duration_minutes=180, step_minutes=5, seed=42)
    peak_no_tx = max(s.cgm_glucose_mgdl for s in no_tx_snaps)

    records, _ = run_closed_loop_evaluation(
        simulation_inputs=scenario,
        duration_minutes=180,
        step_minutes=5,
        seed=42,
        autonomous_isf=True,
        swarm_bolus=True,
    )
    peak_closed_loop = max(r.cgm_glucose_mgdl for r in records)

    assert peak_closed_loop < peak_no_tx, (
        f"Closed-loop peak ({peak_closed_loop:.1f}) should be below no-treatment peak "
        f"({peak_no_tx:.1f}). Insulin is not reducing glucose — the loop may not be closed."
    )
    # Expect at least a 20 mg/dL reduction on a 45g meal
    assert peak_no_tx - peak_closed_loop >= 20, (
        f"Expected ≥20 mg/dL reduction, got {peak_no_tx - peak_closed_loop:.1f}. "
        "Autonomous insulin delivery may not be having enough physiological effect."
    )


def test_closed_loop_delivers_nonzero_insulin() -> None:
    """Controller must actually deliver insulin — otherwise the loop is trivially closed."""
    records, summary = run_closed_loop_evaluation(
        simulation_inputs=baseline_meal_scenario(),
        duration_minutes=180,
        step_minutes=5,
        seed=42,
        autonomous_isf=True,
        swarm_bolus=True,
    )
    assert summary.total_insulin_delivered_u > 0.5, (
        f"Expected >0.5 U total insulin, got {summary.total_insulin_delivered_u:.3f} U. "
        "The controller may not be generating recommendations in closed-loop mode."
    )


def test_closed_loop_drift_scenario_achieves_full_tir() -> None:
    """Basal deficit (drift, no meal): autonomous control should achieve ≥80% TIR."""
    records, summary = run_closed_loop_evaluation(
        simulation_inputs=sustained_basal_deficit_scenario(),
        duration_minutes=120,
        step_minutes=5,
        seed=42,
        autonomous_isf=True,
    )
    assert summary.percent_time_in_range >= 80.0, (
        f"Expected ≥80% TIR on dawn scenario, got {summary.percent_time_in_range:.1f}%. "
        "Drift corrections may not be accumulating effectively."
    )


def test_closed_loop_iob_tracked_from_physiology() -> None:
    """In closed-loop mode, IOB should grow after a dose is delivered.

    Because the physiology state now carries the actual delivered insulin,
    the IOB reported in step records should increase following a delivery.
    """
    records, _ = run_closed_loop_evaluation(
        simulation_inputs=baseline_meal_scenario(),
        duration_minutes=180,
        step_minutes=5,
        seed=42,
        autonomous_isf=True,
    )
    delivered_steps = [r for r in records if r.pump_delivered_units > 0.05]
    if not delivered_steps:
        return  # Nothing to check

    # Find the step after the first delivery and verify IOB is non-zero
    first_delivery_t = delivered_steps[0].timestamp_min
    subsequent = [r for r in records if r.timestamp_min > first_delivery_t]
    if subsequent:
        max_iob_after = max(r.insulin_on_board_u for r in subsequent[:6])
        assert max_iob_after > 0, (
            "IOB should be >0 in the steps following a delivery. "
            "The PK/PD state may not be propagating through the closed-loop physiology."
        )
