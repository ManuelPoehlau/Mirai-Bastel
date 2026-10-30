"""The interaction scenario driver (AD-027 §6): feeds an `Application` the events a hand makes, through public
entry points only - `key_press/release`, `pointer_press/drag/release/motion/scroll/leave`, `set_shift/ctrl/alt_held`,
`update_viewport` - and the public calls hosts make (`add_primitive`, `mirror_copy`, `create_morph_target`, ...). It
never calls `dispatch_command` and reads no private `Application` member. After every event it calls
`update_viewport(0)`, the window's frame tick.

The scenarios themselves are `tests/test_interaction_scenarios.py` (V1-V7 of AD-027 §1.1 and Manu's test points,
readable steps with explicit assertions). `observe` is the full observation of one moment the restructuring was
checked against (E1, E2); `tests/test_interaction_structure.py` uses it for the purity of `can_run` (E5 iv).

Lifecycle (AD-027 C1): the randomised digest corpus recorded on `dfd6e5d`, its generator and the E2 command line
were a migration oracle for M0-M8 and are gone (last commit with them: the M8.1 commit, `4ccc13c`).
"""

from __future__ import annotations

import dataclasses
import enum
import hashlib
import sys
from array import array
from itertools import chain
from pathlib import Path
from typing import Any, Callable

_TESTS = Path(__file__).resolve().parent
_REPO = _TESTS.parent
for _path in (str(_REPO / "examples"), str(_REPO / "src"), str(_REPO)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from core import EdgeId, FaceId, Mesh, ObjectId, Scene, Selection, SelectionMode, VertexId  # noqa: E402
from hud import hud_state  # noqa: E402
from loaders.assets import asset_path  # noqa: E402
from mirai import object_space  # noqa: E402
from mirai.object_space import ObjectSpaceCamera  # noqa: E402
from mirai.application import Application  # noqa: E402
from mirai.interaction import commands  # noqa: E402
from mirai.interaction.input import Input  # noqa: E402
from mirai.mask_display import GLMaskOverlay  # noqa: E402
from mirai.soft_selection import GLSoftBandOverlay, GLSoftShadingOverlay  # noqa: E402
from mirai.subdivision.gl_lines import GLSubdLineOverlay  # noqa: E402
from mirai.viewport.picking import pick_component  # noqa: E402
from mirai.viewport.picking_cache import PickCache  # noqa: E402
from viewport.gl_line_overlay import GLLineOverlay  # noqa: E402
from viewport.gl_point_overlay import GLPointOverlay  # noqa: E402
from viewport.gl_symmetry_overlay import GLSymmetryOverlay  # noqa: E402
from viewport.gl_triangle_overlay import GLTriangleOverlay  # noqa: E402

WIDTH, HEIGHT = 800, 600

#: The window's sink types (`src/main.py` `GL_TYPES` without the GL store): all of them hold their data
#: without a GL context, so the headless run takes every overlay path the window takes.
OVERLAYS = {
    "point_overlay_type": GLPointOverlay,
    "line_overlay_type": GLLineOverlay,
    "face_overlay_type": GLTriangleOverlay,
    "soft_overlay_type": GLSoftBandOverlay,
    "soft_shading_overlay_type": GLSoftShadingOverlay,
    "symmetry_overlay_type": GLSymmetryOverlay,
    "subd_overlay_type": GLSubdLineOverlay,
    "mask_overlay_type": GLMaskOverlay,
}

#: The `HudState` fields at the baseline: a field the restructuring adds (M2: availability data) is not
#: part of the equivalence.
HUD_FIELDS = (
    "mode", "tool", "active", "constraint", "space", "symmetry", "display", "soft_on", "soft_radius_percent",
    "soft_curve", "subd_view", "subd_level", "subd_lines", "region", "region_faces", "region_count",
    "region_tint", "group_mask", "light", "look", "morph", "morph_targets", "status", "status_serial",
    "keymap_problem", "constraint_mode", "pivot", "view",
)


# -- observation ------------------------------------------------------------------------------------


#: Sink members that are GL handles, work counters or links back to the app's objects, not drawn data.
_SKIP_SINK_KEYS = frozenset(
    {"_vertex_lists", "uploads", "_stale", "_program", "reports", "preview", "chain", "_synced_mesh", "_watch",
     "pushes", "scans", "plane_recomputes", "provider"}
)


def plain(value: Any, depth: int = 0) -> Any:
    """`value` as nested plain data (no identity, no memory address): what `repr` may digest."""
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, (VertexId, EdgeId, FaceId, ObjectId)):
        return (type(value).__name__, int(value))
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, enum.Enum):
        return f"{type(value).__name__}.{value.name}"
    if depth > 8:
        return type(value).__name__
    if isinstance(value, (list, tuple)):
        return [plain(v, depth + 1) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted((plain(v, depth + 1) for v in value), key=repr)
    if isinstance(value, dict):
        items = [(plain(k, depth + 1), plain(v, depth + 1)) for k, v in value.items()]
        return sorted(items, key=lambda kv: repr(kv[0]))
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return [type(value).__name__] + [
            (f.name, plain(getattr(value, f.name), depth + 1)) for f in dataclasses.fields(value)
        ]
    if callable(value) and not hasattr(value, "__dict__"):
        return type(value).__name__
    attrs = getattr(value, "__dict__", None)
    if attrs is not None and not callable(value):
        return [type(value).__name__] + sorted(
            ((k, plain(v, depth + 1)) for k, v in attrs.items() if k not in _SKIP_SINK_KEYS),
            key=lambda kv: kv[0],
        )
    return type(value).__name__


def _feed(h, value: Any, depth: int = 0) -> None:
    """Streams `value` into the hasher `h` as `plain` would see it, with fast paths for the float
    buffers and point lists the viewport holds (a full `plain` copy of them costs seconds per event)."""
    kind = type(value)
    if value is None or kind in (bool, int, float, str):
        h.update(f"{value!r}|".encode())
        return
    if isinstance(value, (VertexId, EdgeId, FaceId, ObjectId)):
        h.update(f"{kind.__name__}{int(value)}|".encode())
        return
    if isinstance(value, enum.Enum):
        h.update(f"{kind.__name__}.{value.name}|".encode())
        return
    if depth > 8 or isinstance(value, (Mesh, Scene, Selection)):
        h.update(f"<{kind.__name__}>".encode())
        return
    if kind in (list, tuple):
        h.update(f"[{len(value)}".encode())
        if value and _feed_floats(h, value):
            h.update(b"]")
            return
        for item in value:
            _feed(h, item, depth + 1)
        h.update(b"]")
        return
    if isinstance(value, (set, frozenset)):
        h.update(f"{{{len(value)}".encode())
        try:
            items = sorted(value, key=lambda v: (type(v).__name__, v))
        except TypeError:
            items = sorted(value, key=repr)
        for item in items:
            _feed(h, item, depth + 1)
        h.update(b"}")
        return
    if isinstance(value, dict):
        h.update(f"<{len(value)}".encode())
        try:
            keys = sorted(value) if all(type(k) in (int, str) for k in value) else None
        except TypeError:
            keys = None
        if keys is None:
            keys = sorted(value, key=lambda k: repr(plain(k)))
        for key in keys:
            _feed(h, key, depth + 1)
            _feed(h, value[key], depth + 1)
        h.update(b">")
        return
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        h.update(kind.__name__.encode())
        for f in dataclasses.fields(value):
            h.update(f.name.encode())
            _feed(h, getattr(value, f.name), depth + 1)
        return
    attrs = getattr(value, "__dict__", None)
    if attrs is not None and not callable(value):
        h.update(kind.__name__.encode())
        for key in sorted(attrs):
            if key not in _SKIP_SINK_KEYS:
                h.update(key.encode())
                _feed(h, attrs[key], depth + 1)
        return
    h.update(f"<{kind.__name__}>".encode())


def _feed_floats(h, items) -> bool:
    """A list of floats or of float tuples / lists in one `array` (True = fed)."""
    first = items[0]
    try:
        if type(first) is float:
            h.update(b"f")
            h.update(array("d", items).tobytes())
            return True
        if type(first) in (tuple, list) and first and type(first[0]) is float:
            width = len(first)
            if all(type(item) in (tuple, list) and len(item) == width for item in items):
                h.update(f"t{width}".encode())
                h.update(array("d", chain.from_iterable(items)).tobytes())
                return True
    except TypeError:
        return False
    return False


def _hash(data: Any) -> str:
    h = hashlib.blake2b(digest_size=8)
    _feed(h, data)
    return h.hexdigest()


def _store_digest(store) -> str:
    h = hashlib.blake2b(digest_size=8)
    for name in sorted(store.resource_ids()):
        h.update(name.encode())
        _feed(h, store.data(name))
    return h.hexdigest()


def _viewport_digest(viewport) -> str | None:
    if viewport is None:
        return None
    parts = [
        _store_digest(viewport.render_mesh.store),
        {k: _store_digest(rm.store) for k, rm in viewport.object_entries.items()},
        None if viewport.surface_render_mesh is None else _store_digest(viewport.surface_render_mesh.store),
        {k: _store_digest(rm.store) for k, rm in viewport.entry_surface_render_meshes.items()},
        viewport.point_positions,
        viewport.line_layers,
        viewport.face_layers,
        viewport.edge_segments,
        viewport.tool_point_layers,
        viewport.tool_line_layers,
        viewport.hidden_vertices,
        (viewport.show_faces, viewport.show_edges, viewport.flat, viewport.region_tint),
        viewport.model_matrix,
        viewport.light_rig,
        viewport.surface_finish,
        viewport.geometry_revision,
        list(viewport.extra_overlays),
        [viewport.point_overlay, viewport.line_overlay, viewport.face_overlay],
    ]
    return _hash(parts)


def _mesh_digest(mesh) -> str:
    """`export_state()` digested with flat arrays for the three big tables (the generic `_feed` would
    cost ~0.1 s per event on the basemesh)."""
    state = mesh.export_state()
    h = hashlib.blake2b(digest_size=8)
    vertices, edges, faces = state.pop("vertices"), state.pop("edges"), state.pop("faces")
    ids = sorted(vertices)
    h.update(array("q", ids).tobytes())
    h.update(array("d", chain.from_iterable(vertices[i] for i in ids)).tobytes())
    h.update(b"e")
    h.update(
        array(
            "q",
            chain.from_iterable(
                (i, e["v0"], e["v1"], len(e["faces"]), *e["faces"]) for i, e in sorted(edges.items())
            ),
        ).tobytes()
    )
    h.update(b"f")
    h.update(array("q", chain.from_iterable((i, len(b), *b) for i, b in sorted(faces.items()))).tobytes())
    _feed(h, state)
    return h.hexdigest()


def observe(app: Application, result: Any) -> dict:
    """One observation after an event (AD-027 §6 E1). Read-only: properties and public reads."""
    sel = app.selection
    state = hud_state(app)
    scene = app.scene
    objects = []
    for oid in sorted(scene.objects, key=int):
        obj = scene.objects[oid]
        objects.append(
            (
                int(oid), obj.name, plain(obj.state), plain(obj.transform), plain(obj.pivot),
                plain(obj.material), obj.texture, _mesh_digest(obj.mesh),
            )
        )
    history = app.history
    plan = app.resymmetrize_preview
    return {
        "ret": plain(result),
        "status": app.status_message,
        "serial": app.status_serial,
        "owner": app.interaction_owner,
        "hud": [plain(getattr(state, name)) for name in HUD_FIELDS],
        "mode": sel.mode.name,
        "selection": [plain(sel.vertices), plain(sel.edges), plain(sel.faces), plain(sel.objects)],
        "hover": plain(sel.hovered),
        "objects": objects,
        "edit": int(scene.edit_object_id),
        "pairs": plain(scene.mirror_pairs),
        "history": [len(history._undo_stack), len(history._redo_stack), history.can_undo(), history.can_redo()],
        "camera": plain(app.camera),
        "tool": [
            app.transform_command, app.transform_interacting, plain(app.transform_target), app.transform_space,
            app.axis_constraint, app.constraint_mode, app.tweak_command, app.tweak_running,
            app.transform_orientation, app.knife_active, app.morph_view_open, app.cursor_wrap_active,
            app.pivot_placing, plain(app.working_pivot), plain(app.active_pivot), app.view_text, app.view_name,
            plain(app.soft_settings), app.gizmo_size_name, app.knife_mirror_variant,
        ],
        "resym": None if plan is None else _hash(plan),
        "knife": _hash(app.knife_render_data),
        "box": plain(app.selection_box),
        "lasso": plain(app.selection_lasso),
        "through": app.selection_through,
        "gizmo": _hash(app.gizmo_items()),
        "pivot_items": _hash(app.pivot_marker_items()),
        "soft": [_hash(app.soft_bands), _hash(app.soft_shading)],
        "display": [plain(app.display), app.reference_ghost],
        "subd": [app.subdivision.view, app.subdivision.level, app.subdivision.lines_shown],
        "symmetry_display": None if app.symmetry_display is None else app.symmetry_display.visible,
        "viewport": _viewport_digest(app.viewport),
    }


# -- scenes -----------------------------------------------------------------------------------------


SHIFT_S = Input("key", "s", frozenset({"shift"}))
CTRL_H = Input("key", "h", frozenset({"ctrl"}))


def _new_app(coalesce: bool) -> Application:
    app = Application()
    app.gizmo_enabled = True
    app.coalesce_hover = coalesce
    app.gpu_picking = False  # headless anyway; CPU picking is the deterministic path
    return app


def _frame(app: Application) -> None:
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    app.pointer_motion(2.0, 2.0)
    app.update_viewport(0)


def _screen(app: Application, obj, position) -> tuple[float, float] | None:
    return app.camera.project_to_screen(object_space.to_world(obj, position), WIDTH, HEIGHT)


def _click_vertex(app: Application, index: int, shift: bool = False) -> None:
    """Setup only: select the `index`-th vertex (by id) that projects into the window."""
    mesh = app.scene.mesh
    ids = sorted(mesh.all_vertex_ids(), key=int)
    for vid in ids[index:] + ids[:index]:
        point = _screen(app, app.scene.edit_object, mesh.vertex_position(vid))
        if point is not None and 0 < point[0] < WIDTH and 0 < point[1] < HEIGHT:
            inp = Input("mouse", "LEFT", frozenset({"shift"} if shift else ()))
            app.pointer_motion(*point)
            app.pointer_press(inp, *point)
            app.pointer_release("LEFT", *point)
            return


def _scene_cube(app: Application) -> None:
    app.init_scene("cube", **OVERLAYS)
    _frame(app)


def _scene_subd_sym(app: Application) -> None:
    app.init_scene("obj", obj_path=asset_path("subd_cube"), **OVERLAYS)
    _frame(app)
    app.key_press(SHIFT_S)  # symmetry X
    app.key_release(SHIFT_S)


def _scene_basemesh(app: Application) -> None:
    app.init_scene("obj", obj_path=asset_path("man_with_shoes_basemesh"), **OVERLAYS)
    _frame(app)
    app.key_press(SHIFT_S)
    app.key_release(SHIFT_S)


def _scene_objects(app: Application) -> None:
    """Two editable objects, a Reference and a mirror pair (mode `4` work)."""
    app.init_scene("cube", **OVERLAYS)
    _frame(app)
    app.add_primitive("cube")  # mode 4, the new cube selected
    app.mirror_copy("X")
    app.add_reference("cube", name="ref")
    app.update_viewport(0)


def _scene_morph(app: Application) -> None:
    """A subd cube with two morph targets, the second one current at 60 %."""
    app.init_scene("obj", obj_path=asset_path("subd_cube"), **OVERLAYS)
    _frame(app)
    app.create_morph_target()
    app.create_morph_target()
    app.set_morph_weight(60)
    app.update_viewport(0)


def _scene_hidden(app: Application) -> None:
    """A subd cube with symmetry, two vertices hidden and one masked."""
    app.init_scene("obj", obj_path=asset_path("subd_cube"), **OVERLAYS)
    _frame(app)
    app.key_press(SHIFT_S)
    app.key_release(SHIFT_S)
    _click_vertex(app, 3)
    _click_vertex(app, 5, shift=True)
    app.key_press(CTRL_H)
    app.key_release(CTRL_H)
    _click_vertex(app, 8)
    mask = app.bindings.inputs_for(commands.MASK_TOGGLE)
    if mask:
        app.key_press(mask[0])
        app.key_release(mask[0])
    app.update_viewport(0)


SCENES: dict[str, Callable[[Application], None]] = {
    "cube": _scene_cube,
    "subd_sym": _scene_subd_sym,
    "objects": _scene_objects,
    "morph": _scene_morph,
    "hidden": _scene_hidden,
    "basemesh": _scene_basemesh,
}


def make_app(scene: str, coalesce: bool = False) -> Application:
    app = _new_app(coalesce)
    SCENES[scene](app)
    return app


# -- the driver -------------------------------------------------------------------------------------


_MODIFIERS = ("shift", "ctrl", "alt")


class Driver:
    """One app plus the hand's state (held keys, buttons, modifiers, cursor) and the injected clock.
    Every method is one event: it calls one public entry point, ticks the viewport and names the event."""

    def __init__(self, scene: str, coalesce: bool = False) -> None:
        self.app = make_app(scene, coalesce)
        self.now = 1000.0
        self.app.knife_clock = lambda: self.now
        self.cursor: tuple[float, float] | None = (2.0, 2.0)
        self.modifiers: set[str] = set()
        self.keys_down: dict[str, Input] = {}  # key value -> the press input
        self.button: str | None = None
        self.events: list[str] = []

    # -- recording

    def _record(self, label: str, call: Callable[[], Any]) -> Any:
        result = call()
        self.app.update_viewport(0)
        self.events.append(label)
        return result

    def tick(self, seconds: float) -> None:
        self.now += seconds

    # -- modifiers

    def set_modifier(self, name: str, held: bool) -> None:
        if (name in self.modifiers) == held:
            return
        (self.modifiers.add if held else self.modifiers.discard)(name)
        setter = getattr(self.app, f"set_{name}_held")
        self._record(f"{name}={'down' if held else 'up'}", lambda: setter(held))

    def modifiers_to(self, wanted) -> None:
        for name in _MODIFIERS:
            self.set_modifier(name, name in wanted)

    # -- keys

    def key_down(self, inp: Input) -> Any:
        self.modifiers_to(inp.modifiers)
        self.keys_down[inp.value] = inp
        return self._record(f"key+ {_label(inp)}", lambda: self.app.key_press(inp))

    def key_up(self, value: str) -> Any:
        self.keys_down.pop(value, None)
        inp = Input("key", value, frozenset(self.modifiers))
        return self._record(f"key- {value}", lambda: self.app.key_release(inp))

    def tap(self, inp: Input) -> None:
        self.key_down(inp)
        self.key_up(inp.value)

    # -- pointer

    def motion(self, x: float, y: float) -> Any:
        dx, dy = (0.0, 0.0) if self.cursor is None else (x - self.cursor[0], y - self.cursor[1])
        self.cursor = (x, y)
        if self.button is not None:
            return self._record(f"drag {x:.1f},{y:.1f}", lambda: self.app.pointer_drag(dx, dy, x, y))
        return self._record(f"move {x:.1f},{y:.1f}", lambda: self.app.pointer_motion(x, y, dx, dy))

    def nudge(self, dx: float, dy: float) -> Any:
        """A relative motion, kept inside the window."""
        x, y = self.cursor if self.cursor is not None else (WIDTH / 2, HEIGHT / 2)
        return self.motion(min(max(x + dx, 1.0), WIDTH - 1.0), min(max(y + dy, 1.0), HEIGHT - 1.0))

    def press(self, button: str = "LEFT", modifiers=()) -> Any:
        self.modifiers_to(modifiers)
        if self.cursor is None:
            self.motion(WIDTH / 2, HEIGHT / 2)
        inp = Input("mouse", button, frozenset(self.modifiers))
        x, y = self.cursor
        if self.button is None:
            self.button = button
        return self._record(f"press {_label(inp)}", lambda: self.app.pointer_press(inp, x, y))

    def release(self, button: str | None = None) -> Any:
        button = button or self.button or "LEFT"
        if self.button == button:
            self.button = None
        if self.cursor is None:
            self.cursor = (WIDTH / 2, HEIGHT / 2)
        x, y = self.cursor
        return self._record(f"release {button}", lambda: self.app.pointer_release(button, x, y))

    def click(self, x: float, y: float, button: str = "LEFT", modifiers=()) -> Any:
        self.motion(x, y)
        self.press(button, modifiers)
        return self.release(button)

    def scroll(self, value: str, modifiers=()) -> Any:
        self.modifiers_to(modifiers)
        inp = Input("wheel", value, frozenset(self.modifiers))
        return self._record(f"wheel {_label(inp)}", lambda: self.app.pointer_scroll(inp))

    def leave(self) -> Any:
        self.cursor = None
        return self._record("leave", self.app.pointer_leave)

    def focus_loss(self) -> None:
        """The window loses focus: every held key and modifier goes up (`src/main.py` `on_deactivate`
        resets the modifiers; the keys are let go away from the window)."""
        for value in list(self.keys_down):
            self.key_up(value)
        self.modifiers_to(())

    def host(self, label: str, call: Callable[[], Any]) -> Any:
        return self._record(f"host {label}", call)

    # -- targets

    def targets(
        self, kind: str, visible: bool = False, limit: int | None = None, near: tuple[float, float] | None = None
    ) -> list[tuple[float, float]]:
        """Screen points of the edit mesh: vertices, edge midpoints or face centres (inside the window).
        `visible`: only those the CPU picker returns at their own point, so a scripted click hits what it names.
        `near`: nearest to that screen point first; `limit`: at most that many."""
        app = self.app
        obj = app.scene.edit_object
        mesh = obj.mesh
        points = []
        if kind == "vertex":
            items = [(v, mesh.vertex_position(v)) for v in sorted(mesh.all_vertex_ids(), key=int)]
        elif kind == "edge":
            items = []
            for e in sorted(mesh.all_edge_ids(), key=int):
                a, b = (mesh.vertex_position(v) for v in mesh.edge_vertices(e))
                items.append((e, tuple((p + q) / 2 for p, q in zip(a, b))))
        else:
            items = []
            for f in sorted(mesh.all_face_ids(), key=int):
                vs = [mesh.vertex_position(v) for v in mesh.face_vertices(f)]
                items.append((f, tuple(sum(c) / len(vs) for c in zip(*vs))))
        mode = {"vertex": SelectionMode.VERTEX, "edge": SelectionMode.EDGE, "face": SelectionMode.FACE}[kind]
        projected = []
        for element, position in items:
            point = _screen(app, obj, position)
            if point is not None and 0 < point[0] < WIDTH and 0 < point[1] < HEIGHT:
                projected.append((element, point))
        if near is not None:
            projected.sort(key=lambda ep: (ep[1][0] - near[0]) ** 2 + (ep[1][1] - near[1]) ** 2)
        camera = app.camera if object_space.is_identity(obj.transform) else ObjectSpaceCamera(app.camera, obj)
        cache = PickCache()
        for element, point in projected:
            if visible:
                hit = pick_component(camera, mesh, mode, point[0], point[1], WIDTH, HEIGHT, cache=cache, occlusion=True)
                if type(hit) is not type(element) or hit != element:
                    continue
            points.append(point)
            if limit is not None and len(points) >= limit:
                break
        return points

    def object_points(self) -> list[tuple[float, float]]:
        """The screen point of every object's first vertex (mode `4` clicks)."""
        app = self.app
        points = []
        for oid in sorted(app.scene.objects, key=int):
            obj = app.scene.objects[oid]
            ids = sorted(obj.mesh.all_vertex_ids(), key=int)
            if ids:
                point = _screen(app, obj, obj.mesh.vertex_position(ids[len(ids) // 2]))
                if point is not None:
                    points.append(point)
        return points


def _label(inp: Input) -> str:
    return "+".join(sorted(inp.modifiers) + [inp.value])


# -- scenario helpers ---------------------------------------------------------------------------------


def key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


W, E, R, T, G, P, L, N, Q = (key(k) for k in "wertgplnq")
C, X, ESC, ENTER, TAB = key("c"), key("x"), key("ESCAPE"), key("enter"), key("tab")
ALT_M, CTRL_Z, CTRL_Y, CTRL_SHIFT_Z = key("m", "alt"), key("z", "ctrl"), key("y", "ctrl"), key("z", "ctrl", "shift")


def first(points, fallback=(WIDTH / 2, HEIGHT / 2)):
    return points[0] if points else fallback


def centre_face(d: Driver) -> tuple[float, float]:
    """The visible face centre nearest the window centre."""
    faces = d.targets("face", visible=True, limit=1, near=(WIDTH / 2, HEIGHT / 2))
    return faces[0] if faces else (WIDTH / 2, HEIGHT / 2)


def select_vertex(d: Driver, index: int = 0) -> None:
    """A click on the `index`-th of the first eight visible vertices."""
    points = d.targets("vertex", visible=True, limit=8)
    d.click(*points[index % len(points)])


def hold_move(d: Driver, inp: Input, steps=((12, 0), (12, 4), (6, -3))) -> None:
    """Hold a gesture key over a few motions and let it go."""
    d.key_down(inp)
    for dx, dy in steps:
        d.nudge(dx, dy)
    d.key_up(inp.value)
