"""AD-021 M2-0 — Reference display (Q-11, §7.3 RD-1…RD-4), headless.

`Alt+D` switches every Reference between shaded and Ghost (RD-1, RD-2); a Reference is drawn
in Wireframe too (RD-3); picking does not depend on the look (RD-4). The GL side (blend, no
depth write) is observed through a TraceStore that records `set_draw_style`.
"""

from __future__ import annotations

import tests._bootstrap  # noqa: F401

from core import ObjectState
from mirai.application import Application
from mirai.interaction import commands
from mirai.interaction.bindings import build_default_bindings
from mirai.interaction.input import Input
from mirai.scene_objects import REFERENCE_GHOST_ALPHA
from viewport.resource_store import TraceStore

WIDTH, HEIGHT = 800, 600
ALT_D = Input("key", "d", frozenset({"alt"}))
D = Input("key", "d", frozenset())


class StyleStore(TraceStore):
    """TraceStore that keeps the draw style a GLRenderStore would get."""

    def __init__(self, stats) -> None:
        super().__init__(stats)
        self.alpha = 1.0
        self.flat = False

    def set_draw_style(self, flat: bool, polygon_offset: bool, alpha: float = 1.0) -> None:
        self.flat, self.alpha = flat, alpha


def _app() -> Application:
    app = Application()
    app.init_scene("cube", store_type=StyleStore)
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


def _two_objects(app: Application):
    """One Reference and one Normal object besides the edit object."""
    ref = app.add_reference("cube")
    normal = app.add_reference("cube")
    normal.state = ObjectState.NORMAL
    app._objects.sync_views()
    return ref, normal


def test_alt_d_is_bound_to_the_reference_ghost_switch():
    assert build_default_bindings().command_for(ALT_D) == commands.TOGGLE_REFERENCE_GHOST


def test_alt_d_turns_every_reference_into_a_ghost_and_back():
    app = _app()
    ref, normal = _two_objects(app)
    entries = app.viewport.object_entries
    assert entries[ref.id].store.alpha == 1.0

    assert app.key_press(ALT_D)
    assert app.reference_ghost
    assert app.status_message == "References: ghost"
    assert entries[ref.id].store.alpha == REFERENCE_GHOST_ALPHA
    assert entries[normal.id].store.alpha == 1.0  # only References
    depth = len(app.history)

    assert app.key_press(ALT_D)
    assert app.status_message == "References: shaded"
    assert entries[ref.id].store.alpha == 1.0
    assert len(app.history) == depth  # display, not an Undo step


def test_ghosts_are_drawn_after_every_opaque_entry():
    app = _app()
    ghost_ref = app.add_reference("cube")
    ref, normal = _two_objects(app)
    app.key_press(ALT_D)
    order = app.viewport._entry_draw_order()
    assert order == [normal.id, ghost_ref.id, ref.id]


def test_a_reference_switched_to_normal_stops_being_a_ghost():
    app = _app()
    ref = app.add_reference("cube")
    app.key_press(ALT_D)
    entry = app.viewport.object_entries[ref.id]
    assert entry.store.alpha == REFERENCE_GHOST_ALPHA
    app.key_press(Input("key", "4", frozenset()))
    app._objects.switch_state(ref.id, app._selection_snapshot())
    assert ref.state is ObjectState.NORMAL
    assert entry.store.alpha == 1.0


def test_references_stay_drawn_in_wireframe_normal_objects_do_not():
    app = _app()
    ref, normal = _two_objects(app)
    app.key_press(D)
    app.key_press(D)  # Shaded -> Flat -> Wireframe
    assert not app.viewport.show_faces
    assert app.viewport.entry_drawn(ref.id)
    assert not app.viewport.entry_drawn(normal.id)
    assert app.viewport._entry_draw_order() == [ref.id]
    app.key_press(ALT_D)
    assert app.viewport.entry_drawn(ref.id)  # a ghost in wireframe


def test_the_ghost_setting_survives_a_scene_load_and_reaches_a_new_reference():
    app = _app()
    app.key_press(ALT_D)
    app.load_scene("cube", store_type=StyleStore)
    ref = app.add_reference("cube")
    assert app.viewport.object_entries[ref.id].store.alpha == REFERENCE_GHOST_ALPHA


def test_a_ghost_is_picked_in_mode_4_like_an_opaque_reference():
    app = _app()
    ref = app.add_reference("cube")
    app.key_press(Input("key", "4", frozenset()))
    shaded = app._pick(WIDTH / 2, HEIGHT / 2)
    app.key_press(ALT_D)
    assert app._pick(WIDTH / 2, HEIGHT / 2) == shaded
    assert shaded in (ref.id, app.scene.edit_object_id)
