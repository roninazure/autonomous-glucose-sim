"""SWARM Bolus — Autonomous Insulin Delivery Simulation.

Two modes only:
  1. Clinical Review  — run all 9 scenarios, score against ADA targets
  2. Closed Loop Demo — run one scenario, watch the controller in real time
"""
from __future__ import annotations

import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ags.evaluation.runner import run_evaluation
from ags.pump.state import PumpConfig
from ags.safety.state import SafetyThresholds
from ags.simulation.scenarios import (
    baseline_meal_scenario,
    dawn_phenomenon_scenario,
    exercise_hypoglycemia_scenario,
    late_correction_scenario,
    missed_bolus_scenario,
    overnight_stability_scenario,
    rapid_drop_scenario,
    stacked_corrections_scenario,
    sustained_basal_deficit_scenario,
)
from ags.simulation.engine import run_simulation

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="SWARM Bolus",
    page_icon="💉",
    layout="wide",
)

st.markdown(
    """
    <style>
    .metric-card {
        background: #1e2230;
        border-radius: 8px;
        padding: 1rem 1.25rem;
        text-align: center;
    }
    .metric-card h3 { font-size: 2rem; margin: 0; }
    .metric-card p  { font-size: 0.8rem; color: #aaa; margin: 0; }
    .pass  { color: #2ecc71; }
    .fail  { color: #e74c3c; }
    .warn  { color: #f39c12; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Constants ─────────────────────────────────────────────────────────────────

_STEP = 5          # CGM cadence in minutes
_TARGET = 110.0    # mg/dL target
_ISF    = 50.0     # insulin sensitivity factor

# ADA/EASD clinical pass criteria
_TIR_MIN     = 70.0   # % time in range (70–180 mg/dL)
_PEAK_MAX    = 250.0  # mg/dL
_HYPO_MAX    = 0      # steps below 70 mg/dL

_THRESHOLDS = SafetyThresholds()
_PUMP       = PumpConfig()

# ── Scenario registry ─────────────────────────────────────────────────────────

SCENARIOS: dict[str, object] = {
    "Baseline Meal":          baseline_meal_scenario,
    "Dawn Phenomenon":        dawn_phenomenon_scenario,
    "Sustained Basal Deficit":sustained_basal_deficit_scenario,
    "Exercise Hypoglycemia":  exercise_hypoglycemia_scenario,
    "Missed Bolus":           missed_bolus_scenario,
    "Late Correction":        late_correction_scenario,
    "Overnight Stability":    overnight_stability_scenario,
    "Stacked Corrections":    stacked_corrections_scenario,
    "Rapid Drop":             rapid_drop_scenario,
}

SCENARIO_DURATIONS: dict[str, int] = {
    "Baseline Meal":           180,
    "Dawn Phenomenon":         240,
    "Sustained Basal Deficit": 240,
    "Exercise Hypoglycemia":   120,
    "Missed Bolus":            180,
    "Late Correction":         180,
    "Overnight Stability":     480,
    "Stacked Corrections":     300,
    "Rapid Drop":              120,
}

# Scenarios where no insulin should be delivered (safety pass = no dosing)
_NO_INSULIN_SCENARIOS = {"Exercise Hypoglycemia", "Rapid Drop"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _verdict(name: str, tir: float, peak: float, hypo_steps: int) -> tuple[str, str]:
    """Return (label, css_class) verdict for a scenario result."""
    if name in _NO_INSULIN_SCENARIOS:
        return ("SAFE — no dosing", "pass") if hypo_steps == 0 else ("UNSAFE — hypo!", "fail")
    passed = tir >= _TIR_MIN and peak <= _PEAK_MAX and hypo_steps <= _HYPO_MAX
    if passed:
        return ("PASS", "pass")
    issues = []
    if tir < _TIR_MIN:
        issues.append(f"TIR {tir:.1f}%<{_TIR_MIN}%")
    if peak > _PEAK_MAX:
        issues.append(f"peak {peak:.0f}>{_PEAK_MAX}")
    if hypo_steps > _HYPO_MAX:
        issues.append(f"hypo {hypo_steps} steps")
    return ("FAIL — " + ", ".join(issues), "fail")


def _glucose_chart(records, title: str = "") -> go.Figure:
    times  = [r.timestamp_min for r in records]
    cgm    = [r.cgm_glucose_mgdl for r in records]

    fig = go.Figure()
    # Target band
    fig.add_hrect(y0=70, y1=180, fillcolor="rgba(46,204,113,0.10)", line_width=0)
    # CGM trace
    fig.add_trace(go.Scatter(x=times, y=cgm, mode="lines", name="CGM",
                             line=dict(color="#3498db", width=2)))
    # Danger lines
    fig.add_hline(y=70,  line_dash="dot", line_color="#e74c3c", opacity=0.6)
    fig.add_hline(y=180, line_dash="dot", line_color="#f39c12", opacity=0.4)
    fig.add_hline(y=250, line_dash="dot", line_color="#e74c3c", opacity=0.3)

    fig.update_layout(
        title=title,
        xaxis_title="Time (min)",
        yaxis_title="Glucose (mg/dL)",
        template="plotly_dark",
        height=300,
        margin=dict(t=40, b=30, l=50, r=20),
        showlegend=False,
    )
    return fig


def _insulin_chart(records) -> go.Figure:
    times     = [r.timestamp_min for r in records]
    delivered = [r.pump_delivered_units for r in records]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=times, y=delivered, name="Delivered",
                         marker_color="#9b59b6"))
    fig.update_layout(
        xaxis_title="Time (min)",
        yaxis_title="Insulin (U)",
        template="plotly_dark",
        height=220,
        margin=dict(t=10, b=30, l=50, r=20),
        showlegend=False,
    )
    return fig


def _get_clinical_summary(results: dict) -> str:
    """Call Claude to generate an AI clinical summary of scenario results."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return (
            "**API key not configured.**\n\n"
            "To enable AI clinical summaries, add your Anthropic API key as "
            "`ANTHROPIC_API_KEY` in Streamlit Cloud → Settings → Secrets."
        )

    lines = []
    for name, (records, summary, hypo_steps) in results.items():
        tir  = summary.percent_time_in_range
        peak = summary.peak_cgm_glucose_mgdl
        ins  = summary.total_insulin_delivered_u
        label, _ = _verdict(name, tir, peak, hypo_steps)
        lines.append(
            f"  - {name}: TIR={tir:.1f}%, peak={peak:.0f} mg/dL, "
            f"hypo steps={hypo_steps}, insulin={ins:.2f}U — {label}"
        )

    prompt = (
        "You are a clinical advisor reviewing autonomous insulin delivery simulation "
        "results for a physician audience.\n\n"
        "The SWARM Bolus autonomous controller was tested against 9 clinical scenarios. "
        "ADA/EASD pass criteria: TIR ≥70%, peak glucose <250 mg/dL, 0 hypoglycemia steps. "
        "The controller operates without any human intervention — CGM readings feed directly "
        "into the decision engine, which doses autonomously through a 7-gate safety layer.\n\n"
        "Results:\n" + "\n".join(lines) + "\n\n"
        "Write a concise clinical summary (3–4 paragraphs) for a physician reviewing this system. "
        "Cover: overall ADA/EASD performance, safety profile (hypo prevention, suspension), "
        "any scenarios of concern, and what these results suggest about readiness for the next "
        "stage of evaluation. Plain clinical language, flowing paragraphs, no bullet points."
    )

    try:
        import anthropic  # lazy import — only needed when summary button is clicked
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
    except Exception as exc:
        return f"**Error generating summary:** {exc}"


def _run_scenario(name: str, duration_minutes: int | None = None) -> tuple:
    sim_inputs = SCENARIOS[name]()
    dur = duration_minutes or SCENARIO_DURATIONS.get(name, 180)
    records, summary = run_evaluation(
        simulation_inputs=sim_inputs,
        safety_thresholds=_THRESHOLDS,
        pump_config=_PUMP,
        duration_minutes=dur,
        step_minutes=_STEP,
        target_glucose_mgdl=_TARGET,
        correction_factor_mgdl_per_unit=_ISF,
    )
    hypo_steps = summary.time_below_range_steps
    return records, summary, hypo_steps


# ── Sidebar ───────────────────────────────────────────────────────────────────

st.sidebar.title("SWARM Bolus")
st.sidebar.markdown("*Autonomous Insulin Delivery*")
st.sidebar.markdown("---")

mode = st.sidebar.radio(
    "Mode",
    ["Clinical Review", "Closed Loop Demo"],
    help="Clinical Review: full battery of 9 scenarios scored vs ADA targets.\n"
         "Closed Loop Demo: watch one scenario run step-by-step.",
)

# ── Header ────────────────────────────────────────────────────────────────────

st.title("SWARM Bolus — Autonomous Insulin Delivery")
st.markdown(
    "**Mission:** deliver insulin to the patient autonomously, without human intervention. "
    "CGM → Controller → Safety → Pump → Patient feedback loop, no manual bolus required."
)
st.markdown("---")


# ══════════════════════════════════════════════════════════════════════════════
# MODE 1 — CLINICAL REVIEW
# ══════════════════════════════════════════════════════════════════════════════

if mode == "Clinical Review":
    st.header("Clinical Review")
    st.markdown(
        "Runs all 9 evaluation scenarios against ADA/EASD targets: "
        "TIR ≥ 70%, peak < 250 mg/dL, 0 hypoglycaemia steps."
    )

    if st.button("Run All Scenarios", type="primary"):
        results = {}

        progress = st.progress(0, text="Running scenarios…")
        names    = list(SCENARIOS.keys())

        for i, name in enumerate(names):
            progress.progress((i + 1) / len(names), text=f"Running: {name}")
            records, summary, hypo_steps = _run_scenario(name)
            results[name] = (records, summary, hypo_steps)

        progress.empty()
        st.session_state["clinical_results"] = results

    results = st.session_state.get("clinical_results")

    if results:
        # ── Summary verdict table ─────────────────────────────────────────────
        st.subheader("Summary")

        rows = []
        all_pass = True
        for name, (records, summary, hypo_steps) in results.items():
            tir  = summary.percent_time_in_range
            peak = summary.peak_cgm_glucose_mgdl
            label, css = _verdict(name, tir, peak, hypo_steps)
            if css == "fail":
                all_pass = False
            rows.append({
                "Scenario":    name,
                "TIR %":       f"{tir:.1f}",
                "Peak mg/dL":  f"{peak:.0f}",
                "Hypo steps":  hypo_steps,
                "Insulin U":   f"{summary.total_insulin_delivered_u:.2f}",
                "Verdict":     label,
            })

        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        if all_pass:
            st.success("All scenarios PASSED ADA/EASD targets.")
        else:
            st.error("One or more scenarios FAILED. See details below.")

        # ── Per-scenario expanders ────────────────────────────────────────────
        st.subheader("Scenario Detail")

        for name, (records, summary, hypo_steps) in results.items():
            tir  = summary.percent_time_in_range
            peak = summary.peak_cgm_glucose_mgdl
            label, css = _verdict(name, tir, peak, hypo_steps)

            with st.expander(f"{name}  —  {label}"):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("TIR", f"{tir:.1f}%",
                          delta="pass" if tir >= _TIR_MIN else "fail",
                          delta_color="normal" if tir >= _TIR_MIN else "inverse")
                c2.metric("Peak", f"{peak:.0f} mg/dL",
                          delta="pass" if peak <= _PEAK_MAX else "fail",
                          delta_color="normal" if peak <= _PEAK_MAX else "inverse")
                c3.metric("Hypo steps", hypo_steps,
                          delta="pass" if hypo_steps == 0 else "fail",
                          delta_color="normal" if hypo_steps == 0 else "inverse")
                c4.metric("Insulin", f"{summary.total_insulin_delivered_u:.2f} U")

                st.plotly_chart(_glucose_chart(records, title="Glucose Trajectory"),
                                use_container_width=True, key=f"glucose_{name}")
                st.plotly_chart(_insulin_chart(records),
                                use_container_width=True, key=f"insulin_{name}")

        # ── CSV download ──────────────────────────────────────────────────────
        all_rows = []
        for name, (records, summary, hypo_steps) in results.items():
            for r in records:
                all_rows.append({
                    "scenario":            name,
                    "timestamp_min":       r.timestamp_min,
                    "cgm_glucose_mgdl":    r.cgm_glucose_mgdl,
                    "pump_delivered_u":    r.pump_delivered_units,
                    "insulin_on_board_u":  r.insulin_on_board_u,
                    "safety_status":       r.safety_status,
                    "glucose_cause":       r.glucose_cause,
                })

        csv = pd.DataFrame(all_rows).to_csv(index=False).encode()
        st.download_button(
            "Download full run CSV",
            data=csv,
            file_name="swarm_bolus_clinical_review.csv",
            mime="text/csv",
        )

        # ── AI Clinical Summary ───────────────────────────────────────────────
        st.markdown("---")
        if st.button("Generate AI Clinical Summary", type="primary"):
            with st.spinner("Generating clinical summary…"):
                summary_text = _get_clinical_summary(results)
            st.session_state["ai_summary"] = summary_text

        if st.session_state.get("ai_summary"):
            st.subheader("AI Clinical Summary")
            st.markdown(st.session_state["ai_summary"])


# ══════════════════════════════════════════════════════════════════════════════
# MODE 2 — CLOSED LOOP DEMO
# ══════════════════════════════════════════════════════════════════════════════

else:
    st.header("Closed Loop Demo")
    st.markdown(
        "Select a scenario and watch the autonomous controller manage glucose "
        "without any manual intervention."
    )

    st.sidebar.markdown("---")
    scenario_name = st.sidebar.selectbox("Scenario", list(SCENARIOS.keys()))

    if st.sidebar.button("Run Demo", type="primary"):
        with st.spinner(f"Running {scenario_name}…"):
            records, summary, hypo_steps = _run_scenario(scenario_name)

        tir  = summary.percent_time_in_range
        peak = summary.peak_cgm_glucose_mgdl
        label, css = _verdict(scenario_name, tir, peak, hypo_steps)

        # ── Verdict banner ────────────────────────────────────────────────────
        if css == "pass":
            st.success(f"**{label}**")
        elif css == "warn":
            st.warning(f"**{label}**")
        else:
            st.error(f"**{label}**")

        # ── 4 metric cards ────────────────────────────────────────────────────
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Time in Range", f"{tir:.1f}%",
                  help="Target ≥ 70%")
        c2.metric("Peak Glucose", f"{peak:.0f} mg/dL",
                  help="Target < 250 mg/dL")
        c3.metric("Hypo Steps", hypo_steps,
                  help="Target = 0")
        c4.metric("Total Insulin", f"{summary.total_insulin_delivered_u:.2f} U")

        # ── Glucose trajectory ────────────────────────────────────────────────
        st.subheader("Glucose Trajectory")
        st.plotly_chart(
            _glucose_chart(records, title=f"{scenario_name} — Glucose"),
            use_container_width=True,
        )

        # ── Insulin delivery ──────────────────────────────────────────────────
        st.subheader("Insulin Delivery")
        st.plotly_chart(_insulin_chart(records), use_container_width=True)

        # ── Decision log ─────────────────────────────────────────────────────
        with st.expander("Controller Decision Log"):
            log_rows = [
                {
                    "t (min)":          r.timestamp_min,
                    "CGM (mg/dL)":      f"{r.cgm_glucose_mgdl:.1f}",
                    "Cause":            r.glucose_cause,
                    "Recommended (U)":  f"{r.recommended_units:.3f}",
                    "Safety":           r.safety_status,
                    "Delivered (U)":    f"{r.pump_delivered_units:.3f}",
                    "IOB (U)":          f"{r.insulin_on_board_u:.3f}",
                    "Suspended":        r.is_suspended,
                }
                for r in records
            ]
            st.dataframe(pd.DataFrame(log_rows), use_container_width=True, hide_index=True)
    else:
        st.info("Select a scenario in the sidebar and click **Run Demo** to start.")
