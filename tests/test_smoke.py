from pathlib import Path

from ags.core.config import load_yaml


def test_load_yaml_returns_dict() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    data = load_yaml(repo_root / "configs" / "simulation_default.yaml")
    assert isinstance(data, dict)
    assert "simulation" in data
