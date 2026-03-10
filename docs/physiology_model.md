# Physiological Model

## Purpose
Describe how glucose, meal absorption, and insulin action are represented in simulation.

## Components
- Glucose dynamics model
- Meal absorption model
- Insulin action curve
- CGM lag and sensor noise

## Initial Modeling Strategy
Start with simple parametric models that are easy to explain and test. Increase realism only after the simulation loop and safety logic are stable.

## Model Responsibilities
### Glucose model
Represents true glucose evolution over time.

### Meal model
Adds meal-driven glucose impact using configurable absorption timing.

### Insulin model
Tracks delivered insulin impact and insulin-on-board decay.

### CGM model
Produces an observed CGM value from true glucose with lag/noise.

## Open Questions
- Which insulin action curve family should be used first?
- How should meal absorption variability be represented?
- How much CGM lag/noise is appropriate for baseline testing?
