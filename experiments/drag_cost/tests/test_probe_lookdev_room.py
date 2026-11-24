"""`probe_lookdev_room.py` arguments (AD-039 §4 / §11.2: `--effects`), headless."""

from __future__ import annotations

import pytest

from drag_cost import probe_lookdev_room as room


def test_effects_default_every_built_effect_and_none_measures_no_p3_row():
    from viewport.lookdev_optics import LookdevEffects

    assert room.parse_args([]).effects == LookdevEffects.names() == ("shadow", "eye_shadow", "dual_lobe", "thickness",
                                                                         "cube", "maps")
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


def test_the_dual_lobe_row_measures_it_alone():
    """AD-039 §6: `lookdev +dual` against `lookdev` (every effect off) is S3's cost."""
    assert room.EFFECT_ROWS["dual_lobe"] == ("lookdev +dual", ("dual_lobe",))
    assert room.parse_args(["--effects", "dual_lobe"]).effects == ("dual_lobe",)


def test_the_thickness_row_switches_the_shadow_too():
    """AD-039 §7: `lookdev +shadow +thick` against `lookdev +shadow` is S4's cost."""
    from viewport.lookdev_optics import EFFECT_NEEDS

    label, names = room.EFFECT_ROWS["thickness"]
    assert label == "lookdev +shadow +thick" and set(names) == {"thickness", EFFECT_NEEDS["thickness"]}


def test_the_maps_row_measures_them_alone_with_three_generated_maps():
    """AD-039 §10: `lookdev +maps` against `lookdev` is S7's cost; the probe's maps are deterministic RGBA images and a
    flat region of the normal map decodes to no tilt (128)."""
    import numpy as np

    assert room.EFFECT_ROWS["maps"] == ("lookdev +maps", ("maps",))
    images = room.probe_map_images(64)
    assert set(images) == {"roughness", "normal", "translucency"}
    assert all(im.shape == (64, 64, 4) and im.dtype == np.uint8 for im in images.values())
    assert tuple(images["normal"][1, 1, :3]) == (128, 128, 255)  # a bump's top: no tilt
    assert np.array_equal(room.probe_map_images(64)["roughness"], images["roughness"])
