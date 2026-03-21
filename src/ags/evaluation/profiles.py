"""Patient profile archetypes for population-level algorithm validation.

Each profile defines the physiological parameters that vary across real patients:
  - Insulin sensitivity (ISF) — mg/dL drop per unit of insulin
  - Carbohydrate impact — mg/dL rise per gram of carbs absorbed
  - Insulin peak time — minutes to peak action (determines PK/PD curve shape)

These four archetypes cover the realistic clinical range seen in T1D populations
and are used by the profile sweep to validate that the control algorithm produces
acceptable outcomes across patient diversity — not just for the median patient.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PatientProfile:
    name: str
    description: str
    insulin_sensitivity_mgdl_per_unit: float  # ISF
    carb_impact_mgdl_per_g: float
    insulin_peak_minutes: float


# ── Four clinically distinct archetypes ──────────────────────────────────────

STANDARD_ADULT = PatientProfile(
    name="Standard Adult",
    description="Typical T1D adult · NovoLog/Aspart · median ISF",
    insulin_sensitivity_mgdl_per_unit=50.0,
    carb_impact_mgdl_per_g=3.0,
    insulin_peak_minutes=75.0,
)

INSULIN_RESISTANT = PatientProfile(
    name="Insulin Resistant",
    description="High resistance · larger carb swings · requires more insulin per step",
    insulin_sensitivity_mgdl_per_unit=30.0,
    carb_impact_mgdl_per_g=4.5,
    insulin_peak_minutes=75.0,
)

HIGHLY_SENSITIVE = PatientProfile(
    name="Highly Sensitive",
    description="Lean / athletic · Humalog · elevated hypo risk on any mis-dose",
    insulin_sensitivity_mgdl_per_unit=85.0,
    carb_impact_mgdl_per_g=2.5,
    insulin_peak_minutes=65.0,
)

RAPID_RESPONDER = PatientProfile(
    name="Rapid Responder",
    description="Fiasp/ultra-rapid · fast peak · timing-sensitive · early IOB build-up",
    insulin_sensitivity_mgdl_per_unit=50.0,
    carb_impact_mgdl_per_g=3.0,
    insulin_peak_minutes=55.0,
)

# Ordered list used by the sweep runner and dashboard
ALL_PROFILES: list[PatientProfile] = [
    STANDARD_ADULT,
    INSULIN_RESISTANT,
    HIGHLY_SENSITIVE,
    RAPID_RESPONDER,
]


# ── Weight-based ISF estimation ───────────────────────────────────────────────

def estimate_isf_from_weight(
    weight_kg: float,
    tdd_factor: float = 0.55,
) -> float:
    """Estimate insulin sensitivity factor (ISF) from body weight.

    Uses the **1700 Rule**:
        ISF (mg/dL/U) ≈ 1700 / TDD
    where TDD (Total Daily Dose) is approximated as:
        TDD ≈ weight_kg × tdd_factor

    The default tdd_factor of 0.55 U/kg is a clinically validated median for
    adult T1D patients on rapid-acting insulin analogues.  Adjust upward for
    insulin-resistant patients (~0.7–0.8) and downward for highly sensitive
    patients (~0.3–0.4).

    Doctor's example: 30g carbs → 6U  →  ICR = 5 g/U
        For a 70 kg patient: TDD ≈ 38.5 U  →  ISF ≈ 44 mg/dL/U  (close to
        the Standard Adult archetype of 50 mg/dL/U).

    Args:
        weight_kg: Patient body weight in kilograms.
        tdd_factor: Fraction of body weight (in kg) used to estimate TDD.

    Returns:
        Estimated ISF in mg/dL per unit, rounded to one decimal place.
    """
    tdd = max(1.0, weight_kg * tdd_factor)
    return round(1700.0 / tdd, 1)


def estimate_carb_ratio_from_weight(
    weight_kg: float,
    tdd_factor: float = 0.55,
) -> float:
    """Estimate insulin-to-carb ratio (ICR) from body weight.

    Uses the **500 Rule**:
        ICR (g/U) ≈ 500 / TDD

    Args:
        weight_kg: Patient body weight in kilograms.
        tdd_factor: Fraction of body weight (in kg) used to estimate TDD.

    Returns:
        Estimated ICR in grams of carbs per unit, rounded to one decimal.
    """
    tdd = max(1.0, weight_kg * tdd_factor)
    return round(500.0 / tdd, 1)
