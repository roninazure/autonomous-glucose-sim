from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PumpConfig:
    dose_increment_u: float = 0.05
    max_units_per_interval: float = 1.0


@dataclass
class PumpRequest:
    requested_units: float


@dataclass
class PumpResult:
    delivered_units: float
    clipped: bool
    rounded: bool
    reason: str


@dataclass
class DualWaveConfig:
    """Configuration for split (combo/dual-wave) bolus delivery.

    Inspired by the doctor's clinical note:
      "30g carbs → 6 units total → 2 units quick + 4 units slowly over 20 min"

    When enabled, each correction bolus is split into:
      - immediate_fraction × total  → delivered right now
      - (1 − immediate_fraction) × total → dripped evenly over extended_duration_minutes

    This matches post-prandial physiology: the initial glucose spike appears in
    5–10 min (needs fast insulin up front), while slower carb absorption
    continues for 20–30 min (needs sustained background delivery).
    """
    enabled: bool = False
    # Fraction of the calculated bolus to deliver immediately.
    # Doctor example: 2 of 6 units = 0.33.
    immediate_fraction: float = 0.33
    # Minutes over which the remaining (extended) portion is dripped.
    extended_duration_minutes: int = 20


@dataclass
class DualWaveState:
    """Tracks the in-progress extended tail of a dual-wave bolus.

    Initialised at zero; updated each time a new dual-wave bolus is triggered
    or the extended portion advances by one step.
    """
    # Units remaining to be delivered in the extended tail.
    extended_remaining_u: float = 0.0
    # Rate per step (U/step) — set when the extended tail is queued,
    # held constant until the tail is exhausted.
    extended_rate_u_per_step: float = 0.0
    # Number of steps still outstanding in the current extended tail.
    extended_steps_remaining: int = 0

    @property
    def is_active(self) -> bool:
        return self.extended_steps_remaining > 0 and self.extended_remaining_u > 0.0
