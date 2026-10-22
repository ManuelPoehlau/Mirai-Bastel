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

RGBA = tuple[float, float, float, float]

#: PROVISIONAL colours of the `color` look, strongest .. weakest: red, orange, teal, blue.
BAND_COLORS: tuple[RGBA, ...] = (
    (1.0, 0.22, 0.15, 1.0),
    (1.0, 0.50, 0.08, 1.0),
    (0.15, 0.78, 0.70, 1.0),
    (0.25, 0.45, 1.0, 1.0),
)
#: PROVISIONAL point size in px (`color` look); below the selected point (6 px since 2026-10-22).
BAND_POINT_SIZE = 5.0
#: PROVISIONAL (2026-10-22) band colours and point size per look (`settings.LOOKS`): `mono` is one neutral
#: white that fades with the band, `tint` one muted coral (no yellow: that is the selection) that fades;
#: both no larger than the `color` points (5 px, below the 6 px selected point), so the surface stays the thing
#: you look at.
BAND_LOOKS: dict[str, tuple[tuple[RGBA, ...], float]] = {
    "mono": (
        ((1.0, 1.0, 1.0, 0.80), (1.0, 1.0, 1.0, 0.60), (1.0, 1.0, 1.0, 0.42), (1.0, 1.0, 1.0, 0.26)),
        5.0,
    ),
    "tint": (
        ((0.95, 0.55, 0.40, 0.85), (0.95, 0.55, 0.40, 0.62), (0.95, 0.55, 0.40, 0.42),
         (0.95, 0.55, 0.40, 0.25)),
        5.0,
    ),
    "color": (BAND_COLORS, BAND_POINT_SIZE),
}


def band_layer_styles(look: str) -> dict[str, tuple[RGBA, float]]:
    colors, size = BAND_LOOKS[look]
    return {layer: (colors[i], size) for i, layer in enumerate(BAND_LAYERS)}


class GLSoftBandOverlay(GLPointOverlay):
    """The band layers as a `GLPointOverlay` subclass (draw order: weakest first, so the
    strongest band is on top)."""

    LAYERS = tuple(reversed(BAND_LAYERS))
    #: The class default is the `color` look; `set_look` gives an instance its own styles.
    LAYER_STYLES = band_layer_styles("color")

    def __init__(self) -> None:
        super().__init__()
        self._bands: SoftBands = EMPTY_BANDS
        self.look = "color"
        #: True until the next `sync()`: the bands changed (or none were synced yet).
        self.dirty = False
        #: Number of `set_bands` calls so far (diagnostics/tests).
        self.pushes = 0

    @property
    def bands(self) -> SoftBands:
        return self._bands

    def set_look(self, look: str) -> None:
        """Colours of the band layers (`settings.LOOKS`); the points are unchanged, the next draw uses them."""
        self.look = look
        self.LAYER_STYLES = band_layer_styles(look)
        self.dirty = True

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
