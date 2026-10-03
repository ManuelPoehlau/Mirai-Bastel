"""Keine Capability-Gabel: die Lab-Module des App-Pfads nutzen nur die öffentliche
H2-R4-Liste von `Application` (AD-013 H2 addendum).

- T-R4a: statischer AST-Scan der neuen Lab-Module (`LAB_APP_MODULES`) auf
  Unterstrich-Attribute an `Application`-Objekten, `dispatch_command`,
  `select_at`, `history.push` und Importe von `PointerGestures`, `ToolManager`,
  `pick_component`. Mit Negativkontrolle, damit der Scan nicht still nichts findet.
- T-R4b: die Wächter-Fixture aus `_app_lab_support` greift genau beim
  unmittelbaren Aufrufer (`sys._getframe(1)`).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from mirai.interaction.input import Input

from symmetry_lab._paths import LAB_DIR

from symmetry_lab.lab_app import lab_key_press

from ._app_lab_support import (  # noqa: F401
    CTRL_Z,
    LAB_APP_MODULES,
    SHIFT_S,
    forbid_lab_calls,
    lab_app,
)

D = Input("key", "d")

FORBIDDEN_CALLS = {"dispatch_command", "select_at", "select_vertex_at"}
FORBIDDEN_IMPORTS = {"PointerGestures", "ToolManager", "pick_component"}


def _is_app_expression(node: ast.AST) -> bool:
    """`app`, `self.app`, `lab.app`, … — die Namen, unter denen Lab-Code die
    `Application` hält."""
    if isinstance(node, ast.Name):
        return node.id == "app"
    if isinstance(node, ast.Attribute):
        return node.attr == "app"
    return False


def violations(source: str) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("_") and not node.attr.startswith("__") and _is_app_expression(
                node.value
            ):
                found.append(f"{ast.unparse(node)} (Unterstrich-Member)")
            if node.attr in FORBIDDEN_CALLS:
                found.append(f"{ast.unparse(node)} (verboten)")
            if (
                node.attr == "push"
                and isinstance(node.value, ast.Attribute)
                and node.value.attr == "history"
            ):
                found.append(f"{ast.unparse(node)} (history.push)")
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in FORBIDDEN_IMPORTS:
                    found.append(f"import {alias.name}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.rsplit(".", 1)[-1] in FORBIDDEN_IMPORTS:
                    found.append(f"import {alias.name}")
        elif isinstance(node, ast.Name) and node.id in FORBIDDEN_IMPORTS:
            found.append(f"{node.id} (Name)")
    return found


@pytest.mark.parametrize("module", LAB_APP_MODULES)
def test_lab_app_modules_use_only_the_public_allow_list(module):
    """T-R4a: kein Lab-Modul des App-Pfads greift an der H2-R4-Liste vorbei."""
    path = LAB_DIR / (module.rsplit(".", 1)[-1] + ".py")
    assert path.is_file(), path
    assert violations(path.read_text(encoding="utf-8")) == []


def test_scan_finds_every_forbidden_pattern():
    """T-R4a, Negativkontrolle: jedes verbotene Muster wird gefunden."""
    bad = """
from mirai.interaction.pointer import PointerGestures
from mirai.interaction.tool import ToolManager
import mirai.viewport.picking.pick_component
def f(app, lab, self):
    app._cancel()
    lab.app._knife = None
    self.app._set_status("x")
    app.dispatch_command("Undo")
    app.select_at("Select", 1, 2)
    app.scene.history.push(None)
    app.history.push(None)
"""
    found = violations(bad)
    assert len(found) == 10, found


def test_scan_ignores_own_underscore_members():
    """T-R4a: eigene private Member (`self._set`, `lab._cycle`) sind keine Verletzung."""
    assert violations("def f(self, lab):\n    self._set(1)\n    lab._cycle()\n") == []


def test_lab_app_modules_cover_every_new_file():
    """T-R4a: jede Datei des App-Pfads steht in der Scan-Liste."""
    for name in ("lab_app", "lab_app_window", "lab_overlays", "run_app"):
        assert f"symmetry_lab.{name}" in LAB_APP_MODULES
        assert (Path(LAB_DIR) / f"{name}.py").is_file()


def test_guard_rejects_a_lab_module_as_immediate_caller(lab_app):
    """T-R4b: `dispatch_command`/`select_at` werfen, wenn ein Lab-Modul sie direkt aufruft."""
    app, _lab = lab_app
    for module in LAB_APP_MODULES:
        scope = {"__name__": module, "app": app}
        with pytest.raises(AssertionError, match="H2-R4"):
            exec("app.dispatch_command('Undo')", scope)
        with pytest.raises(AssertionError, match="H2-R4"):
            exec("app.select_at('Select', 1.0, 1.0)", scope)
    # Ein anderer Aufrufer (hier: der Test) bleibt unberührt.
    assert app.dispatch_command("CycleDisplayMode") in (True, False)


def test_guard_allows_application_calls_below_a_lab_frame(lab_app):
    """T-R4b: `lab_key_press` → `app.key_press` → `dispatch_command` (D, Undo) hat einen
    Lab-Frame weiter oben im Stack, aber `Application` als unmittelbaren Aufrufer —
    legitim, der Wächter (autouse) lässt es durch."""
    app, lab = lab_app
    mode = app.display.mode
    assert lab_key_press(app, lab, D) is True
    assert app.display.mode is not mode
    assert lab_key_press(app, lab, SHIFT_S) is True
    assert lab_key_press(app, lab, CTRL_Z) is True
    assert lab.axis is None
