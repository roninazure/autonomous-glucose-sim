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


st.set_page_config(
    page_title="SWARM Bolus",
    page_icon="🧪",
    layout="wide",
)

st.title("SWARM Bolus")
st.subheader("Autonomous Glucose Simulation Dashboard")

with st.sidebar:
    st.header("Simulation Controls")

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

    run_button = st.button("Run Evaluation", type="primary")

if run_button:
    simulation_inputs = baseline_meal_scenario()

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

    records, summary = run_evaluation(
        simulation_inputs=simulation_inputs,
        safety_thresholds=safety_thresholds,
        pump_config=pump_config,
        duration_minutes=duration_minutes,
        step_minutes=step_minutes,
        seed=42,
    )

    records_df = pd.DataFrame([r.__dict__ for r in records])

    metric_1, metric_2, metric_3, metric_4 = st.columns(4)
    metric_1.metric("Simulation Steps", summary.total_timesteps)
    metric_2.metric("Time in Range %", f"{summary.percent_time_in_range:.2f}%")
    metric_3.metric("Avg CGM", f"{summary.average_cgm_glucose_mgdl:.2f} mg/dL")
    metric_4.metric("Peak CGM", f"{summary.peak_cgm_glucose_mgdl:.2f} mg/dL")

    metric_5, metric_6, metric_7, metric_8 = st.columns(4)
    metric_5.metric("Recommended Insulin", f"{summary.total_recommended_insulin_u:.2f} U")
    metric_6.metric("Delivered Insulin", f"{summary.total_insulin_delivered_u:.2f} U")
    metric_7.metric("Blocked Decisions", summary.blocked_decisions)
    metric_8.metric("Clipped Decisions", summary.clipped_decisions)

    st.markdown("### Glucose Trace")
    st.line_chart(
        records_df.set_index("timestamp_min")[["true_glucose_mgdl", "cgm_glucose_mgdl"]]
    )

    st.markdown("### Insulin Trace")
    st.line_chart(
        records_df.set_index("timestamp_min")[["recommended_units", "pump_delivered_units"]]
    )

    st.markdown("### Safety Decision Counts")
    safety_counts = records_df["safety_status"].value_counts()
    st.bar_chart(safety_counts)

    st.markdown("### Decision Explainability")
    explain_df = records_df[
        [
            "timestamp_min",
            "cgm_glucose_mgdl",
            "recommended_units",
            "safety_status",
            "safety_final_units",
            "pump_delivered_units",
        ]
    ].copy()

    explain_df["insulin_gap_u"] = (
        explain_df["recommended_units"] - explain_df["pump_delivered_units"]
    ).round(2)

    explain_df["explanation"] = explain_df["safety_status"].map(
        {
            "allowed": "Recommendation passed safety and pump delivery as expected.",
            "clipped": "Recommendation exceeded a safety or pump delivery limit and was reduced.",
            "blocked": "Recommendation was blocked by a safety rule before delivery.",
        }
    )

    st.dataframe(explain_df, width="stretch")

    st.markdown("### Full Timestep Records")
    st.dataframe(records_df, width="stretch")

else:
    st.info("Choose settings in the sidebar, then click 'Run Evaluation'.")
