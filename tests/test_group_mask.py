"""Mask by Polygroup (Manu 2026-10-25, ZBrush-like; PROVISIONAL): Ctrl+Alt+Shift+M switches it on. While on, a
gesture only moves the groups of its selection (else the hovered element); everything else is masked for that
gesture only, the artist's own mask stays untouched."""

from __future__ import annotations

import dataclasses

import pytest

import tests._bootstrap  # noqa: F401

from core import FaceRegion, FaceRegions, SelectionMode
from core.mesh import Mesh
from mirai import regions as api
from mirai.application import Application
from mirai.interaction.input import Input

WIDTH, HEIGHT = 800, 600


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


TOGGLE, W, O, S = _key("m", "ctrl", "alt", "shift"), _key("w"), _key("o"), _key("s")


def _grid(n: int = 6) -> Mesh:
    mesh = Mesh()
    ids = [[mesh.add_vertex((float(x), float(y), 0.0)) for x in range(n + 1)] for y in range(n + 1)]
    for y in range(n):
        for x in range(n):
            mesh.add_face([ids[y][x], ids[y][x + 1], ids[y + 1][x + 1], ids[y + 1][x]])
    return mesh


def _center_x(mesh, f):
    return sum(mesh.vertex_position(v)[0] for v in mesh.face_vertices(f)) / 4.0


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.scene.mesh.load_state(_grid().export_state())
    app._soft_refresh_radius()  # the Soft radius follows the loaded grid, not the cube
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    mesh = app.scene.mesh
    left = frozenset(f for f in mesh.all_face_ids() if _center_x(mesh, f) < 3)
    mesh.face_regions = FaceRegions((FaceRegion("Group 1", left),))  # the right half has no group
    return app


def _vertex(mesh, x, y):
    return next(v for v in mesh.all_vertex_ids() if mesh.vertex_position(v)[:2] == (float(x), float(y)))


def _positions(mesh):
    return {v: mesh.vertex_position(v) for v in mesh.all_vertex_ids()}


def _move(app):
    assert app.key_press(W)
    for dx, dy in ((8, 3), (6, 2)):
        app.pointer_motion(400.0, 300.0, float(dx), float(dy))
    assert app.key_release(W)


def test_group_lock_frees_the_seeds_groups_and_keeps_their_border_masked(app):
    mesh = app.scene.mesh
    inner = {_vertex(mesh, 1, 1)}
    lock = api.group_lock(mesh, inner)
    assert _vertex(mesh, 2, 2) not in lock and _vertex(mesh, 0, 0) not in lock
    assert _vertex(mesh, 3, 2) in lock  # the border to the ungrouped half stays
    assert _vertex(mesh, 5, 5) in lock
    on_border = {_vertex(mesh, 3, 3)}
    assert api.group_lock(mesh, on_border) == set()  # touches both: the group and the ungrouped faces
    assert api.group_lock(mesh, {_vertex(mesh, 5, 5)}) >= {_vertex(mesh, 1, 1)}  # ungrouped is a group too
    assert api.group_lock(_grid(), inner) == set()  # no groups: no restriction


def test_off_by_default_and_toggle_reports(app):
    assert not app.group_mask
    assert app.key_press(TOGGLE) and app.group_mask and "on" in app.status_message
    assert app.key_press(TOGGLE) and not app.group_mask


def test_soft_move_stays_inside_the_group_and_leaves_the_own_mask_alone(app):
    mesh = app.scene.mesh
    app.selection.mode = SelectionMode.VERTEX
    seed = _vertex(mesh, 2, 3)
    app.selection.set({seed})
    app.viewport.on_selection_changed()
    assert app.key_press(O)  # Soft on, radius 2.5 grid steps: the falloff reaches the right half
    app._soft = dataclasses.replace(app._soft, world_radius=2.5)
    before = _positions(mesh)
    _move(app)
    assert any(before[v][0] >= 3 and mesh.vertex_position(v) != before[v] for v in before)  # without the switch
    app.key_press(_key("z", "ctrl"))
    app.key_press(TOGGLE)
    _move(app)
    after = _positions(mesh)
    moved = {v for v in before if before[v] != after[v]}
    assert seed in moved and len(moved) > 1  # the Soft falloff moved neighbours too
    assert all(before[v][0] < 3 for v in moved)  # nothing at or right of the border moved
    assert not app._mask  # the artist's mask stays empty


def test_hover_picks_the_group_when_nothing_is_selected(app):
    mesh = app.scene.mesh
    app.key_press(TOGGLE)
    seeds = {_vertex(mesh, 5, 3)}  # in the ungrouped half
    values = app._mask_values(seeds)
    assert values.get(_vertex(mesh, 1, 1)) == 1.0 and _vertex(mesh, 5, 3) not in values
    app.key_press(TOGGLE)
    assert app._mask_values(seeds) == {}


def test_hud_shows_the_switch(app):
    from hud import hud_rows, hud_state, key_hints

    app.key_press(TOGGLE)
    row = {r.label: r for r in hud_rows(hud_state(app), key_hints(app.bindings))}["Region"]
    assert row.value.endswith("group mask on")
