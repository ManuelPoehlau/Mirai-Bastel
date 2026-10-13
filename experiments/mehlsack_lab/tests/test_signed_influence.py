"""§7.4 Influence: with `CURVES["smooth"]` the lab influence equals `compute_influence` bit for
bit; with a signed curve negative weights are present and `w == 0` vertices are absent.
Plus the distance cache and the signed bands."""

from __future__ import annotations

import pytest

from mehlsack_lab.lab_bands import SignedBands, negative_band_index
from mehlsack_lab.signed_curve import DEFAULT_CURVE, PRESET_HAT, SignedCurve
from mehlsack_lab.signed_influence import DistanceCache, signed_influence
from mirai.soft_selection import BAND_COUNT, CURVES, METRICS, band_index, compute_influence

from .helpers import box, mid_target


def smooth_of_x(x):
    """`CURVES["smooth"]` on the lab's axis (x = d/r): the same float ops as
    `compute_influence`'s `shape(1.0 - d / radius)`."""
    return CURVES["smooth"](1.0 - x)


@pytest.mark.parametrize("metric", sorted(METRICS))
@pytest.mark.parametrize("radius", [0.0, 0.4, 1.0, 2.5, 10.0])
@pytest.mark.parametrize("mode", ["loop", "ring"])
def test_smooth_equals_compute_influence_bit_for_bit(metric, radius, mode):
    mesh = box(h=6, n=4)
    _, target = mid_target(mesh, mode)
    lab = signed_influence(mesh, target.seeds, radius, metric, smooth_of_x)
    app = compute_influence(mesh, target.seeds, radius, metric=metric, curve="smooth")
    assert lab == app  # same keys, same float values (== on floats is bitwise here)


@pytest.mark.parametrize("metric", sorted(METRICS))
@pytest.mark.parametrize("radius", [0.0, 0.4, 1.0, 2.5, 10.0])
@pytest.mark.parametrize("mode", ["loop", "ring"])
def test_smooth_preset_equals_compute_influence(metric, radius, mode):
    """Slice 2a E13: the Smooth preset *is* smoothstep, so the lab influence with the preset
    itself (not a stand-in lambda) equals the app's within 1e-12 — same vertices."""
    mesh = box(h=6, n=4)
    _, target = mid_target(mesh, mode)
    lab = signed_influence(mesh, target.seeds, radius, metric, DEFAULT_CURVE)
    app = compute_influence(mesh, target.seeds, radius, metric=metric, curve="smooth")
    assert set(lab) == set(app)
    assert max((abs(lab[v] - app[v]) for v in app), default=0.0) <= 1e-12


@pytest.mark.parametrize("metric", sorted(METRICS))
def test_signed_curve_gives_negative_weights_and_no_zeros(metric):
    mesh = box(h=10, n=5)
    _, target = mid_target(mesh)
    hat = SignedCurve.from_preset(PRESET_HAT)
    weights = signed_influence(mesh, target.seeds, 1.5, metric, hat)
    assert any(w < 0.0 for w in weights.values())
    assert all(w != 0.0 for w in weights.values())
    assert all(-1.0 <= w <= 1.0 for w in weights.values())
    assert all(weights[s] == 1.0 for s in target.seeds)
    # `w == 0` vertices are absent: a curve that is 0 at x = 0.4 drops exactly those vertices
    distances = METRICS[metric](mesh, set(target.seeds), 1.5)
    zero_at = SignedCurve.from_knots((0.5, 0.0, 0.0, 0.0))
    weights0 = signed_influence(mesh, target.seeds, 1.5, metric, zero_at)
    for vid, d in distances.items():
        if vid in target.seeds:
            continue
        expected = zero_at(d / 1.5)
        assert (vid in weights0) == (expected != 0.0)


def test_negative_weights_are_not_dropped_like_in_compute_influence():
    """The one rule that differs: `compute_influence` keeps `w > 0` only."""
    mesh = box(h=10, n=5)
    _, target = mid_target(mesh)
    flipped = signed_influence(mesh, target.seeds, 1.5, "geodesic", lambda x: -smooth_of_x(x))
    app = compute_influence(mesh, target.seeds, 1.5, metric="geodesic", curve="smooth")
    assert set(flipped) == set(app)
    for vid, w in app.items():
        assert flipped[vid] == (1.0 if vid in target.seeds else -w)


def test_stale_seeds_and_bad_arguments():
    mesh = box()
    assert signed_influence(mesh, [], 1.0, "geodesic", smooth_of_x) == {}
    with pytest.raises(ValueError):
        signed_influence(mesh, mesh.all_vertex_ids()[:1], -1.0, "geodesic", smooth_of_x)
    with pytest.raises(ValueError):
        signed_influence(mesh, mesh.all_vertex_ids()[:1], 1.0, "manhattan", smooth_of_x)


def test_distance_cache_reuses_metric_runs_per_token():
    mesh = box(h=6, n=4)
    _, target = mid_target(mesh)
    cache = DistanceCache()
    hat = SignedCurve.from_preset(PRESET_HAT)
    a = cache.influence(mesh, target.seeds, 1.0, "geodesic", smooth_of_x, token=1)
    b = cache.influence(mesh, target.seeds, 1.0, "geodesic", hat, token=1)
    assert (cache.misses, cache.hits) == (1, 1)
    assert a == signed_influence(mesh, target.seeds, 1.0, "geodesic", smooth_of_x)
    assert b == signed_influence(mesh, target.seeds, 1.0, "geodesic", hat)
    cache.influence(mesh, target.seeds, 1.0, "geodesic", hat, token=2)
    assert cache.misses == 2


def test_bands_split_by_sign():
    assert negative_band_index(-1.0) == 0 and negative_band_index(-0.9) == band_index(0.9)
    assert negative_band_index(0.5) is None and negative_band_index(0.0) is None
    weights = {1: 1.0, 2: 0.9, 3: 0.1, 4: -0.1, 5: -1.0, 6: -0.6}
    bands = SignedBands.from_weights(weights)
    assert bands.positive_count == 2 and bands.negative_count == 3
    assert bands.positive[band_index(0.9)] == (2,)
    assert bands.negative[0] == (5,) and bands.negative[BAND_COUNT - 1] == (4,)
    assert 1 not in {v for b in bands.positive + bands.negative for v in b}  # seeds: hover points
