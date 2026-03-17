from __future__ import annotations

from ags.evaluation.runner import run_evaluation
from ags.simulation.scenarios import baseline_meal_scenario


def main() -> None:
    simulation_inputs = baseline_meal_scenario()

    records, summary = run_evaluation(
        simulation_inputs=simulation_inputs,
        duration_minutes=180,
        step_minutes=5,
        seed=42,
    )

    print("Evaluation demo")
    print("=" * 24)
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
