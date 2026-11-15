"""Surface Slide, Phase 3 (audit 2026-11-14 §13.4): the gesture in the app - gate G3.

Hold J (Manu 2026-11-15, E6): the selected (else the hovered) vertices slide across the drawn surface of the press
state; every motion maps the summed pixel drag at the pivot's drawn press position (M1). Pinned: one History entry,
Undo / Redo exact, Esc and a drag back to the press pixel bit-exact, a press without motion writes nothing; a held
gesture refuses Undo / Redo / topology / mode commands and a second hold key; refusals at the press reach the status
line and leave no session; posed (bound) and object mode refused; under symmetry the cage stays `VALID` with bitwise
mirror pairs; with a morph target dialled in the base slides on the base surface (0 % == no target, bit for bit);
the Soft radius steps live; hidden faces are walls and the rest of the mesh stays.
"""

from __future__ import annotations

import functools
import random
from pathlib import Path

import pytest

import tests._bootstrap  # noqa: F401
from tests.mesh_invariants import assert_mesh_invariants
from tests.surface_slide_fixtures import point_triangle_distance
from tests.test_surface_slide_plan import bits, near

from viewport.derived import triangulate_mesh_face  # noqa: E402
from viewport.packed_geometry import np  # noqa: E402

from core import LayerKind, PointLayerInfo, SelectionMode  # noqa: E402
from mirai.application import Application  # noqa: E402
from mirai.controllers.gestures import SurfaceSlideGesture  # noqa: E402
from mirai.interaction import commands  # noqa: E402
from mirai.interaction.input import Input  # noqa: E402
from mirai.morph_targets import morph_target_ids  # noqa: E402
from mirai.symmetry import SymmetryState, mirror_position, symmetry_state, vertex_correspondence  # noqa: E402

_REPO = Path(__file__).resolve().parent.parent
GOLLUM = _REPO / "scenes" / "Gollum_Head_01.mirai.json"
MORPHS = _REPO / "scenes" / "Gollum_Head_01_Morphs.mirai.json"
WIDTH, HEIGHT = 800, 600


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


J, W, G, C, ESC = _key("j"), _key("w"), _key("g"), _key("c"), _key("ESCAPE")
CTRL_Z, CTRL_Y, CTRL_M, CTRL_H = _key("z", "ctrl"), _key("y", "ctrl"), _key("m", "ctrl"), _key("h", "ctrl")
K1, K2, K3, K4, O, TAB = _key("1"), _key("2"), _key("3"), _key("4"), _key("o"), _key("tab")
WHEEL_UP = Input("wheel", "UP", frozenset())


def _app(path: Path = GOLLUM) -> Application:
    app = Application()
    app.init_scene("cube")
    app.load_scene("file", scene_path=path)
    app.set_viewport_size(WIDTH, HEIGHT)
    app.key_press(K1)
    return app


def _state(app) -> dict:
    return app.scene.mesh.export_state()


def _drag(app, steps, start=(400.0, 300.0)) -> tuple[float, float]:
    """Pointer motions by the pixel steps `steps`; returns the pointer position."""
    x, y = start
    for dx, dy in steps:
        x, y = x + dx, y + dy
        app.pointer_motion(x, y, dx, dy)
    return (x, y)


def _session(app) -> SurfaceSlideGesture | None:
    session = app._gestures.session
    return session if isinstance(session, SurfaceSlideGesture) else None


def _cheek(app):
    return near(app.scene.mesh, (0.12, 0.25, 0.32), seam=False)


def _assert_symmetric(mesh) -> None:
    assert symmetry_state(mesh) is SymmetryState.VALID
    definition = mesh.symmetry_definition
    for v, c in vertex_correspondence(mesh).items():
        if c.partner is not None and c.partner != v:
            assert bits(mesh.vertex_position(c.partner)) == bits(
                mirror_position(mesh.vertex_position(v), definition.plane_point, definition.plane_normal))


# -- history, Esc, zero drag ------------------------------------------------------------------------------------------

def test_one_history_entry_undo_redo_exact_and_the_cage_stays_symmetric():
    app = _app()
    mesh = app.scene.mesh
    seed = _cheek(app)
    app.selection.vertices = {seed}
    before = _state(app)
    start = mesh.vertex_position(seed)
    assert app.key_press(J) is True
    assert app.status_message.startswith("Surface Slide: ") and "(symmetric)" in app.status_message
    assert "release J to commit" in app.status_message
    assert app.transform_command == commands.SURFACE_SLIDE
    _drag(app, [(4.0, -2.0)] * 8)
    assert mesh.vertex_position(seed) != start
    assert " h" in app.status_message
    assert app.key_release(J) is True
    assert app.status_message == "Surface Slide committed"
    after = _state(app)
    assert after != before
    assert_mesh_invariants(mesh)
    _assert_symmetric(mesh)
    assert app.key_press(CTRL_Z) is True and _state(app) == before
    assert not app.history.can_undo()
    assert app.key_press(CTRL_Y) is True and _state(app) == after
    _assert_symmetric(mesh)


def test_esc_after_motion_and_a_drag_back_to_the_press_pixel_are_bit_exact():
    app = _app()
    app.selection.vertices = {_cheek(app)}
    before = _state(app)
    app.key_press(J)
    _drag(app, [(5.0, 3.0)] * 6)
    assert _state(app) != before
    assert app.key_press(ESC) is True
    assert app.status_message == "Surface Slide cancelled"
    assert _state(app) == before and not app.history.can_undo()
    assert _session(app) is None

    app.key_press(J)
    _drag(app, [(5.0, 3.0)] * 6 + [(-5.0, -3.0)] * 6)   # back to the press pixel
    assert _state(app) == before
    assert app.status_message.startswith("Surface Slide: 0.0 h")
    app.key_release(J)
    assert _state(app) == before


def test_a_press_without_motion_writes_nothing_and_pushes_no_entry():
    app = _app()
    app.selection.vertices = {_cheek(app)}
    before = _state(app)
    assert app.key_press(J) is True
    assert app.key_release(J) is True
    assert app.status_message == "Surface Slide: no change"
    assert _state(app) == before and not app.history.can_undo()


# -- the held gesture --------------------------------------------------------------------------------------------------

def test_a_held_gesture_refuses_undo_redo_topology_mode_and_a_second_hold_key():
    app = _app()
    app.selection.vertices = {_cheek(app)}
    app.key_press(J)
    assert app.key_press(W) is False and app.key_press(G) is False   # a second hold key
    assert _session(app) is not None and _session(app).key == "j"
    _drag(app, [(4.0, 0.0)] * 5)
    shown = _state(app)
    for key in (CTRL_Z, CTRL_Y, C, K2, K3, K4):
        app.key_press(key)
        assert _state(app) == shown, key
        assert _session(app) is not None, key
    assert app.selection.mode is SelectionMode.VERTEX
    assert app.key_release(J) is True and app.history.can_undo()


# -- refusals at the press ---------------------------------------------------------------------------------------------

def test_refusals_at_the_press_reach_the_status_line_and_leave_no_session():
    app = _app()
    mesh = app.scene.mesh
    before = _state(app)
    app.selection.vertices = set()
    app.selection.hovered = None
    assert app.key_press(J) is False
    assert app.status_message == "Surface Slide: select or hover a vertex"
    assert _session(app) is None and app.transform_command is None

    seed = _cheek(app)
    app.selection.vertices = {seed}
    assert app.key_press(CTRL_M)          # mask the selection
    masked = _state(app)
    assert app.key_press(J) is False
    assert "all selected points are masked" in app.status_message and _session(app) is None
    assert app.key_press(CTRL_M)          # unmask
    assert _state(app) == masked

    # a vertex off its mirror image: weighted vertices without a partner
    x, y, z = mesh.vertex_position(seed)
    mesh.set_vertex_position(seed, (x + 1e-4, y, z))
    assert app.key_press(J) is False
    text = app.status_message   # the plan's own text, or the symmetric field's refusal passed on (§13.3 item 9)
    assert text.startswith("Surface Slide: ") and ("mirror partner" in text or "Spiegelpartner" in text), text
    assert _session(app) is None
    mesh.set_vertex_position(seed, (x, y, z))
    assert _state(app) == before


def test_object_mode_is_refused():
    app = _app()
    app.selection.vertices = {_cheek(app)}
    before = _state(app)
    app.key_press(K4)
    assert app.key_press(J) is False
    assert _session(app) is None and _state(app) == before


def test_a_posed_rig_with_a_bound_mesh_is_refused():
    from tests.test_skinning import _random_pose, _rig

    app = Application()
    app.init_scene("cube")
    app.set_viewport_size(WIDTH, HEIGHT)
    app.key_press(K1)
    rig = _rig()
    app.scene.rig = rig
    mesh = app.scene.mesh
    skin = mesh.add_point_layer(PointLayerInfo("Skin", LayerKind.WEIGHTS))
    for v in mesh.all_vertex_ids():
        mesh.set_layer_value(skin, v, ((int(rig.bone_ids()[0]), 1.0),))
    app.selection.vertices = {mesh.all_vertex_ids()[0]}
    app._skeleton.set_pose(_random_pose(random.Random(3), rig, share=1.0))
    assert app.posed
    before = _state(app)
    assert app.key_press(J) is False
    assert "is posed" in app.status_message
    assert _session(app) is None and _state(app) == before
    app._skeleton.set_pose({})
    assert app.key_press(J) is True, app.status_message
    app.key_press(ESC)


# -- morph mix (E2) ----------------------------------------------------------------------------------------------------

@functools.lru_cache(maxsize=None)
def _jaw_vertex() -> int:
    """A +X vertex with a large Jaw_Open offset (also in depth)."""
    from core.serialization import scene_from_json
    mesh = scene_from_json(MORPHS.read_text(encoding="utf-8")).mesh
    lid = next(l for l in mesh.point_layer_ids() if mesh.point_layer_info(l).name == "Jaw_Open")
    items = [(v, d) for v, d in mesh.layer_items(lid) if mesh.vertex_position(v)[0] > 0.05]
    return int(max(items, key=lambda item: abs(item[1][2]) + 0.5 * abs(item[1][1]))[0])


def _morph_app(weight: int, *, without_targets: bool = False) -> Application:
    app = _app(MORPHS)
    mesh = app.scene.mesh
    if without_targets:
        for lid in morph_target_ids(mesh):
            mesh.remove_point_layer(lid)
    else:
        lid = next(l for l in mesh.point_layer_ids() if mesh.point_layer_info(l).name == "Jaw_Open")
        app.set_morph_weight(weight, lid)
    vid = next(v for v in mesh.all_vertex_ids() if int(v) == _jaw_vertex())
    app.selection.vertices = {vid}
    return app


def _layers(mesh) -> dict:
    return {int(lid): dict(mesh.layer_items(lid)) for lid in mesh.point_layer_ids()}


def test_morph_mix_at_zero_equals_the_same_gesture_without_a_target_bit_for_bit():
    results = []
    for app in (_morph_app(0), _morph_app(0, without_targets=True)):
        assert app.key_press(J) is True, app.status_message
        _drag(app, [(3.0, -4.0)] * 6)
        app.key_release(J)
        mesh = app.scene.mesh
        results.append({int(v): bits(mesh.vertex_position(v)) for v in mesh.all_vertex_ids()})
    assert results[0] == results[1]


def test_morph_mix_at_full_slides_the_base_on_the_base_surface_mapped_at_the_drawn_depth():
    app = _morph_app(100)
    mesh = app.scene.mesh
    layers = _layers(mesh)
    press = {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()}
    drawn = {f: set(triangulate_mesh_face(mesh, f)) for f in mesh.all_face_ids()}
    shown_mesh = app._query_mesh()
    assert shown_mesh is not mesh
    assert app.key_press(J) is True, app.status_message
    gesture = _session(app)
    plan = gesture.plan
    shown = shown_mesh.vertex_position(plan.pivot)
    rest = press[plan.pivot]
    assert max(abs(a - b) for a, b in zip(shown, rest)) > 10 * plan.edge_scale * 1e-3
    assert gesture.anchor == pytest.approx(shown, abs=1e-12)
    steps = [(3.0, -4.0)] * 6
    _drag(app, steps)
    sx, sy = sum(s[0] for s in steps), sum(s[1] for s in steps)
    camera = app._objects.edit_camera
    assert gesture.delta == pytest.approx(camera.screen_delta_to_world(shown, sx, sy, WIDTH, HEIGHT), abs=1e-15)
    assert gesture.delta != pytest.approx(camera.screen_delta_to_world(rest, sx, sy, WIDTH, HEIGHT), abs=1e-9)
    # every driven base vertex on a drawn triangle of the press *base* (not of the mix)
    session = gesture.session
    cap = session.capture
    tri, bary = session.slide.anchors()
    assert np.all(bary >= 0.0)
    corners = np.array(cap.vertex_ids, dtype=object)[cap.reference.T[tri]].tolist()
    for t, vs in zip(tri.tolist(), corners):
        assert tuple(vs) in drawn[cap.triangle_face[t]]
    P = np.array([mesh.vertex_position(v) for v in plan.vertex_ids])
    for v in plan.seam_vertex_ids:
        P[plan.vertex_ids.index(v), 0] = 0.0
    A, B, Cc = (np.array([[press[c[k]] for c in corners]]).reshape(-1, 3) for k in range(3))
    assert point_triangle_distance(P, A, B, Cc).max(initial=0.0) <= 1e-12 * plan.edge_scale
    assert any(mesh.vertex_position(v) != press[v] for v in plan.vertex_ids)
    app.key_release(J)
    assert _layers(mesh) == layers          # positions only: the offsets bit-identical
    _assert_symmetric(mesh)


def test_on_a_targets_editing_view_it_slides_the_target_shape_as_w_does():
    app = _morph_app(100)
    base = app.scene.edit_object
    offsets = _layers(base.mesh)
    assert app.key_press(TAB) and app.morph_view_open
    view_mesh = app.scene.mesh
    assert view_mesh is not base.mesh and app._query_mesh() is view_mesh
    before = view_mesh.export_state()
    app.selection.vertices = {next(v for v in view_mesh.all_vertex_ids() if int(v) == _jaw_vertex())}
    assert app.key_press(J) is True, app.status_message
    _drag(app, [(3.0, -4.0)] * 6)
    app.key_release(J)
    assert app.status_message == "Surface Slide committed"
    assert view_mesh.export_state() != before
    assert _layers(base.mesh) != offsets    # the edit lands in the target's offsets
    assert app.key_press(CTRL_Z)
    assert _layers(base.mesh) == offsets


# -- Soft live, hidden faces -------------------------------------------------------------------------------------------

def test_soft_radius_steps_live_one_entry_and_esc_exact():
    app = _app()
    app.selection.vertices = {_cheek(app)}
    assert app.key_press(O) and app.soft_settings.enabled
    before = _state(app)
    for commit in (True, False):
        app.key_press(J)
        gesture = _session(app)
        assert "Soft: wheel = radius" in app.status_message
        weights = dict(zip(gesture.plan.vertex_ids, gesture.plan.weights))
        _drag(app, [(4.0, -2.0)] * 5)
        assert app.pointer_scroll(WHEEL_UP)
        assert _session(app) is gesture
        new = dict(zip(gesture.plan.vertex_ids, gesture.plan.weights))
        assert new != weights and len(new) >= len(weights)
        assert_mesh_invariants(app.scene.mesh)
        _assert_symmetric(app.scene.mesh)
        _drag(app, [(2.0, 1.0)] * 3)
        if commit:
            app.key_release(J)
            assert app.status_message == "Surface Slide committed"
            assert app.key_press(CTRL_Z) and _state(app) == before
            assert not app.history.can_undo()
        else:
            app.key_press(ESC)
            assert _state(app) == before and not app.history.can_undo()


def test_hidden_faces_are_walls_and_the_rest_of_the_mesh_stays():
    app = _app()
    mesh = app.scene.mesh
    seed = near(mesh, (0.2, 0.2, 0.3), seam=False)
    p = np.array(mesh.vertex_position(seed))
    hidden = {f for f in mesh.all_face_ids()
              if all(0.02 < (np.array(mesh.vertex_position(v)) - p)[1] < 0.12 for v in mesh.face_vertices(f))
              and all(mesh.vertex_position(v)[0] > 0.05 for v in mesh.face_vertices(f))}
    assert hidden
    app.key_press(K3)
    app.selection.faces = set(hidden)
    assert app.key_press(CTRL_H)
    app.key_press(K1)
    app.selection.vertices = {seed}
    press = {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()}
    hidden_corners = {v for f in hidden for v in mesh.face_vertices(f)}
    assert app.key_press(J) is True, app.status_message
    gesture = _session(app)
    up = app._objects.edit_camera.project_to_screen(tuple(p + (0.0, 0.3, 0.0)), WIDTH, HEIGHT)
    at = app._objects.edit_camera.project_to_screen(tuple(p), WIDTH, HEIGHT)
    dy = (up[1] - at[1]) / 30.0
    walls = False
    for _ in range(30):
        _drag(app, [(0.0, dy)])
        tri, _ = gesture.session.slide.anchors()
        assert not {gesture.session.capture.triangle_face[t] for t in tri.tolist()} & hidden
        walls |= "at a wall" in app.status_message
    assert walls                            # rows stopped at the hidden faces
    app.key_release(J)
    moved = {v for v in mesh.all_vertex_ids() if mesh.vertex_position(v) != press[v]}
    assert moved and moved <= set(gesture.plan.origins)
    assert not moved & (hidden_corners - {v for f in mesh.all_face_ids() if f not in hidden
                                          for v in mesh.face_vertices(f)})
    assert_mesh_invariants(mesh)
    _assert_symmetric(mesh)
