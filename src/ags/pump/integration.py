from __future__ import annotations

from ags.pump.state import PumpRequest
from ags.safety.state import SafetyDecision


def build_pump_request(
    safety_decision: SafetyDecision,
) -> PumpRequest:
    return PumpRequest(requested_units=safety_decision.final_units)
