from pathlib import Path

from ags.simulation.run import build_output_path


def test_build_output_path_uses_outputs_directory_and_csv_suffix() -> None:
    repo_root = Path("/tmp/autonomous-glucose-sim")
    output_path = build_output_path(repo_root)

    assert output_path.parent == repo_root / "experiments" / "outputs"
    assert output_path.name.startswith("simulation_run_")
    assert output_path.suffix == ".csv"
