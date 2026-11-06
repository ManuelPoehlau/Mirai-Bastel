"""AD-029 P1 on the app path: `src/zbrush_bridge.py` + `Application.apply_goz_return`, with a fake GoZ root, fake
ZBrush utilities and the ZBrush 2022.0.8 captures of `tests/fixtures/goz/` as returns (acceptance A1-A8, audit §8.2).
Headless."""

from __future__ import annotations

import copy
import itertools
import json
from pathlib import Path

import pytest

import tests._bootstrap  # noqa: F401
from tests._bootstrap import _REPO_ROOT
from tests.test_goz_format import BANDS, E2_REGROUPED, E2_UNCHANGED, band_regions, e2, fixture, flipped

from core import PointLayerInfo, SelectionMode
from core.serialization import scene_to_dict
from interop.goz import helper
from interop.goz import install as goz_install
from interop.goz.transfer import manifest_path
from interop.goz.bridge import ReturnKind
from interop.goz.files import GozPaths, write_goz_list
from interop.goz.format import as_float32, encode_goz, parse_goz
from interop.goz.manifest import Manifest
from mirai.application import Application
from mirai.interaction import commands
from viewport.gl_symmetry_overlay import GLSymmetryOverlay
from viewport.resource_store import TraceStore
from zbrush_bridge import (
    APPLY_PREFIX,
    DROP_PREFIX,
    INSTALL_LABEL,
    NEW_OBJECT_PREFIX,
    SEND_LABEL,
    ZBrushBridge,
)

HEAD = _REPO_ROOT / "examples" / "meshes" / "head_basemesh.obj"


class FakeProc:
    def __init__(self, code):
        self.code = code

    def poll(self):
        return self.code


class FakeZBrush:
    """Stands in for `GoZMakeObjectPath.exe` (writes the identifier back) and `GoZBrushFromApp.exe` (records)."""

    def __init__(self, paths: GozPaths):
        self.paths = paths
        self.commands: list[list[str]] = []

    def __call__(self, command, cwd):
        self.commands.append(list(command))
        if Path(command[0]).stem == "GoZMakeObjectPath":
            short = self.paths.object_path_file.read_text().strip()
            self.paths.object_path_file.write_text(str(self.paths.project_dir() / (short + "1")))
            return FakeProc(0)
        return FakeProc(None)

    def press_goz(self, identifier: str, data: bytes, inbox: Path):
        """The artist presses GoZ: ZBrush writes the file and the list, then runs Edit.bat (= the helper)."""
        Path(identifier + ".GoZ").write_bytes(data)
        write_goz_list(self.paths.object_list, [identifier])
        helper.run(self.paths, inbox, settle=0.0)


@pytest.fixture
def env(tmp_path):
    root = tmp_path / "Pixologic"
    for sub in ("GoZBrush", "GoZProjects/Default"):
        (root / sub).mkdir(parents=True)
    paths = GozPaths(root)
    for exe in ("GoZMakeObjectPath", "GoZBrushFromApp"):
        paths.utility(exe).write_bytes(b"")
    app = Application()
    app.init_scene("obj", obj_path=HEAD, store_type=TraceStore, symmetry_overlay_type=GLSymmetryOverlay)
    zb = FakeZBrush(paths)
    scene_file = {"path": None}
    bridge = ZBrushBridge(app, root=root, inbox=tmp_path / "inbox", runner=zb, clock=itertools.count().__next__,
                          scene_path=lambda: scene_file["path"], manifests=tmp_path / "manifests",
                          textures=tmp_path / "textures")
    return {"app": app, "bridge": bridge, "zb": zb, "paths": paths, "inbox": tmp_path / "inbox", "tmp": tmp_path,
            "scene_file": scene_file}


def zbrush_knows_mirai(env) -> None:
    """Registered, ZBrush restarted, Mirai picked with R: ZBrush wrote GoZApps\\Mirai\\GoZ_Config.txt."""
    paths = env["paths"]
    if not goz_install.is_installed(paths):
        goz_install.install(paths, env["inbox"])
    (paths.app_dir / "GoZ_Config.txt").write_text('PATH = "C:/Mirai.cmd"\r\n')


def send(env) -> str:
    """Sends the object; returns the base's identifier (P3c: its morph targets follow in the same list)."""
    zbrush_knows_mirai(env)
    assert env["bridge"].activate(SEND_LABEL), env["app"].status_message
    return env["paths"].read_object_list()[0]


def goz_back(env, identifier, data):
    env["zb"].press_goz(identifier, data, env["inbox"])
    return env["bridge"].tick()


def row(env, prefix):
    rows = [r for r in env["bridge"].entries() if r.startswith(prefix)]
    assert len(rows) == 1, env["bridge"].entries()
    return rows[0]


def positions(mesh):
    return {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()}


def test_send_writes_file_manifest_list_and_starts_zbrush_without_tmap(env):
    app, paths = env["app"], env["paths"]
    identifier = send(env)
    assert identifier == str(paths.project_dir() / "head_basemesh1")
    goz = parse_goz(Path(identifier + ".GoZ").read_bytes())
    mesh = app.scene.edit_object.mesh
    first = mesh.vertex_position(mesh.all_vertex_ids()[0])
    assert goz.points[0] == (as_float32(first[0]), as_float32(-first[1]), as_float32(-first[2]))
    manifest = Manifest.from_json(manifest_path(env["bridge"].manifest_dir, identifier).read_text())
    assert sorted(p.name for p in paths.project_dir().iterdir()) == ["head_basemesh1.GoZ"]  # nothing else of Mirai's
    assert manifest.object_id == int(app.scene.edit_object.id) and manifest.session_id == env["bridge"].session_id
    assert paths.application_file.read_text() == "Mirai"
    assert [Path(c[0]).stem for c in env["zb"].commands] == ["GoZMakeObjectPath", "GoZBrushFromApp"]
    assert all("-tmap" not in c for c in env["zb"].commands)
    assert len(app.history) == 0 and "sent (326 points; UVs)" in app.status_message
    assert send(env) == identifier  # a resend reuses the identifier: ZBrush updates the same Tool
    assert [Path(c[0]).stem for c in env["zb"].commands].count("GoZMakeObjectPath") == 1


def test_move_brush_return_waits_for_confirm_then_is_one_exact_undo_step(env):
    """A1-A4 on the head: only moved points change (bit-exact elsewhere), IDs / faces / UVs / layers / other objects
    unchanged, one History entry, Undo exact, Redo re-applies."""
    app = env["app"]
    other = app.add_primitive("cube")
    app._objects.set_edit_object(app.scene.objects[next(iter(app.scene.objects))].id)
    app.selection.mode = SelectionMode.VERTEX  # leave mode 4: the edit object is sent
    obj = app.scene.edit_object
    mesh = obj.mesh
    lid = mesh.add_point_layer(PointLayerInfo("Smile"))
    some = mesh.all_vertex_ids()[3]
    mesh.set_layer_value(lid, some, (0.1, 0.0, 0.0))
    identifier = send(env)
    before = positions(mesh)
    before_scene = scene_to_dict(app.scene)
    history = len(app.history)
    assert goz_back(env, identifier, flipped(fixture("zb2022_C_move_brush.GoZ"))) == 1
    assert positions(mesh) == before and len(app.history) == history  # D1: nothing before the confirm
    label = row(env, APPLY_PREFIX)
    assert "101 of 326 points moved" in app.status_message and "1 morph target follow" in app.status_message
    assert env["bridge"].activate(label), app.status_message
    after = positions(mesh)
    raw = parse_goz(fixture("zb2022_C_move_brush.GoZ")).points
    moved = [v for v in after if after[v] != before[v]]
    assert len(moved) == 101 and len(app.history) == history + 1
    for i, v in enumerate(mesh.all_vertex_ids()):
        assert after[v] == (raw[i] if v in moved else before[v])
    after_scene = scene_to_dict(app.scene)
    for state in (before_scene, after_scene):
        for o in state["objects"]:
            o["mesh"] = {k: val for k, val in o["mesh"].items() if k != "vertices"}
    assert after_scene == before_scene  # A2/A4: everything but the positions
    assert mesh.layer_items(lid) == [(some, (0.1, 0.0, 0.0))]
    assert other.mesh.all_vertex_ids() and not any(r.startswith(APPLY_PREFIX) for r in env["bridge"].entries())
    app._undo_redo(commands.UNDO)
    assert positions(mesh) == before
    app._undo_redo(commands.REDO)
    assert positions(mesh) == after


def test_further_sculpting_without_a_resend_is_planned_against_the_applied_state(env):
    app = env["app"]
    identifier = send(env)
    goz_back(env, identifier, flipped(fixture("zb2022_C_move_brush.GoZ")))
    assert env["bridge"].activate(row(env, APPLY_PREFIX))
    goz = parse_goz(flipped(fixture("zb2022_C_move_brush.GoZ")))
    more = list(goz.points)
    more[0] = (more[0][0] + 0.25, more[0][1], more[0][2])
    goz_back(env, identifier, encode_goz(goz.name, more, goz.faces))
    assert "1 of 326 points moved" in app.status_message, app.status_message
    assert env["bridge"].activate(row(env, APPLY_PREFIX))


def test_unchanged_and_divided_returns_change_nothing(env):
    app = env["app"]
    mesh = app.scene.edit_object.mesh
    identifier = send(env)
    before = positions(mesh)
    goz_back(env, identifier, flipped(fixture("zb2022_C_unchanged.GoZ")))
    assert "no point moved" in app.status_message
    goz_back(env, identifier, flipped(fixture("zb2022_C_divided_once.GoZ")))
    assert "looks divided in ZBrush" in app.status_message and "held" in app.status_message
    assert env["bridge"].entries() == (SEND_LABEL,)
    assert positions(mesh) == before and len(app.history) == 0


def test_mirai_edit_since_send_is_a_conflict_new_object_only(env):
    """A8 + D3 proposal: the original stays as edited in Mirai; the return can only become a new object."""
    app = env["app"]
    obj = app.scene.edit_object
    identifier = send(env)
    vid = obj.mesh.all_vertex_ids()[0]
    app.apply_mesh_change("nudge", lambda: obj.mesh.set_vertex_position(vid, (9.0, 9.0, 9.0)) or {vid})
    edited = positions(obj.mesh)
    goz_back(env, identifier, flipped(fixture("zb2022_C_move_brush.GoZ")))
    assert "changed in Mirai since the send (point positions)" in app.status_message
    count = len(app.scene.objects)
    assert env["bridge"].activate(row(env, NEW_OBJECT_PREFIX))
    assert len(app.scene.objects) == count + 1 and positions(obj.mesh) == edited
    new = list(app.scene.objects.values())[-1]
    assert new.name == "head_basemesh ZBrush" and len(new.mesh.all_vertex_ids()) == 326


def test_topology_change_never_touches_the_original(env):
    """A5: ZBrush returns other topology -> only a new object; the original's IDs and positions stay."""
    app = env["app"]
    obj = app.scene.edit_object
    identifier = send(env)
    before = positions(obj.mesh)
    goz = parse_goz(flipped(fixture("zb2022_C_unchanged.GoZ")))
    goz_back(env, identifier, encode_goz(goz.name, goz.points, goz.faces[:-2]))
    assert "topology changed in ZBrush" in app.status_message
    assert env["bridge"].activate(row(env, NEW_OBJECT_PREFIX))
    assert positions(obj.mesh) == before and len(list(app.scene.objects.values())[-1].mesh.all_face_ids()) == 322


def test_corrupt_transfer_changes_nothing(env):
    """A6: a truncated file -> 'transfer incomplete' in the status line, no row, nothing changed."""
    app = env["app"]
    identifier = send(env)
    before = positions(app.scene.edit_object.mesh)
    Path(identifier + ".GoZ").write_bytes(fixture("zb2022_C_move_brush.GoZ")[:500])
    write_goz_list(env["paths"].object_list, [identifier])
    helper.run(env["paths"], env["inbox"], settle=0.0, deadline=0.0)
    env["bridge"].tick()
    assert "transfer incomplete" in app.status_message
    assert env["bridge"].entries() == (SEND_LABEL,)
    assert positions(app.scene.edit_object.mesh) == before


def test_refusals_keep_the_return_waiting(env, monkeypatch):
    """A7: during an interaction, while posed, or when the object is not the edit object: nothing changes, the row
    stays for a retry."""
    app = env["app"]
    mesh = app.scene.edit_object.mesh
    identifier = send(env)
    goz_back(env, identifier, flipped(fixture("zb2022_C_move_brush.GoZ")))
    label = row(env, APPLY_PREFIX)
    before = positions(mesh)
    monkeypatch.setattr(app._skeleton, "posed_text", lambda key: f"{key}: the mesh is posed (6 = rest pose)")
    assert not env["bridge"].activate(label) and "posed" in app.status_message
    monkeypatch.undo()
    monkeypatch.setattr(Application, "interaction_owner", property(lambda self: "knife"))
    assert not env["bridge"].activate(label) and "knife" in app.status_message
    monkeypatch.undo()
    head = app.scene.edit_object
    cube = app.add_primitive("cube")
    app._objects.set_edit_object(cube.id)
    assert not env["bridge"].activate(label) and "make it the edit object" in app.status_message
    app._objects.set_edit_object(head.id)
    app.selection.mode = SelectionMode.VERTEX
    assert positions(mesh) == before and len(app.history) == 1  # only the cube's Add
    assert env["bridge"].activate(row(env, APPLY_PREFIX))


def test_a_scene_edit_between_arrival_and_confirm_shows_the_new_verdict(env):
    app = env["app"]
    obj = app.scene.edit_object
    identifier = send(env)
    goz_back(env, identifier, flipped(fixture("zb2022_C_move_brush.GoZ")))
    label = row(env, APPLY_PREFIX)
    vid = obj.mesh.all_vertex_ids()[0]
    app.apply_mesh_change("nudge", lambda: obj.mesh.set_vertex_position(vid, (9.0, 9.0, 9.0)) or {vid})
    edited = positions(obj.mesh)
    assert not env["bridge"].activate(label)
    assert "changed since it arrived, nothing applied" in app.status_message and positions(obj.mesh) == edited
    assert row(env, NEW_OBJECT_PREFIX)


def test_drop_forgets_and_a_newer_goz_supersedes(env):
    identifier = send(env)
    goz_back(env, identifier, flipped(fixture("zb2022_C_move_brush.GoZ")))
    goz_back(env, identifier, flipped(fixture("zb2022_C_move_brush.GoZ")))
    assert len(env["bridge"].waiting) == 1
    assert env["bridge"].activate(row(env, DROP_PREFIX)) and env["bridge"].waiting == []


def test_ticket_waits_for_a_later_mirai_and_the_scene_file_links_it(env):
    """D11: the ticket waits; a new Mirai session finds the manifest on disk. Same scene file -> in place; no
    scene file -> only a new object."""
    app = env["app"]
    env["scene_file"]["path"] = env["tmp"] / "kopf.mirai.json"
    identifier = send(env)
    env["zb"].press_goz(identifier, flipped(fixture("zb2022_C_move_brush.GoZ")), env["inbox"])
    later = ZBrushBridge(app, root=env["paths"].root, inbox=env["inbox"], clock=itertools.count().__next__,
                         scene_path=lambda: env["tmp"] / "kopf.mirai.json", manifests=env["bridge"].manifest_dir)
    assert later.tick() == 1 and any(r.startswith(APPLY_PREFIX) for r in later.entries())
    env["zb"].press_goz(identifier, flipped(fixture("zb2022_C_move_brush.GoZ")), env["inbox"])
    stranger = ZBrushBridge(app, root=env["paths"].root, inbox=env["inbox"], clock=itertools.count().__next__,
                            manifests=env["bridge"].manifest_dir)
    assert stranger.tick() == 1 and "another Mirai session" in app.status_message
    assert any(r.startswith(NEW_OBJECT_PREFIX) for r in stranger.entries())


def test_a_foreign_subtool_is_offered_as_a_new_object(env):
    app = env["app"]
    goz_back(env, str(env["paths"].project_dir() / "A"), fixture("zb2022_A_obj_import.GoZ"))
    assert "not sent from Mirai" in app.status_message
    assert env["bridge"].activate(row(env, NEW_OBJECT_PREFIX))
    assert list(app.scene.objects.values())[-1].name == "A ZBrush"


def test_install_row_registers_mirai_once(env):
    app = env["app"]
    assert env["bridge"].activate(INSTALL_LABEL), app.status_message
    assert (env["paths"].root / "GoZApps" / "Mirai" / "Edit.bat").is_file() and "restart ZBrush" in app.status_message
    assert INSTALL_LABEL not in env["bridge"].entries()


def test_send_refusals(env, monkeypatch):
    app = env["app"]
    monkeypatch.setattr(Application, "interaction_owner", property(lambda self: "knife"))
    assert not env["bridge"].activate(SEND_LABEL) and "knife" in app.status_message
    monkeypatch.undo()
    bridge = ZBrushBridge(app, root=env["tmp"] / "nowhere", inbox=env["inbox"], manifests=env["tmp"] / "m")
    assert not bridge.activate(SEND_LABEL) and "missing" in app.status_message
    assert bridge.entries() == (SEND_LABEL,)


def test_a_failing_plan_or_apply_is_a_status_line_not_a_crash(env, monkeypatch):
    import zbrush_bridge

    app = env["app"]
    identifier = send(env)
    monkeypatch.setattr(zbrush_bridge, "plan_return", lambda *a, **k: 1 / 0)
    assert goz_back(env, identifier, flipped(fixture("zb2022_C_move_brush.GoZ"))) == 1
    assert "return failed: ZeroDivisionError" in app.status_message
    monkeypatch.undo()
    goz_back(env, identifier, flipped(fixture("zb2022_C_move_brush.GoZ")))
    monkeypatch.setattr(Application, "apply_goz_return", lambda self, plan: 1 / 0)
    assert not env["bridge"].activate(row(env, APPLY_PREFIX)) and "failed: ZeroDivisionError" in app.status_message


def test_no_send_until_zbrush_knows_mirai(env):
    """ZBrush 2022.0.8 crashed when a send named `Mirai` as the GoZ app while GoZApps\\Mirai did not exist (Manu,
    2026-11-05). Not registered, or registered but not yet picked in ZBrush: nothing is written, nothing started."""
    app, paths = env["app"], env["paths"]
    paths.application_file.write_text("MiraiProbe")
    assert not env["bridge"].activate(SEND_LABEL) and "register Mirai first" in app.status_message
    assert env["bridge"].activate(INSTALL_LABEL)
    assert not env["bridge"].activate(SEND_LABEL) and "does not know Mirai yet" in app.status_message
    assert env["zb"].commands == [] and list(paths.project_dir().iterdir()) == []
    assert paths.application_file.read_text() == "MiraiProbe" and not paths.object_list.exists()
    (paths.app_dir / "GoZ_Config.txt").write_text('PATH = "C:/Mirai.cmd"\r\n')  # ZBrush: restarted, R > Mirai
    assert env["bridge"].activate(SEND_LABEL) and paths.application_file.read_text() == "Mirai"


def _unpaired(mesh) -> int:
    from mirai.symmetry import CorrespondenceState, vertex_correspondence

    return sum(1 for c in vertex_correspondence(mesh).values() if c.state is CorrespondenceState.UNPAIRED)


def _sym_x(env):
    from mirai.symmetry_axis import set_symmetry_axis

    mesh = env["app"].scene.edit_object.mesh
    set_symmetry_axis(mesh, "X")
    assert _unpaired(mesh) == 0
    return mesh


def test_zbrush_smooth_asymmetry_is_made_exact_while_mirai_symmetry_is_on(env):
    """Manu 2026-11-05: ZBrush's Smooth with X symmetry breaks 76 of 145 pairs by up to 0.0102 (0.2 %); with Mirai's
    symmetry on the return comes back exactly symmetric, in the same Undo step."""
    app = env["app"]
    mesh = _sym_x(env)
    identifier = send(env)
    goz_back(env, identifier, fixture("zb2022_P1_head_move_symx.GoZ"))
    assert "symmetry made exact" not in app.status_message  # Move with symmetry is bit-exact already
    assert env["bridge"].activate(row(env, APPLY_PREFIX)) and _unpaired(mesh) == 0
    history = len(app.history)
    goz_back(env, identifier, fixture("zb2022_P1_head_smooth_symx.GoZ"))
    assert "symmetry made exact: 76 mirror pairs, 13 seam points" in app.status_message, app.status_message
    before = positions(mesh)
    assert env["bridge"].activate(row(env, APPLY_PREFIX))
    assert _unpaired(mesh) == 0 and len(app.history) == history + 1
    smooth = parse_goz(fixture("zb2022_P1_head_smooth_symx.GoZ")).points
    vids = mesh.all_vertex_ids()
    worst = max(max(abs(a - b) for a, b in zip(mesh.vertex_position(v), (p[0], -p[1], -p[2])))
                for v, p in zip(vids, smooth))
    assert 0 < worst <= 0.0102 / 2 + 1e-9  # each side moves by half the gap at most
    app._undo_redo(commands.UNDO)
    assert positions(mesh) == before
    app._undo_redo(commands.REDO)
    goz_back(env, identifier, fixture("zb2022_P1_head_smooth_symx.GoZ"))  # the same ZBrush state again
    assert "no point moved" in app.status_message  # the mirrored means are kept, not re-read as moves


def test_without_mirai_symmetry_the_return_is_taken_as_zbrush_sends_it(env):
    app = env["app"]
    from mirai.symmetry_axis import set_symmetry_axis

    mesh = _sym_x(env)
    set_symmetry_axis(mesh, None)
    identifier = send(env)
    goz_back(env, identifier, fixture("zb2022_P1_head_smooth_symx.GoZ"))
    assert "symmetry made exact" not in app.status_message
    assert env["bridge"].activate(row(env, APPLY_PREFIX))
    smooth = parse_goz(fixture("zb2022_P1_head_smooth_symx.GoZ")).points
    vids = mesh.all_vertex_ids()
    moved = [v for v, p in zip(vids, smooth) if tuple(as_float32(c) for c in mesh.vertex_position(v)) != tuple(as_float32(c) for c in (p[0], -p[1], -p[2]))]
    assert moved == []  # every point exactly ZBrush's value (or untouched)


def test_asymmetry_beyond_one_percent_stays_and_is_reported(env):
    app = env["app"]
    mesh = _sym_x(env)
    identifier = send(env)
    goz = parse_goz(fixture("zb2022_P1_head_smooth_symx.GoZ"))
    pts = list(goz.points)
    vids = mesh.all_vertex_ids()
    off_plane = next(i for i, v in enumerate(vids) if mesh.vertex_position(v)[0] > 1.0)
    pts[off_plane] = (pts[off_plane][0] + 0.2, pts[off_plane][1], pts[off_plane][2])  # 0.2 > 1 % of 5.2
    goz_back(env, identifier, encode_goz(goz.name, pts, goz.faces))
    assert "1 pairs / 0 seam points stay asymmetric" in app.status_message, app.status_message
    assert env["bridge"].activate(row(env, APPLY_PREFIX))
    assert _unpaired(mesh) == 2
    assert mesh.vertex_position(vids[off_plane])[0] == as_float32(pts[off_plane][0])


def test_more_sculpting_after_a_mirrored_apply_needs_no_resend(env):
    """Manu 2026-11-05 asked whether a resend is needed after the symmetry fix changed Mirai's mesh: no - the next GoZ
    of the same SubTool is planned against the applied state (no conflict) and stays symmetric."""
    app = env["app"]
    mesh = _sym_x(env)
    identifier = send(env)
    goz_back(env, identifier, fixture("zb2022_P1_head_move_symx.GoZ"))
    assert env["bridge"].activate(row(env, APPLY_PREFIX))
    goz_back(env, identifier, fixture("zb2022_P1_head_smooth_symx.GoZ"))
    assert env["bridge"].activate(row(env, APPLY_PREFIX))
    goz = parse_goz(fixture("zb2022_P1_head_smooth_symx.GoZ"))  # ZBrush still holds its own, unmirrored state
    pts = list(goz.points)
    for i in range(0, 40):
        pts[i] = (pts[i][0], pts[i][1] + 0.01, pts[i][2])  # more sculpting in ZBrush (one side, then mirrored below)
    goz_back(env, identifier, encode_goz(goz.name, pts, goz.faces))
    assert "points moved" in app.status_message and "changed in Mirai" not in app.status_message, app.status_message
    assert env["bridge"].activate(row(env, APPLY_PREFIX))
    assert _unpaired(mesh) == 0


def test_a_return_after_undo_of_an_apply_links_without_a_resend(env):
    """Manu 2026-11-05: after Ctrl+Z of an apply the next GoZ was a conflict. Now it links to the manifest version the
    object is back at: ZBrush's state comes back as an ordinary return, no resend."""
    app = env["app"]
    mesh = app.scene.edit_object.mesh
    identifier = send(env)
    before = positions(mesh)
    goz_back(env, identifier, flipped(fixture("zb2022_C_move_brush.GoZ")))
    assert env["bridge"].activate(row(env, APPLY_PREFIX))
    after = positions(mesh)
    app._undo_redo(commands.UNDO)
    assert positions(mesh) == before
    goz_back(env, identifier, flipped(fixture("zb2022_C_move_brush.GoZ")))
    assert "101 of 326 points moved" in app.status_message, app.status_message
    assert env["bridge"].activate(row(env, APPLY_PREFIX)) and positions(mesh) == after
    goz_back(env, identifier, flipped(fixture("zb2022_C_move_brush.GoZ")))
    assert "no point moved" in app.status_message
    vid = mesh.all_vertex_ids()[0]
    app.apply_mesh_change("nudge", lambda: mesh.set_vertex_position(vid, (9.0, 9.0, 9.0)) or {vid})
    goz_back(env, identifier, flipped(fixture("zb2022_C_move_brush.GoZ")))
    assert "changed in Mirai since the send" in app.status_message  # a real Mirai edit is still a conflict


def test_after_adding_a_return_as_new_object_the_status_says_what_send_sends(env):
    app = env["app"]
    identifier = send(env)
    obj = app.scene.edit_object
    vid = obj.mesh.all_vertex_ids()[0]
    app.apply_mesh_change("nudge", lambda: obj.mesh.set_vertex_position(vid, (9.0, 9.0, 9.0)) or {vid})
    goz_back(env, identifier, flipped(fixture("zb2022_C_move_brush.GoZ")))
    assert env["bridge"].activate(row(env, NEW_OBJECT_PREFIX))
    assert "it is selected now" in app.status_message and "leave mode 4" in app.status_message


# -- polygroups (P2a) --------------------------------------------------------------------------------------------------


def _bands(env):
    mesh = env["app"].scene.edit_object.mesh
    mesh.face_regions = band_regions(mesh)
    return mesh


def test_regroup_and_sculpt_come_back_as_one_undo_step(env):
    """P2a (Manu 2026-11-05, "Mit übernehmen"): ZBrush's regroup (E2 capture) and a sculpt in the same return: one
    confirm, one History entry; Ctrl+Z restores regions and points together, Ctrl+Y both again."""
    app = env["app"]
    mesh = _bands(env)
    identifier = send(env)
    before, regions_before = positions(mesh), mesh.face_regions
    history = len(app.history)
    sculpt = parse_goz(flipped(fixture("zb2022_C_move_brush.GoZ"))).points
    goz_back(env, identifier, e2(E2_REGROUPED, points=sculpt))
    assert "101 of 326 points moved" in app.status_message and "groups: 1 changed, 1 new" in app.status_message
    assert mesh.face_regions is regions_before  # D1: nothing before the confirm
    assert env["bridge"].activate(row(env, APPLY_PREFIX)), app.status_message
    after, regions_after = positions(mesh), mesh.face_regions
    assert len(app.history) == history + 1 and after != before
    assert [r.name for r in regions_after.regions] == [*BANDS, "Group 1"]
    assert len(regions_after.get("Group 1").faces) == 12 and len(regions_after.get("Hals").faces) == 38
    app._undo_redo(commands.UNDO)
    assert positions(mesh) == before and mesh.face_regions == regions_before
    app._undo_redo(commands.REDO)
    assert positions(mesh) == after and mesh.face_regions == regions_after
    goz_back(env, identifier, e2(E2_REGROUPED, points=sculpt))  # the same ZBrush state again
    assert "no point moved, no group changed" in app.status_message, app.status_message


def test_a_groups_only_return_is_appliable_and_its_new_group_keeps_its_name(env):
    app = env["app"]
    mesh = _bands(env)
    identifier = send(env)
    before = positions(mesh)
    goz_back(env, identifier, e2(E2_REGROUPED))
    assert "no point moved, groups changed" in app.status_message
    assert env["bridge"].activate(row(env, APPLY_PREFIX)), app.status_message
    assert positions(mesh) == before and mesh.face_regions.get("Group 1") is not None
    goz = parse_goz(e2(E2_REGROUPED))
    groups = list(goz.groups)
    hals = [i for i, g in enumerate(groups) if g == 4][:3]
    for i in hals:
        groups[i] = 3225  # more faces painted with ZBrush's new group, no resend
    goz_back(env, identifier, encode_goz(goz.name, goz.points, goz.faces, groups))
    assert "groups: 2 changed, 0 new (3 faces regrouped)" in app.status_message, app.status_message
    assert env["bridge"].activate(row(env, APPLY_PREFIX))
    assert len(mesh.face_regions.get("Group 1").faces) == 15 and len(mesh.face_regions.regions) == 5


def test_a_mirai_group_edit_since_the_send_makes_the_return_a_new_object(env):
    app = env["app"]
    mesh = _bands(env)
    identifier = send(env)
    app.apply_mesh_change("regroup", lambda: setattr(mesh, "face_regions", band_regions(mesh, BANDS[:3])) or set())
    edited = mesh.face_regions
    goz_back(env, identifier, e2(E2_REGROUPED))
    assert "changed in Mirai since the send (groups)" in app.status_message, app.status_message
    assert row(env, NEW_OBJECT_PREFIX) and mesh.face_regions == edited


def test_undo_of_a_group_apply_links_the_next_return_without_a_resend(env):
    app = env["app"]
    mesh = _bands(env)
    identifier = send(env)
    goz_back(env, identifier, e2(E2_REGROUPED))
    assert env["bridge"].activate(row(env, APPLY_PREFIX))
    app._undo_redo(commands.UNDO)
    goz_back(env, identifier, e2(E2_REGROUPED))
    assert "groups: 1 changed, 1 new" in app.status_message, app.status_message
    assert env["bridge"].activate(row(env, APPLY_PREFIX)) and mesh.face_regions.get("Group 1") is not None


# -- n-gons (P2b) ------------------------------------------------------------------------------------------------------


def test_ngons_travel_split_and_stay_ngons_in_mirai(env):
    """P2b (Manu 2026-11-05): the send splits n-gons in the file only (quads); ZBrush's sculpt on the pieces comes back
    by point index, one Undo step, and Mirai's n-gons are still n-gons."""
    app = env["app"]
    mesh = app.scene.edit_object.mesh
    edges = []
    touched = set()
    for e in mesh.all_edge_ids():
        faces = set(mesh.edge_faces(e))
        if len(faces) == 2 and not faces & touched:
            edges.append(e)
            touched |= faces
            if len(edges) == 2:
                break
    app.apply_mesh_change("dissolve", lambda: [mesh.dissolve_edges([e], cleanup=False) for e in edges] and None)
    boundaries = {f: mesh.face_vertices(f) for f in mesh.all_face_ids()}
    assert sum(len(b) == 6 for b in boundaries.values()) == 2
    identifier = send(env)
    sent = parse_goz(Path(identifier + ".GoZ").read_bytes())
    assert len(sent.faces) == 324 and all(len(f) == 4 for f in sent.faces)
    before = positions(mesh)
    history = len(app.history)
    sculpt = parse_goz(flipped(fixture("zb2022_C_move_brush.GoZ"))).points
    goz_back(env, identifier, encode_goz(sent.name, sculpt, sent.faces, sent.groups))
    assert "101 of 326 points moved" in app.status_message, app.status_message
    assert env["bridge"].activate(row(env, APPLY_PREFIX)), app.status_message
    assert len(app.history) == history + 1 and positions(mesh) != before
    assert {f: mesh.face_vertices(f) for f in mesh.all_face_ids()} == boundaries
    app._undo_redo(commands.UNDO)
    assert positions(mesh) == before


def test_an_object_with_skin_weights_is_sent_and_a_weight_edit_is_a_conflict(env):
    """Manu 2026-11-05: `SubD_Cube` (a Skin weights layer) did not send and showed nothing - the weights fingerprint
    raised a TypeError that no status line caught. Now it sends; a weights edit since the send is a conflict."""
    from core import LayerKind

    app = env["app"]
    mesh = app.scene.edit_object.mesh
    lid = mesh.add_point_layer(PointLayerInfo("Skin", LayerKind.WEIGHTS))
    vids = mesh.all_vertex_ids()
    mesh.set_layer_value(lid, vids[0], [(1, 0.75), (2, 0.25)])
    identifier = send(env)
    assert "sent (326 points" in app.status_message
    app.apply_mesh_change("reweight", lambda: mesh.set_layer_value(lid, vids[0], [(1, 1.0)]) or set())
    goz_back(env, identifier, flipped(fixture("zb2022_C_move_brush.GoZ")))
    assert "changed in Mirai since the send (morph targets / weights)" in app.status_message, app.status_message


def test_an_unexpected_send_failure_is_a_status_line(env, monkeypatch):
    import zbrush_bridge

    app = env["app"]
    zbrush_knows_mirai(env)
    monkeypatch.setattr(zbrush_bridge, "build_send", lambda *a, **k: 1 / 0)
    assert not env["bridge"].activate(SEND_LABEL)
    assert "nothing sent - failed: ZeroDivisionError" in app.status_message


def test_the_send_status_names_the_mirror_symmetric_ngon_split(env):
    """Manu 2026-11-05: with Mirai's symmetry on, mirrored n-gons are split alike (quads where possible)."""
    from tests.test_goz_format import head_with_mirrored_ngons

    app = env["app"]
    mesh, _sym = head_with_mirrored_ngons(2)
    app.scene.edit_object.mesh.load_state(mesh.export_state())
    identifier = send(env)
    assert "4 n-gons split in the file, 4 mirror-symmetric" in app.status_message, app.status_message
    assert len(parse_goz(Path(identifier + ".GoZ").read_bytes()).faces) > len(mesh.all_face_ids())


# -- P3: UVs, texture, morph targets ------------------------------------------------------------------------------------


def _uvs(mesh):
    return {f: mesh.face_uvs(f) for f in mesh.all_face_ids()}


def test_uv_master_return_is_applied_with_one_undo_step(env):
    """Manu 2026-11-06 („Mit übernehmen“): ZBrush's new UVs (E3 capture) come in with the confirm, one Undo step."""
    app = env["app"]
    mesh = app.scene.edit_object.mesh
    identifier = send(env)
    before, uvs_before = positions(mesh), _uvs(mesh)
    goz_back(env, identifier, fixture("zb2022_E3_head_uvmaster.GoZ"))
    assert "no point moved, UVs changed" in app.status_message, app.status_message
    history = len(app.history)
    assert env["bridge"].activate(row(env, APPLY_PREFIX))
    unwrapped = parse_goz(fixture("zb2022_E3_head_uvmaster.GoZ")).uvs
    assert [mesh.face_uvs(f) for f in mesh.all_face_ids()] == [tuple(u) for u in unwrapped]
    assert positions(mesh) == before and len(app.history) == history + 1
    app._undo_redo(commands.UNDO)
    assert _uvs(mesh) == uvs_before
    app._undo_redo(commands.REDO)
    goz_back(env, identifier, fixture("zb2022_E3_head_uvmaster.GoZ"))
    assert "no point moved" in app.status_message and "UVs" not in app.status_message  # ZBrush's UVs are the baseline


def _with_texture(data: bytes, path) -> bytes:
    from interop.goz.format import BLOCK_HEADER, TAG_TEXTURE_MAP_PATH

    raw = str(path).encode() + b"\0"
    raw += b"\0" * (-len(raw) % 4)
    return data[:-16] + BLOCK_HEADER.pack(TAG_TEXTURE_MAP_PATH, 16 + len(raw), 1, 0.0) + raw + data[-16:]


def test_a_texture_from_zbrush_is_copied_beside_the_scene_and_undone_with_the_return(env):
    from tests.test_goz_format import _tiff

    app = env["app"]
    obj = app.scene.edit_object
    env["scene_file"]["path"] = env["tmp"] / "kopf.mirai.json"
    identifier = send(env)
    zbrush_file = Path(identifier + "_TXTR.tif")
    zbrush_file.write_bytes(_tiff(2, 2, [b"\x10\x20\x30" * 2, b"\x40\x50\x60" * 2]))
    goz_back(env, identifier, _with_texture(fixture("zb2022_E3_head_uvmaster.GoZ"), zbrush_file))
    assert "texture: head_basemesh_" in app.status_message, app.status_message
    zbrush_file.write_bytes(b"overwritten by the next GoZ")  # the copy was made at arrival
    assert env["bridge"].activate(row(env, APPLY_PREFIX))
    copy = Path(obj.texture)
    assert copy.parent == env["tmp"] / "kopf_textures" and copy.suffix == ".png" and copy.is_file()
    app._undo_redo(commands.UNDO)
    assert obj.texture is None and _uvs(obj.mesh)[obj.mesh.all_face_ids()[0]] != parse_goz(
        fixture("zb2022_E3_head_uvmaster.GoZ")).uvs[0]
    app._undo_redo(commands.REDO)
    assert obj.texture == str(copy)


def test_a_texture_only_return_is_its_own_undo_step(env):
    from tests.test_goz_format import _tiff

    app = env["app"]
    obj = app.scene.edit_object
    identifier = send(env)
    image = env["tmp"] / "paint_TXTR.tif"
    image.write_bytes(_tiff(1, 1, [b"\x01\x02\x03"]))
    goz_back(env, identifier, _with_texture(fixture("zb2022_E3_head_uvs_as_sent.GoZ"), image))
    assert "no point moved, texture changed" in app.status_message, app.status_message
    history = len(app.history)
    assert env["bridge"].activate(row(env, APPLY_PREFIX))
    assert Path(obj.texture).parent == env["bridge"].texture_dir and len(app.history) == history + 1
    app._undo_redo(commands.UNDO)
    assert obj.texture is None


def _bump_target(app):
    from tests.test_goz_format import bump

    mesh = app.scene.edit_object.mesh
    lid = mesh.add_point_layer(PointLayerInfo("Bump"))
    for v, d in bump(mesh).items():
        mesh.set_layer_value(lid, v, d)
    return mesh, lid


def test_base_and_target_go_as_two_subtools_and_a_target_sculpt_comes_back_into_its_layer(env):
    """Manu 2026-11-06: base and targets to ZBrush (E3 T9.5: both arrive); a sculpt on the target SubTool goes into
    that target only, one Undo step; the base's SubTool stays linked (no conflict afterwards)."""
    app = env["app"]
    mesh, lid = _bump_target(app)
    base_id = send(env)
    base_list = env["paths"].read_object_list()
    assert len(base_list) == 2 and base_list[1].endswith("head_basemesh_Bump1")
    assert "1 morph target as own SubTools" in app.status_message
    target_id = base_list[1]
    assert parse_goz(Path(target_id + ".GoZ").read_bytes()).points == parse_goz(
        fixture("zb2022_E3_head_bump_target.GoZ")).points
    goz = parse_goz(fixture("zb2022_E3_head_bump_target.GoZ"))
    pts = list(goz.points)
    pts[3] = (pts[3][0], pts[3][1] + 0.3, pts[3][2])
    before, offsets_before = positions(mesh), mesh.layer_items(lid)
    goz_back(env, target_id, encode_goz(goz.name, pts, goz.faces))
    assert "1 of 326 points of target 'Bump' moved" in app.status_message, app.status_message
    assert env["bridge"].activate(row(env, APPLY_PREFIX))
    v3 = mesh.all_vertex_ids()[3]
    assert positions(mesh) == before
    assert mesh.layer_value(lid, v3)[1] == pytest.approx(-(pts[3][1]) - mesh.vertex_position(v3)[1])
    assert [x for x in mesh.layer_items(lid) if x[0] != v3] == [x for x in offsets_before if x[0] != v3]
    goz_back(env, base_id, flipped(fixture("zb2022_C_move_brush.GoZ")))  # the base SubTool is still linked
    assert "101 of 326 points moved" in app.status_message, app.status_message
    assert env["bridge"].activate(row(env, APPLY_PREFIX))
    goz_back(env, target_id, encode_goz(goz.name, pts, goz.faces))  # ZBrush still holds the same target
    assert "no point of target 'Bump' moved" in app.status_message, app.status_message
    app._undo_redo(commands.UNDO)
    app._undo_redo(commands.UNDO)
    assert positions(mesh) == before and mesh.layer_items(lid) == offsets_before


def test_a_foreign_subtool_with_a_texture_becomes_a_textured_new_object(env):
    """Manu 2026-11-06: a Tool started in ZBrush, UV Master + New From Polypaint, GoZ -> the new object had UVs but no
    texture (the new-object plans dropped it)."""
    from tests.test_goz_format import _tiff

    app = env["app"]
    image = env["tmp"] / "Foreign_TXTR.tif"
    image.write_bytes(_tiff(1, 1, [b"\x01\x02\x03"]))
    goz_back(env, str(env["paths"].project_dir() / "Foreign"),
             _with_texture(fixture("zb2022_E3_head_uvmaster.GoZ"), image))
    assert env["bridge"].activate(row(env, NEW_OBJECT_PREFIX))
    obj = list(app.scene.objects.values())[-1]
    assert obj.mesh.has_face_uvs() and Path(obj.texture).parent == env["tmp"] / "textures"
    assert "with its texture (shown once it is not selected in mode 4)" in app.status_message



# -- a Tool ZBrush renamed (Manu 2026-11-06) ---------------------------------------------------------------------------


def test_a_return_under_a_name_zbrush_changed_links_by_topology(env):
    """ZBrush appends a number when a Tool of the sent name exists already; GoZ then returns under that name. The
    return links by exact topology to the SubTool whose shape it matches (base, not its target), says so, and further
    returns under the new name stay linked."""
    app = env["app"]
    mesh, lid = _bump_target(app)
    base_id = send(env)
    target_renamed = env["paths"].read_object_list()[1] + "_2"
    renamed = base_id + "_1"
    goz_back(env, renamed, flipped(fixture("zb2022_C_move_brush.GoZ")))
    assert "linked by topology: ZBrush renamed 'head_basemesh1' to 'head_basemesh1_1'" in app.status_message
    assert "101 of 326 points moved" in app.status_message, app.status_message
    assert env["bridge"].activate(row(env, APPLY_PREFIX))
    goz_back(env, renamed, flipped(fixture("zb2022_C_move_brush.GoZ")))
    assert "no point moved" in app.status_message, app.status_message
    goz = parse_goz(fixture("zb2022_E3_head_bump_target.GoZ"))
    pts = list(goz.points)
    pts[3] = (pts[3][0], pts[3][1] + 0.3, pts[3][2])
    goz_back(env, target_renamed, encode_goz(goz.name, pts, goz.faces))
    assert "of target 'Bump' moved" in app.status_message, app.status_message


def test_no_link_when_the_topology_matches_no_sent_subtool_or_several_alike(env):
    app = env["app"]
    mesh = app.scene.edit_object.mesh
    mesh.add_point_layer(PointLayerInfo("Flat"))  # a target without offsets: its SubTool equals the base point for point
    send(env)
    goz = parse_goz(flipped(fixture("zb2022_C_unchanged.GoZ")))
    goz_back(env, str(env["paths"].project_dir() / "Other"), encode_goz(goz.name, goz.points, goz.faces[:-1]))
    assert "not sent from Mirai" in app.status_message  # other topology
    goz_back(env, str(env["paths"].project_dir() / "Tie"), encode_goz(goz.name, goz.points, goz.faces))
    assert "not sent from Mirai" in app.status_message and "linked by topology" not in app.status_message  # a tie
