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
from tests.test_goz_format import fixture, flipped

from core import PointLayerInfo, SelectionMode
from core.serialization import scene_to_dict
from interop.goz import helper
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
                          scene_path=lambda: scene_file["path"])
    return {"app": app, "bridge": bridge, "zb": zb, "paths": paths, "inbox": tmp_path / "inbox", "tmp": tmp_path,
            "scene_file": scene_file}


def send(env) -> str:
    assert env["bridge"].activate(SEND_LABEL), env["app"].status_message
    (identifier,) = env["paths"].read_object_list()
    return identifier


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
    manifest = Manifest.from_json(Path(identifier + ".mirai-goz.json").read_text())
    assert manifest.object_id == int(app.scene.edit_object.id) and manifest.session_id == env["bridge"].session_id
    assert paths.application_file.read_text() == "Mirai"
    assert [Path(c[0]).stem for c in env["zb"].commands] == ["GoZMakeObjectPath", "GoZBrushFromApp"]
    assert all("-tmap" not in c for c in env["zb"].commands)
    assert len(app.history) == 0 and INSTALL_LABEL in app.status_message
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
    assert env["bridge"].entries() == (SEND_LABEL, INSTALL_LABEL)
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
    assert env["bridge"].entries() == (SEND_LABEL, INSTALL_LABEL)
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
                         scene_path=lambda: env["tmp"] / "kopf.mirai.json")
    assert later.tick() == 1 and any(r.startswith(APPLY_PREFIX) for r in later.entries())
    env["zb"].press_goz(identifier, flipped(fixture("zb2022_C_move_brush.GoZ")), env["inbox"])
    stranger = ZBrushBridge(app, root=env["paths"].root, inbox=env["inbox"], clock=itertools.count().__next__)
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
    bridge = ZBrushBridge(app, root=env["tmp"] / "nowhere", inbox=env["inbox"])
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
