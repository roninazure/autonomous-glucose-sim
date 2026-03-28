<div align="center">

![header](https://roninazure.github.io/autonomous-glucose-sim/assets/header.svg)

</div>

<div align="center">

![Build Status](https://roninazure.github.io/autonomous-glucose-sim/assets/status.svg)

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
*Bergman physiology · 8-gate safety layer · 3-state arming gate · cause-aware dosing · IOB tracking · ADA/EASD clinical metrics*<br/>
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
| **Clinical Review** | Runs all 9 evaluation scenarios automatically, scores each against ADA/EASD targets (TIR ≥70%, peak <250 mg/dL, 0 hypo steps). One-click verdict table + charts + CSV export. |
| **Closed Loop Demo** | **The artificial pancreas loop made visible.** Select a scenario, watch the autonomous controller manage glucose with zero manual input. Glucose trajectory, insulin delivery bars, and full decision log. |

---

## Architecture

<div align="center">

![architecture](https://roninazure.github.io/autonomous-glucose-sim/assets/architecture.svg)

</div>

| Component | Role |
|:--|:--|
| **Physiology Engine** | Bergman 3-compartment model. Produces ground-truth glucose from patient params + meal events |
| **CGM Sensor Model** | Gaussian noise, interstitial lag, calibration drift. Outputs 5-min sensor readings |
| **Controller** | Rule-based + ML-ready decision engine. Recommends bolus / basal adjustments. RoR-tiered micro-bolus. |
| **Safety Layer** | 3-state arming gate (monitor → armed → firing), IOB tracking, hypo prediction, stateful suspension, hard clamps. 8 gates in series at every step |
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

### 8 · 3-State Arming Gate (Doctor-Specified)
Runs as **Gate 0**, before all other safety checks. Ensures the controller only delivers insulin when a genuine glucose excursion is confirmed — not transient sensor noise or a single rising CGM tick.

| Phase | Slope | Duration | Action |
|:--|:--|:--|:--|
| **MONITORING** | 0.3–0.5 mg/dL/min | — | Watch only, no dose |
| **ARMED** | ≥ 0.5 mg/dL/min | 1 step (5 min) | Primed, no dose yet |
| **FIRING** | ≥ 0.7 mg/dL/min | 2 steps (10 min) **or** cumulative rise ≥ 5 mg/dL | Dose allowed |
| **HOLD → reset** | < 0.3, any negative slope, or drop > 3 mg/dL/min | any | Return to MONITORING |

Acceleration reversal while FIRING also triggers a HOLD reset. The gate resets to MONITORING on hypo suspension entry and after hypo recovery — the system must re-confirm a genuine rise before dosing again.

The arming phase (`MONITORING` / `ARMED` / `FIRING`) is tracked per-step and visible in the **Arm Phase** column of the Controller Decision Log.

---

## Clinical Metrics

Every simulation run emits a full clinical-grade metrics payload:

| Metric | Target | Description |
|:--|:--:|:--|
| `percent_time_in_range` | **≥ 70%** | % of readings 70–180 mg/dL (ADA/EASD standard) |
| `average_cgm_glucose_mgdl` | 80–140 | Mean sensor glucose across window |
| `peak_cgm_glucose_mgdl` | < 250 | Maximum excursion — hyperglycemia severity |
| `time_above_250_steps` | → 0 | Steps in severe hyperglycemia |
| `glucose_variability_sd_mgdl` | < 36 | Glycemic variability — lower = more stable |
| `total_recommended_insulin_u` | — | Raw controller output pre-safety |
| `total_insulin_delivered_u` | — | Actual delivery post safety + pump model |
| `blocked_decisions` | → 0 | Requests fully rejected by safety layer |
| `clipped_decisions` | → 0 | Requests reduced (not blocked) by safety layer |
| `time_suspended_steps` | → 0 | Steps where pump was suspended due to predicted hypo |

---

## Decision Explainability

Every step is logged in the **Controller Decision Log** (expandable in the Closed Loop Demo). Columns per timestep:

| Column | Description |
|:--|:--|
| `t (min)` | Simulation time |
| `CGM (mg/dL)` | Sensor glucose reading |
| `Arm Phase` | Arming gate state: MONITORING / ARMED / FIRING |
| `Cause` | Autonomous classification: MEAL / BASAL_DRIFT / REBOUND / MIXED / FLAT |
| `Recommended (U)` | Raw controller output before safety |
| `Safety` | Safety gate that fired |
| `Delivered (U)` | Actual insulin delivered by pump |
| `IOB (U)` | Insulin on board at this timestep |
| `Suspended` | Whether pump suspension was active |

Eight safety gates — each returns one of three statuses (`blocked`, `clipped`, `allowed`):

| Gate | Status | When it fires |
|:--|:--|:--|
| `arming_gate` (Gate 0) | blocked | Slope not yet confirmed: MONITORING or ARMED phase |
| `no_dose` | blocked | Controller recommended 0 U (glucose ≤ target) |
| `trend_confirmation` | blocked | Rising trend not yet confirmed |
| `hypo_guard` | blocked | Predicted glucose below safety threshold |
| `iob_guard` | blocked | Active insulin on board exceeds stacking limit |
| `hypo_suspension` | blocked | Stateful suspension active — holds until glucose confirmed recovered |
| `max_interval_cap` | clipped | Dose reduced to per-interval maximum |
| *(pass-through)* | allowed | Recommendation passed all gates, delivered in full |

---

## Closed Loop Demo

Select **Closed Loop Demo** in the dashboard sidebar to see the full artificial pancreas loop:

```
CGM reading → controller → safety check → pump delivery
     ↑                                          ↓
  next glucose ← advance_physiology(dose) ←←←←←←
```

The delivered insulin is fed back into the physiology model — glucose responds to what the algorithm actually gave. No pre-programming, no manual override.

**What the demo screen shows:**
- Verdict banner — PASS / FAIL / SAFE against ADA targets
- Four metric cards — TIR %, peak glucose (mg/dL), hypo steps, total insulin (U)
- Glucose trajectory chart — blue CGM line with green target band (70–180 mg/dL)
- Insulin delivery bar chart — every autonomous dose by timestep
- Expandable Controller Decision Log — every step: CGM, arm phase, cause, recommended, safety status, delivered, IOB, suspended

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
    ├── simulation/       <- physiology engine · CGM sensor model · scenario definitions
    ├── controller/       <- decision engine · insulin recommendation logic
    ├── safety/           <- 8-gate hard constraints · 3-state arming gate · IOB tracking · hypo suspension
    ├── pump/             <- delivery abstraction · dual-wave bolus state machine
    ├── evaluation/       <- metrics · ADA/EASD scoring · RunSummary
    ├── detection/        <- meal detection · basal drift detection · cause classifier
    ├── explainability/   <- DecisionExplanation · gate annotator · narrative generator
    └── core/             <- startup config · print summary

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
- 9 evaluation scenarios covering hypo, hyper, drift, exercise, overnight, stacked corrections, late correction, sustained basal deficit<br/>
- ADA/EASD pass criteria enforced: TIR ≥70%, peak <250 mg/dL, 0 hypo steps<br/>
- 247 automated tests, all passing<br/>
- Cause-aware dosing: MEAL / BASAL_DRIFT / REBOUND / MIXED / FLAT detection + distinct strategies<br/>
- Doctor-specified 3-state arming gate (monitor → armed → firing) validated across all 9 scenarios
</details>

<details>
<summary><b>02 · Safety Layer Maturity ✓</b></summary>
<br/>
- Insulin-on-board (IOB) modeling with 2-compartment PK/PD<br/>
- Stateful predictive hypoglycemia suspension with configurable resume margin<br/>
- 8 independent safety gates: arming gate (3-state), no-dose, trend confirmation, hypo guard, IOB guard, hypo suspension, interval cap, pass-through<br/>
- Full auditability of every safety intervention via named gate identifiers
</details>

<details>
<summary><b>03 · Human Factors and Explainability ✓</b></summary>
<br/>
- Per-step decision log: CGM, arm phase, cause, recommended dose, safety gate, delivered dose, IOB, suspension state<br/>
- 8 stable named safety gates — every intervention is identified and auditable<br/>
- Cause classification per step: MEAL / BASAL_DRIFT / REBOUND / MIXED / FLAT<br/>
- Full decision log exportable as CSV from Clinical Review mode
</details>

<details>
<summary><b>04 · Clinical Evidence ✓</b></summary>
<br/>
- **Closed-loop demo** with real physiological feedback — delivered insulin changes the glucose trajectory<br/>
- **Clinical Review** mode: one-click full battery with ADA/EASD verdict table and CSV export<br/>
- 9 scenarios validated: baseline meal, dawn phenomenon, overnight stability, stacked corrections, rapid drop, exercise, missed bolus, late correction, sustained basal deficit
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
