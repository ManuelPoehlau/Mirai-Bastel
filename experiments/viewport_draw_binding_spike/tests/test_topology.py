"""§7 "Topology": split edge → new IDs, index count correct, no stale
attribute data."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
for _p in (str(_ROOT / "src"), str(_ROOT / "examples"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import Selection  # noqa: E402
from mirai.scene_factory import create_cube  # noqa: E402
from viewport.derived import triangulate_face  # noqa: E402
from viewport.overlay import SelectionOverlay  # noqa: E402
from viewport.render_mesh import RenderMesh  # noqa: E402

from spike_gl_store import SpikeGLStore  # noqa: E402


def test_edge_split_gives_new_ids_and_correct_indices(gl_window):
    mesh = create_cube(size=2.0)
    selection = Selection()
    overlay = SelectionOverlay(selection)
    rm = RenderMesh(mesh, overlay=overlay, store_type=SpikeGLStore)

    ids_before = rm.resource_ids()
    vlist_before = rm.store.vertex_list()
    n_verts_before = len(list(mesh.all_vertex_ids()))

    edge_id = next(iter(mesh.all_edge_ids()))
    new_vertex, _e1, _e2 = mesh.split_edge(edge_id)
    rm.mark_topology_dirty()
    rm.sync()

    ids_after = rm.resource_ids()
    for name in ("positions", "normals", "indices", "highlight_flags"):
        assert ids_after[name] != ids_before[name], f"{name} resource id did not change"

    vlist_after = rm.store.vertex_list()
    assert vlist_after is not vlist_before

    n_verts_after = len(list(mesh.all_vertex_ids()))
    assert n_verts_after == n_verts_before + 1

    expected_triangle_count = sum(
        len(triangulate_face(mesh.face_vertices(fid))) for fid in mesh.all_face_ids()
    )
    assert len(vlist_after.indices[:]) == expected_triangle_count * 3

    # No stale data: new vertex's position in the buffer matches the mesh.
    new_idx = rm.vertex_index_of(new_vertex)
    expected_pos = tuple(mesh.vertex_position(new_vertex))
    got_pos = tuple(vlist_after.position[new_idx * 3: new_idx * 3 + 3])
    assert got_pos == expected_pos

    # Every index references a valid vertex slot.
    for i in vlist_after.indices[:]:
        assert 0 <= i < n_verts_after
