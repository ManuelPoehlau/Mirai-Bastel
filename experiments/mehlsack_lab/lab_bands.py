"""Signed influence bands (handoff E8): positive weights warm, negative weights cool.

Headless part: `SignedBands.from_weights()` sorts `0 < w < 1` into the four positive
bands of `mirai.soft_selection.bands.band_index` (same edges as the app) and `w < 0`
into four negative bands by `|w|` (same edges; `w = -1` is the strongest negative band).
Seeds (`w == 1`) are drawn as hover points by the scene, `w == 0` is never drawn.

GL part: `GLSignedBandOverlay` is a `GLPointOverlay` subclass with eight layers (the
H1/S2b precedent of `GLSoftBandOverlay`); `sync(mesh)` only turns the pushed bands into
positions at the mesh's current positions — it computes no influence.

Colours are `PROVISIONAL`. The app's band set runs warm → cold *within* the positive
weights (red, orange, teal, blue). Here blue has to mean "moves against the drag"
(practical test step 4), so the lab keeps the app's two warm colours for the strong
positive bands and replaces the cool tail with two lab-local warm tones (rose), and
draws the negative bands in a lab-local blue set. Open point in the README.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from core import Mesh, VertexId
from mirai.soft_selection import BAND_COUNT, band_index
from mirai.soft_selection.gl_bands import BAND_COLORS, BAND_POINT_SIZE
from viewport.gl_point_overlay import GLPointOverlay

Position = tuple[float, float, float]
RGBA = tuple[float, float, float, float]


def negative_band_index(weight: float):
    """Band of a negative weight by `|w|` (0 = strongest), None for `w >= 0`."""
    if not weight < 0.0:
        return None
    magnitude = -weight
    if magnitude >= 1.0:
        return 0
    return band_index(magnitude)


@dataclass(frozen=True)
class SignedBands:
    positive: tuple[tuple[VertexId, ...], ...] = field(
        default_factory=lambda: tuple(() for _ in range(BAND_COUNT))
    )
    negative: tuple[tuple[VertexId, ...], ...] = field(
        default_factory=lambda: tuple(() for _ in range(BAND_COUNT))
    )

    @classmethod
    def from_weights(cls, weights: Mapping[VertexId, float]) -> "SignedBands":
        pos: list[list[VertexId]] = [[] for _ in range(BAND_COUNT)]
        neg: list[list[VertexId]] = [[] for _ in range(BAND_COUNT)]
        for vid, w in weights.items():
            if w < 0.0:
                neg[negative_band_index(w)].append(vid)
            else:
                index = band_index(w)  # None for seeds (w == 1) and w == 0
                if index is not None:
                    pos[index].append(vid)
        return cls(tuple(tuple(sorted(b)) for b in pos), tuple(tuple(sorted(b)) for b in neg))

    @property
    def positive_count(self) -> int:
        return sum(len(b) for b in self.positive)

    @property
    def negative_count(self) -> int:
        return sum(len(b) for b in self.negative)

    def positions(self, mesh: Mesh) -> tuple[list[Position], ...]:
        """Positive bands then negative bands, at the mesh's current positions."""
        valid = mesh.is_valid_vertex
        position = mesh.vertex_position
        return tuple([position(v) for v in band if valid(v)] for band in self.positive + self.negative)


EMPTY_SIGNED_BANDS = SignedBands()

POSITIVE_LAYERS: tuple[str, ...] = tuple(f"pos_band_{i}" for i in range(BAND_COUNT))
NEGATIVE_LAYERS: tuple[str, ...] = tuple(f"neg_band_{i}" for i in range(BAND_COUNT))
#: PROVISIONAL, strongest .. weakest: the app's red and orange, then two lab-local rose tones.
POSITIVE_COLORS: tuple[RGBA, ...] = (
    BAND_COLORS[0],
    BAND_COLORS[1],
    (0.95, 0.42, 0.55, 1.0),
    (0.72, 0.36, 0.44, 1.0),
)
#: PROVISIONAL, strongest .. weakest |w|: lab-local blues.
NEGATIVE_COLORS: tuple[RGBA, ...] = (
    (0.20, 0.42, 1.0, 1.0),
    (0.30, 0.62, 1.0, 1.0),
    (0.48, 0.78, 0.98, 1.0),
    (0.58, 0.64, 0.86, 1.0),
)


class GLSignedBandOverlay(GLPointOverlay):
    """Eight band layers; draw order weakest first, so the strongest bands are on top."""

    LAYERS = tuple(reversed(NEGATIVE_LAYERS)) + tuple(reversed(POSITIVE_LAYERS))
    LAYER_STYLES = {
        **{layer: (POSITIVE_COLORS[i], BAND_POINT_SIZE) for i, layer in enumerate(POSITIVE_LAYERS)},
        **{layer: (NEGATIVE_COLORS[i], BAND_POINT_SIZE) for i, layer in enumerate(NEGATIVE_LAYERS)},
    }

    def __init__(self) -> None:
        super().__init__()
        self.bands: SignedBands = EMPTY_SIGNED_BANDS
        self.visible = True

    def set_bands(self, bands: SignedBands) -> None:
        self.bands = bands

    def sync(self, mesh: Mesh) -> None:
        bands = self.bands if self.visible else EMPTY_SIGNED_BANDS
        for layer, positions in zip(POSITIVE_LAYERS + NEGATIVE_LAYERS, bands.positions(mesh)):
            self.set_points(layer, positions)
