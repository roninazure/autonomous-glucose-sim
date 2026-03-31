"""Fitness function for PSO: wraps closed-loop simulation + metrics.

Fitness is designed to be **minimised**:

    fitness = -TIR  +  hypo_weight × time_below_range%
                    +  peak_weight  × time_above_250%

Where TIR and time percentages are expressed 0–100.  This penalises both
hyperglycaemia (low TIR) and hypoglycaemia (explicit positive penalty), with
severe peaks (>250 mg/dL) receiving additional weight.

Each candidate particle is evaluated across every combination of:
  • scenario  (default: Baseline Meal, Dawn Phenomenon, Missed Bolus)
  • patient profile  (Standard Adult, Insulin Resistant, Highly Sensitive,
                      Rapid Responder)

The reported fitness is the average across all scenario × profile pairs.
"""
from __future__ import annotations

import copy

from ags.evaluation.profiles import ALL_PROFILES
from ags.evaluation.runner import run_closed_loop_evaluation
from ags.optimization.state import PSOConfig
from ags.safety.state import SafetyThresholds
from ags.simulation.scenarios import (
    baseline_meal_scenario,
    dawn_phenomenon_scenario,
    exercise_hypoglycemia_scenario,
    sustained_basal_deficit_scenario,
    stacked_corrections_scenario,
)
from ags.simulation.state import SimulationInputs


NAMED_SCENARIOS: dict[str, SimulationInputs] = {
    "Baseline Meal":           baseline_meal_scenario(),
    "Dawn Phenomenon":         dawn_phenomenon_scenario(),
    "Exercise Hypoglycaemia":  exercise_hypoglycemia_scenario(),
    "Sustained Basal Deficit": sustained_basal_deficit_scenario(),
    "Stacked Corrections":     stacked_corrections_scenario(),
}


def evaluate_candidate(
    params: dict[str, float],
    config: PSOConfig,
) -> float:
    """Return scalar fitness for a single candidate parameter set.

    Args:
        params: Dict mapping parameter name → value (clipped to bounds by PSO).
        config: PSO run configuration (scenarios, weights, duration).

    Returns:
        Scalar fitness (lower = better).
    """
    safety = SafetyThresholds(
        max_units_per_interval=params["max_units_per_interval"],
        max_insulin_on_board_u=params["max_insulin_on_board_u"],
        min_predicted_glucose_mgdl=params["min_predicted_glucose_mgdl"],
    )

    total_fitness = 0.0
    n_runs = 0

    for scenario_name in config.scenario_names:
        base_scenario = NAMED_SCENARIOS[scenario_name]

        for profile in ALL_PROFILES:
            scenario = SimulationInputs(
                insulin_sensitivity_mgdl_per_unit=profile.insulin_sensitivity_mgdl_per_unit,
                carb_impact_mgdl_per_g=profile.carb_impact_mgdl_per_g,
                baseline_drift_mgdl_per_step=base_scenario.baseline_drift_mgdl_per_step,
                meal_events=copy.deepcopy(base_scenario.meal_events),
                insulin_peak_minutes=profile.insulin_peak_minutes,
            )

            _records, summary = run_closed_loop_evaluation(
                simulation_inputs=scenario,
                safety_thresholds=safety,
                duration_minutes=config.duration_minutes,
                step_minutes=config.step_minutes,
                target_glucose_mgdl=params["target_glucose_mgdl"],
                correction_factor_mgdl_per_unit=params["correction_factor_mgdl_per_unit"],
                microbolus_fraction=params["microbolus_fraction"],
                min_excursion_delta_mgdl=params["min_excursion_delta_mgdl"],
            )

            n_steps = summary.total_timesteps or 1
            tir_pct = summary.percent_time_in_range
            below_pct = (summary.time_below_range_steps / n_steps) * 100.0
            above250_pct = (summary.time_above_250_steps / n_steps) * 100.0

            fitness = (
                -tir_pct
                + config.hypo_penalty_weight * below_pct
                + config.peak_penalty_weight * above250_pct
            )
            total_fitness += fitness
            n_runs += 1

    return total_fitness / max(1, n_runs)


def params_to_tir(params: dict[str, float], config: PSOConfig) -> float:
    """Return mean TIR (%) for a candidate — used for display purposes."""
    safety = SafetyThresholds(
        max_units_per_interval=params["max_units_per_interval"],
        max_insulin_on_board_u=params["max_insulin_on_board_u"],
        min_predicted_glucose_mgdl=params["min_predicted_glucose_mgdl"],
    )

    total_tir = 0.0
    n_runs = 0

    for scenario_name in config.scenario_names:
        base_scenario = NAMED_SCENARIOS[scenario_name]

        for profile in ALL_PROFILES:
            scenario = SimulationInputs(
                insulin_sensitivity_mgdl_per_unit=profile.insulin_sensitivity_mgdl_per_unit,
                carb_impact_mgdl_per_g=profile.carb_impact_mgdl_per_g,
                baseline_drift_mgdl_per_step=base_scenario.baseline_drift_mgdl_per_step,
                meal_events=copy.deepcopy(base_scenario.meal_events),
                insulin_peak_minutes=profile.insulin_peak_minutes,
            )

            _records, summary = run_closed_loop_evaluation(
                simulation_inputs=scenario,
                safety_thresholds=safety,
                duration_minutes=config.duration_minutes,
                step_minutes=config.step_minutes,
                target_glucose_mgdl=params["target_glucose_mgdl"],
                correction_factor_mgdl_per_unit=params["correction_factor_mgdl_per_unit"],
                microbolus_fraction=params["microbolus_fraction"],
                min_excursion_delta_mgdl=params["min_excursion_delta_mgdl"],
            )

            total_tir += summary.percent_time_in_range
            n_runs += 1

    return total_tir / max(1, n_runs)
