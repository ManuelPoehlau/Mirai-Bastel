"""GL sink of the mask: masked vertices as dark points (Mask Geometry, `mirai.mask`).

A `GLPointOverlay` subclass attached with `Viewport.add_overlay` (the same contract as the soft bands:
`sync(mesh, selection)` and `dirty`). `Application` pushes the values with `set_values`; `sync` turns
them into positions at the mesh's current vertex positions, so the points follow a running gesture.
Like every point layer they ignore depth. Look values are `PROVISIONAL`.
"""

from __future__ import annotations

from viewport.gl_point_overlay import GLPointOverlay

from .mask import FULL

MASK_LAYER_FULL = "mask_full"
MASK_LAYER_PARTIAL = "mask_partial"


class GLMaskOverlay(GLPointOverlay):
    """Fully masked vertices near-black, partially masked ones grey; both a little larger than the soft
    bands so the protection reads at a glance."""

    LAYERS = (MASK_LAYER_PARTIAL, MASK_LAYER_FULL)
    LAYER_STYLES = {
        MASK_LAYER_PARTIAL: ((0.45, 0.45, 0.50, 0.90), 6.0),
        MASK_LAYER_FULL: ((0.04, 0.04, 0.06, 1.0), 7.0),
    }

    def __init__(self) -> None:
        super().__init__()
        self._values: dict = {}
        #: True until the next `sync()`: the values changed (or none were synced yet).
        self.dirty = False

    @property
    def values(self) -> dict:
        return dict(self._values)

    def set_values(self, values) -> None:
        self._values = dict(values)
        self.dirty = True

    def sync(self, mesh, selection) -> None:
        full, partial = [], []
        for vid, m in self._values.items():
            if mesh.is_valid_vertex(vid):
                (full if m >= FULL else partial).append(mesh.vertex_position(vid))
        self.set_points(MASK_LAYER_FULL, full)
        self.set_points(MASK_LAYER_PARTIAL, partial)
        self.dirty = False
