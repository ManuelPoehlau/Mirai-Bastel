"""Slice 2a E14, headless: preview colour data — sign → hue, |w| → strength, w = 0 → alpha 0;
only faces touched by the influence; per-vertex corners; the overlay computes no influence
and only rebuilds when positions, weights or visibility change."""

from __future__ import annotations

import pytest

from mehlsack_lab.lab_preview import (
    PREVIEW_ALPHA_MAX,
    PREVIEW_BLUE,
    PREVIEW_LAYER,
    PREVIEW_ORANGE,
    GLInfluencePreviewOverlay,
    preview_color,
    preview_triangles,
    touched_faces,
)
from mehlsack_lab.signed_curve import PRESET_HAT, SignedCurve
from mehlsack_lab.signed_influence import signed_influence

from .helpers import box, mid_target


@pytest.mark.parametrize("w", [1.0, 0.75, 0.5, 0.1, 1e-6])
def test_sign_gives_hue_and_magnitude_gives_strength(w):
    pos, neg = preview_color(w), preview_color(-w)
    assert pos[:3] == PREVIEW_ORANGE and neg[:3] == PREVIEW_BLUE
    assert pos[3] == neg[3] == pytest.approx(w * PREVIEW_ALPHA_MAX)


def test_zero_is_transparent_and_seeds_are_strongest():
    assert preview_color(0.0)[3] == 0.0
    assert preview_color(1.0)[3] == PREVIEW_ALPHA_MAX
    alphas = [preview_color(w)[3] for w in (0.1, 0.3, 0.6, 0.9, 1.0)]
    assert alphas == sorted(alphas) and len(set(alphas)) == 5  # monotone in |w|


def test_triangles_cover_exactly_the_touched_faces_with_per_vertex_colours():
    mesh = box(h=10, n=5)
    _, target = mid_target(mesh)
    weights = signed_influence(mesh, target.seeds, 1.2, "geodesic", SignedCurve.from_preset(PRESET_HAT))
    assert any(w < 0 for w in weights.values())
    faces = touched_faces(mesh, weights)
    assert faces and len(faces) < len(mesh.all_face_ids())
    for f in mesh.all_face_ids():
        touched = any(weights.get(v, 0.0) != 0.0 for v in mesh.face_vertices(f))
        assert (f in faces) == touched
    triangles, colours = preview_triangles(mesh, weights)
    assert len(triangles) == len(colours) == 2 * len(faces)  # quads -> two triangles each
    by_position = {mesh.vertex_position(v): v for v in mesh.all_vertex_ids()}
    for tri, corners in zip(triangles, colours):
        for p, rgba in zip(tri, corners):
            assert rgba == preview_color(weights.get(by_position[p], 0.0))
    assert not preview_triangles(mesh, {})[0]


def test_overlay_rebuilds_only_on_change_and_computes_no_influence():
    mesh = box(h=6, n=3)
    _, target = mid_target(mesh)
    weights = {v: 1.0 for v in target.seeds}
    overlay = GLInfluencePreviewOverlay()
    assert overlay.visible is False
    overlay.set_weights(weights)
    overlay.sync(mesh, version=1)
    assert overlay.triangle_count(PREVIEW_LAYER) == 0  # off: nothing to draw
    overlay.visible = True
    overlay.sync(mesh, version=1)
    count = overlay.triangle_count(PREVIEW_LAYER)
    assert count == len(preview_triangles(mesh, weights)[0]) > 0
    assert len(overlay.colors()) == count * 3 * 4
    stale = set(overlay._stale)
    overlay._stale.clear()
    overlay.sync(mesh, version=1)  # nothing changed: no rebuild
    assert not overlay._stale
    overlay.sync(mesh, version=2)  # positions "changed" but equal: data equal, no upload marked
    assert not overlay._stale
    overlay.set_weights({v: -0.5 for v in target.seeds})
    overlay.sync(mesh, version=2)
    assert overlay._stale == stale == {PREVIEW_LAYER}
