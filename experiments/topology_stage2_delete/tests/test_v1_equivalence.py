"""V1 (patched buffers) against a fresh `RenderMesh` built with the original code, headless (TraceStore).

V1 keeps slots (a dead face's triangles degenerate, a dead vertex's slot unused), so the layout differs from a
fresh build; the comparison is **per element**: every live face draws the same triangles (same vertex IDs, same
order) and has the same face row, every live vertex has the same position and normal (normals within 1e-9: a
vertex normal sums over a `set`), the index buffer holds exactly those triangles at the face's range and nothing
but degenerate triangles elsewhere, `triangle_faces` maps every live triangle to its face's row, adjacency and
face normals match, the highlight flags sit at the vertex slots, the stage-1 V0 cache matches the mesh. Steps:
Delete in all three modes, Undo / Redo, several entries deep, a W move in between (stage-1 V2 path), and a
Dissolve (a full V0 sync: compaction) followed by Undo through the whole stack (the revival falls back).
"""

from __future__ import annotations

import math
import random
from pathlib import Path

import pytest

from topology_stage2_delete import render_patch, stage2
from topology_sync_stage1 import stage1

from core import EdgeId, FaceId, VertexId
from core.selection import SelectionMode
from mirai.application import Application
from mirai.interaction.input import Input
from viewport.render_mesh import FACE_DATA, FACE_ROW_FLOATS, TRIANGLE_FACES, RenderMesh
from viewport.resource_store import TraceStore

REPO = Path(__file__).resolve().parents[3]
HEAD = REPO / "examples" / "meshes" / "head_basemesh.obj"
TOL = 1e-9
MODE_KEYS = {SelectionMode.VERTEX: "1", SelectionMode.EDGE: "2", SelectionMode.FACE: "3"}


def key(name: str, *mods: str) -> Input:
    return Input("key", name, frozenset(mods))


DELETE, CTRL_Z, CTRL_Y = key("delete"), key("z", "ctrl"), key("y", "ctrl")


@pytest.fixture
def app():
    stage2.install("all")
    a = Application()
    a.init_scene("obj", obj_path=HEAD)
    a.set_viewport_size(800, 600)
    a.frame_scene()
    a.viewport.sync()
    render_patch.reset_stats()
    yield a
    stage2.uninstall()


def reference(mesh, selection_overlay) -> RenderMesh:
    stage2.uninstall()
    try:
        return RenderMesh(mesh, selection_overlay, TraceStore)
    finally:
        stage2.install("all")


def close(a, b) -> bool:
    return len(a) == len(b) and all(math.isclose(x, y, rel_tol=0.0, abs_tol=TOL) for x, y in zip(a, b))


def assert_equivalent(app: Application) -> None:
    app.viewport.sync()
    mesh, rm = app.scene.mesh, app.viewport.render_mesh
    ref = reference(mesh, rm.overlay)
    st = render_patch.slots(rm)
    got, want = rm.store, ref.store
    live_faces = mesh.all_face_ids()
    live_vertices = mesh.all_vertex_ids()

    covered: set = set()
    indices = list(got.data("indices"))
    tri_rows = list(got.data(TRIANGLE_FACES))
    for f in live_faces:
        t0, n = render_patch._triangle_range(rm, rm._face_row[f])
        r0, rn = render_patch._triangle_range(ref, ref._face_row[f])
        assert rm._triangle_indices[t0:t0 + n] == ref._triangle_indices[r0:r0 + rn], f
        for t in range(t0, t0 + n):
            tri = rm._triangle_indices[t]
            assert indices[3 * t:3 * t + 3] == [float(rm._vertex_index[v]) for v in tri], f
            assert tri_rows[t] == float(rm._face_row[f])
            covered.add(t)
        row, ref_row = rm._face_row[f] * FACE_ROW_FLOATS, ref._face_row[f] * FACE_ROW_FLOATS
        assert close(list(got.data(FACE_DATA))[row:row + FACE_ROW_FLOATS],
                     list(want.data(FACE_DATA))[ref_row:ref_row + FACE_ROW_FLOATS]), f
    for t in range(len(rm._triangle_indices)):
        if t not in covered:
            a, b, c = indices[3 * t:3 * t + 3]
            assert a == b == c, f"triangle {t} is not live and not degenerate"
    assert {f for f in rm._face_row if f not in st.dead_faces} == set(live_faces)

    positions, normals = list(got.data("positions")), list(got.data("normals"))
    ref_normals = list(want.data("normals"))
    for v in live_vertices:
        i, j = rm._vertex_index[v], ref._vertex_index[v]
        assert positions[3 * i:3 * i + 3] == list(mesh.vertex_position(v)), v
        assert close(normals[3 * i:3 * i + 3], ref_normals[3 * j:3 * j + 3]), v
    for v in st.dead_vertices:
        i = rm._vertex_index[v]
        assert positions[3 * i:3 * i + 3] == render_patch.DEAD_POSITION
    assert {v for v in rm._vertex_index if v not in st.dead_vertices} == set(live_vertices)

    assert rm.derived.vertex_to_faces == ref.derived.vertex_to_faces
    assert rm.derived.face_normals.keys() == ref.derived.face_normals.keys()
    for f, n in ref.derived.face_normals.items():
        assert close(rm.derived.face_normals[f], n), f
    assert rm.derived.vertex_normals.keys() == ref.derived.vertex_normals.keys()
    assert rm.derived.bounds_min == ref.derived.bounds_min
    assert rm.derived.bounds_max == ref.derived.bounds_max

    flags, ref_flags = list(got.data("highlight_flags")), list(want.data("highlight_flags"))
    for v in live_vertices:
        assert flags[rm._vertex_index[v]] == ref_flags[ref._vertex_index[v]], v

    cache = stage1._cache(rm)
    assert set(cache.faces) == set(live_faces)
    assert set(cache.positions) == set(live_vertices)
    assert cache.vids == live_vertices and cache.fids == live_faces


def delete(app: Application, mode: SelectionMode, ids) -> None:
    app.key_press(key(MODE_KEYS[mode]))
    app.selection.set(set(ids))
    app.viewport.on_selection_changed()
    assert app.key_press(DELETE), app.status_message


def pool(mesh, mode):
    return {SelectionMode.VERTEX: mesh.all_vertex_ids, SelectionMode.EDGE: mesh.all_edge_ids,
            SelectionMode.FACE: mesh.all_face_ids}[mode]()


@pytest.mark.parametrize("seed", range(4))
def test_delete_undo_redo_patch_equals_fresh_build(app, seed):
    rng = random.Random(seed)
    mesh = app.scene.mesh
    assert_equivalent(app)
    depth = 4
    for _ in range(depth):
        mode = rng.choice(list(MODE_KEYS))
        delete(app, mode, rng.sample(pool(mesh, mode), rng.randint(1, 20)))
        assert_equivalent(app)
    for _ in range(depth):
        app.key_press(CTRL_Z)
        assert_equivalent(app)
    for _ in range(depth):
        app.key_press(CTRL_Y)
        assert_equivalent(app)
    assert render_patch.STATS.v1_fallbacks == 0
    assert render_patch.STATS.v1_patches == 3 * depth


def test_two_steps_without_a_sync_in_between(app):
    """Delete then Undo (and Undo then Redo) before any frame: the patch applies the net effect."""
    mesh = app.scene.mesh
    delete(app, SelectionMode.FACE, mesh.all_face_ids()[40:45])
    app.key_press(CTRL_Z)
    assert_equivalent(app)
    app.key_press(CTRL_Y)
    app.key_press(CTRL_Z)
    app.key_press(CTRL_Y)
    assert_equivalent(app)


def test_w_move_between_deletes_and_dissolve_compaction(app):
    mesh = app.scene.mesh
    delete(app, SelectionMode.FACE, mesh.all_face_ids()[60:66])
    assert_equivalent(app)
    vid = mesh.all_vertex_ids()[200]
    x, y, z = mesh.vertex_position(vid)

    def move():
        mesh.set_vertex_position(vid, (x + 0.01, y, z))
        return {vid}

    assert app.apply_mesh_change("move", move)
    assert_equivalent(app)
    delete(app, SelectionMode.VERTEX, [mesh.all_vertex_ids()[300]])
    assert_equivalent(app)
    # A Dissolve takes the stage-1 path: full V0 sync, compacted layout.
    app.key_press(key("2"))
    edge = next(e for e in mesh.all_edge_ids() if len(mesh.edge_faces(e)) == 2)
    app.selection.set({EdgeId(edge)})
    assert app.key_press(key("backspace")), app.status_message
    assert_equivalent(app)
    for _ in range(4):
        app.key_press(CTRL_Z)
        assert_equivalent(app)
    for _ in range(4):
        app.key_press(CTRL_Y)
        assert_equivalent(app)
    # The Undo of the deletes made before the compaction has no slots left: one fallback each way.
    assert render_patch.STATS.v1_fallbacks >= 1
