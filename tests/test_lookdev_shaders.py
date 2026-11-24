"""LookDev GLSL text (AD-038 §5.2, E5b): the skin program's BRDF and colour encode are the eye's, character for
character, and the shared library defines none of them (C7). Headless."""

from __future__ import annotations

import re

import tests._bootstrap  # noqa: F401

from viewport import eye_shaders as es
from viewport import lookdev_shaders as ls


def _defined_functions(src: str) -> set[str]:
    return set(re.findall(r"^\w+ (\w+)\([^;{]*\) \{", src, flags=re.M))


def test_brdf_functions_are_substrings_of_the_eye_library():
    for name in ls.BRDF_FUNCTIONS:
        definition = ls.function_src(name, ls.LD_BRDF_SRC)
        assert definition in es.EYE_LIB_SRC, name
        assert definition.startswith(("vec3 ", "float ")) and definition.endswith("\n}\n")
    for name in ls.BRDF_CONSTANTS:
        assert ls.constant_src(name, ls.LD_BRDF_SRC) == ls.constant_src(name, es.EYE_LIB_SRC)
    assert _defined_functions(ls.LD_BRDF_SRC) == set(ls.BRDF_FUNCTIONS)


def test_the_common_library_redefines_nothing_of_the_eye():
    common = _defined_functions(ls.LD_COMMON_SRC)
    assert common == {"srgb_decode", "sh9", "ld_studio", "ld_env_diffuse", "ld_env_specular", "ld_wrap", "ld_diffuse",
                      "ld_lobe", "ld_specular", "ld_tone", "lookdev_output"}
    assert not common & _defined_functions(es.EYE_LIB_SRC)
    for name in ls.BRDF_CONSTANTS:
        assert f"const float {name} " not in ls.LD_COMMON_SRC
    uniforms = re.findall(r"^uniform \w+ (\w+)", ls.LD_COMMON_SRC, flags=re.M)
    assert uniforms and all(u.startswith("u_ld_") for u in uniforms)  # disjoint from the Worklight names


def test_skin_sources_are_the_worklight_vertex_and_geometry_stages():
    from viewport.gl_render_store import TEXTURED_GEOMETRY_SRC, TEXTURED_VERTEX_SRC

    locations = {"position": 0, "normal": 1}
    for albedo_map in (False, True):
        for env_spec in (False, True):
            (vs, k0), (gs, k1), (fs, k2) = ls.skin_sources(locations, albedo_map, env_spec)
            assert (k0, k1, k2) == ("vertex", "geometry", "fragment")
            assert vs == TEXTURED_VERTEX_SRC.format(**locations) and gs == TEXTURED_GEOMETRY_SRC
            assert fs.startswith("#version 330 core\n")
            assert ("#define ALBEDO_MAP 1\n" in fs) == albedo_map and ("#define ENV_SPEC 1\n" in fs) == env_spec
            assert fs.count("vec3 srgb_encode(") == 1 and fs.count("vec3 lookdev_output(") == 1


#: AD-039 §2.3 point 3 (the C6 / I-0 pattern of AD-038): the 4 M1 skin variants (`skin_sources` for `ALBEDO_MAP` x
#: `ENV_SPEC`, attribute locations 0 / 1; vertex, geometry and fragment source each, 12 sources in that order, kind and
#: text hashed character for character). Taken from the code before S1 changed `lookdev_shaders.py` (`9e7dbea`). With
#: every P3 effect off, `skin_sources` must give exactly these sources.
PINNED_SKIN_SOURCES_SHA256 = "a71bd9740763a4c20d5a4703153acb317a477ceacb4f43b7439eed66007f4c38"


def skin_sources_digest(**effects) -> tuple[int, str]:
    import hashlib
    import itertools

    digest, count = hashlib.sha256(), 0
    for albedo_map, env_spec in itertools.product((False, True), (False, True)):
        for src, kind in ls.skin_sources({"position": 0, "normal": 1}, albedo_map, env_spec, **effects):
            digest.update(kind.encode() + b"\0" + src.encode() + b"\0")
            count += 1
    return count, digest.hexdigest()


def test_the_m1_skin_sources_are_pinned():
    """AD-039 §2.3 / §14: every P3 effect off = the M1 skin program, character for character."""
    assert skin_sources_digest() == (12, PINNED_SKIN_SOURCES_SHA256)


#: AD-039 §6 / §18 (S3): the 4 S1 skin variants (`shadow=True`), taken from the code before S3 changed
#: `lookdev_shaders.py` (`f8c771f`). With the dual lobe off, the shadow's programs stay exactly S1's.
PINNED_S1_SKIN_SOURCES_SHA256 = "54cc6cc64403e4ad5f5ef3981afb4f251e34db0ffdbaac92d66b7a7ba1d12313"


def test_the_dual_lobe_off_keeps_m1_and_s1_sources():
    """AD-039 §6: `dual_lobe=False` = the M1 sources and, with the shadow, S1's, character for character."""
    assert skin_sources_digest(dual_lobe=False) == (12, PINNED_SKIN_SOURCES_SHA256)
    assert skin_sources_digest(shadow=True) == (12, PINNED_S1_SKIN_SOURCES_SHA256)
    assert skin_sources_digest(shadow=True, dual_lobe=False) == (12, PINNED_S1_SKIN_SOURCES_SHA256)
    assert skin_sources_digest(dual_lobe=True)[1] != PINNED_SKIN_SOURCES_SHA256


def test_the_dual_lobe_variant_calls_the_dual_twins_for_the_lights_and_the_shadowed_key():
    """AD-039 §6: `DUAL_LOBE` defined once, its library appended once after the common library (it uses `ld_lobe`),
    every light highlight - the `SHADOW` block's key term included - through `ld_direct_dual`; the studio's reflection
    keeps one lobe (P3-0 run 2) and `LD_COMMON_SRC` (the eye's) is unchanged."""
    locations = {"position": 0, "normal": 1}
    for shadow in (False, True):
        fs = ls.skin_sources(locations, True, True, shadow, True)[2][0]
        assert fs.count("#define DUAL_LOBE 1\n") == 1 and fs.count(ls.LD_DUAL_LOBE_SRC) == 1
        assert fs.index(ls.LD_COMMON_SRC) < fs.index(ls.LD_DUAL_LOBE_SRC)
        assert ("#define SHADOW 1\n" in fs) == shadow
        body = fs[fs.index("void main()"):]
        assert "ld_specular_dual(n, v, rough, u_f0)" in body
        assert "ld_env_specular(reflect(-v, n), rough)" in body  # one lobe on the studio
        assert ("ld_direct_dual(n, v, u_ld_light_dir[0], rough, u_ld_light_size[0], u_f0)" in body) == shadow
    assert "ld_specular_dual" not in ls.LD_COMMON_SRC and "DUAL" not in ls.LD_COMMON_SRC
    assert ls.SKIN_EFFECTS[:2] == ("SHADOW", "DUAL_LOBE")
    # without DUAL_LOBE no call to the dual twins is left
    for shadow in (False, True):
        fs = ls.skin_sources(locations, True, True, shadow, False)[2][0]
        assert "ld_specular_dual" not in fs and "ld_direct_dual" not in fs and "DUAL_LOBE" not in fs


#: AD-039 §7 / §19 (S4): the 4 S3 skin variants with the shadow (`shadow=True, dual_lobe=True`), taken from the code before
#: S4 changed `lookdev_shaders.py` (`eadb291`). With the thickness off, the frame's programs stay exactly S3's.
PINNED_S3_SKIN_SOURCES_SHA256 = "23271b8cb690c9c3eb992ff57b74d0746c54ef6dd175856320e3de7f12105188"


def test_the_thickness_off_keeps_the_m1_s1_and_s3_sources():
    """AD-039 §7: `thickness=False` = the sources before, character for character."""
    assert skin_sources_digest(thickness=False) == (12, PINNED_SKIN_SOURCES_SHA256)
    assert skin_sources_digest(shadow=True, thickness=False) == (12, PINNED_S1_SKIN_SOURCES_SHA256)
    assert skin_sources_digest(shadow=True, dual_lobe=True) == (12, PINNED_S3_SKIN_SOURCES_SHA256)
    assert skin_sources_digest(shadow=True, dual_lobe=True, thickness=False) == (12, PINNED_S3_SKIN_SOURCES_SHA256)


def test_the_thickness_variant_replaces_the_rim_proxy_and_needs_the_shadow():
    """AD-039 §7: `THICKNESS` defined once, its library once after `LD_SHADOW_SRC` (it uses `ld_shadow_coord` and the
    map's scale); the backscatter's view-rim proxy replaced by the transmission; refused without the shadow."""
    import pytest

    locations = {"position": 0, "normal": 1}
    for dual in (False, True):
        fs = ls.skin_sources(locations, True, True, True, dual, True)[2][0]
        assert fs.count("#define THICKNESS 1\n") == 1 and fs.count(ls.LD_THICKNESS_SRC) == 1
        assert fs.index(ls.LD_SHADOW_SRC) < fs.index(ls.LD_THICKNESS_SRC)
        body = fs[fs.index("void main()"):]
        assert "ld_key_transmission(v_world_pos, n, u_ld_light_dir[0])" in body
        assert "(1.0 - nv) * (1.0 - nv) * (1.0 - nv)" in body  # the #else part (resolved by the preprocessor)
    assert ls.SKIN_EFFECTS == ("SHADOW", "DUAL_LOBE", "THICKNESS")
    assert ls.SHADOW_RAW_UNIT == 7 and ls.SHADOW_UNIT == 6
    fs = ls.skin_sources(locations, True, True, True, True, False)[2][0]
    assert "THICKNESS" not in fs and "ld_key_transmission" not in fs and "u_ld_shadow_depth" not in fs
    with pytest.raises(ValueError):
        ls.skin_sources(locations, True, True, False, True, True)


#: AD-039 §10 / §20 (S7): the 4 S4 skin variants with every effect before S7 on (`shadow`, `dual_lobe`, `thickness`),
#: taken from the code before S7 changed `lookdev_shaders.py` (`50c69cd`). With no map, the frame's programs stay
#: exactly S4's.
PINNED_S4_SKIN_SOURCES_SHA256 = "934cf4517e997b6399a9f298bf8db83dfa680fcdbf85fb70dc7cdc4d203bb093"


def test_no_map_keeps_the_m1_to_s4_sources():
    """AD-039 §10: every map off = the sources before S7, character for character."""
    off = dict(roughness_map=False, normal_map=False, translucency_map=False)
    assert skin_sources_digest(**off) == (12, PINNED_SKIN_SOURCES_SHA256)
    assert skin_sources_digest(shadow=True, **off) == (12, PINNED_S1_SKIN_SOURCES_SHA256)
    assert skin_sources_digest(shadow=True, dual_lobe=True, **off) == (12, PINNED_S3_SKIN_SOURCES_SHA256)
    assert skin_sources_digest(shadow=True, dual_lobe=True, thickness=True) == (12, PINNED_S4_SKIN_SOURCES_SHA256)
    assert skin_sources_digest(shadow=True, dual_lobe=True, thickness=True, **off) == (12,
                                                                                      PINNED_S4_SKIN_SOURCES_SHA256)


def test_each_map_has_its_define_and_only_its_text():
    """AD-039 §10: one define per map, `LD_MAP_UV` with any of them, the normal map's library only with it; the
    triangle UVs declared once with or without the albedo map; with the normal map the key map's lookups take the
    geometric normal `n_geo`."""
    import itertools

    locations = {"position": 0, "normal": 1}
    assert ls.SKIN_MAPS == ("ROUGHNESS_MAP", "NORMAL_MAP", "TRANSLUCENCY_MAP")
    assert ls.MAP_UNITS == {"roughness": 9, "normal": 10, "translucency": 11}
    assert set(ls.MAP_UNITS.values()).isdisjoint({0, ls.UV_UNIT, ls.ALBEDO_UNIT, 5, ls.SHADOW_UNIT,
                                                  ls.SHADOW_RAW_UNIT, 8, 12})
    for albedo, rough, normal, trans in itertools.product((False, True), repeat=4):
        if not (rough or normal or trans):
            continue
        fs = ls.skin_sources(locations, albedo, True, True, True, True, rough, normal, trans)[2][0]
        assert fs.count("#define LD_MAP_UV 1\n") == 1
        for name, on in (("ROUGHNESS_MAP", rough), ("NORMAL_MAP", normal), ("TRANSLUCENCY_MAP", trans)):
            assert (f"#define {name} 1\n" in fs) == on
            assert (f"#ifdef {name}" in fs) == on  # an off map's blocks are resolved away
        assert fs.count(ls.LD_NORMAL_MAP_SRC) == (1 if normal else 0)
        assert fs.count("uniform samplerBuffer u_triangle_uvs;") == 2  # once per #ifdef / #ifndef ALBEDO_MAP
        body = fs[fs.index("void main()"):]
        assert ("ld_key_visibility(v_world_pos, n_geo, u_ld_light_dir[0])" in body) == normal
        assert ("ld_key_transmission(v_world_pos, n_geo, u_ld_light_dir[0])" in body) == normal
        assert ("texture(u_roughness_map, map_uv)" in body) == rough
        assert ("texture(u_translucency_map, map_uv)" in body) == trans
    assert "NORMAL_MAP" not in ls.LD_COMMON_SRC and "map_uv" not in ls.LD_COMMON_SRC
