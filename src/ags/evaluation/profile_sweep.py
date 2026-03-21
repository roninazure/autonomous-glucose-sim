"""Profile sweep: run a single scenario across all patient archetypes.

This is the population-level validation step — confirming the control algorithm
achieves acceptable outcomes not only for the median patient (Standard Adult) but
across the full range of physiological variability represented by the four
archetypes in ``profiles.ALL_PROFILES``.

Usage::

    from ags.evaluation.profile_sweep import run_profile_sweep
    from ags.simulation.scenarios import baseline_meal_scenario

    results = run_profile_sweep(
        base_scenario=baseline_meal_scenario(),
        scenario_name="Baseline Meal",
        ...
    )
    # results: list of SweepResult, one per patient profile
"""
from __future__ import annotations

import copy
from dataclasses import dataclass

from ags.evaluation.profiles import ALL_PROFILES, PatientProfile
from ags.evaluation.report import generate_report
from ags.evaluation.runner import run_evaluation
from ags.evaluation.state import RunSummary, TimestepRecord
from ags.pump.state import DualWaveConfig, PumpConfig
from ags.safety.state import SafetyThresholds
from ags.simulation.state import SimulationInputs


@dataclass
class SweepResult:
    profile: PatientProfile
    records: list[TimestepRecord]
    summary: RunSummary
    report: dict


def run_profile_sweep(
    base_scenario: SimulationInputs,
    scenario_name: str,
    safety_thresholds: SafetyThresholds | None = None,
    pump_config: PumpConfig | None = None,
    duration_minutes: int = 180,
    step_minutes: int = 5,
    seed: int = 42,
    target_glucose_mgdl: float = 110.0,
    correction_factor_mgdl_per_unit: float = 50.0,
    min_excursion_delta_mgdl: float = 0.0,
    microbolus_fraction: float = 1.0,
    ror_tiered_microbolus: bool = False,
    autonomous_isf: bool = False,
    dual_wave_config: DualWaveConfig | None = None,
    profiles: list[PatientProfile] | None = None,
) -> list[SweepResult]:
    """Run ``base_scenario`` once per patient profile and return all results.

    Each profile overrides the three physiological parameters on the scenario
    (ISF, carb impact, insulin peak time) while preserving the scenario's meal
    events and drift — so differences in outcome are purely attributable to
    inter-patient variability, not scenario differences.
    """
    safety_thresholds = safety_thresholds or SafetyThresholds()
    pump_config = pump_config or PumpConfig()
    profiles = profiles if profiles is not None else ALL_PROFILES

    sweep_results: list[SweepResult] = []

    for profile in profiles:
        # Derive a per-profile simulation by patching physiological params only
        profile_inputs = SimulationInputs(
            insulin_sensitivity_mgdl_per_unit=profile.insulin_sensitivity_mgdl_per_unit,
            carb_impact_mgdl_per_g=profile.carb_impact_mgdl_per_g,
            baseline_drift_mgdl_per_step=base_scenario.baseline_drift_mgdl_per_step,
            meal_events=copy.deepcopy(base_scenario.meal_events),
            insulin_peak_minutes=profile.insulin_peak_minutes,
        )

        records, summary = run_evaluation(
            simulation_inputs=profile_inputs,
            safety_thresholds=safety_thresholds,
            pump_config=pump_config,
            duration_minutes=duration_minutes,
            step_minutes=step_minutes,
            seed=seed,
            target_glucose_mgdl=target_glucose_mgdl,
            correction_factor_mgdl_per_unit=correction_factor_mgdl_per_unit,
            min_excursion_delta_mgdl=min_excursion_delta_mgdl,
            microbolus_fraction=microbolus_fraction,
            ror_tiered_microbolus=ror_tiered_microbolus,
            autonomous_isf=autonomous_isf,
            dual_wave_config=dual_wave_config,
        )

        report = generate_report(
            scenario_name=f"{scenario_name} · {profile.name}",
            summary=summary,
            duration_minutes=duration_minutes,
            step_minutes=step_minutes,
            safety_thresholds=safety_thresholds,
            pump_config=pump_config,
            target_glucose_mgdl=target_glucose_mgdl,
            correction_factor_mgdl_per_unit=correction_factor_mgdl_per_unit,
            min_excursion_delta_mgdl=min_excursion_delta_mgdl,
            microbolus_fraction=microbolus_fraction,
        )

        sweep_results.append(SweepResult(
            profile=profile,
            records=records,
            summary=summary,
            report=report,
        ))

    return sweep_results


def build_sweep_export(
    scenario_name: str,
    sweep_results: list[SweepResult],
) -> dict:
    """Build a combined JSON-serialisable export for all profiles in the sweep."""
    all_pass = all(r.report["verdicts"]["overall_pass"] for r in sweep_results)
    return {
        "export_type": "profile_sweep",
        "scenario": scenario_name,
        "population_pass": all_pass,
        "profile_count": len(sweep_results),
        "profiles": [r.report for r in sweep_results],
    }
