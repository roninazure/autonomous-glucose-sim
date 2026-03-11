from __future__ import annotations

from pathlib import Path

from ags.simulation.engine import run_simulation
from ags.simulation.io import write_snapshots_csv
from ags.simulation.state import MealEvent, SimulationInputs


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    output_path = repo_root / "experiments" / "outputs" / "simulation_run_001.csv"

    inputs = SimulationInputs(
        insulin_sensitivity_mgdl_per_unit=50.0,
        carb_impact_mgdl_per_g=3.0,
        baseline_drift_mgdl_per_step=0.0,
        meal_events=[
            MealEvent(timestamp_min=30, carbs_g=45.0, absorption_minutes=120),
        ],
    )

    snapshots = run_simulation(
        inputs=inputs,
        duration_minutes=180,
        step_minutes=5,
        seed=42,
    )

    write_snapshots_csv(snapshots, output_path)

    print(f"Saved simulation output to: {output_path}")
    print("timestamp_min,true_glucose_mgdl,cgm_glucose_mgdl,insulin_on_board_u,active_meal_carbs_g,glucose_delta_mgdl")
    for snap in snapshots[:10]:
        print(
            f"{snap.timestamp_min},"
            f"{snap.true_glucose_mgdl:.2f},"
            f"{snap.cgm_glucose_mgdl:.2f},"
            f"{snap.insulin_on_board_u:.2f},"
            f"{snap.active_meal_carbs_g:.2f},"
            f"{snap.glucose_delta_mgdl:.2f}"
        )

    print(f"\nTotal snapshots: {len(snapshots)}")


if __name__ == "__main__":
    main()
