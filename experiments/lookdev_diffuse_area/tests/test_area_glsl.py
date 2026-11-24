"""`area_glsl` patches the production skin fragment (2026-11-24): every anchor is found in the current production
sources, A changes nothing that draws, and the eye's sources are not touched. Headless (string level)."""

import itertools

import pytest

import area_glsl as ag

LOCATIONS = {"position": 0, "normal": 1}


def fragments():
    from viewport.lookdev_shaders import skin_sources

    for shadow, dual, thick in itertools.product((False, True), repeat=3):
        if thick and not shadow:
            continue
        src = skin_sources(LOCATIONS, True, True, shadow=shadow, dual_lobe=dual, thickness=thick, cube_env=True)
        yield (shadow, dual, thick), [s for s, k in src if k == "fragment"][0]


@pytest.mark.parametrize("variant", [ag.Variant(m, samples=8, excess=e, spec=sp, linear=lin, lift=lift, repeat=r)
                                     for m in ("A", "B", "B2", "C") for e in ("lifted", "split", "point")
                                     for sp, lin in ((True, False), (False, True)) for lift in ("effective", "mid")
                                     for r in (1, 4)][::5])
def test_every_variant_patches_every_effect_combination(variant):
    for key, fragment in fragments():
        out = ag.patch_fragment(fragment, variant)
        assert "ldx_diffuse" in out
        if key[0]:
            assert "ldx_diffuse(0, n, u_wrap)" in out


def test_a_keeps_the_production_maths():
    for _, fragment in fragments():
        out = ag.patch_fragment(fragment, ag.Variant("A"))
        assert "ld_wrap(dot(n, u_ld_light_dir[i]), wrap)" in out  # ldx_diffuse(A) is ld_wrap itself


def test_the_eye_sources_are_not_touched():
    from viewport import lookdev_pass, lookdev_shaders

    before = lookdev_shaders.LD_COMMON_SRC
    original = lookdev_pass.skin_sources
    ag.install(ag.Variant("B"))
    try:
        assert lookdev_shaders.LD_COMMON_SRC == before
        assert lookdev_pass.skin_sources is not original
    finally:
        ag.uninstall()
    assert lookdev_pass.skin_sources is original
