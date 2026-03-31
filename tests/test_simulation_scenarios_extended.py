"""Tests for the four new clinical scenarios."""
from __future__ import annotations

import pytest

from ags.simulation.scenarios import (
    dawn_phenomenon_scenario,
    exercise_hypoglycemia_scenario,
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


