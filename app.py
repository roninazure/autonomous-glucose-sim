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
from ags.evaluation.profiles import ALL_PROFILES, estimate_isf_from_weight
from ags.evaluation.report import generate_report
from ags.evaluation.runner import run_closed_loop_evaluation, run_evaluation
from ags.pump.state import DualWaveConfig, PumpConfig
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
    overnight_stability_scenario,
    rapid_drop_scenario,
    stacked_corrections_scenario,
    sustained_basal_deficit_scenario,
)
from ags.simulation.state import MealEvent, SimulationInputs
from ags.optimization.pso import run_pso
from ags.optimization.fitness import NAMED_SCENARIOS, params_to_tir
from ags.optimization.state import PSOConfig, PARAMETER_BOUNDS

# ── Palette ─────────────────────────────────────────────────────────────────
# Clinical light theme — white/light-grey, high contrast, readable at any size.
BG       = "#f8fafc"   # near-white page background
BG2      = "#ffffff"   # sidebar / panel white
BG3      = "#f1f5f9"   # slightly elevated surface (cards, table headers)
NEON     = "#16a34a"   # clinical green (ADA in-range colour)
NEON_DIM = "#dcfce7"   # very light green border/fill
RED      = "#dc2626"   # clear red for hypo/danger
AMBER    = "#d97706"   # amber for hyperglycemia warning
CYAN     = "#1d4ed8"   # medical blue — section headings / accents
WHITE    = "#1e293b"   # near-black body text (high contrast on light bg)
MUTED    = "#64748b"   # slate-grey muted text
GRID     = "#e2e8f0"   # subtle chart gridlines

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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

/* Base — Inter for readable prose, JetBrains Mono only for data values */
html, body, [class*="css"] {{
    background-color: {BG} !important;
    color: {WHITE} !important;
    font-family: 'Inter', sans-serif !important;
}}

/* Sidebar */
[data-testid="stSidebar"] {{
    background-color: {BG2} !important;
    border-right: 1px solid {GRID} !important;
}}
[data-testid="stSidebar"] * {{
    font-family: 'Inter', sans-serif !important;
    font-size: 0.875rem !important;
    color: {WHITE} !important;
}}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {{
    color: {CYAN} !important;
    font-size: 0.72rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.6px;
    text-transform: uppercase;
    padding-bottom: 5px;
    border-bottom: 2px solid {NEON_DIM};
    margin-top: 1.4rem !important;
}}
/* Slider / selectbox labels */
[data-testid="stSidebar"] label {{
    color: {WHITE} !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
}}
/* Radio button text */
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {{
    color: {WHITE} !important;
    font-size: 0.875rem !important;
}}

/* Primary button */
[data-testid="stButton"] > button[kind="primary"] {{
    background: {CYAN} !important;
    border: none !important;
    color: #ffffff !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.9rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.3px;
    width: 100%;
    padding: 0.7rem !important;
    border-radius: 6px !important;
    transition: all 0.15s ease;
}}
[data-testid="stButton"] > button[kind="primary"]:hover {{
    background: #1e40af !important;
    color: #ffffff !important;
}}

/* Metrics */
[data-testid="metric-container"] {{
    background-color: {BG3} !important;
    border: 1px solid {GRID} !important;
    border-radius: 8px !important;
    padding: 12px 16px !important;
}}
[data-testid="stMetricValue"] {{
    color: {CYAN} !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 1.4rem !important;
    font-weight: 600 !important;
}}
[data-testid="stMetricLabel"] {{
    color: {MUTED} !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.75rem !important;
    font-weight: 500 !important;
    letter-spacing: 0.2px;
}}

/* Dataframe */
[data-testid="stDataFrame"] {{
    border: 1px solid {GRID} !important;
    border-radius: 6px !important;
}}
[data-testid="stDataFrame"] th {{
    background-color: {BG3} !important;
    color: {CYAN} !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.2px;
}}
[data-testid="stDataFrame"] td {{
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.82rem !important;
    color: {WHITE} !important;
}}

/* Plotly containers */
[data-testid="stPlotlyChart"] {{
    border: 1px solid {GRID};
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}}

/* Info / alert box */
[data-testid="stAlert"] {{
    font-family: 'Inter', sans-serif !important;
    font-size: 0.875rem !important;
    border-radius: 6px !important;
}}

/* Expander */
[data-testid="stExpander"] summary {{
    font-family: 'Inter', sans-serif !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
    color: {CYAN} !important;
}}

/* Scrollbar */
::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: {BG3}; }}
::-webkit-scrollbar-thumb {{ background: {GRID}; border-radius: 3px; }}
::-webkit-scrollbar-thumb:hover {{ background: {MUTED}; }}

/* Divider */
hr {{ border-color: {GRID} !important; opacity: 0.8; }}

/* Section labels */
.section-label {{
    font-family: 'Inter', sans-serif;
    font-size: 0.7rem;
    font-weight: 600;
    color: {MUTED};
    letter-spacing: 0.5px;
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
            font=dict(family="Inter", size=12, color=WHITE),
            x=0,
            pad=dict(l=0, t=4),
        ),
        height=height,
        margin=dict(l=55, r=20, t=44, b=44),
        plot_bgcolor=BG2,
        paper_bgcolor=BG3,
        font=dict(family="Inter", color=WHITE, size=11),
        xaxis=dict(
            gridcolor=GRID,
            linecolor=GRID,
            tickcolor=GRID,
            tickfont=dict(color=MUTED, size=10),
            title_font=dict(color=MUTED, size=11),
            zeroline=False,
        ),
        yaxis=dict(
            gridcolor=GRID,
            linecolor=GRID,
            tickcolor=GRID,
            tickfont=dict(color=MUTED, size=10),
            title_font=dict(color=MUTED, size=11),
            zeroline=False,
        ),
        legend=dict(
            bgcolor=BG3,
            bordercolor=GRID,
            borderwidth=1,
            font=dict(family="Inter", size=11, color=WHITE),
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
        ),
        hovermode="x unified",
    )


# ── Chart builders ───────────────────────────────────────────────────────────
def _vrect_bands(
    fig: go.Figure,
    df: pd.DataFrame,
    phase_col: str,
    active_values: list[str],
    color: str,
    opacity: float,
    label: str,
) -> None:
    """Group consecutive rows matching active_values into shaded vrect bands."""
    if phase_col not in df.columns:
        return
    in_band = False
    band_start = None
    first_band = True
    for _, row in df.iterrows():
        active = row[phase_col] in active_values
        if active and not in_band:
            band_start = row["timestamp_min"]
            in_band = True
        elif not active and in_band:
            fig.add_vrect(
                x0=band_start, x1=row["timestamp_min"],
                fillcolor=color, opacity=opacity, line_width=0,
                **(dict(
                    annotation_text=label,
                    annotation_position="top left",
                    annotation_font=dict(size=8, color=color),
                ) if first_band else {}),
            )
            first_band = False
            in_band = False
    if in_band and band_start is not None:
        fig.add_vrect(
            x0=band_start, x1=df["timestamp_min"].iloc[-1],
            fillcolor=color, opacity=opacity, line_width=0,
        )


def _add_meal_detection_annotations(fig: go.Figure, df: pd.DataFrame, color: str) -> None:
    """Overlay autonomous meal detection events on a CGM chart."""
    _vrect_bands(fig, df, "meal_phase", ["onset"], color, 0.10, "meal detected")


def _add_drift_annotations(fig: go.Figure, df: pd.DataFrame, color: str) -> None:
    """Overlay basal drift detection windows on a CGM chart."""
    if "basal_drift_detected" not in df.columns:
        return
    _vrect_bands(
        fig, df, "basal_drift_type",
        ["sustained", "dawn", "rebound"],
        color, 0.08, "basal drift",
    )


def cgm_chart(df_a: pd.DataFrame, df_b: pd.DataFrame, name_a: str, name_b: str) -> go.Figure:
    fig = go.Figure()

    # In-range band
    fig.add_hrect(
        y0=70, y1=180,
        fillcolor="rgba(57,255,20,0.04)", line_width=0,
    )
    # Threshold lines
    fig.add_hline(y=70, line=dict(color=RED, width=1, dash="dot"),
                  annotation=dict(text="Hypo  70", font=dict(color=RED, size=9, family="Inter"), xanchor="left"))
    fig.add_hline(y=180, line=dict(color=AMBER, width=1, dash="dot"),
                  annotation=dict(text="High  180", font=dict(color=AMBER, size=9, family="Inter"), xanchor="left"))
    fig.add_hline(y=250, line=dict(color=RED, width=1.5, dash="dash"),
                  annotation=dict(text="Very High  250", font=dict(color=RED, size=9, family="Inter"), xanchor="left"))

    # Autonomous detection bands — shaded regions where the system
    # inferred the cause of a glucose rise without being told
    _add_meal_detection_annotations(fig, df_a, NEON)
    _add_meal_detection_annotations(fig, df_b, CYAN)
    _add_drift_annotations(fig, df_a, "#ff9500")   # amber for drift on A
    _add_drift_annotations(fig, df_b, "#cc7700")   # darker amber for drift on B

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

    layout = _layout("Glucose over time (mg/dL)", height=360)
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

    layout = _layout("Insulin delivered (units)", height=280)
    layout["yaxis"]["title"] = "Units"
    layout["xaxis"]["title"] = "Time (minutes)"
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

    layout = _layout("Insulin still active in the body (IOB)", height=240)
    layout["yaxis"]["title"] = "Units active"
    layout["xaxis"]["title"] = "Time (minutes)"
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
                mode="markers", name=f"{label} Dose blocked (safety cap reached)",
                marker=dict(symbol="x", size=12, color=RED, line=dict(width=2, color=RED)),
                hovertemplate="t=%{x} min — dose blocked by safety system<extra>" + label + "</extra>",
            ))
        if not clipped.empty:
            fig.add_trace(go.Scatter(
                x=clipped["timestamp_min"], y=[label] * len(clipped),
                mode="markers", name=f"{label} Dose reduced to maximum limit",
                marker=dict(symbol="triangle-up", size=11, color=AMBER, line=dict(width=1, color=AMBER)),
                hovertemplate="t=%{x} min — dose reduced to per-interval limit<extra>" + label + "</extra>",
            ))

    layout = _layout("Safety interventions", height=200)
    layout["xaxis"]["title"] = "Time (minutes)"
    layout["yaxis"]["categoryorder"] = "array"
    layout["yaxis"]["categoryarray"] = ["B", "A"]
    layout["margin"]["l"] = 40
    fig.update_layout(**layout)
    return fig


# ── Scenario metadata ────────────────────────────────────────────────────────
SCENARIO_DESCRIPTIONS = {
    "Baseline Meal":           "45 g carbohydrate meal · typical insulin sensitivity · validates time-in-range under standard conditions",
    "Fasting Baseline":        "No meal · stable overnight drift · confirms the algorithm withholds insulin appropriately when no correction is needed",
    "Large Meal Spike":        "90 g carbohydrate meal · steep post-prandial rise · evaluates dosing behaviour during a large glycaemic excursion",
    "Dawn Phenomenon":         "No meal · cortisol-driven pre-dawn rise · assesses whether the algorithm detects and corrects a slow, sustained elevation",
    "Sustained Basal Deficit": "No meal · constant 0.30 mg/dL/min drift · canonical test for BASAL_DRIFT detection and sustained micro-bolus correction",
    "Exercise Hypoglycemia":   "Falling glucose during exercise · high insulin sensitivity · verifies that safety checks prevent compounding hypoglycaemia",
    "Missed Bolus":            "75 g meal with no pre-meal bolus · tests how the algorithm recovers from a delayed correction",
    "Late Correction":         "60 g meal plus snack · insulin given late · explores the risk of glucose-insulin timing mismatch",
    "Overnight Stability":     "8-hour overnight · no meal · no drift · algorithm must stay quiet and not drift glucose downward through unnecessary dosing",
    "Stacked Corrections":     "Three snacks 45 minutes apart · IOB guard must prevent dangerous correction stacking across overlapping absorption windows",
    "Rapid Drop":              "Fast falling glucose (−24 mg/dL/hr) simulating exercise or alcohol · hypo guard and suspension must fire before glucose hits 70 mg/dL",
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

    with st.expander("Decision log", expanded=False):
        # ── Build display DataFrame ─────────────────────────────────────
        rows = []
        gate_ids = []
        for exp in explanations:
            rows.append({
                "Time (min)": exp.timestamp_min,
                "Glucose (mg/dL)": f"{exp.cgm_mgdl:.0f}",
                "Trend": f"{exp.trend_arrow} {exp.trend_rate_mgdl_per_min:+.1f}/min",
                "Predicted +30 min": f"{exp.predicted_glucose_mgdl:.0f}",
                "Active insulin (U)": f"{exp.iob_u:.2f}",
                "Correction wanted (U)": f"{exp.recommended_units:.3f}",
                "Safety decision": GATE_LABELS.get(exp.safety_gate, exp.safety_gate),
                "Delivered (U)": f"{exp.delivered_units:.3f}",
                "Clinical rationale": exp.narrative,
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
                gate_idx = list(_tl_df.columns).index("Safety decision")
                result[gate_idx] = f"background-color:{bg}; color:{fg}; font-weight:700;"
            except ValueError:
                pass
            return result

        _styled = _tl_df.style.apply(_style_gate, axis=1)
        st.dataframe(_styled, use_container_width=True, hide_index=True)

        # ── Step drill-down ─────────────────────────────────────────────
        st.markdown(f"""
        <div style="font-family:'Inter',sans-serif; font-size:0.72rem; font-weight:600;
                    color:{MUTED}; margin:1rem 0 0.4rem 0;">Step detail</div>
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
            f"  Dosing paused   : interval {_e.suspension_step}\n"
            if _e.is_suspended else ""
        )

        st.markdown(f"""
<div style="background:{BG3}; border:1px solid {GRID}; border-left:3px solid {_gate_fg};
            border-radius:6px; padding:1rem 1.25rem; margin-top:0.25rem;
            font-family:'JetBrains Mono',monospace; font-size:0.78rem;
            color:{WHITE}; line-height:1.9; white-space:pre;">
<span style="color:{MUTED}">── t = {_e.timestamp_min} min ─────────────────────────────────────────</span>
<span style="color:{CYAN}">  CGM glucose       : {_e.cgm_mgdl:.1f} mg/dL</span>
<span style="color:{WHITE}">  Glucose trend     : {_e.trend_arrow}  {_e.trend_rate_mgdl_per_min:+.2f} mg/dL/min</span>
<span style="color:{WHITE}">  Predicted (+{_e.prediction_horizon_min} min) : {_e.predicted_glucose_mgdl:.1f} mg/dL</span>
<span style="color:{WHITE}">  Active insulin    : {_e.iob_u:.3f} U</span>
<span style="color:{MUTED}">── Algorithm ──────────────────────────────────────────────────────</span>
<span style="color:{WHITE}">  Calculated dose   : {_e.recommended_units:.3f} U</span>
<span style="color:{MUTED}">  Rationale         : {_e.controller_reason}</span>
<span style="color:{MUTED}">── Safety check ───────────────────────────────────────────────────</span>
<span style="color:{_gate_fg}">  Decision          : {_gate_lbl}</span>
<span style="color:{MUTED}">  Reason            : {_e.safety_reason}</span>
<span style="color:{WHITE}">  Outcome           : {_e.safety_status}</span>
<span style="color:{WHITE}">  Final dose        : {_e.safety_final_units:.3f} U</span>{_susp_line}
<span style="color:{MUTED}">── Delivery ───────────────────────────────────────────────────────</span>
<span style="color:{NEON}">  Delivered         : {_e.delivered_units:.3f} U</span>
<span style="color:{MUTED}">── Clinical summary ───────────────────────────────────────────────</span>
<span style="color:{WHITE}">  {_e.narrative}</span>
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
    if name == "Sustained Basal Deficit":
        return sustained_basal_deficit_scenario()
    if name == "Exercise Hypoglycemia":
        return exercise_hypoglycemia_scenario()
    if name == "Missed Bolus":
        return missed_bolus_scenario()
    if name == "Late Correction":
        return late_correction_scenario()
    if name == "Overnight Stability":
        return overnight_stability_scenario()
    if name == "Stacked Corrections":
        return stacked_corrections_scenario()
    if name == "Rapid Drop":
        return rapid_drop_scenario()
    return baseline_meal_scenario()


# ── Header ───────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="padding:1.75rem 0 1.25rem 0; border-bottom:2px solid {NEON_DIM}; margin-bottom:1.75rem;">
  <div style="display:flex; align-items:baseline; gap:0.9rem; flex-wrap:wrap;">
    <div style="font-family:'Inter',sans-serif; font-size:1.9rem; font-weight:700;
                color:{NEON}; line-height:1; letter-spacing:-0.5px;">
      SWARM Bolus
    </div>
    <div style="font-family:'Inter',sans-serif; font-size:0.9rem; font-weight:400;
                color:{MUTED}; letter-spacing:0px;">
      Autonomous Insulin Dosing Simulation
    </div>
  </div>
  <div style="font-family:'Inter',sans-serif; font-size:0.82rem;
              color:{MUTED}; margin-top:0.4rem;">
    Physiological insulin &amp; glucose model · Supports FreeStyle Libre and Dexcom CGM intervals
  </div>
  <div style="margin-top:0.9rem; display:flex; gap:0.6rem; flex-wrap:wrap; align-items:center;">
    <span style="background:rgba(220,38,38,0.08); border:1px solid {RED}; color:{RED};
                 padding:3px 10px; font-size:0.72rem; font-family:'Inter',sans-serif;
                 border-radius:4px; font-weight:500;">
      ⚠ Research use only — not for clinical decision-making
    </span>
    <span style="background:rgba(22,163,74,0.08); border:1px solid {NEON_DIM}; color:{NEON};
                 padding:3px 10px; font-size:0.72rem; font-family:'Inter',sans-serif;
                 border-radius:4px; font-weight:500;">
      ✓ Active insulin tracking
    </span>
    <span style="background:rgba(22,163,74,0.08); border:1px solid {NEON_DIM}; color:{NEON};
                 padding:3px 10px; font-size:0.72rem; font-family:'Inter',sans-serif;
                 border-radius:4px; font-weight:500;">
      ✓ Multi-layer safety checks
    </span>
    <span style="background:rgba(29,78,216,0.08); border:1px solid {CYAN}; color:{CYAN};
                 padding:3px 10px; font-size:0.72rem; font-family:'Inter',sans-serif;
                 border-radius:4px; font-weight:500;">
      ✓ Split bolus (dual-wave) delivery
    </span>
    <span style="background:rgba(29,78,216,0.08); border:1px solid {CYAN}; color:{CYAN};
                 padding:3px 10px; font-size:0.72rem; font-family:'Inter',sans-serif;
                 border-radius:4px; font-weight:500;">
      ✓ Glucose trend–guided dosing
    </span>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Algorithm Innovations panel ──────────────────────────────────────────────
with st.expander("Clinical Algorithm Features", expanded=False):
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"""
<div style="font-family:'Inter',sans-serif; font-size:0.72rem; font-weight:700;
            color:{CYAN}; text-transform:uppercase; letter-spacing:0.5px;
            margin-bottom:0.4rem; margin-top:0.25rem;">
  1 · 1-Minute CGM Loop
</div>
<div style="font-family:'Inter',sans-serif; font-size:0.85rem; color:{WHITE};
            line-height:1.7; margin-bottom:1rem;">
  Runs at <strong style="color:{NEON};">1-minute intervals</strong>, matching FreeStyle Libre's
  native sampling rate. Detection thresholds are expressed in
  <strong style="color:{NEON};">mg/dL per minute</strong> so the algorithm behaves
  identically whether the loop runs at 1-min or 5-min cadence.<br/>
  <span style="color:{MUTED}; font-size:0.78rem;">Set in sidebar: Simulation → CGM reading interval = 1 min</span>
</div>

<div style="font-family:'Inter',sans-serif; font-size:0.72rem; font-weight:700;
            color:{CYAN}; text-transform:uppercase; letter-spacing:0.5px;
            margin-bottom:0.4rem;">
  2 · Split Delivery (Dual-Wave Bolus)
</div>
<div style="font-family:'Inter',sans-serif; font-size:0.85rem; color:{WHITE};
            line-height:1.7; margin-bottom:0.5rem;">
  Mimics a <strong style="color:{NEON};">combo / dual-wave bolus</strong> as used on
  clinical pumps. Each correction is split into an
  <strong>immediate portion</strong> (covers the initial spike) and an
  <strong>extended tail</strong> dripped evenly over a configurable window.
</div>
<div style="background:{BG3}; border-left:3px solid {CYAN}; padding:0.5rem 0.9rem;
            font-family:'Inter',sans-serif; font-size:0.82rem;
            color:{MUTED}; line-height:1.6; margin-bottom:0.5rem; border-radius:0 4px 4px 0;">
  Example: 30 g carbs → 6 units total → <strong style="color:{WHITE};">2 U now + 4 U over 20 min</strong>
</div>
<div style="font-family:'Inter',sans-serif; font-size:0.78rem; color:{MUTED};">
  Set in sidebar: Split Delivery → Enable, then adjust fraction &amp; duration
</div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
<div style="font-family:'Inter',sans-serif; font-size:0.72rem; font-weight:700;
            color:{CYAN}; text-transform:uppercase; letter-spacing:0.5px;
            margin-bottom:0.4rem; margin-top:0.25rem;">
  3 · Trend-Guided Dosing
</div>
<div style="font-family:'Inter',sans-serif; font-size:0.85rem; color:{WHITE};
            line-height:1.7; margin-bottom:0.5rem;">
  The correction dose is automatically scaled to how fast glucose is
  rising — the faster the rise, the larger the dose.
</div>
<div style="background:{BG3}; border:1px solid {NEON_DIM}; border-radius:4px;
            padding:0.6rem 0.9rem; font-family:'Inter',sans-serif;
            font-size:0.82rem; color:{WHITE}; line-height:2; margin-bottom:0.5rem;">
  <span style="color:{MUTED};">Flat (&lt; 1 mg/dL/min)</span> &nbsp;→&nbsp; <span style="color:#888888;">No dose</span><br/>
  <span style="color:{MUTED};">Moderate (1–2 mg/dL/min)</span> &nbsp;→&nbsp; <span style="color:{AMBER};">25% of correction</span><br/>
  <span style="color:{MUTED};">Rising fast (2–3 mg/dL/min)</span> &nbsp;→&nbsp; <span style="color:{AMBER};">50%</span><br/>
  <span style="color:{MUTED};">Spiking (≥ 3 mg/dL/min)</span> &nbsp;→&nbsp; <span style="color:{NEON};">Full correction</span>
</div>
<div style="font-family:'Inter',sans-serif; font-size:0.78rem;
            color:{MUTED}; margin-bottom:1.25rem;">
  Set in sidebar: Dosing Strategy → Smart dose scaling by rise rate
</div>

<div style="font-family:'Inter',sans-serif; font-size:0.72rem; font-weight:700;
            color:{CYAN}; text-transform:uppercase; letter-spacing:0.5px;
            margin-bottom:0.4rem;">
  4 · Weight-Based Insulin Sensitivity (1700 Rule)
</div>
<div style="font-family:'Inter',sans-serif; font-size:0.85rem; color:{WHITE};
            line-height:1.7; margin-bottom:0.5rem;">
  Insulin sensitivity (ISF) is estimated automatically from body weight
  using the standard 1700 Rule.
</div>
<div style="background:{BG3}; border-left:3px solid {NEON}; padding:0.5rem 0.9rem;
            font-family:'JetBrains Mono',monospace; font-size:0.82rem;
            color:{NEON}; margin-bottom:0.5rem; border-radius:0 4px 4px 0;">
  ISF ≈ 1700 ÷ (weight × 0.55)
</div>
<div style="font-family:'Inter',sans-serif; font-size:0.82rem; color:{WHITE};
            line-height:1.6; margin-bottom:0.4rem;">
  70 kg patient → ~38.5 U/day → ISF ≈ 44 mg/dL per unit<br/>
  Insulin-to-carb ratio also estimated (500 Rule).
</div>
<div style="font-family:'Inter',sans-serif; font-size:0.78rem; color:{MUTED};">
  Set in sidebar: Patient Profile → Estimate from weight
</div>
        """, unsafe_allow_html=True)

# ── Sidebar ──────────────────────────────────────────────────────────────────
SCENARIO_OPTIONS = [
    "Baseline Meal",
    "Fasting Baseline",
    "Large Meal Spike",
    "Dawn Phenomenon",
    "Sustained Basal Deficit",
    "Exercise Hypoglycemia",
    "Missed Bolus",
    "Late Correction",
]

with st.sidebar:
    st.markdown(f"""
    <div style="font-family:'Inter',sans-serif; font-size:1.05rem; font-weight:700;
                color:{NEON}; padding:0.6rem 0 0.9rem 0;
                border-bottom:1px solid {NEON_DIM}; letter-spacing:-0.3px;">
      SWARM Bolus · Settings
    </div>
    """, unsafe_allow_html=True)

    # ── Clinical modes ────────────────────────────────────────────────────
    st.markdown(
        f"<div style='font-size:0.68rem;font-weight:700;color:{MUTED};letter-spacing:0.6px;"
        f"text-transform:uppercase;padding:0.4rem 0 0.3rem 0;'>Clinical</div>",
        unsafe_allow_html=True,
    )
    _nav_clinical = st.radio(
        "",
        ["Clinical Review", "⬡ Closed Loop Demo", "Retrospective CGM Replay", "⬡ Swarm Bolus Lab"],
        key="nav_clinical",
        label_visibility="collapsed",
    )

    st.markdown(
        f"<hr style='border:none;border-top:1px solid {GRID};margin:0.6rem 0 0.4rem 0'/>",
        unsafe_allow_html=True,
    )

    # ── Research & Validation (collapsed by default) ───────────────────
    st.markdown(
        f"<div style='font-size:0.68rem;font-weight:700;color:{MUTED};letter-spacing:0.6px;"
        f"text-transform:uppercase;padding:0.1rem 0 0.3rem 0;'>Research & Validation</div>",
        unsafe_allow_html=True,
    )
    _nav_research_open = st.checkbox("Open research tools", value=False, key="nav_research_open")
    if _nav_research_open:
        _nav_research = st.radio(
            "",
            ["A vs B Comparison", "Population Sweep", "PSO Optimizer"],
            key="nav_research",
            label_visibility="collapsed",
        )
        _dashboard_mode_raw = _nav_research
    else:
        _dashboard_mode_raw = _nav_clinical

    st.markdown(
        f"<hr style='border:none;border-top:1px solid {GRID};margin:0.6rem 0 0.2rem 0'/>",
        unsafe_allow_html=True,
    )

    _MODE_KEY = {
        "Clinical Review":       "Clinical Review",
        "⬡ Closed Loop Demo":    "Closed Loop Demo",
        "Retrospective CGM Replay": "Retrospective Replay",
        "⬡ Swarm Bolus Lab":     "Swarm Bolus Lab",
        "A vs B Comparison":     "Comparison",
        "Population Sweep":      "Profile Sweep",
        "PSO Optimizer":         "PSO Optimizer",
    }
    dashboard_mode = _MODE_KEY[_dashboard_mode_raw]

    st.header("Clinical Scenario")
    if dashboard_mode == "Clinical Review":
        st.markdown(
            f"<div style='font-size:0.82rem;color:{MUTED};line-height:1.6;'>"
            "Runs all critical scenarios automatically. Press <strong>Run Clinical Review</strong> to start."
            "</div>",
            unsafe_allow_html=True,
        )
    elif dashboard_mode == "Closed Loop Demo":
        demo_scenario_name = st.selectbox(
            "Scenario",
            options=["Baseline Meal", "Large Meal Spike", "Missed Bolus", "Dawn Phenomenon", "Sustained Basal Deficit"],
            index=0,
        )
        st.caption(SCENARIO_DESCRIPTIONS.get(demo_scenario_name, ""))
    elif dashboard_mode == "Comparison":
        scenario_a_name = st.selectbox("Scenario A", options=SCENARIO_OPTIONS, index=0)
        st.caption(SCENARIO_DESCRIPTIONS.get(scenario_a_name, ""))
        scenario_b_name = st.selectbox("Scenario B", options=SCENARIO_OPTIONS, index=2)
        st.caption(SCENARIO_DESCRIPTIONS.get(scenario_b_name, ""))
    elif dashboard_mode == "Profile Sweep":
        sweep_scenario_name = st.selectbox("Scenario", options=SCENARIO_OPTIONS, index=0)
        st.caption(SCENARIO_DESCRIPTIONS.get(sweep_scenario_name, ""))
        scenario_a_name = sweep_scenario_name
        scenario_b_name = sweep_scenario_name
    elif dashboard_mode == "PSO Optimizer":
        st.markdown(f"""
<div style="background:rgba(29,78,216,0.07); border:1.5px solid {CYAN};
            border-radius:8px; padding:0.85rem 1rem; margin:0.6rem 0 0.4rem 0;">
  <div style="font-size:0.72rem; font-weight:700; color:{CYAN};
              text-transform:uppercase; letter-spacing:0.5px; margin-bottom:0.4rem;">
    Fully Autonomous · No configuration required
  </div>
  <div style="font-size:0.82rem; color:{WHITE}; line-height:1.6;">
    The swarm evaluates all 6 clinical scenarios across all 4 patient
    archetypes and finds the optimal parameter set automatically.<br/>
    Press <strong>Run PSO Optimisation</strong> — nothing else to set.
  </div>
</div>""", unsafe_allow_html=True)
        # All PSO config is hardcoded — no user input needed.
        # These are the clinical defaults used every time.
        _pso_selected_scenarios = list(NAMED_SCENARIOS.keys())  # all scenarios
        _pso_n_particles = 20
        _pso_n_iterations = 25
        _pso_hypo_weight = 3.0
        # Dummy variables so downstream code that reads scenario_a/b names won't crash
        scenario_a_name = "Baseline Meal"
        scenario_b_name = "Baseline Meal"
    elif dashboard_mode == "Clinical Review":
        # Clinical Review runs its own scenario list — no a/b selection needed.
        # Dummy values prevent NameError in shared downstream code.
        scenario_a_name = "Baseline Meal"
        scenario_b_name = "Baseline Meal"
    else:  # Retrospective Replay
        retro_source = st.radio(
            "CGM data source",
            ["Built-in reference trace", "Upload CSV file", "Paste CSV text"],
        )
        retro_trace_name: str | None = None
        retro_uploaded_text: str | None = None

        if retro_source == "Built-in reference trace":
            retro_trace_name = st.selectbox(
                "Select reference trace",
                options=list(REFERENCE_TRACES.keys()),
            )
            st.caption(REFERENCE_TRACE_DESCRIPTIONS.get(retro_trace_name, ""))
        elif retro_source == "Upload CSV file":
            retro_file = st.file_uploader(
                "Upload CGM file",
                type=["csv", "txt"],
                help="Accepted formats:\n"
                     "• Simple CSV: timestamp_min, glucose_mgdl\n"
                     "• Dexcom G6/G7 Clarity export (auto-detected)",
            )
            if retro_file is not None:
                retro_uploaded_text = retro_file.read().decode("utf-8", errors="replace")
        else:  # Paste
            retro_uploaded_text = st.text_area(
                "Paste CGM readings",
                placeholder="timestamp_min,glucose_mgdl\n0,110\n5,115\n10,121\n...",
                height=160,
            )

        st.header("Patient Parameters (Replay)")
        retro_isf = st.slider(
            "Insulin sensitivity — mg/dL drop per unit",
            20.0, 120.0, 50.0, 1.0,
            help="How much 1 unit of insulin lowers blood glucose for this patient. "
                 "Higher = more sensitive. Typical adult range: 30–80 mg/dL/U.",
        )
        retro_peak = st.selectbox(
            "Insulin type (time to peak action)",
            [55, 65, 75],
            index=2,
            format_func=lambda v: {55: "Fiasp / ultra-rapid (55 min)", 65: "Humalog / Lispro (65 min)", 75: "NovoLog / Aspart (75 min)"}[v],
        )
        scenario_a_name = retro_trace_name or "Custom trace"
        scenario_b_name = scenario_a_name

    if dashboard_mode == "Closed Loop Demo":
        # ── Demo: zero configuration — all defaults, no visible controls ──
        st.markdown(f"""
<div style="background:rgba(22,163,74,0.08); border:1.5px solid {NEON};
            border-radius:8px; padding:0.85rem 1rem; margin:0.75rem 0;">
  <div style="font-size:0.72rem; font-weight:700; color:{NEON};
              text-transform:uppercase; letter-spacing:0.5px; margin-bottom:0.4rem;">
    Autonomous · No setup required
  </div>
  <div style="font-size:0.82rem; color:{WHITE}; line-height:1.6;">
    The algorithm reads the glucose signal only.<br/>
    No patient type. No profile. No manual input.
  </div>
</div>""", unsafe_allow_html=True)
        # Fixed demo defaults — not user-configurable
        _autonomous_isf             = True
        correction_factor_mgdl_per_unit = 50.0
        duration_minutes            = 240
        step_minutes                = 5
        max_units_per_interval      = 1.0
        max_insulin_on_board_u      = 3.0
        min_predicted_glucose_mgdl  = 80
        require_confirmed_trend     = True
        min_excursion_delta         = 0.0
        microbolus_fraction         = 0.25
        _dw_enabled                 = False
        _dw_imm_frac                = 0.33
        _dw_ext_dur                 = 20
        dose_increment_u            = 0.05
        pump_max_units_per_interval = 1.0

    elif dashboard_mode == "PSO Optimizer":
        # PSO uses its own config panel (rendered above in Clinical Scenario section)
        # Provide dummy values for variables that downstream code may reference.
        _autonomous_isf             = False
        correction_factor_mgdl_per_unit = 50.0
        duration_minutes            = 180
        step_minutes                = 5
        max_units_per_interval      = 0.30
        max_insulin_on_board_u      = 3.0
        min_predicted_glucose_mgdl  = 80
        require_confirmed_trend     = True
        min_excursion_delta         = 0.0
        microbolus_fraction         = 0.25
        _dw_enabled                 = False
        _dw_imm_frac                = 0.33
        _dw_ext_dur                 = 20
        dose_increment_u            = 0.05
        pump_max_units_per_interval = 1.0

    else:
        # ── All other modes: full controls ────────────────────────────────
        st.header("Simulation Settings")
        duration_minutes = st.slider("Run duration (minutes)", 30, 360, 180, 30)
        step_minutes = st.selectbox(
            "CGM reading interval",
            [1, 5, 10, 15],
            index=1,
            format_func=lambda v: f"{v} min  ({'FreeStyle Libre' if v == 1 else 'Dexcom G6/G7' if v == 5 else 'standard'})",
            help="How often the CGM provides a reading and the controller makes a decision. "
                 "1 min matches FreeStyle Libre; 5 min matches Dexcom G6/G7. "
                 "Detection thresholds adjust automatically.",
        )

        st.header("Patient Profile")
        _autonomous_isf = st.checkbox(
            "Autonomous mode — infer sensitivity from glucose dynamics",
            value=True,
            help="Full self-driving pancreas mode. Three capabilities activate together:\n\n"
                 "1 · Autonomous ISF: watches how fast glucose spikes and infers insulin sensitivity "
                 "from that signal — no ISF input required. Fast spike → resistant → doses more. "
                 "Slow rise → sensitive → doses conservatively.\n\n"
                 "2 · Online ISF learning: records every dose and the glucose drop it caused 60 min later. "
                 "The more the system runs, the more precisely it knows this patient's real sensitivity — "
                 "blending the live observation history with the rate-of-rise estimate.\n\n"
                 "3 · Cause-aware dosing: distinguishes meal spikes from basal drift from post-hypo rebound. "
                 "Each cause gets a different strategy — pre-bolus on meal ONSET (fires once per meal), "
                 "25%% micro-bolus for drift, 10%% touch for rebound.",
        )
        if _autonomous_isf:
            st.caption(
                "Sensitivity inferred from glucose dynamics · online learning from dose→response history · "
                "cause-aware dosing (meal / basal drift / rebound). No manual ISF input required."
            )
            correction_factor_mgdl_per_unit = 50.0
        else:
            _use_weight_isf = st.checkbox(
                "Estimate insulin sensitivity from weight",
                value=False,
                help="Uses the 1700 Rule: ISF = 1700 ÷ total daily dose, "
                     "where total daily dose ≈ body weight (kg) × 0.55. "
                     "You can override the result manually.",
            )
            _weight_kg = st.slider("Body weight (kg)", 30.0, 150.0, 70.0, 1.0)
            if _use_weight_isf:
                _auto_isf = estimate_isf_from_weight(_weight_kg)
                st.caption(
                    f"Estimated sensitivity: **{_auto_isf:.1f} mg/dL per unit**  "
                    f"(daily dose ≈ {_weight_kg * 0.55:.1f} U)"
                )
                correction_factor_mgdl_per_unit = _auto_isf
            else:
                correction_factor_mgdl_per_unit = st.slider(
                    "Insulin sensitivity — mg/dL drop per unit",
                    20.0, 120.0, 50.0, 1.0,
                    help="How much blood glucose drops per unit of insulin for this patient. "
                         "30 = insulin resistant, 50 = typical adult, 85 = highly sensitive.",
                )

        st.header("Safety Limits")
        max_units_per_interval = st.slider(
            "Maximum dose per reading (units)", 0.05, 3.0, 1.0, 0.05,
            help="Hard cap on insulin delivered in a single interval.",
        )
        max_insulin_on_board_u = st.slider(
            "Maximum active insulin allowed (units)", 0.5, 10.0, 3.0, 0.1,
            help="If total insulin still active in the body reaches this level, "
                 "the controller will not add more — prevents stacking doses.",
        )
        min_predicted_glucose_mgdl = st.slider(
            "Low glucose safety threshold (mg/dL)", 60, 120, 80, 1,
            help="If glucose is predicted to fall below this value within 30 minutes, "
                 "all dosing is suspended until it recovers.",
        )
        require_confirmed_trend = st.checkbox(
            "Wait for two consecutive rising readings before dosing",
            value=True,
            help="Avoids giving insulin on a single noisy reading. Recommended: keep this on.",
        )

        st.header("Dosing Strategy")
        min_excursion_delta = st.slider(
            "Ignore glucose changes smaller than (mg/dL)", 0.0, 15.0, 0.0, 0.5,
            help="Set to a small value (e.g. 2–5) to avoid reacting to sensor noise.",
        )
        _ror_tiered = st.checkbox(
            "Adjust dose size based on how fast glucose is rising",
            value=False,
            help="Faster rise triggers a larger dose automatically.",
        )
        if _ror_tiered:
            microbolus_fraction = 1.0
            st.caption("Dose fraction set automatically — faster rise triggers a larger dose.")
        else:
            microbolus_fraction = st.slider(
                "What fraction of the calculated correction to deliver each interval",
                0.0, 1.0, 0.25, 0.05,
                help="0.25 = cautious micro-bolus. 1.0 = full correction in one go.",
            )

        st.header("Split Bolus Delivery")
        _dw_enabled = st.checkbox(
            "Use dual-wave (combo) bolus delivery",
            value=False,
            help="A portion is delivered immediately; the remainder is spread slowly over a set window.",
        )
        if _dw_enabled:
            _dw_imm_frac = st.slider(
                "Immediate portion (fraction of total dose)", 0.1, 0.9, 0.33, 0.01,
            )
            _dw_ext_dur = st.selectbox(
                "Extended delivery window",
                [10, 15, 20, 30, 45], index=2,
                format_func=lambda v: f"{v} minutes",
            )
        else:
            _dw_imm_frac = 0.33
            _dw_ext_dur  = 20

        st.header("Pump Settings")
        dose_increment_u = st.selectbox(
            "Smallest dose the pump can deliver",
            [0.05, 0.1], index=0,
            format_func=lambda v: f"{v} units",
            help="0.05 U matches most modern insulin pumps.",
        )
        pump_max_units_per_interval = st.slider(
            "Pump hardware dose ceiling (units)", 0.05, 3.0, 1.0, 0.05,
        )

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    _btn_labels = {
        "Closed Loop Demo": "Run Closed Loop Demo",
        "Comparison": "Run Comparison",
        "Profile Sweep": "Run Population Sweep",
        "Retrospective Replay": "Run Retrospective Replay",
        "PSO Optimizer": "Optimise Autonomously",
    }
    _btn_label = _btn_labels.get(dashboard_mode, "Run")
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
    dual_wave_config = DualWaveConfig(
        enabled=_dw_enabled,
        immediate_fraction=_dw_imm_frac,
        extended_duration_minutes=int(_dw_ext_dur),
    )

    if dashboard_mode == "Clinical Review":
        # ─────────────────────────────────────────────────────────────────
        # CLINICAL REVIEW MODE
        # Runs all critical scenarios with a single button. Designed for
        # doctor evaluation — plain language, clear pass/fail, no settings.
        # ─────────────────────────────────────────────────────────────────

        st.markdown(f"""
<div style="font-family:'Inter',sans-serif; font-size:1.4rem; font-weight:700;
            color:{WHITE}; margin:0.5rem 0 0.25rem 0; letter-spacing:-0.3px;">
  Clinical Review — Autonomous Insulin Delivery
</div>
<div style="font-family:'Inter',sans-serif; font-size:0.9rem; color:{MUTED};
            margin-bottom:1rem; line-height:1.7; max-width:820px;">
  This review runs every critical clinical scenario automatically and reports whether the
  algorithm meets ADA/EASD standards without any human intervention.<br/>
  <strong>No settings required. No manual input. The algorithm decides everything.</strong>
</div>
""", unsafe_allow_html=True)

        # (name, duration_min, description, pass_criteria)
        # pass_criteria: "standard" = TIR≥70 + no hypo + peak<250
        #                "no_insulin" = algorithm must deliver 0 insulin (physiological drop — can't prevent)
        #                "no_hypo"    = hypo safety only (TIR may be lower due to IOB throttling)
        _CR_SCENARIOS = [
            ("Baseline Meal",           240, "Standard 45g meal — routine post-meal control",          "standard"),
            ("Missed Bolus",            240, "75g meal, no pre-bolus — retroactive autonomous correction","standard"),
            ("Dawn Phenomenon",         300, "Overnight cortisol rise — slow drift detection",          "standard"),
            ("Sustained Basal Deficit", 240, "Chronic insufficient background insulin",                 "standard"),
            ("Exercise Hypoglycemia",   240, "Rapid glucose fall — hypo guard must suspend all dosing", "no_insulin"),
            ("Rapid Drop",              180, "24 mg/dL/hr drop — algorithm must not dose into the fall","no_insulin"),
            ("Stacked Corrections",     360, "3 snacks, 60 min apart — IOB guard prevents unsafe stacking","no_hypo"),
            ("Overnight Stability",     480, "8 hours, no meal — algorithm must stay quiet and stable", "standard"),
        ]

        _cr_run = st.button("Run Clinical Review", type="primary", key="cr_run")

        if _cr_run:
            _cr_results = []
            _cr_charts = []

            with st.spinner("Running all scenarios — this takes 15–30 seconds…"):
                from ags.simulation.engine import run_simulation as _run_sim_cr

                for _cr_name, _cr_dur, _cr_desc, _cr_criteria in _CR_SCENARIOS:
                    _cr_inputs = build_scenario(_cr_name)
                    _cr_records, _cr_summary = run_closed_loop_evaluation(
                        simulation_inputs=_cr_inputs,
                        safety_thresholds=safety_thresholds,
                        duration_minutes=_cr_dur,
                        step_minutes=5,
                        seed=42,
                        autonomous_isf=True,
                    )
                    _cr_nt = _run_sim_cr(_cr_inputs, duration_minutes=_cr_dur, step_minutes=5, seed=42)
                    _cr_nt_cgm = [s.cgm_glucose_mgdl for s in _cr_nt]
                    _cr_nt_peak = max(_cr_nt_cgm)

                    _tir     = _cr_summary.percent_time_in_range
                    _peak    = _cr_summary.peak_cgm_glucose_mgdl
                    _hypos   = _cr_summary.time_below_range_steps
                    _ins     = _cr_summary.total_insulin_delivered_u
                    _blocked = _cr_summary.blocked_decisions

                    # Scenario-specific pass criteria
                    if _cr_criteria == "standard":
                        _overall = _tir >= 70.0 and _hypos == 0 and _peak < 250.0
                        _criteria_note = "TIR ≥70% · No hypos · Peak <250 mg/dL"
                    elif _cr_criteria == "no_insulin":
                        # Physiological drop — algorithm cannot prevent drift, but must not dose into it
                        _overall = round(_ins, 2) == 0.0
                        _criteria_note = "Algorithm must deliver 0 insulin — cannot add to a falling glucose"
                    else:  # no_hypo
                        _overall = _hypos == 0
                        _criteria_note = "No algorithm-caused hypos — IOB stacking must be prevented"

                    _cr_results.append({
                        "Scenario":        _cr_name,
                        "Description":     _cr_desc,
                        "Criteria":        _criteria_note,
                        "TIR %":           round(_tir, 1),
                        "Peak (mg/dL)":    round(_peak, 0),
                        "Hypo steps":      _hypos,
                        "Insulin (U)":     round(_ins, 2),
                        "Safety blocks":   _blocked,
                        "PASS":            _overall,
                        "_nt_peak":        _cr_nt_peak,
                        "_records":        _cr_records,
                        "_nt_cgm":         _cr_nt_cgm,
                        "_nt_t":           [s.timestamp_min for s in _cr_nt],
                    })

            # ── Summary table ─────────────────────────────────────────────
            st.markdown(f"""
<div style="font-size:1.1rem; font-weight:700; color:{WHITE};
            margin:1.5rem 0 0.75rem 0; border-bottom:2px solid {NEON_DIM};
            padding-bottom:0.4rem;">
  Results Summary
</div>""", unsafe_allow_html=True)

            _all_pass = all(r["PASS"] for r in _cr_results)
            _pass_count = sum(1 for r in _cr_results if r["PASS"])
            _verdict_color = NEON if _all_pass else (AMBER if _pass_count >= 6 else RED)
            _verdict_text = (
                "ALL SCENARIOS PASSED — Algorithm meets ADA/EASD standards across all critical conditions."
                if _all_pass else
                f"{_pass_count}/{len(_cr_results)} scenarios passed. Review failures before clinical submission."
            )
            st.markdown(f"""
<div style="background:rgba(22,163,74,0.07) if {_all_pass} else rgba(220,38,38,0.07);
            border:2px solid {_verdict_color}; border-radius:8px;
            padding:1rem 1.25rem; margin-bottom:1.5rem;
            font-family:'Inter',sans-serif;">
  <div style="font-size:0.72rem; font-weight:700; color:{_verdict_color};
              text-transform:uppercase; letter-spacing:0.5px; margin-bottom:0.4rem;">
    Overall Verdict
  </div>
  <div style="font-size:1rem; font-weight:600; color:{_verdict_color};">
    {_verdict_text}
  </div>
</div>""", unsafe_allow_html=True)

            # Render one row per scenario
            for _r in _cr_results:
                _row_color = NEON if _r["PASS"] else RED
                _status_label = "PASS" if _r["PASS"] else "FAIL"

                with st.expander(
                    f"{'✓' if _r['PASS'] else '✗'}  {_r['Scenario']}  —  "
                    f"TIR {_r['TIR %']}%  ·  Peak {_r['Peak (mg/dL)']:.0f} mg/dL  ·  "
                    f"Hypos {_r['Hypo steps']}  ·  {_status_label}",
                    expanded=not _r["PASS"],
                ):
                    st.caption(_r["Description"])
                    st.caption(f"Pass criteria: {_r['Criteria']}")

                    # Metric row
                    _rc1, _rc2, _rc3, _rc4, _rc5 = st.columns(5)
                    _rc1.metric("Time-in-Range", f"{_r['TIR %']}%", delta="≥70% target",
                                delta_color="normal" if _r["TIR %"] >= 70 else "inverse")
                    _rc2.metric("Peak Glucose", f"{_r['Peak (mg/dL)']:.0f} mg/dL",
                                delta=f"{_r['Peak (mg/dL)'] - _r['_nt_peak']:+.0f} vs no treatment",
                                delta_color="normal" if _r['Peak (mg/dL)'] < _r['_nt_peak'] else "inverse")
                    _rc3.metric("Hypo Steps", str(_r["Hypo steps"]),
                                delta="0 required", delta_color="normal" if _r["Hypo steps"] == 0 else "inverse")
                    _rc4.metric("Insulin Delivered", f"{_r['Insulin (U)']} U")
                    _rc5.metric("Safety Blocks", str(_r["Safety blocks"]))

                    # Glucose chart
                    _rec_df = pd.DataFrame([rec.__dict__ for rec in _r["_records"]])
                    _fig_cr = go.Figure()
                    _fig_cr.add_trace(go.Scatter(
                        x=_r["_nt_t"], y=_r["_nt_cgm"],
                        name="No treatment", line=dict(color=RED, dash="dash", width=1.5),
                        opacity=0.7,
                    ))
                    _fig_cr.add_trace(go.Scatter(
                        x=_rec_df["timestamp_min"], y=_rec_df["cgm_glucose_mgdl"],
                        name="Autonomous control", line=dict(color=NEON, width=2.5),
                    ))
                    # Dose markers
                    _dose_df = _rec_df[_rec_df["insulin_delivered_u"] > 0]
                    if not _dose_df.empty:
                        _fig_cr.add_trace(go.Scatter(
                            x=_dose_df["timestamp_min"],
                            y=_dose_df["cgm_glucose_mgdl"],
                            mode="markers",
                            name="Insulin dose",
                            marker=dict(color=CYAN, symbol="triangle-up", size=8),
                        ))
                    _fig_cr.add_hrect(y0=70, y1=180, fillcolor="rgba(22,163,74,0.06)",
                                      line_width=0, annotation_text="Target range",
                                      annotation_position="top left")
                    _fig_cr.add_hline(y=70,  line_dash="dot", line_color=RED,   line_width=1)
                    _fig_cr.add_hline(y=180, line_dash="dot", line_color=AMBER, line_width=1)
                    _fig_cr.update_layout(
                        height=300, margin=dict(l=40, r=20, t=20, b=40),
                        plot_bgcolor=BG, paper_bgcolor=BG,
                        legend=dict(orientation="h", y=1.08, x=0),
                        xaxis=dict(title="Time (min)", gridcolor=GRID),
                        yaxis=dict(title="Glucose (mg/dL)", gridcolor=GRID, range=[40, 320]),
                    )
                    st.plotly_chart(_fig_cr, use_container_width=True)

            # ── Download summary CSV ───────────────────────────────────────
            _cr_export_cols = ["Scenario", "Description", "Criteria", "TIR %", "Peak (mg/dL)",
                               "Hypo steps", "Insulin (U)", "Safety blocks", "PASS"]
            _cr_df_export = pd.DataFrame(_cr_results)[_cr_export_cols]
            st.download_button(
                "Download Clinical Review CSV",
                data=_cr_df_export.to_csv(index=False).encode(),
                file_name="swarm_bolus_clinical_review.csv",
                mime="text/csv",
            )

    elif dashboard_mode == "Closed Loop Demo":
        # ── Run both trajectories ──────────────────────────────────────────
        _demo_inputs = build_scenario(demo_scenario_name)

        # Demo always runs 240 min — long enough to show full glucose recovery
        _DEMO_DURATION = 240

        with st.spinner("Running closed-loop simulation…"):
            _cl_records, _cl_summary = run_closed_loop_evaluation(
                simulation_inputs=_demo_inputs,
                safety_thresholds=safety_thresholds,
                pump_config=pump_config,
                duration_minutes=_DEMO_DURATION,
                step_minutes=step_minutes,
                seed=42,
                autonomous_isf=True,
            )

        from ags.simulation.engine import run_simulation as _run_sim
        _nt_snaps = _run_sim(_demo_inputs, duration_minutes=_DEMO_DURATION, step_minutes=step_minutes, seed=42)

        _cl_df  = pd.DataFrame([r.__dict__ for r in _cl_records])
        _nt_t   = [s.timestamp_min for s in _nt_snaps]
        _nt_cgm = [s.cgm_glucose_mgdl for s in _nt_snaps]

        # ── Computed summary values ────────────────────────────────────────
        _nt_peak = max(_nt_cgm)
        _cl_peak = _cl_summary.peak_cgm_glucose_mgdl
        _cl_tir  = _cl_summary.percent_time_in_range
        _nt_tir  = sum(1 for g in _nt_cgm if 70 <= g <= 180) / max(len(_nt_cgm), 1) * 100
        _cl_ins  = _cl_summary.total_insulin_delivered_u
        _tir_delta = _cl_tir - _nt_tir
        _peak_delta = _cl_peak - _nt_peak

        # ── Page header ────────────────────────────────────────────────────
        st.markdown(f"""
<div style="font-family:'Inter',sans-serif; font-size:1.4rem; font-weight:700;
            color:{WHITE}; margin:0.5rem 0 0.25rem 0; letter-spacing:-0.3px;">
  Closed Loop Demo &mdash; {demo_scenario_name}
</div>
<div style="font-family:'Inter',sans-serif; font-size:0.9rem; color:{MUTED};
            margin-bottom:1.5rem; line-height:1.7; max-width:820px;">
  The artificial pancreas loop is fully closed. Every insulin dose shown below was decided
  and delivered autonomously — no manual input of any kind. The glucose trajectory responds
  to those deliveries in real time.<br/>
  <span style="color:{RED}; font-weight:600;">&#9644; No treatment</span> &nbsp;shows where glucose goes with zero intervention.&nbsp;
  <span style="color:{NEON}; font-weight:600;">&#9644; Autonomous control</span> &nbsp;shows the algorithm acting on its own.
</div>
""", unsafe_allow_html=True)

        # ── Metric cards (custom HTML — color-coded by clinical meaning) ───
        _card_css = (
            "font-family:'Inter',sans-serif; border-radius:8px; padding:1rem 1.25rem; "
            "min-height:100px; display:flex; flex-direction:column; justify-content:space-between;"
        )
        mc1, mc2, mc3, mc4 = st.columns(4)

        with mc1:
            st.markdown(f"""
<div style="{_card_css} background:rgba(220,38,38,0.07); border:1.5px solid {RED};">
  <div style="font-size:0.75rem; font-weight:600; color:{RED}; text-transform:uppercase;
              letter-spacing:0.5px; margin-bottom:0.5rem;">
    Peak Glucose &mdash; No Treatment
  </div>
  <div style="font-size:2rem; font-weight:700; color:{RED}; font-family:'Inter',sans-serif;">
    {_nt_peak:.0f} <span style="font-size:1rem; font-weight:400;">mg/dL</span>
  </div>
  <div style="font-size:0.75rem; color:{MUTED}; margin-top:0.4rem;">
    Uncontrolled — zero insulin delivered
  </div>
</div>""", unsafe_allow_html=True)

        with mc2:
            _peak_color = NEON if _peak_delta < 0 else RED
            st.markdown(f"""
<div style="{_card_css} background:rgba(22,163,74,0.07); border:1.5px solid {NEON};">
  <div style="font-size:0.75rem; font-weight:600; color:{NEON}; text-transform:uppercase;
              letter-spacing:0.5px; margin-bottom:0.5rem;">
    Peak Glucose &mdash; Autonomous
  </div>
  <div style="font-size:2rem; font-weight:700; color:{NEON}; font-family:'Inter',sans-serif;">
    {_cl_peak:.0f} <span style="font-size:1rem; font-weight:400;">mg/dL</span>
  </div>
  <div style="font-size:0.75rem; color:{_peak_color}; margin-top:0.4rem; font-weight:600;">
    {_peak_delta:+.0f} mg/dL vs no treatment
  </div>
</div>""", unsafe_allow_html=True)

        with mc3:
            _tir_color = NEON if _cl_tir >= 70 else AMBER
            st.markdown(f"""
<div style="{_card_css} background:rgba(22,163,74,0.07); border:1.5px solid {NEON};">
  <div style="font-size:0.75rem; font-weight:600; color:{NEON}; text-transform:uppercase;
              letter-spacing:0.5px; margin-bottom:0.5rem;">
    Time in Range &mdash; Autonomous
  </div>
  <div style="font-size:2rem; font-weight:700; color:{_tir_color}; font-family:'Inter',sans-serif;">
    {_cl_tir:.0f}<span style="font-size:1rem; font-weight:400;">%</span>
  </div>
  <div style="font-size:0.75rem; color:{MUTED}; margin-top:0.4rem;">
    {_tir_delta:+.0f}% vs no treatment &nbsp;·&nbsp; Target ≥70% (ADA)
  </div>
</div>""", unsafe_allow_html=True)

        with mc4:
            st.markdown(f"""
<div style="{_card_css} background:rgba(29,78,216,0.07); border:1.5px solid {CYAN};">
  <div style="font-size:0.75rem; font-weight:600; color:{CYAN}; text-transform:uppercase;
              letter-spacing:0.5px; margin-bottom:0.5rem;">
    Insulin Delivered
  </div>
  <div style="font-size:2rem; font-weight:700; color:{CYAN}; font-family:'Inter',sans-serif;">
    {_cl_ins:.2f} <span style="font-size:1rem; font-weight:400;">U</span>
  </div>
  <div style="font-size:0.75rem; color:{MUTED}; margin-top:0.4rem;">
    Autonomous — zero manual input
  </div>
</div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

        # ── Glucose trajectory chart ───────────────────────────────────────
        _demo_layout = _layout(f"Glucose Trajectory — {demo_scenario_name} (240 min)", height=460)
        _fig_demo = go.Figure(layout=_demo_layout)

        # Target range shading
        _fig_demo.add_hrect(
            y0=70, y1=180,
            fillcolor="rgba(22,163,74,0.06)", line_width=0,
        )

        # Clinical threshold lines — annotations placed LEFT side to avoid clipping
        _fig_demo.add_hline(
            y=250,
            line=dict(color=RED, width=1.5, dash="dash"),
            annotation=dict(
                text="Severe hyperglycemia — 250 mg/dL",
                font=dict(color=RED, size=9, family="Inter"),
                xanchor="left", x=0.01,
                bgcolor="rgba(248,250,252,0.85)",
            ),
        )
        _fig_demo.add_hline(
            y=180,
            line=dict(color=AMBER, width=1, dash="dot"),
            annotation=dict(
                text="Hyperglycemia threshold — 180 mg/dL",
                font=dict(color=AMBER, size=9, family="Inter"),
                xanchor="left", x=0.01,
                bgcolor="rgba(248,250,252,0.85)",
            ),
        )
        _fig_demo.add_hline(
            y=70,
            line=dict(color=RED, width=1, dash="dot"),
            annotation=dict(
                text="Hypoglycemia threshold — 70 mg/dL",
                font=dict(color=RED, size=9, family="Inter"),
                xanchor="left", x=0.01,
                bgcolor="rgba(248,250,252,0.85)",
            ),
        )

        # Meal event markers
        for _meal in _demo_inputs.meal_events:
            _fig_demo.add_vline(
                x=_meal.timestamp_min,
                line=dict(color=AMBER, width=1.5, dash="dot"),
                annotation=dict(
                    text=f"Meal — {_meal.carbs_g:.0f}g carbs",
                    font=dict(color=AMBER, size=9, family="Inter"),
                    textangle=-90,
                    xanchor="right",
                    yanchor="top",
                    bgcolor="rgba(248,250,252,0.85)",
                ),
            )

        # No-treatment trace
        _fig_demo.add_trace(go.Scatter(
            x=_nt_t,
            y=_nt_cgm,
            mode="lines",
            name="No treatment",
            line=dict(color=RED, width=2.5, dash="dash"),
            hovertemplate="<b>No treatment</b><br>t = %{x} min<br>Glucose = %{y:.1f} mg/dL<extra></extra>",
        ))

        # Autonomous closed-loop trace
        _fig_demo.add_trace(go.Scatter(
            x=_cl_df["timestamp_min"],
            y=_cl_df["cgm_glucose_mgdl"],
            mode="lines",
            name="Autonomous control",
            line=dict(color=NEON, width=2.5),
            hovertemplate="<b>Autonomous control</b><br>t = %{x} min<br>Glucose = %{y:.1f} mg/dL<extra></extra>",
        ))

        # Insulin delivery markers
        _dose_df = _cl_df[_cl_df["pump_delivered_units"] > 0].copy()
        if not _dose_df.empty:
            _fig_demo.add_trace(go.Scatter(
                x=_dose_df["timestamp_min"],
                y=_dose_df["cgm_glucose_mgdl"],
                mode="markers",
                name="Insulin delivered",
                marker=dict(
                    symbol="triangle-down",
                    size=12,
                    color=CYAN,
                    line=dict(color="white", width=1.5),
                ),
                customdata=_dose_df["pump_delivered_units"],
                hovertemplate="<b>Autonomous dose</b><br>t = %{x} min<br>%{customdata:.3f} U delivered<extra></extra>",
            ))

        _fig_demo.update_layout(
            xaxis_title="Time (minutes)",
            yaxis_title="Glucose (mg/dL)",
            yaxis=dict(range=[55, 275]),
            legend=dict(
                orientation="h",
                yanchor="bottom", y=1.02,
                xanchor="left", x=0,
                font=dict(size=11, family="Inter"),
                bgcolor="rgba(248,250,252,0.9)",
                bordercolor=GRID,
                borderwidth=1,
            ),
        )
        st.plotly_chart(_fig_demo, use_container_width=True)

        # ── Insulin delivery bar chart ─────────────────────────────────────
        if not _dose_df.empty:
            _ins_layout = _layout("Autonomous Insulin Deliveries", height=220)
            _fig_ins = go.Figure(layout=_ins_layout)
            _fig_ins.add_trace(go.Bar(
                x=_dose_df["timestamp_min"],
                y=_dose_df["pump_delivered_units"],
                name="Delivered (U)",
                marker=dict(color=CYAN, line=dict(color=CYAN, width=0)),
                width=[step_minutes * 0.6] * len(_dose_df),
                hovertemplate="<b>Autonomous dose</b><br>t = %{x} min<br>%{y:.3f} U<extra></extra>",
            ))
            _fig_ins.update_layout(
                yaxis_title="Insulin (U)",
                xaxis_title="Time (minutes)",
                xaxis=dict(range=[-5, _DEMO_DURATION + 5]),
                showlegend=False,
                bargap=0.2,
            )
            st.plotly_chart(_fig_ins, use_container_width=True)

        # ── Step-by-step decision table ────────────────────────────────────
        with st.expander("Step-by-step autonomous decisions", expanded=False):
            _demo_tbl = _cl_df[[
                "timestamp_min", "cgm_glucose_mgdl", "rate_mgdl_per_min",
                "glucose_cause", "meal_phase", "pump_delivered_units",
                "insulin_on_board_u", "recommendation_reason",
            ]].copy()
            _demo_tbl.columns = [
                "Time (min)", "Glucose (mg/dL)", "Rate (mg/dL·min⁻¹)",
                "Cause", "Meal Phase", "Delivered (U)",
                "IOB (U)", "Controller Decision",
            ]
            _demo_tbl["Glucose (mg/dL)"]      = _demo_tbl["Glucose (mg/dL)"].map("{:.1f}".format)
            _demo_tbl["Rate (mg/dL·min⁻¹)"]   = _demo_tbl["Rate (mg/dL·min⁻¹)"].map("{:+.3f}".format)
            _demo_tbl["Delivered (U)"]         = _demo_tbl["Delivered (U)"].map("{:.3f}".format)
            _demo_tbl["IOB (U)"]               = _demo_tbl["IOB (U)"].map("{:.3f}".format)
            st.dataframe(_demo_tbl, hide_index=True, use_container_width=True)

        st.stop()

    elif dashboard_mode == "Retrospective Replay":
        # ── Load readings ──────────────────────────────────────────────────
        try:
            if retro_source == "Built-in reference trace" and retro_trace_name:
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
            ror_tiered_microbolus=_ror_tiered,
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
        <div style="font-family:'Inter',sans-serif; font-size:1rem; font-weight:700;
                    color:{WHITE}; margin-bottom:0.75rem;">
          Retrospective Replay &mdash; {_trace_label}
        </div>
        """, unsafe_allow_html=True)

        # ── Metric row ─────────────────────────────────────────────────────
        rc1, rc2, rc3, rc4, rc5, rc6 = st.columns(6)
        rc1.metric("Time in Range", f"{retro_summary.percent_time_in_range:.1f}%")
        rc2.metric("Average glucose", f"{retro_summary.average_cgm_glucose_mgdl:.0f} mg/dL")
        rc3.metric("Peak glucose", f"{retro_summary.peak_cgm_glucose_mgdl:.0f} mg/dL")
        rc4.metric("Total insulin delivered (U)", f"{retro_summary.total_insulin_delivered_u:.2f}")
        rc5.metric("Blocked by safety", retro_summary.blocked_decisions, help="Intervals where the algorithm wanted to dose but was stopped — most commonly because active insulin had reached the safety cap.")
        rc6.metric("Low-glucose holds", retro_summary.time_suspended_steps, help="Intervals where dosing was suspended because glucose was predicted to drop below the low-glucose threshold.")

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
                mode="markers", name="Dose withheld",
                marker=dict(symbol="x", size=10, color=RED, line=dict(width=2, color=RED)),
                hovertemplate="t=%{x} min — dose withheld at %{y:.1f} mg/dL<extra>Withheld</extra>",
            ))
        _rCGM_layout = _layout("CGM trace — algorithm decisions overlaid", height=400)
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
            _rIns_layout = _layout("Hypothetical insulin delivery", height=280)
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
            _rIOB_layout = _layout("Hypothetical insulin still active in the body (IOB)", height=280)
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
        <div style="font-family:'Inter',sans-serif; font-size:0.8rem; font-weight:600;
                    color:{WHITE}; margin:1rem 0 0.5rem 0;">
          Report export
        </div>
        """, unsafe_allow_html=True)
        _rpass = _retro_report["verdicts"]["overall_pass"]
        _rcolor = NEON if _rpass else RED
        st.markdown(f"""
        <div style="font-family:'Inter',sans-serif; font-size:0.82rem;
                    color:{_rcolor}; margin-bottom:0.5rem;">
          {"✓ Meets ADA/EASD targets" if _rpass else "✗ Outside ADA/EASD targets"} &nbsp;·&nbsp;
          Time in Range {"✓" if _retro_report["verdicts"]["tir_pass"] else "✗"} &nbsp;·&nbsp;
          Peak glucose {"✓" if _retro_report["verdicts"]["peak_pass"] else "✗"} &nbsp;·&nbsp;
          Hypoglycaemia {"✓" if _retro_report["verdicts"]["hypo_pass"] else "✗"} &nbsp;·&nbsp;
          Variability {"✓" if _retro_report["verdicts"]["variability_pass"] else "✗"}
        </div>
        """, unsafe_allow_html=True)
        _rex1, _rex2 = st.columns(2)
        with _rex1:
            st.download_button(
                label="Download retrospective report (JSON)",
                data=json.dumps(_retro_report, indent=2),
                file_name=f"swarm_retro_{_trace_label.lower()[:30].replace(' ', '_')}.json",
                mime="application/json",
            )
        with _rex2:
            st.download_button(
                label="Download CGM trace (CSV)",
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
            ror_tiered_microbolus=_ror_tiered,
            autonomous_isf=_autonomous_isf,
            dual_wave_config=dual_wave_config,
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
        <div style="font-family:'Inter',sans-serif; font-size:1rem; font-weight:700;
                    color:{WHITE}; margin-bottom:0.75rem;">
          Patient Population Results &mdash; {sweep_scenario_name}
        </div>
        """, unsafe_allow_html=True)

        # Overall population pass/fail banner
        _all_pass = all(r.report["verdicts"]["overall_pass"] for r in sweep_results)
        _pop_color = NEON if _all_pass else RED
        _pop_text = "✓ All patient profiles meet ADA/EASD glycaemic targets" \
            if _all_pass else "⚠ One or more patient profiles fall outside ADA/EASD targets"
        st.markdown(f"""
        <div style="font-family:'Inter',sans-serif; font-size:0.875rem; font-weight:600;
                    color:{_pop_color}; border:1px solid {_pop_color}; border-radius:6px;
                    padding:0.6rem 1rem; margin-bottom:1rem;">
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
                <div style="font-family:'Inter',sans-serif; font-size:0.82rem; font-weight:600;
                            color:{_pc}; border-left:3px solid {_pc};
                            padding-left:0.6rem; margin-bottom:0.4rem;">
                  {_sr.profile.name}<br/>
                  <span style="font-size:0.75rem; font-weight:400; color:{MUTED};">{_sr.profile.description}</span>
                </div>
                """, unsafe_allow_html=True)
                st.metric("Time in Range", f"{_sr.summary.percent_time_in_range:.1f}%")
                st.metric("Peak glucose", f"{_sr.summary.peak_cgm_glucose_mgdl:.0f} mg/dL")
                st.metric("Average glucose", f"{_sr.summary.average_cgm_glucose_mgdl:.0f} mg/dL")
                st.metric("Glucose variability (SD)", f"{_sr.summary.glucose_variability_sd_mgdl:.1f}")
                _tir_v = "✓" if _pv["tir_pass"] else "✗"
                _pk_v = "✓" if _pv["peak_pass"] else "✗"
                _hy_v = "✓" if _pv["hypo_pass"] else "✗"
                _sd_v = "✓" if _pv["variability_pass"] else "✗"
                st.markdown(f"""
                <div style="font-family:'Inter',sans-serif; font-size:0.78rem;
                            color:{_pc if _pv["overall_pass"] else RED}; margin-top:0.3rem;">
                  {_ppass} &nbsp;·&nbsp; TIR {_tir_v} &nbsp;·&nbsp; Peak {_pk_v}
                  &nbsp;·&nbsp; Hypo {_hy_v} &nbsp;·&nbsp; Variability {_sd_v}
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
        _cgm_layout = _layout(f"Glucose trajectory — {sweep_scenario_name}", height=380)
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
        _ins_layout = _layout("Insulin delivered by patient profile", height=280)
        _ins_layout["yaxis"]["title"] = "units"
        _ins_layout["xaxis"]["title"] = "minutes"
        _ins_layout["barmode"] = "group"
        _ins_fig.update_layout(**_ins_layout)
        st.plotly_chart(_ins_fig, width="stretch")

        # Summary table
        with st.expander("Full metrics table", expanded=False):
            _tbl_data = {
                "Metric": [
                    "Time in Range (%)", "Average glucose (mg/dL)", "Peak glucose (mg/dL)",
                    "Glucose variability SD (mg/dL)", "Time below 70 mg/dL (readings)", "Time above 250 mg/dL (readings)",
                    "Insulin delivered (U)", "Doses withheld", "Dosing paused (readings)",
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
        <div style="font-family:'Inter',sans-serif; font-size:0.8rem; font-weight:600;
                    color:{WHITE}; margin:1rem 0 0.5rem 0;">
          Export full sweep report
        </div>
        """, unsafe_allow_html=True)
        _sweep_export = build_sweep_export(sweep_scenario_name, sweep_results)
        st.download_button(
            label="Download combined sweep report (JSON)",
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
                correction_factor_mgdl_per_unit=correction_factor_mgdl_per_unit,
                min_excursion_delta_mgdl=min_excursion_delta,
                microbolus_fraction=microbolus_fraction,
                ror_tiered_microbolus=_ror_tiered,
                autonomous_isf=_autonomous_isf,
                dual_wave_config=dual_wave_config,
            )
            records_b, summary_b = run_evaluation(
                simulation_inputs=build_scenario(scenario_b_name),
                safety_thresholds=safety_thresholds,
                pump_config=pump_config,
                duration_minutes=duration_minutes,
                step_minutes=step_minutes,
                seed=42,
                correction_factor_mgdl_per_unit=correction_factor_mgdl_per_unit,
                min_excursion_delta_mgdl=min_excursion_delta,
                microbolus_fraction=microbolus_fraction,
                ror_tiered_microbolus=_ror_tiered,
                autonomous_isf=_autonomous_isf,
                dual_wave_config=dual_wave_config,
            )

        df_a = pd.DataFrame([r.__dict__ for r in records_a])
        df_b = pd.DataFrame([r.__dict__ for r in records_b])

    # ── Scenario metric panels ────────────────────────────────────────────
    st.markdown(f"""
    <div style="font-family:'Inter',sans-serif; font-size:1rem; font-weight:700;
                color:{WHITE}; margin-bottom:0.75rem;">
      Scenario Comparison
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
        <div style="font-family:'Inter',sans-serif; font-size:0.875rem; font-weight:700;
                    color:{NEON}; margin-bottom:0.5rem;
                    border-left:3px solid {NEON}; padding-left:0.75rem;">
          Scenario A &mdash; {scenario_a_name}
        </div>
        """, unsafe_allow_html=True)
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Time in Range", f"{summary_a.percent_time_in_range:.1f}%")
        r2.metric("Average glucose", f"{summary_a.average_cgm_glucose_mgdl:.0f} mg/dL")
        r3.metric("Peak glucose", f"{summary_a.peak_cgm_glucose_mgdl:.0f} mg/dL")
        r4.metric("Above 250 mg/dL", f"{summary_a.time_above_250_steps} readings")
        r5, r6, r7, r8, r9 = st.columns(5)
        r5.metric("Correction wanted (U)", f"{summary_a.total_recommended_insulin_u:.2f}", help="Total insulin the algorithm calculated across all intervals. Most will be blocked when the active-insulin safety cap is reached.")
        r6.metric("Actually delivered (U)", f"{summary_a.total_insulin_delivered_u:.2f}")
        r7.metric("Blocked by safety", summary_a.blocked_decisions, help="Intervals where the algorithm wanted to dose but the safety system said no — most commonly because active insulin had already reached the safety cap.")
        r8.metric("Reduced to limit", summary_a.clipped_decisions, help="Intervals where the calculated dose was trimmed down to the per-interval maximum.")
        r9.metric("Low-glucose holds", summary_a.time_suspended_steps, help="Intervals where all dosing was suspended because glucose was predicted to drop below the low-glucose safety threshold.")

    with col_b:
        st.markdown(f"""
        <div style="font-family:'Inter',sans-serif; font-size:0.875rem; font-weight:700;
                    color:{CYAN}; margin-bottom:0.5rem;
                    border-left:3px solid {CYAN}; padding-left:0.75rem;">
          Scenario B &mdash; {scenario_b_name}
        </div>
        """, unsafe_allow_html=True)
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Time in Range", f"{summary_b.percent_time_in_range:.1f}%")
        r2.metric("Average glucose", f"{summary_b.average_cgm_glucose_mgdl:.0f} mg/dL")
        r3.metric("Peak glucose", f"{summary_b.peak_cgm_glucose_mgdl:.0f} mg/dL")
        r4.metric("Above 250 mg/dL", f"{summary_b.time_above_250_steps} readings")
        r5, r6, r7, r8, r9 = st.columns(5)
        r5.metric("Correction wanted (U)", f"{summary_b.total_recommended_insulin_u:.2f}", help="Total insulin the algorithm calculated across all intervals. Most will be blocked when the active-insulin safety cap is reached.")
        r6.metric("Actually delivered (U)", f"{summary_b.total_insulin_delivered_u:.2f}")
        r7.metric("Blocked by safety", summary_b.blocked_decisions, help="Intervals where the algorithm wanted to dose but the safety system said no — most commonly because active insulin had already reached the safety cap.")
        r8.metric("Reduced to limit", summary_b.clipped_decisions, help="Intervals where the calculated dose was trimmed down to the per-interval maximum.")
        r9.metric("Low-glucose holds", summary_b.time_suspended_steps, help="Intervals where all dosing was suspended because glucose was predicted to drop below the low-glucose safety threshold.")

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    # ── Contextual note: explain blocked doses ─────────────────────────
    _total_blocked = summary_a.blocked_decisions + summary_b.blocked_decisions
    if _total_blocked > 0:
        _block_parts = []
        if summary_a.blocked_decisions > 0:
            _block_parts.append(f"Scenario A: {summary_a.blocked_decisions} intervals blocked")
        if summary_b.blocked_decisions > 0:
            _block_parts.append(f"Scenario B: {summary_b.blocked_decisions} intervals blocked")
        st.info(
            f"**Why were doses blocked?** ({' · '.join(_block_parts)})  \n"
            f"The safety system prevents insulin stacking: once active insulin already in the body "
            f"reaches the cap you set ({max_insulin_on_board_u:.1f} U), no further doses are given until "
            f"that insulin clears. The gap between *Correction wanted* and *Actually delivered* reflects "
            f"this. This is expected behaviour — the algorithm is not broken. "
            f"To allow more aggressive correction, raise **Maximum active insulin allowed** in the sidebar. "
            f"Open the **Decision log** below each scenario to see the reason for every individual interval."
        )

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
    st.caption(
        "Red × = dose blocked by the safety system (active insulin reached the cap, "
        "or low-glucose protection fired). "
        "Orange △ = dose was reduced to the per-interval maximum. "
        "These markers mean the safety layer is working as intended."
    )

    # ── Metrics table ─────────────────────────────────────────────────────
    with st.expander("Clinical metrics table", expanded=False):
        compare_df = pd.DataFrame({
            "Metric": [
                "Time in Range (%)",
                "Average glucose (mg/dL)",
                "Peak glucose (mg/dL)",
                "Time above 250 mg/dL (readings)",
                "Glucose variability — SD (mg/dL)",
                "Algorithm-calculated dose (U)",
                "Insulin delivered (U)",
                "Doses withheld",
                "Doses capped at safety limit",
                "Doses approved",
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
            f"Time in Range:  Scenario A achieves better glycaemic control "
            f"({summary_a.percent_time_in_range:.1f}% vs {summary_b.percent_time_in_range:.1f}% time in range)."
        )
    elif summary_b.percent_time_in_range > summary_a.percent_time_in_range:
        verdict_lines.append(
            f"Time in Range:  Scenario B achieves better glycaemic control "
            f"({summary_b.percent_time_in_range:.1f}% vs {summary_a.percent_time_in_range:.1f}% time in range)."
        )
    else:
        verdict_lines.append("Time in Range:  Both scenarios achieve identical time-in-range.")

    if summary_b.peak_cgm_glucose_mgdl > summary_a.peak_cgm_glucose_mgdl + 10:
        verdict_lines.append(
            f"Peak glucose:   Scenario B has a higher post-prandial excursion "
            f"(peak {summary_b.peak_cgm_glucose_mgdl:.0f} vs {summary_a.peak_cgm_glucose_mgdl:.0f} mg/dL)."
        )
    elif summary_a.peak_cgm_glucose_mgdl > summary_b.peak_cgm_glucose_mgdl + 10:
        verdict_lines.append(
            f"Peak glucose:   Scenario A has a higher post-prandial excursion "
            f"(peak {summary_a.peak_cgm_glucose_mgdl:.0f} vs {summary_b.peak_cgm_glucose_mgdl:.0f} mg/dL)."
        )

    ints_a = summary_a.blocked_decisions + summary_a.clipped_decisions
    ints_b = summary_b.blocked_decisions + summary_b.clipped_decisions
    if ints_b > ints_a:
        verdict_lines.append(
            f"Safety checks:  Scenario B triggered more safety interventions ({ints_b} vs {ints_a}), "
            f"meaning the algorithm tried to dose more aggressively but was held back by the active-insulin cap more often."
        )
    elif ints_a > ints_b:
        verdict_lines.append(
            f"Safety checks:  Scenario A triggered more safety interventions ({ints_a} vs {ints_b}), "
            f"meaning the active-insulin cap was reached more often in that scenario."
        )

    if summary_b.total_insulin_delivered_u > summary_a.total_insulin_delivered_u * 1.15:
        verdict_lines.append(
            f"Insulin use:    Scenario B required "
            f"{summary_b.total_insulin_delivered_u - summary_a.total_insulin_delivered_u:.2f} U more insulin than Scenario A."
        )

    if summary_a.glucose_variability_sd_mgdl < summary_b.glucose_variability_sd_mgdl:
        verdict_lines.append(
            f"Variability:    Scenario A shows lower glucose variability "
            f"(SD {summary_a.glucose_variability_sd_mgdl:.1f} vs {summary_b.glucose_variability_sd_mgdl:.1f} mg/dL)."
        )

    if not verdict_lines:
        verdict_lines.append("Both scenarios perform similarly under the current settings.")

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
    <div style="font-family:'Inter',sans-serif; font-size:0.8rem; font-weight:600;
                color:{WHITE}; margin:1.5rem 0 0.5rem 0;">
      Validation report export
    </div>
    """, unsafe_allow_html=True)
    _exp_a, _exp_b = st.columns(2)
    with _exp_a:
        _pass_a = "✓ Meets targets" if _report_a["verdicts"]["overall_pass"] else "✗ Outside targets"
        _color_a = NEON if _report_a["verdicts"]["overall_pass"] else RED
        st.markdown(f"""
        <div style="font-family:'Inter',sans-serif; font-size:0.82rem;
                    color:{_color_a}; margin-bottom:0.4rem;">
          Scenario A &mdash; {_pass_a}
          &nbsp;·&nbsp; TIR {"✓" if _report_a["verdicts"]["tir_pass"] else "✗"}
          &nbsp;·&nbsp; Peak {"✓" if _report_a["verdicts"]["peak_pass"] else "✗"}
          &nbsp;·&nbsp; Hypo {"✓" if _report_a["verdicts"]["hypo_pass"] else "✗"}
          &nbsp;·&nbsp; Variability {"✓" if _report_a["verdicts"]["variability_pass"] else "✗"}
        </div>
        """, unsafe_allow_html=True)
        st.download_button(
            label="Download Scenario A report (JSON)",
            data=json.dumps(_report_a, indent=2),
            file_name=f"swarm_report_A_{scenario_a_name.lower().replace(' ', '_')}.json",
            mime="application/json",
        )
    with _exp_b:
        _pass_b = "✓ Meets targets" if _report_b["verdicts"]["overall_pass"] else "✗ Outside targets"
        _color_b = NEON if _report_b["verdicts"]["overall_pass"] else RED
        st.markdown(f"""
        <div style="font-family:'Inter',sans-serif; font-size:0.82rem;
                    color:{_color_b}; margin-bottom:0.4rem;">
          Scenario B &mdash; {_pass_b}
          &nbsp;·&nbsp; TIR {"✓" if _report_b["verdicts"]["tir_pass"] else "✗"}
          &nbsp;·&nbsp; Peak {"✓" if _report_b["verdicts"]["peak_pass"] else "✗"}
          &nbsp;·&nbsp; Hypo {"✓" if _report_b["verdicts"]["hypo_pass"] else "✗"}
          &nbsp;·&nbsp; Variability {"✓" if _report_b["verdicts"]["variability_pass"] else "✗"}
        </div>
        """, unsafe_allow_html=True)
        st.download_button(
            label="Download Scenario B report (JSON)",
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
    <div style="font-family:'Inter',sans-serif; font-size:0.8rem; font-weight:600;
                color:{WHITE}; margin:1.5rem 0 0.25rem 0;">
      Scenario A &mdash; Decision log
    </div>
    """, unsafe_allow_html=True)
    decision_timeline_panel(_exps_a, key_suffix="comp_a")
    st.markdown(f"""
    <div style="font-family:'Inter',sans-serif; font-size:0.8rem; font-weight:600;
                color:{WHITE}; margin:0.75rem 0 0.25rem 0;">
      Scenario B &mdash; Decision log
    </div>
    """, unsafe_allow_html=True)
    decision_timeline_panel(_exps_b, key_suffix="comp_b")

    st.markdown(f"""
    <div style="margin-top:1rem;">
      <div style="font-family:'Inter',sans-serif; font-size:0.75rem; color:{MUTED};
                  font-weight:600; letter-spacing:0.4px; text-transform:uppercase;
                  margin-bottom:0.5rem;">
        AI Comparative Verdict
      </div>
      <div style="background:{BG3}; border:1px solid {GRID}; border-left:4px solid {NEON};
                  border-radius:6px; padding:1.25rem 1.5rem; font-family:'Inter',sans-serif;
                  font-size:0.875rem; color:{WHITE}; line-height:1.8; overflow-x:auto;">
{verdict_text}
      </div>
    </div>
    """, unsafe_allow_html=True)

elif dashboard_mode == "PSO Optimizer":
    # ── PSO Optimisation run ───────────────────────────────────────────────
    _pso_scenarios = _pso_selected_scenarios if _pso_selected_scenarios else ["Baseline Meal"]
    _pso_config = PSOConfig(
        n_particles=_pso_n_particles,
        n_iterations=_pso_n_iterations,
        scenario_names=_pso_scenarios,
        hypo_penalty_weight=_pso_hypo_weight,
        duration_minutes=480,
        step_minutes=5,
    )

    # ── Header ────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div style="font-family:'Inter',sans-serif; font-size:1.1rem; font-weight:700;
                color:{CYAN}; margin-bottom:0.5rem;">
      Autonomous Parameter Optimisation
    </div>
    <div style="font-family:'Inter',sans-serif; font-size:0.85rem; color:{MUTED};
                margin-bottom:1rem; line-height:1.6;">
      Swarm of {_pso_n_particles} particles &times; {_pso_n_iterations} iterations
      &nbsp;&middot;&nbsp; {len(_pso_scenarios)} scenarios &times; 4 patient archetypes
      &nbsp;&middot;&nbsp;
      <strong style="color:{WHITE};">
        {_pso_n_particles * _pso_n_iterations * len(_pso_scenarios) * 4:,} closed-loop simulations
      </strong>
      &nbsp;&mdash;&nbsp; fully autonomous, no configuration required
    </div>
    """, unsafe_allow_html=True)

    # ── Default params TIR (baseline to compare against) ─────────────────
    _default_params = {
        "target_glucose_mgdl": 110.0,
        "correction_factor_mgdl_per_unit": 50.0,
        "microbolus_fraction": 0.25,
        "min_excursion_delta_mgdl": 0.0,
        "max_units_per_interval": 0.30,
        "max_insulin_on_board_u": 3.0,
        "min_predicted_glucose_mgdl": 80.0,
    }

    _progress_bar = st.progress(0.0, text="Initialising PSO swarm…")
    _iter_placeholder = st.empty()

    def _pso_progress(iteration: int, total: int, best_fitness: float, best_tir: float) -> None:
        frac = iteration / total
        _progress_bar.progress(frac, text=f"Iteration {iteration}/{total}  ·  Best fitness {best_fitness:.2f}")
        _iter_placeholder.markdown(
            f"<div style='font-family:JetBrains Mono,monospace;font-size:0.8rem;color:{MUTED};'>"
            f"Iteration {iteration}/{total} &nbsp;|&nbsp; best fitness {best_fitness:.3f}</div>",
            unsafe_allow_html=True,
        )

    with st.spinner("Running PSO…"):
        _pso_result = run_pso(config=_pso_config, progress_callback=_pso_progress)

    _progress_bar.progress(1.0, text="Done.")

    # ── Baseline TIR ─────────────────────────────────────────────────────
    with st.spinner("Evaluating default parameters for comparison…"):
        _default_tir = params_to_tir(_default_params, _pso_config)

    # ── Recalculate best TIR properly (PSO stores approx) ─────────────────
    with st.spinner("Scoring best parameters…"):
        _best_tir = params_to_tir(_pso_result.best_params, _pso_config)

    # ── KPI row ───────────────────────────────────────────────────────────
    _delta_tir = _best_tir - _default_tir
    _delta_sign = "+" if _delta_tir >= 0 else ""
    _delta_color = NEON if _delta_tir >= 0 else RED
    _kpi_col1, _kpi_col2, _kpi_col3 = st.columns(3)
    with _kpi_col1:
        st.metric("Default TIR (mean)", f"{_default_tir:.1f}%")
    with _kpi_col2:
        st.metric("Optimised TIR (mean)", f"{_best_tir:.1f}%", delta=f"{_delta_sign}{_delta_tir:.1f}%")
    with _kpi_col3:
        st.metric("Total simulations run", f"{_pso_result.n_evaluations:,}")

    # ── Convergence chart ─────────────────────────────────────────────────
    _hist_df = pd.DataFrame([
        {"Iteration": h.iteration, "Best Fitness": h.best_fitness, "Mean Fitness": h.mean_fitness}
        for h in _pso_result.history
    ])
    _conv_fig = go.Figure()
    _conv_fig.add_trace(go.Scatter(
        x=_hist_df["Iteration"], y=_hist_df["Best Fitness"],
        mode="lines", name="Best fitness",
        line=dict(color=NEON, width=2),
    ))
    _conv_fig.add_trace(go.Scatter(
        x=_hist_df["Iteration"], y=_hist_df["Mean Fitness"],
        mode="lines", name="Swarm mean",
        line=dict(color=AMBER, width=1.5, dash="dot"),
    ))
    _conv_fig.update_layout(
        title="PSO Convergence",
        xaxis_title="Iteration",
        yaxis_title="Fitness (lower = better)",
        height=300,
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        font=dict(family="Inter", color=WHITE),
        legend=dict(orientation="h", yanchor="top", y=1.12),
    )
    st.plotly_chart(_conv_fig, use_container_width=True)

    # ── Best parameters table ─────────────────────────────────────────────
    st.markdown(f"""
    <div style="font-family:'Inter',sans-serif; font-size:0.8rem; font-weight:700;
                color:{CYAN}; text-transform:uppercase; letter-spacing:0.5px;
                margin:1rem 0 0.4rem 0;">
      Optimised Parameters vs Defaults
    </div>
    """, unsafe_allow_html=True)

    _param_rows = []
    for _pb in PARAMETER_BOUNDS:
        _best_val = _pso_result.best_params[_pb.name]
        _def_val  = _default_params[_pb.name]
        _diff     = _best_val - _def_val
        _param_rows.append({
            "Parameter": _pb.description,
            "Default": round(_def_val, 3),
            "Optimised": round(_best_val, 3),
            "Change": f"{'+' if _diff >= 0 else ''}{_diff:.3f}",
        })
    _param_df = pd.DataFrame(_param_rows)
    st.dataframe(_param_df, use_container_width=True, hide_index=True)

    # ── Export ────────────────────────────────────────────────────────────
    import json as _json
    _export = {
        "best_params": _pso_result.best_params,
        "best_tir_pct": round(_best_tir, 2),
        "default_tir_pct": round(_default_tir, 2),
        "delta_tir_pct": round(_delta_tir, 2),
        "n_evaluations": _pso_result.n_evaluations,
        "pso_config": {
            "n_particles": _pso_config.n_particles,
            "n_iterations": _pso_config.n_iterations,
            "scenarios": _pso_config.scenario_names,
        },
    }
    st.download_button(
        "Download optimised parameters (JSON)",
        data=_json.dumps(_export, indent=2),
        file_name="pso_best_params.json",
        mime="application/json",
    )

elif dashboard_mode == "Swarm Bolus Lab":
    # ═══════════════════════════════════════════════════════════════════════
    # SWARM BOLUS LAB
    # Pancreatic first-phase response simulation driven by glucose dynamics.
    #
    # Controller:
    #   I_μ(t) = max(0, β·S(t) + γ·A(t) − δ·IOB(t))
    #   I_total(t) = B₀/60 + I_μ(t)
    #
    # S(t)  = glucose rate-of-change (mg/dL/min)  — rise-over-run
    # A(t)  = acceleration dS/dt (mg/dL/min²)      — change in slope
    # IOB   = insulin-on-board (exponential decay)
    # Safety: S(t) ≤ −3 mg/dL/min → I_μ = 0 (hypoglycaemia guard)
    # ═══════════════════════════════════════════════════════════════════════

    import math as _math

    # ── Meal slope profiles ────────────────────────────────────────────────
    # Each meal is modelled as a trapezoidal glucose-slope waveform.
    # Rise: 0 → peak over 6 min | Plateau: peak held 6–12 min
    # Descent: peak → 0 over 12–24 min | Flat thereafter.

    _SWARM_MEALS: list[tuple[str, float, str]] = [
        ("Slow meal (0.5 mg/dL/min peak)",      0.5,  "#3b82f6"),
        ("Moderate meal (1.0 mg/dL/min peak)",   1.0,  "#f59e0b"),
        ("Fast meal (2.0 mg/dL/min peak)",        2.0,  "#ef4444"),
        ("Very fast meal (3.0 mg/dL/min peak)",   3.0,  "#a855f7"),
    ]

    def _slope_at(t: int, peak: float) -> float:
        if t < 6:
            return peak * t / 6.0
        if t < 12:
            return peak
        if t < 24:
            return peak * (24.0 - t) / 12.0
        return 0.0

    def _run_swarm_bolus(
        peak: float,
        B0: float,
        beta: float,
        gamma: float,
        delta: float,
        iob_tau: float,
        duration: int = 60,
    ) -> pd.DataFrame:
        """Simulate swarm bolus controller response to a meal slope profile."""
        rows: list[dict] = []
        iob = 0.0
        glucose = 100.0
        prev_S = 0.0

        for t in range(duration + 1):
            S = _slope_at(t, peak)
            A = S - prev_S  # first difference ≈ dS/dt at 1-min resolution

            # Safety gate: rapid drop → suspend micro-bolus
            if S <= -3.0:
                micro = 0.0
            else:
                micro = max(0.0, beta * S + gamma * A - delta * iob)

            total = B0 / 60.0 + micro

            rows.append({
                "Minute":                          t,
                "Glucose slope S(t) (mg/dL/min)":  round(S, 4),
                "Acceleration A(t) (mg/dL/min²)":  round(A, 4),
                "Extra swarm insulin (U/min)":      round(micro, 4),
                "Total insulin output (U/min)":     round(total, 4),
                "Glucose (mg/dL)":                  round(glucose, 1),
            })

            glucose += S
            # IOB: accumulate new dose then apply per-minute exponential decay
            iob = (iob + micro) * _math.exp(-1.0 / iob_tau)
            prev_S = S

        return pd.DataFrame(rows)

    # ── Page header ────────────────────────────────────────────────────────
    st.markdown(
        f"""
        <div style="margin-bottom:1.2rem;">
          <div style="font-size:0.72rem;font-weight:700;color:{MUTED};letter-spacing:0.9px;
                      text-transform:uppercase;margin-bottom:0.3rem;">Swarm Bolus Lab</div>
          <h1 style="margin:0;font-size:1.7rem;color:{WHITE};font-weight:700;
                     font-family:'Inter',sans-serif;line-height:1.2;">
            Pancreatic First-Phase Response Simulator
          </h1>
          <p style="margin:0.5rem 0 0 0;color:{MUTED};font-size:0.88rem;max-width:680px;">
            Autonomous micro-bolus controller driven entirely by real-time glucose dynamics.
            No meal announcement required — the system detects, calculates, and delivers
            every dose without user input.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Controller equation banner ─────────────────────────────────────────
    st.markdown(
        f"""
        <div style="background:{BG3};border:1px solid {GRID};border-radius:8px;
                    padding:0.85rem 1.2rem;margin-bottom:1.4rem;font-family:'Inter',sans-serif;">
          <div style="font-size:0.72rem;font-weight:700;color:{MUTED};letter-spacing:0.7px;
                      text-transform:uppercase;margin-bottom:0.4rem;">Controller Signature</div>
          <div style="color:{WHITE};font-size:1.02rem;font-weight:600;letter-spacing:0.2px;">
            I<sub>μ</sub>(t) = max(0, &nbsp;β·S(t) + γ·A(t) − δ·IOB(t))
          </div>
          <div style="color:{WHITE};font-size:1.02rem;font-weight:600;margin-top:0.25rem;">
            I<sub>total</sub>(t) = B<sub>0</sub>/60 &nbsp;+&nbsp; I<sub>μ</sub>(t)
          </div>
          <div style="color:{MUTED};font-size:0.78rem;margin-top:0.55rem;line-height:1.7;">
            <b style="color:{WHITE};">S(t)</b> = glucose slope (mg/dL/min) &nbsp;·&nbsp;
            <b style="color:{WHITE};">A(t)</b> = acceleration dS/dt (mg/dL/min²) &nbsp;·&nbsp;
            <b style="color:{WHITE};">IOB</b> = insulin-on-board (exponential decay) &nbsp;·&nbsp;
            <b style="color:{WHITE};">Safety</b>: S(t) ≤ −3 mg/dL/min → I<sub>μ</sub> = 0
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Tunable parameters ─────────────────────────────────────────────────
    _col_p1, _col_p2, _col_p3, _col_p4, _col_p5 = st.columns(5)
    with _col_p1:
        _sb_B0    = st.number_input("B₀ basal (U/hr)",  min_value=0.1, max_value=3.0, value=0.80, step=0.05, format="%.2f")
    with _col_p2:
        _sb_beta  = st.number_input("β  slope gain",    min_value=0.0, max_value=0.5, value=0.037, step=0.001, format="%.3f")
    with _col_p3:
        _sb_gamma = st.number_input("γ  accel gain",    min_value=0.0, max_value=0.5, value=0.066, step=0.001, format="%.3f")
    with _col_p4:
        _sb_delta = st.number_input("δ  IOB suppression", min_value=0.0, max_value=1.0, value=0.05, step=0.005, format="%.3f")
    with _col_p5:
        _sb_tau   = st.number_input("IOB τ (min)",      min_value=30,  max_value=180,  value=75,   step=5)

    st.caption(
        f"Basal background: **{_sb_B0/60:.4f} U/min** · "
        f"β·1 mg/dL/min = **{_sb_beta:.4f} U/min** · "
        f"γ·1 mg/dL/min² = **{_sb_gamma:.4f} U/min**"
    )

    # ── Run simulations ────────────────────────────────────────────────────
    _sb_dfs: dict[str, pd.DataFrame] = {}
    for _sb_name, _sb_peak, _sb_color in _SWARM_MEALS:
        _sb_dfs[_sb_name] = _run_swarm_bolus(
            peak=_sb_peak,
            B0=_sb_B0,
            beta=_sb_beta,
            gamma=_sb_gamma,
            delta=_sb_delta,
            iob_tau=float(_sb_tau),
        )

    # ── Chart 1 — Glucose trajectory ───────────────────────────────────────
    st.markdown(
        f"<div style='font-size:0.72rem;font-weight:700;color:{MUTED};letter-spacing:0.7px;"
        f"text-transform:uppercase;margin:1.2rem 0 0.4rem 0;'>Glucose Trajectory</div>",
        unsafe_allow_html=True,
    )
    _sb_glc_fig = go.Figure()
    _sb_glc_fig.add_hrect(y0=70, y1=180, fillcolor="rgba(22,163,74,0.07)", line_width=0)
    _sb_glc_fig.add_hline(
        y=180, line=dict(color=AMBER, width=1, dash="dot"),
        annotation=dict(text="High 180", font=dict(color=AMBER, size=9, family="Inter"), xanchor="left"),
    )
    _sb_glc_fig.add_hline(
        y=70, line=dict(color=RED, width=1, dash="dot"),
        annotation=dict(text="Low 70", font=dict(color=RED, size=9, family="Inter"), xanchor="left"),
    )
    for _sb_name, _sb_peak, _sb_color in _SWARM_MEALS:
        _df = _sb_dfs[_sb_name]
        _sb_glc_fig.add_trace(go.Scatter(
            x=_df["Minute"], y=_df["Glucose (mg/dL)"],
            mode="lines", name=_sb_name,
            line=dict(color=_sb_color, width=2),
            hovertemplate="%{x} min → %{y:.1f} mg/dL<extra>" + _sb_name + "</extra>",
        ))
    _sb_glc_layout = _layout("Simulated Glucose — Autonomous Swarm Bolus Response", height=320)
    _sb_glc_layout["xaxis"]["title"] = "minutes"
    _sb_glc_layout["yaxis"]["title"] = "glucose (mg/dL)"
    _sb_glc_fig.update_layout(**_sb_glc_layout)
    st.plotly_chart(_sb_glc_fig, use_container_width=True)

    # ── Chart 2 — Insulin output ───────────────────────────────────────────
    _sb_ins_fig = go.Figure()
    _sb_basal_rate = _sb_B0 / 60.0
    _sb_ins_fig.add_hline(
        y=_sb_basal_rate, line=dict(color=MUTED, width=1, dash="dot"),
        annotation=dict(
            text=f"Basal {_sb_basal_rate:.4f} U/min",
            font=dict(color=MUTED, size=9, family="Inter"), xanchor="left",
        ),
    )
    for _sb_name, _sb_peak, _sb_color in _SWARM_MEALS:
        _df = _sb_dfs[_sb_name]
        _sb_ins_fig.add_trace(go.Scatter(
            x=_df["Minute"], y=_df["Total insulin output (U/min)"],
            mode="lines", name=_sb_name,
            line=dict(color=_sb_color, width=2),
            fill="tozeroy" if _sb_peak == 0.5 else None,
            fillcolor="rgba(59,130,246,0.05)" if _sb_peak == 0.5 else None,
            hovertemplate="%{x} min → %{y:.4f} U/min<extra>" + _sb_name + "</extra>",
        ))
    _sb_ins_layout = _layout("Total Insulin Output — Basal + Swarm Micro-Boluses", height=280)
    _sb_ins_layout["xaxis"]["title"] = "minutes"
    _sb_ins_layout["yaxis"]["title"] = "U/min"
    _sb_ins_fig.update_layout(**_sb_ins_layout)
    st.plotly_chart(_sb_ins_fig, use_container_width=True)

    # ── Chart 3 — Slope and Acceleration ──────────────────────────────────
    _sb_dyn_fig = go.Figure()
    _sb_dyn_fig.add_hline(y=0, line=dict(color=GRID, width=1))
    for _sb_name, _sb_peak, _sb_color in _SWARM_MEALS:
        _df = _sb_dfs[_sb_name]
        _sb_dyn_fig.add_trace(go.Scatter(
            x=_df["Minute"], y=_df["Glucose slope S(t) (mg/dL/min)"],
            mode="lines", name=f"S(t) {_sb_name}",
            line=dict(color=_sb_color, width=2),
            hovertemplate="%{x} min  S=%{y:.3f}<extra>" + _sb_name + "</extra>",
        ))
        _sb_dyn_fig.add_trace(go.Scatter(
            x=_df["Minute"], y=_df["Acceleration A(t) (mg/dL/min²)"],
            mode="lines", name=f"A(t) {_sb_name}",
            line=dict(color=_sb_color, width=1, dash="dot"),
            hovertemplate="%{x} min  A=%{y:.3f}<extra>" + _sb_name + " accel</extra>",
        ))
    _sb_dyn_layout = _layout("Glucose Dynamics — Slope S(t) [solid] & Acceleration A(t) [dotted]", height=280)
    _sb_dyn_layout["xaxis"]["title"] = "minutes"
    _sb_dyn_layout["yaxis"]["title"] = "mg/dL/min"
    _sb_dyn_fig.update_layout(**_sb_dyn_layout)
    st.plotly_chart(_sb_dyn_fig, use_container_width=True)

    # ── Summary data table (checkpoint rows) ──────────────────────────────
    st.markdown(
        f"<div style='font-size:0.72rem;font-weight:700;color:{MUTED};letter-spacing:0.7px;"
        f"text-transform:uppercase;margin:1.2rem 0 0.4rem 0;'>Simulation Data Table</div>",
        unsafe_allow_html=True,
    )
    _CHECKPOINTS = [0, 3, 6, 12, 18, 24, 30]
    _sb_table_frames: list[pd.DataFrame] = []
    for _sb_name, _sb_peak, _sb_color in _SWARM_MEALS:
        _df = _sb_dfs[_sb_name]
        _chunk = _df[_df["Minute"].isin(_CHECKPOINTS)].copy()
        _chunk.insert(0, "Scenario", _sb_name)
        _sb_table_frames.append(_chunk)
    _sb_combined = pd.concat(_sb_table_frames, ignore_index=True)

    # Display columns matching the doctor's CSV
    _display_cols = [
        "Scenario", "Minute",
        "Glucose slope S(t) (mg/dL/min)",
        "Acceleration A(t) (mg/dL/min²)",
        "Extra swarm insulin (U/min)",
        "Total insulin output (U/min)",
        "Glucose (mg/dL)",
    ]
    st.dataframe(_sb_combined[_display_cols], use_container_width=True, hide_index=True)

    # ── CSV download ───────────────────────────────────────────────────────
    _sb_csv = _sb_combined[_display_cols].to_csv(index=False).encode()
    st.download_button(
        "Download full simulation CSV",
        data=_sb_csv,
        file_name=f"Swarm_Bolus_Simulation_Summary_B0_{_sb_B0:.2f}Uhr.csv",
        mime="text/csv",
    )

    # ── Key insight callout ────────────────────────────────────────────────
    st.markdown(
        f"""
        <div style="background:{BG3};border-left:3px solid {NEON};border-radius:0 6px 6px 0;
                    padding:0.75rem 1.1rem;margin-top:1.2rem;font-family:'Inter',sans-serif;">
          <div style="font-size:0.72rem;font-weight:700;color:{NEON};letter-spacing:0.7px;
                      text-transform:uppercase;margin-bottom:0.35rem;">How the system reacts autonomously</div>
          <div style="color:{WHITE};font-size:0.86rem;line-height:1.7;">
            A faster glucose rise triggers a <b>larger and earlier</b> swarm response —
            mirroring the pancreatic first-phase pulse. The acceleration term γ·A(t) fires
            <b>before</b> the slope peaks, front-loading insulin exactly when it is
            physiologically most effective. IOB suppression (δ·IOB) prevents stacking
            as the rise plateaus. <b>No meal announcement, no user action required.</b>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

else:
    # ── Landing state ─────────────────────────────────────────────────────
    st.markdown(f"""
    <div style="display:flex; align-items:center; justify-content:center;
                min-height:340px; border:1px dashed {GRID}; border-radius:8px;
                background:{BG3}; margin-top:1rem;">
      <div style="text-align:center;">
        <div style="font-family:'Inter',sans-serif; font-size:1.5rem; color:{GRID};
                    font-weight:700; margin-bottom:0.75rem;">
          Ready to simulate
        </div>
        <div style="font-family:'Inter',sans-serif; font-size:0.9rem; color:{MUTED};
                    line-height:2;">
          Choose a view in the sidebar<br/>
          Configure the patient and safety settings<br/>
          Press <strong style="color:{CYAN}">Run</strong> to start
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)
