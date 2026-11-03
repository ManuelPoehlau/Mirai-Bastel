"""Seam auf Ebene legen (Manu 2026-11-03, Lösung B; default key Shift+Alt+S, `PROVISIONAL`).

The case it repairs: with symmetry off a mid-seam vertex was moved off the plane and the scene saved.
Shift+S re-derives the seam exactly (E3, no tolerance), finds it with a gap, the seam no longer splits
the mesh in two and Re-Symmetrize refuses. Selecting the seam vertices and running the command lays
them exactly onto the plane and extends the seam, so Re-Symmetrize works again - without a tolerance.
"""

from __future__ import annotations

import sys

import pytest

import tests._bootstrap  # noqa: F401
from tests._bootstrap import _REPO_ROOT

_EXAMPLES = _REPO_ROOT / "examples"
if str(_EXAMPLES) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES))

from core import SelectionMode  # noqa: E402
from loaders.assets import asset_path  # noqa: E402
from mirai.application import Application  # noqa: E402
from mirai.interaction import commands  # noqa: E402
from mirai.interaction.input import Input  # noqa: E402
from mirai.layer_declarations import layer_refusal, view_refusal  # noqa: E402
from mirai.scene_factory import build_core_scene_from_obj  # noqa: E402
from mirai.symmetry_axis import (  # noqa: E402
    SeamToPlaneRejected,
    apply_seam_to_plane,
    current_axis,
    definition_for_axis,
    plan_seam_to_plane,
)
from mirai.symmetry_topology import topological_sides  # noqa: E402

ASSET = "man_with_shoes_basemesh"
NUDGE = 0.001


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


SHIFT_S = _key("s", "shift")
SHIFT_ALT_S = _key("s", "alt", "shift")
ALT_M = _key("m", "alt")
CTRL_Z, CTRL_Y = _key("z", "ctrl"), _key("y", "ctrl")


def _seam_vertex_in_the_middle(mesh):
    on_plane = sorted((v for v in mesh.all_vertex_ids() if mesh.vertex_position(v)[0] == 0.0), key=int)
    return on_plane[len(on_plane) // 2]


def _nudge(mesh, vid, dx=NUDGE):
    x, y, z = mesh.vertex_position(vid)
    mesh.set_vertex_position(vid, (x + dx, y, z))


def broken_mesh():
    """The saved state: symmetry off, one seam vertex 0.001 off the plane."""
    mesh = build_core_scene_from_obj(asset_path(ASSET)).mesh
    vid = _seam_vertex_in_the_middle(mesh)
    _nudge(mesh, vid)
    return mesh, vid


# -- pure plan ----------------------------------------------------------------------------------------


def test_broken_seam_is_repaired_to_the_clean_seam():
    clean = build_core_scene_from_obj(asset_path(ASSET)).mesh
    clean_seam = definition_for_axis(clean, "X").seam_edges
    mesh, vid = broken_mesh()
    mesh.symmetry_definition = definition_for_axis(mesh, "X")
    assert topological_sides(mesh).component_count == 1  # the reported failure

    plan = plan_seam_to_plane(mesh, {vid})
    assert set(plan.moves) == {vid}
    assert plan.max_distance == pytest.approx(NUDGE)
    apply_seam_to_plane(mesh, plan)

    assert mesh.vertex_position(vid)[0] == 0.0
    assert mesh.symmetry_definition.seam_edges == clean_seam
    assert topological_sides(mesh).component_count == 2


def test_existing_seam_edges_are_kept():
    mesh, vid = broken_mesh()
    mesh.symmetry_definition = definition_for_axis(mesh, "X")
    before = mesh.symmetry_definition.seam_edges
    apply_seam_to_plane(mesh, plan_seam_to_plane(mesh, {vid}))
    assert before <= mesh.symmetry_definition.seam_edges


def test_only_the_axis_component_changes():
    mesh, vid = broken_mesh()
    mesh.symmetry_definition = definition_for_axis(mesh, "X")
    _, y, z = mesh.vertex_position(vid)
    apply_seam_to_plane(mesh, plan_seam_to_plane(mesh, {vid}))
    assert mesh.vertex_position(vid) == (0.0, y, z)


def test_vertex_already_on_plane_is_an_empty_plan():
    mesh = build_core_scene_from_obj(asset_path(ASSET)).mesh
    mesh.symmetry_definition = definition_for_axis(mesh, "X")
    assert plan_seam_to_plane(mesh, {_seam_vertex_in_the_middle(mesh)}).is_empty


def test_rejected_when_symmetry_off_or_nothing_selected():
    mesh, vid = broken_mesh()
    with pytest.raises(SeamToPlaneRejected, match="Symmetrie aus"):
        plan_seam_to_plane(mesh, {vid})
    mesh.symmetry_definition = definition_for_axis(mesh, "X")
    with pytest.raises(SeamToPlaneRejected, match="keine Auswahl"):
        plan_seam_to_plane(mesh, set())


def test_gate_classification():
    assert layer_refusal(commands.SEAM_TO_PLANE) is None  # positions + the definition, layers untouched
    assert view_refusal(commands.SEAM_TO_PLANE) is not None  # writes the symmetry definition: base only


# -- in the app -----------------------------------------------------------------------------------------


@pytest.fixture
def broken_app():
    """The reported case in the app: the saved mesh loaded, Shift+S to X, Re-Symmetrize refuses."""
    app = Application()
    app.init_scene("obj", obj_path=asset_path(ASSET))
    mesh = app.scene.mesh
    vid = _seam_vertex_in_the_middle(mesh)
    _nudge(mesh, vid)
    assert app.key_press(SHIFT_S)
    assert current_axis(mesh) == "X"
    side_vertex = next(iter(topological_sides(mesh).vertex_side))
    app.selection.set({side_vertex})
    assert app.key_press(ALT_M) is False
    assert "1 Teile" in app.status_message
    return app, vid, side_vertex


def test_default_key():
    app = Application()
    assert app.bindings.command_for(SHIFT_ALT_S) == commands.SEAM_TO_PLANE


def test_repair_then_resymmetrize_opens(broken_app):
    app, vid, side_vertex = broken_app
    steps = len(app.history)
    app.selection.set({vid})
    assert app.key_press(SHIFT_ALT_S) is True
    assert len(app.history) == steps + 1
    assert "Re-Symmetrize möglich" in app.status_message
    assert app.scene.mesh.vertex_position(vid)[0] == 0.0

    app.selection.set({side_vertex})
    assert app.key_press(ALT_M) is True
    assert app.resymmetrize_preview is not None


def test_edge_mode_selection_works(broken_app):
    app, vid, _ = broken_app
    mesh = app.scene.mesh
    app.selection.mode = SelectionMode.EDGE
    app.selection.set({mesh.vertex_edges(vid)[0]})
    assert app.key_press(SHIFT_ALT_S) is True
    assert mesh.vertex_position(vid)[0] == 0.0


def test_undo_restores_position_and_seam_redo_reapplies(broken_app):
    app, vid, _ = broken_app
    mesh = app.scene.mesh
    position = mesh.vertex_position(vid)
    seam = mesh.symmetry_definition.seam_edges
    app.selection.set({vid})
    assert app.key_press(SHIFT_ALT_S)
    repaired = mesh.symmetry_definition.seam_edges
    assert app.key_press(CTRL_Z)
    assert mesh.vertex_position(vid) == position
    assert mesh.symmetry_definition.seam_edges == seam
    assert app.key_press(CTRL_Y)
    assert mesh.vertex_position(vid)[0] == 0.0
    assert mesh.symmetry_definition.seam_edges == repaired


def test_second_press_records_nothing(broken_app):
    app, vid, _ = broken_app
    app.selection.set({vid})
    assert app.key_press(SHIFT_ALT_S)
    steps = len(app.history)
    assert app.key_press(SHIFT_ALT_S) is False
    assert len(app.history) == steps
    assert "kein Schritt" in app.status_message


def test_refused_with_symmetry_off():
    app = Application()
    app.init_scene("obj", obj_path=asset_path(ASSET))
    app.selection.set({_seam_vertex_in_the_middle(app.scene.mesh)})
    assert app.key_press(SHIFT_ALT_S) is False
    assert app.status_message == "Seam auf Ebene: Symmetrie aus"
