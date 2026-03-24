"""Particle Swarm Optimisation (PSO) for SWARM Bolus controller tuning.

Adaptive inertia-weight PSO with ring topology (lbest):
  - Linearly decaying inertia w: 0.9 → 0.4 over the run
      Wide exploration early, tight exploitation late.
  - Ring (lbest) topology — each particle's social attractor is the best
      position seen by its immediate ring-neighbours {i-1, i, i+1}.
      This prevents the premature convergence caused by global (gbest) topology,
      where a single good particle instantly collapses the whole swarm onto one
      point.  Knowledge spreads gradually around the ring; diversity is
      maintained throughout the run.
  - Velocity clamping and hard bound enforcement
  - True parallel particle evaluation via a persistent ProcessPoolExecutor

    Each *particle* is a vector of controller/safety parameters.
    Each *iteration* all particles:
      1. Compute adaptive inertia weight w(t)
      2. Evaluate ALL particles IN PARALLEL (persistent process pool)
      3. Update personal-best (pbest) for each particle
      4. Update ring-neighbourhood-best (lbest[i]) from {i-1, i, i+1} pbests
      5. Update velocity:  v = w(t)*v + c1*r1*(pbest-x) + c2*r2*(lbest-x)
      6. Update position:  x = x + v  (clamped to bounds)

Parallelism: one ProcessPoolExecutor is created for the full run (not per
iteration) so process spawn overhead is paid once.  All n_particles
evaluations per iteration are submitted simultaneously — each worker runs a
complete closed-loop simulation independently with no shared state.

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
    n = config.n_particles

    # ── Initialise swarm ─────────────────────────────────────────────────────
    positions: list[list[float]] = [_random_position(bounds, rng) for _ in range(n)]
    velocities: list[list[float]] = [_random_velocity(bounds, rng) for _ in range(n)]
    pbest_pos: list[list[float]] = [list(p) for p in positions]
    pbest_fit: list[float] = [float("inf")] * n

    # Ring-topology neighbourhood best — initialised to each particle's own position.
    # Recomputed each iteration from the three-member neighbourhood {i-1, i, i+1}.
    lbest_pos: list[list[float]] = [list(p) for p in positions]
    lbest_fit: list[float] = [float("inf")] * n

    # Global best — tracked separately for result reporting only, not used as
    # the social attractor (that role belongs to lbest).
    gbest_pos: list[float] = list(positions[0])
    gbest_fit: float = float("inf")
    gbest_tir: float = 0.0

    history: list[PSOIteration] = []
    n_evaluations = 0

    # ── Velocity clamp: ±20 % of range ───────────────────────────────────────
    v_max = [(b.high - b.low) * 0.20 for b in bounds]

    # ── One persistent pool for the full run — spawn overhead paid once ───────
    with ProcessPoolExecutor() as executor:
        for iteration in range(config.n_iterations):
            fitnesses: list[float] = [0.0] * n

            # ── Adaptive inertia weight (Shi & Eberhart 1998) ─────────────────
            # Decays linearly: wide exploration early, tight exploitation late.
            if config.n_iterations > 1:
                w = config.w_start - (config.w_start - config.w_end) * iteration / (config.n_iterations - 1)
            else:
                w = config.w_start

            # ── True parallel swarm: all particles evaluated simultaneously ───
            particle_params = [_vec_to_params(positions[i], bounds) for i in range(n)]
            future_to_idx = {
                executor.submit(evaluate_candidate, particle_params[i], config): i
                for i in range(n)
            }
            for future in as_completed(future_to_idx):
                i = future_to_idx[future]
                fitnesses[i] = future.result()
                n_evaluations += 1

            # ── Update personal-best and global-best (for reporting) ──────────
            for i in range(n):
                fitness = fitnesses[i]
                if fitness < pbest_fit[i]:
                    pbest_fit[i] = fitness
                    pbest_pos[i] = list(positions[i])
                if fitness < gbest_fit:
                    gbest_fit = fitness
                    gbest_pos = list(positions[i])
                    gbest_tir = min(100.0, max(0.0, -fitness))

            # ── Update ring-neighbourhood best (lbest) ────────────────────────
            # Each particle's social attractor = best pbest in {i-1, i, i+1}.
            # Using lbest instead of gbest maintains swarm diversity: no single
            # discovery instantly pulls every particle away from its local search.
            for i in range(n):
                for nb in ((i - 1) % n, i, (i + 1) % n):
                    if pbest_fit[nb] < lbest_fit[i]:
                        lbest_fit[i] = pbest_fit[nb]
                        lbest_pos[i] = list(pbest_pos[nb])

            # ── Update velocities and positions ──────────────────────────────
            for i in range(n):
                for d in range(n_dims):
                    r1 = rng.random()
                    r2 = rng.random()
                    cognitive = config.c1 * r1 * (pbest_pos[i][d] - positions[i][d])
                    social    = config.c2 * r2 * (lbest_pos[i][d] - positions[i][d])
                    velocities[i][d] = (
                        w * velocities[i][d] + cognitive + social
                    )
                    velocities[i][d] = _clip(velocities[i][d], -v_max[d], v_max[d])
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
