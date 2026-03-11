from pathlib import Path

from ags.simulation.engine import run_simulation
from ags.simulation.io import write_snapshots_csv
from ags.simulation.state import MealEvent, SimulationInputs


def test_write_snapshots_csv_creates_file(tmp_path: Path) -> None:
    inputs = SimulationInputs(
        meal_events=[MealEvent(timestamp_min=30, carbs_g=45.0, absorption_minutes=120)]
    )

    snapshots = run_simulation(
        inputs=inputs,
        duration_minutes=60,
        step_minutes=5,
        seed=42,
    )

    output_path = tmp_path / "simulation_test.csv"
    write_snapshots_csv(snapshots, output_path)

    assert output_path.exists()

    lines = output_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == len(snapshots) + 1
    assert lines[0].startswith("timestamp_min,true_glucose_mgdl")
