"""Production entry point — Stage B, Slices B1, B2, B2b, B3, B4, B5a, B5b, B6 + B7.

Handoffs: "WP-06 — Slice B1: Head mesh as default scene + camera framing",
"WP-06 — Slice B2: Navigation per Artist Truth + vertex selection,
Modifier variant" and "WP-06 — Slice B2b: Selected vertex as round point +
vertex hover" (2026-09-26), building on Stage A (AD-018 §5/§6, AD-010
Addendum 2026-09-25). Opens a standalone `pyglet` window that shows the
default scene through the real Production draw path:

    Application -> Viewport -> GLRenderStore -> RenderMesh.render(camera)

Scope (binding, see the handoffs):
- Default scene is the head basemesh (`examples/meshes/head_basemesh.obj`),
  loaded through `Application.init_scene("obj", obj_path=...)` and framed
  once via `Application.frame_scene()`. An optional single CLI argument
  overrides this: a path to an `.obj`, or the literal `cube`. A load
  failure prints one line to stderr and falls back to the cube.
- Navigation and vertex selection (B2) go through the bindings:
  pyglet event -> `mirai.pyglet_input` -> `Application.pointer_*` ->
  `BindingSet` + `PointerGestures` (click vs. drag, AD-019). Orbit =
  Alt+LMB drag, Pan = Alt+Shift+LMB drag, Zoom = wheel; LMB click =
  select (Shift add, Ctrl remove, Alt toggle). RMB/MMB are unbound.
- Selected vertices are drawn as small round yellow points by
  `GLPointOverlay` on top of the mesh; the mesh itself is no longer tinted
  (Slice B2b, AD-018 §7 addendum). The vertex under the cursor shows a
  slightly larger, translucent pale-yellow hover point (`PROVISIONAL`):
  `on_mouse_motion`/`on_mouse_leave` -> `Application.pointer_motion`/
  `pointer_leave`.
- Keys (B3): `on_key_press`/`on_key_release` -> `mirai.pyglet_input` ->
  `Application.key_press`/`key_release` -> `BindingSet` (GLOBAL). Move
  (`PROMOTED`, AD-016 hold-key-hover): hold W and move the mouse (no button
  needed; `on_mouse_motion` passes `dx, dy` through) — the selection, or
  else the hovered vertex, follows live; releasing W commits, a tap without
  motion does nothing. Motion with a button held (`on_mouse_drag`) does not
  feed the Move — accepted gap, nothing is bound to a bare LMB drag. Esc =
  Cancel only, Ctrl+Z / Ctrl+Y = Undo / Redo. Rotate (E) and Scale (R)
  work the same way (B4). X/Y/Z toggle a sticky axis constraint and
  Shift+X/Y/Z a plane without that axis (Blender convention; Rotate turns
  about the plane's normal) — with or without W/E/R held; it persists
  across gestures and applies from the next gesture on (B4.1, same as the
  Playground). Display (B5a, `PROVISIONAL`): D cycles Shaded → Flat
  Shaded → Wireframe, Shift+D toggles the wire overlay; edges are drawn
  by `GLLineOverlay` after the mesh. Component modes (B5b, `PROMOTED`):
  1 / 2 / 3 switch to Vertex / Edge / Face (clears selection and hover);
  click selection, hover and W/E/R then work on edges / faces. Selected
  faces are a yellow fill (`GLTriangleOverlay`), selected edges yellow
  lines, hover pale yellow (look `PROVISIONAL`). Contextual C (B6):
  Split / Edge Connect / Vertex Connect from the selection. Knife (B7,
  `PROVISIONAL` interaction): `C` with an empty selection starts a session
  — hover previews the prospective point, LMB click or press-slide-release
  (the pressed edge stays locked) cuts, a line runs from the start to the
  prospective point; Enter commits, Esc cancels, Ctrl+Z / Ctrl+Y /
  Ctrl+Shift+Z undo / redo the last cut. WP-KNIFE-01 UX2 (PROVISIONAL): E or
  a right-click lifts the pen (the next click starts a new cut, nothing is
  committed), a double-click closes the cut and lifts, Shift+click puts the
  point on the edge's midpoint. The press and drag handlers pass the cursor
  position through for this. WP-KNIFE-01 S4 (PROVISIONAL): a far click cuts
  across faces (only the visible part), and a click outside the mesh is a
  point in space that cuts too (it never commits; Enter does).
  WP-KNIFE-01 UX2b (PROVISIONAL): holding Shift already shows the midpoint in
  the Knife's hover preview — the key handlers track the held Shift keys
  (`shift_keys_after`) and report "any Shift held" to
  `Application.set_shift_held`; losing focus (`on_deactivate`) resets it.
  WP-SOFT-01 S2a (`PROVISIONAL`, Manu 2026-10-10, AD-020): Soft Selection, off by
  default. O switches it on/off (the status line shows the full state, e.g.
  `Soft: on · 15 % (0.51) · geodesic · smooth · bands on`); with it on, W/E/R move/rotate/scale
  the selection and a falloff region around it, one History entry per gesture. Shift +
  mouse wheel up/down = radius one step larger/smaller (2 % .. 200 %; this never zooms; the
  window reports "Shift held" with the wheel event — `wheel_input` — and a driver that maps
  Shift+wheel to a horizontal scroll is read from `scroll_x`, direction to be confirmed
  in the S2 test); Shift+O cycles the curve, Ctrl+O the metric. The settings are sticky
  like X/Y/Z and apply from the next gesture on.
  WP-SOFT-01 S2d (`PROVISIONAL`, S2c verdict Manu 2026-10-11, AD-020): geodesic and Smooth
  are the defaults; Shift+O cycles smooth → sphere → root → sharp → linear → custom; Ctrl +
  mouse wheel shapes the `custom` curve (up = rounder, down = sharper, always selects
  `custom`, never zooms — the window tracks Ctrl like Shift, `ctrl_keys_after`, and
  `wheel_input` carries `{"ctrl"}`; Ctrl+Shift+wheel does nothing); Alt+O switches the
  influence bands on/off (no band points at all while off; the status line shows it). With a symmetry definition (only the
  Symmetry Lab sets one) Soft + symmetry is refused visibly.
  WP-SOFT-01 S2b (`PROVISIONAL`, AD-020 §5): with Soft on and a selection, the influence
  region is shown as banded points around the selection (`GLSoftBandOverlay`, an extra
  overlay; four bands over 0 < w < 1, warm = strong .. cold = weak, seeds keep the
  selection look). It follows the selection, the mode, the settings, Undo/Redo and topology
  changes (never the hover); a hover-armed W/E/R shows it once at arm. During a gesture the
  points are the gesture's own weights at the live positions; afterwards the preview
  resumes. Soft off: no band points.
  WP Delete/Dissolve (PROVISIONAL): Delete removes the selection with a
  hole, Backspace dissolves it (Edge / Face: leftover 2-valent vertices
  removed; Vertex: the vertex dissolve), Ctrl+Backspace dissolves Edge /
  Face without that cleanup. Status lines
  (`Application.status_message`) are printed to stdout — `PROVISIONAL`
  until a HUD exists.
- Scene loader (temporary, `PROVISIONAL`, `src/scene_menu.py`): `SPACE`
  opens a small context menu at the cursor listing the available scenes
  (`cube` + the registry assets from `examples/loaders/assets.py`); clicking
  a row loads it through `Application.load_scene` (selection/history/pick
  cache reset, camera re-framed), clicking elsewhere / `SPACE` / `Esc` closes
  it. While open the menu is modal. The key is an engineering proposal
  (INPUT_WIRING_MAP §10 "Load" = TBD) — `SPACE` stays unbound in the
  BindingSet, and the menu only exists when `install_handlers(..., menu=...)`
  is given one, so the Symmetry Lab's shared wiring is unchanged.
- Scene loader (temporary, `PROVISIONAL`, `src/scene_menu.py`): `SPACE`
  opens a small context menu at the cursor listing the available scenes
  (`cube` + the registry assets from `examples/loaders/assets.py`); clicking
  a row loads it through `Application.load_scene` (selection/history/pick
  cache reset, camera re-framed), clicking elsewhere / `SPACE` / `Esc` closes
  it. While open the menu is modal. The key is an engineering proposal
  (INPUT_WIRING_MAP §10 "Load" = TBD) — `SPACE` stays unbound in the
  BindingSet, and the menu only exists when `install_handlers(..., menu=...)`
  is given one, so the Symmetry Lab's shared wiring is unchanged.
- No imports from `playground/` (AD-010 Addendum).

This file is intentionally thin: construction and event translation only,
no business logic. WP-SYM-LAB-03 H6 (2026-10-03): the wiring is importable —
`create_window()`, `install_handlers(window, app, menu=None)` (all event
translation, headless-testable with a stand-in window) and `run(window, app)`
(frame tick + event loop); `main()` composes them with the scene set-up,
behaviour unchanged. Another host (the Symmetry Lab, `experiments/`) reuses
them instead of copying the handlers; `main.py` itself knows no experiment.
The optional `menu` (temporary scene loader, see the list above) is the only
addition and defaults to off, so that host keeps the old behaviour. All state
and execution live in `Application`/`Viewport`
(`src/mirai/application.py`, `src/viewport/viewport.py`), which stay
window-free.

Usage:
    python3 src/main.py                       # head basemesh (default)
    python3 src/main.py cube                   # cube
    python3 src/main.py subd_cube              # registry name (same entries as the SPACE menu)
    python3 src/main.py path/to/mesh.obj       # a different .obj

The window's X button closes it (WP-06 B1, Artist decision A3, 2026-09-26)
— there is no quit hotkey.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent
_ROOT = _SRC.parent
for _p in (str(_SRC), str(_ROOT), str(_ROOT / "examples")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pyglet  # noqa: E402

from mirai.application import Application  # noqa: E402
from mirai.interaction.input import Input  # noqa: E402
from mirai.pyglet_input import (  # noqa: E402
    key_from_pyglet,
    mouse_from_pyglet,
    shift_keys_after,
    wheel_from_pyglet,
)
from mirai.soft_selection import GLSoftBandOverlay  # noqa: E402
from viewport.gl_line_overlay import GLLineOverlay  # noqa: E402
from viewport.gl_point_overlay import GLPointOverlay  # noqa: E402
from viewport.gl_render_store import GLRenderStore  # noqa: E402
from viewport.gl_triangle_overlay import GLTriangleOverlay  # noqa: E402
from scene_menu import SceneMenu, load_named_scene, scene_entries  # noqa: E402

_DEFAULT_HEAD_OBJ = _ROOT / "examples" / "meshes" / "head_basemesh.obj"

#: GL backends handed to `Application.init_scene` (headless callers omit them).
GL_TYPES = {
    "store_type": GLRenderStore,
    "point_overlay_type": GLPointOverlay,
    "line_overlay_type": GLLineOverlay,
    "face_overlay_type": GLTriangleOverlay,
    "soft_overlay_type": GLSoftBandOverlay,
}


def ctrl_keys_after(held: frozenset[int], symbol: int, pressed: bool) -> frozenset[int] | None:
    """The Ctrl keys held after a key event (WP-SOFT-01 S2d), like `shift_keys_after`: the new
    set for `LCTRL`/`RCTRL` (press adds, release removes; key repeat and a release without a
    press change nothing), `None` for any other symbol. Left and right count separately, so a
    Ctrl still held is not read as released. Ctrl alone is no `Input` (no binding); the window
    only needs "any Ctrl held" for the wheel."""
    from pyglet.window import key as _key

    if symbol not in (_key.LCTRL, _key.RCTRL):
        return None
    return held | {symbol} if pressed else held - {symbol}


def wheel_input(
    scroll_x: float, scroll_y: float, shift_held: bool, ctrl_held: bool = False
) -> Input | None:
    """The wheel event as an `Input` (WP-SOFT-01 S2a, AD-020 E5; S2d E6). pyglet's scroll
    event carries no modifiers, so the window passes whether a Shift / Ctrl key is held
    (`shift_keys` / `ctrl_keys` in `install_handlers`): the input then carries `{"shift"}`
    and/or `{"ctrl"}` and the bindings give it its meaning (Shift: Soft radius step, Ctrl:
    shape of the custom Soft curve) - a wheel with either never zooms. Some drivers report
    Shift+wheel as a horizontal scroll (`scroll_y == 0`, `scroll_x != 0`): with a modifier
    held that axis is read instead (the sign is not confirmed yet - Artist test)."""
    modifiers = frozenset(
        name for name, held in (("shift", shift_held), ("ctrl", ctrl_held)) if held
    )
    if modifiers and scroll_y == 0:
        scroll_y = scroll_x
    inp = wheel_from_pyglet(scroll_y)
    if inp is not None and modifiers:
        inp = Input("wheel", inp.value, modifiers)
    return inp


def create_window(caption: str = "Mirai — Stage B"):
    """The resizable 1024x768 window. Create it before `init_scene()`:
    GLRenderStore needs an active GL context for its first `allocate()` (its
    shader is compiled lazily "on first use", see `viewport.gl_render_store`
    module docstring) — pyglet only creates that context together with its
    first Window."""
    return pyglet.window.Window(width=1024, height=768, resizable=True, caption=caption)


def install_handlers(window, app: Application, menu: SceneMenu | None = None) -> None:
    """Translates the window's events to `app` (WP-SYM-LAB-03 H6). Needs only
    `window.event` (decorator), `window.width`/`height` and, when drawn,
    `window.clear()` — headless-testable with a stand-in window.

    `menu` (temporary, `PROVISIONAL`, `src/scene_menu.py`): the scene loader.
    `None` (default) keeps this wiring exactly as it was — the Symmetry Lab
    shares it and therefore gets no menu. While the menu is open it is
    modal: keys, mouse press/drag/release, motion and the wheel are swallowed
    instead of being forwarded to `app`."""

    # Temporary scene loader: last known cursor (None = centre of the window).
    cursor: tuple[float, float] | None = None

    @window.event
    def on_resize(width: int, height: int):
        app.set_viewport_size(window.width, window.height)
        return pyglet.event.EVENT_HANDLED

    # WP-KNIFE-01 UX2b: the Shift keys held right now. Shift alone is no `Input`
    # (no binding); the Knife's hover only needs "any Shift held". Both keys
    # count, so releasing one while the other is held keeps it held.
    shift_keys: frozenset[int] = frozenset()

    def track_shift(symbol: int, pressed: bool) -> None:
        nonlocal shift_keys
        held = shift_keys_after(shift_keys, symbol, pressed)
        if held is not None:
            shift_keys = held
            app.set_shift_held(bool(held))

    # WP-SOFT-01 S2d: the Ctrl keys held right now, for the wheel only (Ctrl+wheel = shape
    # of the custom Soft curve). `Application` never needs to know.
    ctrl_keys: frozenset[int] = frozenset()

    def track_ctrl(symbol: int, pressed: bool) -> None:
        nonlocal ctrl_keys
        held = ctrl_keys_after(ctrl_keys, symbol, pressed)
        if held is not None:
            ctrl_keys = held

    @window.event
    def on_key_press(symbol: int, modifiers: int):
        inp = key_from_pyglet(symbol, modifiers)
        if menu is not None and menu.is_open:
            # Modal: the menu swallows every key; SPACE/Esc closes it.
            menu.key(inp)
            return pyglet.event.EVENT_HANDLED
        if (
            menu is not None
            and inp is not None
            and inp.kind == "key"
            and inp.value == "space"
            and not inp.modifiers
            # No menu in the middle of a running gesture (W/E/R/T, Knife).
            and app.interaction_owner is None
            and not app.pointer.active
        ):
            fallback = (window.width / 2, window.height / 2)
            cx, cy = cursor if cursor is not None else fallback
            menu.open(cx, cy, window.width, window.height)
            return pyglet.event.EVENT_HANDLED
        track_shift(symbol, True)
        track_ctrl(symbol, True)
        if inp is not None:
            app.key_press(inp)
        # Always handled: pyglet's default handler would close the window on
        # Esc, but Esc is Cancel only (B1 A3 — the X button closes).
        return pyglet.event.EVENT_HANDLED

    @window.event
    def on_key_release(symbol: int, modifiers: int):
        # A release only ever clears: tracked even under the modal menu, so a Ctrl let go
        # there cannot stay "held" and turn the plain wheel into a curve-shape step.
        track_ctrl(symbol, False)
        if menu is not None and menu.is_open:
            return pyglet.event.EVENT_HANDLED
        track_shift(symbol, False)
        inp = key_from_pyglet(symbol, modifiers)
        if inp is not None:
            app.key_release(inp)
        return pyglet.event.EVENT_HANDLED

    @window.event
    def on_deactivate():
        # A Shift/Ctrl released while another window has focus sends no release here.
        nonlocal shift_keys, ctrl_keys
        shift_keys = frozenset()
        ctrl_keys = frozenset()
        app.set_shift_held(False)
        # The menu must not outlive the focus (it would stay modal).
        if menu is not None:
            menu.close()

    @window.event
    def on_mouse_press(x: int, y: int, button: int, modifiers: int):
        if menu is not None and menu.is_open:
            # A hit loads the row, a miss closes the menu — never forwarded.
            menu.press(x, y)
            return pyglet.event.EVENT_HANDLED
        inp = mouse_from_pyglet(button, modifiers)
        if inp is not None:
            app.pointer_press(inp, x, y)

    @window.event
    def on_mouse_drag(x: int, y: int, dx: int, dy: int, buttons: int, modifiers: int):
        if menu is not None and menu.is_open:
            return pyglet.event.EVENT_HANDLED
        app.pointer_drag(dx, dy, x, y)

    @window.event
    def on_mouse_release(x: int, y: int, button: int, modifiers: int):
        if menu is not None and menu.is_open:
            return pyglet.event.EVENT_HANDLED
        inp = mouse_from_pyglet(button, modifiers)
        if inp is not None:
            app.pointer_release(inp.value, x, y)

    @window.event
    def on_mouse_motion(x: int, y: int, dx: int, dy: int):
        nonlocal cursor
        cursor = (x, y)
        if menu is not None and menu.is_open:
            menu.motion(x, y)
            return pyglet.event.EVENT_HANDLED
        app.pointer_motion(x, y, dx, dy)

    @window.event
    def on_mouse_leave(x: int, y: int):
        if menu is not None and menu.is_open:
            menu.motion(-1.0, -1.0)
        app.pointer_leave()

    @window.event
    def on_mouse_scroll(x: int, y: int, scroll_x: float, scroll_y: float):
        if menu is not None and menu.is_open:
            return pyglet.event.EVENT_HANDLED
        inp = wheel_input(scroll_x, scroll_y, bool(shift_keys), bool(ctrl_keys))
        if inp is not None:
            app.pointer_scroll(inp)

    @window.event
    def on_draw():
        from pyglet import gl

        gl.glClearColor(0.05, 0.05, 0.08, 1.0)
        window.clear()
        app.viewport.sync()
        app.viewport.render()
        if menu is not None and menu.is_open:
            menu.draw()


def run(window, app: Application) -> None:
    """Frame tick + pyglet event loop; returns when the window closes."""
    status_seen = app.status_serial

    def _tick(dt: float) -> None:
        nonlocal status_seen
        # Keeps `viewport.sync()` running once per frame even without a
        # camera event (Stage B hook — no behavior change for this package).
        app.update_viewport(dt)
        # Console status (B3, E26) — PROVISIONAL until a HUD exists.
        if app.status_serial != status_seen:
            status_seen = app.status_serial
            print(app.status_message, flush=True)

    pyglet.clock.schedule_interval(_tick, 1 / 60.0)
    pyglet.app.run()


def main() -> None:
    window = create_window()

    app = Application()

    entries = scene_entries()
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    if arg == "cube":
        app.init_scene("cube", **GL_TYPES)
    elif arg is not None and arg in entries:
        # Registry name — the same entry list the SPACE menu shows.
        if not load_named_scene(app, arg, GL_TYPES):
            print(f"Failed to load scene '{arg}'", file=sys.stderr)
            app.init_scene("cube", **GL_TYPES)
    else:
        obj_path = Path(arg) if arg is not None else _DEFAULT_HEAD_OBJ
        try:
            app.init_scene("obj", obj_path=obj_path, **GL_TYPES)
        except Exception as exc:
            print(f"Failed to load '{obj_path}': {exc}", file=sys.stderr)
            app.init_scene("cube", **GL_TYPES)

    app.frame_scene()

    # Initial size/aspect so the first frame is not distorted (before any
    # resize or camera event has fired).
    app.set_viewport_size(window.width, window.height)

    # Temporary scene loader (PROVISIONAL): SPACE opens it at the cursor.
    menu = SceneMenu(entries, load=lambda name: load_named_scene(app, name, GL_TYPES))
    install_handlers(window, app, menu=menu)
    run(window, app)


if __name__ == "__main__":
    main()
