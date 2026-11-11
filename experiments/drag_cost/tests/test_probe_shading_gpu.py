"""The shading GPU probe (2026-11-11) - headless: arguments, the shader variant, the oracle import, the boundary."""

from __future__ import annotations

import ast
import inspect

import pytest

from drag_cost import probe_shading_gpu as probe


def test_defaults_are_the_dense_fixture_in_the_window_size_of_the_other_probes():
    args = probe.build_parser().parse_args([])
    assert probe.resolve_asset(args.asset) == probe.DENSE
    assert args.size == [1024, 768] and args.draws == probe.DEFAULT_DRAWS and args.flat is False
    assert probe.build_parser().parse_args(["--size", "1920", "1080"]).size == [1920, 1080]
    with pytest.raises(SystemExit, match="no such mesh"):
        probe.resolve_asset("no_such_mesh.obj")


def test_the_rgba_variant_replaces_exactly_the_r32f_fetch():
    from viewport.gl_render_store import FRAGMENT_SRC

    assert FRAGMENT_SRC.count(probe.R32F_FETCH) == 1  # the production fetch the variant replaces
    source = probe.rgba_fragment_source()
    assert probe.R32F_FETCH not in source and probe.RGBA_FETCH in source
    assert source.replace(probe.RGBA_FETCH, probe.R32F_FETCH) == FRAGMENT_SRC


def test_the_oracle_loads_from_the_repo_tests_folder():
    oracle = probe.load_oracle()
    assert hasattr(oracle, "PreO2Store") and hasattr(oracle, "PRE_O2_FRAGMENT_SRC")


def test_imports_only_src_its_own_folder_and_the_test_oracle_by_path():
    tree = ast.parse(inspect.getsource(probe))
    modules = {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    modules |= {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert modules <= {
        "__future__", "argparse", "array", "ctypes", "importlib", "statistics", "sys", "time", "pathlib",
        "drag_cost", "pyglet", "viewport",
    }
