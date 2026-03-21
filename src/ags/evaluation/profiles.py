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
