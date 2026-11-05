"""AD-029 P1, the stdlib parts of `src/interop/goz/`: format, completeness rule, helper, registration, inbox, and the
pure plan (`bridge`) on ZBrush 2022.0.8 captures (`tests/fixtures/goz/`). Headless, no pyglet."""

from __future__ import annotations

import json
import struct
import subprocess
import sys
from pathlib import Path

import pytest

import tests._bootstrap  # noqa: F401
from tests._bootstrap import _REPO_ROOT

from core import Mesh, ObjectId, Scene, SceneObject
from interop.goz import helper
from interop.goz import install as goz_install
from interop.goz.bridge import (
    ReturnKind,
    SendRefused,
    build_send,
    catmull_clark_vertex_points,
    from_goz,
    looks_subdivided,
    plan_return,
    to_goz,
)
from interop.goz.files import GozPaths, GozSetupError, snapshot_object, write_goz_list
from interop.goz.format import GozFormatError, as_float32, encode_goz, parse_goz
from interop.goz.transfer import Inbox

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "goz"
EXAMPLES = _REPO_ROOT / "examples"
if str(EXAMPLES) not in sys.path:
    sys.path.insert(0, str(EXAMPLES))


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def flipped(data: bytes) -> bytes:
    """A raw-frame E1 capture as ZBrush returns it for a bridge send: points (x, -y, -z), exact in float32."""
    goz = parse_goz(data)
    return encode_goz(goz.name, [to_goz(p) for p in goz.points], goz.faces)


def head_mesh() -> Mesh:
    from loaders.obj_loader import load_obj
    from mirai.scene_factory import mesh_from_obj_data

    return mesh_from_obj_data(load_obj(EXAMPLES / "meshes" / "head_basemesh.obj"))


def sphere_b() -> Mesh:
    """E1 mesh B (`experiments/goz_probe/make_meshes.py`): Mirai's sphere minus the four quads of one vertex."""
    from mirai.scene_factory import PRIMITIVES

    mesh = PRIMITIVES["sphere"]()
    faces_of: dict = {}
    for fid in mesh.all_face_ids():
        for vid in mesh.face_vertices(fid):
            faces_of.setdefault(vid, []).append(fid)
    candidates = [v for v, fs in faces_of.items() if len(fs) == 4 and all(len(mesh.face_vertices(f)) == 4 for f in fs)]
    vid = min(candidates, key=lambda v: (abs(mesh.vertex_position(v)[1]), -mesh.vertex_position(v)[0], int(v)))
    mesh.delete_faces(sorted(faces_of[vid]))
    return mesh


def identity(_obj, p):
    return tuple(p)


def one_object_scene(mesh: Mesh) -> tuple[Scene, SceneObject]:
    obj = SceneObject(ObjectId(0), mesh, name="Kopf")
    return Scene.from_objects([obj], edit_object_id=obj.id, object_id_counter=1), obj


def plan_for(scene, obj, returned: bytes, *, session="s1"):
    _data, manifest = build_send(scene, obj, identifier="P/Kopf", transfer_id="t", session_id="s1", scene_path=None,
                                 to_world=identity)
    return plan_return(parse_goz(returned), manifest, scene, identifier="P/Kopf", session_id=session, scene_path=None,
                       to_world=identity, to_object=identity)


# -- format ------------------------------------------------------------------------------------------------------------


def test_encode_parse_round_trip_and_layout():
    points = [(0.1, 0.2, 0.3), (1, 0, 0), (0, 1, 0), (0, 0, 1)]
    data = encode_goz("Kopf", points, [(0, 1, 2, 3), (0, 1, 2)])
    assert data[:4] == b"GoZb" and data[31] == 0 and len(data) % 4 == 0
    goz = parse_goz(data)
    assert goz.name == "Kopf" and goz.faces == ((0, 1, 2, 3), (0, 1, 2)) and goz.flags == 0
    assert goz.points[0] == tuple(as_float32(c) for c in points[0])
    assert struct.unpack_from("<i", data, len(data) - 16 - 4)[0] == -1  # triangle = 4th index -1


def test_zbrush_files_parse_and_skip_their_attribute_blocks():
    a = parse_goz(fixture("zb2022_A_obj_import.GoZ"))
    assert a.name == "GoZMesh_A" and len(a.points) == 24 and len(a.faces) == 18
    b = parse_goz(fixture("zb2022_B_move_brush.GoZ"))
    assert len(b.points) == 481 and len(b.faces) == 508 and sum(len(f) == 3 for f in b.faces) == 64


@pytest.mark.parametrize("cut", [0, 10, 31, 40, 100, -1, -17])
def test_truncated_files_fail_closed(cut):
    data = fixture("zb2022_A_obj_import.GoZ")
    with pytest.raises(GozFormatError):
        parse_goz(data[:cut])


def test_malformed_files_fail_closed():
    good = encode_goz("x", [(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)])
    with pytest.raises(GozFormatError):
        parse_goz(b"XoZb" + good[4:])
    with pytest.raises(GozFormatError):
        parse_goz(good + b"\0\0\0\0")
    nan = encode_goz("x", [(float("nan"), 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)])
    with pytest.raises(GozFormatError, match="not finite"):
        parse_goz(nan)
    bad_index = good.replace(struct.pack("<4i", 0, 1, 2, -1), struct.pack("<4i", 0, 1, 7, -1))
    with pytest.raises(GozFormatError, match="outside"):
        parse_goz(bad_index)
    with pytest.raises(ValueError, match="triangles and quads"):
        encode_goz("x", [(0, 0, 0)] * 5, [(0, 1, 2, 3, 4)])


# -- send / plan (pure) -------------------------------------------------------------------------------------------------


def test_send_flips_y_and_z_and_refuses_ngons():
    scene, obj = one_object_scene(head_mesh())
    data, manifest = build_send(scene, obj, identifier="P/Kopf", transfer_id="t", session_id="s", scene_path=None,
                                to_world=identity)
    goz = parse_goz(data)
    vids = obj.mesh.all_vertex_ids()
    assert manifest.vertex_ids == [int(v) for v in vids] and len(goz.points) == 326
    x, y, z = obj.mesh.vertex_position(vids[5])
    assert goz.points[5] == (as_float32(x), as_float32(-y), as_float32(-z))
    assert to_goz(from_goz((1.0, 2.0, 3.0))) == (1.0, 2.0, 3.0)
    mesh = Mesh()
    ids = [mesh.add_vertex(p) for p in ((0, 0, 0), (1, 0, 0), (1, 1, 0), (0.5, 1.5, 0), (0, 1, 0))]
    mesh.add_face(ids)
    with pytest.raises(SendRefused, match="more than 4 corners"):
        build_send(*one_object_scene(mesh), identifier="i", transfer_id="t", session_id="s", scene_path=None,
                   to_world=identity)


def test_plan_unchanged_moved_and_untouched_points_keep_float64():
    scene, obj = one_object_scene(head_mesh())
    assert plan_for(scene, obj, flipped(fixture("zb2022_C_unchanged.GoZ"))).kind is ReturnKind.UNCHANGED
    plan = plan_for(scene, obj, flipped(fixture("zb2022_C_move_brush.GoZ")))
    assert plan.kind is ReturnKind.POSITIONS and len(plan.positions) == 101
    raw = parse_goz(fixture("zb2022_C_move_brush.GoZ")).points
    vids = obj.mesh.all_vertex_ids()
    for i, vid in enumerate(vids):
        if vid in plan.positions:
            assert plan.positions[vid] == raw[i]  # the returned float32, back in Mirai's frame, exactly
        else:
            assert tuple(as_float32(c) for c in obj.mesh.vertex_position(vid)) == raw[i]


def test_plan_on_mesh_b_maps_indices_to_ids_with_gaps():
    scene, obj = one_object_scene(sphere_b())
    vids = obj.mesh.all_vertex_ids()
    assert [int(v) for v in vids] != list(range(len(vids)))  # IDs have gaps
    plan = plan_for(scene, obj, flipped(fixture("zb2022_B_move_brush.GoZ")))
    assert plan.kind is ReturnKind.POSITIONS and len(plan.positions) == 12
    raw = parse_goz(fixture("zb2022_B_move_brush.GoZ")).points
    for vid, p in plan.positions.items():
        assert raw[vids.index(vid)] == p


def test_divided_return_is_held_and_moves_are_not_mistaken_for_it():
    scene, obj = one_object_scene(head_mesh())
    assert plan_for(scene, obj, flipped(fixture("zb2022_C_divided_once.GoZ"))).kind is ReturnKind.SUBDIVIDED
    sent = [to_goz(p) for p in (obj.mesh.vertex_position(v) for v in obj.mesh.all_vertex_ids())]
    faces = [list(f) for f in parse_goz(fixture("zb2022_C_unchanged.GoZ")).faces]
    assert not looks_subdivided(sent, [tuple(map(as_float32, p)) for p in sent], faces)
    moved = parse_goz(flipped(fixture("zb2022_C_move_brush.GoZ"))).points
    assert not looks_subdivided(sent, moved, faces)


def test_divide_without_smt_is_unchanged_and_cage_is_appliable_with_a_warning():
    """D13 (Manu 2026-11-05) on T7b / T7c: without SMT the cage comes back bit-identical; after Cage every point
    moved by <= 4.1e-4 - appliable, the status line warns."""
    scene, obj = one_object_scene(head_mesh())
    assert plan_for(scene, obj, flipped(fixture("zb2022_C_divided_no_smt.GoZ"))).kind is ReturnKind.UNCHANGED
    cage = plan_for(scene, obj, flipped(fixture("zb2022_C_cage.GoZ")))
    assert cage.kind is ReturnKind.POSITIONS and cage.cage_like and len(cage.positions) == 326
    assert "Cage reconstruction" in cage.summary()
    moved = plan_for(scene, obj, flipped(fixture("zb2022_C_move_brush.GoZ")))
    assert not moved.cage_like and "Cage" not in moved.summary()
    held = plan_for(scene, obj, flipped(fixture("zb2022_C_divided_once.GoZ")))
    assert "Cage" in held.reason and "SMT off" in held.reason


def test_catmull_clark_vertex_points_skip_borders_and_fix_a_flat_interior():
    mesh = Mesh()
    ids = {(i, j): mesh.add_vertex((float(i), float(j), 0.0)) for i in range(3) for j in range(3)}
    points = [mesh.vertex_position(ids[k]) for k in sorted(ids)]
    index = {k: n for n, k in enumerate(sorted(ids))}
    faces = [[index[(i, j)], index[(i + 1, j)], index[(i + 1, j + 1)], index[(i, j + 1)]] for i in range(2) for j in range(2)]
    vp = catmull_clark_vertex_points(points, faces)
    assert vp[index[(1, 1)]] == (1.0, 1.0, 0.0) and sum(p is None for p in vp) == 8
    assert not looks_subdivided(points, points, faces)  # nothing moves: never "divided"


def test_topology_change_and_foreign_session_are_new_object_plans():
    scene, obj = one_object_scene(head_mesh())
    goz = parse_goz(flipped(fixture("zb2022_C_unchanged.GoZ")))
    fewer = encode_goz(goz.name, goz.points, goz.faces[:-1])
    plan = plan_for(scene, obj, fewer)
    assert plan.kind is ReturnKind.TOPOLOGY_CHANGED and plan.new_object
    rotated = encode_goz(goz.name, goz.points, [goz.faces[0][1:] + goz.faces[0][:1]] + list(goz.faces[1:]))
    assert plan_for(scene, obj, rotated).kind is ReturnKind.TOPOLOGY_CHANGED  # corner rotation counts
    other = plan_for(scene, obj, flipped(fixture("zb2022_C_move_brush.GoZ")), session="s2")
    assert other.kind is ReturnKind.UNKNOWN_OBJECT
    unknown = plan_return(goz, None, scene, identifier="P/X", session_id="s1", scene_path=None, to_world=identity,
                          to_object=identity)
    assert unknown.kind is ReturnKind.UNKNOWN_OBJECT and unknown.new_object


# -- completeness rule, helper, inbox, registration ----------------------------------------------------------------------


@pytest.fixture
def root(tmp_path):
    r = tmp_path / "Pixologic"
    (r / "GoZBrush").mkdir(parents=True)
    (r / "GoZProjects" / "Default").mkdir(parents=True)
    return GozPaths(r)


def test_helper_snapshots_and_tickets_and_mirai_claims_once(root, tmp_path):
    identifier = str(root.project_dir() / "Kopf")
    data = flipped(fixture("zb2022_C_move_brush.GoZ"))
    Path(identifier + ".GoZ").write_bytes(data)
    write_goz_list(root.object_list, [identifier])
    inbox = tmp_path / "inbox"
    ticket = helper.run(root, inbox, settle=0.0)
    raw = json.loads(ticket.read_text())
    assert raw["objects"][0]["complete"] and raw["objects"][0]["identifier"] == identifier
    box = Inbox(inbox)
    assert box.waiting() == [ticket]
    (received,) = box.claim(ticket)
    assert received.error is None and received.goz == parse_goz(data)
    assert box.claim(ticket) is None and box.waiting() == []  # claimed once
    assert Path(identifier + ".GoZ").read_bytes() == data  # ZBrush's file only read


def test_incomplete_transfer_is_reported_not_parsed(root, tmp_path):
    identifier = str(root.project_dir() / "Kopf")
    Path(identifier + ".GoZ").write_bytes(fixture("zb2022_C_unchanged.GoZ")[:-20])
    clock = iter(range(100))
    snap = snapshot_object(identifier, tmp_path / "st", 0, settle=0, deadline=3, clock=lambda: next(clock),
                           sleep=lambda s: None)
    assert not snap.complete and "GozFormatError" in snap.error and snap.attempts > 1
    write_goz_list(root.object_list, [identifier])
    ticket = helper.run(root, tmp_path / "inbox", settle=0, deadline=0)
    (received,) = Inbox(tmp_path / "inbox").claim(ticket)
    assert received.goz is None and "incomplete" in received.error


def test_snapshot_refuses_a_file_that_changes_in_the_quiet_period(tmp_path):
    source = tmp_path / "Kopf"
    data = fixture("zb2022_C_unchanged.GoZ")
    Path(str(source) + ".GoZ").write_bytes(data)

    def sleep(_s):
        Path(str(source) + ".GoZ").write_bytes(fixture("zb2022_C_move_brush.GoZ"))

    snap = snapshot_object(str(source), tmp_path / "st", 0, settle=1.0, deadline=0, sleep=sleep)
    assert not snap.complete and "changed" in snap.error


def test_helper_runs_isolated_stdlib_only(root, tmp_path):
    """What Edit.bat runs: `python -I helper.py ...`, importing neither pyglet nor `core`."""
    script = _REPO_ROOT / "src" / "interop" / "goz" / "helper.py"
    write_goz_list(root.object_list, [])
    run = subprocess.run([sys.executable, "-I", str(script), "--root", str(root.root), "--inbox", str(tmp_path / "in"),
                          "--settle", "0", "--"], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    assert len(Inbox(tmp_path / "in").waiting()) == 1
    probe = ("import runpy, sys; sys.path.insert(0, sys.argv[1]); import interop.goz.helper; "
             "print(sorted(m for m in sys.modules if m.split('.')[0] in ('pyglet', 'core', 'mirai')))")
    out = subprocess.run([sys.executable, "-I", "-c", probe, str(_REPO_ROOT / "src")], capture_output=True, text=True,
                         timeout=60)
    assert out.returncode == 0 and out.stdout.strip() == "[]", out.stdout + out.stderr


def test_install_writes_our_folder_refuses_a_foreign_one_and_uninstalls(root, tmp_path):
    assert not goz_install.is_installed(root)
    app = goz_install.install(root, tmp_path / "inbox", python="C:\\Python\\python.exe")
    names = sorted(p.name for p in app.iterdir())
    assert names == [".mirai_goz_app", "Edit.bat", "GoZ_Info.txt", "Init.bat", "Locate.bat", "Mirai.cmd"]
    info = (app / "GoZ_Info.txt").read_bytes()
    assert b'NAME\t\t= "Mirai"' in info and b"\r\n" in info and b"FLIP" not in info
    edit = (app / "Edit.bat").read_text()
    assert '"C:\\Python\\python.exe" -I' in edit and "helper.py" in edit and "--inbox" in edit and "-tmap" not in edit
    assert app.name == "Mirai" and goz_install.is_installed(root)
    goz_install.install(root, tmp_path / "inbox")  # our own folder: replaced
    assert goz_install.uninstall(root) and not app.exists()
    app.mkdir(parents=True)
    (app / "GoZ_Info.txt").write_text("someone else's")
    with pytest.raises(GozSetupError, match="not Mirai's"):
        goz_install.install(root, tmp_path / "inbox")
    with pytest.raises(GozSetupError):
        goz_install.uninstall(root)
    assert (app / "GoZ_Info.txt").read_text() == "someone else's"


def test_interop_imports_only_core_and_the_standard_library():
    """AD-029 §2: `src/interop/` imports `core`, itself and the stdlib - no pyglet, no `mirai`, no `experiments`."""
    import ast

    stdlib = getattr(sys, "stdlib_module_names", None)
    if stdlib is None:
        pytest.skip("needs Python 3.10+ for sys.stdlib_module_names")
    for path in (_REPO_ROOT / "src" / "interop").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names = [node.module or ""]
            else:
                continue
            for name in names:
                top = name.split(".")[0]
                assert top in stdlib or top in ("core", "interop", "__future__"), f"{path.name}: imports {name}"
