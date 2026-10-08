"""Keine Capability-Gabel: die Lab-Module nutzen nur die öffentliche H2-R4-Liste von
`Application` (AD-013 H2 addendum).

Seit WP-SYM-LAB-03 Slice 5 decken T-R4a und T-R4b **jedes** Lab-Modul ab
(`LAB_MODULES`); bis dahin nur die Module des App-Pfads, weil der alte
`LabDispatcher` daneben lief (Plan §5 Slice 1b).

- T-R4a: statischer AST-Scan der Lab-Module (`LAB_MODULES`) auf
  Unterstrich-Attribute an `Application`-Objekten, `dispatch_command`,
  `select_at`, `history.push` und Importe von `PointerGestures`, `ToolManager`,
  `pick_component`. Seit Slice 2 zusätzlich: jede `Application`-*Methode*, die Lab-Code
  anfasst, steht auf der H2-R4-Liste ((c) `set_status`, (d) `apply_mesh_change`,
  (e) die Event-Eingänge); die einmalige Einrichtung vor dem Event-Loop
  (`init_scene`, `frame_scene`, `set_viewport_size`, H2-R4 (f), Klarstellung
  2026-10-03) nur im Einstieg `run.py` (bis Slice 5 `run_app.py`); zugewiesen wird nur das Gate ((b)
  `command_gate`, `hover_suspended`). Mit Negativkontrollen, damit der Scan nicht
  still nichts findet.
- T-R4a+ (H2-Amendment 2026-10-08, review N3): der Scan schlägt zusätzlich bei jedem
  Aufruf oder Import von `resolve_c_context` und `canonical_vertices`/`canonical_edges`/
  `canonical_faces` in einem Lab-Modul an (sonst wäre es G-4 unter anderem Namen); der Import
  der Enum `CContext` ist erlaubt.
- T-R4b: die Wächter-Fixture aus `_app_lab_support` greift genau beim
  unmittelbaren Aufrufer (`sys._getframe(1)`).
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from mirai.application import Application
from mirai.interaction.input import Input

from symmetry_lab._paths import LAB_DIR

from symmetry_lab.lab_app import lab_key_press

from ._app_lab_support import (  # noqa: F401
    CTRL_Z,
    LAB_MODULES,
    SHIFT_S,
    forbid_lab_calls,
    lab_app,
)

D = Input("key", "d")

FORBIDDEN_CALLS = {"dispatch_command", "select_at", "select_vertex_at"}
FORBIDDEN_IMPORTS = {"PointerGestures", "ToolManager", "pick_component"}
#: T-R4a+ (H2-Amendment, H2-R4): das Lab löst den C-Kontext nie selbst auf und
#: kanonisiert nie selbst — beides wäre G-4 unter anderem Namen.
FORBIDDEN_CONTEXT_NAMES = {
    "resolve_c_context",
    "canonical_vertices",
    "canonical_edges",
    "canonical_faces",
}

#: H2-R4 (c), (d), (e): die öffentlichen `Application`-Methoden für Lab-Code.
ALLOWED_APP_METHODS = {
    "set_status",
    "apply_mesh_change",
    "key_press",
    "key_release",
    "pointer_press",
    "pointer_drag",
    "pointer_release",
    "pointer_scroll",
    "pointer_motion",
    "pointer_leave",
}
#: H2-R4 (f): einmalige Einrichtung vor dem Event-Loop, wie `src/main.py` — nur hier.
SETUP_METHODS = {"init_scene", "frame_scene", "set_viewport_size"}
SETUP_MODULE = "symmetry_lab.run"
#: H2-R4 (b): die einzigen Attribute, die Lab-Code an `Application` setzt.
ASSIGNABLE = {"command_gate", "hover_suspended"}


def _public_methods(cls) -> set[str]:
    return {
        name
        for name in dir(cls)
        if not name.startswith("_")
        and not isinstance(inspect.getattr_static(cls, name), property)
        and callable(getattr(cls, name))
    }


#: Öffentliche Methoden, deren Gebrauch der Methoden-Check prüft (die verbotenen
#: zählt schon `FORBIDDEN_CALLS`).
APP_METHODS = _public_methods(Application) - FORBIDDEN_CALLS


def _is_app_expression(node: ast.AST) -> bool:
    """`app`, `self.app`, `lab.app`, … — die Namen, unter denen Lab-Code die
    `Application` hält."""
    if isinstance(node, ast.Name):
        return node.id == "app"
    if isinstance(node, ast.Attribute):
        return node.attr == "app"
    return False


def violations(source: str, module: str = "") -> list[str]:
    """Verstöße gegen H2-R4 in `source`; `module` = Modulname (für die
    Einrichtungs-Ausnahme (f), die nur `run` hat)."""
    allowed = ALLOWED_APP_METHODS | (SETUP_METHODS if module == SETUP_MODULE else set())
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Attribute) and _is_app_expression(node.value):
            if node.attr in APP_METHODS and node.attr not in allowed:
                found.append(f"{ast.unparse(node)} (nicht auf der H2-R4-Liste)")
            if isinstance(node.ctx, ast.Store) and not node.attr.startswith("_") and (
                node.attr not in ASSIGNABLE
            ):
                found.append(f"{ast.unparse(node)} = … (Schreibzugriff)")
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
                if alias.name in FORBIDDEN_CONTEXT_NAMES:
                    found.append(f"import {alias.name} (H2-R4: Kontext/Kanonisierung)")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.rsplit(".", 1)[-1] in FORBIDDEN_IMPORTS:
                    found.append(f"import {alias.name}")
        elif isinstance(node, ast.Name) and node.id in FORBIDDEN_IMPORTS:
            found.append(f"{node.id} (Name)")
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if name in FORBIDDEN_CONTEXT_NAMES:
                found.append(f"{name}() (H2-R4: Kontext/Kanonisierung)")
    return found


@pytest.mark.parametrize("module", LAB_MODULES)
def test_lab_app_modules_use_only_the_public_allow_list(module):
    """T-R4a: kein Lab-Modul greift an der H2-R4-Liste vorbei."""
    path = LAB_DIR / (module.rsplit(".", 1)[-1] + ".py")
    assert path.is_file(), path
    assert violations(path.read_text(encoding="utf-8"), module) == []


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


def test_scan_flags_context_resolution_and_canonicalisation():
    """T-R4a+, Negativkontrolle: Aufruf und Import von `resolve_c_context` und der drei
    `canonical_*` werden gefunden, der Import der Enum `CContext` nicht."""
    bad = """
from mirai.topology.contextual_c import resolve_c_context
from mirai.symmetry_coordination import canonical_vertices, canonical_edges, canonical_faces
import mirai.topology.contextual_c as cc
def f(app, index, ids):
    resolve_c_context(app.selection)
    cc.resolve_c_context(app.selection)
    canonical_vertices(index, ids)
    canonical_edges(index, ids)
    canonical_faces(index, ids)
"""
    found = violations(bad)
    assert len(found) == 4 + 5, found
    assert violations("from mirai.topology.contextual_c import CContext\nCContext.SPLIT\n") == []


def test_lab_modules_neither_import_nor_call_the_context_functions():
    """T-R4a+ gegen die echten Dateien: kein Lab-Modul trifft eine der vier Funktionen
    (der Gesamt-Scan oben deckt das schon ab; hier die gezielte Aussage mit Text)."""
    for module in LAB_MODULES:
        path = LAB_DIR / (module.rsplit(".", 1)[-1] + ".py")
        text = path.read_text(encoding="utf-8")
        hits = [line for line in violations(text, module) if "Kontext/Kanonisierung" in line]
        assert hits == [], (module, hits)


def test_scan_flags_methods_outside_the_allow_list():
    """T-R4a, Negativkontrolle (Slice 2): öffentliche Methoden außerhalb von H2-R4
    und Schreibzugriffe außerhalb des Gates werden gefunden."""
    bad = """
def f(app, lab):
    app.update_viewport(0.1)
    lab.app.set_shift_held(True)
    app.shutdown()
    handler = app.dispatch_command
    app.status_message = "x"
    app.command_gate = None
    app.hover_suspended = False
    app.set_status("ok")
    app.apply_mesh_change("x", lambda: None)
    app.key_press(None)
"""
    found = violations(bad)
    assert sorted(found) == sorted([
        "app.update_viewport (nicht auf der H2-R4-Liste)",
        "lab.app.set_shift_held (nicht auf der H2-R4-Liste)",
        "app.shutdown (nicht auf der H2-R4-Liste)",
        "app.dispatch_command (verboten)",
        "app.status_message = … (Schreibzugriff)",
    ]), found


@pytest.mark.parametrize("name", sorted(SETUP_METHODS))
def test_setup_calls_are_allowed_only_in_run(name):
    """H2-R4 (f), Klarstellung Slice 2: `init_scene`/`frame_scene`/`set_viewport_size`
    genau in `run.py`, in jedem anderen Lab-Modul ein Verstoß."""
    source = f"def f(app):\n    app.{name}()\n"
    assert violations(source, SETUP_MODULE) == []
    for module in LAB_MODULES:
        if module != SETUP_MODULE:
            assert violations(source, module) == [f"app.{name} (nicht auf der H2-R4-Liste)"]


def test_method_allow_list_names_real_application_methods():
    """Die Listen nennen nur Methoden, die es gibt (Tippfehler fielen sonst nie auf)."""
    assert ALLOWED_APP_METHODS | SETUP_METHODS <= APP_METHODS
    assert {"update_viewport", "shutdown", "set_shift_held"} <= APP_METHODS


def test_run_uses_exactly_the_setup_exception():
    """`run.py` braucht die Ausnahme (f) wirklich — ohne sie wäre es ein Verstoß."""
    source = (LAB_DIR / "run.py").read_text(encoding="utf-8")
    assert violations(source, SETUP_MODULE) == []
    assert sorted(violations(source)) == sorted(
        f"app.{name} (nicht auf der H2-R4-Liste)" for name in SETUP_METHODS
    )


def test_scan_ignores_own_underscore_members():
    """T-R4a: eigene private Member (`self._set`, `lab._cycle`) sind keine Verletzung."""
    assert violations("def f(self, lab):\n    self._set(1)\n    lab._cycle()\n") == []


def test_lab_modules_cover_every_lab_file():
    """T-R4a/T-R4b (seit Slice 5): jede Python-Datei des Labs steht in der Liste —
    ein neues Modul fiele sonst still aus beiden Prüfungen heraus."""
    files = {p.stem for p in Path(LAB_DIR).glob("*.py") if p.stem != "__init__"}
    assert {f"symmetry_lab.{name}" for name in files} == set(LAB_MODULES)


def test_guard_rejects_a_lab_module_as_immediate_caller(lab_app):
    """T-R4b: `dispatch_command`/`select_at` werfen, wenn ein Lab-Modul sie direkt aufruft."""
    app, _lab = lab_app
    for module in LAB_MODULES:
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
