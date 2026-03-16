from __future__ import annotations

from ags.pump.pipeline import run_pump_with_safety_output
from ags.pump.state import PumpConfig
from ags.safety.state import SafetyDecision


def main() -> None:
    safety_decision = SafetyDecision(
        status="clipped",
        allowed=True,
        final_units=0.92,
        reason="recommendation allowed after safety evaluation",
    )

    pump_config = PumpConfig(
        dose_increment_u=0.05,
        max_units_per_interval=1.0,
    )

    pump_result = run_pump_with_safety_output(
        safety_decision=safety_decision,
        pump_config=pump_config,
    )

    print("Safety + Pump demo")
    print("=" * 24)
    print(f"Safety status: {safety_decision.status}")
    print(f"Safety allowed: {safety_decision.allowed}")
    print(f"Safety final units: {safety_decision.final_units:.2f} U")
    print(f"Pump delivered units: {pump_result.delivered_units:.2f} U")
    print(f"Pump clipped: {pump_result.clipped}")
    print(f"Pump rounded: {pump_result.rounded}")
    print(f"Pump reason: {pump_result.reason}")


if __name__ == "__main__":
    main()
