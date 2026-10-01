"""AD-017: key routing for Knife in-session undo/redo (WP-AP-CUT_PLAN 1.9).

Verifies through the real PlaygroundWindow.on_key_press (headless window,
same pattern as test_gizmo.py):

- While a Knife session is active, Ctrl+Z / Ctrl+Y / Ctrl+Shift+Z operate
  exclusively on the session's own step history — the global history stacks
  are neither mutated nor consumed (central isolation invariant).
- Without a session, Ctrl+Z = global Undo, Ctrl+Y = global Redo (canonical),
  Ctrl+Shift+Z = alternative global Redo gesture.
- Ctrl+Shift+Z never enters the Ctrl+Z undo branch (Shift guard).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT / "src"), str(_ROOT), str(_ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.operations.topology import MeshStateCommand  # noqa: E402
from core.selection import SelectionMode  # noqa: E402


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _window():
    from playground.app import PlaygroundApp
    from playground.window import PlaygroundWindow
    app = PlaygroundApp()
    win = PlaygroundWindow(app, initial_mesh="cube")
    return win, app


def _depths(app):
    """(global undo depth, global redo depth)."""
    h = app.scene.history
    return (len(h._undo_stack), len(h._redo_stack))


def _arm_knife(win):
    """Arm a Knife session exactly like the window's C-key path does."""
    from mirai.topology.knife import KnifeTool
    knife = KnifeTool()
    knife.activate()
    knife.begin(
        mesh=win.app.scene.mesh,
        scene=win.app.scene,
        selection=win.app.scene.selection,
    )
    win._knife_tool = knife
    return knife


def _face_diagonal(app):
    """A non-adjacent vertex pair of the first cube face (valid knife targets)."""
    mesh = app.scene.mesh
    fid = sorted(mesh.all_face_ids())[0]
    verts = sorted(mesh.face_vertices(fid))
    return verts[0], verts[2]


def _topo(app):
    from playground.tests.test_ad017_knife import _topo_snapshot
    return _topo_snapshot(app.scene.mesh)


@pytest.fixture
def win_app():
    win, app = _window()
    yield win, app
    win.close()


# ---------------------------------------------------------------------------
# 1. session active: undo/redo gestures stay inside the session
# ---------------------------------------------------------------------------

def test_ctrl_y_routes_to_knife_redo_during_session(win_app):
    """A->B / Ctrl+Z / Ctrl+Y: redo restores the cut segment; global stacks untouched.
    (WP-KNIFE-01 S2: the session's path, not the mesh, carries the cut until commit.)"""
    from pyglet.window import key as _key
    win, app = win_app
    knife = _arm_knife(win)
    va, vb = _face_diagonal(app)
    assert knife.click({"kind": "vertex", "vertex_id": va})
    assert knife.click({"kind": "vertex", "vertex_id": vb})
    path_cut = knife.path
    topo = _topo(app)
    depths = _depths(app)

    win.on_key_press(_key.Z, _key.MOD_CTRL)          # in-session undo
    assert knife.path != path_cut
    assert knife.last_point["vertex_id"] == va
    assert _depths(app) == depths                    # global history untouched

    win.on_key_press(_key.Y, _key.MOD_CTRL)          # canonical in-session redo
    assert knife.path == path_cut
    assert knife.last_point["vertex_id"] == vb
    assert len(knife.cut_segments) == 1
    assert _depths(app) == depths
    assert _topo(app) == topo                        # nothing cut before commit
    assert win._knife_tool is knife                  # session still active


def test_ctrl_shift_z_routes_to_knife_redo_during_session(win_app):
    """Ctrl+Shift+Z is the alternative redo gesture during a session."""
    from pyglet.window import key as _key
    win, app = win_app
    knife = _arm_knife(win)
    va, vb = _face_diagonal(app)
    knife.click({"kind": "vertex", "vertex_id": va})
    knife.click({"kind": "vertex", "vertex_id": vb})
    path_cut = knife.path
    depths = _depths(app)

    win.on_key_press(_key.Z, _key.MOD_CTRL)          # undo
    assert knife.path != path_cut

    win.on_key_press(_key.Z, _key.MOD_CTRL | _key.MOD_SHIFT)  # alternative redo
    assert knife.path == path_cut
    assert knife.last_point["vertex_id"] == vb
    assert _depths(app) == depths


def test_ctrl_shift_z_never_enters_the_undo_branch(win_app):
    """With no redo available, Ctrl+Shift+Z must be a redo no-op — never an undo."""
    from pyglet.window import key as _key
    win, app = win_app
    knife = _arm_knife(win)
    va, vb = _face_diagonal(app)
    knife.click({"kind": "vertex", "vertex_id": va})
    knife.click({"kind": "vertex", "vertex_id": vb})
    path_cut = knife.path

    win.on_key_press(_key.Z, _key.MOD_CTRL | _key.MOD_SHIFT)
    assert knife.path == path_cut                    # redo no-op, NOT an undo
    assert len(knife.cut_segments) == 1

# ---------------------------------------------------------------------------
# 2. no session: gestures route to the global history
# ---------------------------------------------------------------------------

def _seed_global_split_then_undo(app):
    """One real global history entry (edge split) + global undo -> the global
    redo branch is non-empty, the global undo branch holds the entry."""
    from playground.tests.test_ad017_knife import _push_history_split_then_undo
    mesh = app.scene.mesh
    fid = sorted(mesh.all_face_ids())[0]
    verts = mesh.face_vertices(fid)
    eid = mesh._get_or_create_edge(verts[0], verts[1])
    _push_history_split_then_undo(app, eid)
    return (0, 1)  # (undo depth, redo depth): entry pushed and undone


def test_no_session_ctrl_z_is_global_undo(win_app):
    from pyglet.window import key as _key
    win, app = win_app
    assert win._knife_tool is None
    mesh = app.scene.mesh
    topo_before = _topo(app)
    _seed_global_split_then_undo(app)
    assert _depths(app) == (0, 1)
    app.redo()                               # entry back in the undo branch, split applied
    assert _depths(app) == (1, 0)
    assert _topo(app) != topo_before

    win.on_key_press(_key.Z, _key.MOD_CTRL)
    assert _depths(app) == (0, 1)            # global undo consumed the entry
    assert _topo(app) == topo_before         # split is undone


def test_no_session_ctrl_y_is_global_redo(win_app):
    from pyglet.window import key as _key
    win, app = win_app
    assert win._knife_tool is None
    mesh = app.scene.mesh
    topo_before = _topo(app)
    _seed_global_split_then_undo(app)
    assert _depths(app) == (0, 1)

    win.on_key_press(_key.Y, _key.MOD_CTRL)          # canonical global redo
    assert _depths(app) == (1, 0)
    assert _topo(app) != topo_before                 # pre-session split re-applied


def test_no_session_ctrl_shift_z_is_global_redo(win_app):
    from pyglet.window import key as _key
    win, app = win_app
    assert win._knife_tool is None
    mesh = app.scene.mesh
    topo_before = _topo(app)
    _seed_global_split_then_undo(app)

    win.on_key_press(_key.Z, _key.MOD_CTRL | _key.MOD_SHIFT)  # alternative gesture
    assert _depths(app) == (1, 0)
    assert _topo(app) != topo_before

# ---------------------------------------------------------------------------
# 3. WP-KNIFE-01 S2: the session is drawn from its virtual path
# ---------------------------------------------------------------------------

def test_knife_family_draws_the_path_while_the_mesh_stays_uncut(win_app):
    """The shared `KnifeTool` no longer cuts per click: the window draws the placed points and the
    segments commit will cut (same render data as Production), rebuilt on click / undo / redo and
    when a hover sees a new start point; the mesh changes only at Enter."""
    from pyglet.window import key as _key
    win, app = win_app
    knife = _arm_knife(win)
    va, vb = _face_diagonal(app)
    topo = _topo(app)
    assert knife.click({"kind": "vertex", "vertex_id": va})
    assert knife.click({"kind": "vertex", "vertex_id": vb})

    # A hover sees the new start point (hover()["start"] is the last path record) -> path rebuilt.
    sx, sy = app.camera.project_to_screen(app.scene.mesh.vertex_position(va), win.width, win.height)
    win.on_mouse_motion(int(sx), int(sy), 0, 0)
    assert win._knife_last_start == knife.last_point["pid"]
    assert win._vlist_knife_start is not None and win._vlist_knife_path is not None
    win.on_draw()
    assert _topo(app) == topo

    win.on_key_press(_key.Z, _key.MOD_CTRL)          # undo: one point left, no segment
    assert win._vlist_knife_start is not None and win._vlist_knife_path is None
    win.on_key_press(_key.Y, _key.MOD_CTRL)          # redo: the segment is back
    assert win._vlist_knife_path is not None

    win.on_key_press(_key.ENTER, 0)                  # commit: the cut, one history entry
    assert win._knife_tool is None
    assert win._vlist_knife_start is None and win._vlist_knife_path is None
    assert _topo(app) != topo
    assert _depths(app) == (1, 0)


def test_knife_family_hover_snaps_to_an_own_edge_point(win_app):
    """Over one of the session's own edge points the hover target is that point (S2 own-point snap,
    `knife_pick.snap_own_point`) and it is highlighted like a vertex — a click there reaches the
    very point again instead of placing a second one next to it."""
    win, app = win_app
    knife = _arm_knife(win)
    mesh = app.scene.mesh
    fid = sorted(mesh.all_face_ids())[0]
    eid = mesh.face_edges(fid)[0]
    assert knife.click({"kind": "edge", "edge_id": eid, "t": 0.5})
    a, b = (mesh.vertex_position(v) for v in mesh.edge_vertices(eid))
    mid = tuple((a[i] + b[i]) / 2 for i in range(3))
    sx, sy = app.camera.project_to_screen(mid, win.width, win.height)

    from mirai.topology.knife_pick import knife_pick
    picked = knife_pick(app.camera, mesh, sx, sy, win.width, win.height, **win._pick_kwargs())
    assert picked["kind"] == "edge"
    assert win._knife_snap(mesh, sx, sy, picked) == {"kind": "point", "pid": knife.last_point["pid"]}

    win.on_mouse_motion(round(sx), round(sy), 0, 0)
    assert win._vlist_knife_hover_vertex is not None   # highlighted like a vertex
    assert win._vlist_knife_preview_point is None      # not an edge preview
    win.on_draw()


def test_knife_family_shows_and_accepts_a_point_inside_a_face(win_app):
    """WP-KNIFE-01 S3: the shared `KnifeTool` takes face points — over the interior of a face of the last
    point the window shows the point marker (as the Knife Face Lab does), a click adds a face record and
    the path VBO draws it; the mesh stays uncut until Enter."""
    from pyglet.window import key as _key

    from mirai.topology.knife_pick import knife_pick
    win, app = win_app
    knife = _arm_knife(win)
    mesh = app.scene.mesh
    for fid in sorted(mesh.all_face_ids()):                    # a face whose centre is visible
        ps = [mesh.vertex_position(v) for v in mesh.face_vertices(fid)]
        centre = tuple(sum(p[i] for p in ps) / len(ps) for i in range(3))
        cx, cy = app.camera.project_to_screen(centre, win.width, win.height)
        picked = knife_pick(app.camera, mesh, round(cx), round(cy), win.width, win.height, **win._pick_kwargs())
        if picked["kind"] == "face" and picked["face_id"] == fid:
            break
    else:
        pytest.fail("no face centre visible")
    assert knife.click({"kind": "edge", "edge_id": mesh.face_edges(fid)[0], "t": 0.5})
    topo = _topo(app)

    win.on_mouse_motion(round(cx), round(cy), 0, 0)
    assert win._vlist_knife_preview_point is not None          # the face point marker
    target = win._knife_snap(mesh, round(cx), round(cy),
                             knife_pick(app.camera, mesh, round(cx), round(cy), win.width, win.height,
                                        **win._pick_kwargs()))
    assert knife.click(target) and knife.last_point["kind"] == "face"
    win.on_mouse_motion(round(cx) + 40, round(cy), 0, 0)
    assert win._knife_last_start == knife.last_point["pid"] and win._vlist_knife_path is not None
    win.on_draw()
    assert _topo(app) == topo
    win.on_key_press(_key.ENTER, 0)                            # the tail is joined to a corner at Enter
    assert _topo(app) != topo and _depths(app) == (1, 0)
