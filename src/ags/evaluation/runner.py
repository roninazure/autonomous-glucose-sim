from __future__ import annotations

from ags.controller.state import ControllerInputs
from ags.evaluation.metrics import summarize_run
from ags.evaluation.state import RunSummary, TimestepRecord
from ags.pump.pipeline import run_pump_with_safety_output
from ags.pump.state import PumpConfig
from ags.safety.pipeline import run_controller_with_safety
from ags.safety.state import SafetyThresholds
from ags.simulation.engine import run_simulation
from ags.simulation.insulin import advance_insulin_compartments, insulin_on_board
from ags.simulation.state import SimulationInputs


def run_evaluation(
    simulation_inputs: SimulationInputs,
    safety_thresholds: SafetyThresholds | None = None,
    pump_config: PumpConfig | None = None,
    duration_minutes: int = 180,
    step_minutes: int = 5,
    seed: int = 42,
    target_glucose_mgdl: float = 110.0,
    correction_factor_mgdl_per_unit: float = 50.0,
    min_excursion_delta_mgdl: float = 0.0,
    microbolus_fraction: float = 1.0,
) -> tuple[list[TimestepRecord], RunSummary]:
    safety_thresholds = safety_thresholds or SafetyThresholds()
    pump_config = pump_config or PumpConfig()

    snapshots = run_simulation(
        inputs=simulation_inputs,
        duration_minutes=duration_minutes,
        step_minutes=step_minutes,
        seed=seed,
    )

    records: list[TimestepRecord] = []

    # Track the 2-compartment PK/PD state independently so that each
    # delivered dose feeds back into the next timestep's controller and safety
    # decisions using the same physiologically accurate model as the simulation.
    tracked_x1 = snapshots[0].insulin_compartment1_u
    tracked_x2 = snapshots[0].insulin_compartment2_u

    # Rolling CGM history window (oldest → newest) fed to the predictor for
    # exponential smoothing.  Seeded with the first snapshot's CGM reading.
    _HISTORY_WINDOW = 5
    cgm_history: list[float] = [snapshots[0].cgm_glucose_mgdl]

    for previous, current in zip(snapshots[:-1], snapshots[1:]):
        # Capture IOB before this step's delivery so the chart shows what the
        # controller and safety layer actually saw when making their decision.
        step_iob_u = insulin_on_board(tracked_x1, tracked_x2)

        cgm_history.append(current.cgm_glucose_mgdl)
        if len(cgm_history) > _HISTORY_WINDOW:
            cgm_history.pop(0)

        controller_inputs = ControllerInputs(
            current_glucose_mgdl=current.cgm_glucose_mgdl,
            previous_glucose_mgdl=previous.cgm_glucose_mgdl,
            insulin_on_board_u=step_iob_u,
            target_glucose_mgdl=target_glucose_mgdl,
            correction_factor_mgdl_per_unit=correction_factor_mgdl_per_unit,
            glucose_history=list(cgm_history),
            min_excursion_delta_mgdl=min_excursion_delta_mgdl,
            microbolus_fraction=microbolus_fraction,
        )

        _, _, recommendation, safety_decision = run_controller_with_safety(
            controller_inputs=controller_inputs,
            safety_thresholds=safety_thresholds,
        )

        pump_result = run_pump_with_safety_output(
            safety_decision=safety_decision,
            pump_config=pump_config,
        )

        # Advance PK/PD state: the delivered dose enters the subcutaneous
        # depot (x1) and transfers into the active pool (x2) over time.
        tracked_x1, tracked_x2 = advance_insulin_compartments(
            x1=tracked_x1,
            x2=tracked_x2,
            dose_u=pump_result.delivered_units,
            step_minutes=step_minutes,
            peak_minutes=simulation_inputs.insulin_peak_minutes,
        )

        records.append(
            TimestepRecord(
                timestamp_min=current.timestamp_min,
                true_glucose_mgdl=current.true_glucose_mgdl,
                cgm_glucose_mgdl=current.cgm_glucose_mgdl,
                recommended_units=recommendation.recommended_units,
                safety_status=safety_decision.status,
                safety_final_units=safety_decision.final_units,
                pump_delivered_units=pump_result.delivered_units,
                insulin_on_board_u=step_iob_u,
            )
        )

    summary = summarize_run(records)
    return records, summary
