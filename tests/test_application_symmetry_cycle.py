"""Symmetry in the Production app: the Shift+S command (AD-SYM-04 slice A1, Q-1 = E-1).

Headless (TraceStore), `Application()` with its default bindings and no `command_gate` -
exactly what `src/main.py` builds. Named by the A1 row of AD-SYM-04 §6:

- the cycle off → X → Y → Z → off, one Undo step each (`Symmetry <axis>`), Undo/Redo restore
  the definition, the selection stays, nothing but the definition changes;
- the status line per S-1 (`Symmetrie X (valid)`, `... (partial, 54 ohne Partner)`, `Symmetrie aus`);
- `load_scene` drops the definition;
- the viewport is notified (K-3): extra overlays re-sync, the soft bands follow;
- the interaction gates (review R-4): ignored while W/E/R/T is armed or running, ignored inside a
  Knife session; Soft on → Shift+S → W runs symmetric Soft (AD-SYM-04 SS2; at arm and with O after the arm);
- one smoke per coordinated tool once Shift+S has set the definition: W/E/R, `C` in its four
  contexts (Split, Edge Connect, Vertex Connect, Knife), Delete/Dissolve/DissolveNoCleanup, `T`;
- `src/main.py`'s own key handler reaches the command (pyglet-dependent, skipped without it).

The F-a guard (every command constant on a symmetric fixture) is `test_symmetry_fail_closed_guard.py`.
"""

from __future__ import annotations

import importlib.util
import sys

import pytest

import tests._bootstrap  # noqa: F401
from tests._bootstrap import _REPO_ROOT, _SRC

_EXAMPLES = _REPO_ROOT / "examples"
if str(_EXAMPLES) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES))

from core import SelectionMode  # noqa: E402
from loaders.assets import asset_path  # noqa: E402
from mirai.application import Application  # noqa: E402
from mirai.interaction import commands  # noqa: E402
from mirai.soft_selection import DEFAULT_RADIUS_STEP, RADIUS_STEPS_PERCENT  # noqa: E402
from mirai.interaction.bindings import build_default_bindings  # noqa: E402
from mirai.interaction.input import KNIFE_CONTEXT, Input  # noqa: E402
from mirai.soft_selection import SoftBands, symmetric_influence  # noqa: E402
from mirai.symmetry import SymmetryState, symmetry_state  # noqa: E402
from mirai.symmetry_axis import AXIS_NORMALS, ORIGIN, current_axis  # noqa: E402
from mirai.symmetry_coordination import completeness_report, delta_check  # noqa: E402
from mirai.topology.knife_pick import knife_pick  # noqa: E402

WIDTH, HEIGHT = 800, 600
MISS = (2.0, 2.0)
EPS = 1e-9

SHIFT_S = Input("key", "s", frozenset({"shift"}))
W, E, R, T = Input("key", "w"), Input("key", "e"), Input("key", "r"), Input("key", "t")
C = Input("key", "c")
O = Input("key", "o")
ENTER = Input("key", "enter")
ESC = Input("key", "ESCAPE")
DELETE = Input("key", "delete")
BACKSPACE = Input("key", "backspace")
CTRL_BACKSPACE = Input("key", "backspace", frozenset({"ctrl"}))
CTRL_Z = Input("key", "z", frozenset({"ctrl"}))
CTRL_Y = Input("key", "y", frozenset({"ctrl"}))
LMB = Input("mouse", "LEFT")


def make_app(asset: str = "subd_cube", **types) -> Application:
    app = Application()
    app.init_scene("obj", obj_path=asset_path(asset), **types)
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    app.pointer_motion(*MISS)
    return app


def symmetric_app(asset: str = "subd_cube") -> Application:
    app = make_app(asset)
    assert app.key_press(SHIFT_S) is True
    assert current_axis(app.scene.mesh) == "X"
    return app


def screen(app, vid):
    return app.camera.project_to_screen(app.scene.mesh.vertex_position(vid), WIDTH, HEIGHT)


# == The command and its binding ==================================================================


def test_shift_s_is_the_global_symmetry_command_and_free_in_the_knife_context():
    bindings = build_default_bindings()
    assert bindings.command_for(SHIFT_S) == commands.SYMMETRY_CYCLE
    # KNIFE falls back to GLOBAL; the session gate (`_knife_key`) ignores it (test below).
    assert bindings.command_for(SHIFT_S, KNIFE_CONTEXT) == commands.SYMMETRY_CYCLE


def test_cycle_off_x_y_z_off_one_undo_step_each_and_undo_redo_restore():
    app = make_app()
    mesh = app.scene.mesh
    seen = [mesh.symmetry_definition]
    assert seen == [None]
    for step, expected in enumerate(["X", "Y", "Z", None], start=1):
        assert app.key_press(SHIFT_S) is True
        assert current_axis(mesh) == expected
        if expected is not None:
            assert mesh.symmetry_definition.plane_point == ORIGIN
            assert mesh.symmetry_definition.plane_normal == AXIS_NORMALS[expected]
        assert len(app.history) == step
        assert app.history._undo_stack[-1].description == f"Symmetry {expected or 'off'}"
        seen.append(mesh.symmetry_definition)
    for step in range(4, 0, -1):
        assert app.key_press(CTRL_Z)
        assert mesh.symmetry_definition == seen[step - 1]
    for step in range(1, 5):
        assert app.key_press(CTRL_Y)
        assert mesh.symmetry_definition == seen[step]


def test_the_cycle_changes_only_the_definition_and_keeps_the_selection():
    app = make_app("head_basemesh")
    vid = sorted(app.scene.mesh.all_vertex_ids(), key=int)[0]
    app.selection.set({vid})
    before = app.scene.mesh.export_state()
    assert app.key_press(SHIFT_S)
    after = app.scene.mesh.export_state()
    assert after["symmetry"] is not None
    assert {k: v for k, v in after.items() if k != "symmetry"} == {
        k: v for k, v in before.items() if k != "symmetry"
    }
    assert app.selection.vertices == {vid}
    assert app.key_press(CTRL_Z) and app.selection.vertices == {vid}
    assert app.key_press(CTRL_Y) and app.selection.vertices == {vid}


@pytest.mark.parametrize(
    "asset,presses,text",
    [
        ("head_basemesh", 1, "Symmetrie X (valid)"),
        ("man_with_shoes_basemesh", 1, "Symmetrie X (partial, 54 ohne Partner)"),
        ("subd_cube", 2, "Symmetrie Y (partial, 26 ohne Partner)"),
        ("subd_cube", 4, "Symmetrie aus"),
    ],
)
def test_status_line_per_s1(asset, presses, text):
    app = make_app(asset)
    for _ in range(presses):
        serial = app.status_serial
        assert app.key_press(SHIFT_S)
        assert app.status_serial == serial + 1
    assert app.status_message == text


def test_load_scene_drops_the_definition_and_its_history():
    app = symmetric_app()
    app.load_scene("obj", obj_path=asset_path("head_basemesh"))
    assert app.scene.mesh.symmetry_definition is None
    assert not app.history.can_undo()
    assert app.key_press(SHIFT_S) and current_axis(app.scene.mesh) == "X"


# == K-3: the viewport hears about it ============================================================


class _RecordingOverlay:
    def __init__(self) -> None:
        self.dirty = False
        self.synced = []

    def sync(self, mesh, selection) -> None:
        self.synced.append(mesh.symmetry_definition)

    def draw(self, camera_uniforms) -> None:  # pragma: no cover - never rendered headless
        pass


class _BandSink:
    def __init__(self) -> None:
        self.bands = None

    def set_bands(self, bands) -> None:
        self.bands = bands


def test_a_cycle_step_re_syncs_extra_overlays():
    """K-3: a definition-only change is reported like its Undo (topology changed), so an overlay
    that reads the definition (the Lab's today, the app's in A2) re-derives without a host flag."""
    app = make_app()
    overlay = _RecordingOverlay()
    app.viewport.add_overlay(overlay)
    app.viewport.sync()
    overlay.synced.clear()
    app.viewport.sync()
    assert overlay.synced == []  # nothing reported, nothing synced
    assert app.key_press(SHIFT_S)
    app.viewport.sync()
    assert overlay.synced == [app.scene.mesh.symmetry_definition]


def test_the_soft_bands_follow_the_cycle():
    """Under a definition the bands are the symmetric field (AD-SYM-04 D-5, SS3); a cycle step
    refreshes them both ways."""
    app = make_app(soft_overlay_type=_BandSink)
    vid = sorted(app.scene.mesh.all_vertex_ids(), key=int)[0]
    app.selection.set({vid})
    assert app.key_press(O)
    for _ in range(RADIUS_STEPS_PERCENT.index(100) - DEFAULT_RADIUS_STEP):  # reaches the cube's neighbours
        app.dispatch_command(commands.SOFT_RADIUS_UP)
    shown = app.soft_bands
    assert shown.count > 0
    assert app.key_press(SHIFT_S)
    soft = app.soft_settings
    field = symmetric_influence(
        app.scene.mesh, {vid}, soft.world_radius, soft.metric, soft.curve, soft.curve_power
    )
    assert app.soft_bands == SoftBands.from_weights(field.weights) != shown
    for _ in range(3):
        assert app.key_press(SHIFT_S)
    assert app.scene.mesh.symmetry_definition is None
    assert app.soft_bands == shown


# == Interaction gates (review R-4) ===============================================================


def _plus_x_quad(app):
    mesh = app.scene.mesh
    for fid in sorted(mesh.all_face_ids(), key=int):
        vids = mesh.face_vertices(fid)
        if len(vids) == 4 and all(mesh.vertex_position(v)[0] > EPS for v in vids):
            return fid, vids
    raise AssertionError("no quad entirely on the +X side")


@pytest.mark.parametrize("key", [W, E, R])
def test_ignored_while_a_transform_is_armed_or_running(key):
    app = make_app()
    _fid, vids = _plus_x_quad(app)
    app.selection.set(set(vids))
    assert app.key_press(key)
    assert app.interaction_owner == "transform"
    for running in (False, True):
        if running:
            app.pointer_motion(400, 300, 12.0, 7.0)
            assert app.transform_interacting
        history, serial = len(app.history), app.status_serial
        assert app.key_press(SHIFT_S) is False
        assert app.scene.mesh.symmetry_definition is None
        assert (len(app.history), app.status_serial) == (history, serial)  # silent, like C
        assert app.dispatch_command(commands.SYMMETRY_CYCLE) is False
        assert app.scene.mesh.symmetry_definition is None
    assert app.key_release(key)


def test_ignored_while_extrude_is_armed_or_running():
    app = make_app()
    fid, _vids = _plus_x_quad(app)
    app.selection.mode = SelectionMode.FACE
    app.selection.faces = {fid}
    assert app.key_press(T)
    assert app.key_press(SHIFT_S) is False
    app.pointer_motion(400, 300, 0.0, -20.0)
    assert app.transform_interacting
    assert app.key_press(SHIFT_S) is False
    assert app.scene.mesh.symmetry_definition is None
    assert app.key_press(ESC)


def test_ignored_inside_a_knife_session():
    app = make_app()
    app.selection.clear()
    assert app.key_press(C) and app.knife_active
    serial = app.status_serial
    assert app.key_press(SHIFT_S) is False
    assert app.knife_active
    assert app.scene.mesh.symmetry_definition is None
    assert app.status_serial == serial
    assert app.dispatch_command(commands.SYMMETRY_CYCLE) is False
    assert app.key_press(ESC) and not app.knife_active
    assert app.key_press(SHIFT_S) and current_axis(app.scene.mesh) == "X"


def test_soft_on_then_shift_s_runs_symmetric_soft():
    """Soft on → Shift+S → W runs symmetric Soft (AD-SYM-04 SS2; until SS2 refused, I-8): the
    partners of the +X quad move as its mirror; the same with O after the arm (read at begin())."""
    app = make_app()
    _fid, vids = _plus_x_quad(app)
    app.selection.set(set(vids))
    assert app.key_press(O)
    assert app.key_press(SHIFT_S)
    mesh = app.scene.mesh
    for armed_first in (False, True):
        if armed_first:
            assert app.key_press(O)  # Soft off
            assert app.key_press(W)
            assert app.key_press(O)  # Soft on again, after the arm
        else:
            assert app.key_press(W)
        history = len(app.history)
        assert app.pointer_motion(400, 300, 12.0, 7.0)
        op = app.tool_manager.active_tool.operation
        mirrored = op.context.params["symmetry"]["mirrored_vertex_ids"]
        assert mirrored and "influence" in op.context.params
        assert app.key_release(W)
        assert len(app.history) == history + 1
        assert symmetry_state(mesh) is SymmetryState.VALID
        for vid in vids:
            p = mesh.vertex_position(vid)
            partner = next(m for m in mirrored if mesh.vertex_position(m) == (-p[0], p[1], p[2]))
            assert partner is not None


# == One smoke per coordinated tool (A1 row) ======================================================


def _minus_x_signature(mesh) -> tuple:
    """Everything a mirrored operation changes on the -X side: positions, faces, edges there."""

    def centre_x(vids) -> float:
        return sum(mesh.vertex_position(v)[0] for v in vids) / len(vids)

    return (
        tuple(sorted(mesh.vertex_position(v) for v in mesh.all_vertex_ids() if mesh.vertex_position(v)[0] < -EPS)),
        sum(1 for f in mesh.all_face_ids() if centre_x(mesh.face_vertices(f)) < -EPS),
        sum(1 for e in mesh.all_edge_ids() if centre_x(mesh.edge_vertices(e)) < -EPS),
    )


class _Mirrored:
    """Before/after oracle of one coordinated operation: exactly one Undo step, the -X side
    changed too, completeness unchanged (AD-SYM-03 delta rule), the state stays valid."""

    def __init__(self, app) -> None:
        self.app = app
        mesh = app.scene.mesh
        assert symmetry_state(mesh) is SymmetryState.VALID
        self.report = completeness_report(mesh)
        self.history = len(app.history)
        self.minus_x = _minus_x_signature(mesh)
        self.state = mesh.export_state()

    def check(self) -> None:
        mesh = self.app.scene.mesh
        assert mesh.export_state() != self.state
        assert len(self.app.history) == self.history + 1
        assert _minus_x_signature(mesh) != self.minus_x
        assert delta_check(self.report, completeness_report(mesh)).ok
        assert symmetry_state(mesh) is SymmetryState.VALID


@pytest.mark.parametrize("key", [W, E, R], ids=["move", "rotate", "scale"])
def test_smoke_transform(key):
    app = symmetric_app()
    _fid, vids = _plus_x_quad(app)
    app.selection.set(set(vids))
    oracle = _Mirrored(app)
    assert app.key_press(key)
    assert app.pointer_motion(400, 300, 12.0, 7.0)
    assert app.key_release(key)
    oracle.check()


def _edge_between(mesh, a, b):
    return next(e for e in mesh.all_edge_ids() if set(mesh.edge_vertices(e)) == {a, b})


@pytest.mark.parametrize("context", ["split", "edge_connect", "vertex_connect"])
def test_smoke_contextual_c(context):
    app = symmetric_app()
    mesh = app.scene.mesh
    _fid, (a, b, c, d) = _plus_x_quad(app)
    s = app.selection
    if context == "split":
        s.mode = SelectionMode.EDGE
        s.edges = {_edge_between(mesh, a, b)}
    elif context == "edge_connect":
        s.mode = SelectionMode.EDGE
        s.edges = {_edge_between(mesh, a, b), _edge_between(mesh, c, d)}
    else:
        s.mode = SelectionMode.VERTEX
        s.vertices = {a, c}
    oracle = _Mirrored(app)
    assert app.key_press(C) is True
    oracle.check()


def test_smoke_knife():
    app = symmetric_app()
    mesh = app.scene.mesh

    def hits(vid) -> bool:
        target = knife_pick(app.camera, mesh, *screen(app, vid), WIDTH, HEIGHT)
        return target.get("kind") == "vertex" and target.get("vertex_id") == vid

    a = b = None
    for fid in sorted(mesh.all_face_ids(), key=int):
        vids = mesh.face_vertices(fid)
        if len(vids) == 4 and all(mesh.vertex_position(v)[0] > EPS for v in vids):
            if hits(vids[0]) and hits(vids[2]):
                a, b = vids[0], vids[2]
                break
    assert a is not None, "no +X quad with a visible diagonal"
    app.selection.clear()
    oracle = _Mirrored(app)
    assert app.key_press(C) and app.knife_active
    for vid in (a, b):
        pos = screen(app, vid)
        app.pointer_motion(*pos)
        app.pointer_press(LMB, *pos)
        assert app.pointer_release("LEFT", *pos)
    assert app.key_press(ENTER)
    assert not app.knife_active
    oracle.check()


@pytest.mark.parametrize(
    "key,mode",
    [(DELETE, SelectionMode.FACE), (BACKSPACE, SelectionMode.EDGE), (CTRL_BACKSPACE, SelectionMode.EDGE)],
    ids=["delete", "dissolve", "dissolve_no_cleanup"],
)
def test_smoke_removal(key, mode):
    app = symmetric_app()
    mesh = app.scene.mesh
    fid, (a, b, _c, _d) = _plus_x_quad(app)
    s = app.selection
    s.mode = mode
    if mode is SelectionMode.FACE:
        s.faces = {fid}
    else:
        s.edges = {_edge_between(mesh, a, b)}
    oracle = _Mirrored(app)
    assert app.key_press(key) is True
    oracle.check()


def test_smoke_extrude():
    app = symmetric_app()
    fid, _vids = _plus_x_quad(app)
    app.selection.mode = SelectionMode.FACE
    app.selection.faces = {fid}
    oracle = _Mirrored(app)
    assert app.key_press(T)
    app.pointer_motion(400, 300, 0.0, -20.0)
    assert app.transform_interacting
    assert app.key_release(T)
    oracle.check()


# == `src/main.py` reaches the command ============================================================


def test_main_py_key_handler_reaches_the_command():
    pyglet = pytest.importorskip("pyglet")
    pyglet.options["headless"] = True
    try:
        from pyglet.window import key
    except Exception as exc:  # pragma: no cover - environment-dependent (no EGL)
        pytest.skip(f"pyglet.window unavailable: {exc}")
    spec = importlib.util.spec_from_file_location("mirai_src_main_symmetry", _SRC / "main.py")
    main_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(main_module)

    class FakeWindow:
        width, height = WIDTH, HEIGHT

        def __init__(self) -> None:
            self.handlers = {}

        def event(self, func):
            self.handlers[func.__name__] = func
            return func

        def clear(self) -> None:
            pass

    app = make_app()
    window = FakeWindow()
    main_module.install_handlers(window, app)
    window.handlers["on_key_press"](key.S, key.MOD_SHIFT)
    assert current_axis(app.scene.mesh) == "X"
    assert app.status_message == "Symmetrie X (valid)"
