"""Retrospective annotator: generates per-step DecisionExplanation objects
from a completed run's TimestepRecord list.

The annotator replays the controller and safety pipeline on the stored CGM
values and IOB figures.  Because the controller and safety evaluator are both
deterministic functions of their inputs, the replay produces identical
signals, predictions, recommendations, and safety decisions to those that
were computed during the original run — at zero extra overhead beyond the
cost of calling the same functions again.

This design keeps the hot-path runners (run_evaluation, run_retrospective)
lean: they store only the compact ``TimestepRecord``; explainability is
generated on-demand when the user requests the Decision Timeline view.

Usage::

    records, summary = run_evaluation(...)
    explanations = annotate_run(
        records,
        seed_glucose_mgdl=140.0,
        target_glucose_mgdl=110.0,
        correction_factor_mgdl_per_unit=50.0,
        safety_thresholds=SafetyThresholds(),
    )
"""
from __future__ import annotations

from ags.controller.pipeline import run_controller
from ags.controller.state import ControllerInputs
from ags.detection.state import MealPhase
from ags.evaluation.state import TimestepRecord
from ags.explainability.narrative import build_narrative
from ags.explainability.state import (
    DecisionExplanation,
    gate_from_reason,
)
from ags.safety.evaluator import evaluate_safety_stateful
from ags.safety.integration import build_safety_inputs
from ags.safety.state import ArmingState, SafetyThresholds, SuspendState

_HISTORY_WINDOW = 12  # matches runner's CGM history window for EWM prediction fidelity
_MEAL_RESET_STREAK = 4  # matches runner: 20 min of NONE before allowing new pre-bolus
# Rate-of-rise thresholds in mg/dL/min (detector.py uses per-minute rates).
_RISE_THRESHOLD_PER_MIN = 1.0
_FALL_THRESHOLD_PER_MIN = -1.0


def annotate_run(
    records: list[TimestepRecord],
    *,
    seed_glucose_mgdl: float = 140.0,
    target_glucose_mgdl: float = 110.0,
    correction_factor_mgdl_per_unit: float = 50.0,
    min_excursion_delta_mgdl: float = 0.0,
    microbolus_fraction: float = 1.0,
    safety_thresholds: SafetyThresholds | None = None,
    step_minutes: int = 5,
    swarm_bolus: bool = False,
) -> list[DecisionExplanation]:
    """Replay the controller and safety pipeline on ``records`` to produce one
    ``DecisionExplanation`` per timestep.

    Args:
        records: Output of ``run_evaluation`` or ``run_retrospective``.
        seed_glucose_mgdl: The CGM value at the timestep *before* the first
            record (the "seed" snapshot).  Used to compute the delta for the
            first record.  Defaults to 140.0 (SimulationSnapshot default).
            Pass ``readings[0].glucose_mgdl`` for retrospective runs.
        target_glucose_mgdl: Target glucose used during the original run.
        correction_factor_mgdl_per_unit: ISF used during the original run.
        min_excursion_delta_mgdl: Noise filter used during the original run.
        microbolus_fraction: Dose fraction used during the original run.
        safety_thresholds: Safety config used during the original run.
        step_minutes: CGM step duration (minutes).  Used to convert the
            per-step delta to a per-minute rate.

    Returns:
        List of ``DecisionExplanation`` objects, one per record, in the same
        order as ``records``.
    """
    if not records:
        return []

    safety_thresholds = safety_thresholds or SafetyThresholds()

    # CGM history window — seed with the step before the first record
    cgm_history: list[float] = [seed_glucose_mgdl]
    suspend_state = SuspendState()
    arming_state = ArmingState()
    explanations: list[DecisionExplanation] = []

    previous_glucose = seed_glucose_mgdl

    # Pre-bolus de-duplication state — mirrors the runner so that the annotator
    # fires the pre-bolus at most once per meal event, matching the original run.
    meal_prebolus_fired = False
    meal_none_streak = 0
    _prev_acc_ann: float = 0.0

    for record in records:
        current_glucose = record.cgm_glucose_mgdl
        iob_u = record.insulin_on_board_u

        cgm_history.append(current_glucose)
        if len(cgm_history) > _HISTORY_WINDOW:
            cgm_history.pop(0)

        controller_inputs = ControllerInputs(
            current_glucose_mgdl=current_glucose,
            previous_glucose_mgdl=previous_glucose,
            insulin_on_board_u=iob_u,
            target_glucose_mgdl=target_glucose_mgdl,
            correction_factor_mgdl_per_unit=correction_factor_mgdl_per_unit,
            glucose_history=list(cgm_history),
            min_excursion_delta_mgdl=min_excursion_delta_mgdl,
            microbolus_fraction=microbolus_fraction,
            step_minutes=step_minutes,
            prebolus_already_fired=meal_prebolus_fired,
            swarm_bolus=swarm_bolus,
        )

        signal, prediction, recommendation, classification = run_controller(controller_inputs)
        meal_signal = classification.meal_signal if classification else None

        current_acc_ann = signal.acceleration_mgdl_per_min2
        jerk_ann = (current_acc_ann - _prev_acc_ann) / step_minutes
        _prev_acc_ann = current_acc_ann

        # Update pre-bolus state — mirrors runner logic
        if meal_signal is None or meal_signal.phase == MealPhase.NONE:
            meal_none_streak += 1
            if meal_none_streak >= _MEAL_RESET_STREAK:
                meal_prebolus_fired = False
        else:
            meal_none_streak = 0
            if recommendation.reason.startswith(("pre-bolus | meal ONSET", "SWARM pre-bolus")):
                meal_prebolus_fired = True

        safety_inputs = build_safety_inputs(
            recommendation=recommendation,
            prediction=prediction,
            signal=signal,
            insulin_on_board_u=iob_u,
            current_glucose_mgdl=current_glucose,
            delivered_last_30min_u=record.delivered_last_30min_u,
            delivered_last_2hr_u=record.delivered_last_2hr_u,
            jerk_mgdl_per_min3=jerk_ann,
        )

        safety_decision, suspend_state, arming_state = evaluate_safety_stateful(
            inputs=safety_inputs,
            thresholds=safety_thresholds,
            suspend_state=suspend_state,
            arming_state=arming_state,
        )

        # ── Derive display values ─────────────────────────────────────────
        trend_rate = signal.rate_mgdl_per_min  # already normalised to mg/dL/min

        if trend_rate >= _RISE_THRESHOLD_PER_MIN:
            trend_arrow = "↑"
        elif trend_rate <= _FALL_THRESHOLD_PER_MIN:
            trend_arrow = "↓"
        else:
            trend_arrow = "→"

        is_now_suspended = suspend_state.is_suspended
        gate = gate_from_reason(safety_decision.reason, is_now_suspended)
        suspension_step = suspend_state.steps_suspended if is_now_suspended else 0

        exp = DecisionExplanation(
            timestamp_min=record.timestamp_min,
            cgm_mgdl=current_glucose,
            trend_arrow=trend_arrow,
            trend_rate_mgdl_per_min=trend_rate,
            predicted_glucose_mgdl=prediction.predicted_glucose_mgdl,
            prediction_horizon_min=prediction.prediction_horizon_minutes,
            iob_u=iob_u,
            recommended_units=recommendation.recommended_units,
            controller_reason=recommendation.reason,
            safety_gate=gate,
            safety_reason=safety_decision.reason,
            safety_status=safety_decision.status,
            safety_final_units=safety_decision.final_units,
            delivered_units=record.pump_delivered_units,
            is_suspended=is_now_suspended,
            suspension_step=suspension_step,
            narrative="",  # filled in below
        )
        exp = DecisionExplanation(
            **{**exp.__dict__, "narrative": build_narrative(exp)}
        )

        explanations.append(exp)
        previous_glucose = current_glucose

    return explanations
