# Project Overview

## Objective
Design a proof-of-concept simulation platform that evaluates an automated insulin-dosing controller using CGM time-series data.

## Primary Goal
Study the behavior of a controller that:
- detects glucose excursions
- predicts near-term glucose behavior
- estimates insulin correction needs
- simulates fractionated micro-bolus responses
- applies safety gating before simulated delivery

## Non-Goals
- No real device integration
- No treatment recommendations
- No patient-specific medical advice
- No clinical deployment
- No real-world insulin actuation

## Key Requirements
- 5-minute CGM timestep support
- Excursion detection
- Predicted glucose trajectory
- Micro-bolus simulation
- Vendor-neutral pump abstraction
- Safety supervision
- Replayable experiment scenarios

## Stakeholders
- Engineering lead
- Clinical/research partner

## Current Phase
Phase 1 — Architecture design
