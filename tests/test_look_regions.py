"""AD-039 §9 (S6): region materials, application part, headless (Manu 2026-11-24, LD-D8 „A, Regionen wie
vorgeschlagen“).

Pinned here: the panel's „Bereich“ (view state, no Undo) chooses what the material controls edit - „Ganzes Objekt“
(`SceneObject.look`) or a face region (its entry in `SceneObject.look_regions`); a preset, a value, the preview and
„Zurücksetzen“ in a region's area are one Undo step each on that entry; a new entry starts from what the region shows
and goes last (the later entry wins on overlap), at most four (a fifth is refused with the reason); the order changes
as one step; a region's rename carries its entry in the same Undo step; a missing region is not drawn and is shown as
missing; the LookDraw carries the drawn regions in order with their faces; the entries travel with Duplicate, the
mirror copy and Detach; save / load keeps them. Core contract: `test_look_regions_format.py`.
"""

from __future__ import annotations

import json

import pytest

import tests._bootstrap  # noqa: F401

from core import FaceRegion, FaceRegions, RegionLook
from core.serialization import LOOK_FORMAT_VERSION, LOOK_REGIONS_FORMAT_VERSION
from gui import lookdev_model as gm
from mirai import lookdev_material as lm
from mirai.application import Application
from mirai.interaction import commands


def _app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.set_viewport_size(800, 600)
    app.frame_scene()
    return app


def _regions(app, **named) -> dict:
    """Name the cube's faces into regions (in memory, like the probe): `name=count` takes the next `count` faces."""
    mesh = app.scene.mesh
    faces = sorted(mesh.all_face_ids(), key=int)
    out, start = {}, 0
    for name, count in named.items():
        out[name] = frozenset(faces[start:start + count])
        start += count
    mesh.face_regions = FaceRegions(tuple(FaceRegion(name, members) for name, members in out.items()))
    return out


@pytest.fixture
def app() -> Application:
    app = _app()
    _regions(app, Mouth=2, Lips=1)
    app.open_lookdev()
    return app


def _undo(app):
    app.dispatch_command(commands.UNDO)
    app.update_viewport(0.0)


def _redo(app):
    app.dispatch_command(commands.REDO)
    app.update_viewport(0.0)


# -- the area and its material -----------------------------------------------------------------------------------------


def test_the_area_is_view_state_and_offers_the_regions(app):
    history = len(app.history)
    assert app.lookdev_area is None and app.lookdev_area_choices() == [("Mouth", False, False), ("Lips", False, False)]
    assert app.set_lookdev_area("Mouth") and app.lookdev_area == "Mouth" and len(app.history) == history
    assert not app.set_lookdev_area("Mouth")  # unchanged
    assert not app.set_lookdev_area("Jaw") and "keine Region 'Jaw'" in app.status_message
    assert app.set_lookdev_area(None) and app.lookdev_area is None
    st = gm.state(app).material
    assert gm.area_label(st) == gm.AREA_WHOLE and [a.name for a in st.areas] == ["Mouth", "Lips"]


def test_a_preset_in_a_region_is_one_step_on_its_entry(app):
    obj = app.scene.edit_object
    app.set_lookdev_material("Creature Skin")
    assert app.set_lookdev_area("Mouth")
    history = len(app.history)
    assert app.set_lookdev_material("Mundinneres")
    assert len(app.history) == history + 1
    assert obj.look.preset == "Creature Skin"  # the object's material stays
    assert obj.look_regions == (RegionLook("Mouth", lm.preset("Mundinneres")),)
    row = gm.state(app).material
    assert row.preset == "Mundinneres" and row.has_look and row.area == "Mouth" and row.maps == ()
    assert [a.label for a in row.areas] == ["Mouth (eigenes Material)", "Lips"]
    _undo(app)
    assert obj.look_regions == () and obj.look.preset == "Creature Skin"
    _redo(app)
    assert obj.look_regions[0].look.preset == "Mundinneres"


def test_values_and_the_preview_edit_the_region_and_start_from_what_it_shows(app):
    obj = app.scene.edit_object
    app.set_lookdev_material("Wet Skin")
    assert app.set_lookdev_area("Lips")
    assert gm.state(app).material.preset == "Wet Skin"  # before it has an entry: the object's material
    history = len(app.history)
    assert app.preview_lookdev_material_values(roughness=0.8)
    assert obj.look_regions == () and len(app.history) == history  # a preview changes no document
    draw = app.lookdev.look_draw(obj)
    assert [d.roughness for d in draw.regions] == [0.8] and draw.roughness == pytest.approx(0.25)
    assert app.set_lookdev_material_values(roughness=0.8)
    assert len(app.history) == history + 1
    (entry,) = obj.look_regions
    assert entry.region == "Lips" and entry.look.preset == "Wet Skin" and entry.look.adjusted
    assert entry.look.roughness == 0.8 and obj.look.roughness == pytest.approx(0.25)
    app.end_lookdev_material_preview()


def test_reset_in_a_region_removes_only_its_entry(app):
    obj = app.scene.edit_object
    app.set_lookdev_material("Creature Skin")
    app.set_lookdev_area("Mouth")
    app.set_lookdev_material("Mundinneres")
    app.set_lookdev_area("Lips")
    app.set_lookdev_material("Wet Skin")
    history = len(app.history)
    assert app.reset_lookdev_material() and len(app.history) == history + 1
    assert [e.region for e in obj.look_regions] == ["Mouth"] and obj.look.preset == "Creature Skin"
    assert not app.reset_lookdev_material()  # nothing left in this area
    app.set_lookdev_area(None)
    assert app.reset_lookdev_material() and obj.look is None and [e.region for e in obj.look_regions] == ["Mouth"]


def test_new_entries_go_last_the_order_moves_as_one_step_and_four_is_the_limit():
    app = _app()
    _regions(app, A=1, B=1, C=1, D=1, E=1)
    app.open_lookdev()
    obj = app.scene.edit_object
    for name in "ABCD":
        app.set_lookdev_area(name)
        assert app.set_lookdev_material("Zähne")
    assert [e.region for e in obj.look_regions] == list("ABCD")
    app.set_lookdev_area("E")
    history = len(app.history)
    assert not app.set_lookdev_material("Zähne") and "höchstens 4 Region-Materialien" in app.status_message
    assert len(app.history) == history and len(obj.look_regions) == 4
    assert app.preview_lookdev_material_values(roughness=0.9)  # held, but a fifth region is not drawn
    assert len(app.lookdev.look_draw(obj).regions) == 4
    assert not app.set_lookdev_material_values(roughness=0.9) and len(app.history) == history
    app.set_lookdev_area("B")
    assert app.move_lookdev_region(1) and [e.region for e in obj.look_regions] == list("ACBD")
    assert len(app.history) == history + 1
    assert app.move_lookdev_region(1) and app.move_lookdev_region(1) is False  # the last place: nothing to move
    assert [e.region for e in obj.look_regions] == list("ACDB")
    assert app.move_lookdev_region(-1) and [e.region for e in obj.look_regions] == list("ACBD")
    _undo(app)
    assert [e.region for e in obj.look_regions] == list("ACDB")
    app.set_lookdev_area(None)
    assert not app.move_lookdev_region(1) and "erst einen Bereich" in app.status_message


def test_the_look_draw_carries_the_drawn_regions_in_order_and_skips_a_missing_one(app):
    obj = app.scene.edit_object
    faces = {r.name: r.faces for r in obj.mesh.face_regions.regions}
    app.set_lookdev_area("Lips")
    app.set_lookdev_material("Wet Skin")
    app.set_lookdev_area("Mouth")
    app.set_lookdev_material("Mundinneres")
    draw = app.lookdev.look_draw(obj)
    assert draw.region_faces == (faces["Lips"], faces["Mouth"])
    assert [d.roughness for d in draw.regions] == [0.25, 0.3]
    assert draw.regions[1].albedo is None and draw.regions[1].map_paths() == {}
    # the region goes from the mesh: its entry stays, it is not drawn, the panel says it is missing
    obj.mesh.face_regions = FaceRegions((FaceRegion("Mouth", faces["Mouth"]),))
    app.update_viewport(0.0)
    draw = app.lookdev.look_draw(obj)
    assert draw.region_faces == (faces["Mouth"],) and [e.region for e in obj.look_regions] == ["Lips", "Mouth"]
    assert ("Lips", True, True) in app.lookdev_area_choices()
    assert "Lips (eigenes Material, Region fehlt)" in [a.label for a in gm.state(app).material.areas]


def test_the_viewport_gets_the_regions_only_while_the_room_draws(app):
    obj = app.scene.edit_object
    app.set_lookdev_area("Mouth")
    app.set_lookdev_material("Mundinneres")
    app.update_viewport(0.0)
    assert app.viewport._edit_look.regions and app.viewport._edit_look.region_faces[0] == \
        obj.mesh.face_regions.get("Mouth").faces
    app.close_lookdev()
    app.update_viewport(0.0)
    assert app.viewport._edit_look is None and not app.viewport.render_mesh.triangle_material_slots


# -- rename, copies, file ----------------------------------------------------------------------------------------------


def test_a_rename_carries_the_entry_in_the_same_undo_step():
    app = _app()
    _regions(app, **{"Group 1": 2})
    app.open_lookdev()
    obj = app.scene.edit_object
    app.set_lookdev_area("Group 1")
    app.set_lookdev_material("Mundinneres")
    app.close_lookdev()
    app.dispatch_command(commands.SET_FACE_MODE)
    history = len(app.history)
    assert app.dispatch_command(commands.REGION_NAME), app.status_message  # Group 1 -> the first set name
    new = obj.mesh.face_regions.regions[0].name
    assert new != "Group 1" and len(app.history) == history + 1
    assert [e.region for e in obj.look_regions] == [new] and app.lookdev.area == new
    _undo(app)
    assert obj.mesh.face_regions.regions[0].name == "Group 1" and [e.region for e in obj.look_regions] == ["Group 1"]
    _redo(app)
    assert [e.region for e in obj.look_regions] == [new]


def test_a_rename_without_an_entry_is_a_mesh_step_only():
    app = _app()
    _regions(app, **{"Group 1": 2})
    obj = app.scene.edit_object
    app.dispatch_command(commands.SET_FACE_MODE)
    assert app.dispatch_command(commands.REGION_NAME)
    assert obj.look_regions == ()


def test_lm_rename_lets_the_carried_entry_replace_a_missing_regions(app):
    a, b = RegionLook("A", lm.preset("Zähne")), RegionLook("B", lm.preset("Wet Skin"))
    assert lm.renamed_region((a, b), "A", "B") == (RegionLook("B", a.look),)
    assert lm.renamed_region((a,), "X", "Y") == (a,)
    assert lm.moved_region((a, b), "A", 5) == (b, a) and lm.moved_region((a, b), "Z", 1) == (a, b)
    with_maps = lm.with_map(lm.preset("Wet Skin"), "normal", "n.png")
    assert lm.with_region((), "A", with_maps)[0].look.maps is None  # a region's material carries no maps
    assert lm.with_region((a, b), "A", None) == (b,)


def test_duplicate_mirror_copy_and_detach_carry_the_entries(app):
    obj = app.scene.edit_object
    app.set_lookdev_area("Mouth")
    app.set_lookdev_material("Mundinneres")
    entries = obj.look_regions
    app.close_lookdev()
    app.dispatch_command(commands.SET_OBJECT_MODE)
    app.select_objects([obj.id])
    before = set(app.scene.objects)
    assert app.duplicate_objects(), app.status_message
    (copy_id,) = set(app.scene.objects) - before
    assert app.scene.objects[copy_id].look_regions == entries
    app.select_objects([obj.id])
    mirrored = app.mirror_copy("X")
    assert mirrored is not None and mirrored.look_regions == entries
    # Detach: the part keeps the entries by name (a region the part does not have is simply not drawn)
    app.dispatch_command(commands.SET_FACE_MODE)
    app.selection.clear()
    app.selection.faces = {sorted(obj.mesh.all_face_ids(), key=int)[0]}
    before = set(app.scene.objects)
    assert app.dispatch_command(commands.DETACH), app.status_message
    (part_id,) = set(app.scene.objects) - before
    assert app.scene.objects[part_id].look_regions == entries


def test_save_and_load_keep_the_entries_and_without_them_the_file_stays_v15(app, tmp_path):
    obj = app.scene.edit_object
    app.set_lookdev_material("Creature Skin")
    plain = tmp_path / "plain.mirai.json"
    assert app.save_scene_file(plain) and json.loads(plain.read_text())["version"] == LOOK_FORMAT_VERSION
    app.set_lookdev_area("Mouth")
    app.set_lookdev_material("Mundinneres")
    path = tmp_path / "regions.mirai.json"
    assert app.save_scene_file(path)
    data = json.loads(path.read_text())
    assert data["version"] == LOOK_REGIONS_FORMAT_VERSION
    fresh = Application()
    fresh.init_scene("file", scene_path=path)
    assert fresh.scene.edit_object.look_regions == obj.look_regions
    assert fresh.lookdev.area is None  # the area is session view state, not saved
