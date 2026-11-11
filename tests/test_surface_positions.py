"""O1 (audit 2026-11-10 §G.3, 2026-11-11): `mirai.surface_positions.SurfacePositions`, the evaluated surface of the
morph and skin stages as a position table over the base's topology.

What is pinned here (the stages' results themselves are pinned by the randomized oracles in `test_morph_multi.py`
and `test_skin_stage.py`): the view has no write path and carries no layers; its topology is the base's, live; its
journal (`watch()`) has the `MeshWatch` contract and names what its consumers read (moved / new / gone vertices,
the base's edge, face and UV records of a topology edit); the table follows the base's journal (slots freed and
reused); a `RenderMesh` patched from the view's journal equals a fresh build on the view; and the stages no longer
build a `core.Mesh` copy.
"""

from __future__ import annotations

import gc
import random

import pytest

import tests._bootstrap  # noqa: F401

import viewport.render_mesh as render_mesh_module
from core import BoneId, Mesh
from core.mesh import MeshError
from mirai import morph_mix, skinning
from mirai.morph_mix import MixSurface
from mirai.skinning import BonePose, SkinSurface
from mirai.surface_positions import SurfacePositions
from tests.test_application_delete_dissolve import _app
from tests.test_morph_multi import _targets
from tests.test_render_mesh_incremental import _grid, assert_equivalent
from tests.test_skin_stage import _bind, _bone_pose, _rig
from viewport.render_mesh import RenderMesh
from viewport.resource_store import TraceStore

#: every write and state method of `core.Mesh`: none of them exists on the view
_MESH_WRITERS = (
    "set_vertex_position", "add_vertex", "add_face", "add_edge", "remove_face", "split_edge", "collapse_edge",
    "connect_vertices", "split_face", "dissolve_vertex", "dissolve_edges", "dissolve_faces", "delete_faces",
    "delete_edges", "delete_vertices", "set_face_uvs", "add_point_layer", "remove_point_layer", "set_layer_value",
    "set_point_layer_info", "set_point_layer_order", "map_vector_layers", "load_state", "export_state",
    "apply_delta", "begin_change", "end_change", "rollback_change", "revert_change", "release_change",
)


def _shifted(mesh: Mesh, dz: float = 0.5):
    return lambda v: tuple(c + dz if k == 2 else c for k, c in enumerate(mesh.vertex_position(v)))


def test_the_view_reads_the_base_topology_and_has_no_write_path():
    base = _grid(3)
    view = SurfacePositions(base, _shifted(base))
    for name in _MESH_WRITERS:
        assert not hasattr(view, name), name
    assert view.has_point_layers() is False and view.point_layer_ids() == []
    assert view.all_vertex_ids() == base.all_vertex_ids() and view.all_face_ids() == base.all_face_ids()
    for v in base.all_vertex_ids():
        x, y, z = base.vertex_position(v)
        assert view.vertex_position(v) == (x, y, z + 0.5)
    assert view.positions() == {v: view.vertex_position(v) for v in base.all_vertex_ids()}
    assert view.symmetry_definition is base.symmetry_definition and view.face_regions is base.face_regions
    # live: a topology edit of the base is the view's topology at once; the new vertex has no position until the
    # owner writes one (the old copy did not know it either)
    edge = base.all_edge_ids()[0]
    new_v, _, _ = base.split_edge(edge)
    assert view.is_valid_vertex(new_v) and view.all_face_ids() == base.all_face_ids()
    with pytest.raises(KeyError):
        view.vertex_position(new_v)


def test_the_watch_has_the_mesh_watch_contract():
    base = _grid(2)
    view = SurfacePositions(base)
    watch = view.watch()
    assert watch.mesh is view and watch.peek().is_empty()
    v0, v1 = base.all_vertex_ids()[:2]
    p0 = view.vertex_position(v0)
    assert view._owner_write([(v0, (9.0, 9.0, 9.0)), (v1, view.vertex_position(v1))]) == {v0}  # equal: no record
    assert view._owner_write([(v0, (8.0, 8.0, 8.0))]) == {v0}
    change = watch.take()
    assert dict(change.vertices) == {v0: p0}  # the first record wins: the position at the last take
    assert not (change.edges or change.faces or change.face_uvs) and watch.peek().is_empty()
    # topology: the base's records of the edit are forwarded, a vertex that went is named with its last position
    other = view.watch()
    keys = base.watch()  # what a stage's watch of the base holds
    before = view.positions()
    base.delete_vertices([base.all_vertex_ids()[4]])  # the inner vertex: its faces go, and what they alone held
    gone = [v for v in before if not base.is_valid_vertex(v)]
    change = keys.take()
    assert change.faces and change.edges and gone
    view._owner_follow_topology(change)
    got = other.take()
    assert got.faces == change.faces and got.edges == change.edges and got.face_uvs == change.face_uvs
    assert got.vertices == {v: before[v] for v in gone}  # the last shown position (v0's is the owner's 8, 8, 8)
    for v in gone:
        with pytest.raises(KeyError):
            view.vertex_position(v)
    # close and garbage collection stop the recording
    other.close()
    assert len(view._logs) == 1
    del watch
    gc.collect()
    assert view._logs == []


def test_slots_are_freed_and_reused():
    base = _grid(3)
    view = SurfacePositions(base)
    capacity = len(view._pos)
    rng = random.Random(4)
    for _ in range(30):
        edge = rng.choice(base.all_edge_ids())
        watch = base.watch()
        vid, _, _ = base.split_edge(edge, 0.5)
        view._owner_follow_topology(watch.take())
        view._owner_write([(vid, base.vertex_position(vid))])
        watch = base.watch()
        try:
            base.collapse_edge(rng.choice(base.vertex_edges(vid)))
        except MeshError:
            continue
        change = watch.take()
        view._owner_follow_topology(change)
        view._owner_write([(v, base.vertex_position(v)) for v in change.vertices if base.is_valid_vertex(v)])
        assert set(view.positions()) == set(base.all_vertex_ids())
    assert len(view._pos) <= capacity + 1  # one vertex in flight at a time: one extra slot at most
    assert all(view.vertex_position(v) == base.vertex_position(v) for v in base.all_vertex_ids())


@pytest.fixture
def _incremental(monkeypatch):
    monkeypatch.setattr(render_mesh_module, "INCREMENTAL_MIN_ELEMENTS", 0)
    monkeypatch.setattr(render_mesh_module, "SPARE_FRACTION", 0.5)


def test_a_render_mesh_patched_from_the_view_equals_a_fresh_build(_incremental):
    """The viewport's surface RenderMesh reads the view and its journal: after weight steps and topology edits of the
    base (each followed by the stage update), the patched buffers hold what a fresh RenderMesh of the view holds."""
    app = _app(4)
    mesh = app.scene.mesh
    lids = _targets(app, 2, seed=3, every=1)
    surface = MixSurface(mesh)
    surface.update({lids[0]: 60})
    rm = RenderMesh(surface.mesh, overlay=None, store_type=TraceStore)
    rng = random.Random(8)
    for step in range(40):
        op = rng.randrange(4)
        if op == 0:
            weights = {lid: rng.choice((0, 30, 100)) for lid in lids}
        else:
            weights = dict(surface.weights) or {lids[1]: 40}
            if op == 1:
                app.apply_mesh_change("split", lambda: mesh.split_edge(rng.choice(mesh.all_edge_ids())) and None)
            elif op == 2:
                face = rng.choice([f for f in mesh.all_face_ids() if len(mesh.face_vertices(f)) >= 4])
                a, _, c = mesh.face_vertices(face)[:3]
                app.apply_mesh_change("connect", lambda: mesh.connect_vertices(face, a, c) and None)
            elif app.history.can_undo():
                app.history.undo()
        rebuilt, moved = surface.update(weights)
        assert not rebuilt
        if surface.topology_changed:
            rm.mark_topology_dirty()
        elif moved:
            rm.mark_vertices_dirty(moved)
        rm.sync()
        assert_equivalent(rm)
        assert surface.mesh.positions() == morph_mix.evaluate(mesh, surface.weights)


def test_the_stages_build_no_mesh_copy(monkeypatch):
    """O1: neither stage goes through `Mesh.from_state` / `export_state` any more, and the surfaces are views."""
    app = _app(3)
    mesh = app.scene.mesh
    lids = _targets(app, 1, seed=1, every=1)
    _bind(mesh, random.Random(2))
    rig = _rig(mesh)

    def refused(*_args, **_kwargs):
        raise AssertionError("a stage built a core.Mesh copy")

    monkeypatch.setattr(Mesh, "from_state", classmethod(refused))
    monkeypatch.setattr(Mesh, "export_state", refused)
    mix = MixSurface(mesh)
    mix.update({lids[0]: 70})
    skin = SkinSurface(mesh, mix.mesh)
    pose = {BoneId(1): _bone_pose(random.Random(5))}
    skin.update(rig, pose, None)
    assert isinstance(mix.mesh, SurfacePositions) and isinstance(skin.mesh, SurfacePositions)
    assert mix.mesh.base is mesh and skin.mesh.base is mesh
    expected = skinning.evaluate(mesh, morph_mix.evaluate(mesh, {lids[0]: 70}), rig, pose)
    assert skin.mesh.positions() == expected
    # the pose back to rest: the skinned surface is the mix again, exactly
    skin.update(rig, {BoneId(1): BonePose()}, None)
    assert skin.mesh.positions() == mix.mesh.positions()
