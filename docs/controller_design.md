# Controller Design

## Responsibilities
- Detect excursions using slope and acceleration
- Predict short-horizon glucose trajectory
- Estimate correction need
- Fractionate dose into micro-bolus increments
- Recompute at each timestep

## Proposed Pipeline
1. Trend detection
2. Trajectory prediction
3. Dose calculation
4. Micro-bolus planning
5. Safety review

## Initial Assumptions
- CGM cadence is 5 minutes
- Initial prediction horizon is short-range
- Dosing occurs only after sustained trend confirmation
- Any proposed dose must pass all safety gates before simulated delivery

## Open Questions
- What forecast horizon should drive dose calculation?
- How much sustained trend confirmation is required?
- What fractionation strategy should be tested first?
