# System Architecture

## Top-Level Modules
- Scenario manager
- Physiological simulation engine
- CGM sensor model
- Autonomous controller
- Safety supervisor
- Pump abstraction layer
- Metrics and evaluation engine
- Visualization layer

## Core Loop
1. Load scenario inputs
2. Advance physiological state
3. Generate CGM observation
4. Run controller
5. Apply safety gates
6. Emulate pump delivery
7. Log timestep outputs
8. Compute metrics

## Design Principles
- Vendor-neutral
- Sandbox only
- Replaceable models
- Reproducible experiments
- Controller separated from delivery

## Data Flow
Scenario Manager
→ Physiology Engine
→ CGM Sensor
→ Controller
→ Safety Supervisor
→ Pump Emulator
→ State Logger / Metrics

## Notes
The controller may recommend actions, but only the simulation environment may emulate delivery. No module may communicate with real hardware or external therapy systems.
