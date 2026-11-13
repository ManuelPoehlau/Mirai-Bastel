"""The two probes without a GL context (2026-11-13): arguments, import boundaries, the dolly hook. Headless."""

from __future__ import annotations

import ast
import inspect
from types import SimpleNamespace

import pytest

from lookdev_gpu_probe import cube_math, probe_gl_caps

STDLIB = {"__future__", "argparse", "ctypes", "math", "os", "platform", "re", "struct", "subprocess", "sys",
          "tempfile", "time", "traceback", "zlib", "contextlib", "dataclasses", "pathlib", "winreg"}


def imported_roots(module) -> set[str]:
    tree = ast.parse(inspect.getsource(module))
    roots = {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    return roots | {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}


def test_the_capability_probe_is_independent_of_production_code():
    """No `src/` package (core, mirai, viewport, gui, main) and no other lab: the probe owns its context and GL."""
    assert imported_roots(probe_gl_caps) <= STDLIB | {"numpy", "pyglet", "lookdev_gpu_probe"}
    assert imported_roots(cube_math) <= STDLIB | {"numpy"}


def test_capability_probe_defaults():
    args = probe_gl_caps.build_parser().parse_args([])
    assert [probe_gl_caps.parse_size(s) for s in args.sizes] == [(1024, 768), (1920, 1080)]
    assert args.alloc_sizes == [64, 128, 256, 512] and args.cube_size == 128 and args.draws == 40
    assert args.rough_lod == 4.5 and args.fetches == 1 and args.images is None and not args.no_timing
    assert probe_gl_caps.parse_size("640X480") == (640, 480)
    for bad in ("640", "x480", "0x480", "axb"):
        with pytest.raises(SystemExit):
            probe_gl_caps.parse_size(bad)
    with pytest.raises(ValueError):
        probe_gl_caps.main(["--cube-size", "100", "--no-timing"])  # rejected before any window opens


def test_shaders_are_glsl_330_and_keep_unit_0_free():
    for source in (probe_gl_caps.VERTEX_SRC, probe_gl_caps.SAMPLE_FRAGMENT_SRC, probe_gl_caps.TIMING_FRAGMENT_SRC):
        assert source.startswith("#version 330 core\n")
    assert "textureLod(u_cube" in probe_gl_caps.SAMPLE_FRAGMENT_SRC
    assert 0 not in (probe_gl_caps.SAMPLE_UNIT, probe_gl_caps.CUBE_UNIT)
    assert probe_gl_caps.SAMPLE_UNIT != probe_gl_caps.CUBE_UNIT  # two sampler types never share a unit


def test_the_coverage_probe_keeps_the_drag_cost_defaults():
    from drag_cost import probe_shading_gpu as shading
    from lookdev_gpu_probe import probe_worklight_coverage as coverage

    ours = vars(coverage.build_parser().parse_args([]))
    theirs = vars(shading.build_parser().parse_args([]))
    assert {k: ours[k] for k in theirs} == theirs
    assert ours["dolly"][0] == 1.0  # the first run is the probe_shading_gpu view itself
    assert imported_roots(coverage) <= STDLIB | {"drag_cost", "lookdev_gpu_probe", "pyglet"}


def test_the_dolly_hook_targets_what_measure_really_calls():
    """`measure` must import `build_app` from `drag_cost.probe_morph_gl` when it runs (so swapping the module attribute
    takes effect) and keep its signature; otherwise the coverage runs would silently measure the framed view."""
    from drag_cost import probe_shading_gpu as shading

    source = inspect.getsource(shading.measure)
    assert "from drag_cost.probe_morph_gl import build_app" in source
    assert list(inspect.signature(shading.measure).parameters) == ["path", "size", "draws", "flat"]


def test_dolly_scales_the_camera_and_the_hook_is_always_undone(monkeypatch):
    import drag_cost.probe_morph_gl as morph_gl
    from drag_cost import probe_shading_gpu as shading
    from lookdev_gpu_probe import probe_worklight_coverage as coverage

    calls = []
    camera = SimpleNamespace(dolly=lambda f: calls.append(f))
    build = coverage.dollied(lambda path: ("window", SimpleNamespace(camera=camera)), 0.3)
    assert build("p")[0] == "window" and calls == [0.3]

    original = morph_gl.build_app
    seen = []

    def fake_measure(path, size, draws, flat):
        seen.append(morph_gl.build_app is not original)
        raise ValueError("min() iterable argument is empty")

    monkeypatch.setattr(shading, "measure", fake_measure)
    with pytest.raises(ValueError):
        coverage.measure_at("p", (64, 64), 1, False, 0.5)
    assert seen == [True] and morph_gl.build_app is original


def test_coverage_line():
    from lookdev_gpu_probe import probe_worklight_coverage as coverage

    line = coverage.coverage_line("[x] 1 V / 1 F, 1024x768, Smooth, 393216 px covered, 40 rounds after 5", 0.5)
    assert line == "  dolly 0.5: coverage 50.0 % of 1024x768"
