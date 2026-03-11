from ags.simulation.insulin import decay_insulin_on_board, insulin_glucose_effect_mgdl


def test_decay_insulin_on_board_reduces_iob() -> None:
    assert decay_insulin_on_board(2.0) == 1.9
    assert decay_insulin_on_board(0.0) == 0.0


def test_insulin_glucose_effect_mgdl_computes_expected_effect() -> None:
    effect = insulin_glucose_effect_mgdl(
        insulin_on_board_u=2.0,
        insulin_sensitivity_mgdl_per_unit=50.0,
        effect_fraction_per_step=0.05,
    )
    assert effect == 5.0
