from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

import json

from ags.evaluation.profile_sweep import build_sweep_export, run_profile_sweep
from ags.evaluation.profiles import ALL_PROFILES
from ags.evaluation.report import generate_report
from ags.evaluation.runner import run_evaluation
from ags.pump.state import PumpConfig
from ags.explainability.annotator import annotate_run
from ags.explainability.state import GATE_COLOURS, GATE_LABELS
from ags.retrospective.loader import CgmParseError, parse_cgm_text, readings_to_csv
from ags.retrospective.reference_traces import REFERENCE_TRACE_DESCRIPTIONS, REFERENCE_TRACES
from ags.retrospective.runner import RetrospectiveConfig, run_retrospective
from ags.safety.state import SafetyThresholds
from ags.simulation.scenarios import (
    baseline_meal_scenario,
    dawn_phenomenon_scenario,
    exercise_hypoglycemia_scenario,
    late_correction_scenario,
    missed_bolus_scenario,
)
from ags.simulation.state import MealEvent, SimulationInputs

# ── Palette ─────────────────────────────────────────────────────────────────
BG       = "#050a06"
BG2      = "#0b140c"
BG3      = "#0f1a10"
NEON     = "#39ff14"
NEON_DIM = "#1a6b09"
RED      = "#ff4d6d"
AMBER    = "#ffbe0b"
CYAN     = "#00f5ff"
WHITE    = "#d4ecd4"
MUTED    = "#3d6b3d"
GRID     = "#0d200d"

# ── Page config (must be first Streamlit call) ───────────────────────────────
st.set_page_config(
    page_title="SWARM Bolus",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ───────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Orbitron:wght@400;700;900&display=swap');

html, body, [class*="css"] {{
    background-color: {BG} !important;
    color: {WHITE} !important;
    font-family: 'Share Tech Mono', monospace !important;
}}

/* Sidebar */
[data-testid="stSidebar"] {{
    background-color: {BG2} !important;
    border-right: 1px solid {NEON_DIM} !important;
}}
[data-testid="stSidebar"] * {{
    font-family: 'Share Tech Mono', monospace !important;
}}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {{
    color: {NEON} !important;
    font-size: 0.65rem !important;
    letter-spacing: 3px;
    text-transform: uppercase;
    padding-bottom: 6px;
    border-bottom: 1px solid {NEON_DIM};
    margin-top: 1.5rem !important;
}}

/* Primary button */
[data-testid="stButton"] > button[kind="primary"] {{
    background: transparent !important;
    border: 1px solid {NEON} !important;
    color: {NEON} !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 0.8rem !important;
    letter-spacing: 4px;
    text-transform: uppercase;
    width: 100%;
    padding: 0.65rem !important;
    box-shadow: 0 0 12px {NEON_DIM};
    transition: all 0.15s ease;
}}
[data-testid="stButton"] > button[kind="primary"]:hover {{
    background: {NEON} !important;
    color: {BG} !important;
    box-shadow: 0 0 24px {NEON};
}}

/* Metrics */
[data-testid="metric-container"] {{
    background-color: {BG2} !important;
    border: 1px solid {NEON_DIM} !important;
    border-radius: 3px !important;
    padding: 10px 14px !important;
}}
[data-testid="stMetricValue"] {{
    color: {NEON} !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 1.3rem !important;
    text-shadow: 0 0 8px {NEON_DIM};
}}
[data-testid="stMetricLabel"] {{
    color: {MUTED} !important;
    font-size: 0.6rem !important;
    letter-spacing: 2px;
    text-transform: uppercase;
}}

/* Dataframe */
[data-testid="stDataFrame"] {{
    border: 1px solid {NEON_DIM} !important;
}}
[data-testid="stDataFrame"] th {{
    background-color: {BG3} !important;
    color: {NEON} !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 0.7rem !important;
    letter-spacing: 2px;
    text-transform: uppercase;
}}
[data-testid="stDataFrame"] td {{
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 0.8rem !important;
    color: {WHITE} !important;
}}

/* Plotly containers */
[data-testid="stPlotlyChart"] {{
    border: 1px solid {NEON_DIM};
    border-radius: 3px;
    overflow: hidden;
}}

/* Info box */
[data-testid="stAlert"] {{
    background-color: {BG2} !important;
    border: 1px solid {NEON_DIM} !important;
    color: {WHITE} !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 0.8rem !important;
}}

/* Scrollbar */
::-webkit-scrollbar {{ width: 5px; height: 5px; }}
::-webkit-scrollbar-track {{ background: {BG}; }}
::-webkit-scrollbar-thumb {{ background: {NEON_DIM}; border-radius: 2px; }}
::-webkit-scrollbar-thumb:hover {{ background: {NEON}; }}

/* Divider */
hr {{ border-color: {NEON_DIM} !important; opacity: 0.5; }}

/* Section labels */
.section-label {{
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.6rem;
    color: {MUTED};
    letter-spacing: 4px;
    text-transform: uppercase;
    margin-bottom: 0.5rem;
}}
</style>
""", unsafe_allow_html=True)


# ── Helper: shared Plotly layout ────────────────────────────────────────────
def _layout(title: str = "", height: int = 320) -> dict:
    return dict(
        title=dict(
            text=title,
            font=dict(family="Share Tech Mono", size=11, color=NEON),
            x=0,
            pad=dict(l=0, t=4),
        ),
        height=height,
        margin=dict(l=55, r=20, t=44, b=44),
        plot_bgcolor=BG,
        paper_bgcolor=BG2,
        font=dict(family="Share Tech Mono", color=WHITE, size=10),
        xaxis=dict(
            gridcolor=GRID,
            linecolor=NEON_DIM,
            tickcolor=NEON_DIM,
            tickfont=dict(color=MUTED, size=9),
            title_font=dict(color=MUTED, size=9),
            zeroline=False,
        ),
        yaxis=dict(
            gridcolor=GRID,
            linecolor=NEON_DIM,
            tickcolor=NEON_DIM,
            tickfont=dict(color=MUTED, size=9),
            title_font=dict(color=MUTED, size=9),
            zeroline=False,
        ),
        legend=dict(
            bgcolor=BG,
            bordercolor=NEON_DIM,
            borderwidth=1,
            font=dict(family="Share Tech Mono", size=9, color=WHITE),
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
        ),
        hovermode="x unified",
    )


# ── Chart builders ───────────────────────────────────────────────────────────
def cgm_chart(df_a: pd.DataFrame, df_b: pd.DataFrame, name_a: str, name_b: str) -> go.Figure:
    fig = go.Figure()

    # In-range band
    fig.add_hrect(
        y0=70, y1=180,
        fillcolor="rgba(57,255,20,0.04)", line_width=0,
    )
    # Threshold lines
    fig.add_hline(y=70, line=dict(color=RED, width=1, dash="dot"),
                  annotation=dict(text="HYPO 70", font=dict(color=RED, size=8), xanchor="left"))
    fig.add_hline(y=180, line=dict(color=AMBER, width=1, dash="dot"),
                  annotation=dict(text="HYPER 180", font=dict(color=AMBER, size=8), xanchor="left"))
    fig.add_hline(y=250, line=dict(color=RED, width=1.5, dash="dash"),
                  annotation=dict(text="SEVERE 250", font=dict(color=RED, size=8), xanchor="left"))

    fig.add_trace(go.Scatter(
        x=df_a["timestamp_min"], y=df_a["cgm_glucose_mgdl"],
        mode="lines", name=f"A · {name_a}",
        line=dict(color=NEON, width=2),
        hovertemplate="%{y:.1f} mg/dL<extra>A</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=df_b["timestamp_min"], y=df_b["cgm_glucose_mgdl"],
        mode="lines", name=f"B · {name_b}",
        line=dict(color=CYAN, width=2, dash="dash"),
        hovertemplate="%{y:.1f} mg/dL<extra>B</extra>",
    ))

    layout = _layout("CGM TRAJECTORY", height=360)
    layout["yaxis"]["title"] = "mg/dL"
    layout["xaxis"]["title"] = "minutes"
    fig.update_layout(**layout)
    return fig


def insulin_chart(df_a: pd.DataFrame, df_b: pd.DataFrame, name_a: str, name_b: str) -> go.Figure:
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=df_a["timestamp_min"], y=df_a["pump_delivered_units"],
        name="A Delivered", marker_color=NEON, opacity=0.85,
        hovertemplate="%{y:.3f} U<extra>A Delivered</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=df_a["timestamp_min"], y=df_a["recommended_units"],
        mode="lines", name="A Recommended",
        line=dict(color=NEON_DIM, width=1.5, dash="dot"),
        hovertemplate="%{y:.3f} U<extra>A Recommended</extra>",
    ))
    fig.add_trace(go.Bar(
        x=df_b["timestamp_min"], y=df_b["pump_delivered_units"],
        name="B Delivered", marker_color=CYAN, opacity=0.5,
        hovertemplate="%{y:.3f} U<extra>B Delivered</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=df_b["timestamp_min"], y=df_b["recommended_units"],
        mode="lines", name="B Recommended",
        line=dict(color="#005a6b", width=1.5, dash="dot"),
        hovertemplate="%{y:.3f} U<extra>B Recommended</extra>",
    ))

    layout = _layout("INSULIN DELIVERY", height=280)
    layout["yaxis"]["title"] = "units"
    layout["xaxis"]["title"] = "minutes"
    layout["barmode"] = "overlay"
    fig.update_layout(**layout)
    return fig


def iob_chart(df_a: pd.DataFrame, df_b: pd.DataFrame, name_a: str, name_b: str) -> go.Figure:
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df_a["timestamp_min"], y=df_a["insulin_on_board_u"],
        mode="lines", name=f"A · {name_a}",
        line=dict(color=NEON, width=2),
        fill="tozeroy", fillcolor="rgba(57,255,20,0.07)",
        hovertemplate="%{y:.3f} U<extra>A IOB</extra>",
    ))
    fig.add_trace(go.Scatter(
        x=df_b["timestamp_min"], y=df_b["insulin_on_board_u"],
        mode="lines", name=f"B · {name_b}",
        line=dict(color=CYAN, width=2, dash="dash"),
        fill="tozeroy", fillcolor="rgba(0,245,255,0.05)",
        hovertemplate="%{y:.3f} U<extra>B IOB</extra>",
    ))

    layout = _layout("INSULIN ON BOARD", height=240)
    layout["yaxis"]["title"] = "IOB (U)"
    layout["xaxis"]["title"] = "minutes"
    fig.update_layout(**layout)
    return fig


def safety_chart(df_a: pd.DataFrame, df_b: pd.DataFrame, name_a: str, name_b: str) -> go.Figure:
    fig = go.Figure()

    for df, label, col in [(df_a, "A", NEON), (df_b, "B", CYAN)]:
        blocked = df[df["safety_status"] == "blocked"]
        clipped = df[df["safety_status"] == "clipped"]
        if not blocked.empty:
            fig.add_trace(go.Scatter(
                x=blocked["timestamp_min"], y=[label] * len(blocked),
                mode="markers", name=f"{label} Blocked",
                marker=dict(symbol="x", size=12, color=RED, line=dict(width=2, color=RED)),
                hovertemplate="t=%{x} min — BLOCKED<extra>" + label + "</extra>",
            ))
        if not clipped.empty:
            fig.add_trace(go.Scatter(
                x=clipped["timestamp_min"], y=[label] * len(clipped),
                mode="markers", name=f"{label} Clipped",
                marker=dict(symbol="triangle-up", size=11, color=AMBER, line=dict(width=1, color=AMBER)),
                hovertemplate="t=%{x} min — CLIPPED<extra>" + label + "</extra>",
            ))

    layout = _layout("SAFETY INTERVENTIONS", height=200)
    layout["xaxis"]["title"] = "minutes"
    layout["yaxis"]["categoryorder"] = "array"
    layout["yaxis"]["categoryarray"] = ["B", "A"]
    layout["margin"]["l"] = 40
    fig.update_layout(**layout)
    return fig


# ── Scenario metadata ────────────────────────────────────────────────────────
SCENARIO_DESCRIPTIONS = {
    "Baseline Meal":        "45g carbs · standard ISF · controller proves baseline TIR",
    "Fasting Baseline":     "No meal · flat drift · tests controller restraint (zero bolus pressure)",
    "Large Meal Spike":     "90g carbs · steep post-prandial climb · stress-tests dosing cap",
    "Dawn Phenomenon":      "No meal · cortisol-driven drift · slow rise the controller must catch",
    "Exercise Hypoglycemia":"Negative drift · high ISF · safety layer must block compounding drops",
    "Missed Bolus":         "75g meal · no pre-bolus · tests retroactive correction recovery",
    "Late Correction":      "60g meal + snack · delayed insulin · timing mismatch risk",
}


# ── Decision Timeline panel ───────────────────────────────────────────────────

def decision_timeline_panel(
    explanations: list,
    key_suffix: str = "",
) -> None:
    """Render an expandable per-step decision timeline table + drill-down card.

    Shows a colour-coded row per timestep (gate colour), a trend sparkline in
    the table, and a detailed monospace card for the user-selected step.
    """
    if not explanations:
        return

    with st.expander("▶  DECISION TIMELINE", expanded=False):
        # ── Build display DataFrame ─────────────────────────────────────
        rows = []
        gate_ids = []
        for exp in explanations:
            rows.append({
                "t (min)": exp.timestamp_min,
                "CGM": f"{exp.cgm_mgdl:.0f}",
                "trend": f"{exp.trend_arrow} {exp.trend_rate_mgdl_per_min:+.1f}/min",
                "pred +30": f"{exp.predicted_glucose_mgdl:.0f}",
                "IOB (U)": f"{exp.iob_u:.2f}",
                "rec'd (U)": f"{exp.recommended_units:.3f}",
                "gate": GATE_LABELS.get(exp.safety_gate, exp.safety_gate),
                "delivered (U)": f"{exp.delivered_units:.3f}",
                "narrative": exp.narrative,
            })
            gate_ids.append(exp.safety_gate)

        import pandas as _pd
        _tl_df = _pd.DataFrame(rows)
        _gate_id_series = gate_ids  # parallel list for styling

        def _style_gate(row):
            gate_id = _gate_id_series[row.name]
            fg = GATE_COLOURS.get(gate_id, "#888888")
            bg = f"{fg}22"
            result = [""] * len(row)
            try:
                gate_idx = list(_tl_df.columns).index("gate")
                result[gate_idx] = f"background-color:{bg}; color:{fg}; font-weight:700;"
            except ValueError:
                pass
            return result

        _styled = _tl_df.style.apply(_style_gate, axis=1)
        st.dataframe(_styled, use_container_width=True, hide_index=True)

        # ── Step drill-down ─────────────────────────────────────────────
        st.markdown(f"""
        <div style="font-family:'Share Tech Mono',monospace; font-size:0.55rem;
                    color:{MUTED}; letter-spacing:3px; text-transform:uppercase;
                    margin:1rem 0 0.4rem 0;">── STEP DRILL-DOWN</div>
        """, unsafe_allow_html=True)

        _ts_options = [f"t = {e.timestamp_min} min" for e in explanations]
        _selected_label = st.selectbox(
            "Select timestep",
            _ts_options,
            key=f"timeline_step_{key_suffix}",
            label_visibility="collapsed",
        )
        _sel_idx = _ts_options.index(_selected_label)
        _e = explanations[_sel_idx]

        _gate_fg = GATE_COLOURS.get(_e.safety_gate, "#888888")
        _gate_lbl = GATE_LABELS.get(_e.safety_gate, _e.safety_gate)
        _susp_line = (
            f"  suspension    : step {_e.suspension_step}\n"
            if _e.is_suspended else ""
        )

        st.markdown(f"""
<div style="background:{BG2}; border:1px solid {NEON_DIM}; border-left:3px solid {_gate_fg};
            border-radius:3px; padding:1rem 1.25rem; margin-top:0.25rem;
            font-family:'Share Tech Mono',monospace; font-size:0.72rem;
            color:{WHITE}; line-height:1.9; white-space:pre;">
<span style="color:{NEON_DIM}">┌─ t = {_e.timestamp_min} min ──────────────────────────────────────</span>
<span style="color:{CYAN}">  cgm            : {_e.cgm_mgdl:.1f} mg/dL</span>
<span style="color:{WHITE}">  trend           : {_e.trend_arrow}  {_e.trend_rate_mgdl_per_min:+.2f} mg/dL/min</span>
<span style="color:{WHITE}">  predicted +{_e.prediction_horizon_min}   : {_e.predicted_glucose_mgdl:.1f} mg/dL</span>
<span style="color:{WHITE}">  IOB             : {_e.iob_u:.3f} U</span>
<span style="color:{NEON_DIM}">├─ controller ──────────────────────────────────────────────────</span>
<span style="color:{WHITE}">  recommended     : {_e.recommended_units:.3f} U</span>
<span style="color:{MUTED}">  reason          : {_e.controller_reason}</span>
<span style="color:{NEON_DIM}">├─ safety ───────────────────────────────────────────────────────</span>
<span style="color:{_gate_fg}">  gate            : {_gate_lbl}</span>
<span style="color:{MUTED}">  reason          : {_e.safety_reason}</span>
<span style="color:{WHITE}">  status          : {_e.safety_status}</span>
<span style="color:{WHITE}">  final units     : {_e.safety_final_units:.3f} U</span>{_susp_line}
<span style="color:{NEON_DIM}">├─ delivery ─────────────────────────────────────────────────────</span>
<span style="color:{NEON}">  delivered       : {_e.delivered_units:.3f} U</span>
<span style="color:{NEON_DIM}">├─ narrative ────────────────────────────────────────────────────</span>
<span style="color:{WHITE}">  {_e.narrative}</span>
<span style="color:{NEON_DIM}">└──────────────────────────────────────────────────────────────</span>
</div>
        """, unsafe_allow_html=True)


# ── Scenario builder ─────────────────────────────────────────────────────────
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
    if name == "Dawn Phenomenon":
        return dawn_phenomenon_scenario()
    if name == "Exercise Hypoglycemia":
        return exercise_hypoglycemia_scenario()
    if name == "Missed Bolus":
        return missed_bolus_scenario()
    if name == "Late Correction":
        return late_correction_scenario()
    return baseline_meal_scenario()


# ── Header ───────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="padding:2rem 0 1.5rem 0; border-bottom:1px solid {NEON_DIM}; margin-bottom:2rem;">
  <div style="font-family:'Orbitron',monospace; font-size:2.2rem; font-weight:900;
              color:{NEON}; letter-spacing:10px; text-transform:uppercase;
              text-shadow:0 0 20px {NEON}, 0 0 60px {NEON_DIM}; line-height:1;">
    ⬡ SWARM BOLUS
  </div>
  <div style="font-family:'Share Tech Mono',monospace; font-size:0.75rem;
              color:{MUTED}; letter-spacing:5px; margin-top:0.5rem; text-transform:uppercase;">
    Autonomous Glucose Simulation · 2-Compartment PK/PD · Gamma Gut Model
  </div>
  <div style="margin-top:1rem; display:flex; gap:0.75rem; flex-wrap:wrap; align-items:center;">
    <span style="background:{BG2}; border:1px solid {RED}; color:{RED};
                 padding:3px 12px; font-size:0.6rem; letter-spacing:2px;
                 font-family:'Share Tech Mono',monospace; text-transform:uppercase;">
      ⚠ SIMULATION ONLY — NOT CLINICAL SOFTWARE
    </span>
    <span style="background:{BG2}; border:1px solid {NEON_DIM}; color:{NEON};
                 padding:3px 12px; font-size:0.6rem; letter-spacing:2px;
                 font-family:'Share Tech Mono',monospace; text-transform:uppercase;">
      ◉ IOB FEEDBACK ACTIVE
    </span>
    <span style="background:{BG2}; border:1px solid {NEON_DIM}; color:{NEON};
                 padding:3px 12px; font-size:0.6rem; letter-spacing:2px;
                 font-family:'Share Tech Mono',monospace; text-transform:uppercase;">
      ◉ SAFETY LAYER ENABLED
    </span>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ──────────────────────────────────────────────────────────────────
SCENARIO_OPTIONS = [
    "Baseline Meal",
    "Fasting Baseline",
    "Large Meal Spike",
    "Dawn Phenomenon",
    "Exercise Hypoglycemia",
    "Missed Bolus",
    "Late Correction",
]

with st.sidebar:
    st.markdown(f"""
    <div style="font-family:'Orbitron',monospace; font-size:0.9rem; font-weight:700;
                color:{NEON}; letter-spacing:4px; text-transform:uppercase;
                text-shadow:0 0 10px {NEON_DIM}; padding:0.5rem 0 1rem 0;
                border-bottom:1px solid {NEON_DIM};">
      ⬡ CONTROLS
    </div>
    """, unsafe_allow_html=True)

    dashboard_mode = st.radio(
        "Mode",
        ["Comparison", "Profile Sweep", "Retrospective Replay"],
        horizontal=False,
        help="Comparison: side-by-side scenario A vs B.  "
             "Profile Sweep: one scenario across all 4 patient archetypes.  "
             "Retrospective Replay: run controller against a real CGM trace.",
    )

    st.header("Scenarios")
    if dashboard_mode == "Comparison":
        scenario_a_name = st.selectbox("Scenario A", options=SCENARIO_OPTIONS, index=0)
        st.caption(SCENARIO_DESCRIPTIONS.get(scenario_a_name, ""))
        scenario_b_name = st.selectbox("Scenario B", options=SCENARIO_OPTIONS, index=2)
        st.caption(SCENARIO_DESCRIPTIONS.get(scenario_b_name, ""))
    elif dashboard_mode == "Profile Sweep":
        sweep_scenario_name = st.selectbox("Sweep Scenario", options=SCENARIO_OPTIONS, index=0)
        st.caption(SCENARIO_DESCRIPTIONS.get(sweep_scenario_name, ""))
        scenario_a_name = sweep_scenario_name   # keep downstream code happy
        scenario_b_name = sweep_scenario_name
    else:  # Retrospective Replay
        retro_source = st.radio("CGM Source", ["Reference trace", "Upload CSV", "Paste CSV"])
        retro_trace_name: str | None = None
        retro_uploaded_text: str | None = None

        if retro_source == "Reference trace":
            retro_trace_name = st.selectbox(
                "Select trace",
                options=list(REFERENCE_TRACES.keys()),
            )
            st.caption(REFERENCE_TRACE_DESCRIPTIONS.get(retro_trace_name, ""))
        elif retro_source == "Upload CSV":
            retro_file = st.file_uploader(
                "Upload CGM CSV",
                type=["csv", "txt"],
                help="Simple: timestamp_min,glucose_mgdl  or  Dexcom G6/G7 Clarity export.",
            )
            if retro_file is not None:
                retro_uploaded_text = retro_file.read().decode("utf-8", errors="replace")
        else:  # Paste CSV
            retro_uploaded_text = st.text_area(
                "Paste CGM data (timestamp_min,glucose_mgdl)",
                placeholder="timestamp_min,glucose_mgdl\n0,110\n5,115\n10,121\n...",
                height=160,
            )

        st.header("Controller (Retro)")
        retro_isf = st.slider(
            "Correction factor (ISF, mg/dL/U)",
            20.0, 120.0, 50.0, 1.0,
            help="Estimated insulin sensitivity for this patient.",
        )
        retro_peak = st.selectbox(
            "Insulin peak time (min)",
            [55, 65, 75],
            index=2,
            help="55 = Fiasp, 65 = Humalog, 75 = NovoLog",
        )
        scenario_a_name = retro_trace_name or "Custom trace"
        scenario_b_name = scenario_a_name

    st.header("Simulation")
    duration_minutes = st.slider("Duration (minutes)", 30, 360, 180, 30)
    step_minutes = st.selectbox("Timestep (minutes)", [5, 10, 15], index=0)

    st.header("Safety Layer")
    max_units_per_interval = st.slider("Max units per interval", 0.1, 3.0, 1.0, 0.05)
    max_insulin_on_board_u = st.slider("Max insulin on board (U)", 0.5, 10.0, 3.0, 0.1)
    min_predicted_glucose_mgdl = st.slider("Min predicted glucose (mg/dL)", 60, 120, 80, 1)
    require_confirmed_trend = st.checkbox("Require confirmed rising trend", value=True)

    st.header("Controller")
    min_excursion_delta = st.slider("Min excursion delta (mg/dL)", 0.0, 15.0, 0.0, 0.5,
                                    help="Minimum glucose change per step to trigger correction. Filters noise-driven micro-excursions.")
    microbolus_fraction = st.slider("Microbolus fraction", 0.1, 1.0, 1.0, 0.05,
                                    help="Scale correction down to a fraction of full dose. 0.25 = quarter-dose microbolus strategy.")

    st.header("Pump")
    dose_increment_u = st.selectbox("Dose increment (U)", [0.05, 0.1], index=0)
    pump_max_units_per_interval = st.slider("Pump max units per interval", 0.1, 3.0, 1.0, 0.05)

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    _btn_label = "▶  RUN COMPARISON" if dashboard_mode == "Comparison" else "▶  RUN PROFILE SWEEP"
    run_button = st.button(_btn_label, type="primary")

# ── Results ──────────────────────────────────────────────────────────────────
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

    if dashboard_mode == "Retrospective Replay":
        # ── Load readings ──────────────────────────────────────────────────
        try:
            if retro_source == "Reference trace" and retro_trace_name:
                retro_readings = list(REFERENCE_TRACES[retro_trace_name])
                _trace_label = retro_trace_name
            elif retro_uploaded_text and retro_uploaded_text.strip():
                retro_readings = parse_cgm_text(retro_uploaded_text)
                _trace_label = "Custom trace"
            else:
                st.error("No CGM data provided. Select a reference trace or upload/paste a CSV.")
                st.stop()
        except CgmParseError as exc:
            st.error(f"CGM parse error: {exc}")
            st.stop()

        retro_cfg = RetrospectiveConfig(
            target_glucose_mgdl=110.0,
            correction_factor_mgdl_per_unit=retro_isf,
            min_excursion_delta_mgdl=min_excursion_delta,
            microbolus_fraction=microbolus_fraction,
            insulin_peak_minutes=float(retro_peak),
        )
        with st.spinner(""):
            retro_records, retro_summary = run_retrospective(
                readings=retro_readings,
                config=retro_cfg,
                safety_thresholds=safety_thresholds,
                pump_config=pump_config,
            )

        retro_df = pd.DataFrame([r.__dict__ for r in retro_records])
        _duration_min = retro_readings[-1].timestamp_min
        _step_min = retro_readings[1].timestamp_min - retro_readings[0].timestamp_min

        # ── Header ─────────────────────────────────────────────────────────
        st.markdown(f"""
        <div style="font-family:'Share Tech Mono',monospace; font-size:0.6rem; color:{MUTED};
                    letter-spacing:4px; text-transform:uppercase; margin-bottom:0.75rem;">
          ── RETROSPECTIVE REPLAY · {_trace_label.upper()}
        </div>
        """, unsafe_allow_html=True)

        # ── Metric row ─────────────────────────────────────────────────────
        rc1, rc2, rc3, rc4, rc5, rc6 = st.columns(6)
        rc1.metric("Time in Range", f"{retro_summary.percent_time_in_range:.1f}%")
        rc2.metric("Avg CGM", f"{retro_summary.average_cgm_glucose_mgdl:.0f} mg/dL")
        rc3.metric("Peak CGM", f"{retro_summary.peak_cgm_glucose_mgdl:.0f} mg/dL")
        rc4.metric("Delivered U", f"{retro_summary.total_insulin_delivered_u:.2f}")
        rc5.metric("Blocked", retro_summary.blocked_decisions)
        rc6.metric("Suspended", retro_summary.time_suspended_steps)

        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

        # ── CGM trace + intervention markers ──────────────────────────────
        _rCGM = go.Figure()
        _rCGM.add_hrect(y0=70, y1=180, fillcolor="rgba(57,255,20,0.04)", line_width=0)
        _rCGM.add_hline(y=70, line=dict(color=RED, width=1, dash="dot"),
                        annotation=dict(text="HYPO 70", font=dict(color=RED, size=8), xanchor="left"))
        _rCGM.add_hline(y=180, line=dict(color=AMBER, width=1, dash="dot"),
                        annotation=dict(text="HYPER 180", font=dict(color=AMBER, size=8), xanchor="left"))
        _rCGM.add_hline(y=250, line=dict(color=RED, width=1.5, dash="dash"),
                        annotation=dict(text="SEVERE 250", font=dict(color=RED, size=8), xanchor="left"))
        _rCGM.add_trace(go.Scatter(
            x=retro_df["timestamp_min"], y=retro_df["cgm_glucose_mgdl"],
            mode="lines+markers", name="CGM Trace",
            line=dict(color=NEON, width=2.5),
            marker=dict(size=5, color=NEON),
            hovertemplate="%{y:.1f} mg/dL<extra>CGM</extra>",
        ))
        # Dosing decisions as vertical annotations via scatter
        _dose_df = retro_df[retro_df["pump_delivered_units"] > 0]
        if not _dose_df.empty:
            _rCGM.add_trace(go.Scatter(
                x=_dose_df["timestamp_min"],
                y=_dose_df["cgm_glucose_mgdl"],
                mode="markers", name="Controller Dose",
                marker=dict(
                    symbol="triangle-down", size=14,
                    color=CYAN, line=dict(width=1.5, color=CYAN),
                ),
                hovertemplate="t=%{x} min · dose at %{y:.1f} mg/dL<extra>Dose</extra>",
            ))
        _blocked_df = retro_df[retro_df["safety_status"] == "blocked"]
        if not _blocked_df.empty:
            _rCGM.add_trace(go.Scatter(
                x=_blocked_df["timestamp_min"],
                y=_blocked_df["cgm_glucose_mgdl"],
                mode="markers", name="Blocked",
                marker=dict(symbol="x", size=10, color=RED, line=dict(width=2, color=RED)),
                hovertemplate="t=%{x} min — BLOCKED at %{y:.1f} mg/dL<extra>Blocked</extra>",
            ))
        _rCGM_layout = _layout(f"CGM TRACE · CONTROLLER DECISIONS", height=400)
        _rCGM_layout["yaxis"]["title"] = "mg/dL"
        _rCGM_layout["xaxis"]["title"] = "minutes"
        _rCGM.update_layout(**_rCGM_layout)
        st.plotly_chart(_rCGM, width="stretch")

        # ── Insulin recommendation vs delivery ────────────────────────────
        _rc1, _rc2 = st.columns([3, 2])
        with _rc1:
            _rIns = go.Figure()
            _rIns.add_trace(go.Bar(
                x=retro_df["timestamp_min"], y=retro_df["pump_delivered_units"],
                name="Delivered", marker_color=NEON, opacity=0.9,
                hovertemplate="%{y:.3f} U<extra>Delivered</extra>",
            ))
            _rIns.add_trace(go.Scatter(
                x=retro_df["timestamp_min"], y=retro_df["recommended_units"],
                mode="lines", name="Recommended",
                line=dict(color=NEON_DIM, width=1.5, dash="dot"),
                hovertemplate="%{y:.3f} U<extra>Recommended</extra>",
            ))
            _rIns_layout = _layout("HYPOTHETICAL INSULIN DELIVERY", height=280)
            _rIns_layout["yaxis"]["title"] = "units"
            _rIns_layout["xaxis"]["title"] = "minutes"
            _rIns_layout["barmode"] = "overlay"
            _rIns.update_layout(**_rIns_layout)
            st.plotly_chart(_rIns, width="stretch")
        with _rc2:
            _rIOB = go.Figure()
            _rIOB.add_trace(go.Scatter(
                x=retro_df["timestamp_min"], y=retro_df["insulin_on_board_u"],
                mode="lines", name="IOB",
                line=dict(color=CYAN, width=2),
                fill="tozeroy", fillcolor="rgba(0,245,255,0.07)",
                hovertemplate="%{y:.3f} U<extra>IOB</extra>",
            ))
            _rIOB_layout = _layout("HYPOTHETICAL IOB", height=280)
            _rIOB_layout["yaxis"]["title"] = "IOB (U)"
            _rIOB_layout["xaxis"]["title"] = "minutes"
            _rIOB.update_layout(**_rIOB_layout)
            st.plotly_chart(_rIOB, width="stretch")

        # ── Report + export ────────────────────────────────────────────────
        _retro_report = generate_report(
            scenario_name=_trace_label,
            summary=retro_summary,
            duration_minutes=_duration_min,
            step_minutes=int(_step_min),
            safety_thresholds=safety_thresholds,
            pump_config=pump_config,
            correction_factor_mgdl_per_unit=retro_isf,
            min_excursion_delta_mgdl=min_excursion_delta,
            microbolus_fraction=microbolus_fraction,
        )
        _retro_report["retrospective"] = True
        _retro_report["trace_points"] = len(retro_readings)
        _retro_report["insulin_peak_minutes"] = float(retro_peak)

        st.markdown(f"""
        <div style="font-family:'Share Tech Mono',monospace; font-size:0.6rem; color:{MUTED};
                    letter-spacing:4px; text-transform:uppercase; margin:1rem 0 0.5rem 0;">
          ── RETROSPECTIVE REPORT EXPORT
        </div>
        """, unsafe_allow_html=True)
        _rpass = _retro_report["verdicts"]["overall_pass"]
        _rcolor = NEON if _rpass else RED
        st.markdown(f"""
        <div style="font-family:'Share Tech Mono',monospace; font-size:0.7rem;
                    color:{_rcolor}; margin-bottom:0.5rem;">
          {"✓ PASS" if _rpass else "✗ FAIL"} &nbsp;·&nbsp;
          TIR {"✓" if _retro_report["verdicts"]["tir_pass"] else "✗"} &nbsp;·&nbsp;
          Peak {"✓" if _retro_report["verdicts"]["peak_pass"] else "✗"} &nbsp;·&nbsp;
          Hypo {"✓" if _retro_report["verdicts"]["hypo_pass"] else "✗"} &nbsp;·&nbsp;
          SD {"✓" if _retro_report["verdicts"]["variability_pass"] else "✗"}
        </div>
        """, unsafe_allow_html=True)
        _rex1, _rex2 = st.columns(2)
        with _rex1:
            st.download_button(
                label="↓  EXPORT RETROSPECTIVE REPORT (JSON)",
                data=json.dumps(_retro_report, indent=2),
                file_name=f"swarm_retro_{_trace_label.lower()[:30].replace(' ', '_')}.json",
                mime="application/json",
            )
        with _rex2:
            st.download_button(
                label="↓  EXPORT TRACE AS CSV",
                data=readings_to_csv(retro_readings),
                file_name=f"cgm_trace_{_trace_label.lower()[:30].replace(' ', '_')}.csv",
                mime="text/csv",
            )

        # ── Decision Timeline ──────────────────────────────────────────────
        retro_exps = annotate_run(
            retro_records,
            seed_glucose_mgdl=retro_readings[0].glucose_mgdl,
            target_glucose_mgdl=retro_cfg.target_glucose_mgdl,
            correction_factor_mgdl_per_unit=retro_cfg.correction_factor_mgdl_per_unit,
            min_excursion_delta_mgdl=retro_cfg.min_excursion_delta_mgdl,
            microbolus_fraction=retro_cfg.microbolus_fraction,
            safety_thresholds=safety_thresholds,
            step_minutes=int(_step_min),
        )
        decision_timeline_panel(retro_exps, key_suffix="retro")

        st.stop()

    elif dashboard_mode == "Profile Sweep":
        _sweep_common = dict(
            safety_thresholds=safety_thresholds,
            pump_config=pump_config,
            duration_minutes=duration_minutes,
            step_minutes=step_minutes,
            seed=42,
            min_excursion_delta_mgdl=min_excursion_delta,
            microbolus_fraction=microbolus_fraction,
        )
        with st.spinner(""):
            sweep_results = run_profile_sweep(
                base_scenario=build_scenario(sweep_scenario_name),
                scenario_name=sweep_scenario_name,
                **_sweep_common,
            )

        # ── Profile Sweep results ─────────────────────────────────────────
        _PROFILE_COLORS = ["#39ff14", "#ff4d6d", "#ffbe0b", "#00f5ff"]

        st.markdown(f"""
        <div style="font-family:'Share Tech Mono',monospace; font-size:0.6rem; color:{MUTED};
                    letter-spacing:4px; text-transform:uppercase; margin-bottom:0.75rem;">
          ── PROFILE SWEEP · {sweep_scenario_name.upper()}
        </div>
        """, unsafe_allow_html=True)

        # Overall population pass/fail banner
        _all_pass = all(r.report["verdicts"]["overall_pass"] for r in sweep_results)
        _pop_color = NEON if _all_pass else RED
        _pop_text = "◉ POPULATION PASS — all profiles meet ADA/EASD targets" \
            if _all_pass else "⚠ POPULATION FAIL — one or more profiles outside targets"
        st.markdown(f"""
        <div style="font-family:'Share Tech Mono',monospace; font-size:0.75rem;
                    color:{_pop_color}; border:1px solid {_pop_color};
                    padding:0.5rem 1rem; margin-bottom:1rem; letter-spacing:2px;">
          {_pop_text}
        </div>
        """, unsafe_allow_html=True)

        # Per-profile metric cards
        _pcols = st.columns(4)
        for _i, _sr in enumerate(sweep_results):
            _pc = _PROFILE_COLORS[_i]
            _pv = _sr.report["verdicts"]
            _ppass = "✓ PASS" if _pv["overall_pass"] else "✗ FAIL"
            with _pcols[_i]:
                st.markdown(f"""
                <div style="font-family:'Share Tech Mono',monospace; font-size:0.65rem;
                            color:{_pc}; border-left:3px solid {_pc};
                            padding-left:0.6rem; margin-bottom:0.4rem; letter-spacing:1px;">
                  {_sr.profile.name.upper()}<br/>
                  <span style="font-size:0.55rem; color:{MUTED};">{_sr.profile.description}</span>
                </div>
                """, unsafe_allow_html=True)
                st.metric("TIR", f"{_sr.summary.percent_time_in_range:.1f}%")
                st.metric("Peak CGM", f"{_sr.summary.peak_cgm_glucose_mgdl:.0f} mg/dL")
                st.metric("Avg CGM", f"{_sr.summary.average_cgm_glucose_mgdl:.0f} mg/dL")
                st.metric("Glucose SD", f"{_sr.summary.glucose_variability_sd_mgdl:.1f}")
                _tir_v = "✓" if _pv["tir_pass"] else "✗"
                _pk_v = "✓" if _pv["peak_pass"] else "✗"
                _hy_v = "✓" if _pv["hypo_pass"] else "✗"
                _sd_v = "✓" if _pv["variability_pass"] else "✗"
                st.markdown(f"""
                <div style="font-family:'Share Tech Mono',monospace; font-size:0.65rem;
                            color:{_pc if _pv["overall_pass"] else RED}; margin-top:0.3rem;">
                  {_ppass} &nbsp;·&nbsp; TIR {_tir_v} &nbsp;·&nbsp; Peak {_pk_v}
                  &nbsp;·&nbsp; Hypo {_hy_v} &nbsp;·&nbsp; SD {_sd_v}
                </div>
                """, unsafe_allow_html=True)

        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

        # 4-trace CGM chart
        _cgm_fig = go.Figure()
        _cgm_fig.add_hrect(y0=70, y1=180, fillcolor="rgba(57,255,20,0.04)", line_width=0)
        _cgm_fig.add_hline(y=70, line=dict(color=RED, width=1, dash="dot"),
                           annotation=dict(text="HYPO 70", font=dict(color=RED, size=8), xanchor="left"))
        _cgm_fig.add_hline(y=180, line=dict(color=AMBER, width=1, dash="dot"),
                           annotation=dict(text="HYPER 180", font=dict(color=AMBER, size=8), xanchor="left"))
        _cgm_fig.add_hline(y=250, line=dict(color=RED, width=1.5, dash="dash"),
                           annotation=dict(text="SEVERE 250", font=dict(color=RED, size=8), xanchor="left"))
        for _i, _sr in enumerate(sweep_results):
            _df_p = pd.DataFrame([r.__dict__ for r in _sr.records])
            _cgm_fig.add_trace(go.Scatter(
                x=_df_p["timestamp_min"], y=_df_p["cgm_glucose_mgdl"],
                mode="lines", name=_sr.profile.name,
                line=dict(color=_PROFILE_COLORS[_i], width=2),
                hovertemplate="%{y:.1f} mg/dL<extra>" + _sr.profile.name + "</extra>",
            ))
        _cgm_layout = _layout(f"CGM TRAJECTORY · {sweep_scenario_name.upper()}", height=380)
        _cgm_layout["yaxis"]["title"] = "mg/dL"
        _cgm_layout["xaxis"]["title"] = "minutes"
        _cgm_fig.update_layout(**_cgm_layout)
        st.plotly_chart(_cgm_fig, width="stretch")

        # Insulin delivery chart (4 bars)
        _ins_fig = go.Figure()
        for _i, _sr in enumerate(sweep_results):
            _df_p = pd.DataFrame([r.__dict__ for r in _sr.records])
            _ins_fig.add_trace(go.Bar(
                x=_df_p["timestamp_min"], y=_df_p["pump_delivered_units"],
                name=_sr.profile.name,
                marker_color=_PROFILE_COLORS[_i], opacity=0.75,
                hovertemplate="%{y:.3f} U<extra>" + _sr.profile.name + "</extra>",
            ))
        _ins_layout = _layout("INSULIN DELIVERY PER PROFILE", height=280)
        _ins_layout["yaxis"]["title"] = "units"
        _ins_layout["xaxis"]["title"] = "minutes"
        _ins_layout["barmode"] = "group"
        _ins_fig.update_layout(**_ins_layout)
        st.plotly_chart(_ins_fig, width="stretch")

        # Summary table
        with st.expander("FULL METRICS TABLE", expanded=False):
            _tbl_data = {
                "Metric": [
                    "Time in Range %", "Avg CGM (mg/dL)", "Peak CGM (mg/dL)",
                    "Glucose SD (mg/dL)", "Time Below 70 (steps)", "Time Above 250 (steps)",
                    "Delivered Insulin (U)", "Blocked Decisions", "Suspended Steps",
                ],
            }
            for _sr in sweep_results:
                _s = _sr.summary
                _tbl_data[_sr.profile.name] = [
                    _s.percent_time_in_range,
                    _s.average_cgm_glucose_mgdl,
                    _s.peak_cgm_glucose_mgdl,
                    _s.glucose_variability_sd_mgdl,
                    _s.time_below_range_steps,
                    _s.time_above_250_steps,
                    _s.total_insulin_delivered_u,
                    _s.blocked_decisions,
                    _s.time_suspended_steps,
                ]
            st.dataframe(pd.DataFrame(_tbl_data), hide_index=True, width="stretch")

        # Combined export
        st.markdown(f"""
        <div style="font-family:'Share Tech Mono',monospace; font-size:0.6rem; color:{MUTED};
                    letter-spacing:4px; text-transform:uppercase; margin:1rem 0 0.5rem 0;">
          ── SWEEP REPORT EXPORT
        </div>
        """, unsafe_allow_html=True)
        _sweep_export = build_sweep_export(sweep_scenario_name, sweep_results)
        st.download_button(
            label="↓  EXPORT COMBINED SWEEP REPORT (JSON)",
            data=json.dumps(_sweep_export, indent=2),
            file_name=f"swarm_sweep_{sweep_scenario_name.lower().replace(' ', '_')}.json",
            mime="application/json",
        )
        st.stop()  # Comparison code below must not run in sweep mode

    else:  # Comparison mode
        with st.spinner(""):
            records_a, summary_a = run_evaluation(
                simulation_inputs=build_scenario(scenario_a_name),
                safety_thresholds=safety_thresholds,
                pump_config=pump_config,
                duration_minutes=duration_minutes,
                step_minutes=step_minutes,
                seed=42,
                min_excursion_delta_mgdl=min_excursion_delta,
                microbolus_fraction=microbolus_fraction,
            )
            records_b, summary_b = run_evaluation(
                simulation_inputs=build_scenario(scenario_b_name),
                safety_thresholds=safety_thresholds,
                pump_config=pump_config,
                duration_minutes=duration_minutes,
                step_minutes=step_minutes,
                seed=42,
                min_excursion_delta_mgdl=min_excursion_delta,
                microbolus_fraction=microbolus_fraction,
            )

        df_a = pd.DataFrame([r.__dict__ for r in records_a])
        df_b = pd.DataFrame([r.__dict__ for r in records_b])

    # ── Scenario metric panels ────────────────────────────────────────────
    st.markdown(f"""
    <div style="font-family:'Share Tech Mono',monospace; font-size:0.6rem; color:{MUTED};
                letter-spacing:4px; text-transform:uppercase; margin-bottom:0.75rem;">
      ── SCENARIO COMPARISON
    </div>
    """, unsafe_allow_html=True)

    col_a, col_b = st.columns(2)

    def tir_color(pct: float) -> str:
        if pct >= 70:
            return NEON
        if pct >= 50:
            return AMBER
        return RED

    with col_a:
        st.markdown(f"""
        <div style="font-family:'Share Tech Mono',monospace; font-size:0.7rem;
                    color:{NEON}; letter-spacing:3px; text-transform:uppercase;
                    margin-bottom:0.5rem; border-left:3px solid {NEON}; padding-left:0.75rem;">
          SCENARIO A · {scenario_a_name.upper()}
        </div>
        """, unsafe_allow_html=True)
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Time in Range", f"{summary_a.percent_time_in_range:.1f}%")
        r2.metric("Avg CGM", f"{summary_a.average_cgm_glucose_mgdl:.0f}")
        r3.metric("Peak CGM", f"{summary_a.peak_cgm_glucose_mgdl:.0f}")
        r4.metric("Above 250", f"{summary_a.time_above_250_steps} steps")
        r5, r6, r7, r8, r9 = st.columns(5)
        r5.metric("Recommended U", f"{summary_a.total_recommended_insulin_u:.2f}")
        r6.metric("Delivered U", f"{summary_a.total_insulin_delivered_u:.2f}")
        r7.metric("Blocked", summary_a.blocked_decisions)
        r8.metric("Clipped", summary_a.clipped_decisions)
        r9.metric("Suspended", summary_a.time_suspended_steps)

    with col_b:
        st.markdown(f"""
        <div style="font-family:'Share Tech Mono',monospace; font-size:0.7rem;
                    color:{CYAN}; letter-spacing:3px; text-transform:uppercase;
                    margin-bottom:0.5rem; border-left:3px solid {CYAN}; padding-left:0.75rem;">
          SCENARIO B · {scenario_b_name.upper()}
        </div>
        """, unsafe_allow_html=True)
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Time in Range", f"{summary_b.percent_time_in_range:.1f}%")
        r2.metric("Avg CGM", f"{summary_b.average_cgm_glucose_mgdl:.0f}")
        r3.metric("Peak CGM", f"{summary_b.peak_cgm_glucose_mgdl:.0f}")
        r4.metric("Above 250", f"{summary_b.time_above_250_steps} steps")
        r5, r6, r7, r8, r9 = st.columns(5)
        r5.metric("Recommended U", f"{summary_b.total_recommended_insulin_u:.2f}")
        r6.metric("Delivered U", f"{summary_b.total_insulin_delivered_u:.2f}")
        r7.metric("Blocked", summary_b.blocked_decisions)
        r8.metric("Clipped", summary_b.clipped_decisions)
        r9.metric("Suspended", summary_b.time_suspended_steps)

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    # ── Charts ────────────────────────────────────────────────────────────
    st.plotly_chart(
        cgm_chart(df_a, df_b, scenario_a_name, scenario_b_name),
        width="stretch",
    )

    c1, c2 = st.columns([3, 2])
    with c1:
        st.plotly_chart(
            insulin_chart(df_a, df_b, scenario_a_name, scenario_b_name),
            width="stretch",
        )
    with c2:
        st.plotly_chart(
            iob_chart(df_a, df_b, scenario_a_name, scenario_b_name),
            width="stretch",
        )

    st.plotly_chart(
        safety_chart(df_a, df_b, scenario_a_name, scenario_b_name),
        width="stretch",
    )

    # ── Metrics table ─────────────────────────────────────────────────────
    with st.expander("CLINICAL METRICS TABLE", expanded=False):
        compare_df = pd.DataFrame({
            "Metric": [
                "Time in Range %",
                "Average CGM (mg/dL)",
                "Peak CGM (mg/dL)",
                "Time Above 250 (steps)",
                "Glucose Variability SD",
                "Recommended Insulin (U)",
                "Delivered Insulin (U)",
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
        })
        st.dataframe(compare_df, width="stretch", hide_index=True)

    # ── AI Verdict ────────────────────────────────────────────────────────
    verdict_lines: list[str] = []

    if summary_a.percent_time_in_range > summary_b.percent_time_in_range:
        verdict_lines.append(
            f"[TIR]   A outperforms B on glycemic control "
            f"({summary_a.percent_time_in_range:.1f}% vs {summary_b.percent_time_in_range:.1f}% in range)."
        )
    elif summary_b.percent_time_in_range > summary_a.percent_time_in_range:
        verdict_lines.append(
            f"[TIR]   B outperforms A on glycemic control "
            f"({summary_b.percent_time_in_range:.1f}% vs {summary_a.percent_time_in_range:.1f}% in range)."
        )
    else:
        verdict_lines.append("[TIR]   Both scenarios achieve identical time-in-range.")

    if summary_b.peak_cgm_glucose_mgdl > summary_a.peak_cgm_glucose_mgdl + 10:
        verdict_lines.append(
            f"[PEAK]  B exhibits higher excursion risk "
            f"(peak {summary_b.peak_cgm_glucose_mgdl:.0f} vs {summary_a.peak_cgm_glucose_mgdl:.0f} mg/dL)."
        )
    elif summary_a.peak_cgm_glucose_mgdl > summary_b.peak_cgm_glucose_mgdl + 10:
        verdict_lines.append(
            f"[PEAK]  A exhibits higher excursion risk "
            f"(peak {summary_a.peak_cgm_glucose_mgdl:.0f} vs {summary_b.peak_cgm_glucose_mgdl:.0f} mg/dL)."
        )

    ints_a = summary_a.blocked_decisions + summary_a.clipped_decisions
    ints_b = summary_b.blocked_decisions + summary_b.clipped_decisions
    if ints_b > ints_a:
        verdict_lines.append(
            f"[SAFETY] B triggers more safety interventions ({ints_b} vs {ints_a}), "
            f"indicating greater constraint pressure on dosing."
        )
    elif ints_a > ints_b:
        verdict_lines.append(
            f"[SAFETY] A triggers more safety interventions ({ints_a} vs {ints_b})."
        )

    if summary_b.total_insulin_delivered_u > summary_a.total_insulin_delivered_u * 1.15:
        verdict_lines.append(
            f"[INSULIN] B requires {summary_b.total_insulin_delivered_u - summary_a.total_insulin_delivered_u:.2f} U "
            f"more insulin than A."
        )

    if summary_a.glucose_variability_sd_mgdl < summary_b.glucose_variability_sd_mgdl:
        verdict_lines.append(
            f"[VAR]   A shows lower glycemic variability "
            f"(SD {summary_a.glucose_variability_sd_mgdl:.1f} vs {summary_b.glucose_variability_sd_mgdl:.1f} mg/dL)."
        )

    if not verdict_lines:
        verdict_lines.append("[INFO]  Both scenarios behave similarly under current constraints.")

    # Pre-build reports so download buttons are always available after a run
    _report_a = generate_report(
        scenario_name=scenario_a_name,
        summary=summary_a,
        duration_minutes=duration_minutes,
        step_minutes=step_minutes,
        safety_thresholds=safety_thresholds,
        pump_config=pump_config,
        min_excursion_delta_mgdl=min_excursion_delta,
        microbolus_fraction=microbolus_fraction,
    )
    _report_b = generate_report(
        scenario_name=scenario_b_name,
        summary=summary_b,
        duration_minutes=duration_minutes,
        step_minutes=step_minutes,
        safety_thresholds=safety_thresholds,
        pump_config=pump_config,
        min_excursion_delta_mgdl=min_excursion_delta,
        microbolus_fraction=microbolus_fraction,
    )

    verdict_text = "\n".join(f"  {line}" for line in verdict_lines)

    # ── Export ────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div style="font-family:'Share Tech Mono',monospace; font-size:0.6rem; color:{MUTED};
                letter-spacing:4px; text-transform:uppercase; margin:1.5rem 0 0.5rem 0;">
      ── VALIDATION REPORT EXPORT
    </div>
    """, unsafe_allow_html=True)
    _exp_a, _exp_b = st.columns(2)
    with _exp_a:
        _pass_a = "✓ PASS" if _report_a["verdicts"]["overall_pass"] else "✗ FAIL"
        _color_a = NEON if _report_a["verdicts"]["overall_pass"] else RED
        st.markdown(f"""
        <div style="font-family:'Share Tech Mono',monospace; font-size:0.7rem;
                    color:{_color_a}; margin-bottom:0.4rem;">
          Scenario A · {_pass_a}
          &nbsp;·&nbsp; TIR {"✓" if _report_a["verdicts"]["tir_pass"] else "✗"}
          &nbsp;·&nbsp; Peak {"✓" if _report_a["verdicts"]["peak_pass"] else "✗"}
          &nbsp;·&nbsp; Hypo {"✓" if _report_a["verdicts"]["hypo_pass"] else "✗"}
          &nbsp;·&nbsp; SD {"✓" if _report_a["verdicts"]["variability_pass"] else "✗"}
        </div>
        """, unsafe_allow_html=True)
        st.download_button(
            label="↓  EXPORT SCENARIO A REPORT",
            data=json.dumps(_report_a, indent=2),
            file_name=f"swarm_report_A_{scenario_a_name.lower().replace(' ', '_')}.json",
            mime="application/json",
        )
    with _exp_b:
        _pass_b = "✓ PASS" if _report_b["verdicts"]["overall_pass"] else "✗ FAIL"
        _color_b = NEON if _report_b["verdicts"]["overall_pass"] else RED
        st.markdown(f"""
        <div style="font-family:'Share Tech Mono',monospace; font-size:0.7rem;
                    color:{_color_b}; margin-bottom:0.4rem;">
          Scenario B · {_pass_b}
          &nbsp;·&nbsp; TIR {"✓" if _report_b["verdicts"]["tir_pass"] else "✗"}
          &nbsp;·&nbsp; Peak {"✓" if _report_b["verdicts"]["peak_pass"] else "✗"}
          &nbsp;·&nbsp; Hypo {"✓" if _report_b["verdicts"]["hypo_pass"] else "✗"}
          &nbsp;·&nbsp; SD {"✓" if _report_b["verdicts"]["variability_pass"] else "✗"}
        </div>
        """, unsafe_allow_html=True)
        st.download_button(
            label="↓  EXPORT SCENARIO B REPORT",
            data=json.dumps(_report_b, indent=2),
            file_name=f"swarm_report_B_{scenario_b_name.lower().replace(' ', '_')}.json",
            mime="application/json",
        )

    # ── Decision Timelines (Scenario A then B) ────────────────────────────
    _cfg_a = build_scenario(scenario_a_name)
    _cfg_b = build_scenario(scenario_b_name)
    _exps_a = annotate_run(
        records_a,
        seed_glucose_mgdl=140.0,
        target_glucose_mgdl=110.0,
        correction_factor_mgdl_per_unit=_cfg_a.insulin_sensitivity_mgdl_per_unit,
        min_excursion_delta_mgdl=min_excursion_delta,
        microbolus_fraction=microbolus_fraction,
        safety_thresholds=safety_thresholds,
        step_minutes=step_minutes,
    )
    _exps_b = annotate_run(
        records_b,
        seed_glucose_mgdl=140.0,
        target_glucose_mgdl=110.0,
        correction_factor_mgdl_per_unit=_cfg_b.insulin_sensitivity_mgdl_per_unit,
        min_excursion_delta_mgdl=min_excursion_delta,
        microbolus_fraction=microbolus_fraction,
        safety_thresholds=safety_thresholds,
        step_minutes=step_minutes,
    )
    st.markdown(f"""
    <div style="font-family:'Share Tech Mono',monospace; font-size:0.6rem; color:{MUTED};
                letter-spacing:4px; text-transform:uppercase; margin:1.5rem 0 0.25rem 0;">
      ── SCENARIO A · DECISION TIMELINE
    </div>
    """, unsafe_allow_html=True)
    decision_timeline_panel(_exps_a, key_suffix="comp_a")
    st.markdown(f"""
    <div style="font-family:'Share Tech Mono',monospace; font-size:0.6rem; color:{MUTED};
                letter-spacing:4px; text-transform:uppercase; margin:0.75rem 0 0.25rem 0;">
      ── SCENARIO B · DECISION TIMELINE
    </div>
    """, unsafe_allow_html=True)
    decision_timeline_panel(_exps_b, key_suffix="comp_b")

    st.markdown(f"""
    <div style="margin-top:1rem;">
      <div style="font-family:'Share Tech Mono',monospace; font-size:0.6rem; color:{MUTED};
                  letter-spacing:4px; text-transform:uppercase; margin-bottom:0.5rem;">
        ── AI COMPARATIVE VERDICT
      </div>
      <div style="background:{BG2}; border:1px solid {NEON_DIM}; border-left:3px solid {NEON};
                  border-radius:3px; padding:1.25rem 1.5rem; font-family:'Share Tech Mono',monospace;
                  font-size:0.8rem; color:{WHITE}; line-height:2;
                  white-space:pre; overflow-x:auto;">
<span style="color:{NEON_DIM}">$ swarm-bolus --verdict</span>

{verdict_text}

<span style="color:{NEON_DIM}; animation:blink 1s step-end infinite;">▌</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

else:
    # ── Landing state ─────────────────────────────────────────────────────
    st.markdown(f"""
    <div style="display:flex; align-items:center; justify-content:center;
                min-height:340px; border:1px solid {NEON_DIM}; border-radius:3px;
                background:{BG2}; margin-top:1rem;">
      <div style="text-align:center;">
        <div style="font-family:'Orbitron',monospace; font-size:1.2rem; color:{NEON_DIM};
                    letter-spacing:6px; text-transform:uppercase; margin-bottom:1rem;">
          AWAITING INPUT
        </div>
        <div style="font-family:'Share Tech Mono',monospace; font-size:0.75rem; color:{MUTED};
                    letter-spacing:2px; text-transform:uppercase; line-height:2;">
          Select scenarios in the sidebar<br/>
          Configure safety &amp; pump parameters<br/>
          Press <span style="color:{NEON}">▶ RUN COMPARISON</span> to simulate
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)
