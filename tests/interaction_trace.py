"""AD-027 §6 E1/E2: the interaction trace driver - a migration oracle for the interaction-layer
restructuring (slot, `can_run`, controllers).

The driver feeds an `Application` only through public entry points (`key_press/release`,
`pointer_press/drag/release/motion/scroll/leave`, `set_shift/ctrl/alt_held`, `update_viewport`) and the
public calls hosts make (`add_primitive`, `mirror_copy`, `create_morph_target`, `set_light`, ...). It
never calls `dispatch_command` (its gating changes on purpose, AD-027 §3.3) and reads no private
`Application` member. After every event it calls `update_viewport(0)` (the window's frame tick) and
digests one observation (`observe`): return value, status, `interaction_owner`, the HUD state, the
selection and hover, every object (mesh `export_state()`, transform, material, state), the history,
the camera, the overlays the window reads, and the headless viewport's buffers and sinks.

Two kinds of sequences (fixtures in `tests/fixtures/interaction_traces/`, checked by
`tests/test_interaction_trace.py`):

- **random** - a seed per sequence; one 12-hex digest per event. Lifecycle (AD-027 C1): a migration
  oracle only; removed together with this generator at M8.
- **scripted** - named scenarios (V1-V7 of AD-027 §1.1, Manu's test points); the full observation per
  step, for a readable diff. They become the permanent regression tests at M8.

The corpus is recorded on the baseline commit (`dfd6e5d`) and never re-recorded to make a step pass;
only a bug in this driver justifies re-recording, from a worktree of the baseline (AD-027 §6).

E2 (differential deep run) uses the CLI at the bottom: `python tests/interaction_trace.py digests ...`
prints the digests of seeds beyond the corpus, `... observe ...` the full observation at one event.
"""

from __future__ import annotations

import argparse
import dataclasses
import enum
import hashlib
import json
import random
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
from mirai.interaction.input import KNIFE_CONTEXT, MORPH_CONTEXT, SUBD_CONTEXT, Input  # noqa: E402
from mirai.mask_display import GLMaskOverlay  # noqa: E402
from mirai.soft_selection import GLSoftBandOverlay, GLSoftShadingOverlay  # noqa: E402
from mirai.subdivision.gl_lines import GLSubdLineOverlay  # noqa: E402
from mirai.viewport.picking import pick_component  # noqa: E402
from mirai.viewport.picking_cache import PickCache  # noqa: E402
from viewport.gl_line_overlay import GLLineOverlay  # noqa: E402
from viewport.gl_point_overlay import GLPointOverlay  # noqa: E402
from viewport.gl_symmetry_overlay import GLSymmetryOverlay  # noqa: E402
from viewport.gl_triangle_overlay import GLTriangleOverlay  # noqa: E402

FIXTURES = _TESTS / "fixtures" / "interaction_traces"
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


def driver_hash() -> str:
    """Hash of this file: a fixture recorded by another driver version is refused, not compared."""
    return hashlib.blake2b(Path(__file__).read_bytes(), digest_size=6).hexdigest()


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


def digest(observation: dict) -> str:
    return hashlib.blake2b(repr(observation).encode(), digest_size=6).hexdigest()


# -- scenes -----------------------------------------------------------------------------------------


def _key(value: str, *modifiers: str) -> Input:
    return Input("key", value, frozenset(modifiers))


SHIFT_S = _key("s", "shift")
CTRL_H = _key("h", "ctrl")


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
    Every method is one event: it calls one public entry point, ticks the viewport and records."""

    def __init__(self, scene: str, coalesce: bool = False, keep: bool = False) -> None:
        self.app = make_app(scene, coalesce)
        self.now = 1000.0
        self.app.knife_clock = lambda: self.now
        self.cursor: tuple[float, float] | None = (2.0, 2.0)
        self.modifiers: set[str] = set()
        self.keys_down: dict[str, Input] = {}  # key value -> the press input
        self.button: str | None = None
        self.keep = keep
        self.digests: list[str] = []
        self.observations: list[dict] = []
        self.events: list[str] = []

    # -- recording

    def _record(self, label: str, call: Callable[[], Any]) -> Any:
        try:
            result = call()
        except Exception as exc:  # noqa: BLE001 - an exception is an observed outcome, the run goes on
            result = f"EXC {type(exc).__name__}: {exc}"
        self.app.update_viewport(0)
        obs = observe(self.app, result)
        self.digests.append(digest(obs))
        self.events.append(label)
        if self.keep:
            self.observations.append(obs)
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
        `visible` (the scripted sequences): only those the CPU picker returns at their own point, so a
        scripted click hits what it names; the random generator also clicks hidden ones (a miss).
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


# -- the random generator (removed at M8, AD-027 C1) ------------------------------------------------


def bound_key_inputs(app: Application) -> list[Input]:
    """Every key input bound in the global, SubD, morph and Knife contexts (the window's own context
    excluded: `Application` never resolves it)."""
    names = {getattr(commands, n) for n in dir(commands) if n.isupper() and isinstance(getattr(commands, n), str)}
    found: set[Input] = set()
    for context in (None, SUBD_CONTEXT, MORPH_CONTEXT, KNIFE_CONTEXT):
        for name in names:
            found.update(inp for inp in app.bindings.inputs_for(name, context) if inp.kind == "key")
    return sorted(found, key=lambda i: (i.value, sorted(i.modifiers)))


_MOUSE_INTENTS = (
    ("LEFT", ()), ("LEFT", ()), ("LEFT", ()), ("LEFT", ("shift",)), ("LEFT", ("ctrl",)), ("LEFT", ("alt",)),
    ("LEFT", ("alt", "shift")), ("LEFT", ("ctrl", "shift")), ("RIGHT", ()), ("MIDDLE", ()),
)
_WHEEL_INTENTS = (("UP", ()), ("DOWN", ()), ("UP", ("shift",)), ("DOWN", ("shift",)), ("UP", ("ctrl",)))

#: Commands a hand holds (several events between press and release) and the keys pressed most.
_FAVOURED = frozenset(
    {
        *commands.HOLD_COMMANDS, commands.CANCEL, commands.CONNECT, commands.UNDO, commands.REDO,
        commands.SET_VERTEX_MODE, commands.SET_EDGE_MODE, commands.SET_FACE_MODE, commands.CONSTRAIN_AXIS_X, commands.CONSTRAIN_AXIS_Y, commands.RESYMMETRIZE, commands.SOFT_TOGGLE,
        commands.KNIFE_COMMIT, commands.KNIFE_LIFT, commands.LOOP_INSERT, commands.SYMMETRY_CYCLE,
        commands.MORPH_EDIT_TOGGLE, commands.EDGE_LOOP, commands.DELETE,
    }
)


def _host_calls(app: Application, rng: random.Random) -> list[tuple[str, Callable[[], Any]]]:
    return [
        ("add_primitive", lambda: app.add_primitive(rng.choice(("cube", "plane")))),
        ("mirror_copy", lambda: app.mirror_copy("X")),
        ("pair_selected", lambda: app.pair_selected("X")),
        ("break_mirror_pairs", app.break_mirror_pairs),
        ("resync_mirror_pairs", app.resync_mirror_pairs),
        ("create_morph_target", app.create_morph_target),
        ("set_morph_weight", lambda: app.set_morph_weight(rng.randrange(0, 101, 10))),
        ("step_morph_target", lambda: app.step_morph_target(rng.choice((1, -1)))),
        ("edit_morph_target", app.edit_morph_target),
        ("leave_morph_target", app.leave_morph_target),
        ("set_light", lambda: app.set_light(key_azimuth=float(rng.randrange(-90, 91, 15)))),
        ("toggle_symmetry_display", app.toggle_symmetry_display),
        ("set_object_material", lambda: app.set_object_material(specular=rng.choice((0.2, 0.8)))),
        ("frame_scene", app.frame_scene),
    ]


@dataclasses.dataclass
class _Hand:
    """What the generator knows about the app's keys (fixed per sequence)."""

    keys: list
    weights: list
    hold_keys: set
    hosts: list


def random_sequence(driver: Driver, rng: random.Random, events: int) -> None:
    """Drive `driver` with a hand-like random sequence until it has recorded `events` events: single
    random events, interleaved with short "macros" a hand does (select + hold a gesture key and move,
    a Knife session, the Re-Symmetrize preview, a drag selection, a held P / L / N / Q, a gizmo drag)
    that themselves carry random noise."""
    app = driver.app
    keys = bound_key_inputs(app)
    weights = [6.0 if _context_command(app, k) in _FAVOURED else 1.0 for k in keys]
    hand = _Hand(
        keys, weights, {k.value for k in keys if _context_command(app, k) in commands.HOLD_COMMANDS},
        _host_calls(app, rng),
    )
    macros = (_macro_gesture, _macro_gesture, _macro_knife, _macro_resym, _macro_drag, _macro_hold, _macro_gizmo)
    while len(driver.digests) < events:
        if rng.random() < 0.25:
            rng.choice(macros)(driver, rng, hand)
        else:
            _step(driver, rng, hand)
    del driver.digests[events:]
    del driver.events[events:]
    del driver.observations[events:]


def _step(driver: Driver, rng: random.Random, hand: _Hand) -> None:
    """One random event (sometimes two: a click, a tap)."""
    driver.tick(rng.choice((0.05, 0.12, 0.3, 0.8)))
    # Keys let go: a tapped key soon, a held one after a while.
    for value in list(driver.keys_down):
        if rng.random() < (0.12 if value in hand.hold_keys else 0.6):
            driver.key_up(value)
    roll = rng.random()
    if roll < 0.30:
        _random_motion(driver, rng)
    elif roll < 0.50:
        driver.key_down(rng.choices(hand.keys, hand.weights)[0])
    elif roll < 0.62:
        if driver.button is None:
            button, mods = rng.choice(_MOUSE_INTENTS)
            _random_motion(driver, rng, jump=True)
            driver.press(button, mods)
        else:
            driver.release(driver.button if rng.random() < 0.9 else rng.choice(("LEFT", "RIGHT")))
    elif roll < 0.70:
        button, mods = rng.choice(_MOUSE_INTENTS)
        x, y = _random_point(driver, rng)
        driver.click(x, y, button, mods)
    elif roll < 0.78:
        name = rng.choice(_MODIFIERS)
        driver.set_modifier(name, name not in driver.modifiers)
    elif roll < 0.83:
        driver.scroll(*rng.choice(_WHEEL_INTENTS))
    elif roll < 0.86:
        driver.tap(_key("ESCAPE"))
    elif roll < 0.89:
        label, call = rng.choice(hand.hosts)
        driver.host(label, call)
    elif roll < 0.91:
        driver.leave()
    elif roll < 0.92:
        driver.focus_loss()
    else:
        _random_motion(driver, rng)


def _noise(driver: Driver, rng: random.Random, hand: _Hand, p: float = 0.15) -> None:
    if rng.random() < p:
        _step(driver, rng, hand)


def _let_go(driver: Driver) -> None:
    """Release the button and the keys a macro starts from a clean hand."""
    if driver.button is not None:
        driver.release()
    for value in list(driver.keys_down):
        driver.key_up(value)


_GESTURE_KEYS = (
    _key("w"), _key("w"), _key("e"), _key("r"), _key("t"), _key("g"), _key("s"), _key("s", "alt"), _key("i"),
    _key("b", "ctrl"),
)
_CONSTRAINT_KEYS = (_key("x"), _key("y"), _key("z"), _key("x", "shift"), _key("z", "shift"))
_MODE_KEYS = {"VERTEX": _key("1"), "EDGE": _key("2"), "FACE": _key("3")}
_MODE_TARGETS = {"VERTEX": "vertex", "EDGE": "edge", "FACE": "face"}


def _component_select(driver: Driver, rng: random.Random, hand: _Hand) -> None:
    mode = driver.app.selection.mode.name
    if mode not in _MODE_KEYS or rng.random() < 0.3:
        mode = rng.choice(("VERTEX", "VERTEX", "EDGE", "FACE"))
        driver.tap(_MODE_KEYS[mode])
    points = driver.targets(_MODE_TARGETS[mode])
    for _ in range(rng.choice((0, 1, 1, 1, 2, 3))):
        if points:
            driver.click(*rng.choice(points), modifiers=("shift",) if rng.random() < 0.5 else ())
        _noise(driver, rng, hand)


def _wiggle(driver: Driver, rng: random.Random, hand: _Hand, count: int) -> None:
    for _ in range(count):
        driver.nudge(rng.uniform(-25, 25), rng.uniform(-25, 25))
        roll = rng.random()
        if roll < 0.08:
            name = rng.choice(_MODIFIERS)
            driver.set_modifier(name, name not in driver.modifiers)
        elif roll < 0.12:
            driver.scroll(*rng.choice(_WHEEL_INTENTS))
        elif roll < 0.16:
            driver.tap(rng.choice(_CONSTRAINT_KEYS))
        else:
            _noise(driver, rng, hand, 0.08)


def _macro_gesture(driver: Driver, rng: random.Random, hand: _Hand) -> None:
    _let_go(driver)
    _component_select(driver, rng, hand)
    driver.modifiers_to(())
    if rng.random() < 0.3:
        driver.tap(rng.choice(_CONSTRAINT_KEYS))
    key = rng.choice(_GESTURE_KEYS)
    driver.key_down(key)
    _wiggle(driver, rng, hand, rng.randint(0, 6))
    roll = rng.random()
    if roll < 0.2:
        driver.tap(_key("ESCAPE"))
    elif roll < 0.25:
        driver.tap(rng.choice((_key("z", "ctrl"), _key("y", "ctrl"))))
    if rng.random() < 0.95:
        driver.key_up(key.value)


def _macro_knife(driver: Driver, rng: random.Random, hand: _Hand) -> None:
    _let_go(driver)
    if rng.random() < 0.6:
        driver.click(3.0, 3.0)  # empty space clears the selection, so C starts the Knife
    driver.tap(_key("c"))
    for _ in range(rng.randint(1, 6)):
        roll = rng.random()
        kind = rng.choice(("edge", "edge", "vertex", "face"))
        points = driver.targets(kind)
        point = rng.choice(points) if points else _random_point(driver, rng)
        if roll < 0.6:
            driver.click(*point, modifiers=("shift",) if rng.random() < 0.2 else ())
            if rng.random() < 0.15:
                driver.tick(0.1)
                driver.click(*point)  # a double-click
        elif roll < 0.7:
            driver.tap(_key("e"))  # pen lift
        elif roll < 0.75:
            driver.click(*point, button="RIGHT")
        elif roll < 0.85:
            driver.tap(rng.choice((_key("z", "ctrl"), _key("z", "ctrl", "shift"), _key("y", "ctrl"))))
        else:
            driver.motion(*point)
        _noise(driver, rng, hand)
    roll = rng.random()
    if roll < 0.5:
        driver.tap(_key("enter"))
    elif roll < 0.9:
        driver.tap(_key("ESCAPE"))


def _macro_resym(driver: Driver, rng: random.Random, hand: _Hand) -> None:
    _let_go(driver)
    if driver.app.selection.mode.name != "VERTEX":
        driver.tap(_key("1"))
    points = driver.targets("vertex")
    if points:
        driver.click(*rng.choice(points))
    driver.tap(_key("m", "alt"))
    for _ in range(rng.randint(0, 3)):
        _step(driver, rng, hand)
    driver.tap(_key("m", "alt") if rng.random() < 0.5 else _key("ESCAPE"))


def _macro_drag(driver: Driver, rng: random.Random, hand: _Hand) -> None:
    _let_go(driver)
    lasso = rng.random() < 0.25
    if lasso:
        driver.key_down(_key("q"))
    driver.motion(*_random_point(driver, rng))
    driver.press("LEFT", rng.choice(((), (), ("shift",), ("alt",), ("ctrl",), ("alt", "shift"))))
    for _ in range(rng.randint(1, 6)):
        if rng.random() < 0.4:
            driver.motion(*_random_point(driver, rng))
        else:
            driver.nudge(rng.uniform(-60, 60), rng.uniform(-60, 60))
        _noise(driver, rng, hand, 0.1)
    if rng.random() < 0.15:
        driver.tap(_key("ESCAPE"))
    if rng.random() < 0.3:
        driver.set_modifier("alt", True)
    driver.release("LEFT")
    if lasso:
        driver.key_up("q")


def _macro_hold(driver: Driver, rng: random.Random, hand: _Hand) -> None:
    _let_go(driver)
    key = rng.choice((_key("p"), _key("p"), _key("l"), _key("n"), _key("q")))
    driver.key_down(key)
    for _ in range(rng.randint(1, 4)):
        roll = rng.random()
        if roll < 0.4:
            _wiggle(driver, rng, hand, 1)
        elif roll < 0.7:
            driver.click(*_random_point(driver, rng), modifiers=("shift",) if rng.random() < 0.3 else ())
        elif roll < 0.8:
            driver.tap(_key("ESCAPE"))
        elif roll < 0.9:
            driver.key_down(rng.choice(_GESTURE_KEYS))
        else:
            _step(driver, rng, hand)
    driver.key_up(key.value)


def _macro_gizmo(driver: Driver, rng: random.Random, hand: _Hand) -> None:
    _let_go(driver)
    _component_select(driver, rng, hand)
    driver.modifiers_to(())
    driver.tap(rng.choice((_key("w"), _key("e"), _key("r"))))  # a tap sets the gizmo's tool
    app = driver.app
    mesh = app.scene.mesh
    ids = [v for v in app.selection.vertices if mesh.is_valid_vertex(v)]
    if not ids:
        return
    centre = tuple(sum(c) / len(ids) for c in zip(*(mesh.vertex_position(v) for v in ids)))
    point = _screen(app, app.scene.edit_object, centre)
    if point is None:
        return
    x, y = point
    driver.motion(x + rng.choice((0.0, 0.0, 30.0, 60.0)), y + rng.choice((0.0, -30.0, 0.0)))
    driver.press("LEFT")
    for _ in range(rng.randint(0, 4)):
        driver.nudge(rng.uniform(-20, 20), rng.uniform(-20, 20))
        _noise(driver, rng, hand, 0.1)
    if rng.random() < 0.15:
        driver.tap(_key("ESCAPE"))
    driver.release("LEFT")


def _context_command(app: Application, inp: Input):
    for context in (None, SUBD_CONTEXT, MORPH_CONTEXT, KNIFE_CONTEXT):
        command = app.bindings.command_for(inp, context)
        if command is not None:
            return command
    return None


def _random_point(driver: Driver, rng: random.Random) -> tuple[float, float]:
    if driver.app.selection.mode.name == "OBJECT" and rng.random() < 0.6:
        points = driver.object_points()
    else:
        points = driver.targets(rng.choice(("vertex", "vertex", "edge", "face")))
    if points and rng.random() < 0.8:
        x, y = rng.choice(points)
        return x + rng.uniform(-1.5, 1.5), y + rng.uniform(-1.5, 1.5)
    return rng.uniform(3, WIDTH - 3), rng.uniform(3, HEIGHT - 3)


def _random_motion(driver: Driver, rng: random.Random, jump: bool = False) -> None:
    if jump or driver.cursor is None or rng.random() < 0.35:
        driver.motion(*_random_point(driver, rng))
        return
    step = rng.choice((1.0, 3.0, 8.0, 20.0))
    driver.nudge(rng.uniform(-step, step), rng.uniform(-step, step))


def run_random(scene: str, seed: int, events: int, keep: bool = False) -> Driver:
    rng = random.Random(f"{scene}:{seed}")
    driver = Driver(scene, coalesce=rng.random() < 0.5, keep=keep)
    random_sequence(driver, rng, events)
    return driver


# -- scripted sequences ------------------------------------------------------------------------------


def _first(points, fallback=(WIDTH / 2, HEIGHT / 2)):
    return points[0] if points else fallback


def _centre_face(d: Driver) -> tuple[float, float]:
    faces = d.targets("face", visible=True, limit=1, near=(WIDTH / 2, HEIGHT / 2))
    return faces[0] if faces else (WIDTH / 2, HEIGHT / 2)


def _select_vertex(d: Driver, index: int = 0) -> None:
    points = d.targets("vertex", visible=True, limit=8)
    d.click(*points[index % len(points)])


def _hold_move(d: Driver, key: Input, steps=((12, 0), (12, 4), (6, -3))) -> None:
    d.key_down(key)
    for dx, dy in steps:
        d.nudge(dx, dy)
    d.key_up(key.value)


W, E, R, T, G, P, L, N, Q = (_key(k) for k in "wertgplnq")
C, X, ESC, ENTER = _key("c"), _key("x"), _key("ESCAPE"), _key("enter")
ALT_M, CTRL_Z, CTRL_Y, CTRL_SHIFT_Z, TAB = _key("m", "alt"), _key("z", "ctrl"), _key("y", "ctrl"), \
    _key("z", "ctrl", "shift"), _key("tab")


def _v1(d: Driver) -> None:
    """V1: hold P, then W (Move armed), Esc: Esc cancels the pivot placement, Move stays armed."""
    _select_vertex(d, 2)
    d.key_down(P)
    d.key_down(W)
    d.tap(ESC)
    d.nudge(10, 0)
    d.key_up("w")
    d.key_up("p")


def _v2(d: Driver) -> None:
    """V2: W armed, then P: P refused silently."""
    _select_vertex(d, 2)
    d.key_down(W)
    d.key_down(P)
    d.key_up("p")
    d.key_up("w")


def _v3(d: Driver) -> None:
    """V3: hold P, W armed, LMB click: the pivot is placed while Move stays armed."""
    _select_vertex(d, 2)
    d.key_down(P)
    d.key_down(W)
    d.click(*_centre_face(d))
    d.key_up("w")
    d.key_up("p")


def _v4(d: Driver) -> None:
    """V4: hold L and N (either order), move: the light turns, the weight does not."""
    d.key_down(L)
    d.key_down(N)
    d.nudge(30, 5)
    d.key_up("l")
    d.key_up("n")
    d.key_down(N)
    d.key_down(L)
    d.nudge(-30, -5)
    d.key_up("n")
    d.key_up("l")


def _v5(d: Driver) -> None:
    """V5: hold L, hold W, move, release W, move: the motion drives Move, then turns the light again."""
    _select_vertex(d, 2)
    d.key_down(L)
    d.key_down(W)
    d.nudge(15, 0)
    d.key_up("w")
    d.nudge(15, 0)
    d.key_up("l")


def _v6(d: Driver) -> None:
    """V6: hold P, then C (Knife), LMB click, Esc: LMB sets a Knife point; Esc ends the Knife, P held."""
    d.key_down(P)
    d.tap(C)
    edges = d.targets("edge", visible=True, limit=8)
    d.click(*_first(edges))
    d.tap(ESC)
    d.key_up("p")


def _v7(d: Driver) -> None:
    """V7: hold P, then Alt+M (Re-Symmetrize preview), LMB, Esc: LMB places the pivot under the open
    preview; Esc closes the preview, P stays held."""
    _select_vertex(d, 1)
    d.key_down(P)
    d.tap(ALT_M)
    d.click(*_centre_face(d))
    d.tap(ESC)
    d.key_up("p")


def _knife_scenario(d: Driver) -> None:
    """Knife: cut across faces, pen lift, double-click, in-session Undo/Redo, commit; a second session
    cancelled."""
    d.tap(C)
    edges = d.targets("edge", visible=True, limit=8)
    for point in edges[:3]:
        d.click(*point)
    d.tap(_key("e"))  # pen lift
    d.click(*edges[3 % len(edges)])
    d.tap(CTRL_Z)
    d.tap(CTRL_SHIFT_Z)
    d.click(*edges[4 % len(edges)])
    d.tick(0.1)
    d.click(*edges[4 % len(edges)])  # double-click
    d.tap(ENTER)
    d.tap(C)
    d.click(*_first(d.targets("edge", visible=True, limit=8)))
    d.tap(ESC)
    d.tap(CTRL_Z)


def _wer_scenario(d: Driver) -> None:
    """W/E/R held with a constraint, Shift fine, Ctrl snap, Alt orbit."""
    _select_vertex(d, 0)
    d.tap(X)
    _hold_move(d, W)
    d.key_down(E)
    d.set_modifier("ctrl", True)
    d.nudge(25, 10)
    d.set_modifier("ctrl", False)
    d.key_up("e")
    d.key_down(R)
    d.set_modifier("shift", True)
    d.nudge(20, 0)
    d.set_modifier("shift", False)
    d.set_modifier("alt", True)
    d.nudge(20, 0)
    d.set_modifier("alt", False)
    d.nudge(5, 0)
    d.key_up("r")
    d.key_down(W)
    d.nudge(9, 0)
    d.tap(ESC)
    d.key_up("w")
    d.tap(CTRL_Z)
    d.tap(CTRL_Y)


def _box_paint_lasso_scenario(d: Driver) -> None:
    """Box from empty space, Paint from the mesh, Lasso with Q, Alt through, Esc cancels."""
    d.motion(5, 5)
    d.press()
    for step in range(4):
        d.motion(5 + 100 * (step + 1), 5 + 80 * (step + 1))
    d.release()
    face = _centre_face(d)
    d.motion(*face)
    d.press(modifiers=("shift",))
    d.motion(face[0] + 30, face[1] + 10)
    d.motion(face[0] + 60, face[1] + 5)
    d.release()
    d.key_down(Q)
    d.motion(100, 100)
    d.press()
    for x, y in ((700, 120), (680, 520), (120, 500)):
        d.motion(x, y)
    d.set_modifier("alt", True)
    d.release()
    d.set_modifier("alt", False)
    d.key_up("q")
    d.motion(5, 5)
    d.press()
    d.motion(300, 300)
    d.tap(ESC)
    d.release()


def _gizmo_scenario(d: Driver) -> None:
    """Gizmo: click on the centre handle, then a drag on it (Move along the handle), Esc on a second drag."""
    _select_vertex(d, 4)
    d.tap(W)
    pivot = d.app.gizmo_items()
    del pivot
    face = _centre_face(d)
    points = d.targets("vertex", visible=True, limit=8)
    centre = points[4 % len(points)]
    d.click(*centre)
    d.motion(*centre)
    d.press()
    d.motion(centre[0] + 20, centre[1])
    d.motion(centre[0] + 40, centre[1] + 5)
    d.release()
    d.motion(*centre)
    d.press()
    d.motion(centre[0] - 20, centre[1])
    d.tap(ESC)
    d.release()
    d.motion(*face)


def _pivot_scenario(d: Driver) -> None:
    """Working Pivot: place, tap off / on, Esc restores."""
    d.key_down(P)
    d.click(*_centre_face(d))
    d.key_up("p")
    d.tap(P)
    d.tap(P)
    d.key_down(P)
    d.click(*_first(d.targets("vertex", visible=True, limit=8)), modifiers=("shift",))
    d.tap(ESC)
    d.key_up("p")
    _select_vertex(d, 3)
    _hold_move(d, E)


def _morph_scenario(d: Driver) -> None:
    """The morph view: Tab, W in the view, N drag, Undo, Tab back."""
    d.tap(TAB)
    _select_vertex(d, 2)
    _hold_move(d, W)
    d.key_down(N)
    d.nudge(40, 0)
    d.key_up("n")
    d.tap(N)
    d.tap(CTRL_Z)
    d.tap(TAB)
    d.tap(CTRL_Z)
    d.tap(CTRL_Y)


def _undo_chain_scenario(d: Driver) -> None:
    """Undo/Redo chains across a move, an extrude and a connect."""
    _select_vertex(d, 1)
    _hold_move(d, W)
    d.tap(_key("3"))
    d.click(*_centre_face(d))
    d.key_down(T)
    for _ in range(3):
        d.nudge(4, -6)
    d.key_up("t")
    d.tap(_key("1"))
    _select_vertex(d, 0)
    _select_vertex(d, 5)
    for _ in range(3):
        d.tap(CTRL_Z)
    for _ in range(2):
        d.tap(CTRL_Y)


def _objects_scenario(d: Driver) -> None:
    """Object gestures with a mirror pair (mode `4`)."""
    d.tap(_key("4"))
    points = d.object_points()
    d.click(*points[1 % len(points)])
    _hold_move(d, W, steps=((15, 0), (10, 5)))
    _hold_move(d, E, steps=((15, 0), (10, 5)))
    d.key_down(R)
    d.nudge(10, 0)
    d.tap(ESC)
    d.key_up("r")
    d.tap(CTRL_Z)
    d.tap(_key("1"))


def _resym_scenario(d: Driver) -> None:
    """Re-Symmetrize: open, a refused key and click, close with Esc; open again, execute, Undo."""
    _select_vertex(d, 1)
    d.tap(ALT_M)
    d.tap(W)
    d.click(*_centre_face(d))
    d.scroll("UP", ("shift",))
    d.tap(_key("d"))
    d.tap(ESC)
    _select_vertex(d, 1)
    d.tap(ALT_M)
    d.tap(ALT_M)
    d.tap(CTRL_Z)


SCRIPTED: dict[str, tuple[str, Callable[[Driver], None]]] = {
    "v1_pivot_then_move_esc": ("subd_sym", _v1),
    "v2_move_then_pivot": ("subd_sym", _v2),
    "v3_pivot_move_click": ("subd_sym", _v3),
    "v4_light_and_morph_weight": ("morph", _v4),
    "v5_light_move_light": ("subd_sym", _v5),
    "v6_pivot_knife": ("cube", _v6),
    "v7_pivot_resym_preview": ("basemesh", _v7),
    "knife_session": ("cube", _knife_scenario),
    "knife_symmetric": ("subd_sym", _knife_scenario),
    "wer_constraint_modifiers": ("subd_sym", _wer_scenario),
    "box_paint_lasso": ("subd_sym", _box_paint_lasso_scenario),
    "gizmo_click_drag": ("subd_sym", _gizmo_scenario),
    "working_pivot": ("subd_sym", _pivot_scenario),
    "morph_view": ("morph", _morph_scenario),
    "undo_redo_chain": ("cube", _undo_chain_scenario),
    "object_gestures_mirror_pair": ("objects", _objects_scenario),
    "resymmetrize": ("basemesh", _resym_scenario),
    "hidden_geometry": ("hidden", _undo_chain_scenario),
}


def run_scripted(name: str) -> Driver:
    scene, script = SCRIPTED[name]
    driver = Driver(scene, keep=True)
    script(driver)
    return driver


# -- the default corpus (E1) ------------------------------------------------------------------------

#: scene -> (number of sequences, events per sequence) for the default run.
CORPUS: dict[str, tuple[int, int]] = {
    "cube": (60, 250),
    "subd_sym": (60, 250),
    "objects": (40, 250),
    "morph": (40, 250),
    "hidden": (40, 250),
    "basemesh": (12, 250),
}


def record(out: Path = FIXTURES) -> None:
    """Record the corpus (only on the baseline commit, AD-027 §6)."""
    out.mkdir(parents=True, exist_ok=True)
    stamp = driver_hash()
    for scene, (count, events) in CORPUS.items():
        sequences = []
        for seed in range(count):
            driver = run_random(scene, seed, events)
            sequences.append({"seed": seed, "events": events, "digests": "".join(driver.digests)})
        payload = {"driver": stamp, "scene": scene, "sequences": sequences}
        (out / f"random_{scene}.json").write_text(json.dumps(payload, indent=0) + "\n", encoding="utf-8")
    scripted = {}
    for name in SCRIPTED:
        driver = run_scripted(name)
        scripted[name] = [
            {"event": label, "observation": obs} for label, obs in zip(driver.events, driver.observations)
        ]
    (out / "scripted.json").write_text(
        json.dumps({"driver": stamp, "sequences": scripted}, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )


def split_digests(text: str) -> list[str]:
    return [text[i:i + 12] for i in range(0, len(text), 12)]


def _main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("record", help="record the corpus into tests/fixtures/interaction_traces (baseline only)")
    dig = sub.add_parser("digests", help="print one line per event: <scene> <seed> <index> <digest> <event>")
    dig.add_argument("scene")
    dig.add_argument("first_seed", type=int)
    dig.add_argument("count", type=int)
    dig.add_argument("events", type=int)
    obs = sub.add_parser("observe", help="print the observation at one event (JSON)")
    obs.add_argument("scene")
    obs.add_argument("seed", type=int)
    obs.add_argument("events", type=int)
    obs.add_argument("index", type=int)
    args = parser.parse_args(argv)
    if args.cmd == "record":
        record()
    elif args.cmd == "digests":
        for seed in range(args.first_seed, args.first_seed + args.count):
            driver = run_random(args.scene, seed, args.events)
            for i, (d, label) in enumerate(zip(driver.digests, driver.events)):
                print(args.scene, seed, i, d, label)
            sys.stdout.flush()
    else:
        driver = run_random(args.scene, args.seed, args.events, keep=True)
        print(json.dumps({"event": driver.events[args.index], "observation": driver.observations[args.index]},
                         indent=1, sort_keys=True, default=repr))
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
