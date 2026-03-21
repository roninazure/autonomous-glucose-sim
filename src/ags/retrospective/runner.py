"""Retrospective CGM trace replay runner.

In retrospective mode the glucose trajectory is FIXED from real (or reference)
CGM readings.  The controller and safety layer run exactly as in forward
simulation, but:

  - ``cgm_glucose_mgdl`` at each step is taken directly from the trace rather
    than from the physiology model.
  - ``true_glucose_mgdl`` is set equal to the CGM reading (no separate ground
    truth in a retrospective trace).
  - Insulin PK/PD is tracked independently: every unit the controller
    *would have delivered* accumulates in the 2-compartment model and feeds
    back into safety decisions (IOB guard) on subsequent steps.  This creates
    a realistic counterfactual — "if we had followed the controller, here is
    the IOB that would have built up."
  - The glucose trajectory itself does NOT change based on controller actions.
    This is the defining property of retrospective replay.

Returns:
    (list[TimestepRecord], RunSummary) — same types as forward evaluation,
    enabling the same metrics, reporting, and export pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass

from ags.controller.pipeline import run_controller
from ags.controller.state import ControllerInputs
from ags.evaluation.metrics import summarize_run
from ags.evaluation.state import RunSummary, TimestepRecord
from ags.pump.pipeline import run_pump_with_safety_output
from ags.pump.state import PumpConfig
from ags.retrospective.loader import CgmReading
from ags.safety.evaluator import evaluate_safety_stateful
from ags.safety.integration import build_safety_inputs
from ags.safety.state import SafetyThresholds, SuspendState
from ags.simulation.insulin import advance_insulin_compartments, insulin_on_board


@dataclass
class RetrospectiveConfig:
    """Controller and PK/PD parameters used during retrospective replay.

    ``insulin_peak_minutes`` governs the PK/PD shape for the hypothetical
    insulin accumulation.  It does not affect the CGM readings.
    ``correction_factor_mgdl_per_unit`` is typically the same as the ISF
    used in the original patient data — if unknown, 50 mg/dL/U is a
    reasonable starting point for an average T1D adult.
    """
    target_glucose_mgdl: float = 110.0
    correction_factor_mgdl_per_unit: float = 50.0
    min_excursion_delta_mgdl: float = 0.0
    microbolus_fraction: float = 1.0
    insulin_peak_minutes: float = 75.0


def run_retrospective(
    readings: list[CgmReading],
    config: RetrospectiveConfig | None = None,
    safety_thresholds: SafetyThresholds | None = None,
    pump_config: PumpConfig | None = None,
) -> tuple[list[TimestepRecord], RunSummary]:
    """Replay a fixed CGM trace through the controller and safety pipeline.

    The first reading is used as the starting point; the controller begins
    making decisions from the second reading onward (same convention as the
    forward simulation runner — we need a ``previous_glucose`` for step 0).

    Args:
        readings: Sorted list of CgmReading (from loader or reference trace).
        config:   Controller and PK/PD parameters (defaults if None).
        safety_thresholds: Safety configuration (defaults if None).
        pump_config: Pump hardware constraints (defaults if None).

    Returns:
        (records, summary) — TimestepRecords for each replayed step plus a
        RunSummary with the same clinical metrics as forward evaluation.
    """
    if len(readings) < 2:
        raise ValueError("Retrospective replay requires at least 2 CGM readings.")

    config = config or RetrospectiveConfig()
    safety_thresholds = safety_thresholds or SafetyThresholds()
    pump_config = pump_config or PumpConfig()

    # Infer step_minutes from the first two readings (used for PK/PD only).
    # If the trace is irregular we use the most common inter-reading gap.
    gaps = [
        readings[i + 1].timestamp_min - readings[i].timestamp_min
        for i in range(min(5, len(readings) - 1))
    ]
    step_minutes = float(max(set(gaps), key=gaps.count))

    # Initialise 2-compartment PK/PD at zero insulin
    tracked_x1 = 0.0
    tracked_x2 = 0.0

    # Rolling CGM history for the predictor (smoothing window)
    _HISTORY_WINDOW = 5
    cgm_history: list[float] = [readings[0].glucose_mgdl]

    suspend_state = SuspendState()
    records: list[TimestepRecord] = []

    for previous, current in zip(readings[:-1], readings[1:]):
        step_iob_u = insulin_on_board(tracked_x1, tracked_x2)

        cgm_history.append(current.glucose_mgdl)
        if len(cgm_history) > _HISTORY_WINDOW:
            cgm_history.pop(0)

        controller_inputs = ControllerInputs(
            current_glucose_mgdl=current.glucose_mgdl,
            previous_glucose_mgdl=previous.glucose_mgdl,
            insulin_on_board_u=step_iob_u,
            target_glucose_mgdl=config.target_glucose_mgdl,
            correction_factor_mgdl_per_unit=config.correction_factor_mgdl_per_unit,
            glucose_history=list(cgm_history),
            min_excursion_delta_mgdl=config.min_excursion_delta_mgdl,
            microbolus_fraction=config.microbolus_fraction,
        )

        signal, prediction, recommendation = run_controller(controller_inputs)

        safety_inputs = build_safety_inputs(
            recommendation=recommendation,
            prediction=prediction,
            signal=signal,
            insulin_on_board_u=step_iob_u,
        )

        safety_decision, suspend_state = evaluate_safety_stateful(
            inputs=safety_inputs,
            thresholds=safety_thresholds,
            suspend_state=suspend_state,
        )

        pump_result = run_pump_with_safety_output(
            safety_decision=safety_decision,
            pump_config=pump_config,
        )

        # Advance hypothetical IOB — the dose the controller *would have*
        # delivered accumulates in the PK/PD model.
        tracked_x1, tracked_x2 = advance_insulin_compartments(
            x1=tracked_x1,
            x2=tracked_x2,
            dose_u=pump_result.delivered_units,
            step_minutes=step_minutes,
            peak_minutes=config.insulin_peak_minutes,
        )

        records.append(TimestepRecord(
            timestamp_min=current.timestamp_min,
            # In retrospective mode true == CGM (no ground-truth separation)
            true_glucose_mgdl=current.glucose_mgdl,
            cgm_glucose_mgdl=current.glucose_mgdl,
            recommended_units=recommendation.recommended_units,
            safety_status=safety_decision.status,
            safety_final_units=safety_decision.final_units,
            pump_delivered_units=pump_result.delivered_units,
            insulin_on_board_u=step_iob_u,
            is_suspended=suspend_state.is_suspended,
        ))

    summary = summarize_run(records)
    return records, summary
