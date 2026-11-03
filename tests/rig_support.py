"""Shared setup of the AD-028 app tests (T-6 `test_application_rig.py`, T-7 `test_jaw_scenario.py`): a head (or the
SubD cube) in the scenario driver of AD-027 (`tests/interaction_trace.py`), its jaw-like faces, a Working Pivot on
the symmetry plane placed with a real click, and the bone keys as code defaults."""

from __future__ import annotations

import tests._bootstrap  # noqa: F401
from core import SelectionMode
from mirai.skinning import skin_layer
from tests.interaction_trace import HEIGHT, OVERLAYS, WIDTH, Driver, _frame, key

from loaders.assets import asset_path

#: The rig keys (code defaults, AD-028 §8.3; `PROVISIONAL`).
POSE_MODE, POSE_TOGGLE, POSE_RESET = key("5"), key("6"), key("6", "alt")
FALLOFF, WEIGHT = key("7"), key("8")
BONE_ADD, BONE_RENAME, BONE_DELETE = key("j", "ctrl"), key("j", "ctrl", "shift"), key("j", "alt", "shift")
BONE_NEXT, BONE_PREVIOUS = key("j", "alt"), key("j", "ctrl", "alt")
P, E, W, R, I, O = key("p"), key("e"), key("w"), key("r"), key("i"), key("o")
CTRL_G, SHIFT_S = key("g", "ctrl"), key("s", "shift")


def head_driver(symmetric: bool = True, asset: str = "head_basemesh", driver=Driver) -> Driver:
    """The asset framed in the driver's window, symmetry X on (Shift+S) if asked, the camera in front of it (yaw 0)
    so that a click on the plane's projection places the Working Pivot on the plane. `driver`: the driver class (E5
    (iv) swaps in one that checks `can_run` at every step)."""
    d = driver("cube")
    app = d.app
    app.init_scene("obj", obj_path=asset_path(asset), **OVERLAYS)
    _frame(app)
    if symmetric:
        d.tap(SHIFT_S)
    app.camera.set_view(0.0, 0.15)
    app.set_viewport_size(WIDTH, HEIGHT)
    app.update_viewport(0)
    return d


def jaw_faces(mesh, share: float = 0.2) -> set:
    """The jaw-like region: the front faces (centre z > 0) in the lowest `share` of the height."""
    centres = {f: [sum(mesh.vertex_position(v)[i] for v in mesh.face_vertices(f)) / len(mesh.face_vertices(f))
                   for i in range(3)] for f in mesh.all_face_ids()}
    ys = [c[1] for c in centres.values()]
    cut = min(ys) + share * (max(ys) - min(ys))
    return {f for f, c in centres.items() if c[1] <= cut and c[2] > 0.0}


def select_faces(d: Driver, faces) -> None:
    """Setup: face mode (`3`) and these faces selected (a selection, as a box would leave it)."""
    app = d.app
    d.tap(key("3"))
    app.selection.faces = set(faces)
    app.viewport.on_selection_changed()


def place_pivot(d: Driver, world_point) -> None:
    """Hold P and click where `world_point` projects (the pivot lands inside the volume under the cursor)."""
    x, y = d.app.camera.project_to_screen(world_point, WIDTH, HEIGHT)
    d.key_down(P)
    d.click(x, y)
    d.key_up("p")


def hinge_point(mesh) -> tuple:
    """A point on the symmetry plane at about two thirds of the head's height, a little in front of its middle."""
    ys = [mesh.vertex_position(v)[1] for v in mesh.all_vertex_ids()]
    return (0.0, min(ys) + 0.45 * (max(ys) - min(ys)), 0.0)


def rig_head(d: Driver, *, group: bool = True) -> None:
    """Jaw faces as group "Group 1", the pivot on the plane, one bone from there to the jaw's centre (Ctrl+J)."""
    app = d.app
    mesh = app.scene.mesh
    select_faces(d, jaw_faces(mesh))
    if group:
        d.tap(CTRL_G)
    place_pivot(d, hinge_point(mesh))
    assert app.active_pivot is not None, app.status_message
    d.tap(BONE_ADD)
    assert app.scene.rig is not None and len(app.scene.rig.bones) >= 1, app.status_message


def hold(d: Driver, inp, steps=((20, 0),)) -> None:
    d.key_down(inp)
    for dx, dy in steps:
        d.nudge(dx, dy)
    d.key_up(inp.value)


def weights(mesh) -> dict:
    lid = skin_layer(mesh)
    return {} if lid is None else dict(mesh.layer_items(lid))


def component_mode(d: Driver, mode=SelectionMode.VERTEX) -> None:
    d.tap(key({SelectionMode.VERTEX: "1", SelectionMode.EDGE: "2", SelectionMode.FACE: "3"}[mode]))

