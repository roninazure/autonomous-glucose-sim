from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ags.simulation.engine import run_simulation
from ags.simulation.io import write_snapshots_csv
from ags.simulation.scenarios import baseline_meal_scenario


def build_output_path(repo_root: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return repo_root / "experiments" / "outputs" / f"simulation_run_{timestamp}.csv"


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    output_path = build_output_path(repo_root)

    inputs = baseline_meal_scenario()

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
