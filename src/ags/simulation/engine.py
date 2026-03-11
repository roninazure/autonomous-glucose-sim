from __future__ import annotations

import random

from ags.simulation.physiology import advance_physiology
from ags.simulation.sensor import generate_cgm_reading
from ags.simulation.state import SimulationInputs, SimulationSnapshot


def run_simulation(
    inputs: SimulationInputs,
    duration_minutes: int = 240,
    step_minutes: int = 5,
    seed: int = 42,
) -> list[SimulationSnapshot]:
    random.seed(seed)

    snapshots: list[SimulationSnapshot] = [SimulationSnapshot()]
    steps = max(1, duration_minutes // step_minutes)

    current = snapshots[0]

    for _ in range(steps):
        next_snapshot = advance_physiology(
            snapshot=current,
            inputs=inputs,
            step_minutes=step_minutes,
        )
        next_snapshot.cgm_glucose_mgdl = generate_cgm_reading(next_snapshot)
        snapshots.append(next_snapshot)
        current = next_snapshot

    return snapshots
