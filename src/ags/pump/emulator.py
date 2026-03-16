from __future__ import annotations

from ags.pump.quantizer import quantize_dose
from ags.pump.state import PumpConfig, PumpRequest, PumpResult


def emulate_pump_delivery(
    request: PumpRequest,
    config: PumpConfig | None = None,
) -> PumpResult:
    config = config or PumpConfig()

    clipped_request = min(request.requested_units, config.max_units_per_interval)
    clipped = clipped_request < request.requested_units

    delivered_units = quantize_dose(clipped_request, config)
    rounded = delivered_units != clipped_request

    if request.requested_units <= 0:
        return PumpResult(
            delivered_units=0.0,
            clipped=False,
            rounded=False,
            reason="no positive dose requested",
        )

    if clipped and rounded:
        reason = "dose clipped to pump max and rounded to increment"
    elif clipped:
        reason = "dose clipped to pump max"
    elif rounded:
        reason = "dose rounded to pump increment"
    else:
        reason = "dose delivered as requested"

    return PumpResult(
        delivered_units=delivered_units,
        clipped=clipped,
        rounded=rounded,
        reason=reason,
    )
