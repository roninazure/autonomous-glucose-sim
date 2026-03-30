from __future__ import annotations

from dataclasses import dataclass, field

from ags.detection.state import MealSignal


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
    # Autonomous meal signal — populated by the runner when autonomous_isf=True.
    # The recommender uses this to fire a pre-bolus on ONSET and to scale the
    # correction dose appropriately throughout the post-prandial window.
    meal_signal: MealSignal | None = None
    # Set to True by the runner once a pre-bolus has been fired for the
    # current meal event.  Prevents the recommender from re-firing on every
    # consecutive ONSET step of the same meal.  Reset by the runner when the
    # meal signal returns to NONE (meal over).
    prebolus_already_fired: bool = False
    # When True, use the SWARM Auto-Bolus formula (ACC + ROC driven) instead
    # of the legacy correction-fraction approach.
    swarm_bolus: bool = False
    # Minutes elapsed since the meal was first detected this session.
    # Used by the SWARM recommender to apply the early meal push multiplier
    # during the early push window below.
    minutes_since_meal_detected: float = 0.0
    # ── SWARM tuning parameters (passed from SafetyThresholds by runner) ─────
    # Dosing formula coefficients.
    swarm_u_base: float = 0.15
    swarm_a_roc: float = 3.0
    swarm_b_acc: float = 25.0
    # Per-pulse ceiling for the SWARM micro-bolus formula.
    swarm_max_pulse_u: float = 1.0
    # IOB dampening breakpoints — dose scales 1.0× below bp1,
    # 0.7× between bp1 and bp2, 0.4× at or above bp2.
    swarm_iob_scale_bp1: float = 1.5
    swarm_iob_scale_bp2: float = 3.0
    # Early meal push window (minutes after first meal detection).
    swarm_early_push_min_minutes: float = 5.0
    swarm_early_push_max_minutes: float = 75.0
    # Early push dose multiplier.
    swarm_early_push_multiplier: float = 2.5
    # Late-phase maintenance window and dose.
    swarm_late_phase_glucose_min: float = 125.0
    swarm_late_phase_glucose_max: float = 175.0
    swarm_late_phase_roc_threshold: float = 0.2
    swarm_late_phase_iob_max: float = 1.5
    swarm_late_phase_dose_u: float = 0.125
    # Micro-bolus glucose floor — main micro-bolus only fires above this.
    swarm_min_glucose_for_microbolus: float = 130.0
    swarm_min_glucose_during_meal: float = 120.0


@dataclass
class ExcursionSignal:
    glucose_delta_mgdl: float
    rate_mgdl_per_min: float   # glucose_delta / step_minutes
    rising: bool
    falling: bool
    # Second derivative of glucose in mg/dL/min².
    # Positive = accelerating upward (rising faster); negative = decelerating.
    # Requires at least 3 readings in glucose_history; 0.0 when unavailable.
    acceleration_mgdl_per_min2: float = 0.0


@dataclass
class GlucosePrediction:
    predicted_glucose_mgdl: float
    prediction_horizon_minutes: int


@dataclass
class CorrectionRecommendation:
    recommended_units: float
    reason: str
