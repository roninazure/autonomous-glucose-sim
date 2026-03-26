<div align="center">

![header](assets/header.svg)

</div>

<div align="center">

![Build Status](assets/status.svg)

</div>

<div align="center">

![Phase](https://img.shields.io/badge/Phase_4-Clinical_Evidence-39ff14?style=flat-square&labelColor=050a06&color=39ff14)
![Status](https://img.shields.io/badge/Status-Active_Development-39ff14?style=flat-square&labelColor=050a06)
![Boundary](https://img.shields.io/badge/⬡_Boundary-Simulation_Only-ff4d6d?style=flat-square&labelColor=050a06)
![Python](https://img.shields.io/badge/Python-3.10+-39ff14?style=flat-square&logo=python&logoColor=39ff14&labelColor=050a06)
![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-ff4d6d?style=flat-square&logo=streamlit&logoColor=white&labelColor=050a06)
![Tests](https://img.shields.io/badge/Tests-247_passing-39ff14?style=flat-square&logo=pytest&logoColor=39ff14&labelColor=050a06)

</div>

---

<div align="center">

*Autonomous insulin delivery — CGM → Controller → Safety → Pump → Patient, no human intervention.*<br/>
*Bergman physiology · 7-gate safety layer · cause-aware dosing · IOB tracking · ADA/EASD clinical metrics*<br/>
*Validate the algorithm in simulation before deployment into reality.*

</div>

---

## ⬡  Safety Boundary

> [!CAUTION]
> This is **simulation-only research software**. Nothing in this repository controls real insulin pumps, interfaces with CGM hardware, provides medical advice, or delivers treatment to any person. All outputs are synthetic. No clinical deployment before full regulatory validation.

---

## What This Is

SWARM Bolus is a **closed-loop simulation stack** that mirrors a real AID system architecture exactly — with every component replaceable by its hardware counterpart once pre-clinical validation is complete.

The dashboard has two modes:

| Mode | Description |
|:--|:--|
| **Clinical Review** | Runs all 8 evaluation scenarios automatically, scores each against ADA/EASD targets (TIR ≥70%, peak <250 mg/dL, 0 hypo steps). One-click verdict table + charts + CSV export. |
| **Closed Loop Demo** | **The artificial pancreas loop made visible.** Select a scenario, watch the autonomous controller manage glucose with zero manual input. Glucose trajectory, insulin delivery bars, and full decision log. |

---

## Architecture

<div align="center">

![architecture](assets/architecture.svg)

</div>

| Component | Role |
|:--|:--|
| **Physiology Engine** | Bergman 3-compartment model. Produces ground-truth glucose from patient params + meal events |
| **CGM Sensor Model** | Gaussian noise, interstitial lag, calibration drift. Outputs 1-min or 5-min sensor readings |
| **Controller** | Rule-based + ML-ready decision engine. Recommends bolus / basal adjustments. RoR-tiered micro-bolus. |
| **Safety Layer** | IOB tracking, hypo prediction, stateful suspension logic, hard clamps. Blocks or clips unsafe dosing |
| **Pump Abstraction** | Delivery rate limits, dual-wave (split) bolus state machine, quantisation |
| **Evaluation Engine** | Clinical metrics, ADA/EASD scoring, per-scenario verdict, Streamlit dashboard |
| **Closed-Loop Runner** | `run_evaluation` — true feedback loop: each pump delivery is fed back into `advance_physiology` so delivered insulin changes subsequent glucose |

---

## Algorithm Innovations

Seven algorithm innovations, each clinically motivated:

### 1 · 5-Minute CGM Loop
The controller runs at **5-minute timesteps**, matching standard CGM cadence. All detection thresholds are expressed in **mg/dL/min** so behaviour is physiologically consistent.

### 2 · Dual-Wave (Split) Bolus
Mimics a **combo/dual-wave bolus** as used on insulin pumps today. Instead of one atomic dose, a correction is split into:
- **Immediate portion** (e.g. ⅓ of total) — delivered now, hits the initial glucose spike in 5–10 min
- **Extended tail** (remaining ⅔) — dripped evenly over a configurable window (default 20 min)

*Doctor's example: 30g carbs → 6U total → 2U quick + 4U slowly.*

### 3 · Rate-of-Rise Tiered Micro-Bolus
The controller scales its micro-bolus fraction **dynamically based on the observed rate of rise** (mg/dL/min):

| Rate | Action |
|:--|:--|
| < 1.0 mg/dL/min | No micro-bolus (flat / sensor noise) |
| 1–2 mg/dL/min | 25% of full correction |
| 2–3 mg/dL/min | 50% of full correction |
| ≥ 3.0 mg/dL/min | 100% (aggressive spike — full correction) |

### 4 · Weight-Based ISF (1700 Rule)
The Insulin Sensitivity Factor is estimated from body weight using the 1700 Rule:

```
ISF ≈ 1700 ÷ TDD       where  TDD ≈ weight_kg × 0.55
```

For a 70 kg patient: TDD ≈ 38.5 U/day → ISF ≈ 44 mg/dL/U.

### 5 · Pre-Bolus De-Duplication (Cause-Aware Dosing)
When a meal is detected at ONSET, the controller fires a **single pre-bolus** that covers the leading edge of carb absorption (~40% of estimated carb impact). Subsequent ONSET steps — which would previously re-fire the pre-bolus on every CGM reading — are suppressed by a persistent state flag that resets only after 20 consecutive minutes of no meal signal. Result: one surgical pre-dose per meal, not a repeated stack.

| Cause | Strategy |
|:--|:--|
| Meal ONSET | Pre-bolus (once per meal) + adaptive micro-bolus loop |
| Meal PEAK | RoR-tiered micro-bolus (25–100% of correction) |
| Basal drift | 25%-fraction micro-bolus — accumulates against slow creep |
| Post-hypo rebound | 10%-fraction touch — allows natural stabilisation first |

### 6 · Online ISF Learning (Dose → Response Feedback)
After every significant insulin delivery, the system **records the glucose level at time of delivery** and waits 60 minutes. It then measures the actual glucose drop and adds an `(units, drop)` observation to a rolling 12-entry window. The recommender blends this empirical evidence with the rate-of-rise estimate:

```
effective_ISF = 0.6 × RoR_estimated + 0.4 × observed_from_history
```

The longer the system runs with a patient, the more precisely it knows their real ISF — converging from a generic lookup table toward patient-specific evidence. Zero configuration required.

### 7 · Basal Drift Detection (Fixed)
The basal drift detector uses a 60-minute sliding window and requires ≥6 CGM readings for a reliable R² linearity test. The CGM history window in the runner was previously set to 5 — **one reading short**, meaning drift detection never fired in production. Fixed to 12 readings (matching the detector's full look-back). A new **Sustained Basal Deficit** simulation scenario (0.30 mg/dL/min constant drift, no meal) provides the canonical end-to-end validation path for the `BASAL_DRIFT` detection and correction loop.

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
| `blocked_decisions` | → 0 | Requests fully rejected by safety layer |
| `clipped_decisions` | → low | Requests reduced (not blocked) by safety layer |

---

## Decision Explainability

Every step in every run can be expanded into a full **Decision Timeline** showing what the controller saw and why it acted:

```
┌─ t = 35 min ──────────────────────────────────────────
  cgm            : 191.0 mg/dL
  trend           : ↑  +1.60 mg/dL/min
  predicted +30   : 239.2 mg/dL
  IOB             : 0.000 U
├─ controller ──────────────────────────────────────────
  recommended     : 0.579 U
  reason          : predicted glucose above target
├─ safety ──────────────────────────────────────────────
  gate            : allowed ✓
  reason          : recommendation allowed
  status          : allowed
  final units     : 0.579 U
├─ delivery ────────────────────────────────────────────
  delivered       : 0.579 U
├─ narrative ───────────────────────────────────────────
  CGM 191 mg/dL (↑ +1.6/min) → pred 239 mg/dL at t+30 —
  delivered 0.58 U (full recommendation: 0.58 U).
└──────────────────────────────────────────────────────
```

Seven named safety gates — colour-coded in the timeline table:

| Gate | When it fires |
|:--|:--|
| `no_dose` | Controller recommended 0 U (glucose ≤ target) |
| `trend_confirmation` | Rising trend not yet confirmed over two consecutive steps |
| `hypo_guard` | Predicted glucose at t+30 < safety threshold |
| `iob_guard` | Active insulin on board exceeds the stacking limit |
| `max_interval_cap` | Recommendation clipped to per-interval maximum |
| `allowed ✓` | Full recommendation passed all gates and was delivered |
| `SUSPENSION` | Stateful hypo suspension is active (holds until confirmed recovery) |

---

## Closed Loop Demo

Select **⬡ Closed Loop Demo** in the dashboard sidebar to see the full artificial pancreas loop:

```
CGM reading → controller → safety check → pump delivery
     ↑                                          ↓
  next glucose ← advance_physiology(dose) ←←←←←←
```

Every green data point on the chart was produced by the algorithm delivering insulin that **actually suppressed the glucose** — no pre-programming, no manual override.

| Scenario | No treatment | Autonomous control |
|:--|:--|:--|
| Baseline Meal (45g carbs) | 247 mg/dL peak | 200 mg/dL · 3.8 U delivered |
| Dawn Phenomenon (drift) | Unchecked rise | 100% time in range · 0.7 U |
| Missed Bolus (75g carbs) | 305+ mg/dL | Controller detects & corrects |

**What the demo screen shows:**
- Glucose trajectory chart — CGM readings across the full simulation window
- Insulin delivery bars — every autonomous dose, timestamp and amount
- Four metric cards — TIR %, peak glucose, hypo steps, total insulin
- Expandable decision log — every step: CGM, cause, recommended, safety gate, delivered, IOB

---

## Quickstart

```bash
# clone & install
git clone https://github.com/roninazure/autonomous-glucose-sim
cd autonomous-glucose-sim && pip install -r requirements.txt
```

```bash
# simulation engine
PYTHONPATH=src python -m ags.simulation.run

# controller
PYTHONPATH=src python -m ags.controller.run

# streamlit dashboard
PYTHONPATH=src streamlit run app.py

# test suite
PYTHONPATH=src pytest -q
```

---

## Structure

```
src/
└── ags/
    ├── simulation/       <- physiology engine · CGM model · scenario runner
    ├── controller/       <- decision engine · insulin recommendation logic
    ├── safety/           <- hard constraints · IOB tracking · hypo prediction
    ├── pump/             <- delivery abstraction · rate modeling
    └── evaluation/       <- metrics · ADA/EASD scoring · clinical report

tests/                    <- 247 tests, all passing
docs/                     <- quick_reference.md · user_guide.md
app.py                    <- Streamlit dashboard (Clinical Review · Closed Loop Demo)
```

---

## FDA Pathway Strategy

Built from day one for a future **Software as a Medical Device (SaMD)** classification — likely **Class II** via FDA 510(k) or De Novo, comparable to existing hybrid closed-loop AID systems (Omnipod 5, Control-IQ).

<details>
<summary><b>01 · Algorithm Validation ✓</b></summary>
<br/>
- 8 evaluation scenarios covering hypo, hyper, drift, exercise, overnight, stacked corrections<br/>
- ADA/EASD pass criteria enforced: TIR ≥70%, peak <250 mg/dL, 0 hypo steps<br/>
- 247 automated tests, all passing<br/>
- Cause-aware dosing: MEAL / BASAL_DRIFT / REBOUND / MIXED / FLAT detection + distinct strategies
</details>

<details>
<summary><b>02 · Safety Layer Maturity ✓</b></summary>
<br/>
- Insulin-on-board (IOB) modeling with 2-compartment PK/PD<br/>
- Stateful predictive hypoglycemia suspension with configurable resume margin<br/>
- 7 independent safety gates: no-dose, trend confirmation, hypo guard, IOB guard, interval cap, allowed ✓, SUSPENSION<br/>
- Full auditability of every safety intervention via named gate identifiers
</details>

<details>
<summary><b>03 · Human Factors and Explainability ✓</b></summary>
<br/>
- Per-step <code>DecisionExplanation</code> capturing the full controller-safety-pump trace<br/>
- 7 stable gate identifiers with colour-coded dashboard timeline<br/>
- Plain-English narrative sentence per step (clinician-readable, no code required)<br/>
- Step drill-down: any timestep expandable into a full monospace audit card
</details>

<details>
<summary><b>04 · Clinical Evidence ✓</b></summary>
<br/>
- **Closed-loop demo** with real physiological feedback — delivered insulin changes the glucose trajectory<br/>
- **Clinical Review** mode: one-click full battery with ADA/EASD verdict table and CSV export<br/>
- 8 scenarios validated: baseline meal, dawn phenomenon, overnight stability, stacked corrections, rapid drop, exercise, missed bolus, sustained basal deficit
</details>

<details>
<summary><b>05 · Regulatory Filing</b></summary>
<br/>
- FDA 510(k) or De Novo pathway (predicated on final claims)<br/>
- Pre-submission meeting alignment<br/>
- Comparable device analysis vs. existing AID systems<br/>
- Design History File generation (in progress)
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
