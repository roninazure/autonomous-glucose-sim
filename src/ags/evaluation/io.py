from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

from ags.evaluation.state import RunSummary, TimestepRecord


def write_timestep_records_csv(
    records: list[TimestepRecord],
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
                "recommended_units",
                "safety_status",
                "safety_final_units",
                "pump_delivered_units",
            ]
        )

        for record in records:
            writer.writerow(
                [
                    record.timestamp_min,
                    record.true_glucose_mgdl,
                    record.cgm_glucose_mgdl,
                    record.recommended_units,
                    record.safety_status,
                    record.safety_final_units,
                    record.pump_delivered_units,
                ]
            )


def write_run_summary_json(
    summary: RunSummary,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(asdict(summary), indent=2),
        encoding="utf-8",
    )
