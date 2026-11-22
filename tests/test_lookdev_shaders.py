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
