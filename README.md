<div align="center">

![header](assets/header.svg)

</div>

<div align="center">

![Phase](https://img.shields.io/badge/Phase_3-Controller_Prototype-39ff14?style=flat-square&labelColor=050a06&color=39ff14)
![Status](https://img.shields.io/badge/Status-Active_Development-39ff14?style=flat-square&labelColor=050a06)
![Boundary](https://img.shields.io/badge/⬡_Boundary-Simulation_Only-ff4d6d?style=flat-square&labelColor=050a06)
![Python](https://img.shields.io/badge/Python-3.10+-39ff14?style=flat-square&logo=python&logoColor=39ff14&labelColor=050a06)
![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-ff4d6d?style=flat-square&logo=streamlit&logoColor=white&labelColor=050a06)
![Tests](https://img.shields.io/badge/Tests-Passing-39ff14?style=flat-square&logo=pytest&logoColor=39ff14&labelColor=050a06)

</div>

---

<div align="center">

*Simulation-first platform for building an autonomous insulin dosing engine.*<br/>
*Iterate on glucose dynamics, decision logic, and safety constraints — in a controlled, non-clinical environment.*

</div>

---

## ⬡  Safety Boundary

> [!CAUTION]
> This is **simulation-only research software**. Nothing in this repository controls real insulin pumps, interfaces with CGM hardware, provides medical advice, or delivers treatment to any person. All outputs are synthetic. No clinical deployment before full regulatory validation.

---

## What This Is

SWARM Bolus is a **closed-loop simulation stack** that mirrors a real AID system architecture exactly — with every component replaceable by its hardware counterpart once pre-clinical validation is complete.

The core evaluation primitive is **Scenario A vs B**: same algorithm, same safety constraints, different conditions. This enables controlled, reproducible testing of meal impact, fasting response, and extreme glucose excursion behavior. Each run produces a full clinical-grade metrics payload plus an AI-generated plain-English verdict.

---

## Architecture

<div align="center">

![architecture](assets/architecture.svg)

</div>

| Component | Role |
|:--|:--|
| **Physiology Engine** | Bergman 3-compartment model. Produces ground-truth glucose from patient params + meal events |
| **CGM Sensor Model** | Gaussian noise, interstitial lag, calibration drift. Outputs realistic 5-min sensor readings |
| **Controller** | Rule-based + ML-ready decision engine. Recommends bolus / basal adjustments |
| **Safety Layer** | IOB tracking, hypo prediction, hard clamps, override logic. Blocks or clips unsafe dosing |
| **Pump Abstraction** | Delivery rate limits, infusion modeling, occlusion simulation |
| **Evaluation Engine** | Clinical metrics, scenario comparison, AI-generated verdict, Streamlit dashboard |

---

## Clinical Metrics

Every simulation run emits a full clinical-grade metrics payload:

| Metric | Target | Description |
|:--|:--:|:--|
| `time_in_range` | **> 70%** | % of readings 70-180 mg/dL (ADA/EASD standard) |
| `cgm_mean` | 80-140 | Mean sensor glucose across window |
| `cgm_peak` | < 250 | Maximum excursion — hyperglycemia severity |
| `time_above_250` | < 1% | Severe hyperglycemia exposure |
| `glucose_sd` | < 36 | Glycemic variability — lower = more stable |
| `insulin_recommended` | — | Raw controller output pre-safety |
| `insulin_delivered` | — | Actual delivery post safety + pump model |
| `blocked_decisions` | -> 0 | Requests fully rejected by safety layer |
| `clipped_decisions` | -> low | Requests reduced (not blocked) by safety layer |

---

## Quickstart

\`\`\`bash
# clone & install
git clone https://github.com/roninazure/autonomous-glucose-sim
cd autonomous-glucose-sim && pip install -r requirements.txt
\`\`\`

\`\`\`bash
# simulation engine
PYTHONPATH=src python -m ags.simulation.run

# controller
PYTHONPATH=src python -m ags.controller.run

# streamlit dashboard
streamlit run app.py

# test suite
PYTHONPATH=src pytest -q
\`\`\`

---

## Structure

\`\`\`
src/
└── ags/
    ├── simulation/    <- physiology engine · CGM model · scenario runner
    ├── controller/    <- decision engine · insulin recommendation logic
    ├── safety/        <- hard constraints · IOB tracking · hypo prediction
    ├── pump/          <- delivery abstraction · rate modeling
    ├── evaluation/    <- metrics · AI verdict · clinical report
    └── scenarios/     <- meal presets · fasting · extremes

tests/
docs/
experiments/
app.py             <- Streamlit dashboard entrypoint
\`\`\`

---

## FDA Pathway Strategy

Built from day one for a future **Software as a Medical Device (SaMD)** classification — likely **Class II** via FDA 510(k) or De Novo, comparable to existing hybrid closed-loop AID systems (Omnipod 5, Control-IQ).

<details>
<summary><b>01 · Algorithm Validation</b></summary>
<br/>
- Large-scale simulation testing across diverse patient profiles<br/>
- Edge-case coverage: hypo/hyper extremes, missed meals, pump occlusions<br/>
- Cross-scenario repeatability and statistical robustness
</details>

<details>
<summary><b>02 · Safety Layer Maturity</b></summary>
<br/>
- Insulin-on-board (IOB) modeling<br/>
- Predictive hypoglycemia suspension logic<br/>
- Hard safety constraint architecture<br/>
- Full auditability of every safety intervention
</details>

<details>
<summary><b>03 · Human Factors and Explainability</b></summary>
<br/>
- Decision explainability for every controller recommendation<br/>
- Clinician-readable output format<br/>
- Clinician-in-the-loop testing protocol
</details>

<details>
<summary><b>04 · Clinical Evidence</b></summary>
<br/>
- Retrospective validation against real CGM traces<br/>
- Controlled simulation pilot studies<br/>
- Outcome comparison vs. standard-of-care heuristics
</details>

<details>
<summary><b>05 · Regulatory Filing</b></summary>
<br/>
- FDA 510(k) or De Novo pathway (predicated on final claims)<br/>
- Pre-submission meeting alignment<br/>
- Comparable device analysis vs. existing AID systems
</details>

---

## Build Status

<div align="center">

![status](assets/status.svg)

</div>

---

## The Thesis

> *Build the decision engine first. Validate it in simulation. Then deploy it into reality.*

Insulin dosing is one of the most consequential, error-prone, and cognitively demanding tasks in chronic disease management. SWARM Bolus is the pre-clinical algorithm validation layer for a future fully autonomous insulin dosing brain — one that integrates with any CGM and pump, adapts per patient, continuously learns, and operates safely inside regulatory frameworks.

**One-line pitch:** We are building the decision engine that powers the future of autonomous insulin delivery — starting in simulation, validated before reality.

---

<div align="center">
<sub><b>SWARM Bolus</b> · simulation-first · safety-obsessed · clinically rigorous</sub>
</div>
