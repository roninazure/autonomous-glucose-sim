"""
Tests that controller parameters flow through to the SWARM dosing path.

Note: target_glucose_mgdl and correction_factor_mgdl_per_unit are legacy
parameters not used by the SWARM micro-bolus formula. Tests that verified
legacy ISF correction behaviour have been removed.
"""
from __future__ import annotations
