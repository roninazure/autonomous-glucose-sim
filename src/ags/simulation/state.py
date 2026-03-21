from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MealEvent:
    timestamp_min: int
    carbs_g: float
    absorption_minutes: int = 120


@dataclass
class SimulationSnapshot:
    timestamp_min: int = 0
    true_glucose_mgdl: float = 110.0
    cgm_glucose_mgdl: float = 110.0
    insulin_on_board_u: float = 0.0
    # 2-compartment PK/PD state: subcutaneous pool (x1) and active/interstitial
    # pool (x2). insulin_on_board_u == x1 + x2 for convenience.
    insulin_compartment1_u: float = 0.0
    insulin_compartment2_u: float = 0.0
    active_meal_carbs_g: float = 0.0
    delivered_insulin_u: float = 0.0
    glucose_delta_mgdl: float = 0.0


@dataclass
class SimulationInputs:
    insulin_sensitivity_mgdl_per_unit: float = 50.0
    carb_impact_mgdl_per_g: float = 3.0
    baseline_drift_mgdl_per_step: float = 0.0
    meal_events: list[MealEvent] = field(default_factory=list)
    # Peak action time in minutes. 75 ≈ NovoLog/Aspart; 65 ≈ Humalog/Lispro;
    # 55 ≈ Fiasp (ultra-rapid).
    insulin_peak_minutes: float = 75.0
