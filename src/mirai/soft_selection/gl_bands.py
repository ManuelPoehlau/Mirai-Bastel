"""GL sink of the influence bands: a `GLPointOverlay` with band layers (WP-SOFT-01 S2b, AD-020 §5).

Attached with `Viewport.add_overlay` (WP-SYM-LAB-03 H1 contract: `sync(mesh, selection)` and
`dirty`, `draw(camera_uniforms)`); the Viewport knows neither soft selection nor these layers.
`Application` pushes the bands with `set_bands()` (which sets `dirty`); `sync()` only turns
them into positions at the mesh's current vertex positions - it never computes influence, so a
drag costs one position lookup per band vertex per move (F9).

Look values are `PROVISIONAL` (S2c verdict): warm (strong) -> cold (weak), smaller than the
selection point (8 px) and the hover point (10 px), no yellow, so the bands stay apart from
both. Like every point layer they ignore depth. Seeds are drawn by the Viewport's own point
overlay after this one, so they stay on top.
"""

from __future__ import annotations

from viewport.gl_point_overlay import GLPointOverlay

from .bands import BAND_COUNT, EMPTY_BANDS, SoftBands

#: Layer names, strongest band first (`bands.SoftBands.bands` order).
BAND_LAYERS: tuple[str, ...] = tuple(f"soft_band_{i}" for i in range(BAND_COUNT))

#: PROVISIONAL colours, strongest .. weakest: red, orange, teal, blue.
BAND_COLORS: tuple[tuple[float, float, float, float], ...] = (
    (1.0, 0.22, 0.15, 1.0),
    (1.0, 0.50, 0.08, 1.0),
    (0.15, 0.78, 0.70, 1.0),
    (0.25, 0.45, 1.0, 1.0),
)
#: PROVISIONAL point size in px.
BAND_POINT_SIZE = 6.0


class GLSoftBandOverlay(GLPointOverlay):
    """The band layers as a `GLPointOverlay` subclass (draw order: weakest first, so the
    strongest band is on top)."""

    LAYERS = tuple(reversed(BAND_LAYERS))
    LAYER_STYLES = {layer: (BAND_COLORS[i], BAND_POINT_SIZE) for i, layer in enumerate(BAND_LAYERS)}

    def __init__(self) -> None:
        super().__init__()
        self._bands: SoftBands = EMPTY_BANDS
        #: True until the next `sync()`: the bands changed (or none were synced yet).
        self.dirty = False
        #: Number of `set_bands` calls so far (diagnostics/tests).
        self.pushes = 0

    @property
    def bands(self) -> SoftBands:
        return self._bands

    def set_bands(self, bands: SoftBands) -> None:
        self._bands = bands
        self.dirty = True
        self.pushes += 1

    def sync(self, mesh, selection) -> None:
        """Viewport contract. Positions at the mesh's current vertex positions; unchanged
        layers are not rebuilt (`set_points` compares)."""
        for layer, positions in zip(BAND_LAYERS, self._bands.positions(mesh)):
            self.set_points(layer, positions)
        self.dirty = False
