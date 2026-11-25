"""`probe_lookdev_room.py` arguments (AD-039 §4 / §11.2: `--effects`), headless."""

from __future__ import annotations

import pytest

from drag_cost import probe_lookdev_room as room


def test_effects_default_every_built_effect_and_none_measures_no_p3_row():
    from viewport.lookdev_optics import LookdevEffects

    assert room.parse_args([]).effects == LookdevEffects.names() == ("shadow", "eye_shadow", "dual_lobe", "thickness",
                                                                         "cube", "regions", "maps",
                                                                         "area_diffuse", "soft_shadow")
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


def test_the_soft_light_row_measures_it_alone():
    """AD-039 §23 (S8): `lookdev +area` against `lookdev` (every effect off) is the soft light's cost (≤ +0.3 ms)."""
    assert room.EFFECT_ROWS["area_diffuse"] == ("lookdev +area", ("area_diffuse",))
    assert room.parse_args(["--effects", "area_diffuse"]).effects == ("area_diffuse",)


def test_the_soft_shadow_row_measures_it_against_the_shadow():
    """AD-039 §24 (S9): `lookdev +shadow +soft` against `lookdev +shadow` is the soft shadow's cost."""
    assert room.EFFECT_ROWS["soft_shadow"] == ("lookdev +shadow +soft", ("shadow", "soft_shadow"))


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


def test_the_regions_row_names_a_polygroup_as_the_mouth_in_memory():
    """AD-039 §9: `lookdev +regions` against `lookdev` is S6's cost; the probe names the edit object's first polygroup
    "Mouth" and gives it "Mundinneres" as a region material (one Undo step, nothing saved)."""
    from core import FaceRegion, FaceRegions
    from mirai.application import Application

    assert room.EFFECT_ROWS["regions"] == ("lookdev +regions", ("regions",))
    assert room.parse_args(["--effects", "regions"]).effects == ("regions",)
    app = Application()
    app.init_scene("cube")
    assert room.probe_region(app) is None  # no polygroup: nothing done
    mesh = app.scene.mesh
    faces = sorted(mesh.all_face_ids(), key=int)
    mesh.face_regions = FaceRegions((FaceRegion("Group 2", frozenset(faces[:2])), FaceRegion("Group 4",
                                                                                          frozenset(faces[2:3]))))
    assert room.probe_region(app) == "'Group 2' -> 'Mouth' (2 faces), 'Mundinneres'"
    obj = app.scene.edit_object
    assert [r.name for r in mesh.face_regions.regions] == ["Mouth", "Group 4"]
    assert [(e.region, e.look.preset) for e in obj.look_regions] == [("Mouth", "Mundinneres")]
    assert app.lookdev_area is None and obj.look is None


def test_the_ld3a_rows_run_by_default_at_two_sizes_and_can_be_skipped():
    """AD-040 §11.1: the LD-3a rows (tiers framed / close per size, drag policies, idle) are part of the default run."""
    args = room.parse_args([])
    assert args.ld3a == "all" and args.ld3a_sizes == ((1024, 768), (1920, 1080))
    assert room.parse_args(["--ld3a", "none"]).ld3a == "none"
    assert room.parse_args(["--ld3a-sizes", "800x600"]).ld3a_sizes == ((800, 600),)
    with pytest.raises(SystemExit):
        room.parse_args(["--ld3a-sizes", "big"])
