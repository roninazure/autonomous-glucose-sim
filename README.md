<div align="center">

# SWARM Bolus — Autonomous Glucose Simulation

<p>
  <strong>Simulation platform for autonomous insulin-control algorithm development</strong><br>
  CGM simulation • controller prototyping • safety-first architecture • clinical evaluation
</p>

<p>
  <img alt="Phase" src="https://img.shields.io/badge/Phase-3%20Controller%20Prototype-blue">
  <img alt="Status" src="https://img.shields.io/badge/Status-Active%20Development-success">
  <img alt="Mode" src="https://img.shields.io/badge/Mode-Simulation%20Only-important">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-informational">
  <img alt="Tests" src="https://img.shields.io/badge/Tests-Passing-success">
</p>

</div>

---

## 🧠 What This Is

SWARM Bolus is a **simulation-first platform for building an autonomous insulin dosing engine**.

It enables engineers and clinicians to evaluate:
- glucose dynamics
- insulin decision logic
- safety constraints
- delivery behavior

All in a **controlled, non-clinical environment**.

---

## ⚠️ Safety Boundary

This system:

- ❌ does NOT control real insulin pumps  
- ❌ does NOT connect to CGM hardware  
- ❌ does NOT provide medical advice  
- ❌ does NOT deliver treatment  

This is **simulation-only research software**.

---

## 🎯 What We Have Built

A complete **closed-loop simulation stack**:

1. **Physiology Engine** → models glucose behavior  
2. **CGM Sensor Model** → generates noisy readings  
3. **Controller** → recommends insulin  
4. **Safety Layer** → blocks/clips unsafe dosing  
5. **Pump Abstraction** → enforces delivery constraints  
6. **Evaluation Layer** → produces clinical-style metrics  

---

## 🏗️ Architecture

```
Scenario Inputs
      ↓
Physiology Engine
      ↓
True Glucose
      ↓
CGM Sensor Model
      ↓
Controller (Decision Engine)
      ↓
Safety Layer
      ↓
Pump Abstraction
      ↓
Evaluation + Visualization
```

---

## ⚡ Core Capability: Scenario Comparison

Run **Scenario A vs Scenario B**:

- Same algorithm
- Same constraints
- Different conditions

This allows controlled testing of:
- meal impact
- fasting response
- extreme glucose excursions

---

## 📊 Clinical Metrics Layer

Each run produces:

| Metric | Meaning |
|------|--------|
| Time in Range % | % of time 70–180 mg/dL |
| Average CGM | Mean glucose |
| Peak CGM | Max excursion |
| Time Above 250 | Severe hyperglycemia exposure |
| Glucose Variability (SD) | Stability |
| Recommended Insulin | Controller output |
| Delivered Insulin | After safety/pump |
| Blocked Decisions | Fully stopped |
| Clipped Decisions | Reduced dosing |

---

## 🧠 AI Comparative Verdict

The system generates a **plain-English interpretation**:

- better vs worse control
- spike severity
- insulin demand differences
- safety intervention frequency

This is an **assistive interpretation layer**.

---

## 🖥️ Streamlit Dashboard

Run:

```bash
streamlit run app.py
```

### Dashboard includes:

- Scenario comparison controls
- Clinical summary cards
- Metric comparison table
- CGM trajectory visualization
- Insulin delivery comparison
- Safety intervention overlay
- AI-generated verdict

---

## 🧪 Example Use Case

Compare:

- Baseline Meal vs Large Meal Spike

Evaluate:

- glucose rise magnitude
- insulin required
- safety intervention frequency
- control stability

---

## 🚀 How to Run

### Simulation
```bash
PYTHONPATH=src python -m ags.simulation.run
```

### Controller
```bash
PYTHONPATH=src python -m ags.controller.run
```

### UI
```bash
streamlit run app.py
```

### Tests
```bash
PYTHONPATH=src pytest -q
```

---

## 📁 Structure

```
src/
  ags/
    controller/
    evaluation/
    pump/
    safety/
    simulation/
    scenarios/

tests/
docs/
experiments/
```

---

# 🧬 FDA Pathway Thinking (Early Strategy)

This project is being designed with a **future regulated medical-device pathway in mind**.

### Likely classification
- Software as a Medical Device (SaMD)
- Potentially Class II (similar to insulin dosing support / AID systems)

---

## Required evolution toward clinical use

### 1. Algorithm Validation
- large-scale simulation testing
- edge-case coverage (hypo/hyper extremes)
- repeatability across scenarios

### 2. Safety Layer Maturity
- insulin-on-board modeling
- hypoglycemia prediction
- hard safety constraints
- override logic

### 3. Human Factors / UX
- explainability of decisions
- clinician interpretability
- auditability of outputs

### 4. Data & Clinical Evidence
- retrospective dataset validation
- controlled pilot studies
- outcome comparison vs standard care

### 5. Regulatory Pathway
- FDA 510(k) or De Novo pathway (depending on claims)
- alignment with existing AID systems (e.g., hybrid closed loop)

---

## Key design principle

> Build the **decision engine + safety logic in simulation first**, then validate, then integrate.

This repo represents the **pre-clinical algorithm validation layer**.

---

# 📈 Pitch Deck (Condensed)

## Problem

- Insulin dosing remains **complex, error-prone, and manual**
- Patients and clinicians rely on:
  - heuristics
  - delayed CGM interpretation
  - non-adaptive strategies

Result:
- glucose variability
- hyperglycemia exposure
- hypoglycemia risk

---

## Solution

SWARM Bolus is a **simulation-trained autonomous insulin decision engine**.

It:
- continuously evaluates glucose trends
- predicts short-term trajectory
- recommends dosing
- enforces safety constraints

---

## Why This Approach Wins

- simulation-first → safe iteration
- measurable outcomes → clinical metrics
- explainable decisions → clinician trust
- modular architecture → device-agnostic

---

## Current Stage

- fully working simulation engine
- controller prototype complete
- comparison + evaluation framework live
- UI for real-time scenario testing

---

## What’s Next

- safety layer expansion
- pump behavior realism
- risk scoring system
- dataset validation
- clinician-in-the-loop testing

---

## Long-Term Vision

A **fully autonomous insulin dosing brain** that can:

- integrate with CGMs and pumps
- adapt per patient
- continuously learn
- operate safely within regulatory frameworks

---

## One-Line Pitch

> We are building the decision engine that powers the future of autonomous insulin delivery — starting in simulation, validated before reality.

---

## 🧭 Status

| Phase | Status |
|------|--------|
| Architecture | ✅ |
| Simulation Engine | ✅ |
| Controller | ✅ |
| Safety Layer | 🟡 |
| Pump Abstraction | 🟡 |
| Evaluation Engine | 🟡 |

---

<div align="center">
  <sub><strong>SWARM</strong> — build the brain first, validate it, then deploy it</sub>
</div>
