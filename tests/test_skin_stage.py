"""T-4 (AD-028 §12): the skin stage in the app's surface chain (morph -> skin -> SubD, §5.2).

Headless through `Application`. A randomized oracle - pose steps, weight writes, base moves, topology
edits, morph weight steps, bone add / delete, Undo / Redo - with the shown surface bit-exact against
`skinning.evaluate` of the mix after every step; order independence (the same inputs reached in other
orders, and a fresh provider, give bit-identical surfaces); morph -> skin -> SubD = SubD of the skinned
mix from scratch (≤ 1e-12); the stage is wanted only while posed with a weights layer, and kept at rest
while SubD reads it (the toggle patches instead of rebuilding); the entry surface beside the morph view.
The pose is set through the API (no UI in this slice).
"""

from __future__ import annotations

import math
import random

import pytest

import tests._bootstrap  # noqa: F401

from core import BoneId, LayerKind, Mesh, PointLayerInfo, Rig, SelectionMode
from core.operations.collapse import collapse_elements
from mirai import morph_mix, morph_targets, skinning
from mirai.interaction import commands
from mirai.object_space import axis_angle_rotation
from mirai.skin_weights import delete_bone_weights, parent_function, set_bone_weight
from mirai.skinning import BonePose, SkinSurfaceProvider
from mirai.surface_chain import ChainedSurface
from tests.mesh_invariants import assert_layer_invariants
from tests.test_application_delete_dissolve import _app
from tests.test_morph_multi import TAB, _targets


def _rig(mesh: Mesh) -> Rig:
    xs = [mesh.vertex_position(v)[0] for v in mesh.all_vertex_ids()]
    ys = [mesh.vertex_position(v)[1] for v in mesh.all_vertex_ids()]
    lo, hi = min(ys), max(ys)
    mid = (min(xs) + max(xs)) / 2.0
    rig = Rig()
    rig, head = rig.with_new_bone("Head", (mid, (lo + hi) / 2.0, 0.0), (mid, hi, 0.0))
    rig, jaw = rig.with_new_bone("Jaw", (mid, (lo + hi) / 2.0, 0.0), (mid, lo, 0.4), parent=head)
    rig, _ = rig.with_new_bone("Lip", (mid, lo, 0.4), (mid, lo - 0.3, 0.6), parent=jaw)
    return rig


def _bind(mesh: Mesh, rng: random.Random, keys=(0, 1, 2)):
    lid = mesh.add_point_layer(PointLayerInfo("Skin", LayerKind.WEIGHTS))
    for v in mesh.all_vertex_ids():
        if rng.random() < 0.8:
            chosen = rng.sample(keys, rng.randint(1, len(keys)))
            raw = [rng.random() + 0.05 for _ in chosen]
            scale = 1.0 if rng.random() < 0.6 else rng.uniform(0.3, 0.95)
            mesh.set_layer_value(lid, v, [(k, w / sum(raw) * scale) for k, w in zip(chosen, raw)])
    return lid


def _bone_pose(rng: random.Random) -> BonePose:
    axis = [rng.uniform(-1, 1) for _ in range(3)]
    n = math.sqrt(sum(c * c for c in axis)) or 1.0
    return BonePose(
        rotation=axis_angle_rotation(tuple(c / n for c in axis), rng.uniform(-0.8, 0.8)),
        translation=tuple(rng.uniform(-0.2, 0.2) for _ in range(3)) if rng.random() < 0.3 else (0.0, 0.0, 0.0),
        scale=rng.uniform(0.8, 1.2) if rng.random() < 0.2 else 1.0,
    )


def _setup(n: int = 4, seed: int = 0):
    app = _app(n)
    rng = random.Random(seed)
    mesh = app.scene.mesh
    lid = _bind(mesh, rng)
    app.scene.rig = _rig(mesh)
    return app, mesh, lid, rng


def _expected(app) -> dict:
    """`evaluate` of the edit object's mix (or rest) with the app's rig, pose and placement."""
    obj = app.scene.edit_object
    weights = app.morph.provider.object_weights(obj.id)
    mix = morph_mix.evaluate(obj.mesh, weights) if weights else None
    return skinning.evaluate(obj.mesh, mix, app.scene.rig, app.skin.provider.pose, skinning.placement_of(obj))


def _assert_shown(app) -> None:
    app.update_viewport(0.0)
    provider = app.skin.provider
    mesh = app.scene.mesh
    if not provider.posed() or skinning.skin_layer(mesh) is None:
        if app.surface_chain.holds(provider):  # kept at rest while SubD reads it: exactly the input
            assert provider.surface_mesh is not None and not provider.posed()
            assert all(provider.surface_mesh.vertex_position(v) == p for v, p in _expected(app).items())
        return
    surface = provider.surface_mesh
    assert surface is not None and app.surface_chain.holds(provider)
    assert sorted(surface.all_vertex_ids()) == sorted(mesh.all_vertex_ids())
    assert set(surface.positions()) == set(mesh.all_vertex_ids())  # O1: the table follows the input's journal
    assert {f: surface.face_vertices(f) for f in surface.all_face_ids()} == {
        f: mesh.face_vertices(f) for f in mesh.all_face_ids()}
    for v, p in _expected(app).items():
        assert surface.vertex_position(v) == p, v


# -- the randomized oracle ----------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(5))
def test_the_shown_surface_is_the_definition_through_random_steps(seed):
    """Seeds 0-2 with two morph targets (the skin reads the mix), 3-4 without (it reads the edit mesh)."""
    app, mesh, lid, rng = _setup(4, seed)
    lids = _targets(app, 2, seed=seed, every=2) if seed < 3 else []
    skin = app.skin.provider
    builds, last = 0, None
    for step in range(160):
        rig = app.scene.rig
        ids = mesh.all_vertex_ids()
        op = rng.randrange(14)
        if op <= 2 and rig is not None and rig.bones:
            pose = dict(skin.pose)
            bone = rng.choice(rig.bone_ids())
            pose[bone] = BonePose() if rng.random() < 0.2 else _bone_pose(rng)
            skin.set_pose(pose)
        elif op == 3:
            skin.set_pose({})  # the rest pose
        elif op == 4 and skinning.skin_layer(mesh) is not None:
            v = rng.choice(ids)
            layer = skinning.skin_layer(mesh)
            bone = rng.choice(rig.bone_ids()) if rig and rig.bones else BoneId(0)
            new = set_bone_weight(mesh.layer_value(layer, v), bone, rng.random(), parent_function(rig))
            app.apply_mesh_change("weight", lambda: mesh.set_layer_value(layer, v, new))
        elif op == 5:
            v = rng.choice(ids)
            app.apply_mesh_change(
                "move", lambda: mesh.set_vertex_position(v, tuple(c + rng.uniform(-0.1, 0.1) for c in mesh.vertex_position(v))))
        elif op == 6:
            edge = rng.choice(mesh.all_edge_ids())
            app.apply_mesh_change("split", lambda: mesh.split_edge(edge, rng.uniform(0.2, 0.8)) and None)
        elif op == 7:
            face = rng.choice(mesh.all_face_ids())
            a, b, c = mesh.face_vertices(face)[:3]
            p = tuple(sum(mesh.vertex_position(x)[k] for x in (a, b, c)) / 3.0 for k in range(3))
            app.apply_mesh_change(
                "cut", lambda: mesh.split_face(face, a, c, [p], origins=[((a, 0.25), (b, 0.5), (c, 0.25))]) and None)
        elif op == 8:
            edge = rng.choice(mesh.all_edge_ids())
            try:
                app.apply_mesh_change("collapse", lambda: collapse_elements(mesh, mesh.edge_vertices(edge)) and None)
            except Exception:
                pass
        elif op == 9 and app.history.can_undo():
            app.dispatch_command(commands.UNDO if rng.random() < 0.6 else commands.REDO)
        elif op == 10 and lids:
            app.set_morph_weight(rng.choice((0, 30, 70, 100)), rng.choice(lids))
        elif op == 11 and rig is not None:
            # bone add (a rig value; slice 3 makes it a command) / delete with the weights rewrite
            if len(rig.bones) < 5 and rng.random() < 0.5:
                parent = rng.choice(rig.bone_ids()) if rig.bones else None
                app.scene.rig, _ = rig.with_new_bone(
                    f"B{step}", tuple(rng.uniform(-1, 1) for _ in range(3)), (0.0, 0.0, 2.0), parent=parent)
            elif rig.bones:
                bone = rng.choice(rig.bone_ids())
                layer = skinning.skin_layer(mesh)
                if layer is not None:
                    app.apply_mesh_change("bone weights", lambda: delete_bone_weights(mesh, layer, bone, rig) and None)
                app.scene.rig = rig.without_bone(bone)
                skin.set_pose({b: p for b, p in skin.pose.items() if b != bone})
        elif op == 12:
            obj = app.scene.edit_object
            from core import ObjectTransform

            obj.transform = ObjectTransform(
                translation=tuple(rng.uniform(-1, 1) for _ in range(3)),
                rotation=axis_angle_rotation((0.0, 0.0, 1.0), rng.uniform(-1, 1)), scale=rng.uniform(0.7, 1.4))
        elif op == 13 and rng.random() < 0.3:
            app.scene.rig = None if app.scene.rig is not None else _rig(mesh)
        _assert_shown(app)
        assert_layer_invariants(mesh)
        held = app.surface_chain.holds(skin)
        if held and skin.surface_mesh is not None and skin.surface_mesh is not last:
            builds += 1
            last = skin.surface_mesh
    assert builds < 40  # patched in place; rebuilt only when the stage came back or its input changed
    # a fresh provider from the same inputs shows bit-identical positions (no drift)
    if app.surface_chain.holds(skin) and skin.posed() and skin.surface_mesh is not None:
        fresh = SkinSurfaceProvider(lambda: app.scene)
        fresh.set_pose(skin.pose)
        source = app.morph.provider.surface_mesh if app.morph.provider.surface_mesh is not None else mesh
        fresh.sync(source, app.selection)
        assert fresh.surface_mesh.positions() == skin.surface_mesh.positions()


def test_the_surface_is_independent_of_the_order_of_pose_steps_and_weight_writes():
    results = []
    for order in range(3):
        app, mesh, lid, _ = _setup(3, seed=5)
        rng = random.Random(77)
        steps = [("pose", BoneId(rng.randrange(3)), _bone_pose(rng)) for _ in range(6)]
        steps += [("weight", rng.choice(mesh.all_vertex_ids()), rng.random()) for _ in range(6)]
        final_pose = {}
        for kind, a, b in steps:
            if kind == "pose":
                final_pose[a] = b
        writes = [(v, x) for kind, v, x in steps if kind == "weight"]
        random.Random(order).shuffle(steps)
        skin = app.skin.provider
        pose = {}
        for kind, a, b in steps:
            if kind == "pose":
                pose[a] = b if b is final_pose[a] else _bone_pose(rng)  # an intermediate value
                skin.set_pose(pose)
            app.update_viewport(0.0)
        skin.set_pose(final_pose)
        for v, x in writes:  # the same writes in the same order (the write rule is path dependent)
            new = set_bone_weight(mesh.layer_value(lid, v), BoneId(1), x, parent_function(app.scene.rig))
            app.apply_mesh_change("weight", lambda: mesh.set_layer_value(lid, v, new))
            app.update_viewport(0.0)
        _assert_shown(app)
        results.append(skin.surface_mesh.positions())
    assert results[0] == results[1] == results[2]


# -- the stage in the chain ----------------------------------------------------------------------------


def test_the_stage_is_wanted_only_while_posed_with_a_weights_layer():
    app = _app(3)
    app.update_viewport(0.0)
    assert app.viewport.surface_provider is None
    mesh = app.scene.mesh
    app.scene.rig = _rig(mesh)
    app.skin.provider.set_pose({BoneId(1): _bone_pose(random.Random(1))})
    app.update_viewport(0.0)
    assert app.viewport.surface_provider is None  # no weights layer: nothing to show
    _bind(mesh, random.Random(2))
    app.update_viewport(0.0)
    assert app.viewport.surface_provider is app.skin.provider  # alone it sits in the slot itself
    _assert_shown(app)
    app.skin.provider.set_pose({})
    app.update_viewport(0.0)
    assert app.viewport.surface_provider is None  # at rest the chain is today's
    app.skin.provider.set_pose({BoneId(1): _bone_pose(random.Random(3))})
    app.scene.rig = None
    app.update_viewport(0.0)
    assert app.viewport.surface_provider is None  # no rig: not posed


def test_morph_skin_subd_is_subd_of_the_skinned_mix():
    from mirai.subdivision.catmull_clark import SubdSurface

    app, mesh, lid, rng = _setup(4, seed=3)
    lids = _targets(app, 2, seed=4, every=2)
    app.set_morph_weight(60, lids[0])
    app.skin.provider.set_pose({BoneId(1): _bone_pose(rng), BoneId(2): _bone_pose(rng)})
    assert app.subdivision.set_view("cage"), app.status_message
    app.update_viewport(0.0)
    provider = app.viewport.surface_provider
    assert isinstance(provider, ChainedSurface)
    assert provider.stages == (app.morph.provider, app.skin.provider, app.subdivision.provider)
    assert app.skin.provider.surface_mesh is not None
    assert app.subdivision.provider._mesh is app.skin.provider.surface_mesh  # SubD reads the skinned cage

    def check():
        app.update_viewport(0.0)
        state = morph_mix.rest_state(mesh)
        for v, p in _expected(app).items():
            state["vertices"][int(v)] = list(p)
        cage = Mesh.from_state(state)
        surface = SubdSurface(cage)
        level = surface.level(app.subdivision.level)
        expected = level.apply_full([tuple(cage.vertex_position(v)) for v in surface.topology.vertex_ids])
        got = app.subdivision.provider.derived_positions()
        assert len(got) == len(expected)
        assert max(abs(a - b) for p, q in zip(got, expected) for a, b in zip(p, q)) <= 1e-12

    check()
    builds = app.subdivision.provider.topology_builds
    skin_mesh = app.skin.provider.surface_mesh
    for _ in range(3):  # pose steps patch SubD's positions
        app.skin.provider.set_pose({BoneId(1): _bone_pose(rng)})
        check()
    app.set_morph_weight(20, lids[1])
    check()
    # the rest <-> pose toggle while SubD is on: the skin surface is kept, SubD is patched, not rebuilt
    posed = dict(app.skin.provider.pose)
    app.skin.provider.set_pose({})
    check()
    assert app.skin.provider.surface_mesh is skin_mesh and app.subdivision.provider._mesh is skin_mesh
    assert all(skin_mesh.vertex_position(v) == p for v, p in morph_mix.evaluate(
        mesh, app.morph.provider.object_weights(app.scene.edit_object_id)).items())  # rest = the mix exactly
    app.skin.provider.set_pose(posed)
    check()
    assert app.subdivision.provider.topology_builds == builds
    # a topology edit and Undo / Redo with all three shown
    edge = mesh.all_edge_ids()[3]
    app.apply_mesh_change("split", lambda: mesh.split_edge(edge, 0.4) and None)
    check()
    app.dispatch_command(commands.UNDO)
    check()
    app.dispatch_command(commands.REDO)
    check()


def test_the_entry_surface_beside_the_morph_view_shows_mix_and_pose():
    app, mesh, lid, rng = _setup(4, seed=6)
    lids = _targets(app, 2, seed=8)
    base = app.scene.edit_object
    app.set_morph_weight(70, lids[0])
    pose = {BoneId(1): _bone_pose(rng)}
    app.skin.provider.set_pose(pose)
    assert app.key_press(TAB)  # the editing view: the target beside the base
    app.update_viewport(0.0)
    skin = app.skin.provider
    assert set(skin.entry_surfaces) == {base.id}
    assert skin.surface_mesh is None  # the editing view itself shows the target at rest (no layers)
    expected = skinning.evaluate(
        base.mesh, morph_mix.evaluate(base.mesh, app.morph.provider.object_weights(base.id)),
        app.scene.rig, pose, skinning.placement_of(base))
    entry = skin.entry_surfaces[base.id]
    assert all(entry.vertex_position(v) == p for v, p in expected.items())
    provider = app.viewport.surface_provider
    assert provider.entry_surfaces[base.id] is entry  # the later stage wins the merge
    assert app.viewport.entry_surface_render_meshes[base.id].mesh is entry
    # a weight step on the target updates the entry (mix + pose) in place
    app.set_morph_weight(30, lids[0])
    app.update_viewport(0.0)
    expected = skinning.evaluate(
        base.mesh, morph_mix.evaluate(base.mesh, app.morph.provider.object_weights(base.id)),
        app.scene.rig, pose, skinning.placement_of(base))
    entry = skin.entry_surfaces[base.id]
    assert all(entry.vertex_position(v) == p for v, p in expected.items())
    assert app.key_press(TAB)
    app.update_viewport(0.0)
    assert skin.entry_surfaces == {} and skin.surface_mesh is not None
    _assert_shown(app)


def test_picking_and_the_edit_mesh_stay_at_rest():
    app, mesh, lid, rng = _setup(3, seed=9)
    rest = mesh.export_state()
    app.skin.provider.set_pose({BoneId(1): _bone_pose(rng)})
    app.update_viewport(0.0)
    assert app.viewport.mesh is mesh and mesh.export_state() == rest  # no stage writes a scene mesh
    assert app.viewport.surface_provider.wire_follows_surface
    app.selection.mode = SelectionMode.VERTEX
    app.update_viewport(0.0)
    assert mesh.export_state() == rest


def test_a_scene_load_starts_at_rest(tmp_path):
    app, mesh, lid, rng = _setup(3, seed=10)
    app.skin.provider.set_pose({BoneId(1): _bone_pose(rng)})
    app.update_viewport(0.0)
    assert app.viewport.surface_provider is app.skin.provider
    path = tmp_path / "rigged.mirai.json"
    assert app.save_scene_file(path), app.status_message
    rig = app.scene.rig
    app.load_scene("file", scene_path=path)
    app.update_viewport(0.0)
    assert app.skin.provider.pose == {} and app.viewport.surface_provider is None  # rest after the load
    assert app.scene.rig == rig
    loaded = app.scene.mesh
    assert skinning.skin_layer(loaded) is not None and loaded.layer_items(skinning.skin_layer(loaded)) == mesh.layer_items(lid)
    app.load_scene("cube")  # a new scene from a primitive has no rig (the reserved slot is reset)
    assert app.scene.rig is None
