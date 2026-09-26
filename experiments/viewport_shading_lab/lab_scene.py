"""Scene setup shared by the window, `evidence.py` and the tests (handoff E16).

Adapted from `experiments/ad018_gl_render_store_verification/run.py` (mesh →
`RenderMesh` with a GL store → `OrbitCamera` framed on bounds) and the asset
CLI of `experiments/symmetry_lab/lab_scene.py` (rebuilt, not imported — E1).

GL stores need an active GL context at the first `allocate()`, i.e. the
caller creates the window before `build_scene()` (see `src/main.py`).
`resolve_asset_name()` is GL-free so `run.py` can reject a bad name before
any window opens.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core import Selection
from loaders.assets import asset_names, asset_path
from mirai.mesh_geometry import mesh_center_and_radius
from mirai.scene_factory import build_core_scene_from_obj
from mirai.viewport.camera import OrbitCamera
from viewport.overlay import SelectionOverlay
from viewport.render_mesh import RenderMesh

DEFAULT_ASSET = "head_basemesh"
#: Production clear color (`src/main.py`); background is Slice 3, not here (A6).
CLEAR_COLOR = (0.05, 0.05, 0.08)


class UnknownAssetError(LookupError):
    """Asset name is not registered in `loaders.assets.asset_names()`."""


def resolve_asset_name(name: str) -> str:
    """Returns `name` or raises `UnknownAssetError` listing all valid names."""
    valid = asset_names()
    if name not in valid:
        raise UnknownAssetError(
            f"Unbekanntes Asset {name!r}. Gültige Namen: {', '.join(valid)}"
        )
    return name


@dataclass
class LabScene:
    asset_name: str
    mesh: object
    selection: Selection
    camera: OrbitCamera
    render_mesh: RenderMesh

    @property
    def store(self):
        return self.render_mesh.store

    def camera_changed(self, aspect: float) -> None:
        """Camera/aspect change → `camera_uniforms` via the regular dirty path."""
        self.render_mesh.mark_camera_dirty(aspect=aspect)

    def draw(self, rig_uniforms: Optional[dict] = None) -> None:
        """Clears, syncs pending dirty state and draws the mesh (no HUD).
        `rig_uniforms` is ignored by stores without `set_rig_uniforms()`
        (the production `GLRenderStore`, for the baseline comparison)."""
        from pyglet import gl

        gl.glClearColor(*CLEAR_COLOR, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)
        self.render_mesh.sync()
        setter = getattr(self.store, "set_rig_uniforms", None)
        if rig_uniforms is not None and setter is not None:
            setter(rig_uniforms)
        self.render_mesh.render(self.camera)


def build_scene(
    asset_name: str,
    store_type: type,
    aspect: float,
    camera: Optional[OrbitCamera] = None,
) -> LabScene:
    """Loads the asset, frames a new camera on its bounds (unless `camera` is
    given) and builds + syncs a `RenderMesh` on `store_type`. Empty selection:
    the highlight path exists but stays untouched (E16)."""
    resolve_asset_name(asset_name)
    mesh = build_core_scene_from_obj(str(asset_path(asset_name))).mesh
    selection = Selection()
    render_mesh = RenderMesh(mesh, overlay=SelectionOverlay(selection), store_type=store_type)
    if camera is None:
        camera = OrbitCamera()
        center, radius = mesh_center_and_radius(mesh)
        camera.frame_on_bounds(center, radius)
    render_mesh.bind_camera(camera)
    render_mesh.mark_camera_dirty(aspect=aspect)
    render_mesh.sync()
    return LabScene(asset_name, mesh, selection, camera, render_mesh)


def read_rgba(width: int, height: int) -> bytes:
    """RGBA bytes of the current color buffer (bottom-up rows), after `glFinish`."""
    import pyglet
    from pyglet import gl

    gl.glFinish()
    buffer = pyglet.image.get_buffer_manager().get_color_buffer()
    image = buffer.get_region(0, 0, width, height).get_image_data()
    return bytes(image.get_data("RGBA", width * 4))


def save_color_buffer_png(path: str) -> None:
    """Writes the current color buffer as PNG (pyglet's encoder; PIL not required)."""
    import pyglet
    from pyglet import gl

    gl.glFinish()
    pyglet.image.get_buffer_manager().get_color_buffer().save(path)
