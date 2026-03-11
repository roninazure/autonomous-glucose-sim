from __future__ import annotations


def decay_insulin_on_board(
    insulin_on_board_u: float,
    decay_factor: float = 0.95,
) -> float:
    return max(0.0, insulin_on_board_u * decay_factor)


def insulin_glucose_effect_mgdl(
    insulin_on_board_u: float,
    insulin_sensitivity_mgdl_per_unit: float,
    effect_fraction_per_step: float = 0.05,
) -> float:
    return insulin_on_board_u * insulin_sensitivity_mgdl_per_unit * effect_fraction_per_step
