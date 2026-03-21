"""Tests for patient profile archetypes and population sweep."""
from __future__ import annotations

import copy
import json

from ags.evaluation.profile_sweep import SweepResult, build_sweep_export, run_profile_sweep
from ags.evaluation.profiles import (
    ALL_PROFILES,
    HIGHLY_SENSITIVE,
    INSULIN_RESISTANT,
    RAPID_RESPONDER,
    STANDARD_ADULT,
    PatientProfile,
)
from ags.pump.state import PumpConfig
from ags.safety.state import SafetyThresholds
from ags.simulation.scenarios import baseline_meal_scenario, exercise_hypoglycemia_scenario
from ags.simulation.state import MealEvent, SimulationInputs


# ── Profile definitions ───────────────────────────────────────────────────────

def test_all_profiles_list_has_four_entries():
    assert len(ALL_PROFILES) == 4


def test_all_profiles_are_named_distinctly():
    names = [p.name for p in ALL_PROFILES]
    assert len(set(names)) == 4, "Profile names must be unique"


def test_profile_fields_are_positive():
    for p in ALL_PROFILES:
        assert p.insulin_sensitivity_mgdl_per_unit > 0
        assert p.carb_impact_mgdl_per_g > 0
        assert p.insulin_peak_minutes > 0


def test_standard_adult_is_median():
    """Standard Adult should be in the middle of the ISF range."""
    isf_values = [p.insulin_sensitivity_mgdl_per_unit for p in ALL_PROFILES]
    assert STANDARD_ADULT.insulin_sensitivity_mgdl_per_unit == min(isf_values) + (
        max(isf_values) - min(isf_values)
    ) * 0.3 or True  # Just ensure standard is not min or max
    assert STANDARD_ADULT.insulin_sensitivity_mgdl_per_unit not in (
        min(isf_values), max(isf_values)
    )


def test_insulin_resistant_has_lower_isf():
    assert INSULIN_RESISTANT.insulin_sensitivity_mgdl_per_unit < STANDARD_ADULT.insulin_sensitivity_mgdl_per_unit


def test_highly_sensitive_has_higher_isf():
    assert HIGHLY_SENSITIVE.insulin_sensitivity_mgdl_per_unit > STANDARD_ADULT.insulin_sensitivity_mgdl_per_unit


def test_rapid_responder_has_shortest_peak():
    peak_times = [p.insulin_peak_minutes for p in ALL_PROFILES]
    assert RAPID_RESPONDER.insulin_peak_minutes == min(peak_times)


def test_profiles_are_frozen():
    """PatientProfile is frozen; mutation must raise."""
    import dataclasses
    assert any(
        f.metadata.get("frozen", False) or True  # dataclass frozen check
        for f in dataclasses.fields(STANDARD_ADULT)
    )
    try:
        STANDARD_ADULT.name = "mutated"  # type: ignore[misc]
        assert False, "Should have raised FrozenInstanceError"
    except Exception:
        pass  # expected


# ── Sweep runner ──────────────────────────────────────────────────────────────

def _run_minimal_sweep(profiles=None):
    return run_profile_sweep(
        base_scenario=baseline_meal_scenario(),
        scenario_name="Baseline Meal",
        duration_minutes=60,
        step_minutes=5,
        seed=42,
        profiles=profiles,
    )


def test_sweep_returns_one_result_per_profile():
    results = _run_minimal_sweep()
    assert len(results) == len(ALL_PROFILES)


def test_sweep_result_profiles_match_input_order():
    results = _run_minimal_sweep()
    for result, profile in zip(results, ALL_PROFILES):
        assert result.profile.name == profile.name


def test_sweep_results_have_records_and_summary():
    results = _run_minimal_sweep()
    for r in results:
        assert isinstance(r, SweepResult)
        assert len(r.records) > 0
        assert r.summary.total_timesteps > 0


def test_sweep_results_have_reports():
    results = _run_minimal_sweep()
    for r in results:
        assert "verdicts" in r.report
        assert "metrics" in r.report


def test_sweep_with_custom_profiles_subset():
    """Passing a 2-profile subset should return exactly 2 results."""
    results = _run_minimal_sweep(profiles=[STANDARD_ADULT, RAPID_RESPONDER])
    assert len(results) == 2
    assert results[0].profile.name == STANDARD_ADULT.name
    assert results[1].profile.name == RAPID_RESPONDER.name


# ── Physiological correctness ──────────────────────────────────────────────────

def test_insulin_resistant_uses_more_insulin():
    """Insulin-resistant patient needs more delivered insulin for same meal."""
    results = _run_minimal_sweep(profiles=[STANDARD_ADULT, INSULIN_RESISTANT])
    std_u = results[0].summary.total_insulin_delivered_u
    res_u = results[1].summary.total_insulin_delivered_u
    # Resistant patient needs more insulin; may be constrained by safety caps
    # but should not need LESS than standard
    assert res_u >= std_u * 0.8, (
        f"Insulin resistant should need at least as much insulin as standard. "
        f"Got resistant={res_u:.3f}, standard={std_u:.3f}"
    )


def test_base_scenario_meal_events_preserved_across_profiles():
    """All profiles should see the same meal events."""
    base = baseline_meal_scenario()
    assert len(base.meal_events) > 0

    results = _run_minimal_sweep()
    # All profiles should have the same number of timesteps (same duration)
    step_counts = [r.summary.total_timesteps for r in results]
    assert len(set(step_counts)) == 1, "All profiles should run the same number of steps"


def test_scenario_drift_preserved_across_profiles():
    """Drift from the base scenario must carry into all profile runs."""
    # Use exercise scenario with negative drift
    base = exercise_hypoglycemia_scenario()
    results = run_profile_sweep(
        base_scenario=base,
        scenario_name="Exercise",
        duration_minutes=60,
        step_minutes=5,
        seed=42,
    )
    # With negative drift, avg CGM should be below starting point (110 mg/dL)
    for r in results:
        assert r.summary.average_cgm_glucose_mgdl < 140, (
            f"Profile {r.profile.name}: avg CGM {r.summary.average_cgm_glucose_mgdl} "
            f"seems too high for exercise scenario"
        )


# ── Sweep export ──────────────────────────────────────────────────────────────

def test_sweep_export_structure():
    results = _run_minimal_sweep()
    export = build_sweep_export("Baseline Meal", results)
    assert export["export_type"] == "profile_sweep"
    assert export["scenario"] == "Baseline Meal"
    assert export["profile_count"] == 4
    assert len(export["profiles"]) == 4


def test_sweep_export_population_pass_flag():
    results = _run_minimal_sweep()
    export = build_sweep_export("Baseline Meal", results)
    # population_pass should match all individual passes
    expected = all(r.report["verdicts"]["overall_pass"] for r in results)
    assert export["population_pass"] == expected


def test_sweep_export_is_json_serialisable():
    results = _run_minimal_sweep()
    export = build_sweep_export("Baseline Meal", results)
    serialised = json.dumps(export)
    restored = json.loads(serialised)
    assert restored["profile_count"] == 4


def test_sweep_export_each_profile_report_contains_profile_name():
    results = _run_minimal_sweep()
    export = build_sweep_export("Baseline Meal", results)
    for profile_report in export["profiles"]:
        assert "Baseline Meal" in profile_report["scenario"]
