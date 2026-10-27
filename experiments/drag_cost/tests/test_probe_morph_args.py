"""Argument handling and import boundary of the morph probe (AD-025 Phases 3 and 5) - headless: no pyglet,
no window (the probe imports pyglet and `src/main.py` lazily)."""

from __future__ import annotations

import ast
import inspect

import pytest

from drag_cost import probe_morph_gl as probe
from drag_cost._paths import REPO_ROOT


def test_defaults_are_head_body_and_gollum_20k():
    args = probe.build_parser().parse_args([])
    assert args.assets == list(probe.DEFAULT_ASSETS) and args.steps == probe.DEFAULT_STEPS
    assert args.reps == probe.DEFAULT_REPS and args.only_topology is False
    assert probe.resolve_mesh("head_basemesh").name == "head_basemesh.obj"
    assert probe.resolve_mesh("examples/meshes/gollum_20k.obj") == REPO_ROOT / "examples/meshes/gollum_20k.obj"


def test_an_unknown_mesh_exits_with_the_known_names():
    with pytest.raises(SystemExit, match="head_basemesh"):
        probe.resolve_mesh("no_such_mesh")


def test_imports_only_src_examples_and_its_own_folder():
    tree = ast.parse(inspect.getsource(probe))
    modules = {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    modules |= {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert modules <= {"__future__", "argparse", "math", "sys", "time", "pathlib", "drag_cost", "loaders",
                       "pyglet", "main", "mirai", "core", "viewport"}


def test_topology_rows_cover_the_phase5_operations():
    args = probe.build_parser().parse_args(["--only-topology", "--reps", "3"])
    assert args.only_topology and args.reps == 3
    assert probe.TOPOLOGY_OPS == ("knife", "loop insert", "extrude", "collapse")
