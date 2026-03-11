<div align="center">

# SWARM — Autonomous Glucose Simulation

<p>
  <strong>Research sandbox for autonomous glucose-control algorithm development</strong><br>
  CGM simulation • controller prototyping • safety-first architecture
</p>

<p>
  <img alt="Phase" src="https://img.shields.io/badge/Phase-3%20Controller%20Prototype-blue">
  <img alt="Status" src="https://img.shields.io/badge/Status-Active%20Development-success">
  <img alt="Simulation Only" src="https://img.shields.io/badge/Mode-Simulation%20Only-important">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-informational">
  <img alt="Tests" src="https://img.shields.io/badge/Tests-8%20Passing-success">
</p>

</div>

---

<div align="center">

<table>
  <tr>
    <td align="center"><strong>Phase 1</strong><br>Architecture</td>
    <td align="center"><strong>Phase 2</strong><br>Simulation Engine</td>
    <td align="center"><strong>Phase 3</strong><br>Controller Prototype</td>
    <td align="center"><strong>Phase 4</strong><br>Safety Layer</td>
    <td align="center"><strong>Phase 5</strong><br>Pump Abstraction</td>
    <td align="center"><strong>Phase 6</strong><br>Evaluation Framework</td>
  </tr>
  <tr>
    <td align="center">✅ Complete</td>
    <td align="center">✅ Complete</td>
    <td align="center">✅ Complete</td>
    <td align="center">🟡 Next</td>
    <td align="center">⚪ Planned</td>
    <td align="center">⚪ Planned</td>
  </tr>
</table>

</div>

---

## <span>Purpose</span>

SWARM is a research simulation platform for exploring autonomous glucose-control algorithms in a **fully sandboxed environment**.

The platform simulates glucose dynamics, CGM-like readings, and controller behavior so insulin-dosing strategies can be studied **without interacting with real medical devices**.

It is designed for:

- algorithm development
- simulation-based controller testing
- safety logic research
- repeatable experiment design
- collaboration between engineering and clinical stakeholders

---

## <span>Safety / Research Boundary</span>

<table>
  <tr>
    <td>
      <strong>Important:</strong> This repository is strictly a <strong>simulation and algorithm research environment</strong>.
      <br><br>
      It does <strong>not</strong>:
      <ul>
        <li>control real insulin pumps</li>
        <li>connect to CGM hardware</li>
        <li>provide medical advice</li>
        <li>deliver treatment recommendations</li>
        <li>replace clinician judgment</li>
      </ul>
      All work in this repository is simulation-only.
    </td>
  </tr>
</table>

---

## <span>Core Objectives</span>

- Simulate glucose physiology under configurable meal scenarios
- Generate CGM-like sensor readings with noise
- Detect glucose excursions from time-series data
- Predict short-horizon glucose trajectories
- Estimate corrective insulin requirements
- Study micro-bolus controller behavior
- Add safety constraints such as IOB ceilings and hypo protection
- Evaluate controller strategies across repeatable scenarios

---

## <span>System Architecture</span>

```text
Scenario Inputs
      ↓
Physiology Engine
      ↓
True Glucose
      ↓
CGM Sensor Model
      ↓
Controller Pipeline
      ↓
Safety Layer (next)
      ↓
Pump Abstraction (planned)
      ↓
Experiment Output / Evaluation
```

---

## <span>Development Status</span>

### Phase 1 — Architecture Design ✅
System architecture, documentation, collaboration structure, and project boundaries defined.

**Key assets**
- architecture documentation
- physiology design notes
- controller design notes
- safety model planning
- GitHub workflow templates

**Location**
```text
docs/
```

---

### Phase 2 — Physiological Simulation Engine ✅
A modular baseline simulation engine is implemented.

**Implemented capabilities**
- meal absorption modeling
- glucose dynamics simulation
- CGM noise generation
- insulin action helper separation
- reusable baseline scenario setup
- CSV run export
- timestamped output files

**Core modules**
```text
src/ags/simulation/
  state.py
  physiology.py
  insulin.py
  sensor.py
  engine.py
  io.py
  scenarios.py
  run.py
```

**Example output**
```text
experiments/outputs/simulation_run_<timestamp>.csv
```

---

### Phase 3 — Controller Prototype ✅
A baseline autonomous controller pipeline is implemented.

**Current controller flow**
```text
Current / Previous CGM
        ↓
Excursion Detection
        ↓
Short-Horizon Prediction
        ↓
Correction Recommendation
```

**Implemented modules**
```text
src/ags/controller/
  state.py
  detector.py
  predictor.py
  recommender.py
  pipeline.py
  run.py
```

**Current controller behavior**
- glucose-delta excursion detection
- linear short-horizon projection
- correction-factor dosing estimate

This is an **algorithm prototype**, not a clinically mature dosing model.

---

## <span>Upcoming Phases</span>

### Phase 4 — Safety Layer
Planned safeguards include:
- insulin-on-board ceiling checks
- predicted hypoglycemia suspend rules
- per-interval dose limits
- controller override / clipping decisions

### Phase 5 — Pump Abstraction
Planned delivery modeling includes:
- micro-bolus execution simulation
- pump-like state handling
- delivery constraint emulation
- vendor-neutral dose behavior

### Phase 6 — Evaluation Framework
Planned evaluation work includes:
- outcome metrics
- replayable experiments
- scenario comparison
- risk scoring
- result summaries and plots

---

## <span>Repository Structure</span>

```text
src/
  ags/
    controller/
    core/
    evaluation/
    models/
    pump/
    safety/
    scenarios/
    simulation/
    visualization/

tests/
docs/
configs/
experiments/
```

---

## <span>Run the Simulation</span>

```bash
PYTHONPATH=src python -m ags.simulation.run
```

This writes a timestamped CSV file to:

```text
experiments/outputs/simulation_run_<timestamp>.csv
```

---

## <span>Run the Controller Demo</span>

```bash
PYTHONPATH=src python -m ags.controller.run
```

**Example result**
```text
Controller demo
====================
Current glucose: 150.00 mg/dL
Previous glucose: 140.00 mg/dL
Glucose delta: 10.00 mg/dL
Rising: True
Falling: False
Predicted glucose (30 min): 210.00 mg/dL
Recommended correction: 2.00 U
Reason: predicted glucose above target
```

---

## <span>Run the Test Suite</span>

```bash
PYTHONPATH=src pytest -q
```

**Current coverage includes**
- simulation engine behavior
- scenario configuration
- CSV export
- insulin helper functions
- timestamped output path generation
- controller pipeline output

---

## <span>Project Workflow</span>

<table>
  <tr>
    <th align="left">Area</th>
    <th align="left">Purpose</th>
  </tr>
  <tr>
    <td>GitHub Issues</td>
    <td>Track work items, experiments, and tasks</td>
  </tr>
  <tr>
    <td>Pull Requests</td>
    <td>Review code and documentation changes</td>
  </tr>
  <tr>
    <td>GitHub Projects</td>
    <td>Track roadmap progress across phases</td>
  </tr>
  <tr>
    <td>Google Docs</td>
    <td>Clinical review and physician collaboration</td>
  </tr>
</table>

---

## <span>Current Status</span>

<table>
  <tr>
    <td>
      <strong>Current phase:</strong> Phase 3 — Controller Prototype
      <br>
      <strong>Next milestone:</strong> Phase 4 — Safety Layer
      <br>
      <strong>Repository state:</strong> active, test-backed, simulation-only
    </td>
  </tr>
</table>

---

<div align="center">
  <sub><strong>SWARM</strong> — simulation-first architecture for autonomous glucose-control research</sub>
</div>

