"""Stage 1 (V0 + V2 + V3 + H0) against the unchanged code, headless (TraceStore, no pyglet).

After every step the patched viewport's `RenderMesh` must hold what a fresh `RenderMesh` built with the
original code holds for the same mesh: index map, triangles, face rows, adjacency, buffers; normals within 1e-9
(a vertex normal is a sum over a `set` of faces whose iteration order may differ). Undo / Redo must restore the
exact `export_state()` of before / after the op (H0's lazy after-state).
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from topology_sync_stage1 import stage1

from core import EdgeId, FaceId
from mirai.application import Application
from mirai.interaction.input import Input
from viewport.render_mesh import FACE_DATA, TRIANGLE_FACES, RenderMesh
from viewport.resource_store import TraceStore

REPO = Path(__file__).resolve().parents[3]
HEAD = REPO / "examples" / "meshes" / "head_basemesh.obj"
W, H = 1024, 768
TOL = 1e-9


def key(name: str, *mods: str) -> Input:
    return Input("key", name, frozenset(mods))


CTRL_Z, CTRL_Y = key("z", "ctrl"), key("y", "ctrl")


@pytest.fixture(params=["all", "V0,V3", "V0,V2", "V3", "H0"])
def switches(request):
    installed = stage1.install(request.param)
    yield installed
    stage1.uninstall()


def make_app() -> Application:
    app = Application()
    app.init_scene("obj", obj_path=HEAD)
    app.set_viewport_size(W, H)
    app.frame_scene()
    app.viewport.sync()
    return app


def reference(mesh) -> RenderMesh:
    active = stage1.active()
    stage1.uninstall()
    try:
        return RenderMesh(mesh, None, TraceStore)
    finally:
        stage1.install(active)


def close(a, b) -> bool:
    return len(a) == len(b) and all(math.isclose(x, y, rel_tol=0.0, abs_tol=TOL) for x, y in zip(a, b))


def assert_equivalent(app: Application) -> None:
    app.viewport.sync()
    rm = app.viewport.render_mesh
    ref = reference(app.scene.mesh)
    assert rm._vertex_index == ref._vertex_index
    assert list(rm._vertex_index) == list(ref._vertex_index)
    assert rm._triangle_indices == ref._triangle_indices
    assert rm._face_row == ref._face_row
    assert rm._triangle_face_rows == ref._triangle_face_rows
    assert rm.derived.vertex_to_faces == ref.derived.vertex_to_faces
    assert rm.derived.face_normals.keys() == ref.derived.face_normals.keys()
    for f, n in ref.derived.face_normals.items():
        assert close(rm.derived.face_normals[f], n), f
    assert rm.derived.vertex_normals.keys() == ref.derived.vertex_normals.keys()
    for v, n in ref.derived.vertex_normals.items():
        assert close(rm.derived.vertex_normals[v], n), v
    assert rm.derived.bounds_min == ref.derived.bounds_min
    assert rm.derived.bounds_max == ref.derived.bounds_max
    got, want = rm.store, ref.store
    for name in ("positions", "indices", TRIANGLE_FACES):
        assert list(got.data(name)) == list(want.data(name)), name
    for name in ("normals", FACE_DATA):
        assert close(list(got.data(name)), list(want.data(name))), name
    flags = rm.overlay.build_highlight_flags(app.scene.mesh)
    assert list(got.data("highlight_flags")) == list(flags)


def select_faces(app: Application, faces) -> None:
    app.key_press(key("3"))
    app.selection.set({FaceId(f) for f in faces})
    app.viewport.on_selection_changed()


def front_face(app: Application) -> int:
    """The face whose centroid is nearest the camera eye."""
    mesh, cam = app.scene.mesh, app.camera
    best = None
    for f in mesh.all_face_ids():
        pts = [mesh.vertex_position(v) for v in mesh.face_vertices(f)]
        c = tuple(sum(p[i] for p in pts) / len(pts) for i in range(3))
        d = math.dist(c, cam.eye())
        if best is None or d < best[0]:
            best = (d, f)
    return best[1]


def screen_centroid(app: Application, f) -> tuple[float, float]:
    mesh = app.scene.mesh
    pts = [app.camera.project_to_screen(mesh.vertex_position(v), W, H) for v in mesh.face_vertices(f)]
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def undo_redo_roundtrip(app: Application, before: dict, after: dict) -> None:
    mesh = app.scene.mesh
    assert app.key_press(CTRL_Z) is not False
    assert mesh.export_state()["faces"] == before["faces"]
    assert mesh.export_state()["vertices"] == before["vertices"]
    assert_equivalent(app)
    app.key_press(CTRL_Y)
    state = mesh.export_state()
    assert state["faces"] == after["faces"] and state["vertices"] == after["vertices"]
    assert state["edges"] == after["edges"]
    assert_equivalent(app)
    app.key_press(CTRL_Z)
    assert_equivalent(app)


def test_initial_build(switches):
    assert_equivalent(make_app())


def test_delete_dissolve_undo_redo(switches):
    app = make_app()
    mesh = app.scene.mesh
    f = front_face(app)
    before = mesh.export_state()
    select_faces(app, [f])
    app.key_press(key("delete"))
    after = mesh.export_state()
    assert after != before
    assert_equivalent(app)
    undo_redo_roundtrip(app, before, after)

    edge = mesh.face_edges(mesh.all_face_ids()[5])[0]
    app.key_press(key("2"))
    app.selection.set({EdgeId(edge)})
    app.viewport.on_selection_changed()
    before = mesh.export_state()
    app.key_press(key("backspace"))
    after = mesh.export_state()
    assert after != before
    assert_equivalent(app)
    undo_redo_roundtrip(app, before, after)


def test_positions_only_change_and_undo(switches):
    """W-like move through `apply_mesh_change` (geometry path), then Undo / Redo (topology-dirty path:
    with V2 a patch, else a full rebuild)."""
    app = make_app()
    mesh = app.scene.mesh
    vs = mesh.all_vertex_ids()[:40]
    before = mesh.export_state()

    def mutate():
        for v in vs:
            x, y, z = mesh.vertex_position(v)
            mesh.set_vertex_position(v, (x + 0.05, y - 0.02, z + 0.03))
        return set(vs)

    assert app.apply_mesh_change("move", mutate)
    assert_equivalent(app)
    after = mesh.export_state()
    undo_redo_roundtrip(app, before, after)


def test_move_then_topology_then_undo_back(switches):
    """A moved vertex whose position returns to the cached one must still get its normals recomputed
    (the geometry sync changed them in between): move, sync, delete, undo, undo."""
    app = make_app()
    mesh = app.scene.mesh
    f = front_face(app)
    vs = mesh.face_vertices(f)

    def mutate():
        for v in vs:
            x, y, z = mesh.vertex_position(v)
            mesh.set_vertex_position(v, (x, y, z + 0.2))
        return set(vs)

    app.apply_mesh_change("move", mutate)
    assert_equivalent(app)
    other = next(g for g in mesh.all_face_ids() if g != f and not set(mesh.face_vertices(g)) & set(vs))
    select_faces(app, [other])
    app.key_press(key("delete"))
    assert_equivalent(app)
    app.key_press(CTRL_Z)
    assert_equivalent(app)
    app.key_press(CTRL_Z)
    assert_equivalent(app)


def test_boundary_change_with_same_ids(switches):
    """Rotating face boundaries (same vertices, same IDs, same lists) changes the fan diagonal: the
    structure is not "unchanged", so V2 must not patch."""
    app = make_app()
    mesh = app.scene.mesh
    quads = [f for f in mesh.all_face_ids() if len(mesh.face_vertices(f)) == 4][:30]
    before = mesh.export_state()

    def mutate():
        state = mesh.export_state()
        for f in quads:
            b = state["faces"][int(f)]
            state["faces"][int(f)] = b[1:] + b[:1]
        mesh.load_state(state)
        return None

    assert app.apply_mesh_change("rotate boundaries", mutate)
    assert_equivalent(app)
    undo_redo_roundtrip(app, before, mesh.export_state())


def test_extrude_gesture_undo_redo(switches):
    app = make_app()
    mesh = app.scene.mesh
    f = front_face(app)
    cx, cy = screen_centroid(app, f)
    select_faces(app, [f])
    app.pointer_motion(cx, cy)
    app.viewport.sync()
    before = mesh.export_state()
    stage1.reset_stats()
    app.key_press(key("t"))
    app.pointer_motion(cx, cy + 8.0, 0.0, 8.0)
    assert_equivalent(app)
    app.pointer_motion(cx, cy + 16.0, 0.0, 8.0)
    assert_equivalent(app)
    app.key_release(key("t"))
    after = mesh.export_state()
    assert len(after["faces"]) > len(before["faces"])
    assert_equivalent(app)
    if "V2" in switches:
        # begin = one full rebuild; release = a patch (the structure did not change since begin)
        assert stage1.STATS.full_buffer_rebuilds == 1
        assert stage1.STATS.patch_syncs >= 1
    undo_redo_roundtrip(app, before, after)


def test_h0_lazy_after_state():
    stage1.install("H0")
    try:
        app = make_app()
        mesh = app.scene.mesh
        select_faces(app, [front_face(app)])
        before = mesh.export_state()
        stage1.reset_stats()
        app.key_press(key("delete"))
        assert stage1.STATS.counts_decided_changed == 1
        cmd = app.history._undo_stack[-1]  # private, test only
        assert isinstance(cmd, stage1.LazyAfterMeshStateCommand) and cmd.after_state is None
        after = mesh.export_state()
        undo_redo_roundtrip(app, before, after)
        assert stage1.STATS.lazy_after_exports == 1
    finally:
        stage1.uninstall()


def test_parse():
    assert stage1.parse("all") == frozenset(stage1.ALL)
    assert stage1.parse("none") == frozenset()
    assert stage1.parse("v0, v3") == {"V0", "V3"}
    with pytest.raises(ValueError):
        stage1.parse("V2")
    with pytest.raises(ValueError):
        stage1.parse("V9")


def test_uninstall_restores_originals():
    original = RenderMesh.__dict__["_sync_topology"]
    stage1.install("all")
    assert RenderMesh.__dict__["_sync_topology"] is not original
    stage1.uninstall()
    assert RenderMesh.__dict__["_sync_topology"] is original
    assert Application.__dict__["_mesh_transaction"].__name__ == "_mesh_transaction"
