from __future__ import annotations

from ags.pump.state import PumpConfig


def quantize_dose(
    requested_units: float,
    config: PumpConfig,
) -> float:
    if requested_units <= 0:
        return 0.0

    increment = config.dose_increment_u
    quantized = round(requested_units / increment) * increment
    return max(0.0, round(quantized, 4))
