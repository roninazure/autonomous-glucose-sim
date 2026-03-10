from __future__ import annotations

from typing import Any


def print_startup_summary(
    simulation_cfg: dict[str, Any],
    controller_cfg: dict[str, Any],
    safety_cfg: dict[str, Any],
    pump_cfg: dict[str, Any],
) -> None:
    print("Autonomous Glucose Simulation")
    print("=" * 32)
    print("Mode: research sandbox")
    print()

    print("Simulation config:")
    print(simulation_cfg)
    print()

    print("Controller config:")
    print(controller_cfg)
    print()

    print("Safety config:")
    print(safety_cfg)
    print()

    print("Pump profiles:")
    print(pump_cfg)
    print()

    print("Phase 1 scaffold loaded successfully.")
