"""Specular / gloss finish of the viewport material (2026-10-23, `viewport.material`), GL-free.

- the glossiness → exponent mapping is the documented one (4 · 64^g, clamped);
- the packet layout and its reading (6 floats = full, 3 = colour with the default finish);
- the Python reference (`light_rig.shade` with `view_dir`): highlight only on the lit side, neutral,
  strength sets the peak, glossiness the size, fill specular separate and off by default;
- the settings path: `DisplayState.set_surface_finish` → `Application._apply_display` →
  `Viewport.set_surface_finish` is a material update only — no geometry, topology or face-data work.

The GL side (shader = reference, image changes, draw state only) is `test_gl_shading.py`.
"""

from __future__ import annotations

import math

import tests._bootstrap  # noqa: F401

import pytest

from mirai.application import Application
from viewport.gl_render_store import DEFAULT_BASE_COLOR
from viewport.light_rig import PRESET_HEUTE, PRESET_RAITT, PRESETS, resolve, shade
from viewport.material import (
    DEFAULT_FINISH,
    EXPONENT_MAX,
    EXPONENT_MIN,
    MATTE_FINISH,
    Material,
    SurfaceFinish,
    gloss_exponent,
    read_packet,
    specular_term,
)


def _close(a, b, tol=1e-12):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


# -- mapping and packet -----------------------------------------------------------------------


def test_gloss_exponent_is_logarithmic_between_the_documented_ends():
    assert gloss_exponent(0.0) == pytest.approx(EXPONENT_MIN)
    assert gloss_exponent(1.0) == pytest.approx(EXPONENT_MAX)
    assert (EXPONENT_MIN, EXPONENT_MAX) == (4.0, 256.0)
    assert gloss_exponent(0.5) == pytest.approx(32.0)
    # equal steps are equal ratios
    assert gloss_exponent(0.75) / gloss_exponent(0.5) == pytest.approx(gloss_exponent(0.5) / gloss_exponent(0.25))
    assert gloss_exponent(-1.0) == pytest.approx(EXPONENT_MIN)
    assert gloss_exponent(2.0) == pytest.approx(EXPONENT_MAX)


def test_defaults_are_conservative_and_fill_specular_is_off():
    assert DEFAULT_FINISH.specular == 0.25
    assert DEFAULT_FINISH.glossiness == 0.5
    assert DEFAULT_FINISH.fill_specular == 0.0
    assert DEFAULT_FINISH.exponent == pytest.approx(32.0)
    assert MATTE_FINISH.specular == 0.0 and MATTE_FINISH.fill_specular == 0.0


def test_finish_values_are_clamped():
    f = SurfaceFinish(specular=3.0, glossiness=-0.5, fill_specular=-1.0)
    assert (f.specular, f.glossiness, f.fill_specular) == (1.0, 0.0, 0.0)


def test_packet_layout_and_reading():
    m = Material((0.1, 0.2, 0.3), SurfaceFinish(0.4, 0.6, 0.1))
    assert m.uniform_packet() == pytest.approx([0.1, 0.2, 0.3, 0.4, 0.6, 0.1])
    color, finish = read_packet(m.uniform_packet(), DEFAULT_BASE_COLOR)
    assert color == pytest.approx((0.1, 0.2, 0.3))
    assert finish == SurfaceFinish(0.4, 0.6, 0.1)
    # a colour-only packet (a host material) gets the default finish
    assert read_packet([0.5, 0.5, 0.5], DEFAULT_BASE_COLOR) == ((0.5, 0.5, 0.5), DEFAULT_FINISH)
    assert read_packet([], DEFAULT_BASE_COLOR) == (DEFAULT_BASE_COLOR, DEFAULT_FINISH)


# -- reference formula ----------------------------------------------------------------------------


def test_without_view_dir_shade_is_the_diffuse_term_alone():
    u = resolve(PRESETS[PRESET_HEUTE])
    n = (0.2, 0.3, 0.9)
    assert shade(n, u, DEFAULT_BASE_COLOR) == shade(n, u, DEFAULT_BASE_COLOR, view_dir=(0, 0, 1), finish=MATTE_FINISH)


def test_highlight_is_neutral_and_peaks_at_strength_times_key_luminance():
    u = resolve(PRESETS[PRESET_HEUTE])
    key = u["u_key_dir"]
    # normal = view = light: N·H = 1, so the highlight is exactly specular · luminance(key)
    finish = SurfaceFinish(specular=0.5, glossiness=0.9)
    lit = shade(key, u, DEFAULT_BASE_COLOR, view_dir=key, finish=finish)
    matte = shade(key, u, DEFAULT_BASE_COLOR, view_dir=key, finish=MATTE_FINISH)
    added = [a - b for a, b in zip(lit, matte)]
    assert added == pytest.approx([0.5 * 0.65] * 3)  # "Heute" key: 0.65, neutral white, equal channels


def test_no_highlight_on_the_side_facing_away_from_the_key():
    u = resolve(PRESETS[PRESET_HEUTE])
    key = u["u_key_dir"]
    away = (-key[0], -key[1], -key[2])
    assert specular_term(away, key, away, 32.0) == 0.0
    finish = SurfaceFinish(specular=1.0, glossiness=0.0)
    assert shade(away, u, DEFAULT_BASE_COLOR, view_dir=away, finish=finish) == shade(
        away, u, DEFAULT_BASE_COLOR, view_dir=away, finish=MATTE_FINISH
    )


def test_glossiness_concentrates_the_highlight_without_changing_its_peak():
    key = (0.0, 0.0, 1.0)
    view = (0.0, 0.0, 1.0)
    off_peak = (math.sin(0.3), 0.0, math.cos(0.3))
    broad, tight = gloss_exponent(0.2), gloss_exponent(0.8)
    assert specular_term(key, key, view, broad) == pytest.approx(1.0)
    assert specular_term(key, key, view, tight) == pytest.approx(1.0)
    assert specular_term(off_peak, key, view, tight) < specular_term(off_peak, key, view, broad)


def test_fill_specular_is_separate_and_off_by_default():
    camera_u = resolve(PRESETS[PRESET_RAITT].with_(space="world"))
    fill = camera_u["u_fill_dir"]
    # a normal facing the fill, seen from the fill side: no key light, only the fill could shine
    default = shade(fill, camera_u, DEFAULT_BASE_COLOR, view_dir=fill)
    matte = shade(fill, camera_u, DEFAULT_BASE_COLOR, view_dir=fill, finish=MATTE_FINISH)
    assert _close(default, matte)
    with_fill = shade(fill, camera_u, DEFAULT_BASE_COLOR, view_dir=fill, finish=DEFAULT_FINISH.with_(fill_specular=0.5))
    assert with_fill[0] > matte[0]


# -- settings path: a material update, never geometry ------------------------------------------


def test_finish_change_is_a_material_update_only():
    app = Application()
    app.init_scene("cube")
    vp = app.viewport
    vp.sync()
    rm = vp.render_mesh
    before = dict(rm.benchmark_counters)
    ids = rm.resource_ids()

    app.display.set_surface_finish(specular=0.6, glossiness=0.8)
    app._apply_display()
    vp.sync()

    after = rm.benchmark_counters
    assert after.get("material_updates", 0) == before.get("material_updates", 0) + 1
    for name in ("structural_rebuilds", "topology_updates", "vertex_updates", "geometry_uploads", "mesh_rebuilds"):
        assert after.get(name, 0) == before.get(name, 0), name
    now = rm.resource_ids()
    for name, rid in ids.items():
        if name != "material_uniforms":
            assert now[name] == rid, name  # no geometry resource was recreated
    packet = rm.store.data("material_uniforms")
    assert packet[3:] == pytest.approx([0.6, 0.8, 0.0])
    assert packet[:3] == pytest.approx(list(DEFAULT_BASE_COLOR))
    # unchanged finish: nothing to do
    assert vp.set_surface_finish(app.display.surface_finish) is False


def test_finish_reaches_object_entries_and_survives_a_colour_change():
    app = Application()
    app.init_scene("cube")
    ref = app.add_reference("cube")
    app.display.set_surface_finish(specular=0.1)
    app._apply_display()
    entry = app.viewport.object_entries[ref.id]
    assert entry.material.finish.specular == pytest.approx(0.1)
    app.viewport.set_edit_base_color((0.9, 0.1, 0.1))
    assert app.viewport.render_mesh.material.finish.specular == pytest.approx(0.1)
