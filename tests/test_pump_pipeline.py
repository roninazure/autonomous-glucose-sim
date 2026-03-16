from ags.pump.pipeline import run_pump_with_safety_output
from ags.pump.state import PumpConfig
from ags.safety.state import SafetyDecision


def test_run_pump_with_safety_output_rounds_delivery() -> None:
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

    result = run_pump_with_safety_output(safety_decision, pump_config)

    assert result.delivered_units == 0.9
    assert result.clipped is False
    assert result.rounded is True
    assert result.reason == "dose rounded to pump increment"


def test_run_pump_with_safety_output_zero_delivery_when_blocked() -> None:
    safety_decision = SafetyDecision(
        status="blocked",
        allowed=False,
        final_units=0.0,
        reason="blocked by safety layer",
    )
    pump_config = PumpConfig()

    result = run_pump_with_safety_output(safety_decision, pump_config)

    assert result.delivered_units == 0.0
    assert result.clipped is False
    assert result.rounded is False
    assert result.reason == "no positive dose requested"
