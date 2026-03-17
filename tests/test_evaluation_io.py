from pathlib import Path

from ags.evaluation.io import write_run_summary_json, write_timestep_records_csv
from ags.evaluation.state import RunSummary, TimestepRecord


def test_write_timestep_records_csv_and_summary_json(tmp_path: Path) -> None:
    records = [
        TimestepRecord(
            timestamp_min=5,
            true_glucose_mgdl=100.0,
            cgm_glucose_mgdl=101.0,
            recommended_units=0.5,
            safety_status="allowed",
            safety_final_units=0.5,
            pump_delivered_units=0.5,
        ),
        TimestepRecord(
            timestamp_min=10,
            true_glucose_mgdl=180.0,
            cgm_glucose_mgdl=182.0,
            recommended_units=1.2,
            safety_status="clipped",
            safety_final_units=1.0,
            pump_delivered_units=1.0,
        ),
    ]

    summary = RunSummary(
        total_timesteps=2,
        time_in_range_steps=1,
        time_above_range_steps=1,
        time_below_range_steps=0,
        percent_time_in_range=50.0,
        average_cgm_glucose_mgdl=141.5,
        peak_cgm_glucose_mgdl=182.0,
        total_recommended_insulin_u=1.7,
        total_insulin_delivered_u=1.5,
        blocked_decisions=0,
        clipped_decisions=1,
        allowed_decisions=1,
    )

    csv_path = tmp_path / "records.csv"
    json_path = tmp_path / "summary.json"

    write_timestep_records_csv(records, csv_path)
    write_run_summary_json(summary, json_path)

    assert csv_path.exists()
    assert json_path.exists()

    csv_lines = csv_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(csv_lines) == 3
    assert csv_lines[0].startswith("timestamp_min,true_glucose_mgdl")

    json_text = json_path.read_text(encoding="utf-8")
    assert '"total_timesteps": 2' in json_text
    assert '"percent_time_in_range": 50.0' in json_text
    assert '"average_cgm_glucose_mgdl": 141.5' in json_text
    assert '"peak_cgm_glucose_mgdl": 182.0' in json_text
    assert '"total_recommended_insulin_u": 1.7' in json_text
    assert '"total_insulin_delivered_u": 1.5' in json_text
