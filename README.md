# SWARM Bolus --- Autonomous Glucose Simulation

## Purpose

SWARM is a research simulation platform for exploring autonomous
glucose-control algorithms in a **fully sandboxed environment**.

The system simulates glucose dynamics, CGM sensor readings, and
controller decisions so insulin-dosing strategies can be studied
**without interacting with real medical devices**.

This repository is designed for algorithm development, controller
experimentation, and safety research.

------------------------------------------------------------------------

# Research Scope

This project is strictly a **simulation and algorithm research
environment**.

It does **NOT**:

-   Control real insulin pumps
-   Connect to CGM hardware
-   Provide medical advice
-   Deliver treatment recommendations
-   Replace clinical decision making

The system exists solely for **controller algorithm experimentation and
safety research**.

------------------------------------------------------------------------

# Core Objectives

The SWARM platform aims to:

• Simulate glucose physiology under configurable meal scenarios\
• Generate CGM-like sensor signals with noise\
• Detect glucose excursions from time-series data\
• Predict short-horizon glucose trajectories\
• Estimate corrective insulin requirements\
• Study micro-bolus controller behavior\
• Apply safety constraints such as insulin-on-board limits\
• Evaluate controller strategies across repeatable simulations

------------------------------------------------------------------------

# Development Status

The system is being built in layered phases.

## Phase 1 --- Architecture Design ✓ COMPLETE

System architecture, research boundaries, and controller framework
defined.

Documentation located in:

    docs/

------------------------------------------------------------------------

## Phase 2 --- Physiological Simulation Engine ✓ COMPLETE

A deterministic glucose simulation environment has been implemented.

Capabilities:

• Meal absorption modeling\
• Glucose dynamics simulation\
• CGM sensor noise generation\
• Insulin action helpers\
• Scenario-based simulation inputs\
• CSV experiment output

Core modules:

    src/ags/simulation/

    engine.py
    physiology.py
    sensor.py
    insulin.py
    scenarios.py
    io.py
    run.py

Example simulation output:

    experiments/outputs/simulation_run_<timestamp>.csv

------------------------------------------------------------------------

## Phase 3 --- Controller Prototype ✓ COMPLETE

A baseline autonomous controller pipeline has been implemented.

Controller pipeline:

    CGM readings
          ↓
    Excursion detection
          ↓
    Short-horizon prediction
          ↓
    Correction recommendation

Controller modules:

    src/ags/controller/

    state.py
    detector.py
    predictor.py
    recommender.py
    pipeline.py
    run.py

The controller currently uses:

• glucose delta detection\
• linear short-horizon projection\
• correction-factor dosing estimate

This is an **algorithm prototype**, not a clinical dosing model.

------------------------------------------------------------------------

# Upcoming Development Phases

## Phase 4 --- Safety Layer

Introduce safeguards such as:

• insulin-on-board ceilings\
• hypoglycemia prediction guards\
• correction rate limits\
• controller override logic

------------------------------------------------------------------------

## Phase 5 --- Pump Abstraction

Simulate insulin delivery behavior:

• micro-bolus execution\
• insulin absorption modeling\
• pump state tracking

------------------------------------------------------------------------

## Phase 6 --- Evaluation Framework

Controller benchmarking across scenarios:

• outcome metrics\
• risk scoring\
• replayable experiments\
• scenario libraries

------------------------------------------------------------------------

# Repository Structure

    src/
      ags/
        simulation/
        controller/
        safety/
        pump/
        models/
        evaluation/
        visualization/

    tests/
    docs/
    configs/
    experiments/

------------------------------------------------------------------------

# Running the Simulation

Run a glucose simulation:

    PYTHONPATH=src python -m ags.simulation.run

Example output file:

    experiments/outputs/simulation_run_<timestamp>.csv

------------------------------------------------------------------------

# Running the Controller Demo

Run the baseline controller prototype:

    PYTHONPATH=src python -m ags.controller.run

Example output:

    Controller demo
    Current glucose: 150 mg/dL
    Predicted glucose (30 min): 210 mg/dL
    Recommended correction: 2.0 U

------------------------------------------------------------------------

# Test Suite

Run all tests:

    PYTHONPATH=src pytest -q

Current test coverage includes:

• simulation engine\
• scenario configuration\
• CSV output generation\
• insulin action helpers\
• controller pipeline logic

------------------------------------------------------------------------

# Collaboration Model

Development workflow:

• Design discussions → **GitHub Discussions**\
• Work tracking → **GitHub Issues**\
• Code changes → **Pull Requests**\
• Phase planning → **GitHub Projects**

------------------------------------------------------------------------

# Safety Boundaries

SWARM is **not a medical device**.

It does not:

• control insulin pumps\
• connect to CGM sensors\
• deliver treatment recommendations\
• interact with patients

All experiments occur in **simulation only**.

------------------------------------------------------------------------

# Current Status

Current phase:

**Phase 3 --- Controller Prototype**

Next milestone:

**Phase 4 --- Safety Layer**
