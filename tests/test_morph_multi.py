"""AD-025 Phase 4: several morph targets per mesh, their evaluation, and morph + SubD together.

Headless (TraceStore). Covers the Phase 4 Definition of Done: the lifecycle of several targets with exact
Undo / Redo and the current target; save -> load bit-exact; the editing view per target (= b + dᵢ, the
view switches with the target); the mix b + Σ wᵢ·dᵢ through a randomized oracle (weight steps in random
order, base edits, offset writes, topology edits, layer add / remove / reorder, Undo / Redo) - bit-exact
against `morph_mix.evaluate`, within 1e-12 of an independent `math.fsum` evaluation, and bit-identical
whatever the order of the weight changes; morph + SubD = SubD of the mixed cage (reference computation);
every Phase 5 operation with three app targets dialled in; Apply transform and mirror copy with several
targets; the stage chain's slot rules; keys, HUD and the Morph Lab bridge.
"""

from __future__ import annotations

import itertools
import json
import math
import random

import pytest

import tests._bootstrap  # noqa: F401

from core import Mesh, SelectionMode
from mirai import morph_mix, morph_targets
from mirai.interaction import commands
from mirai.interaction.input import MORPH_CONTEXT, Input
from mirai.surface_chain import ChainedSurface
from tests.mesh_invariants import assert_layer_invariants
from tests.test_application_delete_dissolve import _app, _grid_vertex, _select

V, E, F = SelectionMode.VERTEX, SelectionMode.EDGE, SelectionMode.FACE


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


CTRL_N, CTRL_SHIFT_N, ALT_SHIFT_N = _key("n", "ctrl"), _key("n", "ctrl", "shift"), _key("n", "alt", "shift")
NEXT, PREV, TAB, N, PLUS = _key("n", "shift"), _key("n", "alt"), _key("tab"), _key("n"), _key("plus")
CTRL_Z, CTRL_Y = _key("z", "ctrl"), _key("y", "ctrl")


def _content(state: dict) -> dict:
    return {k: v for k, v in state.items() if not k.endswith("_counter")}


def _targets(app, count: int = 3, seed: int = 1, every: int = 1) -> list:
    """`count` targets made through the keys, each with random offsets on every `every`-th point."""
    mesh = app.scene.mesh
    for _ in range(count):
        assert app.key_press(CTRL_N), app.status_message
    lids = morph_targets.morph_target_ids(mesh)
    rng = random.Random(seed)
    for k, lid in enumerate(lids):
        for i, v in enumerate(sorted(mesh.all_vertex_ids(), key=int)):
            if (i + k) % every == 0:
                mesh.set_layer_value(lid, v, (rng.uniform(-0.2, 0.2), rng.uniform(-0.2, 0.2), rng.uniform(-0.2, 0.2)))
    return lids


def _shown_equals_definition(app) -> None:
    """The edit object's shown surface is exactly `evaluate(b, weights)` with the base's topology."""
    app.update_viewport(0.0)
    oid = app.morph_document_object.id
    mesh = app.morph_document_object.mesh
    weights = app.morph.provider.object_weights(oid)
    surface = app.morph.provider.surface_mesh
    if not weights:
        assert surface is None or all(
            surface.vertex_position(v) == mesh.vertex_position(v) for v in mesh.all_vertex_ids())
        return
    assert surface is not None
    expected = morph_mix.evaluate(mesh, weights)
    assert sorted(surface.all_vertex_ids()) == sorted(mesh.all_vertex_ids())
    assert {f: surface.face_vertices(f) for f in surface.all_face_ids()} == {
        f: mesh.face_vertices(f) for f in mesh.all_face_ids()}
    for v, p in expected.items():
        assert surface.vertex_position(v) == p, v


# -- keys -----------------------------------------------------------------------------------------


def test_the_switch_keys_are_free_and_avoid_the_lab_keys():
    app = _app()
    for value in (NEXT, PREV):
        assert app.bindings.command_for(value) is None
    assert app.bindings.command_for(NEXT, MORPH_CONTEXT) == commands.MORPH_NEXT
    assert app.bindings.command_for(PREV, MORPH_CONTEXT) == commands.MORPH_PREVIOUS
    import importlib.util
    import sys
    from pathlib import Path

    lab = Path(__file__).resolve().parents[1] / "experiments"
    sys.path.insert(0, str(lab))
    try:
        if importlib.util.find_spec("morph_lab") is None:
            pytest.skip("morph_lab not importable")
        from morph_lab.lab_app import LAB_KEYS
    finally:
        sys.path.remove(str(lab))
    assert not {e.input for e in LAB_KEYS} & {e.input for e in morph_targets.MORPH_KEYS}


def test_main_window_keys_do_not_take_the_switch_keys():
    import main

    app = _app()
    for inp in (NEXT, PREV):
        assert main.window_command(app, inp) is None


# -- lifecycle --------------------------------------------------------------------------------------


def test_several_targets_lifecycle_with_exact_undo_redo_and_the_current_target():
    app = _app(3)
    mesh = app.scene.mesh
    oid = app.scene.edit_object_id
    states = [mesh.export_state()]
    for _ in range(3):
        assert app.key_press(CTRL_N)
        states.append(mesh.export_state())
        assert app.morph_current_target == mesh.point_layer_ids()[-1]  # a new target becomes current
    assert [mesh.point_layer_info(l).name for l in mesh.point_layer_ids()] == ["Target 1", "Target 2", "Target 3"]
    lids = mesh.point_layer_ids()
    assert app.key_press(NEXT) and app.morph_current_target == lids[0]  # wraps around
    assert app.key_press(PREV) and app.morph_current_target == lids[2]
    assert app.key_press(PREV) and app.morph_current_target == lids[1]
    assert app.key_press(CTRL_SHIFT_N)  # renames the current one
    assert mesh.point_layer_info(lids[1]).name == morph_targets.RENAME_CYCLE[0]
    states.append(mesh.export_state())
    v = mesh.all_vertex_ids()[4]
    assert app.apply_mesh_change("offset", lambda: mesh.set_layer_value(lids[1], v, (0.1, 0.2, 0.3)))
    states.append(mesh.export_state())
    app.set_morph_weight(40)
    assert app.morph.provider.weight(oid, lids[1]) == 40
    assert app.key_press(ALT_SHIFT_N)  # deletes the current one, its weight goes, the next is current
    assert mesh.point_layer_ids() == [lids[0], lids[2]] and app.morph_current_target == lids[2]
    assert lids[1] not in app.morph.provider.weights.get(oid, {})
    states.append(mesh.export_state())
    assert len(app.history) == 6
    for state in reversed(states[:-1]):
        assert app.key_press(CTRL_Z)
        assert _content(mesh.export_state()) == _content(state)
        assert_layer_invariants(mesh)
    assert app.morph_current_target is None
    for state in states[1:]:
        assert app.key_press(CTRL_Y)
        assert _content(mesh.export_state()) == _content(state)
    assert app.morph.provider.weight(oid, lids[1]) == 0  # the weight did not come back with the Redo


def test_the_cap_refuses_one_more_target(monkeypatch):
    import mirai.controllers.morph as morph_controller

    monkeypatch.setattr(morph_controller, "MORPH_MAX_TARGETS", 3)
    app = _app(2)
    for _ in range(3):
        assert app.key_press(CTRL_N)
    history = len(app.history)
    assert app.key_press(CTRL_N) is False
    assert "3 targets" in app.status_message and len(app.history) == history
    assert morph_targets.MAX_TARGETS >= 50  # the budget case of AD-025 §17 fits under the cap


def test_switching_with_one_or_no_target_says_so():
    app = _app(2)
    assert app.key_press(NEXT) is False and "none" in app.status_message
    app.key_press(CTRL_N)
    assert app.key_press(NEXT) is False and "only target" in app.status_message


def test_weights_are_per_target_view_state_and_tap_n_per_target(tmp_path):
    app = _app(3)
    lids = _targets(app, 3)
    oid = app.scene.edit_object_id
    app.set_morph_weight(30, lids[0])
    app.set_morph_weight(70, lids[2])
    assert app.morph.provider.object_weights(oid) == {lids[0]: 30, lids[2]: 70}
    assert app.morph_current_target == lids[2] and app.morph_weight == 70
    assert app.key_press(N) and app.key_release(N)  # tap: the current target 70 -> 0
    assert app.morph.provider.object_weights(oid) == {lids[0]: 30}
    assert app.key_press(N) and app.key_release(N)
    assert app.morph.provider.object_weights(oid) == {lids[0]: 30, lids[2]: 70}
    assert app.key_press(PLUS) and app.morph_weight == 80
    assert len(app.history) == 3  # only the three "New morph target" steps
    path = tmp_path / "w.mirai.json"
    app.save_scene_file(path) if hasattr(app, "save_scene_file") else None
    data = json.loads(json.dumps(app.scene.mesh.export_state()))
    assert "weights" not in json.dumps(data)  # weights are not document state


# -- save / load ------------------------------------------------------------------------------------


def test_several_targets_are_bit_exact_after_save_and_load(tmp_path):
    from core.serialization import scene_from_json, scene_to_json

    app = _app(4)
    lids = _targets(app, 4, seed=5, every=3)
    mesh = app.scene.mesh
    mesh.set_point_layer_order([lids[2], lids[0], lids[3], lids[1]])
    text = scene_to_json(app.scene)
    assert json.loads(text)["version"] == 5
    loaded = scene_from_json(text)
    assert loaded.mesh.export_state() == mesh.export_state()
    assert scene_to_json(loaded) == text  # the JSON text too (order-sensitive)
    for lid in lids:
        assert loaded.mesh.layer_items(lid) == mesh.layer_items(lid)


def test_save_with_the_view_open_writes_every_target(tmp_path):
    app = _app(3)
    lids = _targets(app, 3)
    assert app.key_press(TAB)
    scene = app._morph.document_scene()
    state = scene.edit_object.mesh.export_state()
    assert [entry["id"] for entry in state["point_layers"]] == [int(l) for l in lids]


# -- editing view per target ------------------------------------------------------------------------


def _view_is_base_plus(app, lid) -> None:
    view = app._morph.view
    base, mesh = view.base_mesh, view.view_mesh
    assert view.lid == lid
    for v in base.all_vertex_ids():
        b, d = base.vertex_position(v), base.layer_value(lid, v)
        assert tuple(mesh.vertex_position(v)) == (b[0] + d[0], b[1] + d[1], b[2] + d[2]), v


def test_the_editing_view_shows_and_writes_the_current_target():
    app = _app(4)
    lids = _targets(app, 3, seed=2, every=2)
    base = app.scene.edit_object.mesh
    assert app.key_press(NEXT)  # Target 1
    assert app.key_press(TAB)
    _view_is_base_plus(app, lids[0])
    for step, lid in ((NEXT, lids[1]), (NEXT, lids[2]), (PREV, lids[1])):
        assert app.key_press(step), app.status_message
        _view_is_base_plus(app, lid)
        assert lid == app.morph_current_target
    others = {l: dict(base.layer_items(l)) for l in lids if l != lids[1]}
    v = _grid_vertex(app, 2, 2)
    _select(app, V, {v})
    assert app.key_press(_key("w"))
    app.pointer_motion(400, 300, 12.0, -7.0)
    app.key_release(_key("w"))
    assert base.layer_value(lids[1], v) != (0.0, 0.0, 0.0)
    assert {l: dict(base.layer_items(l)) for l in others} == others  # only the current target written
    _view_is_base_plus(app, lids[1])
    assert app.key_press(CTRL_Z)
    _view_is_base_plus(app, lids[1])
    assert app.key_press(TAB)


# -- the mix: randomized oracle ----------------------------------------------------------------------


def _fsum_mix(base: Mesh, weights: dict, v) -> tuple:
    b = base.vertex_position(v)
    return tuple(
        math.fsum([b[k]] + [w / 100.0 * base.layer_value(lid, v)[k] for lid, w in weights.items() if w > 0])
        for k in range(3))


def test_the_mix_equals_the_definition_through_random_edits():
    """Weight steps on random targets in random order, base moves, offset writes (per element and bulk),
    target add / remove / reorder, deletions, the Phase 5 topology edits, Undo / Redo: after every step
    the surface is bit-exact `evaluate` (the rule in its summation order) and within 1e-12 of an
    independent fsum; a fresh evaluation of the same inputs is bit-identical (no drift)."""
    from core import PointLayerInfo
    from core.operations.collapse import collapse_elements

    app = _app(4)
    mesh = app.scene.mesh
    lids = [mesh.add_point_layer(PointLayerInfo(f"T{k}")) for k in range(4)]
    provider = morph_targets.MorphSurfaceProvider(lambda: app.scene)
    oid = app.scene.edit_object_id
    rng = random.Random(11)

    def check():
        provider.sync(mesh, app.selection)
        weights = provider.object_weights(oid)
        surface = provider.surface_mesh
        if not weights:
            assert surface is None
            return
        expected = morph_mix.evaluate(mesh, weights)
        assert sorted(surface.all_vertex_ids()) == sorted(mesh.all_vertex_ids())
        assert {e: (surface.edge_vertices(e), surface.edge_faces(e)) for e in surface.all_edge_ids()} == {
            e: (mesh.edge_vertices(e), mesh.edge_faces(e)) for e in mesh.all_edge_ids()}
        for v in mesh.all_vertex_ids():
            p = surface.vertex_position(v)
            assert p == expected[v], v
            assert max(abs(a - b) for a, b in zip(p, _fsum_mix(mesh, weights, v))) <= 1e-12

    builds = drops = 0
    last = None
    for step in range(260):
        ids = mesh.all_vertex_ids()
        live = morph_targets.morph_target_ids(mesh)
        op = rng.randrange(13)
        if op <= 2 and live:
            provider.set_weight(oid, rng.randrange(0, 101), rng.choice(live))
        elif op == 3:
            v = rng.choice(ids)
            mesh.set_vertex_position(v, tuple(c + rng.uniform(-0.1, 0.1) for c in mesh.vertex_position(v)))
        elif op == 4 and live:
            v = rng.choice(ids)
            d = (0.0, 0.0, 0.0) if rng.random() < 0.3 else tuple(rng.uniform(-1, 1) for _ in range(3))
            app.apply_mesh_change("offset", lambda: mesh.set_layer_value(rng.choice(live), v, d))
        elif op == 5:
            app.apply_mesh_change("map", lambda: mesh.map_vector_layers(((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0))))
        elif op == 6 and len(mesh.all_face_ids()) > 4:
            face = rng.choice(mesh.all_face_ids())
            app.apply_mesh_change("delete", lambda: mesh.delete_faces([face]))
        elif op == 7 and app.history.can_undo():
            app.dispatch_command(commands.UNDO if rng.random() < 0.6 else commands.REDO)
        elif op == 8:
            edge = rng.choice(mesh.all_edge_ids())
            app.apply_mesh_change("split", lambda: mesh.split_edge(edge, rng.uniform(0.2, 0.8)) and None)
        elif op == 9:
            face = rng.choice(mesh.all_face_ids())
            a, b, c = mesh.face_vertices(face)[:3]
            p = tuple(sum(mesh.vertex_position(x)[k] for x in (a, b, c)) / 3.0 for k in range(3))
            app.apply_mesh_change(
                "cut", lambda: mesh.split_face(face, a, c, [p], origins=[((a, 0.25), (b, 0.5), (c, 0.25))]) and None)
        elif op == 10:
            edge = rng.choice(mesh.all_edge_ids())
            try:
                app.apply_mesh_change("collapse", lambda: collapse_elements(mesh, mesh.edge_vertices(edge)) and None)
            except Exception:
                pass  # a refused collapse leaves everything as it was
        elif op == 11:
            if live and rng.random() < 0.4:
                app.apply_mesh_change("remove", lambda: mesh.remove_point_layer(rng.choice(live)))
            else:
                app.apply_mesh_change("add", lambda: mesh.add_point_layer(PointLayerInfo(f"N{step}")) and None)
        elif op == 12 and len(live) > 1:
            order = live[:]
            rng.shuffle(order)
            app.apply_mesh_change("order", lambda: mesh.set_point_layer_order(order))
        if not provider.object_weights(oid) and live and rng.random() < 0.5:
            provider.set_weight(oid, 50, rng.choice(live))
        check()
        if not morph_targets.morph_target_ids(mesh):
            drops += 1  # the last target went: the surface goes with it, the next one is new
        elif provider.surface_mesh is not None and provider.surface_mesh is not last:
            builds += 1
            last = provider.surface_mesh
    assert builds <= drops + 1  # patched in place, rebuilt only after the mesh lost every target
    fresh = morph_targets.MorphSurfaceProvider(lambda: app.scene)
    for lid, w in provider.object_weights(oid).items():
        fresh.set_weight(oid, w, lid)
    fresh.sync(mesh, app.selection)
    if fresh.surface_mesh is not None:
        assert fresh.surface_mesh.export_state()["vertices"] == provider.surface_mesh.export_state()["vertices"]


def test_the_mix_is_independent_of_the_order_of_weight_changes():
    """The same weights reached in different orders and through long random walks give bit-identical
    surfaces (drift guard by construction: every touched point is recomputed from b, w, d)."""
    app = _app(5)
    lids = _targets(app, 4, seed=9, every=2)
    mesh = app.scene.mesh
    oid = app.scene.edit_object_id
    target = {lids[0]: 37, lids[1]: 100, lids[2]: 3, lids[3]: 64}
    results = []
    rng = random.Random(3)
    for order in list(itertools.permutations(lids))[:6]:
        provider = morph_targets.MorphSurfaceProvider(lambda: app.scene)
        provider.set_weight(oid, 50, lids[1])
        provider.sync(mesh, app.selection)
        for _ in range(150):  # a random walk first
            provider.set_weight(oid, rng.randrange(0, 101), rng.choice(lids))
            provider.sync(mesh, app.selection)
        for lid in order:
            provider.set_weight(oid, target[lid], lid)
            provider.sync(mesh, app.selection)
        results.append(provider.surface_mesh.export_state()["vertices"])
    assert all(r == results[0] for r in results)
    expected = morph_mix.evaluate(mesh, target)
    assert results[0] == {int(v): list(p) for v, p in expected.items()} or all(
        tuple(results[0][int(v)]) == p for v, p in expected.items())


def test_a_weight_step_touches_only_that_targets_points():
    app = _app(5)
    mesh = app.scene.mesh
    lids = _targets(app, 3, seed=4, every=4)
    oid = app.scene.edit_object_id
    for lid in lids:
        app.set_morph_weight(50, lid)
    app.update_viewport(0.0)
    provider = app.morph.provider
    app.set_morph_weight(60, lids[1])
    app.update_viewport(0.0)
    assert 0 < provider.last_changed <= len(mesh.layer_items(lids[1]))
    _shown_equals_definition(app)
    assert provider.object_weights(oid) == {lids[0]: 50, lids[1]: 60, lids[2]: 50}


def test_one_target_gives_the_phase3_values_bit_for_bit():
    rng = random.Random(1)
    for _ in range(500):
        b = tuple(rng.uniform(-3, 3) for _ in range(3))
        d = tuple(rng.choice((0.0, -0.0, rng.uniform(-1, 1))) for _ in range(3))
        w = rng.randrange(1, 101)
        old = (b[0] + d[0], b[1] + d[1], b[2] + d[2]) if w == 100 else tuple(bi + (w / 100.0) * di for bi, di in zip(b, d))
        assert morph_mix.mix_position(b, [(morph_mix.factor(w), d)]) == old


# -- morph + SubD (H5b) -------------------------------------------------------------------------------


def _subd_reference(app, weights) -> list:
    """SubD of the mixed cage, computed from scratch: a cage mesh at `evaluate` positions, its own
    `SubdSurface`, the shown level's stencils over its control positions."""
    from mirai.subdivision.catmull_clark import SubdSurface

    base = app.morph_document_object.mesh
    mixed = morph_mix.evaluate(base, weights)
    state = morph_mix.rest_state(base)
    for v, p in mixed.items():
        state["vertices"][int(v)] = list(p)
    cage = Mesh.from_state(state)
    surface = SubdSurface(cage)
    level = surface.level(app.subdivision.level)
    control = [tuple(cage.vertex_position(v)) for v in surface.topology.vertex_ids]
    return level.apply_full(control)


def _assert_subd_of_the_mix(app) -> None:
    app.update_viewport(0.0)
    provider = app.subdivision.provider
    weights = app.morph.provider.object_weights(app.morph_document_object.id)
    expected = _subd_reference(app, weights)
    got = provider.derived_positions()
    assert len(got) == len(expected)
    assert max(abs(a - b) for p, q in zip(got, expected) for a, b in zip(p, q)) <= 1e-12
    surface = provider.surface_mesh
    ids = provider.derived_elements()[1]
    assert app.viewport.surface_render_mesh.mesh is surface
    for i, vid in enumerate(ids):
        assert surface.vertex_position(vid) == got[i]


def test_morph_and_subd_show_together_as_subd_of_the_mixed_cage():
    app = _app(4)
    lids = _targets(app, 3, seed=6, every=2)
    app.set_morph_weight(40, lids[0])
    app.set_morph_weight(100, lids[2])
    assert app.subdivision.set_view("cage"), app.status_message
    app.update_viewport(0.0)
    assert isinstance(app.viewport.surface_provider, ChainedSurface)
    assert not app.morph.blocked and "hidden" not in app.morph_status_text()
    assert app.subdivision.provider._mesh is app.morph.provider.surface_mesh  # SubD reads the mixed cage
    _assert_subd_of_the_mix(app)
    builds = app.subdivision.provider.topology_builds
    for w in (55, 56, 0, 90):  # weight steps patch SubD's positions (stencils), no rebuild
        app.set_morph_weight(w, lids[1])
        _assert_subd_of_the_mix(app)
    assert app.subdivision.provider.topology_builds == builds
    # a base edit, a topology edit and Undo / Redo with both shown
    mesh = app.scene.mesh
    v = _grid_vertex(app, 2, 2)
    app.apply_mesh_change("move", lambda: mesh.set_vertex_position(v, (0.1, 0.2, 0.3)) or {v})
    _assert_subd_of_the_mix(app)
    edge = mesh.vertex_edges(v)[0]
    app.apply_mesh_change("split", lambda: mesh.split_edge(edge, 0.5) and None)
    _assert_subd_of_the_mix(app)
    assert app.key_press(CTRL_Z)
    _assert_subd_of_the_mix(app)
    assert app.key_press(CTRL_Y)
    _assert_subd_of_the_mix(app)
    # the wire: SubD draws its own cage lines at the mixed positions; the viewport's wire is off
    assert app.viewport.wire_drawn() is False
    cage = app.subdivision.lines.segments
    app.subdivision.lines.sync(app.viewport.mesh, app.selection)
    mixed = morph_mix.evaluate(mesh, app.morph.provider.object_weights(app.scene.edit_object_id))
    assert set(app.subdivision.provider.control_positions()) == set(mixed.values())
    assert cage is not None
    # picking and selection stay on the rest cage
    assert app.viewport.mesh is mesh
    _select(app, V, {v})
    app.viewport.on_selection_changed()
    app.update_viewport(0.0)
    assert any(tuple(p) == mesh.vertex_position(v) for layer in app.viewport.point_positions.values() for p in layer)


def test_subd_alone_and_the_mix_alone_hold_the_slot_themselves():
    app = _app(3)
    app.update_viewport(0.0)
    assert app.subdivision.set_view("cage")
    app.update_viewport(0.0)
    assert app.viewport.surface_provider is app.subdivision.provider  # unchanged without targets
    lids = _targets(app, 2)
    app.update_viewport(0.0)
    # SubD with targets at 0 %: the chain feeds SubD the (rest) mix so a weight step never rebuilds it
    assert isinstance(app.viewport.surface_provider, ChainedSurface)
    _assert_subd_of_the_mix(app)
    app.set_morph_weight(30, lids[0])
    _assert_subd_of_the_mix(app)
    app.subdivision.set_view("off")
    app.update_viewport(0.0)
    assert app.viewport.surface_provider is app.morph.provider
    app.set_morph_weight(0, lids[0])
    app.update_viewport(0.0)
    assert app.viewport.surface_provider is None


def test_a_foreign_host_keeps_the_slot_and_both_say_so():
    class Foreign:
        surface_mesh = None
        dirty = False

        def sync(self, mesh, selection):
            return set()

    app = _app(3)
    lids = _targets(app, 2)
    app.update_viewport(0.0)
    other = Foreign()
    app.viewport.set_surface_provider(other)
    app.set_morph_weight(50, lids[0])
    app.update_viewport(0.0)
    assert app.viewport.surface_provider is other and app.morph.blocked
    assert "another host" in app.morph_status_text()
    assert app.subdivision.set_view("cage") is False


def test_morph_and_subd_on_the_editing_view_and_the_entry_beside_it():
    app = _app(4)
    lids = _targets(app, 2, seed=8)
    base = app.scene.edit_object
    app.set_morph_weight(70, lids[0])
    app.set_morph_weight(20, lids[1])
    app.subdivision.set_view("cage")
    assert app.key_press(TAB)
    app.update_viewport(0.0)
    provider = app.morph.provider
    assert set(provider.entry_surfaces) == {base.id}  # the base beside the view shows the mix
    entry = provider.entry_surfaces[base.id]
    expected = morph_mix.evaluate(base.mesh, provider.object_weights(base.id))
    assert all(entry.vertex_position(v) == p for v, p in expected.items())
    assert app.subdivision.provider._mesh is app.scene.edit_object.mesh  # SubD of the view (no layers)
    assert app.key_press(TAB)


# -- Phase 5 operations with three app targets dialled in -------------------------------------------


def _phase5_cases():
    from tests import test_layer_topology_ops as ops

    return [(key, symmetric) for key in ops.RULE_FIXTURES for symmetric in (False, True)]


@pytest.mark.parametrize("key,symmetric", _phase5_cases(), ids=lambda x: str(x))
def test_every_phase5_operation_with_three_targets_in_the_app(key, symmetric):
    from tests import test_layer_topology_ops as ops
    from tests.test_symmetric_ops import make_app

    plain, sym, rule = ops.RULE_FIXTURES[key]
    app = make_app("subd_cube") if symmetric else _app(3)
    lids = []
    for _ in range(3):
        assert app.key_press(CTRL_N), app.status_message
    mesh = app.scene.mesh
    lids = mesh.point_layer_ids()
    # the values as in Phase 5's fixture (two dense, one sparse; mirrored on the symmetric mesh), written
    # into the app's own targets
    scratch = Mesh.from_state(morph_mix.rest_state(mesh))
    scratch.symmetry_definition = mesh.symmetry_definition
    ops.add_layers(scratch, seed=sum(map(ord, str(key))))
    for lid, src in zip(lids, scratch.point_layer_ids()):
        for v, d in scratch.layer_items(src):
            mesh.set_layer_value(lid, v, d)
    app.set_morph_weight(60, lids[0])
    app.set_morph_weight(25, lids[2])
    command = (sym if symmetric else plain)(app)
    _shown_equals_definition(app)
    before = mesh.export_state()
    ref = Mesh.from_state(before)
    info: dict = {}
    ops._run(app, command, info)
    assert rule(ref, mesh, info) >= 1
    assert_layer_invariants(mesh)
    _shown_equals_definition(app)
    ops._assert_undo_redo_exact(app, before)
    _shown_equals_definition(app)
    assert app.key_press(CTRL_Z)
    _shown_equals_definition(app)


def test_the_knife_with_three_targets_in_the_app():
    from tests import test_layer_topology_ops as ops
    from tests.test_application_knife import ENTER, LMB

    app = ops._knife_app(False)
    for _ in range(3):
        assert app.key_press(CTRL_N)
    mesh = app.scene.mesh
    lids = mesh.point_layer_ids()
    rng = random.Random(2)
    for k, lid in enumerate(lids):
        for v in mesh.all_vertex_ids():
            if k < 2 or int(v) % 3 == 0:
                mesh.set_layer_value(lid, v, tuple(rng.uniform(-0.3, 0.3) for _ in range(3)))
    app.set_morph_weight(50, lids[1])
    app.set_morph_weight(80, lids[2])
    _shown_equals_definition(app)
    before = mesh.export_state()
    ref = Mesh.from_state(before)
    face = max(mesh.all_face_ids(), key=lambda f: min(mesh.vertex_position(v)[0] for v in mesh.face_vertices(f)))
    edges = mesh.face_edges(face)
    pa = [mesh.vertex_position(v) for v in mesh.face_vertices(face)]

    def inside(u, w):
        return tuple(pa[0][k] * (1 - u) * (1 - w) + pa[1][k] * u * (1 - w) + pa[2][k] * u * w + pa[3][k] * (1 - u) * w
                     for k in range(3))

    def on_edge(e, t):
        a, b = mesh.edge_vertices(e)
        p0, p1 = mesh.vertex_position(a), mesh.vertex_position(b)
        return tuple(p0[k] + t * (p1[k] - p0[k]) for k in range(3))

    app.selection.clear()
    assert app.key_press(_key("c")), app.status_message
    for p in (on_edge(edges[0], 0.35), inside(0.45, 0.4), inside(0.6, 0.65), on_edge(edges[2], 0.4)):
        sx, sy = ops._screen_of(app, p)
        app.pointer_motion(sx, sy)
        app.pointer_press(LMB, sx, sy)
        assert app.pointer_release("LEFT", sx, sy), app.status_message
    path = [dict(p) for p in app._knife.tool.path]
    assert app.key_press(ENTER), app.status_message
    ops.knife_rule(ref, mesh, {"path": path, "symmetric": False})
    _shown_equals_definition(app)
    ops._assert_undo_redo_exact(app, before)
    _shown_equals_definition(app)


# -- Apply transform and mirror copy with several targets -------------------------------------------


def test_apply_transform_maps_every_target_and_keeps_the_world_mix():
    from core import ObjectTransform
    from mirai import object_space

    app = _app(3)
    lids = _targets(app, 3, seed=3, every=2)
    obj = app.scene.edit_object
    weights = {lids[0]: 30, lids[1]: 100, lids[2]: 65}
    for lid, w in weights.items():
        app.set_morph_weight(w, lid)
    obj.transform = ObjectTransform(
        translation=(0.3, -0.2, 0.1), rotation=object_space.axis_angle_rotation((0.0, 1.0, 0.0), 0.7), scale=1.5)
    app._objects.placement_changed()
    world_before = {v: object_space.to_world(obj, p) for v, p in morph_mix.evaluate(obj.mesh, weights).items()}
    state = obj.mesh.export_state()
    app.key_press(_key("4"))
    app.selection.objects = {obj.id}
    assert app.dispatch_command(commands.APPLY_TRANSFORM), app.status_message
    after = morph_mix.evaluate(obj.mesh, weights)
    for v, p in after.items():
        assert max(abs(a - b) for a, b in zip(object_space.to_world(obj, p), world_before[v])) <= 1e-12
    assert app.key_press(CTRL_Z)
    assert _content(obj.mesh.export_state()) == _content(state)


def test_mirror_copy_carries_every_target():
    from tests.test_mirror_pairs import _placed_sphere

    app = _app()
    source = _placed_sphere(app)
    app.key_press(_key("4"))
    app.selection.objects = {source.id}
    app.key_press(_key("1"))
    # the targets on the sphere: through the Core API (the sphere is not the edit object of the keys)
    from core import PointLayerInfo

    rng = random.Random(4)
    for k in range(3):
        lid = source.mesh.add_point_layer(PointLayerInfo(f"T{k}"))
        for v in source.mesh.all_vertex_ids()[k::2]:
            source.mesh.set_layer_value(lid, v, tuple(rng.uniform(-1, 1) for _ in range(3)))
    app.key_press(_key("4"))
    app.selection.objects = {source.id}
    copy = app.mirror_copy("X")
    assert copy is not None, app.status_message
    src, dst = source.mesh, copy.mesh
    assert len(dst.point_layer_ids()) == 3
    index = {v: i for i, v in enumerate(sorted(src.all_vertex_ids()))}
    new_ids = sorted(dst.all_vertex_ids())
    for ls, ld in zip(src.point_layer_ids(), dst.point_layer_ids()):
        assert dict(dst.layer_items(ld)) == {new_ids[index[v]]: (-x, y, z) for v, (x, y, z) in src.layer_items(ls)}
    weights = {ld: 40 + 20 * i for i, ld in enumerate(dst.point_layer_ids())}
    src_weights = {ls: 40 + 20 * i for i, ls in enumerate(src.point_layer_ids())}
    mixed_src, mixed_dst = morph_mix.evaluate(src, src_weights), morph_mix.evaluate(dst, weights)
    for v, p in mixed_src.items():
        assert mixed_dst[new_ids[index[v]]] == (-p[0], p[1], p[2])  # the mix mirrors bit for bit
    assert_layer_invariants(dst)


# -- HUD and the bridge ---------------------------------------------------------------------------------


def test_the_hud_lists_the_targets_with_the_current_one_marked():
    from hud import hud_rows, hud_state, key_hints

    app = _app(2)
    app.key_press(CTRL_N)
    rows = {r.label: r for r in hud_rows(hud_state(app), key_hints(app.bindings))}
    assert "Targets" not in rows and rows["Morph"].value == "Target 1 · 0 % · base"
    app.key_press(CTRL_N)
    app.set_morph_weight(40)
    rows = {r.label: r for r in hud_rows(hud_state(app), key_hints(app.bindings))}
    assert rows["Morph"].value == "Target 2 · 40 % · base · 2/2"
    assert rows["Targets"].value == "Target 1 0 · [Target 2 40]" and rows["Targets"].keys == "Shift+N/Alt+N"
    for _ in range(10):
        app.key_press(CTRL_N)
    text = app.morph_targets_text()
    assert "[Target 12 0]" in text and "more" in text


def test_the_bridge_sends_the_current_target(tmp_path):
    from morph_bridge import send_to_morph_lab

    app = _app(3)
    lids = _targets(app, 3, seed=7)
    assert app.key_press(PREV)  # Target 2
    sent = []
    path = send_to_morph_lab(app, directory=tmp_path, launcher=sent.append)
    data = json.loads(path.read_text(encoding="utf-8"))
    layers = data["objects"][0]["mesh"]["point_layers"]
    assert [entry["id"] for entry in layers] == [int(lids[1])]
    assert app.scene.mesh.point_layer_ids() == lids  # the scene keeps all of them
