"""AD-036 §10: eyes, teeth and lids on the rig - the acceptance scenario on `scenes/Gollum_Head_rigging_test.mirai.json`,
as readable named steps in the AD-027 scenario style (as `test_jaw_scenario.py`), headless (the scenario driver of
`tests/interaction_trace.py`).

load -> link the eyes to `Hals` (refused) -> each eye to its eye bone, UPPER to `Hals`, LOWER to `Kiefer` -> turn the head
-> open the jaw -> turn the left eye (the lid follows half) -> the gaze in the pose drives the eye bones -> the gaze at rest
turns only the eyeballs -> refusals in the pose, Apply transform runs -> Undo / Redo -> a topology edit on a tooth -> a rest
edit of the jaw hinge -> bone delete -> save / load. Plus: every bound object shows the pose (a tooth as the edit object),
the morph view's twins stay at rest, and weight 1.0 equals the link.

`UPPER` / `LOWER` are the §10 placeholders until Manu answers E5 (the four teeth sit in one row in the scene, §13.1).
"Exact" = bit-identical; `EPS` = 1e-12 world units.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

import tests._bootstrap  # noqa: F401
from core import BoneId, Mesh, PointLayerInfo
from core.mesh import LayerKind
from core.serialization import scene_from_json
from mirai import bone_links, eye_gaze, object_space, skinning
from mirai.interaction import commands
from mirai.interaction.session import RunContext
from mirai.skinning import BonePose, evaluate, placement_of, skin_layer, skin_transforms
from mirai.viewport.picking import front_face_hit_t
from tests.interaction_trace import CTRL_Y, CTRL_Z, HEIGHT, OVERLAYS, WIDTH, Driver, _frame, key

SCENE = Path(__file__).resolve().parents[1] / "scenes" / "Gollum_Head_rigging_test.mirai.json"
pytestmark = pytest.mark.skipif(not SCENE.exists(), reason="the Gollum rigging scene is not in this checkout")

UPPER = ("tooth", "tooth01")
LOWER = ("Zahn_1", "Zahn_2")
EYES = ("Auge_Links", "Auge_Rechts")
EPS = 1e-12
TEST_KEY = key("w")


# -- helpers -----------------------------------------------------------------------------------------------------------


def _rot(axis, degrees: float):
    return object_space.axis_angle_rotation(axis, math.radians(degrees))


def _t(m):
    return tuple(tuple(m[j][i] for j in range(3)) for i in range(3))


def _apply(affine, p):
    if affine is None:
        return tuple(p)
    m, c = affine
    return tuple(m[i][0] * p[0] + m[i][1] * p[1] + m[i][2] * p[2] + c[i] for i in range(3))


def _close(a, b, eps: float = EPS) -> bool:
    return max(abs(x - y) for x, y in zip(a, b)) <= eps


def _scene_driver() -> Driver:
    d = Driver("cube")
    app = d.app
    app.load_scene("file", scene_path=SCENE, **OVERLAYS)
    app.set_viewport_size(WIDTH, HEIGHT)
    _frame(app)
    app.camera.set_view(0.0, 0.1)
    app.update_viewport(0.0)
    return d


def _obj(app, name):
    return next(o for o in app.scene.objects.values() if o.name == name)


def _bone(app, name) -> BoneId:
    return next(b.id for b in app.scene.rig.bones if b.name == name)


def _world_pose(app, name: str, axis, degrees: float) -> BonePose:
    """A bone's local pose that turns it by `degrees` about the *world* `axis` through its head (S = B·L·B⁻¹)."""
    rb, _ = skinning.rest_frame(app.scene.rig.bone(_bone(app, name)))
    return BonePose(rotation=object_space.matmul3(_t(rb), object_space.matmul3(_rot(axis, degrees), rb)))


def _local_pose(axis, degrees: float) -> BonePose:
    return BonePose(rotation=_rot(axis, degrees))


def _set_pose(app, pose: dict) -> None:
    app._skeleton.set_pose(pose)
    app.update_viewport(0.0)


def _shown(app) -> dict:
    return skin_transforms(app.scene.rig, app.skin.provider.pose)


def _entry_matrix(app, name):
    return app.viewport.object_entries[_obj(app, name).id].model_matrix


def _matrix(transform, pivot):
    return object_space.placement_matrix(transform, pivot)


def _follow_matrix(app, name, bone_name):
    """The definition: `S_b ∘ T` as a matrix (or `T` when the bone is at rest)."""
    obj = _obj(app, name)
    skin = _shown(app).get(_bone(app, bone_name))
    transform = obj.transform if skin is None else bone_links.follow(obj.transform, obj.pivot, skin)
    return _matrix(transform, obj.pivot)


def _world_points(app, name, transform=None) -> list:
    obj = _obj(app, name)
    placed = bone_links.Placed(obj, transform or app.drawn_transform(obj.id))
    return [object_space.to_world(placed, obj.mesh.vertex_position(v)) for v in obj.mesh.all_vertex_ids()]


def _head_input(app) -> dict:
    """The head's skin input: the morph mix the scene's view dials in (four targets), else the rest positions."""
    from mirai import morph_mix

    head = _obj(app, "Gollum")
    weights = app.morph.provider.object_weights(head.id)
    if weights:
        return morph_mix.evaluate(head.mesh, weights)
    return {v: head.mesh.vertex_position(v) for v in head.mesh.all_vertex_ids()}


def _head_drawn(app) -> dict:
    """The definition of the head as drawn: `skinning.evaluate` of its input under the shown pose."""
    head = _obj(app, "Gollum")
    return evaluate(head.mesh, _head_input(app), app.scene.rig, app.skin.provider.pose, placement_of(head))


def _undo(d) -> None:
    history = len(d.app.history)
    d.tap(CTRL_Z)
    assert len(d.app.history) <= history  # (the stack keeps redo entries; the step itself is checked by the caller)


def _redo(d) -> None:
    d.tap(CTRL_Y)


def _weights(app) -> dict:
    mesh = _obj(app, "Gollum").mesh
    return dict(mesh.layer_items(skin_layer(mesh)))


def _mode4(d, names) -> None:
    app = d.app
    if app.selection.mode.name != "OBJECT":
        d.tap(key("4"))
    app.selection.objects = {_obj(app, n).id for n in names}


def _lid_region(app) -> list:
    """§10 setup: head points within 1.3 eye radii of the left eye's centre, above and in front of it, fully on `Hals`."""
    eye = _obj(app, "Auge_Links")
    c = bone_links.eye_center(eye)
    r = eye.transform.scale
    mesh = _obj(app, "Gollum").mesh
    hals = _bone(app, "Hals")
    w = _weights(app)
    out = []
    for v in mesh.all_vertex_ids():
        p = mesh.vertex_position(v)
        if math.dist(p, c) <= 1.3 * r and p[1] > c[1] + 0.2 * r and p[2] > c[2] and w.get(v) == ((hals, 1.0),):
            out.append(v)
    return sorted(out)


def _weight_lid(app, vertices) -> None:
    """The existing write rule (AD-028 W1-W4): 0.5 on `Auge_Links`, the rest stays on `Hals`."""
    mesh = _obj(app, "Gollum").mesh
    lid = skin_layer(mesh)
    hals, eye = _bone(app, "Hals"), _bone(app, "Auge_Links")
    for v in vertices:
        mesh.set_layer_value(lid, v, ((hals, 0.5), (eye, 0.5)))
    app.update_viewport(0.0)


# -- the steps -----------------------------------------------------------------------------------------------------------


def load_and_look(d):
    """Step 0: what follows nothing. The ears are weighted now (§13.1): the unbound points are counted from the file."""
    app = d.app
    raw = json.loads(SCENE.read_text(encoding="utf-8"))
    stored = raw["objects"][0]["mesh"]["point_layers"][0]["values"]
    head = _obj(app, "Gollum")
    unbound = [v for v in head.mesh.all_vertex_ids() if not head.mesh.layer_value(skin_layer(head.mesh), v)]
    assert len(unbound) == len(head.mesh.all_vertex_ids()) - len(stored) == 2
    for name in (*UPPER, *LOWER, *EYES):
        assert app.object_bone(_obj(app, name).id) is None
    return unbound


def eyes_to_the_head_bone_are_refused(d):
    app = d.app
    _mode4(d, EYES)
    history = len(app.history)
    assert app.link_selected_to_bone(_bone(app, "Hals")) is False
    assert "is an eye - it follows its own eye bone" in app.status_message
    assert len(app.history) == history and all(_obj(app, n).bone is None for n in EYES)


def link_the_parts(d):
    """Step 2: one Undo step per command; at rest every entry's matrix exactly as before."""
    app = d.app
    before = {n: _entry_matrix(app, n) for n in (*UPPER, *LOWER, *EYES)}
    history = len(app.history)
    for names, bone in (((EYES[0],), EYES[0]), ((EYES[1],), EYES[1]), (UPPER, "Hals"), (LOWER, "Kiefer")):
        _mode4(d, names)
        assert app.link_selected_to_bone(_bone(app, bone)) is True, app.status_message
        app.update_viewport(0.0)
    assert len(app.history) == history + 4
    for n in (*UPPER, *LOWER, *EYES):
        assert _entry_matrix(app, n) == before[n], n  # bit-exact: the link is rest-relative
        obj = _obj(app, n)
        assert obj.bone is not None
        assert app.drawn_transform(obj.id) is obj.transform  # at rest no product is formed (F-1's short-circuit)


def turn_the_head(d):
    """Step 3: `Hals` 20 degrees about world Y."""
    app = d.app
    app._skeleton.pose_mode = False
    _set_pose(app, {_bone(app, "Hals"): _world_pose(app, "Hals", (0.0, 1.0, 0.0), 20.0)})
    assert app.posed
    for n in (*UPPER, *EYES):
        assert _close(_entry_matrix(app, n), _follow_matrix(app, n, "Hals")), n
    for n in LOWER:  # the jaw at rest under a turned parent takes the parent's transform as it is (F-1)
        assert _close(_entry_matrix(app, n), _follow_matrix(app, n, "Hals")), n
    # a head point fully on Hals keeps its distance to an upper tooth
    head = _obj(app, "Gollum")
    hals = _bone(app, "Hals")
    v = next(v for v, w in _weights(app).items() if w == ((hals, 1.0),))
    tooth_rest = _world_points(app, UPPER[0], _obj(app, UPPER[0]).transform)[0]
    tooth_now = _world_points(app, UPPER[0])[0]
    drawn = _head_drawn(app)
    assert abs(math.dist(drawn[v], tooth_now) - math.dist(_head_input(app)[v], tooth_rest)) <= EPS
    # the eye pass's lid frame turns with the head: equal to the drawn placement (no own eye turn: not passed)
    for n in EYES:
        eye = _obj(app, n)
        assert app._objects.lid_transform(eye) == app.drawn_transform(eye.id)
        assert app.viewport._eye_entries[eye.id].rest_matrix is None or _close(
            app.viewport._eye_entries[eye.id].rest_matrix, _entry_matrix(app, n))


def unbound_points_stay(d, unbound):
    app = d.app
    drawn = _head_drawn(app)
    source = _head_input(app)
    surface = app.skin.provider.surface_mesh
    for v in unbound:
        assert drawn[v] == source[v]  # exact: the rule (the morph mix underneath stays as it is)
        assert tuple(surface.vertex_position(v)) == tuple(source[v])


def click_on_the_drawn_tooth(d):
    """Step 3 / 14: a mode-`4` click where the tooth is drawn selects it; where it was at rest does not."""
    app = d.app
    tooth = _obj(app, UPPER[1])
    mesh = tooth.mesh
    centre_local = tuple(sum(mesh.vertex_position(v)[i] for v in mesh.all_vertex_ids()) / len(mesh.all_vertex_ids())
                         for i in range(3))
    drawn = object_space.to_world(bone_links.Placed(tooth, app.drawn_transform(tooth.id)), centre_local)
    rest = object_space.to_world(tooth, centre_local)
    sx, sy = app.camera.project_to_screen(drawn, WIDTH, HEIGHT)
    rx, ry = app.camera.project_to_screen(rest, WIDTH, HEIGHT)
    assert math.hypot(rx - sx, ry - sy) > 10.0
    # the teeth sit behind the lips: the tooth's own candidate of the mode-4 pick (`pick_object`), occlusion aside
    camera = app._objects.camera_for(tooth)
    assert front_face_hit_t(camera, mesh, sx, sy, WIDTH, HEIGHT) is not None
    assert front_face_hit_t(camera, mesh, rx, ry, WIDTH, HEIGHT) is None
    # with the head out of the way (a Reference ghost is still picked; hide it from the candidates by moving the
    # click to the tooth only): the whole pick selects the tooth where it is drawn
    head = _obj(app, "Gollum")
    head_hit = front_face_hit_t(app._objects.camera_for(head), app._query_mesh(), sx, sy, WIDTH, HEIGHT)
    tooth_hit = front_face_hit_t(camera, mesh, sx, sy, WIDTH, HEIGHT) * app.drawn_transform(tooth.id).scale
    assert app._objects.pick(sx, sy) == (tooth.id if head_hit is None or tooth_hit < head_hit else head.id)


def open_the_jaw(d):
    """Step 4: `Kiefer` 20 degrees about its own X."""
    app = d.app
    pose = dict(app._skeleton.pose)
    pose[_bone(app, "Kiefer")] = _local_pose((1.0, 0.0, 0.0), 20.0)
    upper_before = {n: _entry_matrix(app, n) for n in UPPER}
    _set_pose(app, pose)
    for n in LOWER:
        assert _close(_entry_matrix(app, n), _follow_matrix(app, n, "Kiefer")), n
    for n in UPPER:
        assert _entry_matrix(app, n) == upper_before[n]
    kiefer = _bone(app, "Kiefer")
    v = next(v for v, w in _weights(app).items() if w == ((kiefer, 1.0),))
    head = _obj(app, "Gollum")
    tooth_rest = _world_points(app, LOWER[0], _obj(app, LOWER[0]).transform)[0]
    tooth_now = _world_points(app, LOWER[0])[0]
    assert abs(math.dist(_head_drawn(app)[v], tooth_now) - math.dist(_head_input(app)[v], tooth_rest)) <= EPS


def turn_the_left_eye(d, lid_points):
    """Step 5: `Auge_Links` about its own X by -15 degrees (look up): the eyeball turns about its centre, the lid frame
    stays with the head, a lid point half on the eye bone turns half (its distance from the turn axis by cos 7.5)."""
    app = d.app
    eye = _obj(app, "Auge_Links")
    lid_before = app._objects.lid_transform(eye)
    pose = dict(app._skeleton.pose)
    eye_bone = _bone(app, "Auge_Links")
    pose[eye_bone] = _local_pose((1.0, 0.0, 0.0), -15.0)
    _set_pose(app, pose)
    shown = _shown(app)
    hals = shown[_bone(app, "Hals")]
    assert _close(_entry_matrix(app, "Auge_Links"), _follow_matrix(app, "Auge_Links", "Auge_Links"))
    centre = bone_links.eye_center(bone_links.Placed(eye, app.drawn_transform(eye.id)))
    assert _close(centre, _apply(hals, bone_links.eye_center(eye)))
    assert app._objects.lid_transform(eye) == lid_before  # the lid shading does not turn with the eye
    rest_matrix = app.viewport._eye_entries[eye.id].rest_matrix
    assert rest_matrix is not None and _close(rest_matrix, _matrix(lid_before, eye.pivot))
    # the lid points: what is drawn = evaluate; the half-weighted point turns half
    drawn = _head_drawn(app)
    surface = app.skin.provider.surface_mesh
    head = _obj(app, "Gollum")
    rb, c = skinning.rest_frame(app.scene.rig.bone(eye_bone))
    axis = (rb[0][0], rb[1][0], rb[2][0])  # the bone's local X in world (rest)
    inv = bone_links._inverse(hals)
    for v in lid_points:
        assert _close(surface.vertex_position(v), drawn[v])
        p = _head_input(app)[v]
        q = _apply(inv, drawn[v])  # back through the head's turn: the eye's own turn remains

        def radial(x):
            r = tuple(x[i] - c[i] for i in range(3))
            along = sum(r[i] * axis[i] for i in range(3))
            return math.sqrt(max(0.0, sum(r[i] * r[i] for i in range(3)) - along * along))

        assert abs(radial(q) - math.cos(math.radians(7.5)) * radial(p)) <= EPS


def gaze_in_the_pose(d, lid_points):
    """Step 6 (E2 "ja"): gaze `target` up-left drives the eye bones; the lid points follow; the user's pose stays; gaze
    `rest` brings the manual eye pose back. A target behind the turned head: 50 degrees from the head-carried forward."""
    app = d.app
    user, last = dict(app._skeleton.pose), dict(app._skeleton.last_pose)
    before = _head_drawn(app)
    frame = app._objects.gaze_frame()
    target = eye_gaze.pad_target(frame, 25.0, 15.0, 25.0)
    assert app.set_eye_gaze(mode="target", target=target) is True
    app.update_viewport(0.0)
    shown = app.skin.provider.pose
    for n in EYES:
        bone = _bone(app, n)
        assert shown[bone] != user.get(bone)  # the channel is gaze-derived
        eye = _obj(app, n)
        drawn = app.drawn_transform(eye.id)
        forward = (drawn.rotation[0][2], drawn.rotation[1][2], drawn.rotation[2][2])
        to = eye_gaze._unit(eye_gaze._sub(target, bone_links.eye_center(bone_links.Placed(eye, drawn))))
        assert sum(forward[i] * to[i] for i in range(3)) >= 1.0 - 1e-12  # the eye looks at the target
        assert _close(_entry_matrix(app, n), _matrix(drawn, eye.pivot))
    assert app._skeleton.pose == user and app._skeleton.last_pose == last  # never written
    after = _head_drawn(app)
    assert any(after[v] != before[v] for v in lid_points)  # the lids follow the gaze
    surface = app.skin.provider.surface_mesh
    assert all(_close(surface.vertex_position(v), after[v]) for v in lid_points)
    # the clamp is relative to the head-carried forward
    carried = bone_links.Placed(_obj(app, "Auge_Rechts"), app._objects.lid_transform(_obj(app, "Auge_Rechts")))
    behind = eye_gaze._add(bone_links.eye_center(carried), eye_gaze._scale(eye_gaze.rest_forward(carried), -2.0))
    app.set_eye_gaze(mode="target", target=behind)
    app.update_viewport(0.0)
    drawn = app.drawn_transform(_obj(app, "Auge_Rechts").id)
    f0, f1 = eye_gaze.rest_forward(carried), (drawn.rotation[0][2], drawn.rotation[1][2], drawn.rotation[2][2])
    assert abs(math.degrees(math.acos(min(1.0, sum(f0[i] * f1[i] for i in range(3))))) - 50.0) < 1e-6
    assert app.set_eye_gaze(mode="rest") is True
    app.update_viewport(0.0)
    assert app.skin.provider.pose == user and _head_drawn(app) == before


def gaze_at_rest(d):
    """Step 7: rest toggle, gaze `camera`: the eyes as before (`aimed_transform`), the lid points at rest, not posed, a
    Move on the head runs."""
    app = d.app
    assert app._skeleton.toggle_rest() is True
    app.update_viewport(0.0)
    assert not app.posed
    assert app.set_eye_gaze(mode="camera") is True
    app.update_viewport(0.0)
    target = app._objects.gaze_drawn
    for n in EYES:
        eye = _obj(app, n)
        assert _entry_matrix(app, n) == _matrix(eye_gaze.aimed_transform(eye, target), eye.pivot)
    source = _head_input(app)
    drawn = _head_drawn(app)
    assert all(drawn[v] == source[v] for v in drawn)  # the lid points at rest: the gaze turns only the eyeballs
    assert app._skeleton.posed_text(commands.MOVE) is None
    app.set_eye_gaze(mode="rest")
    assert app._skeleton.toggle_rest() is True  # back to the pose
    app.update_viewport(0.0)
    assert app.posed


def refusals_in_the_pose(d):
    """Step 8: object W/E/R and Clear on a linked tooth refused with the rest key; Apply runs, the world stays."""
    app = d.app
    _mode4(d, (UPPER[0],))
    tooth = _obj(app, UPPER[0])
    for command in (commands.MOVE, commands.ROTATE, commands.SCALE, commands.TWEAK, commands.CLEAR_TRANSFORM):
        refusal = app.can_run(command, RunContext("key", TEST_KEY))
        assert refusal is not None and f"{tooth.name!r} follows 'Hals' - the rig is posed" in refusal.text, command
        assert "= rest pose)" in refusal.text
    state = (tooth.transform, tooth.mesh.export_state())
    d.key_down(key("w"))
    d.nudge(10, 0)
    d.key_up("w")
    assert (tooth.transform, tooth.mesh.export_state()) == state
    # Apply transform: the world points stay (S_b · I · (T p))
    world = _world_points(app, UPPER[0])
    history = len(app.history)
    assert app.can_run(commands.APPLY_TRANSFORM, RunContext("key", TEST_KEY)) is None
    assert app._objects.placement_command(commands.APPLY_TRANSFORM) is True, app.status_message
    app.update_viewport(0.0)
    assert all(_close(a, b) for a, b in zip(world, _world_points(app, UPPER[0])))
    _undo(d)
    assert (tooth.transform, tooth.mesh.export_state()) == state


def undo_redo_the_links(d, steps: int):
    """Step 9: Undo to before the links and Redo back - exact; the pose (view state) untouched."""
    app = d.app
    links = {n: _obj(app, n).bone for n in (*UPPER, *LOWER, *EYES)}
    pose = dict(app._skeleton.pose)
    for _ in range(steps):
        _undo(d)
    assert all(_obj(app, n).bone is None for n in links)
    assert app._skeleton.pose == pose
    for _ in range(steps):
        _redo(d)
    assert {n: _obj(app, n).bone for n in links} == links
    app.update_viewport(0.0)


def topology_edit_on_a_tooth(d):
    """Step 10: at rest a tooth as the edit object, an edge split - the link stays; in the pose the new point follows."""
    app = d.app
    assert app._skeleton.toggle_rest() is True
    tooth = _obj(app, LOWER[1])
    app._objects.set_edit_object(tooth.id)
    mesh = tooth.mesh
    link = tooth.bone
    edge = sorted(mesh.all_edge_ids())[0]
    new = {}

    def split():
        new["v"] = {mesh.split_edge(edge, 0.5)[0]}
        return new["v"]

    assert app.apply_mesh_change("Split edge", split)
    assert tooth.bone == link
    assert app._skeleton.toggle_rest() is True  # the pose again
    app.update_viewport(0.0)
    (v,) = new["v"]
    drawn = app.drawn_transform(tooth.id)
    skin = _shown(app)[link]
    expected = _apply(skin, object_space.to_world(tooth, mesh.vertex_position(v)))
    assert _close(object_space.to_world(bone_links.Placed(tooth, drawn), mesh.vertex_position(v)), expected)
    assert _close(app.viewport.model_matrix, _matrix(drawn, tooth.pivot))  # the edit object rides its bone
    # §4.5: its position and topology edits are refused while posed (as a bound mesh's)
    d.tap(key("1"))
    assert app._skeleton.posed_text(commands.MOVE) is not None
    d.tap(key("4"))


def every_object_shows_the_pose(d):
    """Step 15 (§4.6): with a tooth as the edit object the bound head (not the edit object) is drawn posed."""
    app = d.app
    head = _obj(app, "Gollum")
    assert app.scene.edit_object_id != head.id
    surfaces = app.skin.provider.entry_surfaces
    assert head.id in surfaces
    drawn = _head_drawn(app)
    surface = surfaces[head.id]
    assert all(_close(surface.vertex_position(v), drawn[v]) for v in head.mesh.all_vertex_ids())
    assert app._objects.posed_surfaces()[head.id] is surface  # mode-4 picking reads the posed surface
    app._objects.set_edit_object(head.id)
    app.update_viewport(0.0)


def rest_edit_of_the_hinge(d):
    """Step 11: `Kiefer`'s head 1 % of its length forward at rest: everything exact at rest; in the pose LOWER turns about
    the new hinge."""
    app = d.app
    assert app._skeleton.toggle_rest() is True
    app.update_viewport(0.0)
    rest = {n: _entry_matrix(app, n) for n in (*UPPER, *LOWER)}
    bone = app.scene.rig.bone(_bone(app, "Kiefer"))
    step = 0.01 * bone.length
    head = (bone.head[0], bone.head[1], bone.head[2] + step)
    assert app.edit_bone(bone.id, head=head) is True, app.status_message
    app.update_viewport(0.0)
    assert {n: _entry_matrix(app, n) for n in rest} == rest
    assert app._skeleton.toggle_rest() is True
    app.update_viewport(0.0)
    for n in LOWER:
        assert _close(_entry_matrix(app, n), _follow_matrix(app, n, "Kiefer")), n
    _undo(d)  # the hinge back
    assert app.scene.rig.bone(bone.id) == bone
    app.update_viewport(0.0)


def delete_bones(d):
    """Step 12: delete `Kiefer` (LOWER re-linked to `Hals`, the weights to `Hals`), then `Auge_Links` (the left eye
    unlinked); Undo restores both exactly."""
    app = d.app
    assert app._skeleton.toggle_rest() is True  # bone edits at rest
    app.update_viewport(0.0)
    links = {n: _obj(app, n).bone for n in (*UPPER, *LOWER, *EYES)}
    weights = _weights(app)
    rig = app.scene.rig
    hals = _bone(app, "Hals")
    assert app.delete_bone(_bone(app, "Kiefer")) is True
    assert all(_obj(app, n).bone == hals for n in LOWER)
    assert "now follow 'Hals'" in app.status_message
    assert app.delete_bone(_bone(app, "Auge_Links")) is True
    assert _obj(app, "Auge_Links").bone is None and "follow no bone" in app.status_message
    _undo(d)
    _undo(d)
    assert {n: _obj(app, n).bone for n in links} == links
    assert _weights(app) == weights and app.scene.rig == rig
    assert app._skeleton.toggle_rest() is True
    app.update_viewport(0.0)


def save_and_load(d, tmp_path):
    """Step 13: links saved (v13), the pose not (a load starts at rest); posed again: the same drawn matrices."""
    app = d.app
    pose = dict(app._skeleton.pose)
    matrices = {n: _entry_matrix(app, n) for n in (*UPPER, *LOWER, *EYES)}
    links = {n: _obj(app, n).bone for n in matrices}
    path = tmp_path / "linked.mirai.json"
    assert app.save_scene_file(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == 13
    app.load_scene("file", scene_path=path, **OVERLAYS)
    app.update_viewport(0.0)
    assert not app.posed and {n: _obj(app, n).bone for n in links} == links
    _set_pose(app, pose)
    for n, m in matrices.items():
        assert _close(_entry_matrix(app, n), m), n
    # a dead link loads (the part follows nothing); an id never in the rig makes the file invalid
    dead = json.loads(json.dumps(data))
    next(o for o in dead["objects"] if o["name"] == UPPER[0])["bone"] = 2  # below the counter, not in the rig
    assert scene_from_json(json.dumps(dead)) is not None
    bad = json.loads(json.dumps(data))
    next(o for o in bad["objects"] if o["name"] == UPPER[0])["bone"] = data["rig"]["bone_id_counter"]
    with pytest.raises(ValueError):
        scene_from_json(json.dumps(bad))


# -- the scenario ----------------------------------------------------------------------------------------------------


def test_eyes_teeth_and_lids_on_the_rig(tmp_path):
    d = _scene_driver()
    app = d.app
    unbound = load_and_look(d)
    lid_points = _lid_region(app)
    assert len(lid_points) >= 5
    _weight_lid(app, lid_points)
    eyes_to_the_head_bone_are_refused(d)
    link_the_parts(d)
    turn_the_head(d)
    unbound_points_stay(d, unbound)
    click_on_the_drawn_tooth(d)
    open_the_jaw(d)
    turn_the_left_eye(d, lid_points)
    gaze_in_the_pose(d, lid_points)
    gaze_at_rest(d)
    refusals_in_the_pose(d)
    undo_redo_the_links(d, 4)
    topology_edit_on_a_tooth(d)
    every_object_shows_the_pose(d)
    rest_edit_of_the_hinge(d)
    delete_bones(d)
    save_and_load(d, tmp_path)


# -- single rules ------------------------------------------------------------------------------------------------------


def test_weight_one_on_a_tooth_equals_the_link():
    """Step 17: the same tooth weighted 1.0 instead of linked gives the same world points (<= EPS)."""
    scene = scene_from_json(SCENE.read_text(encoding="utf-8"))
    rig = scene.rig
    ids = {b.name: b.id for b in rig.bones}
    pose = {ids["Hals"]: BonePose(rotation=_rot((0.0, 1.0, 0.0), 20.0)),
            ids["Kiefer"]: BonePose(rotation=_rot((1.0, 0.0, 0.0), 15.0))}
    transforms = skin_transforms(rig, pose)
    for name, bone in ((UPPER[0], "Hals"), (LOWER[0], "Kiefer")):
        obj = next(o for o in scene.objects.values() if o.name == name)
        mesh = Mesh.from_state(obj.mesh.export_state())
        lid = mesh.add_point_layer(PointLayerInfo("Skin", LayerKind.WEIGHTS))
        for v in mesh.all_vertex_ids():
            mesh.set_layer_value(lid, v, ((ids[bone], 1.0),))
        weighted = evaluate(mesh, None, rig, pose, placement_of(obj), lid)
        obj.bone = ids[bone]
        placed = bone_links.Placed(obj, bone_links.drawn_transform(obj, rig, transforms))
        for v, p in weighted.items():
            assert _close(object_space.to_world(obj, p), object_space.to_world(placed, mesh.vertex_position(v)))


def test_linked_xor_bound_and_the_link_refusals():
    """§4.1 / §4.4: linking a weighted mesh is refused; writing weights on a linked edit object is refused; Link and Unlink
    are refused while posed; a mirror copy of a tooth linked to an off-plane bone is unlinked with a note, on a plane bone
    it keeps the link."""
    d = _scene_driver()
    app = d.app
    _mode4(d, ("Gollum",))
    assert app.link_selected_to_bone(_bone(app, "Hals")) is False and "has weights" in app.status_message
    _mode4(d, (LOWER[0],))
    assert app.link_selected_to_bone(_bone(app, "Kiefer")) is True
    copy = app._objects.mirror_copy("X")
    assert copy is not None and copy.bone == _bone(app, "Kiefer")  # Kiefer lies on the plane x = 0
    app.selection.objects = {_obj(app, UPPER[0]).id}
    assert app.link_selected_to_bone(_bone(app, "Auge_Links")) is True  # a tooth may follow any bone
    copy = app._objects.mirror_copy("X")
    assert copy is not None and copy.bone is None and "its mirror bone is needed" in app.status_message
    app.selection.objects = {_obj(app, LOWER[0]).id}
    _set_pose(app, {_bone(app, "Kiefer"): _local_pose((1.0, 0.0, 0.0), 10.0)})
    assert app.bone_link_blocker is not None
    assert app.unlink_selected() is False and "the rig is posed" in app.status_message
    _set_pose(app, {})
    app._objects.set_edit_object(_obj(app, LOWER[0]).id)
    d.tap(key("1"))
    app.selection.vertices = set(_obj(app, LOWER[0]).mesh.all_vertex_ids())
    assert app.set_weight_value(1.0) is False and "a part follows a bone or is weighted" in app.status_message


def test_a_view_twin_stays_at_rest_while_its_original_follows():
    """§5.5: the twins beside a morph target's editing view are drawn at rest; the originals at the base follow."""
    d = _scene_driver()
    app = d.app
    _mode4(d, UPPER)
    assert app.link_selected_to_bone(_bone(app, "Hals")) is True
    _set_pose(app, {_bone(app, "Hals"): _world_pose(app, "Hals", (0.0, 1.0, 0.0), 15.0)})
    tooth = _obj(app, UPPER[0])
    twin = app._objects._drawn_matrix(tooth, None, (1.0, 0.0, 0.0))
    expected = _matrix(tooth.transform, tooth.pivot)
    expected[12] += 1.0
    assert twin == expected
    assert _close(_entry_matrix(app, UPPER[0]), _follow_matrix(app, UPPER[0], "Hals"))


def test_pose_mode_keeps_posing_with_linked_parts_selected_in_mode_4():
    """Regression (Manu 2026-11-18: "Im Pose Modus kann ich nur eine einzige Bewegung machen, danach ist es scheinbar
    eingefroren"): after Link the parts stay selected in mode 4; in pose mode W/E/R pose the current bone, so the object
    placement policy (a linked part is locked while posed) must not refuse the second gesture. The same for a selected
    bound head."""
    from tests.rig_support import POSE_MODE, E, hold

    d = _scene_driver()
    app = d.app
    _mode4(d, LOWER)
    assert app.link_selected_to_bone(_bone(app, "Kiefer")) is True
    app.select_bone(_bone(app, "Hals"))
    d.motion(WIDTH * 0.6, HEIGHT * 0.5)
    d.tap(POSE_MODE)
    assert app.pose_mode
    for selected in (LOWER, ("Gollum",)):
        app.selection.objects = {_obj(app, n).id for n in selected}
        for _ in range(3):
            before = app._skeleton.pose.get(_bone(app, "Hals"))
            hold(d, E, ((12, 0), (12, 0)))
            assert app.status_message.startswith("Pose: 'Hals' rotated"), app.status_message
            assert app._skeleton.pose.get(_bone(app, "Hals")) != before
    # out of pose mode the placement stays locked for a linked part while posed (§4.5)
    d.tap(POSE_MODE)
    app.selection.objects = {_obj(app, LOWER[0]).id}
    refusal = app.can_run(commands.ROTATE, RunContext("key", TEST_KEY))
    assert refusal is not None and "follows 'Kiefer' - the rig is posed" in refusal.text


def test_the_weight_view_follows_a_bone_chosen_in_the_outliner_or_panel():
    """Regression (Manu 2026-11-18): with the weight view on, choosing another bone (Outliner / Bone panel,
    `select_bone`) shows that bone's share at once, without switching the view off and on."""
    d = _scene_driver()
    app = d.app
    d.tap(key("1"))
    app.select_bone(_bone(app, "Hals"))
    assert app._weight_view_toggle() is True and app.weight_view
    before = app.weight_share_computes
    assert app.select_bone(_bone(app, "Kiefer")) is True
    assert app.weight_view_text == "Kiefer"
    assert app.weight_share_computes > before
