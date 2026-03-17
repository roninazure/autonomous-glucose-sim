from ags.evaluation.metrics import summarize_run
from ags.evaluation.state import TimestepRecord


def test_summarize_run_counts_ranges_and_decisions() -> None:
    records = [
        TimestepRecord(
            timestamp_min=5,
            true_glucose_mgdl=100.0,
            cgm_glucose_mgdl=100.0,
            recommended_units=0.0,
            safety_status="blocked",
            safety_final_units=0.0,
            pump_delivered_units=0.0,
        ),
        TimestepRecord(
            timestamp_min=10,
            true_glucose_mgdl=185.0,
            cgm_glucose_mgdl=185.0,
            recommended_units=2.0,
            safety_status="clipped",
            safety_final_units=1.0,
            pump_delivered_units=1.0,
        ),
        TimestepRecord(
            timestamp_min=15,
            true_glucose_mgdl=65.0,
            cgm_glucose_mgdl=65.0,
            recommended_units=0.5,
            safety_status="allowed",
            safety_final_units=0.5,
            pump_delivered_units=0.5,
        ),
    ]

    summary = summarize_run(records)

    assert summary.total_timesteps == 3
    assert summary.time_in_range_steps == 1
    assert summary.time_above_range_steps == 1
    assert summary.time_below_range_steps == 1
    assert summary.total_insulin_delivered_u == 1.5
    assert summary.blocked_decisions == 1
    assert summary.clipped_decisions == 1
    assert summary.allowed_decisions == 1
