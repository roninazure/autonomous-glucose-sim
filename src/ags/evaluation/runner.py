from __future__ import annotations

from ags.controller.state import ControllerInputs
from ags.evaluation.metrics import summarize_run
from ags.evaluation.state import RunSummary, TimestepRecord
from ags.pump.pipeline import run_pump_with_safety_output
from ags.pump.state import PumpConfig
from ags.safety.pipeline import run_controller_with_safety
from ags.safety.state import SafetyThresholds
from ags.simulation.engine import run_simulation
from ags.simulation.state import SimulationInputs

# Must match the decay factor used in src/ags/simulation/insulin.py
_IOB_DECAY_FACTOR = 0.95


def run_evaluation(
    simulation_inputs: SimulationInputs,
    safety_thresholds: SafetyThresholds | None = None,
    pump_config: PumpConfig | None = None,
    duration_minutes: int = 180,
    step_minutes: int = 5,
    seed: int = 42,
    target_glucose_mgdl: float = 110.0,
    correction_factor_mgdl_per_unit: float = 50.0,
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

    # Track IOB independently so that each delivered dose feeds back into the
    # next timestep's controller and safety decisions. Previously, the loop
    # read IOB from the simulation snapshot, which never incorporated delivered
    # insulin, making the safety IOB guard ineffective.
    tracked_iob_u = snapshots[0].insulin_on_board_u

    for previous, current in zip(snapshots[:-1], snapshots[1:]):
        controller_inputs = ControllerInputs(
            current_glucose_mgdl=current.cgm_glucose_mgdl,
            previous_glucose_mgdl=previous.cgm_glucose_mgdl,
            insulin_on_board_u=tracked_iob_u,
            target_glucose_mgdl=target_glucose_mgdl,
            correction_factor_mgdl_per_unit=correction_factor_mgdl_per_unit,
        )

        _, _, recommendation, safety_decision = run_controller_with_safety(
            controller_inputs=controller_inputs,
            safety_thresholds=safety_thresholds,
        )

        pump_result = run_pump_with_safety_output(
            safety_decision=safety_decision,
            pump_config=pump_config,
        )

        # Decay existing IOB then add what was just delivered.
        tracked_iob_u = tracked_iob_u * _IOB_DECAY_FACTOR + pump_result.delivered_units

        records.append(
            TimestepRecord(
                timestamp_min=current.timestamp_min,
                true_glucose_mgdl=current.true_glucose_mgdl,
                cgm_glucose_mgdl=current.cgm_glucose_mgdl,
                recommended_units=recommendation.recommended_units,
                safety_status=safety_decision.status,
                safety_final_units=safety_decision.final_units,
                pump_delivered_units=pump_result.delivered_units,
            )
        )

    summary = summarize_run(records)
    return records, summary
