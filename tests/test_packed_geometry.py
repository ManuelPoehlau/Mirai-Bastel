"""O3 stage 1 (AD-032): `RenderMesh` computes its normals on slot-indexed arrays (`viewport.packed_geometry`).

Pinned here:
- the arrays are **bit-identical** to the pure-Python reference (`derived.face_normal`, `derived.DerivedGeometry`, whose
  vertex normals add the faces in ascending FaceId order) - after a full build, after position patches of any size,
  and after topology patches (random sequences with Undo / Redo) - on quads, triangles, n-gons, a high-valence pole,
  degenerate faces and the reference assets;
- the ragged pools (corner lists, vertex -> faces lists) keep every list through relocation and compaction;
- the id view `RenderMesh.derived` reads the arrays; the store receives exactly the float32 rounding of the arrays;
- the import boundary: NumPy above the Core only, and a missing / unusable NumPy names the pinned version.
"""

from __future__ import annotations

import ast
import importlib.util
import random
import sys
from array import array
from pathlib import Path

import numpy as np
import pytest

import tests._bootstrap  # noqa: F401

import viewport.render_mesh as render_mesh_module
from core import HistoryStack
from core.mesh import Mesh, MeshError
from core.operations import MeshDeltaCommand, record_mesh_change
from viewport.derived import DerivedGeometry, face_normal
from viewport.packed_geometry import Ragged
from viewport.render_mesh import RenderMesh
from viewport.resource_store import TraceStore

REPO = Path(__file__).resolve().parent.parent


def _grid(n: int, seed: int = 0) -> Mesh:
    rng = random.Random(seed)
    mesh = Mesh()
    ids = [[mesh.add_vertex((float(x) + rng.uniform(-0.2, 0.2), float(y) + rng.uniform(-0.2, 0.2),
                             rng.uniform(-0.5, 0.5))) for x in range(n + 1)] for y in range(n + 1)]
    for y in range(n):
        for x in range(n):
            mesh.add_face([ids[y][x], ids[y][x + 1], ids[y + 1][x + 1], ids[y + 1][x]])
    return mesh


def _mixed() -> Mesh:
    """Triangles, quads, a pentagon, a 9-gon, a fan pole of valence 12, a face with three collinear corners, a face
    without area, and a vertex without faces."""
    mesh = _grid(3, seed=4)
    faces = mesh.all_face_ids()
    mesh.split_face(faces[0], mesh.face_vertices(faces[0])[0], mesh.face_vertices(faces[0])[2], [])  # two triangles
    mesh.dissolve_faces(faces[4:6], cleanup=False)  # a hexagon-ish merge
    centre = mesh.add_vertex((10.0, 10.0, 1.0))
    ring = [mesh.add_vertex((10.0 + np.cos(a), 10.0 + np.sin(a), 0.1 * np.sin(3 * a)))
            for a in np.linspace(0.0, 2 * np.pi, 12, endpoint=False)]
    for i in range(12):
        mesh.add_face([centre, ring[i], ring[(i + 1) % 12]])
    nine = [mesh.add_vertex((20.0 + np.cos(a), np.sin(a), 0.2 * np.cos(2 * a)))
            for a in np.linspace(0.0, 2 * np.pi, 9, endpoint=False)]
    mesh.add_face(nine)
    line = [mesh.add_vertex(p) for p in ((30.0, 0.0, 0.0), (31.0, 0.0, 0.0), (32.0, 0.0, 0.0), (31.0, 1.0, 0.0))]
    mesh.add_face(line)  # first three corners collinear: Newell, not the first triangle
    flat = [mesh.add_vertex(p) for p in ((40.0, 0.0, 0.0), (41.0, 0.0, 0.0), (42.0, 0.0, 0.0))]
    mesh.add_face(flat)  # no area: (0, 0, 0)
    mesh.add_vertex((50.0, 0.0, 0.0))  # no faces
    return mesh


def assert_bit_identical(rm: RenderMesh) -> None:
    """Every live face / vertex normal in the arrays == the pure-Python reference, float for float."""
    mesh = rm.mesh
    reference = DerivedGeometry(mesh)
    packed = rm.packed
    positions = {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()}
    for f in mesh.all_face_ids():
        row = rm._face_row[f]
        got = tuple(packed.FN[row].tolist())
        assert got == face_normal(positions, mesh.face_vertices(f)) == reference.face_normals[f], f
    for v in mesh.all_vertex_ids():
        slot = rm.vertex_index_of(v)
        assert tuple(packed.VN[slot].tolist()) == reference.vertex_normals[v], v
        assert tuple(packed.P[slot].tolist()) == mesh.vertex_position(v)


@pytest.mark.parametrize("make", [lambda: _grid(5), _mixed], ids=["grid", "mixed"])
def test_a_full_build_is_bit_identical_to_the_reference(make):
    rm = RenderMesh(make(), store_type=TraceStore)
    assert_bit_identical(rm)


@pytest.mark.parametrize("asset", ["head_basemesh.obj", "gollum_20k.obj"])
def test_the_reference_assets_are_bit_identical_after_build_and_a_region_move(asset):
    from tests.soft_selection_fixtures import HEAD_OBJ  # noqa: F401  (puts `examples/`, the OBJ loader, on the path)

    from loaders.obj_loader import load_obj
    from mirai.scene_factory import mesh_from_positions_and_faces

    data = load_obj(REPO / "examples" / "meshes" / asset)
    mesh = mesh_from_positions_and_faces(data.vertices, data.faces)
    rm = RenderMesh(mesh, store_type=TraceStore)
    assert_bit_identical(rm)
    vids = mesh.all_vertex_ids()
    moved = set(vids[::5])
    for v in moved:
        x, y, z = mesh.vertex_position(v)
        mesh.set_vertex_position(v, (x * 1.01 + 0.003, y - 0.002, z + 0.0007 * x))
    rm.mark_vertices_dirty(moved)
    rm.sync()
    assert_bit_identical(rm)


@pytest.mark.parametrize("share", [1, 30, 100])
def test_position_patches_of_any_size_stay_bit_identical(share):
    mesh = _mixed()
    rm = RenderMesh(mesh, store_type=TraceStore)
    rng = random.Random(share)
    vids = mesh.all_vertex_ids()
    for _ in range(5):
        moved = set(rng.sample(vids, max(1, len(vids) * share // 100)))
        for v in moved:
            x, y, z = mesh.vertex_position(v)
            mesh.set_vertex_position(v, (x + rng.uniform(-0.3, 0.3), y + rng.uniform(-0.3, 0.3), z * 0.9))
        rm.mark_vertices_dirty(moved)
        rm.sync()
        assert_bit_identical(rm)


def _op(mesh: Mesh, rng: random.Random) -> None:
    faces, edges, vertices = mesh.all_face_ids(), mesh.all_edge_ids(), mesh.all_vertex_ids()
    kind = rng.choice(["split_edge", "split_face", "dissolve_edges", "delete_faces", "delete_vertices", "extrude"])
    if kind == "split_edge" and edges:
        mesh.split_edge(rng.choice(edges), rng.uniform(0.2, 0.8))
    elif kind == "split_face" and faces:
        f = rng.choice(faces)
        b = mesh.face_vertices(f)
        if len(b) >= 4:
            mesh.split_face(f, b[0], b[2], [])
    elif kind == "dissolve_edges" and edges:
        mesh.dissolve_edges([rng.choice(edges)], cleanup=rng.random() < 0.5)
    elif kind == "delete_faces" and faces:
        mesh.delete_faces(rng.sample(faces, min(len(faces), 2)))
    elif kind == "delete_vertices" and vertices:
        mesh.delete_vertices([rng.choice(vertices)])
    elif kind == "extrude" and faces:
        f = rng.choice(faces)
        b = mesh.face_vertices(f)
        top = [mesh.add_vertex(tuple(c + (0.4 if k == 2 else 0.05) for k, c in enumerate(mesh.vertex_position(v))))
               for v in b]
        for i in range(len(b)):
            mesh.add_face([b[i], b[(i + 1) % len(b)], top[(i + 1) % len(b)], top[i]])
        mesh.add_face(top)
        mesh.remove_face(f)


@pytest.mark.parametrize("seed", range(4))
def test_topology_patches_stay_bit_identical_and_the_pools_survive_compaction(seed, monkeypatch):
    """Long random sequences on the patch path (relocated lists, compacted pools), Undo / Redo and position moves
    between them; after every sync the arrays equal the reference float for float."""
    monkeypatch.setattr(render_mesh_module, "INCREMENTAL_MIN_ELEMENTS", 0)
    monkeypatch.setattr(render_mesh_module, "SPARE_FRACTION", 3.0)
    monkeypatch.setattr(render_mesh_module, "PATCH_MAX_FRACTION", 10.0)
    rng = random.Random(seed)
    mesh = _grid(5, seed=seed)
    rm = RenderMesh(mesh, store_type=TraceStore)
    history = HistoryStack()
    patches = rm.stats.get("topology_patches")
    for _ in range(60):
        roll = rng.random()
        if roll < 0.15 and history.can_undo():
            history.undo()
        elif roll < 0.2 and history.can_redo():
            history.redo()
        elif roll < 0.35 and mesh.all_vertex_ids():
            moved = set(rng.sample(mesh.all_vertex_ids(), min(4, len(mesh.all_vertex_ids()))))
            for v in moved:
                x, y, z = mesh.vertex_position(v)
                mesh.set_vertex_position(v, (x + 0.1, y - 0.05, z + rng.uniform(-0.2, 0.2)))
            rm.mark_vertices_dirty(moved)
            rm.sync()
            assert_bit_identical(rm)
            continue
        else:
            try:
                delta, _ = record_mesh_change(mesh, lambda: _op(mesh, rng))
            except MeshError:
                continue
            if not delta.empty:
                history.push(MeshDeltaCommand(mesh, delta, "op"))
        rm.mark_topology_dirty()
        rm.sync()
        assert_bit_identical(rm)
    assert rm.stats.get("topology_patches") > patches


def test_ragged_lists_survive_relocation_and_compaction():
    rng = random.Random(7)
    lists = [[rng.randrange(100) for _ in range(rng.randrange(5))] for _ in range(40)]
    ragged = Ragged(len(lists), np.array([len(x) for x in lists]), np.array([v for x in lists for v in x]), 1)
    for step in range(400):
        item = rng.randrange(len(lists))
        lists[item] = [rng.randrange(100) for _ in range(rng.randrange(12))]
        ragged.set(item, lists[item])
        if step % 50 == 0:
            ragged._compact()
        assert [ragged.get(i) for i in range(len(lists))] == lists
    items = np.array([3, 0, 17, 3])
    assert ragged.gather(items).tolist() == [v for i in items.tolist() for v in lists[i]]
    assert ragged.end <= len(ragged.pool)


def test_the_id_view_reads_the_arrays():
    mesh = _mixed()
    rm = RenderMesh(mesh, store_type=TraceStore)
    reference = DerivedGeometry(mesh)
    view = rm.derived
    assert dict(view.vertex_to_faces) == reference.vertex_to_faces  # only vertices with faces, like the reference
    assert dict(view.vertex_normals) == reference.vertex_normals
    assert dict(view.face_normals) == reference.face_normals
    assert (view.bounds_min, view.bounds_max) == (reference.bounds_min, reference.bounds_max)
    lonely = mesh.all_vertex_ids()[-1]
    assert lonely not in view.vertex_to_faces and view.vertex_normals[lonely] == (0.0, 0.0, 0.0)
    with pytest.raises(KeyError):
        view.vertex_normals[10**9]


def test_the_store_holds_the_float32_rounding_of_the_arrays():
    mesh = _mixed()
    rm = RenderMesh(mesh, store_type=TraceStore)
    vids = mesh.all_vertex_ids()
    moved = set(vids[1::3])
    for v in moved:
        x, y, z = mesh.vertex_position(v)
        mesh.set_vertex_position(v, (x + 0.123456789, y, z - 0.987654321))
    rm.mark_vertices_dirty(moved)
    rm.sync()
    data = rm.store.data
    for v in vids:
        s = rm.vertex_index_of(v)
        assert data("positions")[3 * s:3 * s + 3] == array("f", rm.packed.P[s].tolist()).tolist()
        assert data("normals")[3 * s:3 * s + 3] == array("f", rm.packed.VN[s].tolist()).tolist()
    for f, row in rm._face_row.items():
        want = array("f", [*rm.packed.FN[row].tolist(), float(len(mesh.face_vertices(f)))]).tolist()
        assert data("face_normals")[4 * row:4 * row + 4] == want


def test_numpy_stays_above_the_core():
    for path in (REPO / "src" / "core").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        names |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        assert not any(name.split(".")[0] == "numpy" for name in names), path


def test_a_missing_numpy_names_the_pinned_version(monkeypatch):
    monkeypatch.setitem(sys.modules, "numpy", None)  # `import numpy` raises ImportError
    spec = importlib.util.spec_from_file_location("_packed_without_numpy",
                                                  REPO / "src" / "viewport" / "packed_geometry.py")
    module = importlib.util.module_from_spec(spec)
    with pytest.raises(ImportError, match=r"numpy==2\.2\.6.*REFERENCE_HARDWARE"):
        spec.loader.exec_module(module)


def test_the_pin_in_the_module_is_the_pin_in_requirements_txt():
    from viewport.packed_geometry import PINNED_NUMPY

    lines = (REPO / "requirements.txt").read_text(encoding="utf-8").splitlines()
    pins = [line.split("==", 1)[1].strip() for line in lines if line.strip().startswith("numpy==")]
    assert pins == [PINNED_NUMPY]


def _load_packed_geometry(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO / "src" / "viewport" / "packed_geometry.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_an_unpinned_numpy_is_named_before_it_is_loaded(monkeypatch, capsys):
    """A NumPy that ends the process inside its own import (reference PC, Python 3.14, 2026-11-13) leaves no Python
    message; the line is written first."""
    from importlib import metadata

    monkeypatch.setattr(metadata, "version", lambda name: "9.9.9" if name == "numpy" else metadata.version(name))
    _load_packed_geometry("_packed_unpinned")
    err = capsys.readouterr().err
    assert "NumPy 9.9.9" in err and "numpy==2.2.6" in err and "REFERENCE_HARDWARE" in err and sys.executable in err


def test_the_pinned_numpy_imports_silently(monkeypatch, capsys):
    from importlib import metadata

    monkeypatch.setattr(metadata, "version", lambda name: "2.2.6")
    _load_packed_geometry("_packed_pinned")
    assert capsys.readouterr().err == ""

