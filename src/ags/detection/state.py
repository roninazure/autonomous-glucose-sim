from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class MealPhase(str, Enum):
    """Inferred phase of a post-prandial glucose excursion."""
    NONE = "none"            # No meal signal — glucose flat or falling
    ONSET = "onset"          # Rapid rise beginning — meal just detected
    PEAK = "peak"            # Rate decelerating — glucose near excursion peak
    RECOVERY = "recovery"    # Glucose falling back toward target


@dataclass
class MealSignal:
    """Output of the autonomous meal detector.

    Derived entirely from CGM history — no user announcement required.
    """
    detected: bool
    phase: MealPhase

    # Core dynamics
    smoothed_rate_mgdl_per_min: float     # 1st derivative (smoothed)
    acceleration_mgdl_per_min2: float     # 2nd derivative — positive = speeding up
    consecutive_rising_steps: int         # how many steps glucose has been rising

    # Meal characterisation
    estimated_carbs_g: float              # rough carb estimate from spike magnitude
    confidence: float                     # 0.0–1.0

    # Triggering pre-bolus recommendation
    recommend_prebolus: bool              # True only on ONSET, first detection

    @property
    def label(self) -> str:
        if not self.detected:
            return "no meal"
        return f"{self.phase.value} | ~{self.estimated_carbs_g:.0f}g | confidence {self.confidence:.0%}"


@dataclass
class AutonomousControllerState:
    """Persistent state carried across timesteps for the fully autonomous controller.

    This is the 'memory' of the self-driving pancreas — it accumulates evidence
    across CGM readings so each decision is informed by the full session history,
    not just the current reading.
    """
    # Rolling ISF observations for online learning: (delivered_units, glucose_drop)
    isf_observations: list[tuple[float, float]] = field(default_factory=list)

    # Meal tracking — avoid firing multiple pre-bolus recommendations for the
    # same meal event.
    meal_detected_at_step: int | None = None
    last_prebolus_step: int | None = None

    # Session step counter
    step: int = 0

    # Estimated per-session effective ISF — refined as observations accumulate
    session_isf_estimate: float | None = None
