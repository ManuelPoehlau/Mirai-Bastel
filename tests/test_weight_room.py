"""AD-041 slice 2: the Weight Room in the app (`Application.open_weight_room`, `controllers.weight_room`).

Pinned: entering and leaving is view state (no History step; the weight view and the Soft preview come back) and refused
at object level and on an eye; a stroke is one Undo step that creates the skin layer when absent (Undo leaves the mesh
as before, Redo brings the same values); Esc mid-stroke rolls back exactly; the room's input (modelling keys and Undo
mid-stroke refused, Shift+wheel radius, Alt+wheel strength, the plain wheel zooms); refusals (no bone, a linked edit
object, an off-centre bone under symmetry); a bone on the plane paints both sides exactly symmetric; painting while
posed moves the painted vertices at once; bone choice (a click on a bone line, Ctrl+LMB = the largest share); the heatmap
follows the strokes row by row; "Aufräumen" is one Undo step; a changed edit object ends the room; the HUD names it.

Headless, in the AD-027 scenario driver on the head (`tests/rig_support.py`; the window's sink types hold their data
without a GL context).
"""

from __future__ import annotations

import numpy as np
import pytest

import tests._bootstrap  # noqa: F401
from core import SelectionMode
from hud import hud_state
from mirai.interaction import commands
from mirai.interaction.session import RunContext
from mirai.skinning import BonePose, skin_layer
from mirai.soft_selection.shading import WEIGHT_ZERO_RGB, weight_colors
from mirai.symmetry import vertex_correspondence
from tests.interaction_trace import CTRL_Y, CTRL_Z, ESC, HEIGHT, WIDTH, key
from tests.rig_support import FALLOFF, SHIFT_S, head_driver, hold, jaw_faces, rig_head, weights

VIEW = key("9")


def share(app, bone=None) -> dict:
    bone = app.current_bone if bone is None else bone
    return {v: w for v, value in weights(app.scene.mesh).items() for k, w in value if k == bone and w > 0.0}


def room(symmetric: bool = True, **brush):
    """The head with one bone on the plane (no weights yet), face mode, the Weight Room open with a wide brush."""
    d = head_driver(symmetric=symmetric)
    rig_head(d, group=False)
    app = d.app
    assert app.open_weight_room(), app.status_message
    app.set_weight_brush(**{"radius_step": 13, "flow": 1.0, **brush})  # 15 % of the head's radius
    return d


def screen_point(app, side: float = 0.0) -> tuple[float, float]:
    """The screen point of the front jaw surface at `side` (x) - hit by the room's ray."""
    mesh = app.scene.mesh
    faces = jaw_faces(mesh)
    centres = []
    for f in faces:
        pts = np.array([mesh.vertex_position(v) for v in mesh.face_vertices(f)])
        centres.append(pts.mean(axis=0))
    centres = np.array(centres)
    best = centres[np.argmin(np.abs(centres[:, 0] - side) - 0.01 * centres[:, 2])]
    x, y = app._objects.edit_camera.project_to_screen(tuple(best), WIDTH, HEIGHT)
    assert app._weight_room.hit(x, y) is not None
    return x, y


def stroke(d, x, y, steps: int = 8, dx: float = 4.0, dy: float = 0.0, release: bool = True) -> None:
    d.motion(x, y)
    d.press()
    for i in range(1, steps + 1):
        d.motion(x + dx * i, y + dy * i)
    if release:
        d.release()


# -- the room ------------------------------------------------------------------------------------------------------


def test_entering_and_leaving_is_view_state_and_restores_the_weight_view() -> None:
    d = head_driver()
    rig_head(d)
    hold(d, FALLOFF, ((40, 0),))
    app = d.app
    d.tap(VIEW)
    assert app.weight_view and app.soft_shading
    history = len(app.history)
    assert app.open_weight_room() and app.weight_room_open
    assert app.interaction_owner == "weight" and not app.weight_view and not app.soft_shading
    overlay = app._soft_shading_overlay
    assert overlay.heat is app.weight_heat
    assert "Weight Room" in app.status_message and len(app.history) == history
    assert hud_state(app).active.startswith("Weight Room · ")
    assert app.close_weight_room() and not app.weight_room_open
    assert app.interaction_owner is None and app.weight_view and app.soft_shading and overlay.heat is None
    assert len(app.history) == history


def test_the_room_is_refused_at_object_level_and_on_an_eye() -> None:
    d = head_driver()
    app = d.app
    d.tap(key("4"))
    assert not app.open_weight_room() and "1/2/3" in app.status_message
    d.tap(key("3"))
    eye = app.add_eye()
    app._objects.set_edit_object(eye.id)
    app._follow_edit_object()
    assert not app.open_weight_room() and "Auge" in app.status_message


def test_a_stroke_is_one_undo_step_that_makes_the_skin_layer() -> None:
    d = room()
    app = d.app
    mesh = app.scene.mesh
    assert skin_layer(mesh) is None
    history = len(app.history)
    stroke(d, *screen_point(app))
    assert len(app.history) == history + 1, app.status_message
    painted = share(app)
    assert painted and all(0.0 < w <= 1.0 for w in painted.values())
    d.tap(CTRL_Z)
    assert skin_layer(mesh) is None and len(app.history) == history
    d.tap(CTRL_Y)
    assert share(app) == painted


def test_esc_rolls_the_running_stroke_back_exactly() -> None:
    d = room()
    app = d.app
    stroke(d, *screen_point(app))
    before = weights(app.scene.mesh)
    history = len(app.history)
    stroke(d, *screen_point(app), release=False)
    assert app.weight_stroking and weights(app.scene.mesh) != before
    d.tap(ESC)
    assert not app.weight_stroking and weights(app.scene.mesh) == before
    d.release()
    assert len(app.history) == history and weights(app.scene.mesh) == before


def test_the_rooms_input() -> None:
    d = room()
    app = d.app
    assert app.can_run(commands.MOVE, RunContext("key")) is not None  # modelling keys are silent
    assert app.can_run(commands.UNDO, RunContext("key")) is None
    stroke(d, *screen_point(app), release=False)
    assert app.can_run(commands.UNDO, RunContext("key")) is not None  # not while a stroke runs
    d.release()
    app.set_weight_brush(radius_step=5)
    step = app.weight_brush.radius_step
    d.scroll("UP", ("shift",))
    assert app.weight_brush.radius_step == step + 1
    flow = app.weight_brush.flow
    d.scroll("DOWN", ("alt",))
    assert app.weight_brush.flow < flow
    distance = app.camera.distance
    d.scroll("UP")
    assert app.camera.distance != distance and app.weight_brush.radius_step == step + 1


def test_a_brush_that_catches_no_vertex_says_so() -> None:
    d = room(radius_step=0)
    app = d.app
    history = len(app.history)
    stroke(d, *screen_point(app, side=0.9), steps=2, dx=1.0)
    assert len(app.history) == history and "Shift+Rad" in app.status_message


def test_a_stroke_that_writes_nothing_leaves_no_step() -> None:
    d = room(operation="subtract")
    app = d.app
    history = len(app.history)
    stroke(d, *screen_point(app))  # nothing to take away
    assert len(app.history) == history and skin_layer(app.scene.mesh) is None


# -- refusals ------------------------------------------------------------------------------------------------------


def test_without_a_bone_the_room_opens_but_does_not_paint() -> None:
    d = head_driver()
    app = d.app
    d.tap(key("3"))
    assert app.open_weight_room()
    assert app.weight_paint_blocker is not None and "Knochen" in app.weight_paint_blocker
    history = len(app.history)
    x, y = WIDTH / 2, HEIGHT / 2
    stroke(d, x, y)
    assert len(app.history) == history and "Knochen" in app.status_message


def test_an_off_centre_bone_under_symmetry_is_refused() -> None:
    d = room()
    app = d.app
    rig = app.scene.rig
    after, bid = rig.with_new_bone("Wange_Links", (1.0, 0.5, 1.0), (1.5, 0.0, 1.2))
    app.scene.rig = after
    app.select_bone(bid)
    assert "Symmetrie" in app.weight_paint_blocker
    history = len(app.history)
    stroke(d, *screen_point(app))
    assert len(app.history) == history
    for _ in range(3):  # X -> Y -> Z -> off: it paints
        d.tap(SHIFT_S)
    assert app.scene.mesh.symmetry_definition is None
    assert app.weight_paint_blocker is None
    stroke(d, *screen_point(app, side=0.8))
    assert len(app.history) > history and share(app, bid)


# -- symmetry, pose, bone choice ----------------------------------------------------------------------------------


def test_a_bone_on_the_plane_paints_both_sides_exactly_symmetric() -> None:
    d = room(operation="add", flow=0.6)
    app = d.app
    x, y = screen_point(app, side=0.9)
    stroke(d, x, y, steps=8, dx=4.0)
    painted = share(app)
    partners = {v: c.partner for v, c in vertex_correspondence(app.scene.mesh).items()
                if getattr(c, "partner", None) is not None}
    assert painted
    assert any(partners.get(v) not in (None, v) for v in painted)  # off the seam
    for v, w in painted.items():
        p = partners.get(v)
        if p is not None:
            assert painted.get(p) == pytest.approx(w, abs=1e-12)


def test_painting_while_posed_moves_the_painted_vertices_at_once() -> None:
    d = room()
    app = d.app
    bone = app.current_bone
    stroke(d, *screen_point(app, side=0.9), steps=8, dx=4.0)  # bound: the skin stage shows the pose
    assert share(app)
    app._skeleton.set_pose({bone: BonePose(translation=(0.0, -0.6, 0.0))})
    d.motion(*screen_point(app))
    assert app.posed
    cage = app._query_cage()
    assert cage is not None
    rest = {v: cage.vertex_position(v) for v in app.scene.mesh.all_vertex_ids()}
    before = share(app)
    stroke(d, *screen_point(app), release=False)  # (the drags tick the frames: the stroke's dabs run there)
    grown = {v for v, w in share(app).items() if w > before.get(v, 0.0)}
    assert grown
    assert all(app._query_cage().vertex_position(v) != rest[v] for v in grown)
    d.release()
    assert app.posed


def test_a_click_on_a_bone_line_chooses_the_bone_and_a_drag_from_it_paints() -> None:
    d = room()
    app = d.app
    rig = app.scene.rig
    first = app.current_bone
    after, second = rig.with_new_bone("Hals", (0.0, -1.5, 0.0), (0.0, -0.5, 0.2))
    app.scene.rig = after
    app.select_bone(second)
    bone = rig.bone(first)
    mid = tuple((a + b) / 2 for a, b in zip(bone.head, bone.tail))
    x, y = app.camera.project_to_screen(mid, WIDTH, HEIGHT)
    assert app._skeleton.bone_at(x, y) == first
    history = len(app.history)
    d.click(x, y)
    assert app.current_bone == first and len(app.history) == history
    app.select_bone(second)
    stroke(d, x, y, steps=6, dx=3.0)  # beyond the click slop: a stroke from the press point
    assert app.current_bone == second
    assert len(app.history) == history + 1 or "nichts" in app.status_message


def test_ctrl_click_chooses_the_bone_with_the_largest_share() -> None:
    d = room()
    app = d.app
    jaw = app.current_bone
    stroke(d, *screen_point(app))
    after, other = app.scene.rig.with_new_bone("Kopf", (0.0, 1.0, 0.0), (0.0, 2.0, 0.0))
    app.scene.rig = after
    app.select_bone(other)
    x, y = screen_point(app)
    history = len(app.history)
    d.click(x, y, modifiers=("ctrl",))
    assert app.current_bone == jaw and len(app.history) == history


# -- the heatmap ---------------------------------------------------------------------------------------------------


def test_the_heatmap_follows_the_strokes_row_by_row() -> None:
    d = room(flow=0.5)
    app = d.app
    stroke(d, *screen_point(app))  # the first stroke makes the layer (one whole recompute)
    heat = app.weight_heat
    overlay = app._soft_shading_overlay
    full, rows = heat.full_computes, heat.row_updates
    stroke(d, *screen_point(app), dy=3.0)
    assert heat.full_computes == full and heat.row_updates > rows
    positions, colors, tris = overlay.heat_arrays()
    mesh = app.scene.mesh
    assert len(positions) == len(heat.ids) == mesh.vertex_count() if hasattr(mesh, "vertex_count") else True
    expected = np.zeros(len(heat.ids))
    painted = share(app)
    for v, w in painted.items():
        expected[heat.index[v]] = w
    assert np.allclose(heat.shares, expected)
    assert np.allclose(colors, weight_colors(expected))
    assert np.allclose(colors[expected == 0.0][:, :3], WEIGHT_ZERO_RGB)
    faces = sum(1 for _ in mesh.all_face_ids())
    assert len(tris) >= faces  # every shown face is drawn, also at share 0
    d.tap(CTRL_Z)
    assert not np.allclose(heat.shares, expected)


def test_the_heatmap_shows_the_current_bone() -> None:
    d = room()
    app = d.app
    stroke(d, *screen_point(app))
    heat = app.weight_heat
    assert heat.shares.max() > 0.0
    after, other = app.scene.rig.with_new_bone("Kopf", (0.0, 1.0, 0.0), (0.0, 2.0, 0.0))
    app.scene.rig = after
    app.select_bone(other)
    d.motion(10, 10)
    assert heat.bone == other and heat.shares.max() == 0.0


# -- Füllen aus Auswahl, Aufräumen, the edit object, the HUD -----------------------------------------------------


def test_fill_from_the_selection_inside_the_room_is_one_undo_step_and_the_room_stays() -> None:
    """AD-041 §3.4: the room's panel fills from the selection beside the room's session - one History entry, the heatmap
    follows, the room (the slot's owner) stays open, the face shading of the weight view does not cover the heatmap."""
    d = room()
    app = d.app
    assert app.selection.faces and not share(app)
    history = len(app.history)
    assert app.fill_weights_value(15.0), app.status_message
    assert app.status_message.endswith("committed (Ctrl+Z takes it back)")
    assert len(app.history) == history + 1 and share(app)
    assert app.weight_room_open and app.interaction_owner == "weight"
    assert app.weight_heat.shares.max() > 0.0
    assert not app.weight_view  # no face shading over the heatmap
    d.tap(CTRL_Z)
    assert not share(app) and len(app.history) == history and app.interaction_owner == "weight"
    d.tap(CTRL_Y)
    assert share(app)
    # the room still paints afterwards (Add would change nothing on shares that are 1 already)
    app.set_weight_brush(operation="subtract")
    stroke(d, *screen_point(app))
    assert len(app.history) == history + 2


def test_fill_inside_the_room_is_refused_without_a_selection_and_during_a_stroke() -> None:
    d = room()
    app = d.app
    x, y = screen_point(app)
    stroke(d, x, y, release=False)
    assert app.weight_stroking
    history = len(app.history)
    assert not app.fill_weights_value(15.0) and app.status_message == "Fill from selection: not during a stroke"
    assert len(app.history) == history
    d.release()
    app.selection.clear()
    history = len(app.history)
    assert not app.fill_weights_value(15.0)
    assert app.status_message == "Fill from selection: select points or faces first" and len(app.history) == history
    assert app.interaction_owner == "weight"


# -- Aufräumen, the edit object, the HUD -------------------------------------------------------------------------


def test_clean_is_one_undo_step() -> None:
    d = room(flow=0.15)
    app = d.app
    stroke(d, *screen_point(app))
    small = {v for v, w in share(app).items() if w < 0.2}
    assert small
    history = len(app.history)
    assert app.clean_weights_value(0.2)
    assert len(app.history) == history + 1 and not (set(share(app)) & small)
    d.tap(CTRL_Z)
    assert small <= set(share(app))


def test_a_changed_edit_object_ends_the_room() -> None:
    d = room()
    app = d.app
    head = app.scene.edit_object_id
    app.close_weight_room()
    app.add_primitive("cube")
    other = app.scene.edit_object_id
    app._objects.set_edit_object(head)
    app._follow_edit_object()
    d.tap(key("3"))
    assert app.open_weight_room()
    app._objects.set_edit_object(other)
    app._follow_edit_object()
    d.motion(5, 5)
    assert not app.weight_room_open and app.interaction_owner is None


def test_the_hud_names_the_room_bone_and_operation() -> None:
    d = room(operation="smooth")
    app = d.app
    active = hud_state(app).active
    assert active == f"Weight Room · {app.current_bone_name} · Smooth"
    assert app.selection.mode is SelectionMode.FACE
