"""`Viewport.set_surface_provider` — a host's replacement surface (AD-013 Addendum H7).

Headless (TraceStore). Contract (module docstring of `viewport.py`): `p.sync(mesh, selection)`
runs inside `Viewport.sync()` on the H1 triggers or when `p.dirty` is set and returns the moved
vertices of `p.surface_mesh`; a new `surface_mesh` object rebuilds the viewport-owned
`RenderMesh`; with `show_faces` it is drawn instead of the edit mesh, with the edit mesh's camera,
material, light, flat flag and matrix. Without a provider nothing changes.
"""

from __future__ import annotations

import tests._bootstrap  # noqa: F401

from core import Selection
from mirai.scene_factory import create_cube
from mirai.viewport.camera import OrbitCamera
from viewport import Viewport

LOG: list[str] = []


class _Provider:
    def __init__(self, surface=None) -> None:
        self.surface_mesh = surface
        self.dirty = False
        self.syncs: list[tuple] = []
        self.next_moved: set = set()

    def sync(self, mesh, selection):
        self.syncs.append((mesh, selection))
        self.dirty = False
        moved, self.next_moved = self.next_moved, set()
        return moved


def _instrument(render_mesh, name: str) -> None:
    store = render_mesh.store
    store.draw = lambda: LOG.append(name)
    store.set_light_uniforms = lambda uniforms: LOG.append(f"light:{name}")
    store.set_draw_style = lambda flat, polygon_offset, alpha=1.0: LOG.append(
        f"style:{name}:{flat}"
    )


def _viewport() -> Viewport:
    LOG.clear()
    vp = Viewport(create_cube(), selection=Selection())
    vp.bind_camera(OrbitCamera())
    _instrument(vp.render_mesh, "edit")
    vp.sync()
    return vp


def test_without_provider_the_edit_mesh_is_drawn():
    vp = _viewport()
    vp.render()
    assert "edit" in LOG
    assert vp.surface_render_mesh is None


def test_provider_surface_is_drawn_instead_of_the_edit_mesh():
    vp = _viewport()
    surface = create_cube()
    provider = _Provider(surface)
    vp.set_surface_provider(provider)
    vp.sync()
    rm = vp.surface_render_mesh
    assert rm is not None and rm.mesh is surface and rm.overlay is None
    assert rm.camera is vp.render_mesh.camera
    _instrument(rm, "surface")
    LOG.clear()
    vp.render()
    assert LOG == ["light:surface", "surface"]


def test_surface_not_drawn_in_wireframe():
    vp = _viewport()
    vp.set_surface_provider(_Provider(create_cube()))
    vp.sync()
    _instrument(vp.surface_render_mesh, "surface")
    vp.set_display(show_faces=False, show_edges=True, flat=False)
    LOG.clear()
    vp.render()
    assert "surface" not in LOG and "edit" not in LOG


def test_sync_triggers_are_the_h1_triggers_or_dirty():
    vp = _viewport()
    provider = _Provider(create_cube())
    vp.set_surface_provider(provider)
    vp.sync()
    assert provider.syncs == [(vp.mesh, vp.selection)]
    vp.sync()
    vp.on_camera_changed(aspect=1.5)
    vp.sync()
    assert len(provider.syncs) == 1  # idle frames and camera are not a change

    vertex = next(iter(vp.mesh.all_vertex_ids()))
    vp.on_vertices_moved({vertex})
    vp.sync()
    assert len(provider.syncs) == 2
    vp.on_topology_changed()
    vp.sync()
    assert len(provider.syncs) == 3
    provider.dirty = True
    vp.sync()
    assert len(provider.syncs) == 4


def test_moved_vertices_update_without_rebuild_and_new_mesh_rebuilds():
    vp = _viewport()
    surface = create_cube()
    provider = _Provider(surface)
    vp.set_surface_provider(provider)
    vp.sync()
    rm = vp.surface_render_mesh
    vertex = next(iter(surface.all_vertex_ids()))
    surface.set_vertex_position(vertex, (5.0, 5.0, 5.0))
    provider.next_moved = {vertex}
    provider.dirty = True
    rebuilds = rm.benchmark_counters.get("structural_rebuilds", 0)
    vp.sync()
    assert vp.surface_render_mesh is rm
    assert rm.benchmark_counters.get("structural_rebuilds", 0) == rebuilds
    index = rm.vertex_index_of(vertex)
    assert rm.store.data("positions")[index * 3:index * 3 + 3] == [5.0, 5.0, 5.0]

    provider.surface_mesh = create_cube()
    provider.dirty = True
    vp.sync()
    assert vp.surface_render_mesh is not rm
    assert vp.surface_render_mesh.mesh is provider.surface_mesh


def test_surface_none_or_provider_removed_draws_the_edit_mesh_again():
    vp = _viewport()
    provider = _Provider(create_cube())
    vp.set_surface_provider(provider)
    vp.sync()
    provider.surface_mesh = None
    provider.dirty = True
    vp.sync()
    assert vp.surface_render_mesh is None
    provider.surface_mesh = create_cube()
    provider.dirty = True
    vp.sync()
    assert vp.surface_render_mesh is not None
    vp.set_surface_provider(None)
    assert vp.surface_render_mesh is None
    LOG.clear()
    vp.render()
    assert "edit" in LOG


def test_flat_and_model_matrix_follow_the_edit_mesh():
    vp = _viewport()
    matrix = [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 2.0, 0, 0, 1.0]
    vp.set_model_matrix(matrix)
    vp.set_surface_provider(_Provider(create_cube()))
    vp.sync()
    rm = vp.surface_render_mesh
    assert rm.model_matrix == matrix
    _instrument(rm, "surface")
    LOG.clear()
    vp.set_display(show_faces=True, show_edges=False, flat=True)
    assert "style:surface:True" in LOG
    vp.set_model_matrix(None)
    assert rm.model_matrix is None


def test_camera_changes_reach_the_surface_without_asking_the_provider():
    # Manu, 2026-10-16: orbiting moved only the cage; the surface followed after the next hover.
    vp = _viewport()
    provider = _Provider(create_cube())
    vp.set_surface_provider(provider)
    vp.sync()
    rm = vp.surface_render_mesh
    vp.render_mesh.camera.orbit(30.0, 10.0)
    vp.on_camera_changed(aspect=1.7)
    vp.sync()
    assert len(provider.syncs) == 1  # a camera change is not a provider trigger
    assert rm.store.data("camera_uniforms") == vp.render_mesh.store.data("camera_uniforms")
    assert rm.aspect == 1.7


# -- H7-E: replacement surface of an object entry -------------------------------------------------


def test_entry_surface_is_drawn_instead_of_the_entry_with_its_matrix_and_follows_it():
    vp = _viewport()
    other, replacement = create_cube(), create_cube()
    vp.set_object_entry("a", other, model_matrix=[1.0] * 16)
    provider = _Provider()
    provider.entry_surfaces = {"a": replacement}
    provider.entry_moved = {}
    vp.set_surface_provider(provider)
    vp.sync()
    rm = vp.entry_surface_render_meshes["a"]
    assert rm.mesh is replacement and rm.camera is vp.object_entries["a"].camera
    assert rm.model_matrix == [1.0] * 16
    _instrument(vp.object_entries["a"], "entry")
    _instrument(rm, "entry-surface")
    LOG.clear()
    vp.render()
    assert "entry-surface" in LOG and "entry" not in LOG

    vp.set_object_entry("a", other, model_matrix=[2.0] * 16)  # the app moved the object
    vp.sync()
    assert vp.entry_surface_render_meshes["a"].model_matrix == [2.0] * 16

    moved = next(iter(replacement.all_vertex_ids()))
    replacement.set_vertex_position(moved, (7.0, 7.0, 7.0))
    provider.entry_moved = {"a": {moved}}
    provider.dirty = True
    vp.sync()
    assert vp.entry_surface_render_meshes["a"] is rm
    index = rm.vertex_index_of(moved)
    assert rm.store.data("positions")[index * 3:index * 3 + 3] == [7.0, 7.0, 7.0]


def test_entry_surface_is_released_when_the_provider_drops_it_or_the_entry_goes():
    vp = _viewport()
    vp.set_object_entry("a", create_cube())
    provider = _Provider()
    provider.entry_surfaces = {"a": create_cube()}
    vp.set_surface_provider(provider)
    vp.sync()
    assert "a" in vp.entry_surface_render_meshes
    provider.entry_surfaces = {}
    provider.dirty = True
    vp.sync()
    assert vp.entry_surface_render_meshes == {}
    provider.entry_surfaces = {"a": create_cube()}
    provider.dirty = True
    vp.sync()
    vp.remove_object_entry("a")
    assert vp.entry_surface_render_meshes == {}


def test_provider_without_entry_surfaces_changes_nothing_for_entries():
    vp = _viewport()
    vp.set_object_entry("a", create_cube())
    vp.set_surface_provider(_Provider(create_cube()))
    vp.sync()
    assert vp.entry_surface_render_meshes == {}
