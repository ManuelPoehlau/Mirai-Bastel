"""Mask Geometry (`mirai.mask`, docs/future_ideas/MODELING.md, Priorität 1; PROVISIONAL).

Headless unit tests of the mask rules plus the app path: Ctrl+M masks the selection, a masked vertex never
moves in Move / Rotate / Scale / Smooth, Soft influence is scaled by (1 - m), the mask writes no History."""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401
from tests.soft_selection_fixtures import HEAD_OBJ  # noqa: F401

from mirai.application import Application
from mirai.interaction import commands as cmd
from mirai.interaction.input import Input
from mirai.mask import VertexMask, effective_mask, mask_weights, unblocked

WIDTH, HEIGHT = 800, 600


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


CTRL_M, CTRL_SHIFT_M, ALT_SHIFT_M = _key("m", "ctrl"), _key("m", "ctrl", "shift"), _key("m", "alt", "shift")
W, E, R, O, S = _key("w"), _key("e"), _key("r"), _key("o"), _key("s")


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("obj", obj_path=HEAD_OBJ)
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


def _positions(app) -> dict:
    mesh = app.scene.mesh
    return {vid: mesh.vertex_position(vid) for vid in mesh.all_vertex_ids()}


def _select(app, *indices):
    ids = app.scene.mesh.all_vertex_ids()
    chosen = {ids[i] for i in indices}
    app.selection.set(chosen)
    app.viewport.on_selection_changed()
    return chosen


def _gesture(app, key: Input):
    assert app.key_press(key)
    for dx, dy in ((6, 2), (5, 3), (4, -1)):
        app.pointer_motion(300.0, 300.0, float(dx), float(dy))
    assert app.key_release(key)


# -- Unit: the rules ------------------------------------------------------------------


def test_mask_set_clear_and_value_range():
    mask = VertexMask()
    assert not mask
    mask.set([1, 2], 0.5)
    mask.set([3])
    assert mask.value(1) == 0.5 and mask.value(3) == 1.0 and mask.value(9) == 0.0
    assert mask.full() == frozenset({3})
    mask.set([1], 0.0)
    assert mask.value(1) == 0.0 and len(mask) == 2
    with pytest.raises(ValueError):
        mask.set([4], 1.5)
    mask.clear()
    assert not mask


def test_unblocked_drops_only_fully_masked():
    assert unblocked({1, 2, 3}, {1: 1.0, 2: 0.5}) == {2, 3}
    assert unblocked({1, 2}, None) == {1, 2}


def test_mask_weights_keep_seeds_and_scale_the_rest():
    weights = {1: 1.0, 2: 0.8, 3: 0.4, 4: 0.6}
    result = mask_weights(weights, seeds={1}, mask={1: 0.5, 2: 0.5, 3: 1.0})
    assert result == {1: 1.0, 2: pytest.approx(0.4), 4: 0.6}


# -- App path --------------------------------------------------------------------------


def test_ctrl_m_masks_and_unmasks_the_selection_without_history(app):
    chosen = _select(app, 100, 101)
    depth = len(app.history.undo_stack) if hasattr(app.history, "undo_stack") else None
    assert app.key_press(CTRL_M)
    assert app._mask.full() == frozenset(chosen)
    assert app.key_press(CTRL_M)  # all masked -> unmask
    assert not app._mask
    if depth is not None:
        assert len(app.history.undo_stack) == depth


def test_invert_and_clear(app):
    chosen = _select(app, 100)
    app.key_press(CTRL_M)
    app.key_press(CTRL_SHIFT_M)
    total = len(app.scene.mesh.all_vertex_ids())
    assert len(app._mask.full()) == total - len(chosen)
    assert chosen.isdisjoint(app._mask.full())
    app.key_press(ALT_SHIFT_M)
    assert not app._mask


@pytest.mark.parametrize("key", [W, E, R], ids=["move", "rotate", "scale"])
def test_masked_selection_is_refused(app, key):
    _select(app, 100)
    app.key_press(CTRL_M)
    before = _positions(app)
    assert not app.key_press(key)
    assert _positions(app) == before


@pytest.mark.parametrize("key", [W, E, R], ids=["move", "rotate", "scale"])
def test_masked_vertex_stays_while_the_rest_moves(app, key):
    masked = _select(app, 100)
    app.key_press(CTRL_M)
    both = _select(app, 100, 101, 102)  # rotate / scale need two free points to leave their pivot
    free = both - masked
    before = _positions(app)
    _gesture(app, key)
    after = _positions(app)
    (m,) = masked
    assert after[m] == before[m]
    assert any(after[v] != before[v] for v in free)


def test_soft_influence_skips_masked_neighbours(app):
    ids = app.scene.mesh.all_vertex_ids()
    seed = ids[100]
    app.selection.set({seed})
    app.viewport.on_selection_changed()
    app.key_press(O)
    unmasked_run = _positions(app)
    _gesture(app, W)
    moved = {v for v, p in _positions(app).items() if p != unmasked_run[v]}
    neighbours = moved - {seed}
    assert neighbours, "fixture: Soft must move neighbours"
    app.key_press(_key("z", "ctrl"))
    assert _positions(app) == unmasked_run
    app._mask.set(neighbours)
    app._mask_changed("test")
    _gesture(app, W)
    after = _positions(app)
    assert all(after[v] == unmasked_run[v] for v in neighbours)
    assert after[seed] != unmasked_run[seed]


def test_smooth_leaves_masked_vertices(app):
    _select(app, *range(100, 110))
    ids = app.scene.mesh.all_vertex_ids()
    app._mask.set([ids[100], ids[101]])
    before = _positions(app)
    _gesture(app, S)
    after = _positions(app)
    assert after[ids[100]] == before[ids[100]] and after[ids[101]] == before[ids[101]]


def test_effective_mask_is_pair_consistent_under_symmetry(app):
    from mirai.symmetry import CorrespondenceState, vertex_correspondence

    assert app.key_press(_key("s", "shift"))  # Shift+S: symmetry on (first axis)
    mesh = app.scene.mesh
    if mesh.symmetry_definition is None:
        pytest.skip("symmetry did not switch on for this fixture")
    paired = next(
        (v, c.partner) for v, c in vertex_correspondence(mesh).items()
        if c.state is CorrespondenceState.PAIRED and c.partner != v
    )
    mask = VertexMask()
    mask.set([paired[0]])
    effective = effective_mask(mesh, mask)
    assert effective[paired[0]] == effective[paired[1]] == 1.0


def test_scene_load_clears_the_mask(app):
    _select(app, 100)
    app.key_press(CTRL_M)
    app.init_scene("cube")
    assert not app._mask


def test_mask_overlay_follows_the_mesh_and_skips_stale_ids(app):
    from mirai.mask_display import MASK_LAYER_FULL, MASK_LAYER_PARTIAL, GLMaskOverlay

    mesh = app.scene.mesh
    a, b, c = mesh.all_vertex_ids()[:3]
    overlay = GLMaskOverlay()
    overlay.set_values({a: 1.0, b: 0.5, 10**9: 1.0})
    assert overlay.dirty
    overlay.sync(mesh, app.selection)
    assert not overlay.dirty
    assert overlay._positions[MASK_LAYER_FULL] == [mesh.vertex_position(a)]
    assert overlay._positions[MASK_LAYER_PARTIAL] == [mesh.vertex_position(b)]
