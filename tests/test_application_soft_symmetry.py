"""Soft Selection + Symmetry on the app path (AD-SYM-04 SS2; until SS2 refused, AD-020 §8, I-8).

Since SS2 the combination runs: symmetric Soft (weights and categories from
`soft_selection.symmetric_influence`; the asset acceptance is `test_symmetric_soft_selection.py`).
The settings are still read at `begin()` (review F2), so W armed → O → motion runs symmetric Soft
too, and the refusal that remains (D-2, a seed without partner) comes from there.
The soft ops have no symmetry backstop any more (`supports_symmetry` is the Core op's `True`).
The Symmetry Lab's MARK/BLOCK variants are in
`experiments/symmetry_lab/tests/test_app_lab_soft_selection.py`.

Mesh: two quads mirrored at x = 0 (as `test_application_symmetry.py`), shared seam edge on the plane.
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

from core.mesh import Mesh, SymmetryDefinition
from mirai.application import Application
from mirai.interaction.input import Input
from mirai.interaction.tools import MoveTool, RotateTool, ScaleTool
from mirai.soft_selection import SoftMoveOperation, SoftRotateOperation, SoftScaleOperation, SoftSettings

WIDTH, HEIGHT = 800, 600
W, E, R = Input("key", "w"), Input("key", "e"), Input("key", "r")
O = Input("key", "o")
ESC = Input("key", "ESCAPE")


def _mirrored_quads() -> tuple[Mesh, dict]:
    mesh = Mesh()
    ids = {
        "l0": mesh.add_vertex((-1.0, 0.0, 0.0)),
        "l1": mesh.add_vertex((-1.0, 1.0, 0.0)),
        "s0": mesh.add_vertex((0.0, 0.0, 0.0)),
        "s1": mesh.add_vertex((0.0, 1.0, 0.0)),
        "r0": mesh.add_vertex((1.0, 0.0, 0.0)),
        "r1": mesh.add_vertex((1.0, 1.0, 0.0)),
    }
    seam_edge = mesh.add_edge(ids["s0"], ids["s1"])
    mesh.add_face([ids["l0"], ids["s0"], ids["s1"], ids["l1"]])
    mesh.add_face([ids["s0"], ids["r0"], ids["r1"], ids["s1"]])
    mesh.symmetry_definition = SymmetryDefinition(
        plane_point=(0.0, 0.0, 0.0), plane_normal=(1.0, 0.0, 0.0), seam_edges=frozenset({seam_edge})
    )
    return mesh, ids


@pytest.fixture
def setup():
    app = Application()
    app.init_scene("cube")
    mesh, ids = _mirrored_quads()
    app.scene.mesh.load_state(mesh.export_state())
    app.viewport.on_topology_changed()
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    app.selection.set({ids["l0"]})
    app.viewport.on_selection_changed()
    return app, ids


def _state(app):
    return app.scene.mesh.export_state(), len(app.history)


def _mirrored(app, ids):
    mesh = app.scene.mesh
    for left, right in (("l0", "r0"), ("l1", "r1")):
        p, q = mesh.vertex_position(ids[left]), mesh.vertex_position(ids[right])
        assert q == (-p[0], p[1], p[2])
    assert mesh.vertex_position(ids["s0"])[0] == 0.0 and mesh.vertex_position(ids["s1"])[0] == 0.0


@pytest.mark.parametrize("key", [W, E, R], ids=["move", "rotate", "scale"])
def test_armed_then_soft_on_then_motion_runs_symmetric_soft(setup, key):
    """Review F2 order: W (soft off) → O → the first motion reaches begin() with soft on."""
    app, ids = setup
    app.selection.set({ids["l0"], ids["l1"]})  # two seeds: Rotate/Scale about their centre move them
    assert app.key_press(key)
    assert app.interaction_owner == "transform"
    assert app.key_press(O)  # allowed while a transform key is held
    assert app.soft_settings.enabled
    assert app.pointer_motion(300.0, 300.0, 12.0, 7.0)
    assert app.transform_interacting
    op = app.tool_manager.active_tool.operation
    assert "influence" in op.context.params and "symmetry" in op.context.params
    app.pointer_motion(310.0, 300.0, 9.0, -4.0)
    app.key_release(key)
    assert len(app.history) == 1
    _mirrored(app, ids)


@pytest.mark.parametrize("key", [W, E, R], ids=["move", "rotate", "scale"])
def test_soft_on_then_arm_runs_and_cancel_is_exact(setup, key):
    app, ids = setup
    app.key_press(O)
    before = _state(app)
    assert app.key_press(key)
    assert app.pointer_motion(300.0, 300.0, 12.0, 7.0)
    _mirrored(app, ids)
    assert app.key_press(ESC)
    assert _state(app) == before


def test_soft_on_seeds_on_both_sides_explicit_selection_wins(setup):
    """Manu 2026-10-14: a selection on both sides runs like plain W today - both selected
    partners take the same, unmirrored step."""
    app, ids = setup
    app.selection.set({ids["l0"], ids["r0"]})
    app.key_press(O)
    mesh = app.scene.mesh
    l0, r0 = mesh.vertex_position(ids["l0"]), mesh.vertex_position(ids["r0"])
    assert app.key_press(W)
    assert app.pointer_motion(300.0, 300.0, 12.0, 7.0)
    assert not app.tool_manager.active_tool.operation.context.params["symmetry"]["mirrored_vertex_ids"]
    app.key_release(W)
    assert len(app.history) == 1
    dl = [a - b for a, b in zip(mesh.vertex_position(ids["l0"]), l0)]
    dr = [a - b for a, b in zip(mesh.vertex_position(ids["r0"]), r0)]
    assert dl == dr and any(dl)


def test_soft_off_under_symmetry_is_todays_symmetric_move(setup):
    app, ids = setup
    assert app.key_press(W)
    app.pointer_motion(300.0, 300.0, 12.0, 7.0)
    assert app.transform_interacting
    app.key_release(W)
    assert len(app.history) == 1
    left = app.scene.mesh.vertex_position(ids["l0"])
    right = app.scene.mesh.vertex_position(ids["r0"])
    assert right[0] == -left[0]  # the partner mirrored: the symmetric Move is untouched


@pytest.mark.parametrize(
    "tool_cls,op_cls",
    [(MoveTool, SoftMoveOperation), (RotateTool, SoftRotateOperation), (ScaleTool, SoftScaleOperation)],
)
def test_any_host_the_tool_hands_the_op_weights_and_categories(setup, tool_cls, op_cls):
    """Without `Application`: the tool builds the symmetric field itself; the soft op runs it."""
    app, ids = setup
    tool = tool_cls()
    tool.activate()
    soft = SoftSettings(enabled=True, world_radius=2.5)
    tool.begin(scene=app.scene, camera=app.camera, vertex_ids={ids["l0"]}, soft=soft)
    op = tool.operation
    assert type(op) is op_cls and op_cls.supports_symmetry is True
    symmetry = op.context.params["symmetry"]
    assert symmetry["mirrored_vertex_ids"] == {ids["r0"], ids["r1"]}
    assert symmetry["falloff_seam_vertex_ids"] == {ids["s0"], ids["s1"]}
    assert op.weights[ids["l0"]] == op.weights[ids["r0"]] == 1.0
    assert op.weights[ids["l1"]] == op.weights[ids["r1"]] < 1.0
    tool.update(dx=15.0, dy=6.0, width=WIDTH, height=HEIGHT)
    _mirrored(app, ids)
    tool.commit()
    assert len(app.history) == 1
