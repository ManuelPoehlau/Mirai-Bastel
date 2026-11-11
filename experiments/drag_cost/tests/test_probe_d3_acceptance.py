"""The D3 acceptance probe (2026-11-11) - headless: arguments, the bar, the statistics, the byte groups and the
import boundary. No pyglet, no window."""

from __future__ import annotations

import ast
import inspect

import pytest

from drag_cost import probe_d3_acceptance as probe
from drag_cost._paths import REPO_ROOT


def test_defaults_are_the_dense_fixture_a_15_percent_region_and_both_interactions():
    args = probe.build_parser().parse_args([])
    assert probe.resolve_asset(args.asset) == probe.DENSE
    assert args.region == 15 and args.steps == probe.DEFAULT_STEPS
    assert args.interactions == ["pose", "weight"] and args.no_panels is False
    assert args.vertex_textures == "live"
    assert probe.build_parser().parse_args(["--vertex-textures", "copy"]).vertex_textures == "copy"
    with pytest.raises(SystemExit):
        probe.build_parser().parse_args(["--vertex-textures", "none"])
    assert args.face_upload == "subdata"
    assert probe.build_parser().parse_args(["--interactions", "still"]).interactions == ["still"]


def test_an_unknown_mesh_exits():
    with pytest.raises(SystemExit, match="no such mesh"):
        probe.resolve_asset("no_such_mesh.obj")
    assert probe.resolve_asset("examples/meshes/gollum_20k.obj") == REPO_ROOT / "examples/meshes/gollum_20k.obj"


def test_the_bar_is_manus_d3():
    assert probe.verdict(16.7) == "meets 16.7 (60 FPS)"
    assert probe.verdict(16.8) == "meets 33.3 (30 FPS), not 16.7"
    assert probe.verdict(33.3).startswith("meets 33.3")
    assert probe.verdict(33.4) == "OVER 33.3"


def test_percentile_is_nearest_rank():
    samples = [float(v) for v in range(1, 21)]  # 1 .. 20
    assert probe.percentile(samples, 0.95) == 19.0
    assert probe.percentile(samples, 0.5) == 10.0
    assert probe.percentile([3.0], 0.95) == 3.0


def test_bytes_are_grouped_into_vertex_and_face_data():
    assert {probe.resource_group(n) for n in ("positions", "normals", "indices")} == {"vertex"}
    for name in ("face_shading", "face_normals", "face_corners", "triangle_faces", "triangle_uvs"):
        assert probe.resource_group(name) == "face"
    assert probe.resource_group("camera_uniforms") == "other"


def test_both_face_data_layouts_are_timed_under_one_row():
    rows = {(cls, method): row for _module, cls, method, row in probe.TIMED}
    assert rows[("RenderMesh", "_upload_rows")] == rows[("RenderMesh", "_upload_face_normals")] == "face_data"


def test_imports_only_src_examples_and_its_own_folder():
    tree = ast.parse(inspect.getsource(probe))
    modules = {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    modules |= {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert modules <= {
        "__future__", "argparse", "ctypes", "importlib", "math", "statistics", "subprocess", "sys", "time", "pathlib",
        "drag_cost", "pyglet", "main", "hud", "mirai", "viewport",
    }
