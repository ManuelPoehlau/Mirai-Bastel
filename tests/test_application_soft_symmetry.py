"""Soft Selection + Symmetry on the app path: refused visibly, fail-closed (AD-020 §8, E3, F2).

Production reaches this since AD-SYM-04 A1 (Shift+S sets the definition, the A1 case is in
`test_application_symmetry_cycle.py`); the Symmetry Lab too (its MARK/BLOCK variants are in
`experiments/symmetry_lab/tests/test_app_lab_soft_selection.py`).
The refusal is authoritative at `begin()` - that is where the sticky settings are read, so
W armed → O → motion cannot slip through (review F2) - and an early feedback at the key press.
The soft ops keep the `params["symmetry"]` `ValueError` backstop for any other host.

Mesh: two quads mirrored at x = 0 (as `test_application_symmetry.py`), shared seam edge on the plane.
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

from core import HistoryStack, OperationContext
from core.mesh import Mesh, SymmetryDefinition
from mirai.application import SOFT_SYMMETRY_REFUSAL, Application
from mirai.interaction.input import Input
from mirai.interaction.tools import MoveTool, RotateTool, ScaleTool
from mirai.interaction.tools.selection_helpers import _VertexSelectionView
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


@pytest.mark.parametrize("key", [W, E, R], ids=["move", "rotate", "scale"])
def test_armed_then_soft_on_then_motion_is_refused_visibly(setup, key):
    """Review F2: W (soft off, arm passes) → O → the first motion reaches begin() with soft on."""
    app, ids = setup
    before = _state(app)
    assert app.key_press(key)
    assert app.interaction_owner == "transform"
    assert app.key_press(O)  # allowed while a transform key is held
    assert app.soft_settings.enabled
    serial = app.status_serial
    assert app.pointer_motion(300.0, 300.0, 12.0, 7.0) is False  # no exception out of pointer_motion
    assert SOFT_SYMMETRY_REFUSAL in app.status_message and "refused" in app.status_message
    assert app.status_serial > serial
    assert app.interaction_owner is None and not app.transform_interacting
    assert app.tool_manager.active_tool is None
    assert _state(app) == before  # mesh unchanged, no history entry
    # Soft stays on (the refusal changes no setting); switching it off makes the key work again.
    assert app.soft_settings.enabled
    assert app.key_press(O) and not app.soft_settings.enabled
    assert app.key_press(key)
    app.key_press(ESC)


@pytest.mark.parametrize("key", [W, E, R], ids=["move", "rotate", "scale"])
def test_soft_on_then_arm_is_refused_at_the_key_press(setup, key):
    app, ids = setup
    app.key_press(O)
    before = _state(app)
    assert app.key_press(key) is False
    assert SOFT_SYMMETRY_REFUSAL in app.status_message
    assert app.interaction_owner is None
    assert app.tool_manager.active_tool is None
    assert _state(app) == before


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
def test_backstop_the_tool_hands_the_op_the_symmetry_and_the_op_refuses(setup, tool_cls, op_cls):
    """Any other host that bypasses `Application`: the soft op raises before anything moves."""
    app, ids = setup
    mesh = app.scene.mesh
    before = mesh.export_state()
    tool = tool_cls()
    tool.activate()
    soft = SoftSettings(enabled=True, world_radius=0.5)
    with pytest.raises(ValueError, match="symmetry"):
        tool.begin(scene=app.scene, camera=app.camera, vertex_ids={ids["l0"]}, soft=soft)
    assert mesh.export_state() == before
    assert not tool.is_interacting and len(app.history) == 0
    assert op_cls.supports_symmetry is False
