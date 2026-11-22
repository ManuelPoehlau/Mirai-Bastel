"""`probe_lookdev_room.py` arguments (AD-039 §4 / §11.2: `--effects`), headless."""

from __future__ import annotations

import pytest

from drag_cost import probe_lookdev_room as room


def test_effects_default_every_built_effect_and_none_measures_no_p3_row():
    from viewport.lookdev_optics import LookdevEffects

    assert room.parse_args([]).effects == LookdevEffects.names() == ("shadow", "eye_shadow")
    assert room.parse_args(["--effects", "none"]).effects == ()
    assert room.parse_args(["--effects", "shadow"]).effects == ("shadow",)


def test_an_unknown_effect_is_refused():
    with pytest.raises(SystemExit):
        room.parse_args(["--effects", "bloom"])


def test_the_eye_shadow_row_switches_the_shadow_too():
    """AD-039 §5: `lookdev +shadow +eyes` against `lookdev +shadow` (eye shadow off) is S2's cost."""
    from viewport.lookdev_optics import EFFECT_NEEDS

    assert room.EFFECT_ROWS["shadow"] == ("lookdev +shadow", ("shadow",))
    label, names = room.EFFECT_ROWS["eye_shadow"]
    assert label == "lookdev +shadow +eyes" and set(names) == {"eye_shadow", EFFECT_NEEDS["eye_shadow"]}
    assert room.parse_args(["--effects", "shadow,eye_shadow"]).effects == ("shadow", "eye_shadow")
