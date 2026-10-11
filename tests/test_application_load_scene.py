"""`Application.load_scene` — Szenenwechsel zur Laufzeit (PROVISIONAL).

`init_scene` tauscht Mesh und Viewport, lässt aber Selection, History und
Hover der alten Szene stehen; genau diesen mesh-gebundenen Zustand räumt
`load_scene` auf. Bewusst Cube-only, ohne `examples/`-Abhängigkeit.
"""

from __future__ import annotations

import tests._bootstrap  # noqa: F401

from mirai.application import Application
from mirai.interaction import commands
from mirai.mesh_geometry import mesh_center_and_radius
from mirai.viewport import OrbitCamera
from viewport.resource_store import TraceStore


def _app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.set_viewport_size(800, 600)
    return app


def _nudge_first_vertex(app: Application) -> None:
    """Ein History-Eintrag inklusive Selection-Mirror über den public Entry."""
    mesh = app.scene.mesh
    vid = sorted(mesh.all_vertex_ids())[0]

    def bump():
        x, y, z = mesh.vertex_position(vid)
        mesh.set_vertex_position(vid, (x + 0.1, y, z))
        return {vid}

    assert app.apply_mesh_change("nudge", bump) is True


def test_load_scene_swaps_the_mesh_and_keeps_scene_and_selection_identity():
    app = _app()
    scene, selection, viewport = app.scene, app.selection, app.viewport
    mesh_before = app.scene.mesh

    app.load_scene("cube")

    assert app.scene is scene
    assert app.selection is selection  # dasselbe Selection-Objekt wie im Viewport
    assert app.scene.mesh is not mesh_before
    assert app.viewport is not viewport
    assert len(app.scene.mesh.all_vertex_ids()) == 8


def test_load_scene_clears_selection_history_and_the_mirrors():
    app = _app()
    vid = sorted(app.scene.mesh.all_vertex_ids())[0]
    app.selection.set({vid})
    _nudge_first_vertex(app)
    assert len(app.history) == 1
    assert len(app._selection_undo_stack) == 1

    app.load_scene("cube")

    assert app.history is app.scene.history
    assert len(app.history) == 0
    assert app._selection_undo_stack == []
    assert app._selection_redo_stack == []
    assert not app.selection.vertices
    assert not app.selection.edges
    assert not app.selection.faces


def test_load_scene_invalidates_the_pick_cache_clears_hover_and_keeps_the_size():
    app = _app()
    generation = app._pick_cache._generation

    app.load_scene("cube")

    assert app._pick_cache._generation > generation
    assert app.selection.hovered is None
    assert (app.viewport_width, app.viewport_height) == (800, 600)


def test_load_scene_reframes_the_camera_on_the_new_bounds():
    app = _app()
    # Kamera erst aus der Spur fahren, damit das Ausrichten sichtbar wird.
    app.camera.yaw += 1.0
    app.camera.distance *= 2.0

    app.load_scene("cube")

    center, radius = mesh_center_and_radius(app.scene.mesh)
    reference = OrbitCamera()
    reference.frame_on_bounds(center, radius)
    assert app.camera.target == center
    assert app.camera.distance == reference.distance


# -- Soft Selection overlay through the scene loader (WP-SOFT-01 S2b) -----------------------


def test_load_scene_accepts_every_backend_init_scene_accepts():
    # The loader forwards the backend wiring to `init_scene`; a backend added to one
    # signature and not the other is the bug this pins (`soft_overlay_type`, 2026-10-11).
    import inspect

    backends = {
        name
        for name in inspect.signature(Application.init_scene).parameters
        if name.endswith("_type")
    }
    assert backends <= set(inspect.signature(Application.load_scene).parameters)


def test_load_scene_takes_the_full_main_gl_types_set():
    # Real keys of `src/main.py::GL_TYPES`, headless stand-ins (no GL context needed here).
    from mirai.soft_selection import GLSoftBandOverlay

    gl_types = {
        "store_type": TraceStore,
        "point_overlay_type": None,
        "line_overlay_type": None,
        "face_overlay_type": None,
        "soft_overlay_type": GLSoftBandOverlay,
    }
    app = _app()

    app.load_scene("cube", **gl_types)

    assert isinstance(app._soft_overlay, GLSoftBandOverlay)
    assert app._soft_overlay in app.viewport.extra_overlays


def test_load_scene_with_soft_on_and_a_selection_shows_no_bands_of_the_old_scene():
    # Head -> head: the old ids are valid in the new mesh, so `init_scene` alone would
    # compute (and keep showing) bands for a selection the loader then clears.
    import math

    from tests.soft_selection_fixtures import HEAD_OBJ  # noqa: F401  (examples/ on sys.path)

    from mirai.soft_selection import EMPTY_BANDS, GLSoftBandOverlay

    app = Application()
    app.init_scene("obj", obj_path=HEAD_OBJ, soft_overlay_type=GLSoftBandOverlay)
    app.frame_scene()
    app.set_viewport_size(800, 600)
    app.dispatch_command(commands.SOFT_TOGGLE)
    mesh, eye = app.scene.mesh, app.camera.eye()
    vid = min(mesh.all_vertex_ids(), key=lambda v: math.dist(mesh.vertex_position(v), eye))
    x, y = app.camera.project_to_screen(mesh.vertex_position(vid), 800, 600)
    assert app.select_at(commands.SELECT, x, y)
    assert app.soft_bands != EMPTY_BANDS
    old_overlay = app._soft_overlay

    app.load_scene("obj", obj_path=HEAD_OBJ, soft_overlay_type=GLSoftBandOverlay)

    assert app.selection.vertices == set()
    assert app._soft_overlay is not old_overlay  # bound to the new viewport
    assert app.soft_bands == EMPTY_BANDS  # selection is cleared, so is the preview
    assert app.soft_settings.enabled  # the sticky setting survives the scene change
