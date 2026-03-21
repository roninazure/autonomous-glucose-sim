"""Tests for the four new clinical scenarios."""
from __future__ import annotations

import pytest

from ags.simulation.scenarios import (
    dawn_phenomenon_scenario,
    exercise_hypoglycemia_scenario,
    late_correction_scenario,
    missed_bolus_scenario,
)
from ags.simulation.engine import run_simulation


def test_dawn_phenomenon_has_no_meals():
    inputs = dawn_phenomenon_scenario()
    assert inputs.meal_events == []


def test_dawn_phenomenon_positive_drift():
    inputs = dawn_phenomenon_scenario()
    assert inputs.baseline_drift_mgdl_per_step > 0, "Dawn scenario must have positive drift"


def test_dawn_phenomenon_glucose_rises():
    inputs = dawn_phenomenon_scenario()
    snapshots = run_simulation(inputs, duration_minutes=120, step_minutes=5)
    # Glucose should be higher at end than start because of cortisol drift
    assert snapshots[-1].true_glucose_mgdl > snapshots[0].true_glucose_mgdl


def test_exercise_hypo_has_no_meals():
    inputs = exercise_hypoglycemia_scenario()
    assert inputs.meal_events == []


def test_exercise_hypo_negative_drift():
    inputs = exercise_hypoglycemia_scenario()
    assert inputs.baseline_drift_mgdl_per_step < 0, "Exercise scenario must have negative drift"


def test_exercise_hypo_glucose_falls():
    inputs = exercise_hypoglycemia_scenario()
    snapshots = run_simulation(inputs, duration_minutes=60, step_minutes=5)
    assert snapshots[-1].true_glucose_mgdl < snapshots[0].true_glucose_mgdl


def test_exercise_hypo_elevated_isf():
    """Exercise amplifies insulin sensitivity — ISF should be higher than baseline."""
    from ags.simulation.scenarios import baseline_meal_scenario
    baseline = baseline_meal_scenario()
    exercise = exercise_hypoglycemia_scenario()
    assert exercise.insulin_sensitivity_mgdl_per_unit > baseline.insulin_sensitivity_mgdl_per_unit


def test_missed_bolus_large_early_meal():
    inputs = missed_bolus_scenario()
    assert len(inputs.meal_events) == 1
    meal = inputs.meal_events[0]
    assert meal.carbs_g >= 70, "Missed bolus scenario requires a large meal"
    assert meal.timestamp_min <= 15, "Meal should arrive early to create spike before controller reacts"


def test_missed_bolus_produces_glucose_spike():
    inputs = missed_bolus_scenario()
    snapshots = run_simulation(inputs, duration_minutes=120, step_minutes=5)
    peak = max(s.true_glucose_mgdl for s in snapshots)
    assert peak > 180, "Missed bolus should produce a hyperglycemic spike"


def test_late_correction_two_meals():
    inputs = late_correction_scenario()
    assert len(inputs.meal_events) == 2


def test_late_correction_second_meal_is_snack():
    inputs = late_correction_scenario()
    meals = sorted(inputs.meal_events, key=lambda m: m.timestamp_min)
    assert meals[1].carbs_g < meals[0].carbs_g, "Second meal should be smaller snack"


def test_late_correction_produces_extended_excursion():
    inputs = late_correction_scenario()
    snapshots = run_simulation(inputs, duration_minutes=180, step_minutes=5)
    above_180 = sum(1 for s in snapshots if s.true_glucose_mgdl > 180)
    assert above_180 > 0, "Late correction scenario should produce some hyperglycemic time"
