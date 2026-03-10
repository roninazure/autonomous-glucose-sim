# Safety Logic

## Safety Constraints
- Maximum bolus per interval
- Maximum insulin-on-board
- Hypoglycemia prediction suspend
- Sustained-trend requirement before dosing

## Safety Outcomes
- Approve
- Clip
- Suspend
- Reject

## Logging Requirement
Every safety intervention must record:
- Timestamp
- Proposed dose
- Final approved dose
- Reason code

## Example Reason Codes
- MAX_BOLUS_INTERVAL
- MAX_IOB_EXCEEDED
- HYPO_PREDICTION_RISK
- TREND_NOT_SUSTAINED
- NEGATIVE_OR_ZERO_DOSE
- PUMP_INCREMENT_CLIP

## Design Principle
Safety must be implemented as an explicit supervisory layer separate from control logic.
