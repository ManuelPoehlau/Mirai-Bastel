"""Soft Selection influence bands (WP-SOFT-01 S2b, AD-020 §5): weights -> band -> positions,
and the `GLPointOverlay` subclass as their sink. Headless: no GL context is needed to hold
bands and positions (the layers are rebuilt only inside `draw()`).
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401
from tests.soft_selection_fixtures import HEAD_OBJ  # noqa: F401

from core import VertexId
from mirai.scene_factory import build_core_scene_from_obj
from mirai.soft_selection import (
    BAND_COUNT,
    BAND_LAYERS,
    EMPTY_BANDS,
    GLSoftBandOverlay,
    SoftBands,
    band_index,
)
from viewport.gl_point_overlay import GLPointOverlay, HOVER_COLOR, SELECTED_COLOR


def test_four_bands_by_default():
    assert BAND_COUNT == 4
    assert len(BAND_LAYERS) == 4


@pytest.mark.parametrize(
    "weight,expected",
    [
        (0.0, None),        # no influence
        (-0.1, None),
        (1.0, None),        # seed: keeps the selection look
        (1.5, None),
        (1e-9, 3),
        (0.25, 3),          # upper edge belongs to the weaker band
        (0.2500001, 2),
        (0.5, 2),
        (0.5000001, 1),
        (0.75, 1),
        (0.7500001, 0),
        (0.999999, 0),
    ],
)
def test_band_index_boundaries(weight, expected):
    assert band_index(weight) == expected


def test_nan_has_no_band():
    assert band_index(float("nan")) is None


def test_from_weights_excludes_seeds_and_zero_and_sorts():
    weights = {
        VertexId(9): 1.0,   # seed
        VertexId(4): 0.9,
        VertexId(2): 0.8,
        VertexId(7): 0.6,
        VertexId(5): 0.1,
        VertexId(6): 0.0,   # no influence
    }
    bands = SoftBands.from_weights(weights)
    assert bands.bands == (
        (VertexId(2), VertexId(4)),
        (VertexId(7),),
        (),
        (VertexId(5),),
    )
    assert bands.count == 4
    assert bands.weights == {VertexId(4): 0.9, VertexId(2): 0.8, VertexId(7): 0.6, VertexId(5): 0.1}
    assert bool(bands)


def test_empty_weights_and_seeds_only_give_the_empty_bands():
    assert SoftBands.from_weights({}) == EMPTY_BANDS
    assert SoftBands.from_weights({VertexId(1): 1.0}) == EMPTY_BANDS
    assert not EMPTY_BANDS and EMPTY_BANDS.count == 0
    assert len(EMPTY_BANDS.bands) == BAND_COUNT


def test_equal_maps_compare_equal_whatever_the_insertion_order():
    a = SoftBands.from_weights({VertexId(1): 0.9, VertexId(2): 0.3})
    b = SoftBands.from_weights({VertexId(2): 0.3, VertexId(1): 0.9})
    assert a == b


def test_positions_follow_the_mesh_and_skip_dead_vertices():
    mesh = build_core_scene_from_obj(HEAD_OBJ).mesh
    ids = mesh.all_vertex_ids()
    a, b, c = ids[10], ids[11], ids[12]
    bands = SoftBands.from_weights({a: 0.9, b: 0.1, c: 0.6})
    first = bands.positions(mesh)
    assert first[0] == [mesh.vertex_position(a)]
    assert first[1] == [mesh.vertex_position(c)]
    assert first[2] == []
    assert first[3] == [mesh.vertex_position(b)]

    x, y, z = mesh.vertex_position(a)
    mesh.set_vertex_position(a, (x + 1.0, y, z))
    assert bands.positions(mesh)[0] == [(x + 1.0, y, z)]

    # A vertex the mesh no longer knows is skipped instead of raising.
    ghost = SoftBands.from_weights({VertexId(10_000_000): 0.9, a: 0.9})
    assert ghost.positions(mesh)[0] == [(x + 1.0, y, z)]


# -- the GL sink (data side; drawing is in tests/test_gl_soft_bands.py) -----------------


def test_overlay_is_a_point_overlay_with_band_layers_only():
    assert issubclass(GLSoftBandOverlay, GLPointOverlay)
    assert set(GLSoftBandOverlay.LAYERS) == set(BAND_LAYERS)
    assert set(GLSoftBandOverlay.LAYER_STYLES) == set(BAND_LAYERS)
    # Weakest first, so the strongest band is drawn on top.
    assert GLSoftBandOverlay.LAYERS == tuple(reversed(BAND_LAYERS))
    # The base class is untouched.
    assert not set(BAND_LAYERS) & set(GLPointOverlay.LAYERS)


def test_band_look_is_distinct_from_selection_and_hover():
    colors = [GLSoftBandOverlay.LAYER_STYLES[layer][0] for layer in BAND_LAYERS]
    assert len(set(colors)) == BAND_COUNT
    for color in colors:
        assert color != SELECTED_COLOR and color != HOVER_COLOR
    sizes = {GLSoftBandOverlay.LAYER_STYLES[layer][1] for layer in BAND_LAYERS}
    assert max(sizes) < GLPointOverlay.LAYER_STYLES["selected"][1]


def test_set_bands_marks_dirty_and_sync_publishes_positions():
    mesh = build_core_scene_from_obj(HEAD_OBJ).mesh
    ids = mesh.all_vertex_ids()
    overlay = GLSoftBandOverlay()
    assert overlay.dirty is False and overlay.bands == EMPTY_BANDS

    bands = SoftBands.from_weights({ids[3]: 0.9, ids[4]: 0.3})
    overlay.set_bands(bands)
    assert overlay.dirty is True and overlay.bands is bands
    assert overlay.points(BAND_LAYERS[0]) == []  # nothing before the viewport syncs

    overlay.sync(mesh, None)
    assert overlay.dirty is False
    assert overlay.points(BAND_LAYERS[0]) == [mesh.vertex_position(ids[3])]
    assert overlay.points(BAND_LAYERS[2]) == [mesh.vertex_position(ids[4])]
    assert overlay.points(BAND_LAYERS[1]) == [] and overlay.points(BAND_LAYERS[3]) == []


def test_sync_follows_moved_vertices_without_new_bands():
    mesh = build_core_scene_from_obj(HEAD_OBJ).mesh
    vid = mesh.all_vertex_ids()[5]
    overlay = GLSoftBandOverlay()
    overlay.set_bands(SoftBands.from_weights({vid: 0.9}))
    overlay.sync(mesh, None)
    x, y, z = mesh.vertex_position(vid)
    mesh.set_vertex_position(vid, (x, y + 2.0, z))
    overlay.sync(mesh, None)
    assert overlay.points(BAND_LAYERS[0]) == [(x, y + 2.0, z)]
    assert overlay.pushes == 1  # moving is not a new push


def test_unchanged_layers_are_not_rebuilt():
    mesh = build_core_scene_from_obj(HEAD_OBJ).mesh
    vid = mesh.all_vertex_ids()[5]
    overlay = GLSoftBandOverlay()
    overlay.set_bands(SoftBands.from_weights({vid: 0.9}))
    overlay.sync(mesh, None)
    stale = set(overlay._stale)
    overlay.sync(mesh, None)
    assert overlay._stale == stale == {BAND_LAYERS[0]}
