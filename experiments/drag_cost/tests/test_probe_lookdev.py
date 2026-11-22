"""The LookDev LD-0 probe (AD-038 draft): arguments, the pure helpers (SH9, cube directions, the key's matrix, the
stand-in's sources) and the import boundary - headless, no window."""

from __future__ import annotations

import json
import math
import subprocess
import sys
import textwrap

import pytest

from drag_cost import probe_lookdev as probe
from drag_cost._paths import EXPERIMENTS_DIR


def test_defaults_and_limits():
    args = probe.parse_args([])
    assert args.size is None and args.sizes == [(1024, 768), (1920, 1080)]
    assert (args.draws, args.surfaces, args.views, args.skip) == (probe.DEFAULT_DRAWS, list(probe.SURFACES),
                                                                  list(probe.VIEWS), set())
    args = probe.parse_args(["--size", "640", "480", "--skip", "cube,depth", "--surfaces", "cage"])
    assert args.size == [640, 480] and args.skip == {"cube", "depth"} and args.surfaces == ["cage"]
    for argv in (["--sizes", "10x10"], ["--surfaces", "subd2"], ["--views", "top"], ["--skip", "eyes"],
                 ["--draws", "0"], ["--size", "32", "32"]):
        with pytest.raises(SystemExit):
            probe.parse_args(argv)


def test_summary_and_row_format():
    assert probe.summary([3.0, 1.0, 2.0]) == (2.0, 1.0, 3.0)
    line = probe.format_row("ld frame", [1.0, 2.0, 3.0], [5.0, 6.0, 7.0], 0.5)
    assert line.split() == ["ld", "frame", "2.00", "1.00", "3.00", "+1.50", "6.00"]
    assert probe.format_row("worklight", [1.0], [2.0], None).split() == ["worklight", "1.00", "1.00", "1.00", "2.00"]


def test_sh9_of_a_constant_sky_gives_that_radiance_back():
    """E(n) / pi of a uniform radiance L is L for every normal: the projection, the cosine bands and the division."""
    np = pytest.importorskip("numpy")
    coeffs = probe.sh9_project(lambda d: np.tile([0.2, 0.5, 1.0], (len(d), 1)), count=2048)
    normals = probe.fibonacci_directions(64)
    values = probe.sh9_basis(normals) @ coeffs
    assert np.allclose(values, [0.2, 0.5, 1.0], atol=1e-3)


def test_sh9_of_a_light_from_above_is_brightest_above():
    np = pytest.importorskip("numpy")
    coeffs = probe.sh9_project(lambda d: np.repeat(np.maximum(d[:, 1:2], 0.0), 3, axis=1))
    up, side, down = probe.sh9_basis(np.array([[0.0, 1.0, 0.0], [1.0, 0.0, 0.0], [0.0, -1.0, 0.0]])) @ coeffs
    assert up[0] > side[0] > down[0] >= -0.02


def test_cube_face_centres_are_the_axes():
    axes = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
    assert [probe.cube_face_direction(f, 0.0, 0.0) for f in range(6)] == [tuple(float(c) for c in a) for a in axes]
    # GL's table: +X at s = 1 (u = 1) looks toward -Z, +Z at u = 1 toward +X
    assert probe.cube_face_direction(0, 1.0, 0.0)[2] == -1.0 and probe.cube_face_direction(4, 1.0, 0.0)[0] == 1.0


def test_key_light_matrix_puts_the_centre_in_the_middle_of_the_box():
    np = pytest.importorskip("numpy")
    m = np.asarray(probe.look_at_ortho((0.0, 0.0, 1.0), (1.0, 2.0, 3.0), 2.0)).reshape(4, 4).T
    centre = m @ np.array([1.0, 2.0, 3.0, 1.0])
    nearer = m @ np.array([1.0, 2.0, 4.0, 1.0])  # toward the light
    edge = m @ np.array([3.0, 2.0, 3.0, 1.0])
    assert np.allclose(centre[:2], 0.0) and -1.0 < centre[2] < 1.0
    assert nearer[2] < centre[2]
    assert math.isclose(abs(edge[0]), 1.0, abs_tol=1e-9)


def test_stand_in_sources_use_the_stores_vertex_and_geometry_stage():
    from viewport.gl_render_store import TEXTURED_GEOMETRY_SRC, TEXTURED_VERTEX_SRC

    locations = {"position": 0, "normal": 1}
    plain = probe.skin_sources(locations, False, False, False)
    assert [kind for _src, kind in plain] == ["vertex", "geometry", "fragment"]
    assert plain[0][0] == TEXTURED_VERTEX_SRC.format(**locations) and plain[1][0] == TEXTURED_GEOMETRY_SRC
    fragment = plain[2][0]
    assert fragment.startswith("#version 330 core\n") and "#define" not in fragment.split("const float PI")[0]
    full = probe.skin_sources(locations, True, True, True, nonce="abc")[2][0]
    for define in ("ALBEDO_MAP", "ENV_SPEC", "SHADOW"):
        assert f"#define {define} 1\n" in full
    assert full.endswith("// abc\n") and "vec3 studio_radiance(vec3 d, float roughness)" in full
    assert "{{" not in full and "{{" not in probe.cube_sources()[1][0]  # every template formatted


def test_studio_values_pad_to_the_shader_arrays():
    values = probe.studio_values()
    assert 1 <= values["u_studio_n"] <= 4
    for name in ("u_studio_centre", "u_studio_right", "u_studio_up", "u_studio_half", "u_studio_radiance"):
        assert len(values[name]) == 4


def test_no_pyglet_main_or_foreign_experiment_imports():
    script = textwrap.dedent(
        f"""
        import json, sys
        sys.path.insert(0, {str(EXPERIMENTS_DIR)!r})
        from drag_cost._paths import ensure_paths
        ensure_paths()
        import drag_cost.probe_lookdev
        print(json.dumps(sorted(sys.modules)))
        """
    )
    out = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True)
    loaded = set(json.loads(out.stdout))
    assert not {m for m in loaded if m == "pyglet" or m.startswith("pyglet.")}
    assert "main" not in loaded
    assert not {m for m in loaded if m.split(".")[0] in {"playground", "lookdev_eye_lab", "lookdev_gpu_probe"}}


def test_every_glsl_source_is_ascii():
    """GLSL 3.30's character set is ASCII; a stray character in a comment can fail a strict compiler (NVIDIA Cg)."""
    sources = [s for s, _k in probe.skin_sources({"position": 0, "normal": 1}, True, True, True)]
    sources += [s for s, _k in probe.cube_sources()]
    sources += [probe.FULLSCREEN_VS, probe.BACKGROUND_FS, probe.DEPTH_VS.format(position=0), probe.DEPTH_FS,
                probe.CUBE_SAMPLE_FS]
    for source in sources:
        assert source.isascii()


# -- P3-0 (`--p3`, AD-039) ---------------------------------------------------------------------------------------------


def test_p3_flag_defaults_off():
    assert probe.parse_args([]).p3 is False
    assert probe.parse_args(["--p3", "--size", "1024", "768"]).p3 is True


def test_p3_rows_are_unique_and_fit_the_table():
    rows = probe.p3_rows()
    names = [name for name, _options in rows]
    assert names[0] == "ld frame" and len(set(names)) == len(names)
    assert all(len(name) <= 13 for name in names)  # `format_row`'s column
    for name, options in rows:
        assert not options.get("thickness") or options.get("shadow")  # the thickness reads the shadow map
        if options.get("shadow"):
            assert options["shadow_size"] in {s for s, _g in probe.P3_SHADOW}
    assert probe.P3_SETTING in probe.P3_SHADOW


def test_p3_variants_add_their_defines_and_only_those():
    locations = {"position": 0, "normal": 1}
    plain = probe.skin_sources(locations, True, True, False)[2][0]
    for define in ("SHADOW", "THICKNESS", "DUAL_LOBE", "DUAL_LOBE_ENV", "CUBE_ENV", "SHADOW_GRID"):
        assert f"#define {define} " not in plain.split("const float PI")[0]
    lod = probe.skin_sources(locations, True, True, True)[2][0]
    assert "#define SHADOW_GRID" not in lod.split("const float PI")[0]  # LD-0's `ld shadow`: the 4x4 default
    full = probe.skin_sources(locations, True, True, True, shadow_grid=3, thickness=True, dual=2, cube_env=True)[2][0]
    head = full.split("const float PI")[0]
    for define in ("SHADOW", "THICKNESS", "DUAL_LOBE", "DUAL_LOBE_ENV", "CUBE_ENV"):
        assert f"#define {define} 1\n" in head
    assert "#define SHADOW_GRID 3\n" in head and "{{" not in full and full.isascii()
    with pytest.raises(ValueError):
        probe.skin_sources(locations, True, True, False, thickness=True)
    with pytest.raises(ValueError):
        probe.skin_sources(locations, True, True, True, dual=3)
