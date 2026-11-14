"""The procedural studio and its prefiltered chain (headless)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from lookdev_gpu_probe import cube_math as cm
from lookdev_eye_lab import studio_env as se


def test_radiance_is_finite_and_the_softbox_is_where_its_direction_says():
    env = se.DEFAULT_ENV
    d = cm.equirect_directions(128, 64).reshape(-1, 3)
    rad = se.radiance(d, env)
    assert np.all(np.isfinite(rad)) and rad.min() > 0.0
    key = env.key()
    centre = key.frame()[0]
    assert se.radiance(centre[None], env)[0, 0] == pytest.approx(key.radiance[0] + 0.12 + 0.08 * centre[1], rel=0.02)
    assert se.radiance(-centre[None], env)[0, 0] < 1.0


def test_chain_ends_at_2x2_and_maps_roughness_one_onto_it():
    assert se.chain_sizes(128) == [128, 64, 32, 16, 8, 4, 2]
    chain = se.prefilter(se.DEFAULT_ENV, 16, 0)
    assert [lv.shape[1] for lv in chain.levels] == [16, 8, 4, 2]
    assert chain.roughness[0] == 0.0 and chain.roughness[-1] == 1.0
    assert se.chain_bytes(128, 8) == pytest.approx(1.0 * 2 ** 20, rel=0.01)  # audit §5.6: ~1.0 MiB at 128^2


def test_level_0_sits_in_gl_face_order():
    """The brightest level-0 texel lies in the softbox's direction (the face convention is cube_math's)."""
    env = se.DEFAULT_ENV
    level = se.prefilter(env, 32, 0).levels[0]
    face, j, i = np.unravel_index(np.argmax(level[..., 0]), level.shape[:3])
    d = cm.face_st_to_direction(int(face), (i + 0.5) / 32, (j + 0.5) / 32)
    d = d / np.linalg.norm(d)
    assert math.degrees(math.acos(float(d @ env.key().frame()[0]))) < 25.0


def test_corners_are_equalized_on_every_level():
    for level in se.prefilter(se.DEFAULT_ENV, 16, 1).levels:
        assert np.allclose(cm.equalize_corners(level), level)


@pytest.mark.parametrize("mapping", [0, 1])
def test_softbox_footprint_grows_monotonically_with_the_level(mapping):
    env = se.DEFAULT_ENV
    chain = se.prefilter(env, 32, mapping)
    spread = [se.footprint_spread(level, env.key().frame()[0], 0.25) for level in chain.levels]
    assert all(b >= a - 1e-9 for a, b in zip(spread, spread[1:])) and spread[-1] > 3 * spread[0]


def test_prefilter_cache_round_trip(tmp_path):
    first = se.prefilter(se.DEFAULT_ENV, 8, 0, tmp_path)
    again = se.prefilter(se.DEFAULT_ENV, 8, 0, tmp_path)
    assert not first.from_cache and again.from_cache
    assert all(np.array_equal(a, b) for a, b in zip(first.levels, again.levels))


def test_rgbm_round_trip():
    level = se.prefilter(se.DEFAULT_ENV, 8, 0).levels[1]
    decoded = se.rgbm_decode(se.rgbm_encode(level))
    assert np.max(np.abs(decoded - level) / np.maximum(level, 0.05)) < 0.02


def test_ambient_colours_sky_brighter_than_ground():
    sky, ground = se.ambient_colours()
    assert sky[0] > 3 * ground[0] > 0.0
