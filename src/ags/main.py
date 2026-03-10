from __future__ import annotations

from pathlib import Path

from ags.core.config import load_yaml
from ags.core.runner import print_startup_summary


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    simulation_cfg = load_yaml(repo_root / "configs" / "simulation_default.yaml")
    controller_cfg = load_yaml(repo_root / "configs" / "controller_default.yaml")
    safety_cfg = load_yaml(repo_root / "configs" / "safety_default.yaml")
    pump_cfg = load_yaml(repo_root / "configs" / "pump_profiles.yaml")

    print_startup_summary(
        simulation_cfg=simulation_cfg,
        controller_cfg=controller_cfg,
        safety_cfg=safety_cfg,
        pump_cfg=pump_cfg,
    )


if __name__ == "__main__":
    main()
