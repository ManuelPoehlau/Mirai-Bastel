"""`probe_lookdev_room.py` arguments (AD-039 §4 / §11.2: `--effects`), headless."""

from __future__ import annotations

import pytest

from drag_cost import probe_lookdev_room as room


def test_effects_default_every_built_effect_and_none_measures_no_p3_row():
    from viewport.lookdev_optics import LookdevEffects

    assert room.parse_args([]).effects == LookdevEffects.names() == ("shadow",)
    assert room.parse_args(["--effects", "none"]).effects == ()
    assert room.parse_args(["--effects", "shadow"]).effects == ("shadow",)


def test_an_unknown_effect_is_refused():
    with pytest.raises(SystemExit):
        room.parse_args(["--effects", "bloom"])
