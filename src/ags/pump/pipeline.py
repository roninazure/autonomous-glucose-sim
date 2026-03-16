from __future__ import annotations

from ags.pump.emulator import emulate_pump_delivery
from ags.pump.integration import build_pump_request
from ags.pump.state import PumpConfig, PumpResult
from ags.safety.state import SafetyDecision


def run_pump_with_safety_output(
    safety_decision: SafetyDecision,
    pump_config: PumpConfig | None = None,
) -> PumpResult:
    pump_request = build_pump_request(safety_decision)
    return emulate_pump_delivery(pump_request, pump_config)
