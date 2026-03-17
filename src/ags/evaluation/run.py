from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ags.evaluation.io import write_run_summary_json, write_timestep_records_csv
from ags.evaluation.runner import run_evaluation
from ags.simulation.scenarios import baseline_meal_scenario


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    records_path = repo_root / "experiments" / "outputs" / f"evaluation_records_{timestamp}.csv"
    summary_path = repo_root / "experiments" / "outputs" / f"evaluation_summary_{timestamp}.json"

    simulation_inputs = baseline_meal_scenario()

    records, summary = run_evaluation(
        simulation_inputs=simulation_inputs,
        duration_minutes=180,
        step_minutes=5,
        seed=42,
    )

    write_timestep_records_csv(records, records_path)
    write_run_summary_json(summary, summary_path)

    print("Evaluation demo")
    print("=" * 24)
    print(f"Records written to: {records_path}")
    print(f"Summary written to: {summary_path}")
    print(f"Total records: {len(records)}")
    print(f"Time in range steps: {summary.time_in_range_steps}")
    print(f"Time above range steps: {summary.time_above_range_steps}")
    print(f"Time below range steps: {summary.time_below_range_steps}")
    print(f"Total insulin delivered: {summary.total_insulin_delivered_u:.2f} U")
    print(f"Allowed decisions: {summary.allowed_decisions}")
    print(f"Clipped decisions: {summary.clipped_decisions}")
    print(f"Blocked decisions: {summary.blocked_decisions}")

    if records:
        first = records[0]
        print("\nFirst record")
        print(f"Timestamp: {first.timestamp_min} min")
        print(f"CGM glucose: {first.cgm_glucose_mgdl:.2f} mg/dL")
        print(f"Recommended units: {first.recommended_units:.2f} U")
        print(f"Safety status: {first.safety_status}")
        print(f"Pump delivered: {first.pump_delivered_units:.2f} U")


if __name__ == "__main__":
    main()
