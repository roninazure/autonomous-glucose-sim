# SWARM Bolus — Quick Reference Guide

> Simulation-only platform. No real patients, no real insulin delivery.

---

## At a Glance

| Item | Value |
|---|---|
| Purpose | Closed-loop autonomous insulin dosing simulation |
| Physiology model | Bergman 3-compartment (glucose + insulin PK/PD) |
| CGM cadence | 1-min or 5-min |
| Simulation step | 5 minutes (default) |
| Target glucose range | 70–180 mg/dL (TIR standard) |
| Tests passing | 219 |
| Regulatory target | FDA 510(k) / De Novo — Class II SaMD |

---

## Glucose Targets (ADA/EASD)

| Metric | Target |
|---|---|
| Time-in-Range (70–180 mg/dL) | ≥ 70% |
| Time below 70 mg/dL | 0 steps |
| Peak glucose | < 250 mg/dL |
| Glucose variability (SD) | < 36 mg/dL |

---

## Controller — Cause-Aware Dosing

The controller detects *why* glucose is rising, then responds with the appropriate strategy.

| Detected Cause | Trigger Criteria | Dosing Strategy |
|---|---|---|
| **MEAL — Onset** | RoR + acceleration + duration | Single pre-bolus = 40% of estimated carb impact |
| **MEAL — Peak** | Ongoing post-meal rise | Micro-bolus tiered to RoR: slow=25%, moderate=50%, fast=100% |
| **BASAL DRIFT** | RoR 0.08–0.70 mg/dL/min + R²>0.72 | 25% correction fraction (accumulates gradually) |
| **REBOUND** | Post-hypo (<80) rise detected | 10% correction fraction (conservative) |
| **MIXED** | Both meal + drift signals present | RoR tiebreaker: ≥1.5 → MEAL, <0.7 → DRIFT |
| **FLAT** | No detector fires | Standard correction if predicted > target |

**Meal pre-bolus fires once per meal** — de-duplicated; resets after 20 min of NONE signal.

---

## Rate-of-Rise (RoR) Reference

| RoR (mg/dL/min) | Interpretation | ISF Estimate |
|---|---|---|
| ≥ 3.0 | Very fast / meal peak | ~30 (resistant) |
| 1.0–2.9 | Moderate rise | ~50 (average) |
| 0.08–0.70 | Slow / basal drift | ~85 (sensitive) |
| < 0.08 | Flat | No dose triggered |

---

## Safety Gates (evaluated in order, every step)

| # | Gate | Condition | Outcome |
|---|---|---|---|
| 1 | **No-dose** | Recommendation ≤ 0 U | Blocked |
| 2 | **Trend confirmation** | <2 consecutive rising steps | Blocked |
| 3 | **Hypo guard** | Predicted glucose at t+30 min < 80 mg/dL | Blocked |
| 4 | **IOB guard** | Total insulin on board ≥ 3.0 U | Blocked |
| 5 | **Max interval cap** | Dose > 0.5 U per 5-min step | Clipped to limit |
| 6 | **Allowed** | All gates passed | Delivered as-is |
| 7 | **Hypo suspension** | Active suspension state | Blocked until recovery confirmed |

**Hypo suspension** is stateful — once triggered, dosing is locked until:
- Glucose trend is confirmed rising, AND
- Predicted glucose > hypo threshold + 10 mg/dL margin

---

## Default Safety Thresholds

| Parameter | Default | PSO Range |
|---|---|---|
| Target glucose | 110 mg/dL | 90–140 mg/dL |
| Correction factor (ISF) | 50 mg/dL/U | 25–100 mg/dL/U |
| Micro-bolus fraction | 0.25 | 0.05–1.0 |
| Min excursion to dose | 10 mg/dL | 0–30 mg/dL |
| Max dose per 5-min step | 0.5 U | 0.10–0.50 U |
| Max insulin on board (IOB) | 3.0 U | 1.0–6.0 U |
| Hypo guard threshold | 80 mg/dL | 70–100 mg/dL |
| Hypo resume margin | +10 mg/dL | — |

---

## Insulin Profiles Supported

| Profile | Peak Time |
|---|---|
| NovoLog / Aspart | 75 min |
| Humalog / Lispro | 65 min |
| Fiasp | 55 min |

---

## Patient Archetypes (Profile Sweep)

| Profile | ISF (mg/dL/U) | Carb Impact (mg/dL/g) | Peak Time |
|---|---|---|---|
| Standard Adult | 50 | 4.0 | 75 min |
| Insulin Resistant | 30 | 4.5 | 75 min |
| Highly Sensitive | 85 | 3.0 | 65 min |
| Rapid Responder | 50 | 4.0 | 55 min |

---

## Test Scenarios

| Scenario | Setup | Tests |
|---|---|---|
| Baseline Meal | 45g carbs at t=30, no drift | Routine post-prandial control |
| Dawn Phenomenon | No meal, +0.8 mg/dL/step drift | Basal drift detection + slow correction |
| Sustained Basal Deficit | No meal, +1.5 mg/dL/step drift | BASAL_DRIFT gate, strong drift correction |
| Exercise Hypoglycaemia | Negative drift −1.2/step, elevated ISF | Hypo guard + suspension logic |
| Missed Bolus | 75g meal, no pre-bolus | Retroactive correction + IOB stacking limits |
| Late Correction | Meal at t=5 + t=90, no pre-bolus | Delayed insulin-carb timing + rebound risk |

---

## PSO Optimiser — Quick Facts

| Item | Value |
|---|---|
| Algorithm | Particle Swarm Optimisation — ring topology (lbest) |
| Particles | 20 |
| Iterations | 30 |
| Parameters tuned | 7 (see Safety Thresholds table above) |
| Scenarios evaluated | Baseline Meal, Dawn Phenomenon, Missed Bolus |
| Patient profiles | All 4 archetypes |
| Runs per particle | 3 scenarios × 4 profiles = 12 |
| Total evaluations | 20 × 30 = 600 particle-evaluations |
| Parallelism | All 20 particles evaluated simultaneously |
| Inertia weight | 0.9 → 0.4 (linear decay; explore early, exploit late) |

**Fitness formula** (minimised):
```
fitness = −TIR%  +  3.0 × time_below_70%  +  1.5 × time_above_250%
```

---

## Decision Log — Gate Reason Codes

| Code | Meaning |
|---|---|
| `NEGATIVE_OR_ZERO_DOSE` | No positive dose to deliver |
| `TREND_NOT_SUSTAINED` | Rising trend not yet confirmed |
| `HYPO_PREDICTION_RISK` | Predicted glucose too low at t+30 |
| `MAX_IOB_EXCEEDED` | Too much active insulin already on board |
| `MAX_BOLUS_INTERVAL` | Dose clipped to per-step maximum |
| `PUMP_INCREMENT_CLIP` | Rounded to nearest 0.1 U pump increment |
| `ALLOWED` | Dose delivered as recommended |
| `SUSPENDED` | Hypo suspension active |

---

## Dashboard Modes

| Mode | Use For |
|---|---|
| **Closed Loop Demo** | Run a single scenario; see CGM, doses, predictions, metrics |
| **Comparison** | A vs B — same algorithm, different conditions |
| **Profile Sweep** | One scenario × all 4 patient archetypes |
| **PSO Optimizer** | Auto-tune parameters; view convergence; export config |

---

## Key Abbreviations

| Abbreviation | Meaning |
|---|---|
| TIR | Time-in-Range (70–180 mg/dL) |
| IOB | Insulin on Board (total active insulin, U) |
| ISF | Insulin Sensitivity Factor (mg/dL drop per unit) |
| RoR | Rate of Rise (mg/dL/min from CGM trend) |
| PSO | Particle Swarm Optimisation |
| CGM | Continuous Glucose Monitor |
| PK/PD | Pharmacokinetics / Pharmacodynamics |
| AID | Automated Insulin Delivery |
| SaMD | Software as a Medical Device |
| lbest | Local best (ring-topology PSO social attractor) |

---

*SWARM Bolus — Simulation only. Not for clinical use.*
