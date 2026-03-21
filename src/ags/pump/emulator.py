from __future__ import annotations

from ags.pump.quantizer import quantize_dose
from ags.pump.state import DualWaveConfig, DualWaveState, PumpConfig, PumpRequest, PumpResult


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


def apply_dual_wave_split(
    total_units: float,
    dual_wave_config: DualWaveConfig,
    dual_wave_state: DualWaveState,
    step_minutes: int,
    pump_config: PumpConfig | None = None,
) -> tuple[float, DualWaveState]:
    """Split a bolus into immediate + extended tail (dual-wave / combo bolus).

    When a new bolus recommendation arrives:
      - immediate_units = immediate_fraction × total_units → delivered this step
      - extended_units  = (1 − immediate_fraction) × total_units → queued

    The extended tail is distributed evenly over ``extended_duration_minutes``
    in equal per-step instalments.  Any pre-existing tail is **replaced** by
    the new tail (the new bolus supersedes the old one, consistent with how
    clinical pump combo-bolus overrides work).

    Args:
        total_units: Full correction dose recommended by the controller.
        dual_wave_config: Split configuration (fractions and duration).
        dual_wave_state: Current extended-tail tracking state.
        step_minutes: Loop cadence — used to compute the number of steps
            in the extended tail.
        pump_config: Used to quantize the per-step extended rate.

    Returns:
        (immediate_units_to_deliver_now, updated_DualWaveState)
    """
    pump_config = pump_config or PumpConfig()

    immediate_units = total_units * dual_wave_config.immediate_fraction
    extended_units = total_units * (1.0 - dual_wave_config.immediate_fraction)

    extended_steps = max(1, dual_wave_config.extended_duration_minutes // max(1, step_minutes))
    rate_u_per_step = extended_units / extended_steps

    new_state = DualWaveState(
        extended_remaining_u=extended_units,
        extended_rate_u_per_step=rate_u_per_step,
        extended_steps_remaining=extended_steps,
    )

    return immediate_units, new_state


def advance_dual_wave_state(
    dual_wave_state: DualWaveState,
    pump_config: PumpConfig | None = None,
) -> tuple[float, DualWaveState]:
    """Deliver the next instalment from an active extended tail.

    Args:
        dual_wave_state: Current state (may or may not be active).
        pump_config: Used to quantize the instalment.

    Returns:
        (extended_units_delivered_this_step, updated_DualWaveState)
    """
    if not dual_wave_state.is_active:
        return 0.0, dual_wave_state

    pump_config = pump_config or PumpConfig()
    this_step = min(
        dual_wave_state.extended_rate_u_per_step,
        dual_wave_state.extended_remaining_u,
    )
    this_step = quantize_dose(this_step, pump_config)

    new_remaining = max(0.0, dual_wave_state.extended_remaining_u - this_step)
    new_steps = dual_wave_state.extended_steps_remaining - 1

    new_state = DualWaveState(
        extended_remaining_u=new_remaining,
        extended_rate_u_per_step=dual_wave_state.extended_rate_u_per_step,
        extended_steps_remaining=max(0, new_steps),
    )

    return this_step, new_state
