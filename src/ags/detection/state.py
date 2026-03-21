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


class DriftType(str, Enum):
    """Cause of a slow, sustained glucose rise — distinct from a meal spike."""
    NONE = "none"
    DAWN = "dawn"               # Cortisol/GH-driven overnight rise (typically 2–8 am)
    SUSTAINED = "sustained"     # Generalised insufficient basal coverage
    REBOUND = "rebound"         # Post-hypoglycaemic rebound (Somogyi effect)


@dataclass
class BasalDriftSignal:
    """Output of the basal drift detector.

    Identifies slow, sustained glucose rises that indicate insufficient
    background insulin — as opposed to the sharp, accelerating rises that
    signal carbohydrate absorption.  Derived entirely from CGM history.
    """
    detected: bool
    drift_type: DriftType

    # Dynamics
    sustained_rate_mgdl_per_min: float   # slow linear slope over the long window
    linearity_score: float               # 0–1: how straight the rise is (R²-like)
    sustained_steps: int                 # how many consecutive rising steps

    # Cause characterisation
    confidence: float                    # 0.0–1.0
    preceded_by_low: bool                # True → possible rebound

    @property
    def label(self) -> str:
        if not self.detected:
            return "no basal drift"
        return (
            f"{self.drift_type.value} | {self.sustained_rate_mgdl_per_min:+.2f} mg/dL/min "
            f"| linearity {self.linearity_score:.0%} | confidence {self.confidence:.0%}"
        )


class GlucoseCause(str, Enum):
    """Unified classification of the *cause* of the current glucose excursion.

    The controller uses this to choose the appropriate dosing strategy:
    meal → pre-bolus + tiered micro-bolus,
    basal drift → small sustained micro-bolus to counteract slow creep,
    flat → correction only if predicted glucose exceeds target.
    """
    FLAT = "flat"               # No significant excursion
    MEAL = "meal"               # Post-prandial carb absorption
    BASAL_DRIFT = "basal_drift" # Slow, sustained insufficient-basal rise
    REBOUND = "rebound"         # Post-hypoglycaemic rebound
    MIXED = "mixed"             # Both meal and drift signals present


@dataclass
class GlucoseDynamicsClassification:
    """Combined output of the cause classifier."""
    cause: GlucoseCause
    meal_signal: MealSignal | None
    basal_signal: BasalDriftSignal | None
    confidence: float

    @property
    def label(self) -> str:
        return (
            f"cause={self.cause.value} | "
            f"meal={'yes' if self.meal_signal and self.meal_signal.detected else 'no'} | "
            f"drift={'yes' if self.basal_signal and self.basal_signal.detected else 'no'} | "
            f"confidence={self.confidence:.0%}"
        )


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
