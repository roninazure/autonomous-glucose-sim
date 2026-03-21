from __future__ import annotations

from ags.controller.pipeline import run_controller
from ags.controller.state import ControllerInputs
from ags.evaluation.metrics import summarize_run
from ags.evaluation.state import RunSummary, TimestepRecord
from ags.pump.emulator import advance_dual_wave_state, apply_dual_wave_split, emulate_pump_delivery
from ags.pump.pipeline import run_pump_with_safety_output
from ags.pump.state import DualWaveConfig, DualWaveState, PumpConfig
from ags.safety.evaluator import evaluate_safety_stateful
from ags.safety.integration import build_safety_inputs
from ags.safety.state import SafetyThresholds, SuspendState
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
    ror_tiered_microbolus: bool = False,
    autonomous_isf: bool = False,
    dual_wave_config: DualWaveConfig | None = None,
) -> tuple[list[TimestepRecord], RunSummary]:
    safety_thresholds = safety_thresholds or SafetyThresholds()
    pump_config = pump_config or PumpConfig()
    dual_wave_config = dual_wave_config or DualWaveConfig()

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

    # Stateful hypo suspension — persists across timesteps until glucose
    # recovers above the resume threshold.
    suspend_state = SuspendState()

    # Dual-wave extended tail state — persists across steps.
    dual_wave_state = DualWaveState()

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
            step_minutes=step_minutes,
            ror_tiered_microbolus=ror_tiered_microbolus,
            autonomous_isf=autonomous_isf,
        )

        signal, prediction, recommendation, classification = run_controller(controller_inputs)
        meal_signal = classification.meal_signal if classification else None

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

        # ── Dual-wave split ───────────────────────────────────────────────
        # If dual-wave is enabled and this step delivers a bolus, split it
        # into immediate + queued extended tail.
        extended_delivered = 0.0

        if dual_wave_config.enabled and safety_decision.allowed and safety_decision.final_units > 0:
            immediate_u, dual_wave_state = apply_dual_wave_split(
                total_units=safety_decision.final_units,
                dual_wave_config=dual_wave_config,
                dual_wave_state=dual_wave_state,
                step_minutes=step_minutes,
                pump_config=pump_config,
            )
            # Deliver only the immediate fraction through the normal pump path
            from ags.safety.state import SafetyDecision as _SD
            safety_decision = _SD(
                status=safety_decision.status,
                allowed=safety_decision.allowed,
                final_units=immediate_u,
                reason=safety_decision.reason + " [dual-wave: immediate portion]",
            )
        elif dual_wave_state.is_active:
            # Advance the extended tail from the previous bolus even if there
            # is no new recommendation this step.
            extended_delivered, dual_wave_state = advance_dual_wave_state(
                dual_wave_state=dual_wave_state,
                pump_config=pump_config,
            )

        pump_result = run_pump_with_safety_output(
            safety_decision=safety_decision,
            pump_config=pump_config,
        )

        total_delivered = pump_result.delivered_units + extended_delivered

        # Advance PK/PD state: the delivered dose enters the subcutaneous
        # depot (x1) and transfers into the active pool (x2) over time.
        tracked_x1, tracked_x2 = advance_insulin_compartments(
            x1=tracked_x1,
            x2=tracked_x2,
            dose_u=total_delivered,
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
                pump_delivered_units=total_delivered,
                insulin_on_board_u=step_iob_u,
                is_suspended=suspend_state.is_suspended,
                dual_wave_extended_units=extended_delivered,
                rate_mgdl_per_min=signal.rate_mgdl_per_min,
                meal_detected=meal_signal.detected if meal_signal else False,
                meal_phase=meal_signal.phase.value if meal_signal else "none",
                meal_estimated_carbs_g=meal_signal.estimated_carbs_g if meal_signal else 0.0,
                meal_confidence=meal_signal.confidence if meal_signal else 0.0,
                basal_drift_detected=classification.basal_signal.detected if classification and classification.basal_signal else False,
                basal_drift_type=classification.basal_signal.drift_type.value if classification and classification.basal_signal else "none",
                basal_drift_rate_mgdl_per_min=classification.basal_signal.sustained_rate_mgdl_per_min if classification and classification.basal_signal else 0.0,
                basal_drift_linearity=classification.basal_signal.linearity_score if classification and classification.basal_signal else 0.0,
                glucose_cause=classification.cause.value if classification else "flat",
            )
        )

    summary = summarize_run(records)
    return records, summary
