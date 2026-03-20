from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from ags.evaluation.runner import run_evaluation
from ags.pump.state import PumpConfig
from ags.safety.state import SafetyThresholds
from ags.simulation.scenarios import baseline_meal_scenario
from ags.simulation.state import MealEvent, SimulationInputs


def build_scenario(name: str) -> SimulationInputs:
    if name == "Baseline Meal":
        return baseline_meal_scenario()

    if name == "Fasting Baseline":
        return SimulationInputs(
            insulin_sensitivity_mgdl_per_unit=50.0,
            carb_impact_mgdl_per_g=3.0,
            baseline_drift_mgdl_per_step=0.0,
            meal_events=[],
        )

    if name == "Large Meal Spike":
        return SimulationInputs(
            insulin_sensitivity_mgdl_per_unit=50.0,
            carb_impact_mgdl_per_g=3.0,
            baseline_drift_mgdl_per_step=0.0,
            meal_events=[
                MealEvent(timestamp_min=30, carbs_g=90.0, absorption_minutes=150),
            ],
        )

    return baseline_meal_scenario()


st.set_page_config(
    page_title="SWARM Bolus",
    page_icon="🧪",
    layout="wide",
)

st.markdown(
    """
    <style>
    ::-webkit-scrollbar {
        width: 16px;
        height: 16px;
    }
    ::-webkit-scrollbar-thumb {
        background: #888;
        border-radius: 8px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #666;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("SWARM Bolus")
st.subheader("Autonomous Glucose Simulation Dashboard")
st.caption("AI-driven insulin decision engine with safety constraints and explainability")
st.markdown("---")

scenario_options = [
    "Baseline Meal",
    "Fasting Baseline",
    "Large Meal Spike",
]

with st.sidebar:
    st.header("Simulation Controls")

    scenario_a_name = st.selectbox(
        "Scenario A",
        options=scenario_options,
        index=0,
    )

    scenario_b_name = st.selectbox(
        "Scenario B",
        options=scenario_options,
        index=2,
    )

    duration_minutes = st.slider(
        "Duration (minutes)",
        min_value=30,
        max_value=360,
        value=180,
        step=30,
    )

    step_minutes = st.selectbox(
        "Timestep (minutes)",
        options=[5, 10, 15],
        index=0,
    )

    st.header("Safety Settings")

    max_units_per_interval = st.slider(
        "Max units per interval",
        min_value=0.1,
        max_value=3.0,
        value=1.0,
        step=0.05,
    )

    max_insulin_on_board_u = st.slider(
        "Max insulin on board (U)",
        min_value=0.5,
        max_value=10.0,
        value=3.0,
        step=0.1,
    )

    min_predicted_glucose_mgdl = st.slider(
        "Min predicted glucose (mg/dL)",
        min_value=60,
        max_value=120,
        value=80,
        step=1,
    )

    require_confirmed_trend = st.checkbox(
        "Require confirmed rising trend",
        value=True,
    )

    st.header("Pump Settings")

    dose_increment_u = st.selectbox(
        "Dose increment (U)",
        options=[0.05, 0.1],
        index=0,
    )

    pump_max_units_per_interval = st.slider(
        "Pump max units per interval",
        min_value=0.1,
        max_value=3.0,
        value=1.0,
        step=0.05,
    )

    run_button = st.button("Run Comparison", type="primary")

if run_button:
    safety_thresholds = SafetyThresholds(
        max_units_per_interval=max_units_per_interval,
        max_insulin_on_board_u=max_insulin_on_board_u,
        min_predicted_glucose_mgdl=float(min_predicted_glucose_mgdl),
        require_confirmed_trend=require_confirmed_trend,
    )

    pump_config = PumpConfig(
        dose_increment_u=dose_increment_u,
        max_units_per_interval=pump_max_units_per_interval,
    )

    records_a, summary_a = run_evaluation(
        simulation_inputs=build_scenario(scenario_a_name),
        safety_thresholds=safety_thresholds,
        pump_config=pump_config,
        duration_minutes=duration_minutes,
        step_minutes=step_minutes,
        seed=42,
    )

    records_b, summary_b = run_evaluation(
        simulation_inputs=build_scenario(scenario_b_name),
        safety_thresholds=safety_thresholds,
        pump_config=pump_config,
        duration_minutes=duration_minutes,
        step_minutes=step_minutes,
        seed=42,
    )

    records_a_df = pd.DataFrame([r.__dict__ for r in records_a])
    records_b_df = pd.DataFrame([r.__dict__ for r in records_b])

    st.markdown("## Scenario Comparison")

    left, right = st.columns(2)

    with left:
        st.markdown(f"### Scenario A: {scenario_a_name}")
        a1, a2, a3, a4 = st.columns(4)
        a1.metric("Steps", summary_a.total_timesteps)
        a2.metric("Time in Range %", f"{summary_a.percent_time_in_range:.2f}%")
        a3.metric("Avg CGM", f"{summary_a.average_cgm_glucose_mgdl:.2f}")
        a4.metric("Peak CGM", f"{summary_a.peak_cgm_glucose_mgdl:.2f}")

        a5, a6, a7, a8 = st.columns(4)
        a5.metric("Recommended U", f"{summary_a.total_recommended_insulin_u:.2f}")
        a6.metric("Delivered U", f"{summary_a.total_insulin_delivered_u:.2f}")
        a7.metric("Blocked", summary_a.blocked_decisions)
        a8.metric("Clipped", summary_a.clipped_decisions)

    with right:
        st.markdown(f"### Scenario B: {scenario_b_name}")
        b1, b2, b3, b4 = st.columns(4)
        b1.metric("Steps", summary_b.total_timesteps)
        b2.metric("Time in Range %", f"{summary_b.percent_time_in_range:.2f}%")
        b3.metric("Avg CGM", f"{summary_b.average_cgm_glucose_mgdl:.2f}")
        b4.metric("Peak CGM", f"{summary_b.peak_cgm_glucose_mgdl:.2f}")

        b5, b6, b7, b8 = st.columns(4)
        b5.metric("Recommended U", f"{summary_b.total_recommended_insulin_u:.2f}")
        b6.metric("Delivered U", f"{summary_b.total_insulin_delivered_u:.2f}")
        b7.metric("Blocked", summary_b.blocked_decisions)
        b8.metric("Clipped", summary_b.clipped_decisions)

    st.markdown("### Comparison Snapshot")
    compare_df = pd.DataFrame(
        {
            "Metric": [
                "Time in Range %",
                "Average CGM",
                "Peak CGM",
                "Time Above 250",
                "Glucose Variability (SD)",
                "Recommended Insulin",
                "Delivered Insulin",
                "Blocked Decisions",
                "Clipped Decisions",
                "Allowed Decisions",
            ],
            "Scenario A": [
                summary_a.percent_time_in_range,
                summary_a.average_cgm_glucose_mgdl,
                summary_a.peak_cgm_glucose_mgdl,
                summary_a.time_above_250_steps,
                summary_a.glucose_variability_sd_mgdl,
                summary_a.total_recommended_insulin_u,
                summary_a.total_insulin_delivered_u,
                summary_a.blocked_decisions,
                summary_a.clipped_decisions,
                summary_a.allowed_decisions,
            ],
            "Scenario B": [
                summary_b.percent_time_in_range,
                summary_b.average_cgm_glucose_mgdl,
                summary_b.peak_cgm_glucose_mgdl,
                summary_b.time_above_250_steps,
                summary_b.glucose_variability_sd_mgdl,
                summary_b.total_recommended_insulin_u,
                summary_b.total_insulin_delivered_u,
                summary_b.blocked_decisions,
                summary_b.clipped_decisions,
                summary_b.allowed_decisions,
            ],
        }
    )
    st.dataframe(compare_df, width="stretch")

    st.markdown("### CGM Trajectory Comparison")
    cgm_compare_df = pd.DataFrame(
        {
            "time": records_a_df["timestamp_min"],
            "Scenario A CGM": records_a_df["cgm_glucose_mgdl"],
            "Scenario B CGM": records_b_df["cgm_glucose_mgdl"],
        }
    ).set_index("time")
    st.line_chart(cgm_compare_df)

    st.markdown("### Insulin Delivery Comparison")
    insulin_compare_df = pd.DataFrame(
        {
            "time": records_a_df["timestamp_min"],
            "Scenario A Recommended": records_a_df["recommended_units"],
            "Scenario A Delivered": records_a_df["pump_delivered_units"],
            "Scenario B Recommended": records_b_df["recommended_units"],
            "Scenario B Delivered": records_b_df["pump_delivered_units"],
        }
    ).set_index("time")
    st.line_chart(insulin_compare_df)

    st.markdown("### Safety Intervention Overlay")

    safety_overlay_df = pd.DataFrame({
        "time": records_a_df["timestamp_min"],
        "A Blocked": (records_a_df["safety_status"] == "blocked").astype(int),
        "A Clipped": (records_a_df["safety_status"] == "clipped").astype(int),
        "B Blocked": (records_b_df["safety_status"] == "blocked").astype(int),
        "B Clipped": (records_b_df["safety_status"] == "clipped").astype(int),
    }).set_index("time")

    st.bar_chart(safety_overlay_df)

    st.markdown("### AI Comparative Verdict")

    verdict_lines = []

    # Time in range comparison
    if summary_a.percent_time_in_range > summary_b.percent_time_in_range:
        verdict_lines.append("Scenario A maintains better glucose control (higher time in range).")
    elif summary_b.percent_time_in_range > summary_a.percent_time_in_range:
        verdict_lines.append("Scenario B maintains better glucose control (higher time in range).")

    # Peak glucose comparison
    if summary_b.peak_cgm_glucose_mgdl > summary_a.peak_cgm_glucose_mgdl:
        verdict_lines.append("Scenario B experiences higher glucose spikes, indicating greater metabolic stress.")

    # Safety intervention comparison
    if summary_b.blocked_decisions + summary_b.clipped_decisions > summary_a.blocked_decisions + summary_a.clipped_decisions:
        verdict_lines.append("Scenario B triggers more safety interventions, suggesting constraint pressure on dosing.")
    elif summary_a.blocked_decisions + summary_a.clipped_decisions > summary_b.blocked_decisions + summary_b.clipped_decisions:
        verdict_lines.append("Scenario A triggers more safety interventions.")

    # Insulin comparison
    if summary_b.total_insulin_delivered_u > summary_a.total_insulin_delivered_u:
        verdict_lines.append("Scenario B requires significantly more insulin delivery.")

    if not verdict_lines:
        verdict_lines.append("Both scenarios behave similarly under current constraints.")

    for line in verdict_lines:
        st.write(f"- {line}")



else:
    st.info("Choose Scenario A and Scenario B in the sidebar, then click 'Run Comparison'.")
