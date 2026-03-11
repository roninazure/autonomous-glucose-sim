from __future__ import annotations

import csv
from pathlib import Path

from ags.simulation.state import SimulationSnapshot


def write_snapshots_csv(
    snapshots: list[SimulationSnapshot],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "timestamp_min",
                "true_glucose_mgdl",
                "cgm_glucose_mgdl",
                "insulin_on_board_u",
                "active_meal_carbs_g",
                "delivered_insulin_u",
                "glucose_delta_mgdl",
            ]
        )

        for snap in snapshots:
            writer.writerow(
                [
                    snap.timestamp_min,
                    snap.true_glucose_mgdl,
                    snap.cgm_glucose_mgdl,
                    snap.insulin_on_board_u,
                    snap.active_meal_carbs_g,
                    snap.delivered_insulin_u,
                    snap.glucose_delta_mgdl,
                ]
            )
