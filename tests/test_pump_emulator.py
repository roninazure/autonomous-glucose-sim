from ags.pump.emulator import emulate_pump_delivery
from ags.pump.state import PumpConfig, PumpRequest


def test_emulate_pump_delivery_clips_to_max_interval() -> None:
    config = PumpConfig(
        dose_increment_u=0.05,
        max_units_per_interval=1.0,
    )
    request = PumpRequest(requested_units=1.12)

    result = emulate_pump_delivery(request, config)

    assert result.delivered_units == 1.0
    assert result.clipped is True
    assert result.rounded is False
    assert result.reason == "dose clipped to pump max"


def test_emulate_pump_delivery_rounds_to_increment() -> None:
    config = PumpConfig(
        dose_increment_u=0.05,
        max_units_per_interval=1.0,
    )
    request = PumpRequest(requested_units=0.83)

    result = emulate_pump_delivery(request, config)

    assert result.delivered_units == 0.85
    assert result.clipped is False
    assert result.rounded is True
    assert result.reason == "dose rounded to pump increment"


def test_emulate_pump_delivery_rejects_non_positive_request() -> None:
    config = PumpConfig()
    request = PumpRequest(requested_units=0.0)

    result = emulate_pump_delivery(request, config)

    assert result.delivered_units == 0.0
    assert result.clipped is False
    assert result.rounded is False
    assert result.reason == "no positive dose requested"
