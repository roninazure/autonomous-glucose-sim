"""Particle Swarm Optimisation (PSO) for SWARM Bolus controller tuning.

Standard inertia-weight PSO (Kennedy & Eberhart, 1995) with velocity clamping,
hard bound enforcement, and **true parallel particle evaluation**.

    Each *particle* is a vector of controller/safety parameters.
    Each *iteration* all particles:
      1. Evaluate their fitness IN PARALLEL via concurrent.futures
      2. Update personal-best and global-best
      3. Update velocity:  v = w*v + c1*r1*(pbest-x) + c2*r2*(gbest-x)
      4. Update position:  x = x + v  (clamped to bounds)

Parallelism: all n_particles fitness evaluations within each iteration are
submitted simultaneously to a ProcessPoolExecutor.  Each worker runs a
complete closed-loop simulation independently — no shared state, no locks.
On a 4-core machine this cuts wall-clock time by ~4×.

Fitness is minimised (negative TIR + hypo/peak penalties — see fitness.py).

Usage::

    from ags.optimization.pso import run_pso
    from ags.optimization.state import PSOConfig

    result = run_pso(PSOConfig(n_particles=20, n_iterations=30))
    print(result.best_params)
    print(f"Best TIR: {result.best_tir_pct:.1f}%")
"""
from __future__ import annotations

import random
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Callable

from ags.optimization.fitness import evaluate_candidate
from ags.optimization.state import (
    PARAMETER_BOUNDS,
    PSOBounds,
    PSOConfig,
    PSOIteration,
    PSOResult,
)


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _random_position(bounds: list[PSOBounds], rng: random.Random) -> list[float]:
    return [rng.uniform(b.low, b.high) for b in bounds]


def _random_velocity(bounds: list[PSOBounds], rng: random.Random) -> list[float]:
    """Initialise velocity as ±50 % of the parameter range."""
    return [rng.uniform(-(b.high - b.low) * 0.5, (b.high - b.low) * 0.5) for b in bounds]


def _vec_to_params(vec: list[float], bounds: list[PSOBounds]) -> dict[str, float]:
    return {b.name: vec[i] for i, b in enumerate(bounds)}


def run_pso(
    config: PSOConfig | None = None,
    progress_callback: Callable[[int, int, float, float], None] | None = None,
) -> PSOResult:
    """Run PSO and return the best parameter set found.

    Args:
        config: PSO hyperparameters. Uses defaults if None.
        progress_callback: Optional callable(iteration, total, best_fitness,
            best_tir) called after each iteration — useful for live progress
            bars in Streamlit.

    Returns:
        PSOResult with best_params, best_fitness, convergence history, etc.
    """
    config = config or PSOConfig()
    rng = random.Random(config.seed)
    bounds = PARAMETER_BOUNDS
    n_dims = len(bounds)

    # ── Initialise swarm ─────────────────────────────────────────────────────
    positions: list[list[float]] = [_random_position(bounds, rng) for _ in range(config.n_particles)]
    velocities: list[list[float]] = [_random_velocity(bounds, rng) for _ in range(config.n_particles)]
    pbest_pos: list[list[float]] = [list(p) for p in positions]
    pbest_fit: list[float] = [float("inf")] * config.n_particles

    gbest_pos: list[float] = list(positions[0])
    gbest_fit: float = float("inf")
    gbest_tir: float = 0.0

    history: list[PSOIteration] = []
    n_evaluations = 0

    # ── Velocity clamp: ±20 % of range ───────────────────────────────────────
    v_max = [(b.high - b.low) * 0.20 for b in bounds]

    for iteration in range(config.n_iterations):
        fitnesses: list[float] = [0.0] * config.n_particles

        # ── True parallel swarm: all particles evaluated simultaneously ──────
        # Each worker is an independent process — no GIL, no shared state.
        # Futures are keyed by particle index so results map back correctly.
        particle_params = [_vec_to_params(positions[i], bounds) for i in range(config.n_particles)]

        with ProcessPoolExecutor() as executor:
            future_to_idx = {
                executor.submit(evaluate_candidate, particle_params[i], config): i
                for i in range(config.n_particles)
            }
            for future in as_completed(future_to_idx):
                i = future_to_idx[future]
                fitnesses[i] = future.result()
                n_evaluations += 1

        for i in range(config.n_particles):
            fitness = fitnesses[i]

            # Update personal best
            if fitness < pbest_fit[i]:
                pbest_fit[i] = fitness
                pbest_pos[i] = list(positions[i])

            # Update global best
            if fitness < gbest_fit:
                gbest_fit = fitness
                gbest_pos = list(positions[i])
                gbest_tir = min(100.0, max(0.0, -fitness))

        # ── Update velocities and positions ──────────────────────────────────
        for i in range(config.n_particles):
            for d in range(n_dims):
                r1 = rng.random()
                r2 = rng.random()
                cognitive = config.c1 * r1 * (pbest_pos[i][d] - positions[i][d])
                social    = config.c2 * r2 * (gbest_pos[d]     - positions[i][d])
                velocities[i][d] = (
                    config.w * velocities[i][d] + cognitive + social
                )
                # Clamp velocity
                velocities[i][d] = _clip(velocities[i][d], -v_max[d], v_max[d])
                # Move particle
                positions[i][d] = _clip(
                    positions[i][d] + velocities[i][d],
                    bounds[d].low,
                    bounds[d].high,
                )

        mean_fitness = sum(fitnesses) / len(fitnesses)
        snap = PSOIteration(
            iteration=iteration + 1,
            best_fitness=gbest_fit,
            best_tir_pct=gbest_tir,
            mean_fitness=mean_fitness,
        )
        history.append(snap)

        if progress_callback:
            progress_callback(iteration + 1, config.n_iterations, gbest_fit, gbest_tir)

    best_params = _vec_to_params(gbest_pos, bounds)

    return PSOResult(
        best_params=best_params,
        best_fitness=gbest_fit,
        best_tir_pct=gbest_tir,
        history=history,
        n_evaluations=n_evaluations,
    )
