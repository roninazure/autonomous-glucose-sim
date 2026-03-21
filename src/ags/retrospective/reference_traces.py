"""Built-in reference CGM traces for retrospective replay demonstrations.

Each trace represents a clinically realistic glucose pattern at 5-minute
intervals.  They are intentionally diverse: one post-prandial excursion,
one nocturnal hypoglycaemia, one dawn phenomenon rise.  Together they cover
the three most common challenge patterns an autonomous dosing system must
handle safely.

Glucose values are in mg/dL.  All traces start at t=0 and use 5-minute steps.
"""
from __future__ import annotations

from ags.retrospective.loader import CgmReading


def _trace(points: list[tuple[int, float]]) -> list[CgmReading]:
    return [CgmReading(timestamp_min=t, glucose_mgdl=g) for t, g in points]


# ── Trace 1 — Post-prandial spike ─────────────────────────────────────────────
# Pattern: unbolused 60g mixed meal.  Glucose rises sharply from euglycaemia,
# peaks at ~240 mg/dL around t=65, then falls gradually as endogenous insulin
# or a late correction takes effect.  Typical T1D missed-bolus profile.
POSTPRANDIAL_SPIKE: list[CgmReading] = _trace([
    (0,   110.0),
    (5,   112.5),
    (10,  118.0),
    (15,  128.5),
    (20,  142.0),
    (25,  158.5),
    (30,  175.0),
    (35,  191.0),
    (40,  205.5),
    (45,  217.5),
    (50,  226.5),
    (55,  233.0),
    (60,  237.0),
    (65,  238.5),   # ← peak
    (70,  237.0),
    (75,  232.5),
    (80,  225.5),
    (85,  216.0),
    (90,  205.0),
    (95,  192.5),
    (100, 179.5),
    (105, 166.5),
    (110, 154.0),
    (115, 143.0),
    (120, 133.5),
])

# ── Trace 2 — Nocturnal hypoglycaemia ────────────────────────────────────────
# Pattern: slow overnight glucose fall — residual IOB from an evening
# correction combined with elevated overnight sensitivity.  Glucose descends
# from borderline-low at midnight (90 mg/dL) into clinical hypoglycaemia
# (~57 mg/dL at t=60), then slowly recovers via glucagon / liver release.
# The safety layer should enter suspension and hold it until recovery is clear.
NOCTURNAL_HYPO: list[CgmReading] = _trace([
    (0,   90.0),
    (5,   87.5),
    (10,  84.5),
    (15,  81.5),
    (20,  78.5),
    (25,  75.5),
    (30,  72.5),
    (35,  69.5),
    (40,  67.0),
    (45,  64.5),
    (50,  62.0),
    (55,  59.5),
    (60,  57.5),    # ← nadir
    (65,  58.0),
    (70,  60.0),
    (75,  63.5),
    (80,  67.5),
    (85,  72.5),
    (90,  78.0),
])

# ── Trace 3 — Dawn phenomenon ──────────────────────────────────────────────────
# Pattern: cortisol and growth-hormone surge between 04:00 and 08:00 drives a
# gradual glucose rise from near-target (105 mg/dL) to 165 mg/dL over two
# hours.  No meal; the rise is purely hepatic.  The controller must detect the
# slow trend and recommend micro-corrections without over-dosing.
DAWN_RISE: list[CgmReading] = _trace([
    (0,   105.0),
    (5,   107.0),
    (10,  109.5),
    (15,  112.5),
    (20,  115.5),
    (25,  118.5),
    (30,  121.5),
    (35,  124.5),
    (40,  127.5),
    (45,  130.5),
    (50,  133.5),
    (55,  136.0),
    (60,  139.0),
    (65,  141.5),
    (70,  144.0),
    (75,  146.5),
    (80,  149.0),
    (85,  151.5),
    (90,  153.5),
    (95,  155.5),
    (100, 157.5),
    (105, 159.0),
    (110, 160.5),
    (115, 161.5),
    (120, 163.0),
])

# ── Registry ──────────────────────────────────────────────────────────────────

REFERENCE_TRACES: dict[str, list[CgmReading]] = {
    "Post-prandial Spike (60g meal, missed bolus)": POSTPRANDIAL_SPIKE,
    "Nocturnal Hypoglycaemia (overnight IOB, sensitive)": NOCTURNAL_HYPO,
    "Dawn Phenomenon (cortisol rise, no meal)": DAWN_RISE,
}

REFERENCE_TRACE_DESCRIPTIONS: dict[str, str] = {
    "Post-prandial Spike (60g meal, missed bolus)":
        "Glucose rises from 110 → 239 mg/dL over 65 min, then falls. "
        "Tests correction aggressiveness and IOB cap behaviour.",
    "Nocturnal Hypoglycaemia (overnight IOB, sensitive)":
        "Slow descent from 90 → 57 mg/dL (clinical hypo). "
        "Safety layer must suspend and hold until confirmed recovery.",
    "Dawn Phenomenon (cortisol rise, no meal)":
        "Gradual hepatic rise from 105 → 163 mg/dL over 120 min. "
        "Tests trend detection and micro-correction without over-dosing.",
}
