"""`AppServices` (AD-027 §3.4): everything a controller may use of the app, and nothing else.

A controller gets this object, never the `Application`. The member list is fixed by AD-027 §3.4; a new
member needs a reason in its commit. The bridge holds the app only to forward to it (`_app`, which no
controller reads - checked by AD-027 E5 (ii)); this module imports nothing from `mirai.application`.
"""

from __future__ import annotations

from typing import Any, Callable


class AppServices:
    """Read access to the app's state plus the shared operations (status, transactions, picking,
    notifications, hover). Services another controller owns are forwarded, so controllers never import
    each other."""

    __slots__ = ("_app",)

    def __init__(self, app) -> None:
        self._app = app

    # -- read access -------------------------------------------------------------------------------

    @property
    def scene(self):
        return self._app.scene

    @property
    def selection(self):
        return self._app.selection

    @property
    def history(self):
        return self._app.history

    @property
    def camera(self):
        return self._app.camera

    @property
    def display(self):
        return self._app.display

    @property
    def bindings(self):
        return self._app.bindings

    @property
    def viewport(self):
        return self._app.viewport

    @property
    def interaction(self):
        """The `InteractionSlot`."""
        return self._app.interaction

    @property
    def interaction_owner(self) -> str | None:
        """AD-013 H2's owner. Until the gestures and the Knife sit in the slot (AD-027 M3, M6) it also
        reports those, so this is not `interaction.owner` yet (reason for the member, M1)."""
        return self._app.interaction_owner

    @property
    def cursor(self):
        return self._app._cursor

    @property
    def press_point(self):
        return self._app._press_point

    @property
    def viewport_size(self) -> tuple[int, int]:
        return self._app.viewport_width, self._app.viewport_height

    @property
    def modifiers(self) -> tuple[bool, bool, bool]:
        """(Shift, Ctrl, Alt) held, as the window reports them."""
        app = self._app
        return app._shift_held, app._ctrl_held, app._alt_held

    @property
    def edit_camera(self):
        return self._app._edit_camera

    @property
    def pick_cache(self):
        """The edit object's screen-space pick cache. Reason for the member (AD-027 M3): the Knife picks with its
        own occlusion tests on the shared cache (`knife_pick`, `snap_own_point`, the planner's `set_view`);
        picking stays in `Application` (§3.4), the cache is the one it keeps."""
        return self._app._pick_cache

    # -- operations --------------------------------------------------------------------------------

    def status(self, text: str) -> None:
        self._app._set_status(text)

    def can_run(self, command: str | None, ctx) -> Any:
        return self._app.can_run(command, ctx)

    def selection_snapshot(self) -> tuple:
        return self._app._selection_snapshot()

    def restore_selection(self, snapshot: tuple) -> None:
        self._app._restore_selection(snapshot)

    def record_selection_history(self, before: tuple, **kwargs) -> None:
        self._app._record_selection_history(before, **kwargs)

    def mesh_transaction(self, description: str, mutate: Callable, **kwargs):
        return self._app._mesh_transaction(description, mutate, **kwargs)

    def invalidate_picks(self) -> None:
        self._app._pick_cache.invalidate()

    def notify_vertices_moved(self, ids) -> None:
        if self._app.viewport is not None:
            self._app.viewport.on_vertices_moved(ids)

    def notify_topology_changed(self) -> None:
        self._app._notify_topology_changed()

    def notify_selection_changed(self) -> None:
        if self._app.viewport is not None:
            self._app.viewport.on_selection_changed()

    def set_hovered(self, hovered) -> bool:
        return self._app._set_hovered(hovered)

    def refresh_hover(self) -> None:
        self._app._refresh_hover()

    def pick(self, x: float, y: float):
        return self._app._pick(x, y)

    def pick_face(self, x: float, y: float):
        return self._app._pick_face_at(x, y)

    def soft_preview_refresh(self, *args, **kwargs) -> None:
        self._app._soft_preview_refresh(*args, **kwargs)

    def toggle_ortho(self) -> bool:
        """Ortho <-> Persp (view state, `Application._toggle_ortho`). Reason for the member (AD-027 M3): the Knife
        session's own ortho key (resolved in the `knife` context) runs the view command `Application` owns
        (navigation and views stay there, §3.4)."""
        return self._app._toggle_ortho()

    def set_edit_object(self, object_id) -> None:
        self._app._set_edit_object(object_id)

    def follow_edit_object(self) -> None:
        self._app._follow_edit_object()
