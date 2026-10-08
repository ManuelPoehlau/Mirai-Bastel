"""`Application.command_gate` (WP-SYM-LAB-03 H2, AD-013 H2 addendum, Slice 1 part).

Headless, fixture as `tests/test_application_pointer.py`. Application-level
subset of the addendum's § Required tests (the Lab-side ones follow in
Slice 1b, `hover_suspended` and its T-H in Slice 3):

- T-R3   a refused key and a refused click return False, post the text
         (`status_serial` + 1, also for a repeated identical refusal); unbound
         input is never refused; the gate does not act inside a Knife session
- T-R5a  `Application()` has `command_gate is None` and `hover_suspended is False`
- T-R5b  AST guard: `src/main.py` writes no gate data and calls neither
         `apply_mesh_change` nor `set_status` (nor `add_overlay`, plan §4.4)
- T-R5c  pass-through run of every `tests/test_application_*` with an inert
         but active gate → identical outcomes; empty allow-list → failures

Deliberately not named `test_application_*` (that set is what T-R5c re-runs).
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import tests._bootstrap  # noqa: F401

from tests._bootstrap import _REPO_ROOT, _SRC

from mirai.application import Application, CommandGate
from mirai.interaction import commands
from mirai.interaction.input import Input
from mirai.viewport.picking import pick_nearest_vertex

WIDTH, HEIGHT = 800, 600
MISS = (2.0, 2.0)

W = Input("key", "w")
C = Input("key", "c")
D = Input("key", "d")
ESC = Input("key", "ESCAPE")
ENTER = Input("key", "ENTER")
CTRL_Z = Input("key", "z", frozenset({"ctrl"}))
LMB = Input("mouse", "LEFT")
SHIFT_LMB = Input("mouse", "LEFT", frozenset({"shift"}))
ALT_LMB = Input("mouse", "LEFT", frozenset({"alt"}))

CONNECT_ROW = CommandGate(refused={commands.CONNECT: "C refused here"})
SELECT_ROW = CommandGate(
    refused={commands.SELECT: "select refused", commands.SELECT_ADD: "add refused"}
)
DISPLAY_ONLY = CommandGate(
    allowed=frozenset(
        {
            commands.CYCLE_DISPLAY_MODE,
            commands.TOGGLE_WIREFRAME_OVERLAY,
            commands.SET_SHADED,
            commands.SET_FLAT_SHADED,
            commands.SET_WIREFRAME,
        }
    ),
    not_allowed_text="only display commands",
)


@pytest.fixture
def app() -> Application:
    app = Application()
    app.init_scene("cube")
    app.frame_scene()
    app.set_viewport_size(WIDTH, HEIGHT)
    return app


def _visible_screen(app):
    mesh = app.scene.mesh
    for vid in sorted(mesh.all_vertex_ids()):
        sx, sy = app.camera.project_to_screen(mesh.vertex_position(vid), WIDTH, HEIGHT)
        if pick_nearest_vertex(app.camera, mesh, sx, sy, WIDTH, HEIGHT, occlusion=True) == vid:
            return vid, (sx, sy)
    raise AssertionError("no visible vertex")


def _click(app, x, y, inp=LMB):
    app.pointer_press(inp, x, y)
    return app.pointer_release(inp.value, x, y)


# -- CommandGate value ------------------------------------------------------------


def test_gate_value_is_immutable_data():
    source = {commands.CONNECT: "no"}
    gate = CommandGate(refused=source)
    source[commands.MOVE] = "later edit"
    assert gate.refusal(commands.MOVE) is None  # copied, not aliased
    with pytest.raises(TypeError):
        gate.refused[commands.MOVE] = "x"
    with pytest.raises(Exception):
        gate.allowed = frozenset()
    assert gate.refusal(commands.CONNECT) == "no"
    assert DISPLAY_ONLY.refusal(commands.MOVE) == "only display commands"
    assert DISPLAY_ONLY.refusal(commands.CYCLE_DISPLAY_MODE) is None
    # The block-list wins over the allow-list.
    both = CommandGate(refused={commands.SET_SHADED: "blocked"}, allowed=frozenset({commands.SET_SHADED}))
    assert both.refusal(commands.SET_SHADED) == "blocked"


# -- T-R5a ----------------------------------------------------------------------


def test_default_gate_is_none():
    """T-R5a: the default is inert: no gate, hover not suspended (Slice 3; more in
    `tests/test_app_hover_suspended.py`)."""
    app = Application()
    assert app.command_gate is None
    assert app.hover_suspended is False


# -- T-R3 -----------------------------------------------------------------------


def test_refused_key_returns_false_posts_text_and_changes_nothing(app):
    """T-R3 (key): C refused (the Slice 1 row shape) → False, status + 1, text;
    no Knife session, no history."""
    app.command_gate = CONNECT_ROW
    app.pointer_motion(*MISS)
    serial = app.status_serial
    assert app.key_press(C) is False
    assert app.status_serial == serial + 1
    assert app.status_message == "C refused here"
    assert not app.knife_active
    assert not app.history.can_undo()


def test_same_refusal_twice_counts_twice(app):
    """T-R3 (H2-R3): a repeated identical refusal is visible again."""
    app.command_gate = CONNECT_ROW
    serial = app.status_serial
    app.key_press(C)
    app.key_press(C)
    assert app.status_serial == serial + 2
    assert app.status_message == "C refused here"


def test_refused_click_returns_false_and_keeps_selection(app):
    """T-R3 (click): the click command is checked before `select_at`."""
    vid, (sx, sy) = _visible_screen(app)
    app.command_gate = SELECT_ROW
    serial = app.status_serial
    assert _click(app, sx, sy) is False
    assert app.selection.vertices == set()
    assert (app.status_serial, app.status_message) == (serial + 1, "select refused")
    assert _click(app, sx, sy, SHIFT_LMB) is False
    assert (app.status_serial, app.status_message) == (serial + 2, "add refused")
    _click(app, sx, sy, SHIFT_LMB)
    assert app.status_serial == serial + 3

    app.command_gate = None
    assert _click(app, sx, sy) is True
    assert app.selection.vertices == {vid}


def test_allow_list_refuses_everything_else_key_and_click(app):
    """T-R3 (allow-list row): W, Ctrl+Z and a select click refused with
    `not_allowed_text`; a display command still runs; navigation is never
    gated."""
    vid, (sx, sy) = _visible_screen(app)
    app.pointer_motion(sx, sy)
    app.command_gate = DISPLAY_ONLY
    serial = app.status_serial
    assert app.key_press(W) is False
    assert app.transform_command is None
    assert app.key_press(CTRL_Z) is False
    assert _click(app, sx, sy) is False
    assert app.selection.vertices == set()
    assert app.status_serial == serial + 3
    assert app.status_message == "only display commands"

    assert app.key_press(D) is True
    assert app.status_message.startswith("Display:")

    yaw = app.camera.yaw
    app.pointer_press(ALT_LMB, 100, 100)
    assert app.pointer_drag(20.0, 0.0, 120, 100)
    app.pointer_release("LEFT", 120, 100)
    assert app.camera.yaw != yaw


def test_unbound_input_is_never_refused(app):
    """T-R3: an input without a command is not refused (no status), even
    under an empty allow-list."""
    app.command_gate = CommandGate(allowed=frozenset(), not_allowed_text="refused")
    serial = app.status_serial
    assert app.key_press(Input("key", "q")) is False
    assert app.key_press(Input("key", "F12")) is False
    app.pointer_press(Input("mouse", "MIDDLE"), 10, 10)
    app.pointer_release("MIDDLE", 10, 10)
    assert app.status_serial == serial


def test_gate_not_applied_inside_a_knife_session(app):
    """T-R3 / § Limits of G: the check sits after the Knife routing — inside a
    session Esc, Ctrl+Z and Enter keep their Knife meaning even if refused."""
    app.pointer_motion(*MISS)
    assert app.key_press(C)
    assert app.knife_active
    app.command_gate = CommandGate(allowed=frozenset(), not_allowed_text="refused")
    serial = app.status_serial
    assert app.key_press(CTRL_Z) is False  # Knife: nothing to undo (its own text)
    assert app.status_message == "Knife: nothing to undo"
    assert app.key_press(ESC) is True
    assert not app.knife_active
    assert app.status_message == "Knife cancelled"
    assert app.status_serial == serial + 2
    # Outside the session the gate applies again.
    assert app.key_press(C) is False
    assert app.status_message == "refused"


def test_gate_never_ends_a_running_application_interaction(app):
    """H2-R2: the gate only stops `Application` from starting something; a
    running Move still commits on release under a gate refusing everything."""
    vid, (sx, sy) = _visible_screen(app)
    app.pointer_motion(sx, sy)
    assert app.key_press(W)
    app.command_gate = CommandGate(allowed=frozenset(), not_allowed_text="refused")
    app.pointer_motion(400, 300, 10.0, 5.0)
    assert app.transform_interacting
    assert app.key_release(W) is True
    assert app.status_message == "Move committed"
    assert app.history.can_undo()


# -- T-R5b ----------------------------------------------------------------------

_FORBIDDEN_WRITES = {"command_gate", "hover_suspended"}
_FORBIDDEN_CALLS = {"apply_mesh_change", "set_status", "add_overlay"}


def _main_violations(source: str) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(source)):
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
            targets = [node.target]
        for target in targets:
            for sub in ast.walk(target):
                if isinstance(sub, ast.Attribute) and sub.attr in _FORBIDDEN_WRITES:
                    found.append(f"writes {sub.attr}")
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if name in _FORBIDDEN_CALLS:
                found.append(f"calls {name}")
            if name == "setattr" and len(node.args) >= 2:
                arg = node.args[1]
                if isinstance(arg, ast.Constant) and arg.value in _FORBIDDEN_WRITES:
                    found.append(f"setattr {arg.value}")
    return found


def test_main_py_uses_no_host_hook():
    """T-R5b (H2-R5): `src/main.py` never assigns `command_gate` /
    `hover_suspended` and never calls `apply_mesh_change` / `set_status`
    (plan §4.4: nor `add_overlay`)."""
    source = (_SRC / "main.py").read_text(encoding="utf-8")
    assert _main_violations(source) == []


def test_main_py_guard_detects_violations():
    """T-R5b negative control: the scan sees each forbidden form."""
    bad = (
        "app.command_gate = gate\n"
        "app.hover_suspended: bool = True\n"
        "setattr(app, 'command_gate', g)\n"
        "app.apply_mesh_change('x', f)\n"
        "app.set_status('x')\n"
        "app.viewport.add_overlay(o)\n"
    )
    assert len(_main_violations(bad)) == 6


# -- T-R5c ----------------------------------------------------------------------


def _application_test_files() -> list[str]:
    files = sorted(str(p.relative_to(_REPO_ROOT)) for p in (_REPO_ROOT / "tests").glob("test_application_*.py"))
    assert len(files) >= 10
    return files


def _run_application_tests(tmp_path: Path, mode: str) -> tuple[dict[str, str], int, int]:
    report = tmp_path / f"{mode}.xml"
    count_file = tmp_path / f"{mode}.count"
    context_count_file = tmp_path / f"{mode}.context_count"
    env = dict(
        os.environ,
        MIRAI_GATE_MODE=mode,
        MIRAI_GATE_COUNT_FILE=str(count_file),
        MIRAI_CONTEXT_COUNT_FILE=str(context_count_file),
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            *_application_test_files(),
            "-p",
            "tests._inert_gate_plugin",
            "-p",
            "no:cacheprovider",
            "-q",
            f"--junitxml={report}",
        ],
        cwd=_REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
    )
    outcomes = {}
    for case in ET.parse(report).getroot().iter("testcase"):
        key = f"{case.get('classname')}::{case.get('name')}"
        if case.find("failure") is not None or case.find("error") is not None:
            outcomes[key] = "failed"
        elif case.find("skipped") is not None:
            outcomes[key] = "skipped"
        else:
            outcomes[key] = "passed"
    calls = int(count_file.read_text()) if count_file.exists() else 0
    context_calls = int(context_count_file.read_text()) if context_count_file.exists() else 0
    return outcomes, calls, context_calls


def test_pass_through_run_with_inert_active_gate(tmp_path):
    """T-R5c / T-R5c+ (H2-R5, N7; H2 amendment N5): every `tests/test_application_*` with an
    inert but active gate (allow-list = every `mirai.interaction.commands` constant,
    refused = {sentinel}, `refused_contexts` = {}) gives the same outcome per test as without a
    gate, and both the gate and the context check were consulted. Negative controls: an empty
    allow-list makes tests fail, so the gate really is installed on each `Application`; a gate
    listing every operation context makes the contextual-C and Knife tests fail, so the context
    check really acts on that path."""
    baseline, baseline_calls, baseline_context_calls = _run_application_tests(tmp_path, "off")
    inert, inert_calls, inert_context_calls = _run_application_tests(tmp_path, "inert")
    empty, empty_calls, _ = _run_application_tests(tmp_path, "empty")
    contexts, _, listed_context_calls = _run_application_tests(tmp_path, "contexts")

    assert len(baseline) >= 300
    assert "failed" not in baseline.values()
    assert inert == baseline
    assert baseline_calls == 0 and baseline_context_calls == 0
    assert inert_calls > 100
    assert inert_context_calls > 100  # T-R5c+: the context path executed (165 when written)

    failed = [k for k, v in empty.items() if v == "failed"]
    assert len(failed) > 50, f"negative control: only {len(failed)} failures"
    assert set(empty) == set(baseline)
    assert empty_calls > 0

    context_failed = [k for k, v in contexts.items() if v == "failed"]
    assert set(contexts) == set(baseline)
    assert listed_context_calls > 0
    assert len(context_failed) > 50, f"context negative control: only {len(context_failed)} failures"
    assert any("test_application_contextual_c" in k for k in context_failed)
    assert any("test_application_knife" in k for k in context_failed)
