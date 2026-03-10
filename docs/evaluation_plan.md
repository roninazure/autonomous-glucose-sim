# Evaluation Plan

## Purpose
Define how controller performance will be evaluated in the simulation environment.

## Primary Metrics

### Time in Range (TIR)
Percentage of time glucose remains between:

70–180 mg/dL

### Time Below Range
Percentage of time glucose falls below:

70 mg/dL

### Time Above Range
Percentage of time glucose exceeds:

180 mg/dL

### Post-Meal Peak
Maximum glucose value observed after a meal event.

### Glucose Variability
Measured using:
- Standard deviation
- Coefficient of variation

### Insulin Efficiency
Total insulin delivered relative to achieved glucose control.

## Experiment Types

### Baseline Scenario
No meals, stable glucose.

### Standard Meal Scenario
Three mixed meals with normal absorption.

### Stress Scenario
Large meal spikes and rapid glucose excursions.

### Sensitivity Profiles
Run identical scenarios across multiple simulated patient profiles.

## Result Logging
Each experiment should produce:

- timestep glucose trace
- insulin delivery trace
- controller decision log
- safety intervention log
- summary metrics

## Output Artifacts
- CSV or JSON experiment logs
- metric summaries
- visualization plots

## Design Principle
Evaluation must remain reproducible and scenario-driven so that controller improvements can be compared objectively.
