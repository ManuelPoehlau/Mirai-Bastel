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

from core import FaceRegion, FaceRegions, Mesh, ObjectId, Scene, SceneObject
from interop.goz import helper
from interop.goz import install as goz_install
from interop.goz.bridge import (
    REST_GROUP,
    ReturnKind,
    SendRefused,
    build_send,
    catmull_clark_vertex_points,
    from_goz,
    looks_subdivided,
    plan_return,
    SymmetryInfo,
    polygon_area,
    split_ngon,
    split_ngons,
    valid_split,
    to_goz,
)
from interop.goz.files import GozPaths, GozSetupError, snapshot_object, write_goz_list
from interop.goz.format import GozFormatError, as_float32, encode_goz, parse_goz
from interop.goz.transfer import Inbox

from viewport.derived import triangulate_face  # noqa: E402  (the glue's triangulation, core-only)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "goz"
EXAMPLES = _REPO_ROOT / "examples"
if str(EXAMPLES) not in sys.path:
    sys.path.insert(0, str(EXAMPLES))


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def flipped(data: bytes) -> bytes:
    """A raw-frame E1 capture as ZBrush returns it for a bridge send: points (x, -y, -z), exact in float32."""
    goz = parse_goz(data)
    return encode_goz(goz.name, [to_goz(p) for p in goz.points], goz.faces, goz.groups)


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


def plan_for(scene, obj, returned: bytes, *, session="s1", manifest=None, edit=None):
    if manifest is None:
        _data, manifest = build_send(scene, obj, identifier="P/Kopf", transfer_id="t", session_id="s1",
                                     scene_path=None, to_world=identity, triangulate=triangulate_face)
    if edit is not None:
        edit()
    from mirai.regions import new_group_name

    return plan_return(parse_goz(returned), manifest, scene, identifier="P/Kopf", session_id=session, scene_path=None,
                       to_world=identity, to_object=identity, new_group_name=new_group_name)


#: E2 (2026-11-05): the probe sent the head in four bands by height, ids 101-104; here the regions Mirai sends as 1-4
BANDS = ("Stirn", "Augen", "Mund", "Hals")
E2_UNCHANGED = "zb2022_E2_head_groups_unchanged.GoZ"
E2_REGROUPED = "zb2022_E2_head_groups_regrouped.GoZ"


def e2(name: str, *, points=None) -> bytes:
    """An E2 capture as ZBrush returns it for a bridge send of `band_regions`: ids 101-104 -> 1-4 (ZBrush keeps the
    ids it was sent), its own new id 3225 as is. `points` replaces the points (a sculpt on top of the regroup)."""
    goz = parse_goz(fixture(name))
    groups = [g - 100 if 101 <= g <= 104 else g for g in goz.groups]
    return encode_goz(goz.name, goz.points if points is None else points, goz.faces, groups)


def band_regions(mesh: Mesh, bands=BANDS) -> FaceRegions:
    ids = parse_goz(fixture(E2_UNCHANGED)).groups
    fids = mesh.all_face_ids()
    return FaceRegions(tuple(FaceRegion(name, frozenset(f for f, g in zip(fids, ids) if g == 101 + BANDS.index(name)))
                             for name in bands))


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


def test_groups_block_round_trip_and_fail_closed():
    points = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
    data = encode_goz("g", points, [(0, 1, 2), (0, 2, 3)], [7, REST_GROUP])
    assert parse_goz(data).groups == (7, REST_GROUP)
    assert parse_goz(encode_goz("g", points, [(0, 1, 2)])).groups is None
    short = data.replace(struct.pack("<IIIf", 40001, 20, 2, 0.0), struct.pack("<IIIf", 40001, 20, 1, 0.0))
    with pytest.raises(GozFormatError, match="1 ids for 2 faces"):
        parse_goz(short)
    with pytest.raises(ValueError, match="16-bit"):
        encode_goz("g", points, [(0, 1, 2)], [70000])
    unchanged = parse_goz(fixture(E2_UNCHANGED))  # ZBrush 2022.0.8 wrote it: 324 ids, no padding
    assert sorted(set(unchanged.groups)) == [101, 102, 103, 104] and len(unchanged.groups) == 324


# -- send / plan (pure) -------------------------------------------------------------------------------------------------


def test_send_flips_y_and_z_and_needs_a_triangulation_for_ngons():
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
    with pytest.raises(SendRefused, match="no triangulation was given"):
        build_send(*one_object_scene(mesh), identifier="i", transfer_id="t", session_id="s", scene_path=None,
                   to_world=identity)


def test_plan_unchanged_moved_and_untouched_points_keep_float64():
    scene, obj = one_object_scene(head_mesh())
    assert plan_for(scene, obj, flipped(fixture("zb2022_C_unchanged.GoZ"))).kind is ReturnKind.UNCHANGED
    plan = plan_for(scene, obj, flipped(fixture("zb2022_C_move_brush.GoZ")))
    assert plan.kind is ReturnKind.IN_PLACE and len(plan.positions) == 101
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
    assert plan.kind is ReturnKind.IN_PLACE and len(plan.positions) == 12
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
    assert cage.kind is ReturnKind.IN_PLACE and cage.cage_like and len(cage.positions) == 326
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


# -- polygroups (P2a) --------------------------------------------------------------------------------------------------


def head_with_bands(bands=BANDS):
    scene, obj = one_object_scene(head_mesh())
    obj.mesh.face_regions = band_regions(obj.mesh, bands)
    return scene, obj


def test_send_carries_region_ids_a_rest_id_and_records_overlaps():
    scene, obj = head_with_bands(BANDS[:3])  # Hals not a region: its 50 faces are the rest
    mesh = obj.mesh
    first = next(iter(sorted(mesh.face_regions.get("Stirn").faces, key=int)))
    mesh.face_regions = FaceRegions((*mesh.face_regions.regions, FaceRegion("Extra", frozenset({first}))))
    data, manifest = build_send(scene, obj, identifier="P/Kopf", transfer_id="t", session_id="s", scene_path=None,
                                to_world=identity)
    groups = parse_goz(data).groups
    expected = [g - 100 if g != 104 else REST_GROUP for g in parse_goz(fixture(E2_UNCHANGED)).groups]
    assert list(groups) == expected == manifest.sent_groups
    assert manifest.group_names == {"1": "Stirn", "2": "Augen", "3": "Mund", "4": "Extra"}
    assert manifest.rest_group == REST_GROUP
    assert manifest.group_overlaps == [[mesh.all_face_ids().index(first), ["Extra"]]]


def test_e2_unchanged_groups_change_nothing_and_a_regroup_becomes_a_new_group():
    scene, obj = head_with_bands()
    plan = plan_for(scene, obj, e2(E2_UNCHANGED))
    assert plan.kind is ReturnKind.UNCHANGED and "no group changed" in plan.reason and not plan.regions_changed
    plan = plan_for(scene, obj, e2(E2_REGROUPED))
    assert plan.kind is ReturnKind.IN_PLACE and plan.positions == {} and plan.regions_changed
    assert plan.reason == "no point moved, groups changed"
    assert "groups: 1 changed, 1 new (12 faces regrouped)" in plan.summary()
    regions = plan.regions
    assert [r.name for r in regions.regions] == [*BANDS, "Group 1"]
    regrouped = parse_goz(fixture(E2_REGROUPED)).groups
    fids = obj.mesh.all_face_ids()
    assert regions.get("Group 1").faces == {f for f, g in zip(fids, regrouped) if g == 3225}
    assert len(regions.get("Hals").faces) == 38 and regions.get("Stirn") == obj.mesh.face_regions.get("Stirn")
    assert plan.group_names[3225] == "Group 1" and plan.zbrush_groups == tuple(parse_goz(e2(E2_REGROUPED)).groups)


def test_known_ids_rest_id_and_overlaps():
    scene, obj = head_with_bands(BANDS[:3])
    mesh = obj.mesh
    fids = mesh.all_face_ids()
    stirn = sorted(mesh.face_regions.get("Stirn").faces, key=int)
    keep, moved = stirn[0], stirn[1]
    mesh.face_regions = FaceRegions((*mesh.face_regions.regions, FaceRegion("Extra", frozenset({keep, moved}))))
    _data, manifest = build_send(scene, obj, identifier="P/Kopf", transfer_id="t", session_id="s1", scene_path=None,
                                 to_world=identity)
    goz = parse_goz(e2(E2_UNCHANGED))
    groups = list(manifest.sent_groups)
    rest_faces = [i for i, g in enumerate(groups) if g == REST_GROUP][:5]
    for i in rest_faces:
        groups[i] = 2  # rest painted with a known group -> Augen
    groups[fids.index(moved)] = REST_GROUP  # a Stirn face (also in Extra) -> no group at all
    plan = plan_for(scene, obj, encode_goz(goz.name, goz.points, goz.faces, groups), manifest=manifest)
    regions = plan.regions
    assert {fids[i] for i in rest_faces} <= regions.get("Augen").faces
    assert moved not in regions.get("Stirn").faces and regions.get("Extra").faces == {keep}  # overlap of a changed face
    assert keep in regions.get("Stirn").faces  # an unchanged face keeps both memberships
    assert "groups: 3 changed, 0 new (6 faces regrouped)" in plan.summary()


def test_one_unknown_id_for_every_face_leaves_the_groups_alone():
    scene, obj = head_with_bands()
    plan = plan_for(scene, obj, flipped(fixture("zb2022_C_move_brush.GoZ")))  # ZBrush's single id 63238
    assert plan.kind is ReturnKind.IN_PLACE and not plan.regions_changed and plan.zbrush_groups is None
    assert "one group Mirai never sent (63238)" in plan.summary()


def test_a_mirai_region_edit_since_the_send_is_a_conflict():
    scene, obj = head_with_bands()
    mesh = obj.mesh
    plan = plan_for(scene, obj, e2(E2_REGROUPED),
                    edit=lambda: setattr(mesh, "face_regions", band_regions(mesh, BANDS[:3])))
    assert plan.kind is ReturnKind.CONFLICT and "(groups)" in plan.reason


def test_new_group_names_follow_mirai_numbering_and_two_new_ids_get_two_groups():
    scene, obj = head_with_bands()
    mesh = obj.mesh
    mesh.face_regions = FaceRegions(tuple(FaceRegion("Group 7" if r.name == "Mund" else r.name, r.faces)
                                          for r in mesh.face_regions.regions))
    goz = parse_goz(e2(E2_UNCHANGED))
    groups = list(goz.groups)
    groups[0], groups[1] = 500, 501
    plan = plan_for(scene, obj, encode_goz(goz.name, goz.points, goz.faces, groups))
    assert plan.group_names[500] == "Group 8" and plan.group_names[501] == "Group 9"


# -- n-gons (P2b) ------------------------------------------------------------------------------------------------------


def _polygon(points):
    mesh = Mesh()
    ids = [mesh.add_vertex((x, y, 0.0)) for x, y in points]
    return ids, {v: mesh.vertex_position(v) for v in ids}


def _split(points):
    ids, pos = _polygon(points)
    return split_ngon(ids, pos.__getitem__, triangulate_face), [pos[v] for v in ids]


def _check_cover(pieces, pts):
    """Every piece in the boundary's winding with a real area, no reflex quad, together exactly the polygon."""
    whole = polygon_area(pts)
    total = 0.0
    for piece in pieces:
        corners = [pts[k] for k in piece]
        assert list(piece) == sorted(piece) and len(piece) in (3, 4)
        from interop.goz.bridge import newell

        assert newell(corners)[2] > 0  # counter-clockwise like the boundary
        total += polygon_area(corners)
    assert total == pytest.approx(whole)


@pytest.mark.parametrize("points, quads, tris", [
    ([(0, 0), (2, 0), (3, 1), (2, 2), (0, 2), (-1, 1)], 2, 0),  # convex 6-gon
    ([(0, 0), (2, 0), (3, 1), (1, 2), (-1, 1)], 1, 1),  # convex 5-gon: one quad, one triangle
    ([(0, 0), (1, 0), (2, 0), (2, 2), (0, 2)], 1, 1),  # Knife point on an edge: no zero-area triangle
    ([(0, 0), (4, 0), (4, 1), (1, 1), (1, 4), (0, 4)], 2, 0),  # concave L 6-gon
    ([(0, 0), (4, 0), (4, 4), (3, 4), (2, 1), (1, 4), (0, 4)], 2, 1),  # concave 7-gon (a notch)
])
def test_split_ngon_prefers_quads_covers_the_polygon_and_is_deterministic(points, quads, tris):
    pieces, pts = _split(points)
    assert (sum(len(p) == 4 for p in pieces), sum(len(p) == 3 for p in pieces)) == (quads, tris), pieces
    _check_cover(pieces, pts)
    for piece in pieces:
        assert polygon_area([pts[k] for k in piece]) > 0
    assert _split(points)[0] == pieces


def head_with_ngons(count=3):
    """The head with `count` interior edges dissolved (each merges two quads into a 6-gon, no point removed)."""
    scene, obj = one_object_scene(head_mesh())
    mesh = obj.mesh
    chosen, touched = [], set()
    for e in mesh.all_edge_ids():
        faces = set(mesh.edge_faces(e))
        if len(faces) == 2 and not faces & touched and all(len(mesh.face_vertices(f)) == 4 for f in faces):
            chosen.append(e)
            touched |= faces
            if len(chosen) == count:
                break
    for e in chosen:
        mesh.dissolve_edges([e], cleanup=False)
    assert sum(len(mesh.face_vertices(f)) == 6 for f in mesh.all_face_ids()) == count
    return scene, obj


def test_send_splits_ngons_in_the_file_only():
    scene, obj = head_with_ngons()
    mesh = obj.mesh
    data, manifest = build_send(scene, obj, identifier="P/Kopf", transfer_id="t", session_id="s", scene_path=None,
                                to_world=identity, triangulate=triangulate_face)
    goz = parse_goz(data)
    assert len(goz.points) == 326 and len(goz.faces) == 324  # 321 faces, three 6-gons as two quads each
    assert all(len(f) == 4 for f in goz.faces) and len(manifest.ngons) == 3
    for fid, pieces in manifest.ngons:
        assert all(manifest.face_ids[i] == fid for i in pieces) and len(pieces) == 2
        corners = {manifest.vertex_ids[k] for i in pieces for k in goz.faces[i]}
        assert corners == {int(v) for v in mesh.face_vertices(type(mesh.all_face_ids()[0])(fid))}
    assert len(mesh.all_face_ids()) == 321  # Mirai's mesh is unchanged


def test_ngon_round_trip_maps_points_back_and_other_topology_is_a_new_object():
    scene, obj = head_with_ngons()
    data, manifest = build_send(scene, obj, identifier="P/Kopf", transfer_id="t", session_id="s1", scene_path=None,
                                to_world=identity, triangulate=triangulate_face)
    sent = parse_goz(data)
    sculpt = parse_goz(flipped(fixture("zb2022_C_move_brush.GoZ"))).points  # ZBrush's Move brush on the same points
    plan = plan_for(scene, obj, encode_goz(sent.name, sculpt, sent.faces, sent.groups), manifest=manifest)
    assert plan.kind is ReturnKind.IN_PLACE and len(plan.positions) == 101
    plan = plan_for(scene, obj, flipped(fixture("zb2022_C_move_brush.GoZ")), manifest=manifest)  # the old quads
    assert plan.kind is ReturnKind.TOPOLOGY_CHANGED


def test_an_ngon_split_across_groups_takes_the_largest_area():
    mesh = Mesh()
    ids = [mesh.add_vertex((x, y, 0.0)) for x, y in [(0, 0), (6, 0), (8, 1), (6, 2), (0, 2), (-1, 1)]]
    extra = mesh.add_vertex((8, 3, 0.0))
    ngon = mesh.add_face(ids)
    tri = mesh.add_face([ids[3], ids[2], extra])
    mesh.face_regions = FaceRegions((FaceRegion("Kappe", frozenset({ngon})),))
    scene, obj = one_object_scene(mesh)
    data, manifest = build_send(scene, obj, identifier="P/Kopf", transfer_id="t", session_id="s1", scene_path=None,
                                to_world=identity, triangulate=triangulate_face)
    sent = parse_goz(data)
    (_fid, pieces), = manifest.ngons
    areas = [polygon_area([sent.points[k] for k in sent.faces[i]]) for i in pieces]
    assert areas[0] != areas[1]  # 8 and 7
    big, small = (pieces[0], pieces[1]) if areas[0] > areas[1] else (pieces[1], pieces[0])
    for winner, loser, region in ((big, small, "Group 1"), (small, big, "Kappe")):
        groups = list(sent.groups)
        groups[winner], groups[loser] = 777, 1  # ZBrush painted part of the n-gon with a new group
        plan = plan_for(scene, obj, encode_goz(sent.name, sent.points, sent.faces, groups), manifest=manifest)
        assert "1 n-gon split across groups in ZBrush took the group with the largest area" in plan.summary()
        holder = plan.regions.get(region) if plan.regions_changed else obj.mesh.face_regions.get(region)
        assert ngon in holder.faces, (region, plan.summary())
    assert tri in mesh.all_face_ids() and len(mesh.face_vertices(ngon)) == 6


# -- mirror-symmetric n-gon split (Manu 2026-11-05) ---------------------------------------------------------------------


def _mirror_x(p):
    return (-p[0], p[1], p[2])


def _sym_polygon(points):
    """One n-gon in the plane z = 0, mirror plane x = 0: corners with x = 0 are seam, the rest paired by position."""
    mesh = Mesh()
    ids = [mesh.add_vertex((float(x), float(y), 0.0)) for x, y in points]
    face = mesh.add_face(ids)
    at = {mesh.vertex_position(v): v for v in ids}
    seam = tuple(v for v in ids if mesh.vertex_position(v)[0] == 0.0)
    pairs = tuple((v, at[_mirror_x(mesh.vertex_position(v))]) for v in ids if mesh.vertex_position(v)[0] > 0)
    return mesh, face, SymmetryInfo(pairs, seam, _mirror_x)


def _is_own_mirror(pieces, symmetry):
    partner = {v: v for v in symmetry.seam}
    for a, b in symmetry.pairs:
        partner[a], partner[b] = b, a
    return {frozenset(partner[v] for v in p) for p in pieces} == {frozenset(p) for p in pieces}


@pytest.mark.parametrize("points, quads, tris", [
    ([(0, 0), (2, 1), (2, 3), (0, 4), (-2, 3), (-2, 1)], 2, 0),  # two corners on the plane: cut along it
    ([(0, 3), (2, 2), (1, 0), (-1, 0), (-2, 2)], 1, 1),  # apex on the plane: ladder, triangle + quad
    ([(1, 0), (2, 1), (1, 2), (-1, 2), (-2, 1), (-1, 0)], 2, 0),  # the plane crosses two edges: ladder of quads
    ([(0, 0), (2, 1), (3, 2), (2, 3), (0, 4), (-2, 3), (-3, 2), (-2, 1)], 2, 2),  # 8-gon
    ([(0, 0), (3, 1), (3, 3), (0, 1.5), (-3, 3), (-3, 1)], 2, 0),  # concave (a notch at the top)
])
def test_an_ngon_on_the_mirror_plane_is_split_into_its_own_mirror_image(points, quads, tris):
    mesh, face, sym = _sym_polygon(points)
    splits, stats = split_ngons(mesh, [face], triangulate_face, sym)
    pieces = splits[face]
    assert stats == {"split": 1, "mirrored": 1, "asymmetric": 0}
    assert _is_own_mirror(pieces, sym) and valid_split(mesh.face_vertices(face), pieces, mesh.vertex_position)
    assert (sum(len(p) == 4 for p in pieces), sum(len(p) == 3 for p in pieces)) == (quads, tris), pieces


def test_without_symmetry_the_split_is_the_plain_one():
    mesh, face, _sym = _sym_polygon([(0, 0), (2, 1), (2, 3), (0, 4), (-2, 3), (-2, 1)])
    splits, stats = split_ngons(mesh, [face], triangulate_face)
    boundary = mesh.face_vertices(face)
    assert stats == {"split": 1}
    assert splits[face] == [[boundary[k] for k in p] for p in split_ngon(boundary, mesh.vertex_position,
                                                                           triangulate_face)]


def head_with_mirrored_ngons(pairs=8):
    """The head, X symmetry on, with `pairs` interior edges dissolved on the +X side and their mirror edges too: mirrored
    6-gon pairs (before the fix: 0 of 8 pairs split alike, Manu 2026-11-05)."""
    from mirai.symmetry import CorrespondenceState, vertex_correspondence
    from mirai.symmetry_axis import set_symmetry_axis
    from zbrush_bridge import symmetry_info

    mesh = head_mesh()
    set_symmetry_axis(mesh, "X")
    corr = vertex_correspondence(mesh)
    partner = {v: (c.partner if c.state is CorrespondenceState.PAIRED else v) for v, c in corr.items()}
    edge_of = {frozenset(mesh.edge_vertices(e)): e for e in mesh.all_edge_ids()}
    done, touched = 0, set()
    for e in list(mesh.all_edge_ids()):
        if done == pairs:
            break
        a, b = mesh.edge_vertices(e)
        if min(mesh.vertex_position(a)[0], mesh.vertex_position(b)[0]) < 0.3:
            continue
        me = edge_of.get(frozenset((partner[a], partner[b])))
        fs = set(mesh.edge_faces(e)) | set(mesh.edge_faces(me)) if me is not None else set()
        if len(fs) != 4 or fs & touched or any(len(mesh.face_vertices(f)) != 4 for f in fs):
            continue
        touched |= fs
        mesh.dissolve_edges([e], cleanup=False)
        mesh.dissolve_edges([me], cleanup=False)
        done += 1
    assert done == pairs
    return mesh, symmetry_info(mesh)


def test_mirrored_ngon_pairs_are_split_alike():
    mesh, sym = head_with_mirrored_ngons()
    ngons = [f for f in mesh.all_face_ids() if len(mesh.face_vertices(f)) > 4]
    splits, stats = split_ngons(mesh, ngons, triangulate_face, sym)
    assert stats == {"split": 16, "mirrored": 16, "asymmetric": 0}
    every = [p for f in ngons for p in splits[f]]
    assert _is_own_mirror(every, sym)  # the pieces of the whole mesh map onto themselves
    from interop.goz.bridge import newell

    for f in ngons:  # each piece in its face's winding, together the face (Newell vectors add up exactly)
        boundary = mesh.face_vertices(f)
        assert {v for p in splits[f] for v in p} == set(boundary)
        for p in splits[f]:
            assert list(p) == sorted(p, key=boundary.index)
        whole = newell([mesh.vertex_position(v) for v in boundary])
        total = [sum(newell([mesh.vertex_position(v) for v in p])[c] for p in splits[f]) for c in range(3)]
        assert total == pytest.approx(list(whole), abs=1e-9)


def test_an_ngon_with_an_unpaired_corner_keeps_the_plain_split():
    mesh, face, sym = _sym_polygon([(0, 0), (2, 1), (2, 3), (0, 4), (-2, 3), (-2, 1)])
    lonely = SymmetryInfo(sym.pairs[1:], sym.seam, sym.mirror)
    _splits, stats = split_ngons(mesh, [face], triangulate_face, lonely)
    assert stats == {"split": 1, "mirrored": 0, "asymmetric": 1}


def test_ngons_across_the_plane_whose_seam_edge_was_dissolved_split_symmetrically():
    """Dissolving a seam edge merges two mirrored quads into a 6-gon whose corners on the plane are no longer declared
    seam (`mirai.symmetry`: UNPAIRED); they lie exactly on the plane, so the split still treats them as their own
    image: all 36 such 6-gons of the head become two mirrored quads (cut along the plane)."""
    from mirai.symmetry_axis import set_symmetry_axis
    from zbrush_bridge import symmetry_info

    mesh = head_mesh()
    set_symmetry_axis(mesh, "X")
    seam = set(symmetry_info(mesh).seam)
    touched = set()
    for e in list(mesh.all_edge_ids()):
        if not mesh.is_valid_edge(e):
            continue
        a, b = mesh.edge_vertices(e)
        faces = set(mesh.edge_faces(e))
        if {a, b} <= seam and len(faces) == 2 and not faces & touched:
            touched |= faces
            mesh.dissolve_edges([e], cleanup=False)
    sym = symmetry_info(mesh)
    ngons = [f for f in mesh.all_face_ids() if len(mesh.face_vertices(f)) > 4]
    splits, stats = split_ngons(mesh, ngons, triangulate_face, sym)
    assert stats == {"split": 36, "mirrored": 36, "asymmetric": 0}
    on_plane = SymmetryInfo(sym.pairs, tuple({v for f in ngons for v in mesh.face_vertices(f)
                                              if mesh.vertex_position(v)[0] == 0.0} | set(sym.seam)), sym.mirror)
    for f in ngons:
        assert sorted(len(p) for p in splits[f]) == [4, 4] and _is_own_mirror(splits[f], on_plane)


# -- P3: UVs, texture, morph targets ------------------------------------------------------------------------------------


def test_uv_block_round_trip_and_zbrushs_e3_files():
    points = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
    uvs = [[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)], [(0.0, 0.0), (1.0, 1.0), (0.0, 1.0)]]
    goz = parse_goz(encode_goz("uv", points, [(0, 1, 2, 3), (0, 2, 3)], uvs=uvs))
    assert goz.uvs == (tuple(uvs[0]), tuple(uvs[1]))  # a triangle reads its three pairs
    with pytest.raises(ValueError, match="one \\(u, v\\) per corner"):
        encode_goz("uv", points, [(0, 1, 2, 3)], uvs=[uvs[1]])
    sent = parse_goz(fixture("zb2022_E3_head_uvs_as_sent.GoZ"))
    assert len(sent.uvs) == 324 and sent.texture_path is None
    painted = parse_goz(fixture("zb2022_E3_head_uvmaster_texture.GoZ"))
    assert painted.texture_path.endswith("E1_C_P1_UV1_TXTR.tif")


def _head_uvs_as_bridge(mesh):
    return [[tuple(as_float32(c) for c in mesh.corner_uv(f, v)) for v in mesh.face_vertices(f)]
            for f in mesh.all_face_ids()]


def test_send_carries_the_uvs_zbrush_keeps_them_and_uv_master_is_a_uv_change():
    """E3 (2026-11-06): the UV4 block ZBrush returns equals what Mirai sent (OBJ `vt` convention, no flip); after UV
    Master every face has new UVs - the plan writes them, no point moved."""
    scene, obj = one_object_scene(head_mesh())
    data, manifest = build_send(scene, obj, identifier="P/Kopf", transfer_id="t", session_id="s1", scene_path=None,
                                to_world=identity, triangulate=triangulate_face)
    assert [list(map(tuple, f)) for f in parse_goz(data).uvs] == _head_uvs_as_bridge(obj.mesh)
    same = plan_for(scene, obj, fixture("zb2022_E3_head_uvs_as_sent.GoZ"), manifest=manifest)
    assert same.kind is ReturnKind.UNCHANGED and same.uvs == {}
    unwrapped = parse_goz(fixture("zb2022_E3_head_uvmaster.GoZ"))
    plan = plan_for(scene, obj, fixture("zb2022_E3_head_uvmaster.GoZ"), manifest=manifest)
    assert plan.kind is ReturnKind.IN_PLACE and plan.positions == {} and len(plan.uvs) == 324
    assert plan.reason == "no point moved, UVs changed" and "UVs: 324 faces changed" in plan.summary()
    first = obj.mesh.all_face_ids()[0]
    assert plan.uvs[first] == tuple(unwrapped.uvs[0])


def test_a_mirai_uv_edit_since_the_send_is_a_conflict():
    scene, obj = one_object_scene(head_mesh())
    mesh = obj.mesh
    f = mesh.all_face_ids()[0]
    plan = plan_for(scene, obj, fixture("zb2022_E3_head_uvmaster.GoZ"),
                    edit=lambda: mesh.set_face_uvs(f, [(0.5, 0.5)] * len(mesh.face_vertices(f))))
    assert plan.kind is ReturnKind.CONFLICT and "UVs" in plan.reason


def test_uvs_back_onto_an_unmapped_mesh_and_ngon_pieces():
    """No UVs sent (an unmapped mesh) -> ZBrush's UVs are new for every face; an n-gon takes its corners' UVs from
    its pieces."""
    mesh = Mesh()
    ids = [mesh.add_vertex((x, y, 0.0)) for x, y in [(0, 0), (2, 0), (3, 1), (2, 2), (0, 2), (-1, 1)]]
    ngon = mesh.add_face(ids)
    scene, obj = one_object_scene(mesh)
    data, manifest = build_send(scene, obj, identifier="P/Kopf", transfer_id="t", session_id="s1", scene_path=None,
                                to_world=identity, triangulate=triangulate_face)
    assert manifest.sent_uvs is None and parse_goz(data).uvs is None
    sent = parse_goz(data)
    uv_of = {k: (0.1 * k, 0.05 * k) for k in range(6)}
    returned = encode_goz(sent.name, sent.points, sent.faces, sent.groups, [[uv_of[k] for k in f] for f in sent.faces])
    plan = plan_for(scene, obj, returned, manifest=manifest)
    assert plan.uvs == {ngon: tuple(tuple(as_float32(c) for c in uv_of[k]) for k in range(6))}
    assert "UVs: 1 face new" in plan.summary()


def bump(mesh) -> dict:
    """E3's bump target (`experiments/goz_probe/make_meshes.bump_offsets`, restated): around the point with the largest
    z, +z offset 0.15 x extent x w^2, w = 1 - distance / (0.3 x extent)."""
    vids = mesh.all_vertex_ids()
    pos = [mesh.vertex_position(v) for v in vids]
    extent = max(max(p[c] for p in pos) - min(p[c] for p in pos) for c in range(3))
    tip = max(pos, key=lambda p: (p[2], p[1], p[0]))
    out = {}
    for v, p in zip(vids, pos):
        w = max(0.0, 1.0 - sum((a - b) ** 2 for a, b in zip(p, tip)) ** 0.5 / (0.3 * extent))
        out[v] = (0.0, 0.0, 0.15 * extent * w * w)
    return out


def head_with_bump_target():
    from core import PointLayerInfo

    scene, obj = one_object_scene(head_mesh())
    mesh = obj.mesh
    lid = mesh.add_point_layer(PointLayerInfo("Bump"))
    for v, d in bump(mesh).items():
        mesh.set_layer_value(lid, v, d)
    return scene, obj, lid


def test_a_target_is_sent_as_b_plus_d_and_zbrushs_e3_copy_is_bit_identical():
    scene, obj, lid = head_with_bump_target()
    data, manifest = build_send(scene, obj, identifier="P/Kopf_Bump", transfer_id="t", session_id="s1",
                                scene_path=None, to_world=identity, triangulate=triangulate_face, layer=lid)
    assert manifest.representation == f"target:{int(lid)}" and parse_goz(data).name == "Kopf_Bump"
    assert parse_goz(data).points == parse_goz(fixture("zb2022_E3_head_bump_target.GoZ")).points
    plan = plan_for(scene, obj, fixture("zb2022_E3_head_bump_target.GoZ"), manifest=manifest)
    assert plan.kind is ReturnKind.UNCHANGED and plan.target_layer == lid


def test_a_sculpted_target_return_writes_offsets_into_that_layer_only():
    scene, obj, lid = head_with_bump_target()
    mesh = obj.mesh
    _data, manifest = build_send(scene, obj, identifier="P/Kopf_Bump", transfer_id="t", session_id="s1",
                                 scene_path=None, to_world=identity, triangulate=triangulate_face, layer=lid)
    goz = parse_goz(fixture("zb2022_E3_head_bump_target.GoZ"))
    pts = list(goz.points)
    pts[7] = (pts[7][0] + 0.25, pts[7][1], pts[7][2])
    plan = plan_for(scene, obj, encode_goz(goz.name, pts, goz.faces), manifest=manifest)
    v7 = mesh.all_vertex_ids()[7]
    assert plan.kind is ReturnKind.IN_PLACE and plan.positions == {} and set(plan.layer_offsets) == {v7}
    b = mesh.vertex_position(v7)
    assert plan.layer_offsets[v7] == tuple(as_float32(p) - q for p, q in zip(from_goz(pts[7]), b))
    assert "1 of 326 points of target 'Bump' moved" in plan.summary() and "Bump" in plan.label


def _tiff(width, height, rows):
    """An uncompressed RGB TIFF in ZBrush 2022.0.8's layout (E3: II, one strip, rows in file order)."""
    entries = [(256, 3, 1, width), (257, 3, 1, height), (258, 3, 1, 8), (259, 3, 1, 1), (262, 3, 1, 2),
               (273, 4, 1, 0), (277, 3, 1, 3), (278, 3, 1, height), (279, 4, 1, 3 * width * height), (284, 3, 1, 1)]
    ifd = 8
    start = ifd + 2 + 12 * len(entries) + 4
    out = b"II*\0" + struct.pack("<I", ifd) + struct.pack("<H", len(entries))
    for tag, typ, n, value in entries:
        value = start if tag == 273 else value
        out += struct.pack("<HHI", tag, typ, n) + (struct.pack("<HH", value, 0) if typ == 3 else struct.pack("<I", value))
    return out + b"\0\0\0\0" + b"".join(rows)


def test_texture_copy_flips_zbrushs_bottom_up_tiff_into_a_png(tmp_path):
    import zlib

    from interop.goz.texture import copy_texture, texture_dir

    rows = [bytes([10 * y, 0, 0]) * 3 for y in range(2)]  # file row 0 = v 0 (bottom) in ZBrush's file
    source = tmp_path / "Kopf_TXTR.tif"
    source.write_bytes(_tiff(3, 2, rows))
    folder = texture_dir(tmp_path / "kopf.mirai.json", tmp_path / "fallback")
    assert folder == tmp_path / "kopf_textures" and texture_dir(None, tmp_path / "fb") == tmp_path / "fb"
    copy, note = copy_texture(source, folder, "Kopf")
    assert note is None and copy.suffix == ".png" and copy.parent == folder
    png = copy.read_bytes()
    raw = zlib.decompress(png[png.index(b"IDAT") + 4: png.index(b"IEND") - 8])
    assert raw == b"\0" + rows[1] + b"\0" + rows[0]  # top row of the PNG = the TIFF's last row
    assert copy_texture(source, folder, "Kopf")[0] == copy  # same content, same copy
    odd = tmp_path / "Kopf_TXTR.bmp"
    odd.write_bytes(b"BM" + b"\0" * 20)
    other, note = copy_texture(odd, folder, "Kopf")
    assert other.suffix == ".bmp" and "upside down" in note


# -- Mirai's own SubTool names (interop.goz.names, AD-029 §3; Manu 2026-11-06) -----------------------------------------


def _registry(tmp_path):
    from interop.goz.names import NameRegistry

    return NameRegistry(tmp_path / "names.json", clock=iter(range(1000)).__next__)


def _take(reg, title="Head", *, scene=None, session="s1", obj=1, layer=None, files=(), legacy=None):
    return reg.allocate(title, scene=scene, session=session, object_id=obj, layer=layer,
                        foreign_file=lambda stem: stem in files, legacy=legacy or (lambda stem: None)).stem


def test_names_are_readable_stable_and_unique_per_object_and_target(tmp_path):
    reg = _registry(tmp_path)
    assert _take(reg) == "Head" and _take(reg) == "Head"  # a resend: the same name
    assert _take(reg, "Head_Target_4", layer=7) == "Head_Target_4"  # a target: object + its own name, no count
    assert _take(reg, obj=2) == "Head_2" and _take(reg, "HEAD", obj=3) == "HEAD_3"  # Windows: case-insensitive
    assert _take(reg, "x" * 40, obj=4) == "x" * 40 and _take(reg, "x" * 40, obj=5) == "x" * 38 + "_2"
    reg.save()
    again = _registry(tmp_path)
    assert _take(again, obj=2) == "Head_2" and _take(again, "Head_Target_4", layer=7) == "Head_Target_4"


def test_a_name_is_never_taken_from_a_foreign_file_or_another_scene(tmp_path):
    reg = _registry(tmp_path)
    assert _take(reg, files={"Head"}) == "Head_2"  # a .GoZ Mirai did not write
    assert _take(reg, "Body", scene="a.json", obj=2) == "Body"
    assert _take(reg, "Body", scene="b.json", session="s2", obj=2) == "Body_2"  # another scene file keeps its own
    assert _take(reg, "Body", scene="a.json", session="s3", obj=2) == "Body"  # the same file after a restart
    assert _take(reg, "Arm", session="s1", obj=8) == "Arm"
    assert _take(reg, "Arm", session="s1", obj=9) == "Arm_2"  # another object of the same (unsaved) session
    assert _take(reg, "Arm", session="s4", obj=9) == "Arm"  # an unsaved scene after a restart takes its name over


def test_a_saved_scene_keeps_its_name_from_the_unsaved_send_and_follows_a_zbrush_rename(tmp_path):
    from interop.goz.names import NameEntry, stem_of, with_stem

    reg = _registry(tmp_path)
    assert _take(reg) == "Head"
    assert _take(reg, scene="kopf.json") == "Head"  # saved after the send, same session
    assert _take(reg, scene="kopf.json", session="s2") == "Head"  # ... and after a restart
    entry = reg.find("kopf.json", "s9", 1, None)
    reg.follow(entry, "Head1")
    assert _take(reg, scene="kopf.json", session="s3") == "Head1" and reg.owner("head").stem == "Head1"
    assert _take(reg, obj=2, session="s3") == "Head_2"  # the old name stays Mirai's (a return may still use it)
    legacy = NameEntry(stem="Old", title="Old", scene="k.json", session="s0", object_id=5, layer=None)
    assert _take(reg, "Old", scene="k.json", session="s5", obj=5, files={"Old"},
                 legacy=lambda stem: legacy if stem == "Old" else None) == "Old"
    assert stem_of("C:/P/Default/Head1") == "Head1" and with_stem("C:\\P\\Default\\Head", "Head1") == "C:\\P\\Default\\Head1"


def test_an_unreadable_name_registry_starts_empty(tmp_path):
    (tmp_path / "names.json").write_text("{not json", encoding="utf-8")
    reg = _registry(tmp_path)
    assert reg.entries == [] and _take(reg) == "Head"


def test_a_name_of_a_gone_target_is_free_again(tmp_path):
    reg = _registry(tmp_path)
    assert _take(reg, "Cube_Target_1", scene="c.json", layer=3) == "Cube_Target_1"
    gone = {3}
    dead = (lambda e: e.layer in gone)
    assert reg.allocate("Cube_Target_1", scene="c.json", session="s1", object_id=1, layer=8,
                        foreign_file=lambda stem: False, dead=dead).stem == "Cube_Target_1"
    assert _take(reg, "Cube_Target_1", scene="c.json", session="s2", layer=8) == "Cube_Target_1"  # it stays
