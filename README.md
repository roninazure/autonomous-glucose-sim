<div align="center">

<!-- ANIMATED HEADER BANNER -->
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://capsule-render.vercel.app/api?type=waving&color=0:0a0f1a,100:00ffb4&height=180&section=header&text=SWARM%20Bolus&fontSize=52&fontColor=ffffff&fontAlignY=38&animation=fadeIn&desc=Autonomous%20Glucose%20Intelligence%20%E2%80%94%20Closed-Loop%20Simulation%20Platform&descAlignY=58&descSize=14&descColor=00d48a">
  <source media="(prefers-color-scheme: light)" srcset="https://capsule-render.vercel.app/api?type=waving&color=0:e8f5f0,100:00d48a&height=180&section=header&text=SWARM%20Bolus&fontSize=52&fontColor=0a0f1a&fontAlignY=38&animation=fadeIn&desc=Autonomous%20Glucose%20Intelligence%20%E2%80%94%20Closed-Loop%20Simulation%20Platform&descAlignY=58&descSize=14&descColor=006644">
  <img alt="SWARM Bolus Banner" src="https://capsule-render.vercel.app/api?type=waving&color=0:0a0f1a,100:00ffb4&height=180&section=header&text=SWARM%20Bolus&fontSize=52&fontColor=ffffff&fontAlignY=38&animation=fadeIn&desc=Autonomous%20Glucose%20Intelligence%20%E2%80%94%20Closed-Loop%20Simulation%20Platform&descAlignY=58&descSize=14&descColor=00d48a" width="100%">
</picture>

<br/>

<!-- BADGES ROW 1: PROJECT STATUS -->
![Phase](https://img.shields.io/badge/Phase-3%20%E2%80%94%20Controller%20Prototype-00ffb4?style=flat-square&labelColor=0d1117)
![Status](https://img.shields.io/badge/Status-Active%20Development-00d48a?style=flat-square&labelColor=0d1117)
![Boundary](https://img.shields.io/badge/%E2%9A%A0%EF%B8%8F%20Boundary-Simulation%20Only-ff4d6d?style=flat-square&labelColor=0d1117)

<!-- BADGES ROW 2: TECH -->
![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab?style=flat-square&logo=python&logoColor=white&labelColor=0d1117)
![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-ff4b4b?style=flat-square&logo=streamlit&logoColor=white&labelColor=0d1117)
![Tests](https://img.shields.io/badge/Tests-Passing-00d48a?style=flat-square&logo=pytest&logoColor=white&labelColor=0d1117)
![License](https://img.shields.io/badge/License-Research%20Only-6b7784?style=flat-square&labelColor=0d1117)

<br/>
<br/>

> **Simulation-first platform for building an autonomous insulin dosing engine.**  
> Iterate on glucose dynamics, decision logic, and safety constraints — in a controlled, non-clinical environment.

<br/>

</div>

---

## ⬡ &nbsp;Safety Boundary

<table>
<tr>
<td>

This is **simulation-only research software**. Nothing in this repository:

- ✕ &nbsp;Controls real insulin pumps
- ✕ &nbsp;Interfaces with CGM hardware
- ✕ &nbsp;Provides medical advice or treatment
- ✕ &nbsp;Delivers insulin to any person

All outputs are synthetic. No clinical deployment before full regulatory validation.

</td>
</tr>
</table>

---

## &nbsp;What This Is

SWARM Bolus is a **closed-loop simulation stack** that mirrors a real AID system architecture exactly — with every component replaceable by its hardware counterpart once pre-clinical validation is complete.

The core evaluation primitive is **Scenario A vs Scenario B**: same algorithm, same constraints, different conditions. This enables controlled, reproducible testing of meal impact, fasting response, and glucose excursion behavior.

---

## &nbsp;Closed-Loop Architecture

```
┌─────────────────────────────────────────────────┐
│                  Scenario Input                  │
│        (meal events · patient params · horizon)  │
└─────────────────────┬───────────────────────────┘
                      │
                      ▼
              ┌───────────────┐
              │  Physiology   │  ← Bergman 3-compartment model
              │    Engine     │     glucose–insulin dynamics
              └───────┬───────┘
                      │ ground-truth glucose
                      ▼
              ┌───────────────┐
              │  CGM Sensor   │  ← Gaussian noise · interstitial lag
              │    Model      │     calibration drift
              └───────┬───────┘
                      │ sensor readings
                      ▼
              ┌───────────────┐
              │  Controller   │  ← Rule-based + ML-ready
              │ Decision Eng. │     bolus / basal recommendations
              └───────┬───────┘
                      │ recommended dose
                      ▼
         ┌────────────────────────┐
         │  ⬡  Safety Layer  ⬡   │  ← IOB tracking · hypo prediction
         │  [CRITICAL PATH]       │     hard clamps · override logic
         └────────────┬───────────┘
                      │ safe dose
                      ▼
              ┌───────────────┐
              │    Pump       │  ← Rate limits · delivery constraints
              │  Abstraction  │     infusion modeling
              └───────┬───────┘
                      │
                      ▼
        ┌──────────────────────────┐
        │  Evaluation + Viz Layer  │  ← Clinical metrics · AI verdict
        │  Streamlit Dashboard     │     scenario comparison report
        └──────────────────────────┘
```

---

## &nbsp;Clinical Metrics

Every simulation run emits a full clinical-grade metrics payload:

| Metric | Target | Description |
|:--|:--|:--|
| `time_in_range` | **> 70%** | % of readings 70–180 mg/dL *(ADA/EASD standard)* |
| `cgm_mean` | 80–140 | Mean sensor glucose across simulation window |
| `cgm_peak` | < 250 | Maximum excursion — hyperglycemia severity |
| `time_above_250` | < 1% | Severe hyperglycemia exposure (minutes) |
| `glucose_sd` | < 36 | Glycemic variability — lower = more stable control |
| `insulin_recommended` | — | Raw controller output before safety processing |
| `insulin_delivered` | — | Actual delivery post safety layer + pump model |
| `blocked_decisions` | → 0 | Controller requests fully rejected by safety |
| `clipped_decisions` | → low | Controller requests reduced *(not blocked)* by safety |

The system generates a **plain-English AI comparative verdict** covering spike severity, insulin demand delta, safety intervention frequency, and overall control quality.

---

## &nbsp;Quickstart

```bash
# clone & install
git clone https://github.com/scottsteele/swarm-bolus
cd swarm-bolus && pip install -r requirements.txt
```

```bash
# run simulation engine
PYTHONPATH=src python -m ags.simulation.run

# run controller
PYTHONPATH=src python -m ags.controller.run

# launch dashboard
streamlit run app.py

# test suite
PYTHONPATH=src pytest -q
```

---

## &nbsp;Project Structure

```
src/
└── ags/
    ├── simulation/    ← physiology engine · CGM model · scenario runner
    ├── controller/    ← decision engine · insulin recommendation logic
    ├── safety/        ← hard constraints · IOB tracking · hypo prediction
    ├── pump/          ← delivery abstraction · rate modeling
    ├── evaluation/    ← metrics · AI verdict · clinical report
    └── scenarios/     ← meal presets · fasting · extremes

tests/
docs/
experiments/
app.py             ← Streamlit dashboard entrypoint
```

---

## &nbsp;FDA Pathway Strategy

Built from day one for a future **Software as a Medical Device (SaMD)** classification — likely **Class II** via FDA 510(k) or De Novo, comparable to existing hybrid closed-loop AID systems.

**Required evolution toward clinical use:**

<details>
<summary><strong>01 &nbsp;·&nbsp; Algorithm Validation</strong></summary>
<br/>

- Large-scale simulation testing across diverse patient profiles
- Edge-case coverage: hypo/hyper extremes, missed meals, pump occlusions
- Cross-scenario repeatability and statistical robustness

</details>

<details>
<summary><strong>02 &nbsp;·&nbsp; Safety Layer Maturity</strong></summary>
<br/>

- Insulin-on-board (IOB) modeling — complete
- Predictive hypoglycemia suspension logic
- Hard safety constraint architecture
- Clinician override logging and auditability

</details>

<details>
<summary><strong>03 &nbsp;·&nbsp; Human Factors & Explainability</strong></summary>
<br/>

- Decision explainability layer for every controller recommendation
- Clinician-readable output format
- Full auditability of safety interventions

</details>

<details>
<summary><strong>04 &nbsp;·&nbsp; Clinical Evidence</strong></summary>
<br/>

- Retrospective dataset validation against real CGM traces
- Controlled simulation pilot studies
- Outcome comparison vs. standard-of-care heuristics

</details>

<details>
<summary><strong>05 &nbsp;·&nbsp; Regulatory Filing</strong></summary>
<br/>

- FDA 510(k) or De Novo pathway (predicated on final claims)
- Pre-submission meeting alignment
- Comparable device analysis (existing AID systems: Omnipod 5, Control-IQ, etc.)

</details>

---

## &nbsp;The Thesis

> *Build the decision engine first. Validate it in simulation. Then deploy it into reality.*

Insulin dosing is one of the most consequential, error-prone, and cognitively demanding tasks in chronic disease management. SWARM Bolus is the **pre-clinical algorithm validation layer** for a future fully autonomous insulin dosing brain — one that integrates with any CGM and pump, adapts per patient, continuously learns, and operates safely inside regulatory frameworks.

**One-line pitch:** We are building the decision engine that powers the future of autonomous insulin delivery — starting in simulation, validated before reality.

---

## &nbsp;Build Status

| Component | Status |
|:--|:--|
| Architecture | ✅ Complete |
| Simulation Engine | ✅ Complete |
| Controller (Phase 3) | ✅ Complete |
| Safety Layer | 🟡 In Progress |
| Pump Abstraction | 🟡 In Progress |
| Evaluation Engine | 🟡 In Progress |
| Risk Scoring System | ⬜ Roadmap |
| Dataset Validation | ⬜ Roadmap |
| Clinician-in-the-Loop | ⬜ Roadmap |

---

<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://capsule-render.vercel.app/api?type=waving&color=0:00ffb4,100:0a0f1a&height=100&section=footer&reversal=false">
  <source media="(prefers-color-scheme: light)" srcset="https://capsule-render.vercel.app/api?type=waving&color=0:00d48a,100:e8f5f0&height=100&section=footer&reversal=false">
  <img alt="footer" src="https://capsule-render.vercel.app/api?type=waving&color=0:00ffb4,100:0a0f1a&height=100&section=footer" width="100%">
</picture>

<sub><strong>SWARM Bolus</strong> &nbsp;·&nbsp; simulation-first &nbsp;·&nbsp; safety-obsessed &nbsp;·&nbsp; clinically rigorous</sub>

</div>
````
