"""WP-STAB-09: _patch_vbo_single_vertex uses .start for correct absolute buffer offset.

Pyglet allocates vertex lists inside a shared VertexDomain; set_region() on the domain
buffer takes *absolute* positions, not list-local ones. The method previously used raw
local offsets (starting at 0), so for _vlist_sel_verts it silently wrote into slot 0 of
the shared domain — i.e., the first vertex of _vlist_verts — while the selection
highlight itself never got updated.

    S1  Shared-domain scenario: on a fresh cube _vlist_verts and _vlist_sel_verts share
        one domain (_overlay_program, position float3), so _vlist_sel_verts.start == 8
        (== vertex count), NOT 0.  After a single-vertex patch on a vertex that is NOT
        at slot 0:
          (a) _vlist_sel_verts.position[0:3] matches mesh.vertex_position(dragged_vid)
              — the highlight received the correct position.
          (b) _vlist_verts.position[0:3] still matches the ORIGINAL position of the
              first mesh vertex — no corruption of an unrelated vertex.

    S2  _vlist_verts branch: patched vertex position matches mesh.vertex_position(vid).
    S3  _vlist_edges branch: patched edge-endpoint position matches mesh.vertex_position(vid).
    S4  _vlist_faces branch: every occurrence of the patched vertex in the faces VBO
        matches mesh.vertex_position(vid).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT / "src"), str(_ROOT), str(_ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.selection import SelectionMode  # noqa: E402
from playground.transformer import update_transform  # noqa: E402
from viewport.derived import triangulate_face  # noqa: E402


def _window(initial_mesh: str = "cube"):
    from playground.app import PlaygroundApp
    from playground.window import PlaygroundWindow
    app = PlaygroundApp()
    win = PlaygroundWindow(app, initial_mesh=initial_mesh)
    return win, app


@pytest.fixture
def cube_win():
    win, app = _window("cube")
    yield win, app
    win.close()


def _do_single_vertex_tweak(win, app, vid, dx=25.0, dy=10.0):
    """Pre-select `vid`, rebuild selection VBO, begin a Tweak, drag, return mesh."""
    sel = app.scene.selection
    sel.mode = SelectionMode.VERTEX
    sel.clear()
    sel.add({vid})
    # Direct sel.add() bypasses the click path that normally follows with
    # _rebuild_selection_vbo(); call it explicitly so _vlist_sel_verts exists.
    win._rebuild_selection_vbo()

    ok = win._tweak_begin("move", 640, 400)
    assert ok and win._tweak_started

    update_transform(win._tweak_tool, dx, dy, win.width, win.height)
    win._sync_after_transform()

    return app.scene.mesh


# ---------------------------------------------------------------------------
# S1 — shared domain: sel_verts updated, verts not corrupted
# ---------------------------------------------------------------------------

def test_s1_sel_verts_updated_and_verts_not_corrupted(cube_win):
    win, app = cube_win
    all_vids = list(app.scene.mesh.all_vertex_ids())

    # Must have at least 2 vertices so we can drag one while another acts as
    # the corruption canary.
    assert len(all_vids) >= 2

    # Select the LAST vertex so slot 0 in _vlist_verts belongs to a different,
    # unselected vertex — the canary for corruption.
    canary_vid = all_vids[0]
    drag_vid   = all_vids[-1]

    # Record the canary's original world-space position before any patch.
    original_canary_pos = tuple(app.scene.mesh.vertex_position(canary_vid))

    mesh = _do_single_vertex_tweak(win, app, drag_vid)

    # Precondition: the two vlists share one VertexDomain, so sel_verts.start != 0.
    # If this ever changes (pyglet changes allocation strategy), the test is still
    # valid — it just no longer exercises the domain-sharing path specifically.
    assert win._vlist_sel_verts is not None
    assert win._vlist_verts is not None
    assert (
        win._vlist_sel_verts.start != 0
    ), "_vlist_sel_verts.start == 0 — domain sharing not reproduced; test premise changed"

    expected_drag_pos = tuple(mesh.vertex_position(drag_vid))

    # (a) Selection highlight received the new position.
    sel_pos = tuple(win._vlist_sel_verts.position[0:3])
    assert sel_pos == pytest.approx(expected_drag_pos, abs=1e-5), (
        f"_vlist_sel_verts not updated: got {sel_pos}, expected {expected_drag_pos}"
    )

    # (b) The canary vertex (slot 0 in _vlist_verts) was not corrupted.
    canary_pos_after = tuple(win._vlist_verts.position[0:3])
    assert canary_pos_after == pytest.approx(original_canary_pos, abs=1e-5), (
        f"_vlist_verts slot 0 corrupted: got {canary_pos_after}, expected {original_canary_pos}"
    )

    win._tweak_commit()


# ---------------------------------------------------------------------------
# S2 — _vlist_verts branch: patched slot matches mesh ground truth
# ---------------------------------------------------------------------------

def test_s2_verts_vbo_still_correct(cube_win):
    win, app = cube_win
    all_vids = list(app.scene.mesh.all_vertex_ids())
    drag_vid  = all_vids[1] if len(all_vids) > 1 else all_vids[0]

    mesh = _do_single_vertex_tweak(win, app, drag_vid)

    assert win._vlist_verts is not None
    expected = tuple(mesh.vertex_position(drag_vid))

    for slot, v in enumerate(mesh.all_vertex_ids()):
        if v == drag_vid:
            got = tuple(win._vlist_verts.position[slot * 3: slot * 3 + 3])
            assert got == pytest.approx(expected, abs=1e-5), (
                f"_vlist_verts slot {slot}: got {got}, expected {expected}"
            )
            break

    win._tweak_commit()


# ---------------------------------------------------------------------------
# S3 — _vlist_edges branch: patched edge-endpoint matches mesh ground truth
# ---------------------------------------------------------------------------

def test_s3_edges_vbo_still_correct(cube_win):
    win, app = cube_win
    all_vids = list(app.scene.mesh.all_vertex_ids())
    drag_vid  = all_vids[-1]

    mesh = _do_single_vertex_tweak(win, app, drag_vid)

    assert win._vlist_edges is not None
    expected = tuple(mesh.vertex_position(drag_vid))

    for edge_slot, eid in enumerate(mesh.all_edge_ids()):
        va, vb = mesh.edge_vertices(eid)
        if va == drag_vid:
            base = edge_slot * 2
            got = tuple(win._vlist_edges.position[base * 3: base * 3 + 3])
            assert got == pytest.approx(expected, abs=1e-5), (
                f"_vlist_edges edge {edge_slot} va: got {got}, expected {expected}"
            )
            break
        if vb == drag_vid:
            base = edge_slot * 2 + 1
            got = tuple(win._vlist_edges.position[base * 3: base * 3 + 3])
            assert got == pytest.approx(expected, abs=1e-5), (
                f"_vlist_edges edge {edge_slot} vb: got {got}, expected {expected}"
            )
            break

    win._tweak_commit()


# ---------------------------------------------------------------------------
# S4 — _vlist_faces branch: every occurrence of the patched vertex in the
#      faces VBO matches mesh ground truth
# ---------------------------------------------------------------------------

def test_s4_faces_vbo_still_correct(cube_win):
    win, app = cube_win
    all_vids = list(app.scene.mesh.all_vertex_ids())
    drag_vid  = all_vids[-1]

    mesh = _do_single_vertex_tweak(win, app, drag_vid)

    assert win._vlist_faces is not None
    expected = tuple(mesh.vertex_position(drag_vid))

    # Scan through the faces VBO in the same order as _patch_vbo_single_vertex.
    slot = 0
    found = False
    for fid in mesh.all_face_ids():
        boundary = mesh.face_vertices(fid)
        for a, b, c in triangulate_face(boundary):
            for slot_vid in (a, b, c):
                if slot_vid == drag_vid:
                    got = tuple(win._vlist_faces.position[slot * 3: slot * 3 + 3])
                    assert got == pytest.approx(expected, abs=1e-5), (
                        f"_vlist_faces slot {slot}: got {got}, expected {expected}"
                    )
                    found = True
                slot += 1

    assert found, f"drag_vid {drag_vid} not found in any face"

    win._tweak_commit()
