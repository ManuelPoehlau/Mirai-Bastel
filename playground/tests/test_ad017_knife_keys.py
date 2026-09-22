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
    from playground.topology_tools.knife import KnifeTool
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
    """A->B / Ctrl+Z / Ctrl+Y: redo restores the cut; global stacks untouched."""
    from pyglet.window import key as _key
    win, app = win_app
    knife = _arm_knife(win)
    va, vb = _face_diagonal(app)
    assert knife.click({"kind": "vertex", "vertex_id": va})
    assert knife.click({"kind": "vertex", "vertex_id": vb})
    topo_cut = _topo(app)
    depths = _depths(app)

    win.on_key_press(_key.Z, _key.MOD_CTRL)          # in-session undo
    assert _topo(app) != topo_cut
    assert knife._start == va
    assert _depths(app) == depths                    # global history untouched

    win.on_key_press(_key.Y, _key.MOD_CTRL)          # canonical in-session redo
    assert _topo(app) == topo_cut
    assert knife._start == vb
    assert len(knife._path_edges) == 1
    assert _depths(app) == depths
    assert win._knife_tool is knife                  # session still active


def test_ctrl_shift_z_routes_to_knife_redo_during_session(win_app):
    """Ctrl+Shift+Z is the alternative redo gesture during a session."""
    from pyglet.window import key as _key
    win, app = win_app
    knife = _arm_knife(win)
    va, vb = _face_diagonal(app)
    knife.click({"kind": "vertex", "vertex_id": va})
    knife.click({"kind": "vertex", "vertex_id": vb})
    topo_cut = _topo(app)
    depths = _depths(app)

    win.on_key_press(_key.Z, _key.MOD_CTRL)          # undo
    assert _topo(app) != topo_cut

    win.on_key_press(_key.Z, _key.MOD_CTRL | _key.MOD_SHIFT)  # alternative redo
    assert _topo(app) == topo_cut
    assert knife._start == vb
    assert _depths(app) == depths


def test_ctrl_shift_z_never_enters_the_undo_branch(win_app):
    """With no redo available, Ctrl+Shift+Z must be a redo no-op — never an undo."""
    from pyglet.window import key as _key
    win, app = win_app
    knife = _arm_knife(win)
    va, vb = _face_diagonal(app)
    knife.click({"kind": "vertex", "vertex_id": va})
    knife.click({"kind": "vertex", "vertex_id": vb})
    topo_cut = _topo(app)

    win.on_key_press(_key.Z, _key.MOD_CTRL | _key.MOD_SHIFT)
    assert _topo(app) == topo_cut                    # redo no-op, NOT an undo
    assert len(knife._step_stack) == 2

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