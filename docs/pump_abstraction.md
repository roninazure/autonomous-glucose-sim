# Pump Abstraction Layer

## Purpose
Provide a vendor-neutral interface that emulates insulin pump behavior in the simulation environment.

This layer ensures the controller does not depend on any specific pump manufacturer.

## Responsibilities
- Accept controller dose requests
- Apply pump-specific constraints
- Quantize doses to pump increment size
- Emulate delivery timing
- Return delivery confirmation to the simulation

## Pump Constraints
Different pump families may vary by:
- Minimum dose increment
- Delivery latency
- Maximum dose per interval

## Example Pump Profiles
- Omnipod-like
- Tandem-like
- Medtronic-like

Each profile defines:
- dose increment
- delivery latency
- maximum interval delivery

## Design Principle
The controller proposes a dose.

The pump abstraction layer decides how that dose would be delivered under the rules of a particular pump profile.

## Simulation Role
This module **does not control real pumps**.

It simply emulates how different pump classes would behave if a dose were requested.
