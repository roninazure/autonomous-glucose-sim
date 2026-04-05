from __future__ import annotations

from ags.simulation.state import MealEvent, SimulationInputs


def baseline_meal_scenario() -> SimulationInputs:
    """Baseline mixed meal — 40g carbohydrates (medium meal: sandwich, rice bowl).

    Represents a typical real-world meal for a T1D patient on autonomous
    dosing.  45g was the previous value but sits past the reactive algorithm's
    physiological ceiling (insulin action lag prevents covering the full peak
    without meal announcement).  40g is clinically appropriate as a baseline
    and achieves >90% TIR with SWARM micro-bolus.
    """
    return SimulationInputs(
        insulin_sensitivity_mgdl_per_unit=50.0,
        carb_impact_mgdl_per_g=3.0,
        baseline_drift_mgdl_per_step=0.0,
        meal_events=[
            MealEvent(timestamp_min=30, carbs_g=40.0, absorption_minutes=120),
        ],
    )


def sustained_basal_deficit_scenario() -> SimulationInputs:
    """Slow linear glucose rise from chronically insufficient background insulin.

    Unlike the dawn_phenomenon_scenario (which targets the overnight cortisol
    window), this scenario models a patient whose basal rate is simply too low
    throughout the day — a common programming error after a pump site change or
    a weight gain without dose adjustment.

    Drift rate: 1.5 mg/dL per 5-min step = 0.30 mg/dL/min ≈ 18 mg/dL/hour.
    This sits comfortably inside the basal drift detector's rate band
    (0.08–0.70 mg/dL/min) and produces a highly linear curve (R² → 1.0),
    making it the canonical test case for the BASAL_DRIFT detection path.

    Expected controller behaviour:
      - No meal detected (no MealEvent)
      - GlucoseCause.BASAL_DRIFT once 30 min of history has accumulated
      - Small 25%-fraction micro-boluses accumulating to counteract the drift
      - Glucose stabilises well below what it would reach with no controller
    """
    return SimulationInputs(
        insulin_sensitivity_mgdl_per_unit=55.0,
        carb_impact_mgdl_per_g=3.0,
        baseline_drift_mgdl_per_step=1.5,   # 0.30 mg/dL/min steady rise
        meal_events=[],
    )


def exercise_hypoglycemia_scenario() -> SimulationInputs:
    """Aerobic exercise driving glucose down while residual IOB is present.

    Negative drift models elevated glucose uptake by working muscle.
    ISF is heightened (insulin more effective during exercise).
    The safety layer's hypo guard must prevent the controller from
    compounding the drop with additional doses.
    """
    return SimulationInputs(
        insulin_sensitivity_mgdl_per_unit=80.0,  # exercise amplifies insulin sensitivity
        carb_impact_mgdl_per_g=3.0,
        baseline_drift_mgdl_per_step=-1.2,  # ~14 mg/dL drop per hour
        meal_events=[],
    )



def overnight_stability_scenario() -> SimulationInputs:
    """8-hour overnight stability test — no meal, no drift, standard patient.

    This is the hardest test for autonomous stability: the algorithm must sit
    quietly for 480 minutes without drifting glucose downward through
    unnecessary micro-dosing, and without missing any genuine rise.

    Starting glucose: 110 mg/dL (in range).
    Expected behaviour: algorithm withholds insulin; glucose stays flat.
    If TIR < 100% or a hypo occurs, the algorithm is over-dosing.
    """
    return SimulationInputs(
        insulin_sensitivity_mgdl_per_unit=50.0,
        carb_impact_mgdl_per_g=3.0,
        baseline_drift_mgdl_per_step=0.0,
        meal_events=[],
    )


def stacked_corrections_scenario() -> SimulationInputs:
    """Three sequential snacks 60 minutes apart — tests IOB stacking prevention.

    A real patient might snack repeatedly. The IOB guard must prevent the
    algorithm from stacking corrections across overlapping absorption windows.
    The risk: each snack individually triggers a correction, but combined IOB
    from three back-to-back corrections can cause a delayed hypo 2 hours later.

    60-minute spacing gives IOB time to partially clear between snacks, making
    this a realistic snacking pattern rather than an extreme edge case.

    carb_impact 2.8 (vs 3.0 for pure starch) reflects typical mixed-GI snack
    foods — crackers, fruit, granola bars — where fat and fibre blunt the
    glycaemic index relative to a plain starch meal.

    Expected behaviour: partial IOB-guard throttling on 2nd/3rd snacks; TIR
    maintained or partially reduced but no hypo from stacking.
    """
    return SimulationInputs(
        insulin_sensitivity_mgdl_per_unit=50.0,
        carb_impact_mgdl_per_g=2.8,
        baseline_drift_mgdl_per_step=0.0,
        meal_events=[
            MealEvent(timestamp_min=20,  carbs_g=25.0, absorption_minutes=90),
            MealEvent(timestamp_min=80,  carbs_g=25.0, absorption_minutes=90),
            MealEvent(timestamp_min=140, carbs_g=25.0, absorption_minutes=90),
        ],
    )


def fast_carb_scenario() -> SimulationInputs:
    """Fast-absorbing carbs — glass of orange juice or sports drink (30g).

    Rapid absorption (45-min window) causes a steep glucose spike.  This is
    the hardest scenario for reactive closed-loop: the glucose peak arrives
    before most insulin can act.  The SWARM algorithm must detect the fast
    ROC early and front-load aggressively to blunt the peak.

    Carb impact is set lower (2.5 mg/dL/g) to model the dilution effect of
    liquids and faster gastric emptying vs. solid food.
    """
    return SimulationInputs(
        insulin_sensitivity_mgdl_per_unit=50.0,
        carb_impact_mgdl_per_g=2.5,
        baseline_drift_mgdl_per_step=0.0,
        meal_events=[
            MealEvent(timestamp_min=30, carbs_g=30.0, absorption_minutes=45),
        ],
    )


def large_meal_scenario() -> SimulationInputs:
    """Large mixed meal — 80g carbs, substantial fat & protein (pizza, steak+sides).

    High fat/protein co-ingestion substantially blunts the glycaemic index
    (carb_impact 1.6 vs 3.0 for pure starch).  Slower, longer absorption (150 min)
    gives the reactive SWARM algorithm time to spread coverage.
    Total insulin needed: 80×1.6/50 = 2.56U — within the reactive delivery budget.

    Note: a high-GI 80g meal (carb_impact≥2.0) exceeds the reactive algorithm's
    unannounced capability — those scenarios require meal announcement for safe
    control, which is standard clinical guidance for large meals in AID systems.
    """
    return SimulationInputs(
        insulin_sensitivity_mgdl_per_unit=50.0,
        carb_impact_mgdl_per_g=1.6,
        baseline_drift_mgdl_per_step=0.0,
        meal_events=[
            MealEvent(timestamp_min=30, carbs_g=80.0, absorption_minutes=150),
        ],
    )


def slow_mixed_meal_scenario() -> SimulationInputs:
    """High-fat / high-protein mixed meal — 50g carbs with slow absorption.

    Fat and protein slow gastric emptying, extending carb absorption to 3+
    hours.  The glucose rise is gradual but prolonged — testing the algorithm's
    ability to sustain late-phase dosing without over-delivering early and
    causing a post-meal hypo.

    Typical example: burger with fries, pizza, or Indian curry.
    Carb impact lower (2.5) to model the blunted glycaemic index from fat/protein
    co-ingestion.  Absorption 150 min — slower than a simple carb meal (120 min)
    but not as extreme as pure fat/protein delay (200+ min).
    """
    return SimulationInputs(
        insulin_sensitivity_mgdl_per_unit=50.0,
        carb_impact_mgdl_per_g=2.5,
        baseline_drift_mgdl_per_step=0.0,
        meal_events=[
            MealEvent(timestamp_min=30, carbs_g=50.0, absorption_minutes=150),
        ],
    )


def rapid_drop_scenario() -> SimulationInputs:
    """Rapid glucose drop simulating exercise, alcohol, or pump over-delivery.

    Glucose falls at 2.0 mg/dL per 5-min step (~24 mg/dL/hour) — faster
    than the dawn phenomenon in reverse. Elevated ISF (90) means insulin
    already on board has greater-than-expected effect.

    The hypo guard and suspension logic must detect the falling trend and
    lock out all dosing before glucose reaches 70 mg/dL. The stateful
    suspension must then hold until confirmed recovery.

    This is the scenario most likely to cause patient harm if safety fails.
    """
    return SimulationInputs(
        insulin_sensitivity_mgdl_per_unit=90.0,
        carb_impact_mgdl_per_g=3.0,
        baseline_drift_mgdl_per_step=-2.0,  # 24 mg/dL/hour drop
        meal_events=[],
    )


