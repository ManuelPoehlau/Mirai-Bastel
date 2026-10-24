"""Parity: the Production Look rows (`src/mirai/viewport/look_controls.py`, AD-024 §8) step the
Worklight exactly as this lab's rows do. The lab is the oracle; Production keeps its own copy
(it imports nothing from `experiments/`), so this test catches the two drifting apart."""

from __future__ import annotations

import pytest

from mirai.viewport.look_controls import LIGHT_ROW_IDS, light_row
from viewport_shading_lab.lab_controls import ROW_IDS, ROWS
from viewport_shading_lab.lab_rig import PRESET_RAITT, PRESET_SOFTBOX, PRESETS


def test_same_rows_in_the_same_order():
    assert LIGHT_ROW_IDS == ROW_IDS


@pytest.mark.parametrize("row_id", ROW_IDS)
@pytest.mark.parametrize("fine", [False, True])
@pytest.mark.parametrize("direction", [-1, 1])
def test_each_step_matches_the_lab(row_id, fine, direction):
    lab_row = ROWS[ROW_IDS.index(row_id)]
    for rig in (
        PRESETS[PRESET_RAITT],
        PRESETS[PRESET_RAITT].with_(fill_coupled=False),
        PRESETS[PRESET_SOFTBOX].with_(key_azimuth=175.0, key_elevation=88.0, ambient=0.58),
    ):
        assert light_row(row_id).step(rig, direction, fine) == lab_row.step(rig, direction, fine)
        assert light_row(row_id).applies(rig) == lab_row.applies(rig)
