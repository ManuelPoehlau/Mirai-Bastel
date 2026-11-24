"""`pcss_glsl` patches the production skin fragment (2026-11-24): every anchor is found in every effect combination with
the shadow, both lookups go through `ldx_key_shadow`, nothing changes without the shadow, the eye is not touched, and
`install` / `uninstall` restore production. Headless (string level)."""

import itertools

import pytest

import area_glsl as ag
import pcss_glsl as pg

LOCATIONS = {"position": 0, "normal": 1}


def fragments():
    from viewport.lookdev_shaders import skin_sources

    for shadow, dual, thick, nmap, area in itertools.product((False, True), repeat=5):
        if thick and not shadow:
            continue
        src = skin_sources(LOCATIONS, True, True, shadow=shadow, dual_lobe=dual, thickness=thick, normal_map=nmap,
                           cube_env=True, area_diffuse=area)
        yield (shadow, dual, thick, nmap, area), [s for s, k in src if k == "fragment"][0]


VARIANTS = [pg.Pcss(b, p, kind, full, search_at=at, early=early)
            for b, p in ((9, 9), (16, 16), (16, 32)) for kind in ("disc", "grid") if kind == "disc" or b in (9, 16)
            for full in (True, False) for at in ("shared", "each") for early in (True, False)
            if kind != "grid" or p in (9, 16)]


K = dict(search_test="cone", cone=2.0, pcf_test="level", level=0.5, band_lift=0.15, fade=4.0)
VARIANTS += [pg.Pcss(16, 16, "disc", **K), pg.Pcss(9, 9, "grid", full=False, **K),
             pg.Pcss(16, 16, "disc", search_at="each", early=False, **K),
             pg.Pcss(16, 16, plane="normal", back_flat=True, search_test="both", pcf_test="min")]


@pytest.mark.parametrize("p", VARIANTS[::3] + VARIANTS[-4:], ids=lambda p: p.label())
def test_every_variant_patches_every_effect_combination(p):
    for key, fragment in fragments():
        out = pg.patch_shadow(fragment, p)
        if not key[0]:
            assert out == fragment
            continue
        assert out.count("ldx_key_shadow(v_world_pos,") == (2 if key[3] else 1)
        assert "ld_key_visibility(v_world_pos" not in out and "ld_key_visibility_lifted(v_world_pos" not in out
        assert out.count("uniform sampler2D u_ld_shadow_depth;") == 1  # declared once, before its first use
        assert out.index("uniform sampler2D u_ld_shadow_depth;") < out.index("u_ld_shadow_depth, (sp.xy")


def test_patterns():
    for kind, n in (("grid", 9), ("grid", 16), ("disc", 16), ("disc", 32)):
        pts = pg.pattern(kind, n)
        assert len(pts) == n and len(set(pts)) == n
        assert max(max(abs(x), abs(y)) for x, y in pts) <= 1.0 + 1e-12
    with pytest.raises(ValueError):
        pg.pattern("grid", 12)


def test_install_restores_production_and_leaves_the_eye():
    from viewport import lookdev_optics, lookdev_pass, lookdev_shaders

    before = (lookdev_pass.skin_sources, lookdev_optics.shadow_resolution, lookdev_pass.LookdevPass.draw,
              lookdev_shaders.LD_SHADOW_SRC, lookdev_shaders.LD_COMMON_SRC)
    pg.install(ag.Variant("A"), pg.Pcss())
    try:
        assert lookdev_optics.shadow_resolution(1.0) == lookdev_optics.SHADOW_SIZE
        assert lookdev_shaders.LD_SHADOW_SRC == before[3]  # the eye appends this string: unchanged
        frag = [s for s, k in lookdev_pass.skin_sources(LOCATIONS, False, True, shadow=True) if k == "fragment"][0]
        assert "ldx_key_shadow" in frag
        pg.install(ag.Variant("A"), None)  # production's lookup, the effective resolution
        assert lookdev_optics.shadow_resolution(1.0) == before[1](1.0) < lookdev_optics.SHADOW_SIZE
    finally:
        pg.uninstall()
    assert (lookdev_pass.skin_sources, lookdev_optics.shadow_resolution, lookdev_pass.LookdevPass.draw) == before[:3]
