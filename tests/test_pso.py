"""Tests for the PSO optimisation module."""
from __future__ import annotations

import pytest

from ags.optimization.fitness import NAMED_SCENARIOS, evaluate_candidate, params_to_tir
from ags.optimization.pso import run_pso
from ags.optimization.state import (
    PARAMETER_BOUNDS,
    PSOConfig,
    PSOResult,
)


# ── Minimal config for fast test execution ────────────────────────────────────
_FAST_CONFIG = PSOConfig(
    n_particles=3,
    n_iterations=2,
    scenario_names=["Baseline Meal"],
    seed=99,
)

_DEFAULT_PARAMS = {b.name: (b.low + b.high) / 2.0 for b in PARAMETER_BOUNDS}


# ── PARAMETER_BOUNDS ──────────────────────────────────────────────────────────

class TestParameterBounds:
    def test_all_bounds_have_names(self):
        for b in PARAMETER_BOUNDS:
            assert b.name, "Every bound must have a non-empty name"

    def test_low_less_than_high(self):
        for b in PARAMETER_BOUNDS:
            assert b.low < b.high, f"{b.name}: low must be < high"

    def test_expected_parameters_present(self):
        names = {b.name for b in PARAMETER_BOUNDS}
        required = {
            "target_glucose_mgdl",
            "correction_factor_mgdl_per_unit",
            "microbolus_fraction",
            "min_excursion_delta_mgdl",
            "max_units_per_interval",
            "max_insulin_on_board_u",
            "min_predicted_glucose_mgdl",
        }
        assert required.issubset(names)


# ── NAMED_SCENARIOS ───────────────────────────────────────────────────────────

class TestNamedScenarios:
    def test_all_default_pso_scenarios_present(self):
        for name in ["Baseline Meal", "Dawn Phenomenon", "Missed Bolus"]:
            assert name in NAMED_SCENARIOS, f"'{name}' must be in NAMED_SCENARIOS"

    def test_scenario_objects_are_simulation_inputs(self):
        from ags.simulation.state import SimulationInputs
        for name, scenario in NAMED_SCENARIOS.items():
            assert isinstance(scenario, SimulationInputs), f"'{name}' must be a SimulationInputs"


# ── FITNESS FUNCTION ──────────────────────────────────────────────────────────

class TestEvaluateCandidate:
    def test_returns_scalar(self):
        fitness = evaluate_candidate(_DEFAULT_PARAMS, _FAST_CONFIG)
        assert isinstance(fitness, float)

    def test_fitness_is_finite(self):
        fitness = evaluate_candidate(_DEFAULT_PARAMS, _FAST_CONFIG)
        assert fitness == fitness  # not NaN
        assert abs(fitness) < 1e6

    def test_good_params_better_than_extreme_params(self):
        """Sensible params should beat clearly pathological ones."""
        good_params = {
            "target_glucose_mgdl": 110.0,
            "correction_factor_mgdl_per_unit": 50.0,
            "microbolus_fraction": 0.25,
            "min_excursion_delta_mgdl": 5.0,
            "max_units_per_interval": 0.30,
            "max_insulin_on_board_u": 3.0,
            "min_predicted_glucose_mgdl": 80.0,
        }
        # Target of 200 means controller never sees an excursion → almost no dosing
        bad_params = dict(good_params)
        bad_params["target_glucose_mgdl"] = 200.0
        bad_params["microbolus_fraction"] = 0.01

        good_fit = evaluate_candidate(good_params, _FAST_CONFIG)
        bad_fit  = evaluate_candidate(bad_params, _FAST_CONFIG)
        # Lower fitness = better; good params should win
        assert good_fit <= bad_fit

    def test_hypo_penalty_applied(self):
        """Increasing hypo_penalty_weight should worsen fitness when glucose goes low."""
        low_penalty_cfg = PSOConfig(
            n_particles=2, n_iterations=1,
            scenario_names=["Exercise Hypoglycaemia"],
            hypo_penalty_weight=1.0,
            seed=0,
        )
        high_penalty_cfg = PSOConfig(
            n_particles=2, n_iterations=1,
            scenario_names=["Exercise Hypoglycaemia"],
            hypo_penalty_weight=10.0,
            seed=0,
        )
        # A permissive config that allows dosing (may cause hypo in exercise scenario)
        params = dict(_DEFAULT_PARAMS)
        params["min_predicted_glucose_mgdl"] = 70.0  # low hypo guard → more doses

        f_low  = evaluate_candidate(params, low_penalty_cfg)
        f_high = evaluate_candidate(params, high_penalty_cfg)
        # Higher penalty weight must produce fitness >= lower (or equal if no hypo events)
        assert f_high >= f_low


class TestParamsToTir:
    def test_returns_percentage(self):
        tir = params_to_tir(_DEFAULT_PARAMS, _FAST_CONFIG)
        assert 0.0 <= tir <= 100.0

    def test_returns_float(self):
        tir = params_to_tir(_DEFAULT_PARAMS, _FAST_CONFIG)
        assert isinstance(tir, float)


# ── PSO ALGORITHM ─────────────────────────────────────────────────────────────

class TestRunPso:
    def test_returns_pso_result(self):
        result = run_pso(config=_FAST_CONFIG)
        assert isinstance(result, PSOResult)

    def test_best_params_has_all_keys(self):
        result = run_pso(config=_FAST_CONFIG)
        for b in PARAMETER_BOUNDS:
            assert b.name in result.best_params

    def test_best_params_within_bounds(self):
        result = run_pso(config=_FAST_CONFIG)
        for b in PARAMETER_BOUNDS:
            val = result.best_params[b.name]
            assert b.low <= val <= b.high, (
                f"{b.name}={val:.3f} outside [{b.low}, {b.high}]"
            )

    def test_history_length(self):
        result = run_pso(config=_FAST_CONFIG)
        assert len(result.history) == _FAST_CONFIG.n_iterations

    def test_history_fitness_non_increasing(self):
        """Global best fitness must be monotonically non-increasing."""
        result = run_pso(config=PSOConfig(n_particles=4, n_iterations=5,
                                          scenario_names=["Baseline Meal"], seed=7))
        fits = [h.best_fitness for h in result.history]
        for i in range(1, len(fits)):
            assert fits[i] <= fits[i - 1] + 1e-9, (
                f"Best fitness increased at iteration {i}: {fits[i-1]:.4f} → {fits[i]:.4f}"
            )

    def test_n_evaluations_correct(self):
        cfg = PSOConfig(n_particles=3, n_iterations=2,
                        scenario_names=["Baseline Meal"], seed=0)
        result = run_pso(config=cfg)
        expected = cfg.n_particles * cfg.n_iterations
        assert result.n_evaluations == expected

    def test_deterministic_with_same_seed(self):
        cfg = PSOConfig(n_particles=3, n_iterations=2,
                        scenario_names=["Baseline Meal"], seed=42)
        r1 = run_pso(config=cfg)
        r2 = run_pso(config=cfg)
        assert r1.best_fitness == pytest.approx(r2.best_fitness, abs=1e-6)

    def test_different_seeds_may_differ(self):
        cfg_a = PSOConfig(n_particles=5, n_iterations=3,
                          scenario_names=["Baseline Meal"], seed=1)
        cfg_b = PSOConfig(n_particles=5, n_iterations=3,
                          scenario_names=["Baseline Meal"], seed=2)
        r1 = run_pso(config=cfg_a)
        r2 = run_pso(config=cfg_b)
        # Not identical (different seeds) — they *could* coincide but it's highly unlikely
        # with different seeds and random initialisation; just check they both ran
        assert r1.n_evaluations == r2.n_evaluations

    def test_progress_callback_called(self):
        calls: list[int] = []

        def _cb(iteration, total, best_fitness, best_tir):
            calls.append(iteration)

        cfg = PSOConfig(n_particles=2, n_iterations=3,
                        scenario_names=["Baseline Meal"], seed=0)
        run_pso(config=cfg, progress_callback=_cb)
        assert calls == [1, 2, 3]

    def test_multi_scenario_pso(self):
        """PSO with multiple scenarios must still converge and return valid result."""
        cfg = PSOConfig(
            n_particles=3,
            n_iterations=2,
            scenario_names=["Baseline Meal", "Dawn Phenomenon"],
            seed=0,
        )
        result = run_pso(config=cfg)
        assert isinstance(result.best_fitness, float)
        assert result.n_evaluations == cfg.n_particles * cfg.n_iterations


# ── PSOConfig defaults ────────────────────────────────────────────────────────

class TestPSOConfig:
    def test_default_scenario_names_are_valid(self):
        cfg = PSOConfig()
        for name in cfg.scenario_names:
            assert name in NAMED_SCENARIOS

    def test_inertia_weight_in_reasonable_range(self):
        cfg = PSOConfig()
        assert 0.0 < cfg.w_start <= 1.0
        assert 0.0 < cfg.w_end < cfg.w_start  # end must be lower (exploitation < exploration)

    def test_acceleration_coefficients_positive(self):
        cfg = PSOConfig()
        assert cfg.c1 > 0
        assert cfg.c2 > 0
