from __future__ import annotations

import random

from ags.simulation.state import SimulationSnapshot


def generate_cgm_reading(
    snapshot: SimulationSnapshot,
    noise_stddev: float = 5.0,
) -> float:
    noisy_value = snapshot.true_glucose_mgdl + random.gauss(0.0, noise_stddev)
    return max(40.0, noisy_value)
