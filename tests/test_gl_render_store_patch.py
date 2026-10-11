"""GLRenderStore partial updates write only the changed slice (WP-VIEW-PATCH-01).

`update()` used to hand the whole attribute buffer to `_patch_attribute`, so every
per-vertex update re-copied all V vertices. It now writes `[offset, offset + n)`.
These tests read the buffers back from the GPU (not from the VertexList's CPU
shadow) and compare them to the store's CPU copy `_cpu`.

Needs a real GL context (Xvfb or a display); skips cleanly without one, like
`test_gl_render_store.py`.
"""

from __future__ import annotations

import ctypes
import random
import sys
from pathlib import Path

import tests._bootstrap  # noqa: F401

import pytest

pyglet = pytest.importorskip("pyglet", reason="pyglet not installed")

from core import Selection  # noqa: E402
from mirai.scene_factory import build_core_scene_from_obj  # noqa: E402
from viewport.gl_render_store import GLRenderStore  # noqa: E402
from viewport.overlay import SelectionOverlay  # noqa: E402
from viewport.render_mesh import RenderMesh  # noqa: E402

_HEAD_OBJ = Path(__file__).resolve().parents[1] / "examples" / "meshes" / "head_basemesh.obj"
#: store resource name -> VertexList attribute (AD-018 §5 layout declaration)
_ATTRIBUTES = {"positions": "position", "normals": "normal", "highlight_flags": "highlight_flag"}


@pytest.fixture(scope="module")
def gl_window():
    try:
        win = pyglet.window.Window(width=128, height=128, visible=False)
    except Exception as exc:  # pragma: no cover - environment-dependent
        pytest.skip(f"no GL context available: {exc}")
    yield win
    win.close()


def _build_head():
    if not _HEAD_OBJ.exists():
        pytest.skip(f"reference mesh not found: {_HEAD_OBJ}")
    examples_dir = str(_HEAD_OBJ.parents[1])  # the shared OBJ loader lives there
    if examples_dir not in sys.path:
        sys.path.insert(0, examples_dir)
    mesh = build_core_scene_from_obj(str(_HEAD_OBJ)).mesh
    rm = RenderMesh(mesh, overlay=SelectionOverlay(Selection()), store_type=GLRenderStore)
    rm.sync()
    return mesh, rm


def _gpu_read(vlist, attr: str) -> list[float] | None:
    """The attribute's floats as stored in the GL buffer object (after the
    pending dirty range is committed, as `draw()` does). None = the driver
    dropped the attribute from the program."""
    if getattr(vlist, attr, None) is None:
        return None
    buf = vlist.domain.attrib_name_buffers[attr]
    buf.commit()
    n_floats = vlist.count * buf.count
    out = (ctypes.c_float * n_floats)()
    pyglet.gl.glBindBuffer(pyglet.gl.GL_ARRAY_BUFFER, buf.id)
    pyglet.gl.glGetBufferSubData(
        pyglet.gl.GL_ARRAY_BUFFER, vlist.start * buf.stride, n_floats * 4, out
    )
    return list(out)


def _assert_gpu_equals_cpu(store: GLRenderStore) -> int:
    """Every declared attribute: GL buffer content == `_cpu` (float32-rounded).
    Returns how many attributes were compared."""
    vlist = store.vertex_list()
    compared = 0
    for name, attr in _ATTRIBUTES.items():
        gpu = _gpu_read(vlist, attr)
        if gpu is None:
            continue
        cpu = store.uniform_data(name)
        assert len(gpu) == len(cpu), name
        expected = list((ctypes.c_float * len(cpu))(*cpu))
        assert gpu == expected, f"{name}: GPU buffer differs from CPU copy"
        compared += 1
    assert compared >= 2  # positions + normals always survive
    return compared


def _random_update(rng: random.Random, store: GLRenderStore, n_verts: int) -> None:
    name = rng.choice(["positions", "normals", "highlight_flags"])
    comps = 1 if name == "highlight_flags" else 3
    first = rng.randrange(n_verts)
    count = rng.choice([1, 1, 1, 2, 5, 17])  # mostly single-vertex, as in a drag
    count = min(count, n_verts - first)
    data = [rng.uniform(-5.0, 5.0) for _ in range(count * comps)]
    store.update(name, first * comps, data, len(data) * 4)


def test_random_partial_updates_gpu_equals_cpu(gl_window):
    mesh, rm = _build_head()
    store = rm.store
    n_verts = store.vertex_list().count
    rng = random.Random(20261010)

    for step in range(300):
        _random_update(rng, store, n_verts)
        if step % 50 == 49:
            _assert_gpu_equals_cpu(store)
    _assert_gpu_equals_cpu(store)


def test_update_writes_only_the_changed_slice(gl_window):
    """A sentinel planted outside the updated range survives: a full-buffer
    write (the old behaviour) would overwrite it with the CPU copy."""
    mesh, rm = _build_head()
    store = rm.store
    vlist = store.vertex_list()
    sentinel = 12345.0
    shadow = vlist.position
    shadow[0:3] = [sentinel] * 3  # vertex 0, not in the update below

    store.update("positions", 3 * 10, [1.0, 2.0, 3.0], 12)

    assert list(vlist.position[0:3]) == [sentinel] * 3
    assert list(vlist.position[30:33]) == [1.0, 2.0, 3.0]


def test_drag_moves_and_normal_ring_gpu_equals_cpu(gl_window):
    """The real caller: `_sync_geometry` issues one update per moved vertex and
    per 1-ring normal, over many frames."""
    mesh, rm = _build_head()
    rng = random.Random(7)
    ids = mesh.all_vertex_ids()

    for _frame in range(25):
        moved = set(rng.sample(ids, rng.choice([1, 3, 9, 40])))
        for vid in moved:
            x, y, z = mesh.vertex_position(vid)
            mesh.set_vertex_position(
                vid, (x + rng.uniform(-0.05, 0.05), y + rng.uniform(-0.05, 0.05), z)
            )
        rm.mark_vertices_dirty(moved)
        rm.sync()

    store = rm.store
    _assert_gpu_equals_cpu(store)
    positions = store.uniform_data("positions")
    for vid in rng.sample(ids, 30):
        idx = rm.vertex_index_of(vid)
        assert positions[idx * 3: idx * 3 + 3] == pytest.approx(
            list(mesh.vertex_position(vid)), abs=1e-6
        )


def test_rebuild_after_partial_updates_is_correct(gl_window):
    mesh, rm = _build_head()
    store = rm.store
    n_verts = store.vertex_list().count
    rng = random.Random(3)
    for _ in range(80):
        _random_update(rng, store, n_verts)
    _assert_gpu_equals_cpu(store)

    vlist_before = store.vertex_list()
    mesh.split_edge(next(iter(mesh.all_edge_ids())))
    rm.mark_topology_dirty()
    rm.sync()

    assert store.vertex_list() is not vlist_before
    assert store.vertex_list().count == n_verts + 1
    _assert_gpu_equals_cpu(store)

    for _ in range(80):  # partial updates keep working on the rebuilt list
        _random_update(rng, store, n_verts + 1)
    _assert_gpu_equals_cpu(store)
