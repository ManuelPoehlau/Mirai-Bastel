"""`Application.load_scene` — Szenenwechsel zur Laufzeit (PROVISIONAL).

`init_scene` tauscht Mesh und Viewport, lässt aber Selection, History und
Hover der alten Szene stehen; genau diesen mesh-gebundenen Zustand räumt
`load_scene` auf. Bewusst Cube-only, ohne `examples/`-Abhängigkeit.
"""

from __future__ import annotations

import tests._bootstrap  # noqa: F401

from mirai.application import Application
from mirai.mesh_geometry import mesh_center_and_radius
from mirai.viewport import OrbitCamera


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
