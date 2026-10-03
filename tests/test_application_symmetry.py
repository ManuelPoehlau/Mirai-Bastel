"""Application under a Symmetry Definition (WP-SYM-LAB-03 H5 + plan §4.4).

Headless (TraceStore). `src/main.py` never sets a definition; any host that
does (the Symmetry Lab) reaches these paths through `Application`'s normal
input:

- H5: E (Rotate) on a seam vertex about an axis that would lift it off the
  plane → `SeamConstraintError` is caught in `_transform_step`: the transform
  ends, status `Rotate: refused — <reason>` (PROVISIONAL), no history entry,
  mesh unchanged, hover re-picked. Before H5 the error escaped the handler.
- Symmetric Move with an axis constraint (plan §4.4; `tests/test_symmetric_move.py`
  has no `space` case): the partner mirrors, the seam vertex stays on the plane.

Mesh: two quads mirrored at x = 0, sharing the seam edge s0–s1 on the plane.
"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401

from core.mesh import Mesh, SymmetryDefinition
from mirai.application import Application
from mirai.interaction import commands
from mirai.interaction.input import Input
from mirai.symmetry import CorrespondenceState, vertex_correspondence

WIDTH, HEIGHT = 800, 600
MISS = (2.0, 2.0)

W = Input("key", "w")
E = Input("key", "e")
X = Input("key", "x")
Y = Input("key", "y")


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
    # Same mesh instance stays bound to scene and viewport (in-place load).
    app.scene.mesh.load_state(mesh.export_state())
    app.viewport.on_topology_changed()
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    correspondence = vertex_correspondence(app.scene.mesh)
    assert correspondence[ids["s0"]].state is CorrespondenceState.SEAM
    assert correspondence[ids["l0"]].state is CorrespondenceState.PAIRED
    return app, ids


def _select(app, *vids):
    app.selection.set(set(vids))
    app.viewport.on_selection_changed()


def _pos(app, vid):
    return app.scene.mesh.vertex_position(vid)


def _close(a, b, tol=1e-9):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


# -- H5 ------------------------------------------------------------------------


def test_seam_rotate_refusal_ends_transform_without_history(setup):
    """H5: refusal → no history entry, transform ended, status posted."""
    app, ids = setup
    forward, _, _ = app.camera.basis()
    assert abs(abs(forward[0]) - 1.0) > 1e-3  # the view axis is not the plane normal
    _select(app, ids["s0"])
    app.pointer_motion(*MISS)
    state = app.scene.mesh.export_state()
    assert app.key_press(E)
    assert app.interaction_owner == "transform"
    serial = app.status_serial

    assert app.pointer_motion(400, 300, 15.0, 0.0) is False
    assert app.transform_command is None
    assert app.interaction_owner is None
    assert not app.transform_interacting
    assert app.tool_manager.active_tool is None
    assert app.status_serial == serial + 1
    assert app.status_message.startswith("Rotate: refused — ")
    assert "Seam" in app.status_message
    assert not app.history.can_undo()
    assert app.scene.mesh.export_state() == state

    # The held E's release is a no-op; further motion hovers again.
    assert app.key_release(E) is False
    assert app.pointer_motion(400, 300, 5.0, 0.0) is not None
    # A fresh E arms again (nothing is stuck).
    assert app.key_press(E)
    assert app.transform_command == commands.ROTATE


def test_seam_rotate_about_plane_normal_is_allowed(setup):
    """Control: with constraint X (axis = plane normal) Rotate of the seam
    vertices runs (two of them, so the pivot is not a vertex itself) and they
    stay on the plane."""
    app, ids = setup
    _select(app, ids["s0"], ids["s1"])
    app.pointer_motion(*MISS)
    assert app.key_press(X)
    assert app.key_press(E)
    assert app.pointer_motion(400, 300, 15.0, 0.0) is True
    assert app.key_release(E) is True
    assert app.status_message.startswith("Rotate committed")
    assert app.history.can_undo()
    for vid in (ids["s0"], ids["s1"]):
        assert _pos(app, vid)[0] == pytest.approx(0.0, abs=1e-9)
    assert _pos(app, ids["s0"])[2] != pytest.approx(0.0)


def test_refusal_repicks_hover(setup, monkeypatch):
    app, ids = setup
    _select(app, ids["s0"])
    app.pointer_motion(*MISS)
    app.key_press(E)
    calls = []
    original = app._refresh_hover
    monkeypatch.setattr(app, "_refresh_hover", lambda: (calls.append(1), original()))
    app.pointer_motion(400, 300, 15.0, 0.0)
    assert calls == [1]


# -- Symmetric Move + axis constraint (plan §4.4) ------------------------------


def _w_drag(app, dx=25.0, dy=-18.0, steps=3):
    app.pointer_motion(*MISS)
    assert app.key_press(W)
    for _ in range(steps):
        assert app.pointer_motion(400, 300, dx, dy)
    assert app.key_release(W)


@pytest.mark.parametrize("axis_key, moved_axis", [(Y, 1), (X, 0)])
def test_symmetric_move_with_axis_constraint(setup, axis_key, moved_axis):
    app, ids = setup
    l0, r0 = _pos(app, ids["l0"]), _pos(app, ids["r0"])
    _select(app, ids["l0"])
    assert app.key_press(axis_key)
    _w_drag(app)
    new_l0, new_r0 = _pos(app, ids["l0"]), _pos(app, ids["r0"])
    for axis in range(3):
        if axis != moved_axis:
            assert new_l0[axis] == pytest.approx(l0[axis])
    assert abs(new_l0[moved_axis] - l0[moved_axis]) > 1e-3
    # The partner is the mirror image of the moved vertex (x negated).
    assert _close(new_r0, (-new_l0[0], new_l0[1], new_l0[2]))
    assert app.history.can_undo()
    assert app.status_message.endswith(
        f"(constraint {'Y' if moved_axis == 1 else 'X'})"
    )
    # One undo step restores both.
    app.key_press(Input("key", "z", frozenset({"ctrl"})))
    assert _close(_pos(app, ids["l0"]), l0) and _close(_pos(app, ids["r0"]), r0)


def test_seam_vertex_stays_on_plane_under_constraint(setup):
    app, ids = setup
    s0 = _pos(app, ids["s0"])
    _select(app, ids["s0"])
    assert app.key_press(Input("key", "z", frozenset({"shift"})))  # XY plane
    assert app.axis_constraint == "xy"
    _w_drag(app)
    new_s0 = _pos(app, ids["s0"])
    assert new_s0[0] == pytest.approx(0.0, abs=1e-9)  # slides in the plane
    assert new_s0[2] == pytest.approx(s0[2])
    assert abs(new_s0[1] - s0[1]) > 1e-3
