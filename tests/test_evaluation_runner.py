from ags.evaluation.runner import run_evaluation
from ags.simulation.scenarios import baseline_meal_scenario


def test_run_evaluation_returns_records_and_summary() -> None:
    simulation_inputs = baseline_meal_scenario()

    records, summary = run_evaluation(
        simulation_inputs=simulation_inputs,
        duration_minutes=60,
        step_minutes=5,
        seed=42,
    )

    assert len(records) == 12
    assert summary.total_timesteps == 12
    assert summary.time_in_range_steps + summary.time_above_range_steps + summary.time_below_range_steps == 12
    assert summary.blocked_decisions + summary.clipped_decisions + summary.allowed_decisions == 12
    assert summary.total_insulin_delivered_u >= 0.0

    first = records[0]
    assert first.timestamp_min == 5
    assert first.safety_status in {"allowed", "clipped", "blocked"}
    assert first.pump_delivered_units >= 0.0
