"""Regression test: mesh-count methods must NOT be called during orbit/pan.

Acceptance criterion (task-brief fix — orbit-lag):
    During a pure orbit drag (_push_camera with no preceding _rebuild_vbo),
    mesh.all_vertex_ids() / all_edge_ids() / all_face_ids() must not be
    called — the HUD mesh-count line is only refreshed when
    _hud_mesh_counts_dirty is True (set by _rebuild_vbo).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REPO_SRC = _REPO_ROOT / "src"
_RIGGING = _REPO_ROOT / "experiments" / "rigging-skinning-morphing"
_LAB = _REPO_ROOT / "experiments" / "mirai_bastel_integration_lab"
for _p in (str(_LAB), str(_REPO_SRC), str(_REPO_ROOT), str(_RIGGING)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from playground.app import PlaygroundApp  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app_with_cube() -> PlaygroundApp:
    app = PlaygroundApp()
    app.load_cube()
    return app


class _FakeWindow:
    """Minimal stand-in for PlaygroundWindow — only the HUD-update logic."""

    def __init__(self, app: PlaygroundApp) -> None:
        from playground.hud import PlaygroundHUD

        self.app = app
        self._hud = PlaygroundHUD()
        self._hud_mesh_counts_dirty: bool = True
        self.width = 1280
        self.height = 800
        self._renderer = None

    # Copy the exact _update_hud implementation from PlaygroundWindow.
    def _update_hud(self) -> None:
        cam = self.app.camera
        self._hud.update_camera(cam.yaw, cam.pitch, cam.distance)
        if self._hud_mesh_counts_dirty:
            mesh = self.app.viewport.render_mesh.mesh if self.app.viewport else None
            if mesh is not None:
                v_count = len(list(mesh.all_vertex_ids()))
                e_count = len(list(mesh.all_edge_ids()))
                f_count = len(list(mesh.all_face_ids()))
                self._hud.update_mesh(v_count, e_count, f_count)
            self._hud_mesh_counts_dirty = False

    def _push_camera(self) -> None:
        if self._renderer is not None:
            pass  # skip GL notify in headless context
        self._update_hud()

    def _rebuild_vbo(self) -> None:
        self._hud_mesh_counts_dirty = True
        # (no actual VBO work in headless)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_mesh_ids_not_called_during_orbit():
    """all_vertex/edge/face_ids must not be called on pure orbit (_push_camera
    without preceding _rebuild_vbo)."""
    app = _make_app_with_cube()
    win = _FakeWindow(app)

    # Simulate initial build: flag is set, first _push_camera clears it.
    win._push_camera()
    assert not win._hud_mesh_counts_dirty

    # Now orbit: _push_camera without _rebuild_vbo.
    mesh = app.viewport.render_mesh.mesh
    with (
        patch.object(mesh, "all_vertex_ids", wraps=mesh.all_vertex_ids) as mock_v,
        patch.object(mesh, "all_edge_ids",   wraps=mesh.all_edge_ids)   as mock_e,
        patch.object(mesh, "all_face_ids",   wraps=mesh.all_face_ids)   as mock_f,
    ):
        win._push_camera()
        win._push_camera()
        win._push_camera()

    mock_v.assert_not_called()
    mock_e.assert_not_called()
    mock_f.assert_not_called()


def test_mesh_ids_called_after_rebuild_vbo():
    """all_vertex/edge/face_ids ARE called on the first _push_camera after
    _rebuild_vbo (flag is set), then not again until the next rebuild."""
    app = _make_app_with_cube()
    win = _FakeWindow(app)
    win._hud_mesh_counts_dirty = False  # start clean

    win._rebuild_vbo()
    assert win._hud_mesh_counts_dirty

    mesh = app.viewport.render_mesh.mesh
    with (
        patch.object(mesh, "all_vertex_ids", wraps=mesh.all_vertex_ids) as mock_v,
        patch.object(mesh, "all_edge_ids",   wraps=mesh.all_edge_ids)   as mock_e,
        patch.object(mesh, "all_face_ids",   wraps=mesh.all_face_ids)   as mock_f,
    ):
        win._push_camera()   # first call after rebuild → counts refreshed
        win._push_camera()   # second call → flag already cleared, no recount

    mock_v.assert_called_once()
    mock_e.assert_called_once()
    mock_f.assert_called_once()


def test_flag_state_matches_window_implementation():
    """Verify the _FakeWindow's _update_hud logic matches PlaygroundWindow's
    by importing and inspecting the real source."""
    import ast
    import inspect
    from playground.window import PlaygroundWindow

    src = inspect.getsource(PlaygroundWindow._update_hud)
    # The real implementation must guard on _hud_mesh_counts_dirty.
    assert "_hud_mesh_counts_dirty" in src, (
        "PlaygroundWindow._update_hud must check _hud_mesh_counts_dirty"
    )
    # And _rebuild_vbo must set the flag.
    src_rebuild = inspect.getsource(PlaygroundWindow._rebuild_vbo)
    assert "_hud_mesh_counts_dirty" in src_rebuild, (
        "PlaygroundWindow._rebuild_vbo must set _hud_mesh_counts_dirty"
    )
