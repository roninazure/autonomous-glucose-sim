from ags.simulation.engine import run_simulation
from ags.simulation.state import MealEvent, SimulationInputs


def test_run_simulation_returns_snapshots() -> None:
    inputs = SimulationInputs(
        meal_events=[MealEvent(timestamp_min=30, carbs_g=45.0, absorption_minutes=120)]
    )

    snapshots = run_simulation(
        inputs=inputs,
        duration_minutes=60,
        step_minutes=5,
        seed=42,
    )

    assert len(snapshots) == 13
    assert snapshots[0].timestamp_min == 0
    assert snapshots[-1].timestamp_min == 60
    assert any(s.active_meal_carbs_g > 0 for s in snapshots)
    assert snapshots[-1].true_glucose_mgdl >= snapshots[0].true_glucose_mgdl
