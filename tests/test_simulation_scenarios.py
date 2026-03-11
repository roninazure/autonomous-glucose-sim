from ags.simulation.scenarios import baseline_meal_scenario


def test_baseline_meal_scenario_contains_expected_meal() -> None:
    inputs = baseline_meal_scenario()

    assert inputs.insulin_sensitivity_mgdl_per_unit == 50.0
    assert inputs.carb_impact_mgdl_per_g == 3.0
    assert len(inputs.meal_events) == 1

    meal = inputs.meal_events[0]
    assert meal.timestamp_min == 30
    assert meal.carbs_g == 45.0
    assert meal.absorption_minutes == 120
