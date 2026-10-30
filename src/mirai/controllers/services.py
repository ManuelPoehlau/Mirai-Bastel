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
    def status_message(self) -> str:
        """The status line as it stands (public on `Application`). Reason for the member (AD-027 M6): a gesture's
        commit appends "free again (one-shot)" to the line its kind just posted."""
        return self._app.status_message

    @property
    def active_pivot(self):
        """The Working Pivot's position when W/E/R use it (`Application.active_pivot`), else None. Reason for the
        member (AD-027 M6): Rotate / Scale turn about it; the pivot is the pointer tools', its "active" rule (edit
        object, on, not mode `4`) `Application`'s."""
        return self._app.active_pivot

    @property
    def gizmo_press(self):
        """The running gizmo handle press (`pointer_tools.GizmoPress`), else None. Reason for the member (AD-027
        M6): a gesture armed from a handle drag reads its press point and handle (the Rotate trackball); forwarded,
        so the gesture controller does not import the pointer tools."""
        return self._app._pointer_tools.gizmo_press

    @property
    def soft_settings(self):
        """The sticky Soft Selection settings (`Application.soft_settings`). Reason for the member (AD-027 M6): a
        gesture reads them at `begin()`; Soft settings stay in `Application` (§3.4)."""
        return self._app._soft

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

    def pick_in_rect(self, rect, occlusion: bool) -> set:
        """The elements of the active mode inside a window rectangle (GPU ID buffers, else the CPU picker). Reason
        for the member (AD-027 M5): Box Select's release picks a region; picking stays in `Application` (§3.4)."""
        return self._app._elements_in_rect(rect, occlusion)

    def pick_in_polygon(self, polygon, occlusion: bool) -> set:
        """The elements of the active mode inside a window polygon (as `pick_in_rect`). Reason for the member
        (AD-027 M5): Lasso Select's release."""
        return self._app._elements_in_polygon(polygon, occlusion)

    def prune_selection(self) -> None:
        """Drop selected / hovered IDs the mesh no longer has (`Application._prune_ghost_selection`). Reason for the
        member (AD-027 M6): a topology gesture (Extrude, Inset / Bevel) sweeps after its begin, commit and cancel."""
        self._app._prune_ghost_selection()

    def soft_preview_refresh(self) -> bool:
        """True = the preview shows weights now (AD-027 M6: a hover-armed gesture then owns the bands it put there)."""
        return self._app._soft_preview_refresh()

    def set_soft_settings(self, settings) -> None:
        """Reason for the member (AD-027 M6): a live radius / flow step of a running Soft gesture takes the sticky
        setting along (AD-020 "Live radius")."""
        self._app._soft = settings

    def show_soft_weights(self, weights, mode: str) -> bool:
        """Route `weights` (None = nothing) to the Soft display mode `mode`; False (nothing done) without an
        influence sink (headless). Reason for the member (AD-027 M6): a running Soft gesture shows its own weights;
        the display stays in `Application` (§3.4)."""
        app = self._app
        if app._soft_overlay is None and app._soft_shading_overlay is None:
            return False
        app._soft_show(weights, mode)
        return True

    def mask_values(self, seeds=()) -> dict:
        """The protection weights for `seeds` (Mask Geometry, Hide, groups: `Application._mask_values`). Reason for
        the member (AD-027 M6): the gestures pass them to their tools; mask / hide stay in `Application` (§3.4)."""
        return self._app._mask_values(seeds)

    def flush_hover(self) -> None:
        """Pick a hover `coalesce_hover` left stale. Reason for the member (AD-027 M6): a gesture's tool activation
        went through `Application._execute`, which flushes first; the gesture keeps that order."""
        self._app.flush_hover()

    def set_light(self, **changes) -> bool:
        """The Worklight's edit path (`Application.set_light`). Reason for the member (AD-027 M4): the light drag
        (a hold key, `controllers.pointer_tools`) turns the key light; display and the Worklight look stay in
        `Application` (§3.4)."""
        return self._app.set_light(**changes)

    def toggle_ortho(self) -> bool:
        """Ortho <-> Persp (view state, `Application._toggle_ortho`). Reason for the member (AD-027 M3): the Knife
        session's own ortho key (resolved in the `knife` context) runs the view command `Application` owns
        (navigation and views stay there, §3.4)."""
        return self._app._toggle_ortho()

    def set_edit_object(self, object_id) -> None:
        self._app._set_edit_object(object_id)

    def follow_edit_object(self) -> None:
        self._app._follow_edit_object()
