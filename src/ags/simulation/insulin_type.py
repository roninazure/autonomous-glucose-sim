"""Rapid-acting insulin analog registry.

Each analog is defined by its pharmacokinetic profile used in the 2-compartment
PK/PD model.  The key parameter is ``peak_minutes`` (τ), which controls both
the transfer rate between compartments and the glucose-lowering effect rate.

Clinical reference ranges (approximate):
    Admelog  (Lispro biosimilar)   — onset 15–30 min, peak ~65 min
    Apidra   (Glulisine)           — onset 10–20 min, peak ~55 min
    Fiasp    (Fast Aspart)         — onset  2– 4 min, peak ~50 min
    Humalog  (Lispro)              — onset 15–30 min, peak ~65 min
    Lyumjev  (Ultra-rapid Lispro)  — onset ~5     min, peak ~45 min
    Novolog  (Aspart)              — onset 10–20 min, peak ~75 min
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class InsulinPKProfile:
    """Pharmacokinetic profile for a rapid-acting insulin analog."""

    name: str
    peak_minutes: float  # τ — time to peak activity; drives compartment transfer rate
    onset_minutes: float  # approximate clinical onset (informational)
    duration_hours: float  # approximate duration of action (informational)
    notes: str = ""


class InsulinAnalog(Enum):
    """Supported rapid-acting insulin analogs with their PK profiles."""

    ADMELOG = InsulinPKProfile(
        name="Admelog (Lispro biosimilar)",
        peak_minutes=65.0,
        onset_minutes=20.0,
        duration_hours=4.0,
        notes="Biosimilar to Humalog; identical PK profile.",
    )
    APIDRA = InsulinPKProfile(
        name="Apidra (Glulisine)",
        peak_minutes=55.0,
        onset_minutes=15.0,
        duration_hours=2.5,
        notes="Slightly faster than Humalog; shorter duration.",
    )
    FIASP = InsulinPKProfile(
        name="Fiasp (Fast-acting Aspart)",
        peak_minutes=50.0,
        onset_minutes=4.0,
        duration_hours=4.0,
        notes="Ultra-rapid niacinamide-enhanced formulation of Aspart.",
    )
    HUMALOG = InsulinPKProfile(
        name="Humalog (Lispro)",
        peak_minutes=65.0,
        onset_minutes=20.0,
        duration_hours=4.0,
        notes="Standard rapid-acting analog; widely used reference.",
    )
    LYUMJEV = InsulinPKProfile(
        name="Lyumjev (Ultra-rapid Lispro)",
        peak_minutes=45.0,
        onset_minutes=5.0,
        duration_hours=5.0,
        notes="Fastest-onset Lispro; citrate/treprostinil formulation.",
    )
    NOVOLOG = InsulinPKProfile(
        name="Novolog (Aspart)",
        peak_minutes=75.0,
        onset_minutes=15.0,
        duration_hours=4.5,
        notes="Original rapid-acting Aspart; longest τ among supported analogs.",
    )

    @property
    def profile(self) -> InsulinPKProfile:
        return self.value

    @property
    def peak_minutes(self) -> float:
        return self.value.peak_minutes
