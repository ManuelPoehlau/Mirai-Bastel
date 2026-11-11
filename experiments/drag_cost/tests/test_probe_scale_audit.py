"""The scale audit probes (2026-11-10) - headless: arguments, the dense asset, the import boundary, and that
the kernel probe's array variants compute what the production code computes. No pyglet, no window."""

from __future__ import annotations

import ast
import inspect

import pytest

from drag_cost import probe_kernels as kernels
from drag_cost import probe_scale_audit as probe
from drag_cost._paths import REPO_ROOT


def test_defaults_are_gollum_20k_and_the_dense_mesh():
    args = probe.build_parser().parse_args([])
    assert args.assets == [probe.GOLLUM_20K, probe.DENSE_NAME]
    assert args.regions == list(probe.DEFAULT_REGIONS) and args.steps == probe.DEFAULT_STEPS
    assert args.only is None and args.make_dense is False
    assert probe.resolve_asset(probe.GOLLUM_20K) == REPO_ROOT / probe.GOLLUM_20K


def test_an_unknown_mesh_exits_naming_the_dense_one():
    with pytest.raises(SystemExit, match=probe.DENSE_NAME):
        probe.resolve_asset("no_such_mesh.obj")


def test_only_takes_one_of_the_blocks():
    assert probe.build_parser().parse_args(["--only", "split"]).only == "split"
    with pytest.raises(SystemExit):
        probe.build_parser().parse_args(["--only", "everything"])


def test_the_dense_asset_is_one_catmull_clark_step_of_gollum_20k(tmp_path):
    target = probe.make_dense(tmp_path / "dense.obj")
    lines = target.read_text(encoding="ascii").splitlines()
    vertices = [line for line in lines if line.startswith("v ")]
    faces = [line for line in lines if line.startswith("f ")]
    assert len(vertices) == 87_500 and len(faces) == 87_500
    assert all(len(line.split()) == 5 for line in faces)  # quads
    # Manu D5 (2026-11-11): the committed fixture is exactly what the generator writes (provenance: fixtures/README.md)
    assert target.read_bytes() == probe.DENSE.read_bytes()


def test_process_memory_is_a_number_or_none():
    value = probe.process_memory_mib()
    assert value is None or value > 0.0


@pytest.mark.parametrize("module", [probe, kernels])
def test_imports_only_src_examples_and_its_own_folder(module):
    tree = ast.parse(inspect.getsource(module))
    modules = {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    modules |= {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert modules <= {
        "__future__", "argparse", "array", "ctypes", "gc", "hashlib", "math", "os", "platform", "shutil", "statistics",
        "subprocess", "sys", "tempfile", "time", "pathlib",
        "drag_cost", "loaders", "pyglet", "numpy", "mirai", "core", "viewport",
    }


# -- the kernel probe computes what production computes ----------------------------------------------------


def _head():
    from loaders.obj_loader import load_obj
    from mirai.scene_factory import mesh_from_positions_and_faces
    from viewport.render_mesh import RenderMesh
    from viewport.resource_store import TraceStore

    data = load_obj(REPO_ROOT / "examples/meshes/head_basemesh.obj")
    mesh = mesh_from_positions_and_faces(data.vertices, data.faces)
    return data, mesh, RenderMesh(mesh, store_type=TraceStore)


def test_the_flat_python_patch_gives_the_production_vertex_normals():
    data, mesh, render_mesh = _head()
    flat = kernels.FlatPython(data.vertices, data.faces)
    flat.patch(range(len(data.vertices)))
    normals = render_mesh.derived.vertex_normals
    for slot, vid in enumerate(mesh.all_vertex_ids()):
        got = flat.nrm_mirror[3 * slot:3 * slot + 3]
        assert got == pytest.approx(normals[vid], abs=1e-6)  # the mirror is float32


def test_the_packed_normals_equal_production_for_a_patch_and_for_the_whole_mesh():
    np = pytest.importorskip("numpy")
    data, mesh, render_mesh = _head()
    packed = kernels.Packed(np, data.vertices, data.faces)
    packed.numpy_all_normals()
    normals = render_mesh.derived.vertex_normals
    vids = mesh.all_vertex_ids()
    for slot, vid in enumerate(vids):
        assert tuple(packed.VN[slot]) == pytest.approx(normals[vid], abs=1e-12)
    # move a region in both, patch both: the 1-ring result is the same
    moved = list(range(0, len(vids), 7))
    for slot in moved:
        x, y, z = mesh.vertex_position(vids[slot])
        mesh.set_vertex_position(vids[slot], (x + 0.01, y - 0.02, z + 0.005))
        packed.P[slot] = (x + 0.01, y - 0.02, z + 0.005)
    render_mesh.mark_vertices_dirty({vids[slot] for slot in moved})
    render_mesh.sync()
    packed.numpy_patch(np.asarray(moved, dtype=np.int64))
    for slot, vid in enumerate(vids):
        assert tuple(packed.VN[slot]) == pytest.approx(render_mesh.derived.vertex_normals[vid], abs=1e-12)


def test_the_blocks_report_without_numpy_too():
    data, mesh, render_mesh = _head()
    lines = kernels.visible_block(mesh, data.vertices, data.faces, render_mesh, None, None, None)
    assert len(lines) == 2 + len(kernels.VISIBLE_REGIONS)
    assert lines[-1].split()[-2:] == ["-", "-"]  # NumPy and native columns empty
    assert any("apply_full" in line for line in kernels.subd_block(mesh, None, None))
