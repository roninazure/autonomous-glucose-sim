from __future__ import annotations

from ags.controller.pipeline import run_controller
from ags.controller.state import ControllerInputs
from ags.evaluation.metrics import summarize_run
from ags.evaluation.state import RunSummary, TimestepRecord
from ags.pump.emulator import advance_dual_wave_state, apply_dual_wave_split, emulate_pump_delivery
from ags.detection.state import MealPhase
from ags.pump.pipeline import run_pump_with_safety_output
from ags.pump.state import DualWaveConfig, DualWaveState, PumpConfig
from ags.safety.evaluator import evaluate_safety_stateful
from ags.safety.integration import build_safety_inputs
from ags.safety.state import ArmingState, SafetyThresholds, SuspendState
from ags.simulation.engine import run_simulation
from ags.simulation.insulin import advance_insulin_compartments, insulin_on_board
from ags.simulation.physiology import advance_physiology
from ags.simulation.sensor import generate_cgm_reading
from ags.simulation.state import SimulationInputs, SimulationSnapshot


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
    # exponential smoothing and to the drift detector for linearity analysis.
    # Must be >= the drift detector's _MIN_WINDOW (6) and ideally matches its
    # full 60-min look-back (12 steps at 5-min cadence).  5 was too short —
    # drift detection never fired because it always saw fewer than 6 readings.
    _HISTORY_WINDOW = 12
    cgm_history: list[float] = [snapshots[0].cgm_glucose_mgdl]

    # Stateful hypo suspension — persists across timesteps until glucose
    # recovers above the resume threshold.
    suspend_state = SuspendState()

    # Arming state — tracks the monitor → armed → firing state machine.
    arming_state = ArmingState()

    # Dual-wave extended tail state — persists across steps.
    dual_wave_state = DualWaveState()

    # Pre-bolus de-duplication: fire exactly once per meal event.
    # Reset only after _MEAL_RESET_STREAK consecutive NONE steps so that a
    # brief gap in the ONSET signal mid-meal does not prematurely re-arm the
    # flag and allow a second pre-bolus for the same meal event.
    meal_prebolus_fired = False
    meal_none_streak = 0
    _MEAL_RESET_STREAK = 4  # 20 min of consecutive NONE before allowing new pre-bolus

    # ── Online ISF learning ───────────────────────────────────────────────────
    # After each significant dose, record (step, units, glucose_at_dose) and
    # wait 60 minutes (12 × 5-min steps).  Then measure glucose_drop and add
    # (units, drop) to isf_observations, which the recommender uses to refine
    # its autonomous ISF estimate via _refine_isf_from_observations.
    _ISF_LEARNING_HORIZON_STEPS = max(1, 60 // step_minutes)
    _ISF_MAX_OBS = 12
    isf_observations: list[tuple[float, float]] = []
    # Each entry: (delivery_step_idx, delivered_units, glucose_at_delivery_mgdl)
    pending_isf_obs: list[tuple[int, float, float]] = []

    for previous, current in zip(snapshots[:-1], snapshots[1:]):
        # Current step index (0-based), used for ISF learning horizon tracking.
        step_idx = len(records)

        # Capture IOB before this step's delivery so the chart shows what the
        # controller and safety layer actually saw when making their decision.
        step_iob_u = insulin_on_board(tracked_x1, tracked_x2)

        cgm_history.append(current.cgm_glucose_mgdl)
        if len(cgm_history) > _HISTORY_WINDOW:
            cgm_history.pop(0)

        # ── Online ISF learning: mature pending observations ──────────────────
        # Any dose delivered >= _ISF_LEARNING_HORIZON_STEPS ago now has a
        # measurable glucose response.  Compute drop and add to the observation
        # window; negative drops (glucose rose despite insulin) are discarded.
        still_pending: list[tuple[int, float, float]] = []
        for obs_step, obs_units, obs_glucose in pending_isf_obs:
            if step_idx - obs_step >= _ISF_LEARNING_HORIZON_STEPS:
                glucose_drop = obs_glucose - current.cgm_glucose_mgdl
                if obs_units > 0.05 and glucose_drop > 0:
                    isf_observations.append((obs_units, glucose_drop))
                    if len(isf_observations) > _ISF_MAX_OBS:
                        isf_observations = isf_observations[-_ISF_MAX_OBS:]
            else:
                still_pending.append((obs_step, obs_units, obs_glucose))
        pending_isf_obs = still_pending

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
            prebolus_already_fired=meal_prebolus_fired,
            isf_observations=list(isf_observations),
        )

        signal, prediction, recommendation, classification = run_controller(controller_inputs)
        meal_signal = classification.meal_signal if classification else None

        # ── Pre-bolus de-duplication state update ─────────────────────────────
        # If a pre-bolus just fired, mark it so subsequent ONSET steps skip it.
        # Reset only after _MEAL_RESET_STREAK consecutive NONE steps so that a
        # brief interruption in the ONSET signal mid-meal does not prematurely
        # re-arm the flag and trigger a second pre-bolus for the same meal.
        if meal_signal is None or meal_signal.phase == MealPhase.NONE:
            meal_none_streak += 1
            if meal_none_streak >= _MEAL_RESET_STREAK:
                meal_prebolus_fired = False
        else:
            meal_none_streak = 0
            if recommendation.reason.startswith("pre-bolus | meal ONSET"):
                meal_prebolus_fired = True

        safety_inputs = build_safety_inputs(
            recommendation=recommendation,
            prediction=prediction,
            signal=signal,
            insulin_on_board_u=step_iob_u,
            current_glucose_mgdl=current.cgm_glucose_mgdl,
        )

        safety_decision, suspend_state, arming_state = evaluate_safety_stateful(
            inputs=safety_inputs,
            thresholds=safety_thresholds,
            suspend_state=suspend_state,
            arming_state=arming_state,
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

        # ── Online ISF learning: queue this delivery for future evaluation ────
        # After _ISF_LEARNING_HORIZON_STEPS steps, we compare current glucose
        # against glucose_at_delivery to estimate the real ISF for this patient.
        if total_delivered > 0.05:
            pending_isf_obs.append((step_idx, total_delivered, current.cgm_glucose_mgdl))

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
                recommendation_reason=recommendation.reason,
                isf_observation_count=len(isf_observations),
                arming_phase=arming_state.phase,
            )
        )

    summary = summarize_run(records)
    return records, summary


def run_closed_loop_evaluation(
    simulation_inputs: SimulationInputs,
    safety_thresholds: SafetyThresholds | None = None,
    pump_config: PumpConfig | None = None,
    duration_minutes: int = 180,
    step_minutes: int = 5,
    seed: int = 42,
    target_glucose_mgdl: float = 110.0,
    correction_factor_mgdl_per_unit: float = 50.0,
    min_excursion_delta_mgdl: float = 0.0,
    microbolus_fraction: float = 0.25,
    ror_tiered_microbolus: bool = False,
    autonomous_isf: bool = False,
    initial_glucose_mgdl: float = 110.0,
) -> tuple[list[TimestepRecord], RunSummary]:
    """True closed-loop evaluation: delivered insulin changes the glucose trajectory.

    Unlike run_evaluation() — which pre-computes the full glucose curve and then
    replays the controller against it (open-loop) — this runner steps through
    physiology one snapshot at a time.  Each step's pump delivery is fed back
    into advance_physiology() so that insulin actually suppresses glucose.

    This is the artificial pancreas loop:

        CGM reading → controller → safety → pump → physiology → next CGM reading
                ↑_______________________________________________________|

    Args:
        simulation_inputs: Patient physiology and scenario (meals, drift, ISF).
        safety_thresholds: Safety gate configuration.
        pump_config: Pump delivery constraints.
        duration_minutes: Total simulation length.
        step_minutes: CGM cadence (5 min = Dexcom, 1 min = Libre).
        seed: RNG seed for sensor noise reproducibility.
        target_glucose_mgdl: Controller target.
        correction_factor_mgdl_per_unit: Used only when autonomous_isf=False.
        autonomous_isf: If True, ISF is inferred from CGM dynamics with online
            learning — no pre-programmed sensitivity number required.
        initial_glucose_mgdl: Starting glucose (default 110 = euglycaemia).

    Returns:
        (records, summary) — same schema as run_evaluation for drop-in comparison.
    """
    import random
    random.seed(seed)

    safety_thresholds = safety_thresholds or SafetyThresholds()
    pump_config = pump_config or PumpConfig()
    n_steps = max(1, duration_minutes // step_minutes)

    # ── Seed the initial physiological state ─────────────────────────────────
    current = SimulationSnapshot(
        timestamp_min=0,
        true_glucose_mgdl=initial_glucose_mgdl,
        cgm_glucose_mgdl=initial_glucose_mgdl,
        insulin_compartment1_u=0.0,
        insulin_compartment2_u=0.0,
        insulin_on_board_u=0.0,
    )

    records: list[TimestepRecord] = []
    _HISTORY_WINDOW = 12
    cgm_history: list[float] = [current.cgm_glucose_mgdl]

    suspend_state = SuspendState()
    arming_state = ArmingState()

    # Pre-bolus de-duplication
    meal_prebolus_fired = False
    meal_none_streak = 0
    _MEAL_RESET_STREAK = 4

    # Online ISF learning
    _ISF_LEARNING_HORIZON_STEPS = max(1, 60 // step_minutes)
    _ISF_MAX_OBS = 12
    isf_observations: list[tuple[float, float]] = []
    pending_isf_obs: list[tuple[int, float, float]] = []

    for step_idx in range(n_steps):
        # IOB from the live physiology state (not a separately tracked shadow)
        step_iob_u = insulin_on_board(
            current.insulin_compartment1_u,
            current.insulin_compartment2_u,
        )

        cgm_history.append(current.cgm_glucose_mgdl)
        if len(cgm_history) > _HISTORY_WINDOW:
            cgm_history.pop(0)

        # ── Online ISF learning: mature pending observations ──────────────────
        still_pending: list[tuple[int, float, float]] = []
        for obs_step, obs_units, obs_glucose in pending_isf_obs:
            if step_idx - obs_step >= _ISF_LEARNING_HORIZON_STEPS:
                glucose_drop = obs_glucose - current.cgm_glucose_mgdl
                if obs_units > 0.05 and glucose_drop > 0:
                    isf_observations.append((obs_units, glucose_drop))
                    if len(isf_observations) > _ISF_MAX_OBS:
                        isf_observations = isf_observations[-_ISF_MAX_OBS:]
            else:
                still_pending.append((obs_step, obs_units, obs_glucose))
        pending_isf_obs = still_pending

        prev_glucose = cgm_history[-2] if len(cgm_history) >= 2 else current.cgm_glucose_mgdl

        controller_inputs = ControllerInputs(
            current_glucose_mgdl=current.cgm_glucose_mgdl,
            previous_glucose_mgdl=prev_glucose,
            insulin_on_board_u=step_iob_u,
            target_glucose_mgdl=target_glucose_mgdl,
            correction_factor_mgdl_per_unit=correction_factor_mgdl_per_unit,
            min_excursion_delta_mgdl=min_excursion_delta_mgdl,
            microbolus_fraction=microbolus_fraction,
            ror_tiered_microbolus=ror_tiered_microbolus,
            glucose_history=list(cgm_history),
            step_minutes=step_minutes,
            autonomous_isf=autonomous_isf,
            prebolus_already_fired=meal_prebolus_fired,
            isf_observations=list(isf_observations),
        )

        signal, prediction, recommendation, classification = run_controller(controller_inputs)
        meal_signal = classification.meal_signal if classification else None

        # Pre-bolus de-duplication state update
        if meal_signal is None or meal_signal.phase == MealPhase.NONE:
            meal_none_streak += 1
            if meal_none_streak >= _MEAL_RESET_STREAK:
                meal_prebolus_fired = False
        else:
            meal_none_streak = 0
            if recommendation.reason.startswith("pre-bolus | meal ONSET"):
                meal_prebolus_fired = True

        safety_inputs = build_safety_inputs(
            recommendation=recommendation,
            prediction=prediction,
            signal=signal,
            insulin_on_board_u=step_iob_u,
            current_glucose_mgdl=current.cgm_glucose_mgdl,
        )
        safety_decision, suspend_state, arming_state = evaluate_safety_stateful(
            inputs=safety_inputs,
            thresholds=safety_thresholds,
            suspend_state=suspend_state,
            arming_state=arming_state,
        )
        pump_result = run_pump_with_safety_output(
            safety_decision=safety_decision,
            pump_config=pump_config,
        )
        total_delivered = pump_result.delivered_units

        # Queue for ISF learning
        if total_delivered > 0.05:
            pending_isf_obs.append((step_idx, total_delivered, current.cgm_glucose_mgdl))

        records.append(TimestepRecord(
            timestamp_min=current.timestamp_min,
            true_glucose_mgdl=current.true_glucose_mgdl,
            cgm_glucose_mgdl=current.cgm_glucose_mgdl,
            recommended_units=recommendation.recommended_units,
            safety_status=safety_decision.status,
            safety_final_units=safety_decision.final_units,
            pump_delivered_units=total_delivered,
            insulin_on_board_u=step_iob_u,
            is_suspended=suspend_state.is_suspended,
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
            recommendation_reason=recommendation.reason,
            isf_observation_count=len(isf_observations),
            arming_phase=arming_state.phase,
        ))

        # ── THE CLOSED LOOP ───────────────────────────────────────────────────
        # Advance physiology WITH this step's delivery so insulin actually
        # suppresses glucose.  This is the line that makes it an artificial
        # pancreas rather than an open-loop observer.
        next_snapshot = advance_physiology(
            snapshot=current,
            inputs=simulation_inputs,
            step_minutes=step_minutes,
            delivered_dose_u=total_delivered,
        )
        next_snapshot.cgm_glucose_mgdl = generate_cgm_reading(next_snapshot)
        current = next_snapshot

    summary = summarize_run(records)
    return records, summary
