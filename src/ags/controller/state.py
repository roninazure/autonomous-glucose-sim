from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ControllerInputs:
    current_glucose_mgdl: float
    previous_glucose_mgdl: float
    insulin_on_board_u: float
    target_glucose_mgdl: float = 110.0
    correction_factor_mgdl_per_unit: float = 50.0
    # Recent CGM history (oldest → newest, including current reading).
    # When populated with 3+ readings, the predictor uses exponential
    # smoothing over the recent trend instead of naive linear extrapolation.
    glucose_history: list[float] = field(default_factory=list)
    # Minimum glucose delta (mg/dL per step) required before the controller
    # fires any correction. Filters out noise-driven micro-excursions.
    min_excursion_delta_mgdl: float = 0.0
    # Fraction of the calculated correction to deliver as a microbolus.
    # 1.0 = full correction; 0.25 = quarter-dose microbolus strategy.
    # Ignored when ror_tiered_microbolus=True.
    microbolus_fraction: float = 1.0
    # CGM step duration — used to convert per-step delta to mg/dL/min and to
    # scale detection thresholds correctly for 1-min or 5-min loops.
    step_minutes: int = 5
    # When True, overrides microbolus_fraction with a tiered fraction derived
    # from the observed rate of rise (mg/dL/min):
    #   < 1.0 → 0.0   (flat — no extra micro-bolus pressure)
    #   1–2   → 0.25
    #   2–3   → 0.50
    #   ≥ 3.0 → 1.0   (aggressive spike — full correction)
    ror_tiered_microbolus: bool = False
    # When True, correction_factor_mgdl_per_unit is IGNORED.  Instead the
    # controller infers effective insulin sensitivity (ISF) autonomously from
    # the observed rate of glucose rise — no user input required.
    #   Fast spike (≥3 mg/dL/min) → ISF ≈ 30  (insulin resistant → dose more)
    #   Moderate (1–2 mg/dL/min)  → ISF ≈ 50  (standard adult)
    #   Slow (<0.5 mg/dL/min)     → ISF ≈ 85  (highly sensitive → dose less)
    # This is the "Tesla" / artificial-pancreas mode — the algorithm adapts to
    # each patient's physiology purely from CGM dynamics, with no pre-programmed
    # sensitivity parameter.
    autonomous_isf: bool = False
    # Rolling history of (delivered_units, observed_glucose_drop_mgdl) pairs
    # collected during a live session.  Used by the online ISF learner to
    # refine the autonomous estimate as the session accumulates evidence.
    # Oldest observations are dropped once the window exceeds 12 entries.
    isf_observations: list[tuple[float, float]] = field(default_factory=list)


@dataclass
class ExcursionSignal:
    glucose_delta_mgdl: float
    rate_mgdl_per_min: float   # glucose_delta / step_minutes
    rising: bool
    falling: bool


@dataclass
class GlucosePrediction:
    predicted_glucose_mgdl: float
    prediction_horizon_minutes: int


@dataclass
class CorrectionRecommendation:
    recommended_units: float
    reason: str
