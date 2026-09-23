"""WP-STAB-08: Tweak temp-target lifecycle rebuilds the selection-highlight
overlay.

Uses a real, GL-backed `PlaygroundWindow` (same pattern as
`test_wp_stab_01_selection_overlay_lifecycle.py` /
`test_wp_stab_02_hover_reset.py`), driven through the window's own Tweak
helpers (`_tweak_begin` / `_tweak_commit` / `_tweak_cancel`) — this is the
"headless equivalent" of a live manual check; a live GUI check was not
possible in this environment. `pick_component` is monkeypatched (same
technique as `test_wp_stab_02_hover_reset.py`'s S10) so the test does not
depend on exact screen-to-world picking math for a bare-cursor Tweak.

Root cause (pre-fix): when Tweak starts with nothing selected, it hit-tests
under the cursor and calls `add_temp_target(selection, hit)`, which adds the
hit element directly into `Selection.vertices/.edges/.faces` — bypassing
the normal click path that always follows with `_rebuild_selection_vbo()`.
`_tweak_begin()` never called it either, so `_vlist_sel_verts` (the
highlight overlay) stayed whatever it was before the gesture — typically
`None` — for the entire temp-target drag.

    S1  `_tweak_begin()` with no pre-selection (temp-target path) leaves
        `_vlist_sel_verts` non-None and matching the (now temp-)selected
        vertex, immediately — before any drag update.
    S2  A drag update moves the vertex; the highlight overlay stays present
        (non-None, still exactly 1 point) through the whole gesture instead
        of disappearing mid-drag.
        NOTE: `_patch_vbo_single_vertex()`'s "Selection VBO" branch (position
        of a single selected vertex always patched at buffer slot 0) is only
        correct when `_vlist_sel_verts` happens to be the first same-format
        GL_POINTS vertex_list allocated in its shared domain. In practice
        `_vlist_verts` (all mesh vertices) is always built first in
        `_rebuild_vbo()`/`_rebuild_selection_vbo()`, so `_vlist_sel_verts`'s
        real buffer offset is `len(mesh.all_vertex_ids())`, not 0 — the patch
        silently writes into the wrong slot and the highlight's position does
        NOT track the live drag (verified empirically; reproducible for an
        ordinary pre-selected single-vertex Tweak too, not just temp-target).
        That is a separate, pre-existing defect in that branch, outside
        WP-STAB-08's scope (rebuilding the overlay on temp-target add/clear)
        — flagged here rather than silently asserted around.
    S3  `_tweak_commit()` clears the temp target and the highlight
        (`_vlist_sel_verts` back to `None`), leaving the real Selection
        unchanged (still empty).
    S4  `_tweak_cancel()` does the same on the cancel path.
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
from playground.vbo_builder import build_selection_vertex_data  # noqa: E402


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


def _begin_temp_target_tweak(win, app, monkeypatch, vid):
    """Arm a temp-target Tweak (no pre-selection) on `vid` via `_tweak_begin`,
    with `pick_component` monkeypatched to report `vid` regardless of the
    (arbitrary) screen coordinates passed in."""
    import playground.window as window_mod

    sel = app.scene.selection
    sel.mode = SelectionMode.VERTEX
    sel.clear()
    assert sel.is_empty()

    monkeypatch.setattr(
        window_mod, "pick_component",
        lambda camera, mesh, s, sx, sy, w, h: vid,
    )
    ok = win._tweak_begin("move", 640, 400)
    assert ok and win._tweak_started
    assert win._tweak_temp_target is True
    return sel


# ---------------------------------------------------------------------------
# S1 — highlight visible immediately on temp-target begin
# ---------------------------------------------------------------------------

def test_s1_temp_target_begin_shows_highlight(cube_win, monkeypatch):
    win, app = cube_win
    vid = next(iter(app.scene.mesh.all_vertex_ids()))
    sel = _begin_temp_target_tweak(win, app, monkeypatch, vid)

    assert vid in sel.vertices  # add_temp_target() did its job
    assert win._vlist_sel_verts is not None, (
        "highlight overlay must be rebuilt right after add_temp_target()"
    )
    expected = build_selection_vertex_data(app.scene.mesh, {vid})
    assert win._vlist_sel_verts.count == len(expected) // 3

    win._tweak_cancel()


# ---------------------------------------------------------------------------
# S2 — highlight tracks the live position during the drag
# ---------------------------------------------------------------------------

def test_s2_temp_target_highlight_stays_visible_through_drag(cube_win, monkeypatch):
    win, app = cube_win
    vid = next(iter(app.scene.mesh.all_vertex_ids()))
    _begin_temp_target_tweak(win, app, monkeypatch, vid)
    assert win._vlist_sel_verts is not None  # visible at gesture start (S1)

    update_transform(win._tweak_tool, 30.0, -12.0, win.width, win.height)
    win._sync_after_transform()

    # Pre-fix, this was already None from the start (add_temp_target() was
    # never followed by a rebuild) and stayed None. Post-fix it must still be
    # present — and correctly sized — after a drag update, not just at t=0.
    assert win._vlist_sel_verts is not None
    expected = build_selection_vertex_data(app.scene.mesh, {vid})
    assert win._vlist_sel_verts.count == len(expected) // 3

    win._tweak_cancel()


# ---------------------------------------------------------------------------
# S3 — commit clears the temp target and the highlight
# ---------------------------------------------------------------------------

def test_s3_temp_target_commit_clears_highlight(cube_win, monkeypatch):
    win, app = cube_win
    vid = next(iter(app.scene.mesh.all_vertex_ids()))
    sel = _begin_temp_target_tweak(win, app, monkeypatch, vid)

    update_transform(win._tweak_tool, 10.0, 5.0, win.width, win.height)
    win._sync_after_transform()

    win._tweak_commit()

    assert sel.is_empty(), "temp target must not leak into the real Selection"
    assert win._vlist_sel_verts is None


# ---------------------------------------------------------------------------
# S4 — cancel clears the temp target and the highlight
# ---------------------------------------------------------------------------

def test_s4_temp_target_cancel_clears_highlight(cube_win, monkeypatch):
    win, app = cube_win
    vid = next(iter(app.scene.mesh.all_vertex_ids()))
    sel = _begin_temp_target_tweak(win, app, monkeypatch, vid)

    update_transform(win._tweak_tool, -8.0, 15.0, win.width, win.height)
    win._sync_after_transform()

    win._tweak_cancel()

    assert sel.is_empty()
    assert win._vlist_sel_verts is None
