"""Influence bands: weights -> band index -> positions (WP-SOFT-01 S2b, AD-020 §5).

Headless data behind the window's Soft Selection look: which influenced vertices fall into
which of `BAND_COUNT` bands over `0 < w < 1`, strongest band first. Seeds (`w == 1`) are not
part of any band - they keep the existing selection look. Nothing here computes influence
(`Application` hands in the weights, review F9) and nothing here knows GL; the GL sink is
`gl_bands.GLSoftBandOverlay`.

Band edges are `PROVISIONAL` look values (S2c verdict): equal widths over `(0, 1)`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Mapping

from core import Mesh, VertexId

Position = tuple[float, float, float]

#: PROVISIONAL (handoff E5): four equal bands, index 0 = strongest (warm) .. 3 = weakest (cold).
BAND_COUNT = 4


def band_index(weight: float) -> int | None:
    """Band of `weight`, or None when it carries no band point (`w <= 0` is no influence,
    `w >= 1` is a seed). Band `i` covers `(1 - (i + 1) / N, 1 - i / N]`, so `0.75 < w < 1`
    is band 0 and `0 < w <= 0.25` is the last one."""
    if not 0.0 < weight < 1.0:
        return None
    return min(BAND_COUNT - 1, int(math.floor((1.0 - weight) * BAND_COUNT)))


@dataclass(frozen=True)
class SoftBands:
    """The band membership of one influence map: `bands[i]` are the vertices of band `i`
    (sorted, so equal maps compare equal), `weights` the `0 < w < 1` entries they came from
    (kept so a test can pin "preview weights == the op's weights at `begin()`")."""

    bands: tuple[tuple[VertexId, ...], ...] = field(
        default_factory=lambda: tuple(() for _ in range(BAND_COUNT))
    )
    weights: Mapping[VertexId, float] = field(default_factory=dict)

    @classmethod
    def from_weights(cls, weights: Mapping[VertexId, float]) -> "SoftBands":
        """Bands of an influence map as `compute_influence` returns it; seeds (`w == 1`)
        and zero weights are left out."""
        members: list[list[VertexId]] = [[] for _ in range(BAND_COUNT)]
        kept: dict[VertexId, float] = {}
        for vid, w in weights.items():
            index = band_index(w)
            if index is None:
                continue
            members[index].append(vid)
            kept[vid] = w
        return cls(tuple(tuple(sorted(m)) for m in members), kept)

    @property
    def count(self) -> int:
        return sum(len(b) for b in self.bands)

    def __bool__(self) -> bool:
        return self.count > 0

    def positions(self, mesh: Mesh) -> tuple[list[Position], ...]:
        """World positions per band at the mesh's *current* positions (so the points follow
        a drag). Vertices the mesh no longer knows are skipped."""
        valid = mesh.is_valid_vertex
        position = mesh.vertex_position
        return tuple([position(v) for v in band if valid(v)] for band in self.bands)


#: The no-influence state (soft off, bands off, empty selection, a selection symmetric Soft refuses).
EMPTY_BANDS = SoftBands()
