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
  by `GLLineOverlay` after the mesh. Flat shades one normal per polygon and
  Smooth blends the normals bilinearly over each quad, so no triangulation
  diagonal shows (B5a.1, 2026-10-15). Worklight (Shading Lab promoted
  2026-10-15, keys `PROVISIONAL`): Key + Fill, start "Raitt 2:1" following the
  camera; Ctrl+D cycles Raitt 2:1 → Softbox → Warm/Kalt → Heute, Ctrl+Shift+D
  toggles camera / world. Component modes (B5b, `PROMOTED`):
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
  `wheel_input` carries `{"ctrl"}`; Ctrl+Shift+wheel is the Loop / Ring balance since 2026-10-22, AD-020
  "Loop / Ring flow"); Alt+O switches the
  influence bands on/off (no band points at all while off; the status line shows it). With a symmetry definition
  (Shift+S, below) W/E/R act on both sides (AD-SYM-04 SS2) and the bands show both sides, the
  symmetric field (SS3); a selected vertex without a mirror partner shows no bands and is refused
  visibly at the first motion.
  Symmetry (AD-SYM-04 slice A1, Q-1 = E-1, key `PROVISIONAL`): Shift+S cycles the mesh's symmetry
  off → X → Y → Z → off (plane through the origin, seam = the edges at exactly 0 on that axis), one
  Undo step each; the status line says `Symmetrie X (valid)` / `Symmetrie X (partial, 54 ohne
  Partner)` / `Symmetrie aus`. With symmetry on, W/E/R, C (Split / Edge Connect / Vertex Connect /
  Knife), Delete / Dissolve and T mirror by themselves (`Application`; this file adds no symmetry
  code and installs no gate, AD-013 H2-R5 as amended 2026-10-14). Ignored while W/E/R/T is held
  or a Knife session runs. Display (AD-SYM-04 slice A2, Q-2 = S-2, look `PROVISIONAL`): with
  symmetry on, the plane is drawn as a light-blue outline through the origin (mesh bounds + 10 %),
  and the problem markers as points - seam vertices green, vertices without a mirror partner
  magenta, ambiguous ones white; no partner markers. The only symmetry import here is that GL
  sink, `GLSymmetryOverlay` in `GL_TYPES` (T-G3b as narrowed); `Application` owns what it shows
  (`mirai.symmetry_display`) and keeps the outline and markers from the drag start while W/E/R/T
  runs (the markers follow the moved vertices).
  WP-SOFT-01 S2b (`PROVISIONAL`, AD-020 §5): with Soft on and a selection, the influence
  region is shown as banded points around the selection (`GLSoftBandOverlay`, an extra
  overlay; four bands over 0 < w < 1, warm = strong .. cold = weak, seeds keep the
  selection look). It follows the selection, the mode, the settings, Undo/Redo and topology
  changes; during a gesture the points are the gesture's own weights at the live positions;
  afterwards the preview resumes. Soft off: no band points.
  Hover preview and display modes (`PROVISIONAL`, 2026-10-22, AD-020): with no selection the
  preview is the influence region of the hovered component (current Vertex/Edge/Face mode;
  recomputed when the hovered component changes, never per pointer move); with a selection it
  stays the selection's region and the hover is only the highlight. Alt+Shift+O switches the
  display between the vertex bands and face shading (`GLSoftShadingOverlay`, translucent
  corner colours under the wire and highlights); only one is shown. Alt+O hides/shows the
  active one - Soft stays on. View state only: not in scene files or History.
  WP Delete/Dissolve (PROVISIONAL): Delete removes the selection with a
  hole, Backspace dissolves it (Edge / Face: leftover 2-valent vertices
  removed; Vertex: the vertex dissolve), Ctrl+Backspace dissolves Edge /
  Face without that cleanup. WP Toolbox Gaps B1: Shift+C collapses each
  connected group of the V/E/F selection to one point at its centroid and
  selects the points in Vertex mode (`PROVISIONAL`). C2: hold S = Smooth,
  hold Alt+S = Relax (a tap = one step, drag right/left = stronger/weaker,
  release commits, Esc restores; `PROVISIONAL`). Status lines
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
  AD-021 M1 (Q-10): Shift+click on a row adds it to the scene as a Reference
  instead (`Application.add_reference`, one Undo step, the camera stays, Q-9).
- Add Mesh (Track A1, `PROVISIONAL`, `src/scene_menu.py`): `Shift+A` opens a menu at the cursor with
  Plane (4x4 grid), Cube, Sphere (32x16), Cylinder (32); a click adds the primitive as a Normal
  object at the origin (`Application.add_primitive`, one Undo step): Object mode `4`, the new object
  is the selection (W/E/R place it, 1/2/3 edit it), the edit object stays. Window-level like SPACE
  (`install_handlers(..., add_menu=...)`), not in the BindingSet.
- Mirror pairs (2026-10-23, `PROVISIONAL`, OBJECT_MIRROR_SYMMETRY_PROPOSAL): `Shift+M` opens the "Mirror"
  menu (window level like Shift+A; bare M stays the Morph Lab bridge): Mirror copy / Pair selected across
  X/Y/Z = 0, Break pair, Re-sync pair - mode `4`, on the selected objects (`Application.mirror_copy`, ...).
  A paired object's partner follows W/E/R and the gizmo mirrored (`install_handlers(..., mirror_menu=...)`).
- Scene files (`PROVISIONAL`, Manu 2026-10-15, `src/scene_files.py`): the
  SPACE menu starts with "Szene speichern (Strg+S)", "Als neue Szene
  speichern" and the saved scenes in `scenes/` ("Datei: <name>", newest
  first); clicking a file row loads it (all objects, the edit object,
  symmetry; selection/history reset, camera re-framed). Ctrl+S overwrites the
  current scene file (the one last loaded or saved), else writes a new
  `scenes/<edit object>_<date-time>.mirai.json`; refused while W/E/R/T or a
  Knife session runs. Like SPACE it is window-level (`install_handlers(...,
  save=...)`), not in the BindingSet.
- Morph Lab bridge (`PROVISIONAL`, Manu 2026-10-17, `src/morph_bridge.py`): `M` sends the
  selected object (mode `4`: the one selected; otherwise the edit object) to the Morph Lab, which
  opens in its own window with base and target already built. Window-level like Ctrl+S
  (`install_handlers(..., morph=...)`), not in the BindingSet; refused while W/E/R/T or a Knife
  session runs. This file only calls the bridge and knows no experiment.
- Objects (AD-021 M1, `PROVISIONAL` look and click): `4` = Object mode. A
  Reference is drawn in a muted blue (no selection overlays, never pickable in
  `1`/`2`/`3`, picking goes through it); in `4` a click selects (Shift/Ctrl/Alt
  add, remove, toggle) and the selected objects are drawn tinted yellow;
  Alt+R switches the selected objects Reference <-> Normal (one Undo step; the
  edited object stays Normal) - Q-12 revised 2026-10-16, a plain click no
  longer switches. T, C,
  Dissolve and Shift+S are refused in `4` (status line); Delete there deletes the selected
  objects (Track A2, `PROVISIONAL`: one Undo step, the edit object moves to a surviving Normal
  object, the last object / only References left is refused). AD-021 M2-0
  (`PROVISIONAL` key and alpha): Alt+D draws every Reference as a translucent
  Ghost / shaded again; References stay drawn in Wireframe. AD-021 M2-2: in
  `4`, hold W/E/R on the selected objects = move / rotate / scale them
  (object level, one Undo step; X/Y/Z are world axes, Scale always uniform;
  a Reference is locked and stays), Esc cancels exactly. AD-021 M2-3
  (`PROVISIONAL` keys): in `4`, Ctrl+A = Apply transform (bake the placement
  into the mesh), Alt+Shift+A = Clear transform (placement back to identity).
  AD-021 M2-4: in `4` select one Normal object, then 1/2/3 = edit that object;
  Undo/Redo switch back to the object a step was made on.
- Playground tools promoted 2026-10-15 (Manu; keys and look `PROVISIONAL`): LMB drag
  from empty space = Box Select (rubber band drawn here, `draw_selection_box`; with the Lasso key `Q` held a
  Lasso outline, `draw_selection_lasso`), from the mesh
  = Paint Select; no modifier replaces, Shift adds; Esc discards. Alt held at the release of a Box /
  Lasso selects through the mesh (WP Toolbox Gaps A2, band drawn blue meanwhile). Ctrl+LMB drag = Tweak with
  the last W/E/R (Move until one is pressed; a tap sets it) on the selection, else on the
  element under the press point; Ctrl+LMB click still removes. Edge mode: Shift+L / Shift+R
  add the edge loop / ring, I inserts a loop through the ring, hold G slides the selected
  loop(s); under symmetry Loop Insert and Loop Slide mirror. All in `Application`.
- Transform gizmo (2026-10-21, promoted from the Playground, AD-016 D3; look `PROVISIONAL`): with a point / edge / face
  selection a world-axis gizmo is drawn at its centroid (`draw_gizmo`), shaped for the current tool (the last W/E/R).
  LMB on a handle sets the constraint, LMB drag runs the tool along it, release commits, Esc cancels. All in
  `Application` (`gizmo_enabled` is set here only).
  Also shown for a placed edit object (2026-10-23): at the selection's world position, world axes.
  Object level (2026-10-23, `PROVISIONAL`): in mode `4` the same gizmo sits at the centroid of the selected
  Normal objects' pivots (Reference: none) and drives the object gesture along the world axes.
  World / Normal (WP Toolbox Gaps C1, `PROVISIONAL`): K toggles the transform space; in Normal the gizmo and
  X/Y/Z use the selection's frame (one face: first edge / normal × edge / normal; otherwise the normal only),
  shown in the HUD row "Space" (`mirai.transform_space`).
- SubD preview (2026-10-23, `PROVISIONAL` keys, `mirai.subdivision`, promoted from the SubD Lab): V cycles
  off → smooth surface + cage → smooth surface + isolines, Ctrl+1/2/3 the level (start 2), Shift+V the cage's
  depth (hidden by the surface / always visible), Alt+V the opacity of the cage in the isoline view; in a SubD
  view Shift+D hides / shows the cage or isolines (highlights stay) instead of the wire overlay. A hovered /
  selected edge lights up on the cage and as its isoline chain on the surface. View state only; all tools keep
  editing the cage. Lives in
  `Application` (binding context `subd`); this file only adds its GL sink `GLSubdLineOverlay` to `GL_TYPES`.
- HUD (GUI Stage 1, 2026-10-23, `PROVISIONAL` look, `src/hud.py`): a read-only state display over the
  viewport (mode, tool, constraint, symmetry, display, Soft, SubD, last status message) replaces the console
  as the place to read the status; the console print stays as a fallback. `H` (Input Truth
  `application.toggle_hud`, binding context `window`, never resolved by `Application`) steps bar -> corner
  -> hidden while both layout variants are on trial. Window level like the menus: `install_handlers(...,
  hud=None)` keeps the old wiring for the Labs.
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
    python3 src/main.py scenes/x.mirai.json    # a saved scene file

The window's X button closes it (WP-06 B1, Artist decision A3, 2026-09-26)
— there is no quit hotkey.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

_SRC = Path(__file__).resolve().parent
_ROOT = _SRC.parent
for _p in (str(_SRC), str(_ROOT), str(_ROOT / "examples")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pyglet  # noqa: E402

from mirai.application import Application  # noqa: E402
from mirai.cursor_wrap import CursorWrapper  # noqa: E402
from mirai.interaction import commands  # noqa: E402
from mirai.interaction.input import WINDOW_CONTEXT, Input  # noqa: E402
from mirai.pyglet_input import (  # noqa: E402
    key_from_pyglet,
    mouse_from_pyglet,
    shift_keys_after,
    wheel_from_pyglet,
)
from mirai.soft_selection import GLSoftBandOverlay, GLSoftShadingOverlay  # noqa: E402
from mirai.subdivision.gl_lines import GLSubdLineOverlay  # noqa: E402
from viewport.gl_gizmo_overlay import draw_gizmo  # noqa: E402
from viewport.gl_line_overlay import GLLineOverlay  # noqa: E402
from viewport.gl_point_overlay import GLPointOverlay  # noqa: E402
from viewport.gl_render_store import GLRenderStore  # noqa: E402
from viewport.gl_symmetry_overlay import GLSymmetryOverlay  # noqa: E402
from viewport.gl_triangle_overlay import GLTriangleOverlay  # noqa: E402
from hud import Hud  # noqa: E402
from morph_bridge import send_to_morph_lab  # noqa: E402
from scene_files import SceneFiles, is_scene_file  # noqa: E402
from scene_menu import (  # noqa: E402
    SceneMenu,
    add_mesh_entries,
    add_named_reference,
    add_primitive_named,
    load_named_scene,
    mirror_entries,
    run_mirror_entry,
    scene_entries,
)

_DEFAULT_HEAD_OBJ = _ROOT / "examples" / "meshes" / "head_basemesh.obj"

#: GL backends handed to `Application.init_scene` (headless callers omit them).
GL_TYPES = {
    "store_type": GLRenderStore,
    "point_overlay_type": GLPointOverlay,
    "line_overlay_type": GLLineOverlay,
    "face_overlay_type": GLTriangleOverlay,
    "soft_overlay_type": GLSoftBandOverlay,
    "soft_shading_overlay_type": GLSoftShadingOverlay,
    "symmetry_overlay_type": GLSymmetryOverlay,
    "subd_overlay_type": GLSubdLineOverlay,
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


def alt_keys_after(held: frozenset[int], symbol: int, pressed: bool) -> frozenset[int] | None:
    """The Alt keys held after a key event, like `ctrl_keys_after` (2026-10-22: Alt during a transform
    orbits, `Application.set_alt_held`)."""
    from pyglet.window import key as _key

    if symbol not in (_key.LALT, _key.RALT):
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


def is_save_key(inp: Input | None) -> bool:
    """Ctrl+S (scene files, `PROVISIONAL`): exactly Ctrl, no other modifier."""
    return (
        inp is not None
        and inp.kind == "key"
        and inp.value == "s"
        and inp.modifiers == frozenset({"ctrl"})
    )


def is_morph_key(inp: Input | None) -> bool:
    """M (bridge to the Morph Lab, `PROVISIONAL`): exactly M, no modifier."""
    return (
        inp is not None and inp.kind == "key" and inp.value == "m" and not inp.modifiers
    )


def is_hud_key(app: Application, inp: Input | None) -> bool:
    """The HUD key (`H`, Input Truth `application.toggle_hud`): whatever the bindings resolve to
    `ToggleHud` in the window context, so a `keymap.json` can move it."""
    return (
        inp is not None
        and inp.kind == "key"
        and app.bindings.command_for(inp, WINDOW_CONTEXT) == commands.TOGGLE_HUD
    )


def install_handlers(
    window,
    app: Application,
    menu: SceneMenu | None = None,
    save: Callable[[], object] | None = None,
    morph: Callable[[], object] | None = None,
    add_menu: SceneMenu | None = None,
    mirror_menu: SceneMenu | None = None,
    hud: Hud | None = None,
) -> None:
    """Translates the window's events to `app` (WP-SYM-LAB-03 H6). Needs only
    `window.event` (decorator), `window.width`/`height` and, when drawn,
    `window.clear()` — headless-testable with a stand-in window.

    `menu` (temporary, `PROVISIONAL`, `src/scene_menu.py`): the scene loader.
    `None` (default) keeps this wiring exactly as it was — the Symmetry Lab
    shares it and therefore gets no menu. While the menu is open it is
    modal: keys, mouse press/drag/release, motion and the wheel are swallowed
    instead of being forwarded to `app`.

    `save` (scene files, `PROVISIONAL`, `src/scene_files.py`): called on Ctrl+S
    instead of forwarding that key to `app`. `None` (default) keeps the wiring
    as it was. `Application.save_scene_file` refuses during a gesture itself.

    `morph` (bridge to the Morph Lab, `PROVISIONAL`, `src/morph_bridge.py`): called on M instead
    of forwarding that key to `app`. `None` (default) keeps the wiring as it was, so the labs
    that share it get no M (the Morph Lab's own M is its A/B key).

    `add_menu` (Track A1, `PROVISIONAL`, `src/scene_menu.py`): the "Add Mesh" menu, opened on Shift+A
    at the cursor like the scene menu (window level; no binding). Modal in the same way; `None`
    (default) keeps the wiring as it was.

    `mirror_menu` (mirror pairs, `PROVISIONAL`): the "Mirror" menu, opened on Shift+M at the cursor in
    the same way as `add_menu`; `None` (default) keeps the wiring as it was.

    `hud` (GUI Stage 1, `PROVISIONAL`, `src/hud.py`): the read-only state display, drawn last but
    under an open menu; `H` steps its layout / hides it. It only reads `app`. `None` (default) keeps
    the wiring as it was."""

    # Temporary scene loader: last known cursor (None = centre of the window).
    cursor: tuple[float, float] | None = None

    def open_menu() -> SceneMenu | None:
        """The menu that is open right now (the scene loader or "Add Mesh"), else None."""
        for candidate in (menu, add_menu, mirror_menu):
            if candidate is not None and candidate.is_open:
                return candidate
        return None

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

    # WP-SOFT-01 S2d: the Ctrl keys held right now, for the wheel (Ctrl+wheel = shape of the custom
    # Soft curve) and, since 2026-10-22, `Application.set_ctrl_held` (Ctrl = snap in a transform).
    ctrl_keys: frozenset[int] = frozenset()

    def track_ctrl(symbol: int, pressed: bool) -> None:
        nonlocal ctrl_keys
        held = ctrl_keys_after(ctrl_keys, symbol, pressed)
        if held is not None:
            ctrl_keys = held
            app.set_ctrl_held(bool(held))

    # 2026-10-22: the Alt keys held right now (`Application.set_alt_held`: Alt during a transform orbits).
    alt_keys: frozenset[int] = frozenset()

    def track_alt(symbol: int, pressed: bool) -> None:
        nonlocal alt_keys
        held = alt_keys_after(alt_keys, symbol, pressed)
        if held is not None:
            alt_keys = held
            app.set_alt_held(bool(held))

    # 2026-10-22: the pointer leaves the viewport on one side and comes back on the other during a transform.
    wrapper = CursorWrapper(window, app)

    @window.event
    def on_key_press(symbol: int, modifiers: int):
        inp = key_from_pyglet(symbol, modifiers)
        shown = open_menu()
        if shown is not None:
            # Modal: the menu swallows every key; SPACE/Esc closes it.
            shown.key(inp)
            return pyglet.event.EVENT_HANDLED
        for shift_menu, letter in ((add_menu, "a"), (mirror_menu, "m")):
            if (
                shift_menu is not None
                and inp is not None
                and inp.kind == "key"
                and inp.value == letter
                and inp.modifiers == frozenset({"shift"})
                and app.interaction_owner is None
                and not app.pointer.active
            ):
                fallback = (window.width / 2, window.height / 2)
                cx, cy = cursor if cursor is not None else fallback
                shift_menu.open(cx, cy, window.width, window.height)
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
        if save is not None and is_save_key(inp):
            save()
            return pyglet.event.EVENT_HANDLED
        if morph is not None and is_morph_key(inp):
            morph()
            return pyglet.event.EVENT_HANDLED
        if hud is not None and is_hud_key(app, inp):
            hud.toggle()
            return pyglet.event.EVENT_HANDLED
        track_shift(symbol, True)
        track_ctrl(symbol, True)
        track_alt(symbol, True)
        if inp is not None:
            app.key_press(inp)
        # Always handled: pyglet's default handler would close the window on
        # Esc, but Esc is Cancel only (B1 A3 — the X button closes).
        return pyglet.event.EVENT_HANDLED

    @window.event
    def on_key_release(symbol: int, modifiers: int):
        # A release only ever clears: tracked even under the modal menu, so a Ctrl let go
        # there cannot stay "held" and turn the plain wheel into a curve-shape step. Shift too:
        # Shift+A opens "Add Mesh" with Shift held, and its release arrives under the open menu.
        track_ctrl(symbol, False)
        track_alt(symbol, False)
        track_shift(symbol, False)
        if open_menu() is not None:
            return pyglet.event.EVENT_HANDLED
        inp = key_from_pyglet(symbol, modifiers)
        if inp is not None:
            app.key_release(inp)
        return pyglet.event.EVENT_HANDLED

    @window.event
    def on_deactivate():
        # A Shift/Ctrl released while another window has focus sends no release here.
        nonlocal shift_keys, ctrl_keys, alt_keys
        shift_keys = frozenset()
        ctrl_keys = frozenset()
        alt_keys = frozenset()
        app.set_shift_held(False)
        app.set_ctrl_held(False)
        app.set_alt_held(False)
        # The menu must not outlive the focus (it would stay modal).
        for candidate in (menu, add_menu, mirror_menu):
            if candidate is not None:
                candidate.close()

    @window.event
    def on_mouse_press(x: int, y: int, button: int, modifiers: int):
        inp = mouse_from_pyglet(button, modifiers)
        shown = open_menu()
        if shown is not None:
            # A hit loads the row (Shift: adds it as a Reference, AD-021 Q-10; in "Add Mesh" a
            # hit adds the primitive), a miss closes the menu — never forwarded.
            shown.press(x, y, add=inp is not None and "shift" in inp.modifiers)
            return pyglet.event.EVENT_HANDLED
        if inp is not None:
            app.pointer_press(inp, x, y)

    @window.event
    def on_mouse_drag(x: int, y: int, dx: int, dy: int, buttons: int, modifiers: int):
        if open_menu() is not None:
            return pyglet.event.EVENT_HANDLED
        step = wrapper.filter(x, y, dx, dy)
        if step is None:
            return
        app.pointer_drag(step[0], step[1], x, y)
        wrapper.after_event(x, y)

    @window.event
    def on_mouse_release(x: int, y: int, button: int, modifiers: int):
        if open_menu() is not None:
            return pyglet.event.EVENT_HANDLED
        inp = mouse_from_pyglet(button, modifiers)
        if inp is not None:
            app.pointer_release(inp.value, x, y)

    @window.event
    def on_mouse_motion(x: int, y: int, dx: int, dy: int):
        nonlocal cursor
        cursor = (x, y)
        shown = open_menu()
        if shown is not None:
            shown.motion(x, y)
            return pyglet.event.EVENT_HANDLED
        step = wrapper.filter(x, y, dx, dy)
        if step is None:
            return
        app.pointer_motion(x, y, step[0], step[1])
        wrapper.after_event(x, y)

    @window.event
    def on_mouse_leave(x: int, y: int):
        shown = open_menu()
        if shown is not None:
            shown.motion(-1.0, -1.0)
        app.pointer_leave()

    @window.event
    def on_mouse_scroll(x: int, y: int, scroll_x: float, scroll_y: float):
        if open_menu() is not None:
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
        gizmo = app.gizmo_items()
        if gizmo:
            draw_gizmo(gizmo, app.gizmo_camera_uniforms())
        box = app.selection_box
        if box is not None:
            draw_selection_box(box, through=app.selection_through)
        lasso = app.selection_lasso
        if lasso is not None:
            draw_selection_lasso(lasso, through=app.selection_through)
        if hud is not None:
            hud.update(app, window.width, window.height)
            hud.draw()
        shown = open_menu()
        if shown is not None:
            shown.draw()


#: Rubber band / lasso colour (look `PROVISIONAL`): pale yellow = only what is visible; cool blue
#: while Alt is held = select through the mesh (WP Toolbox Gaps A2, `Application.selection_through`).
BAND_RGB = (255, 236, 160)
BAND_THROUGH_RGB = (150, 205, 255)


def draw_selection_box(box: tuple[float, float, float, float], through: bool = False) -> None:
    """The Box Select rubber band (window pixels; look `PROVISIONAL`): a thin pale outline
    over the viewport, drawn like the menu (depth off, blending on); blue while it selects through."""
    from pyglet import gl, shapes

    x0, y0, x1, y1 = box
    rgb = BAND_THROUGH_RGB if through else BAND_RGB
    gl.glDisable(gl.GL_DEPTH_TEST)
    gl.glEnable(gl.GL_BLEND)
    gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
    shapes.Rectangle(x0, y0, x1 - x0, y1 - y0, color=(*rgb, 28)).draw()
    shapes.Box(x0, y0, x1 - x0, y1 - y0, thickness=1, color=(*rgb, 200)).draw()


_LASSO_DRAW: dict = {"points": None, "through": None, "batch": None, "shapes": None}


def draw_selection_lasso(points: list[tuple[float, float]], through: bool = False) -> None:
    """The Lasso Select outline (window pixels; look `PROVISIONAL`, same colours as the Box band): the path
    drawn so far plus a fainter closing line back to the first point; blue while it selects through. The
    line batch is rebuilt only when the outline grew or the colour changed, not every frame."""
    from pyglet import gl, graphics, shapes

    if len(points) < 2:
        return
    cache = _LASSO_DRAW
    if cache["points"] != points or cache["through"] != through:
        rgb = BAND_THROUGH_RGB if through else BAND_RGB
        batch = graphics.Batch()
        lines = [
            shapes.Line(a[0], a[1], b[0], b[1], thickness=1, color=(*rgb, 220), batch=batch)
            for a, b in zip(points, points[1:])
        ]
        lines.append(shapes.Line(points[-1][0], points[-1][1], points[0][0], points[0][1], thickness=1,
                                 color=(*rgb, 90), batch=batch))
        cache["points"], cache["through"], cache["batch"], cache["shapes"] = list(points), through, batch, lines
    gl.glDisable(gl.GL_DEPTH_TEST)
    gl.glEnable(gl.GL_BLEND)
    gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
    cache["batch"].draw()


def run(window, app: Application) -> None:
    """Frame tick + pyglet event loop; returns when the window closes."""
    status_seen = app.status_serial
    # WP-VIEW-PERF-01 Slice 2: mouse moves and wheel notches between two ticks pick the hover
    # once, in `_tick` (`Application.flush_hover`) - not once per event.
    app.coalesce_hover = True

    def _tick(dt: float) -> None:
        nonlocal status_seen
        # Keeps `viewport.sync()` running once per frame even without a
        # camera event (Stage B hook — no behavior change for this package).
        app.update_viewport(dt)
        # Console status (B3, E26): the fallback behind the HUD (`src/hud.py`, GUI Stage 1).
        if app.status_serial != status_seen:
            status_seen = app.status_serial
            print(app.status_message, flush=True)

    pyglet.clock.schedule_interval(_tick, 1 / 60.0)
    pyglet.app.run()


def main() -> None:
    window = create_window()

    app = Application()
    app.gizmo_enabled = True  # this window draws the gizmo (`draw_gizmo`); Labs on Application do not
    files = SceneFiles(app, gl_types=GL_TYPES)

    entries = scene_entries()
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    if arg is not None and is_scene_file(arg):
        app.init_scene("cube", **GL_TYPES)
        if not files.load(arg):
            print(app.status_message, file=sys.stderr)
    elif arg == "cube":
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

    # Temporary scene loader (PROVISIONAL): SPACE opens it at the cursor; the
    # scene-file rows come first and are re-read on every open.
    def load(name: str) -> bool:
        if files.handles(name):
            return files.activate(name)
        loaded = load_named_scene(app, name, GL_TYPES)
        if loaded:
            files.forget()
        return loaded

    def add(name: str) -> bool:
        if files.handles(name):
            return files.refuse_add(name)
        return add_named_reference(app, name)

    menu = SceneMenu(
        files.entries() + entries,
        load=load,
        add=add,
        refresh=lambda: files.entries() + scene_entries(),
    )
    add_menu = SceneMenu(
        add_mesh_entries(),
        load=lambda name: add_primitive_named(app, name),
        title="Add Mesh (Shift+A)",
    )
    mirror_menu = SceneMenu(
        mirror_entries(),
        load=lambda name: run_mirror_entry(app, name),
        title="Mirror (Shift+M) - mode 4, selected objects",
    )
    install_handlers(
        window,
        app,
        menu=menu,
        save=files.save,
        morph=lambda: send_to_morph_lab(app),
        add_menu=add_menu,
        mirror_menu=mirror_menu,
        hud=Hud(app.bindings),
    )
    run(window, app)


if __name__ == "__main__":
    main()
