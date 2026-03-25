# SWARM Bolus — User Guide

> Simulation-only software. No real patients, no real insulin delivery.

---

## Getting Started

### Launch the Dashboard

```bash
# From the project root
streamlit run app.py
```

Open your browser to `http://localhost:8501`. The dashboard opens with the sidebar on the left and the main panel on the right.

---

## Navigation

The sidebar has two sections:

**Clinical** (default, always visible)
- `⬡ Closed Loop Demo` — run a simulation and watch the algorithm work
- `Retrospective CGM Replay` — replay the controller against a real CGM trace
- `⬡ Swarm Bolus Lab` — first-phase pancreatic response experiments

**Research & Validation** (hidden by default — tick *Open research tools* to reveal)
- `A vs B Comparison` — compare two scenarios side by side
- `Population Sweep` — run one scenario across all 4 patient types
- `PSO Optimizer` — auto-tune controller parameters

---

## Mode 1 · Closed Loop Demo

**What it does:** Runs a full artificial pancreas simulation. The algorithm reads CGM, decides on a dose, the pump delivers it, and that insulin actually changes the glucose trajectory — just like a real closed-loop system.

### Step-by-step

**1. Select a scenario** (sidebar → Clinical Scenario)

| Scenario | What it simulates |
|---|---|
| Baseline Meal | 45g carbs at t=30 min — standard post-meal control |
| Large Meal Spike | Higher carb load — tests aggressive rise handling |
| Missed Bolus | 75g meal with no manual pre-bolus — controller must catch it |
| Dawn Phenomenon | No meal; slow cortisol-driven glucose rise overnight |
| Sustained Basal Deficit | Continuous glucose creep — insufficient background insulin |

**2. Configure the patient** (sidebar → Patient)
- Set starting glucose (mg/dL)
- Optionally enable *Estimate ISF from weight* — enter body weight (kg) and the 1700 Rule calculates the Insulin Sensitivity Factor automatically
- Select insulin type: NovoLog (75 min peak), Humalog (65 min), or Fiasp (55 min)

**3. Configure the controller** (sidebar → Controller)
- **Target glucose** — the value the algorithm aims for (default 110 mg/dL)
- **Correction factor (ISF)** — mg/dL drop per unit of insulin (overridden if weight-based ISF is enabled)
- **Micro-bolus fraction** — what fraction of the full correction is delivered per step (default 0.25)
- **Min excursion to dose** — how far above target before a dose is triggered (default 10 mg/dL)
- **RoR-tiered micro-bolus** — toggle adaptive scaling based on rate of rise (recommended: on)
- **Timestep** — 1 min (FreeStyle Libre cadence) or 5 min (standard)

**4. Configure safety thresholds** (sidebar → Safety)
- **Max dose per step** — hard cap per 5-min interval (default 0.5 U)
- **Max insulin on board** — IOB stacking limit (default 3.0 U)
- **Hypo guard threshold** — predicted glucose floor; blocks dosing if t+30 min prediction is below this (default 80 mg/dL)

**5. Configure the pump** (sidebar → Pump)
- **Dual-wave bolus** — splits each dose into an immediate fraction + extended tail
  - Enable the toggle, then set *Immediate fraction* (e.g. 0.33 = ⅓ now, ⅔ extended)
  - Set *Extended duration* — how many minutes to drip the tail (default 20 min)

**6. Set simulation duration** (sidebar → Simulation)
- Default: 240 minutes (4 hours)
- Increase for overnight scenarios (dawn phenomenon, sustained drift)

**7. Click "Run Simulation"**

### Reading the Results

**Chart — top panel**
- Red dashed line = no treatment (glucose goes where physics takes it)
- Green solid line = autonomous control (algorithm + pump)
- Blue triangles = every insulin dose delivered (hover for amount and time)
- Shaded band = 30-minute glucose prediction
- Coloured annotations = detected events (meal onset, drift, rebound)

**Metric cards (below chart)**
- Peak delta — how much lower the algorithm kept the peak vs. no treatment
- Time-in-range % — % of time between 70–180 mg/dL
- Total insulin delivered — cumulative units
- Safety interventions — blocked / clipped / suspended counts

**Decision Timeline (expandable)**
- Every timestep listed as a row: time, CGM, trend, dose, gate fired
- Click any row to expand a full audit card showing:
  - CGM reading and rate of rise
  - 30-min glucose prediction
  - Insulin on board (IOB)
  - What the controller recommended and why
  - Which safety gate fired and its outcome
  - Plain-English narrative

---

## Mode 2 · Retrospective CGM Replay

**What it does:** Takes a fixed CGM trace (real patient data or a built-in reference) and runs the controller against it as if it had been there. The glucose trajectory does not change — this is a *what-would-it-have-decided* audit tool.

### Step-by-step

**1. Choose a data source** (sidebar → CGM Source)

*Built-in reference traces:*
| Trace | Pattern |
|---|---|
| Post-prandial Spike | 60g meal, missed bolus → 110 → 239 → 134 mg/dL |
| Nocturnal Hypo | Overnight IOB, sensitive patient → 90 → 57 → 78 mg/dL |
| Dawn Phenomenon | Cortisol rise, no meal → 105 → 163 mg/dL |

*Upload your own:*
- Simple CSV format: two columns — `timestamp_min` and `glucose_mgdl`
- Dexcom G6/G7 Clarity export: auto-detected; EGV rows extracted automatically

**2. Configure controller and safety settings** — same as Closed Loop Demo above

**3. Click "Replay"**

### Reading the Results

- CGM trace plotted as-is (fixed — not altered by the controller)
- Overlaid with the controller's hypothetical dose recommendations at each step
- IOB accumulation tracked as if doses had been delivered
- Safety gate annotations at every blocked or suspended step
- Full Decision Timeline available

---

## Mode 3 · Swarm Bolus Lab

**What it does:** Simulates the pancreas's first-phase insulin response — the sharp burst of insulin a healthy pancreas fires within 2 minutes of detecting a glucose rise. Experiments with different trigger thresholds and response magnitudes.

### Step-by-step

**1. Configure the trigger** (sidebar)
- Set the glucose rate-of-rise threshold that fires the first-phase response
- Set the response magnitude (units)

**2. Click "Run Experiment"**

**3. Review the checkpoint table** — glucose and IOB at key timepoints across the simulation

---

## Mode 4 · A vs B Comparison *(Research tools)*

**What it does:** Runs two different scenarios through the same algorithm and compares clinical outcomes side by side.

### Step-by-step

1. Tick *Open research tools* in the sidebar
2. Select *A vs B Comparison*
3. Choose **Scenario A** and **Scenario B** from the dropdowns
4. Configure controller, safety, and pump settings (applied to both runs)
5. Click **"Run Comparison"**

### Reading the Results

- Two charts displayed side by side (A left, B right)
- Comparative metrics table: TIR, peak, variability, insulin delivered, safety interventions
- AI-generated plain-English verdict — overall assessment of which conditions the algorithm handled best and why

---

## Mode 5 · Population Sweep *(Research tools)*

**What it does:** Runs one scenario against all four patient archetypes to test whether the controller works across a diverse population.

### Step-by-step

1. Tick *Open research tools* in the sidebar
2. Select *Population Sweep*
3. Choose a scenario
4. Configure controller and safety settings
5. Click **"Run Sweep"**

### Patient archetypes tested

| Profile | ISF | Carb Impact | Insulin Peak |
|---|---|---|---|
| Standard Adult | 50 mg/dL/U | 4.0 mg/dL/g | 75 min |
| Insulin Resistant | 30 mg/dL/U | 4.5 mg/dL/g | 75 min |
| Highly Sensitive | 85 mg/dL/U | 3.0 mg/dL/g | 65 min |
| Rapid Responder | 50 mg/dL/U | 4.0 mg/dL/g | 55 min |

### Reading the Results

- Four charts in a 2×2 grid — one per archetype
- Summary table: TIR, peak, mean glucose, variability for each profile
- Identifies which patient types are most challenging for the current parameter set

---

## Mode 6 · PSO Optimizer *(Research tools)*

**What it does:** Automatically searches for the best combination of 7 controller and safety parameters. No manual configuration needed — press one button.

### Step-by-step

1. Tick *Open research tools* in the sidebar
2. Select *PSO Optimizer*
3. Click **"Run PSO Optimisation"** — nothing else to set

The optimizer runs 20 particles × 25 iterations. Each particle is a candidate set of parameters. All 20 are evaluated in parallel across all 6 scenarios × 4 patient profiles = 480 closed-loop simulations per run.

### Reading the Results

**Convergence chart**
- X-axis: iteration number
- Y-axis: best fitness score (lower = better)
- Watch the curve descend — the swarm is converging on better parameters

**Progress table** — best TIR % and fitness score at each iteration

**Best parameters found** — table of all 7 tuned values:

| Parameter | What it controls |
|---|---|
| Target glucose | The glucose level the algorithm aims to maintain |
| Correction factor (ISF) | How aggressively it corrects a given excursion |
| Micro-bolus fraction | What fraction of the full correction is delivered each step |
| Min excursion delta | How far above target before a dose fires |
| Max dose per step | Safety cap per 5-min interval |
| Max IOB | Maximum active insulin allowed before blocking new doses |
| Hypo guard threshold | Predicted glucose floor below which dosing is blocked |

**Export** — download the optimized parameters as JSON to use in subsequent runs.

---

## Exporting Data

Every run produces downloadable outputs:

| Export | Format | Contents |
|---|---|---|
| Timestep records | CSV | Every step: time, CGM, trend, recommendation, gate, delivered dose, IOB |
| Clinical report | JSON | Full parameter set, scenario, metrics, ADA/EASD pass/fail verdicts |
| Optimized config | JSON | Best PSO parameters (Optimizer mode only) |
| Profile sweep | CSV | All 4 archetypes × all metrics in one table |

Look for the **Download** buttons below each results panel.

---

## Reading the Decision Timeline

Every step can be expanded into a full audit card. Here is what each field means:

```
t = 35 min
  cgm             191.0 mg/dL         — sensor reading this step
  trend           ↑ +1.60 mg/dL/min   — rate of rise from recent history
  predicted +30   239.2 mg/dL         — where glucose is headed in 30 min
  IOB             0.000 U             — active insulin already on board

  recommended     0.579 U             — what the controller asked for
  reason          predicted glucose above target

  gate            allowed ✓           — which safety gate fired
  reason          recommendation allowed
  final units     0.579 U             — what was actually delivered

  narrative       CGM 191 mg/dL (↑ +1.6/min) → pred 239 mg/dL at t+30 —
                  delivered 0.58 U (full recommendation: 0.58 U).
```

**Safety gate colour codes:**

| Colour | Gate | Meaning |
|---|---|---|
| Green | allowed ✓ | Dose delivered in full |
| Yellow | max_interval_cap | Dose reduced to per-step maximum |
| Red | hypo_guard | Blocked — predicted glucose too low |
| Orange | iob_guard | Blocked — too much insulin already active |
| Grey | no_dose | Nothing to deliver (glucose at or below target) |
| Blue | trend_confirmation | Blocked — rising trend not yet confirmed |
| Pink | SUSPENSION | Blocked — hypo suspension lock-out active |

---

## Common Questions

**Why does the algorithm sometimes not dose even though glucose is high?**
One of the 7 safety gates has blocked it. Expand the Decision Timeline to see which gate fired and why. Most commonly: IOB guard (insulin already on board), trend confirmation (only one rising step so far), or hypo guard (prediction shows a future dip).

**What is IOB and why does it matter?**
Insulin on Board is the total active insulin still working in the body. Dosing on top of high IOB causes stacking — glucose crashes hours later. The IOB guard prevents this.

**Why does the controller use a small fraction instead of a full correction?**
Micro-bolus fraction (default 0.25) means only 25% of the full correction is given per step. The loop re-evaluates every 5 minutes, so the algorithm delivers insulin gradually and adjusts in real time rather than over-shooting with one large dose.

**What does "closed loop" mean?**
The delivered insulin is fed back into the physiology model — it actually lowers the simulated glucose. This is different from an open-loop calculation where you estimate a dose but don't simulate the result. The green trace on the chart is the real outcome of the algorithm's decisions.

**What is dual-wave bolus?**
A split dose: part delivered immediately (hits the early glucose spike fast), the remainder dripped slowly over 20 minutes (covers the prolonged carb absorption tail). Mimics what insulin pumps call a "combo bolus."

---

## Glossary

| Term | Definition |
|---|---|
| CGM | Continuous Glucose Monitor — sensor reading every 1 or 5 minutes |
| TIR | Time-in-Range — % of readings between 70 and 180 mg/dL |
| IOB | Insulin on Board — active insulin still working in the body (units) |
| ISF | Insulin Sensitivity Factor — how many mg/dL one unit of insulin lowers glucose |
| RoR | Rate of Rise — how fast glucose is changing (mg/dL per minute) |
| Micro-bolus | A small correction dose, a fraction of the full calculated correction |
| Pre-bolus | A dose fired at meal onset to get ahead of the carb absorption curve |
| Dual-wave | A split bolus: immediate fraction + extended tail |
| Hypo | Hypoglycaemia — glucose below 70 mg/dL |
| Hyper | Hyperglycaemia — glucose above 180 mg/dL |
| PSO | Particle Swarm Optimisation — automated parameter search algorithm |
| SaMD | Software as a Medical Device |

---

*SWARM Bolus — Simulation only. Not for clinical use.*
