"""Data classes for PSO configuration and results."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PSOBounds:
    """Bounds for a single optimisable parameter."""
    name: str
    low: float
    high: float
    description: str = ""


# ── Canonical search space ────────────────────────────────────────────────────
# Each entry is one dimension of the PSO particle vector.
PARAMETER_BOUNDS: list[PSOBounds] = [
    PSOBounds("target_glucose_mgdl",              90.0,  140.0, "Controller glucose target (mg/dL)"),
    PSOBounds("correction_factor_mgdl_per_unit",  25.0,  100.0, "ISF — mg/dL drop per unit"),
    PSOBounds("microbolus_fraction",               0.05,   1.0,  "Fraction of correction delivered per step"),
    PSOBounds("min_excursion_delta_mgdl",          0.0,   30.0,  "Minimum excursion to trigger a dose (mg/dL)"),
    PSOBounds("max_units_per_interval",            0.10,   0.50, "Safety: max bolus per 5-min step (U)"),
    PSOBounds("max_insulin_on_board_u",            1.0,    6.0,  "Safety: IOB cap (U)"),
    PSOBounds("min_predicted_glucose_mgdl",       70.0,  100.0,  "Safety: hypo guard threshold (mg/dL)"),
]


@dataclass
class PSOConfig:
    """Hyperparameters for the PSO run."""
    n_particles: int = 20
    n_iterations: int = 30
    w_start: float = 0.90  # inertia at iteration 0 — wide exploration
    w_end: float   = 0.40  # inertia at final iteration — tight exploitation
    # w decays linearly: w(t) = w_start - (w_start - w_end) * t / (n_iterations - 1)
    c1: float = 1.49       # cognitive (personal best) acceleration
    c2: float = 1.49       # social (global best) acceleration
    seed: int = 0
    # Scenarios to evaluate each candidate against (names must match keys in
    # ags.optimization.fitness.NAMED_SCENARIOS)
    scenario_names: list[str] = field(default_factory=lambda: [
        "Baseline Meal",
        "Dawn Phenomenon",
        "Stacked Corrections",
    ])
    duration_minutes: int = 180
    step_minutes: int = 5
    # Fitness weights
    hypo_penalty_weight: float = 3.0   # multiplier on time-below-range %
    peak_penalty_weight: float = 1.5   # multiplier on time-above-250 %


@dataclass
class PSOIteration:
    """Snapshot of PSO state at one iteration."""
    iteration: int
    best_fitness: float       # lower is better (negated TIR + penalties)
    best_tir_pct: float       # best Time-in-Range seen so far (%)
    mean_fitness: float


@dataclass
class PSOResult:
    """Full output from a PSO run."""
    best_params: dict[str, float]
    best_fitness: float
    best_tir_pct: float
    history: list[PSOIteration]
    n_evaluations: int
