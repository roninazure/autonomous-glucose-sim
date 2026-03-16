from __future__ import annotations

from ags.pump.emulator import emulate_pump_delivery
from ags.pump.state import PumpConfig, PumpRequest


def main() -> None:
    config = PumpConfig(
        dose_increment_u=0.05,
        max_units_per_interval=1.0,
    )

    request = PumpRequest(requested_units=1.12)

    result = emulate_pump_delivery(request, config)

    print("Pump demo")
    print("=" * 20)
    print(f"Requested units: {request.requested_units:.2f} U")
    print(f"Pump increment: {config.dose_increment_u:.2f} U")
    print(f"Pump max per interval: {config.max_units_per_interval:.2f} U")
    print(f"Delivered units: {result.delivered_units:.2f} U")
    print(f"Clipped: {result.clipped}")
    print(f"Rounded: {result.rounded}")
    print(f"Reason: {result.reason}")


if __name__ == "__main__":
    main()
