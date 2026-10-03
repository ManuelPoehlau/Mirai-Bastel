"""Gemeinsame Helfer der Tests für das Lab auf dem App-Pfad (WP-SYM-LAB-03 S1b).

Headless wie `tests/test_application_pointer.py` (TraceStore, kein Fenster). Das Lab
wird wie in `run_app.build_lab` aufgebaut, nur ohne Fenster-Handler.

`forbid_lab_calls` ist T-R4b (AD-013 H2-R4, review CLAUDE-002 N6): jeder Test, der
diese Fixture importiert, läuft mit `Application.dispatch_command` und `select_at`
so gepatcht, dass sie werfen, wenn ihr **unmittelbarer** Aufrufer ein neues
Lab-Modul ist. `key_press` → `dispatch_command` mit einem Lab-Frame weiter oben
im Stack bleibt erlaubt.
"""

from __future__ import annotations

import sys

import pytest

from mirai.application import Application
from mirai.interaction.input import Input
from mirai.viewport.picking import pick_nearest_vertex

from symmetry_lab.lab_app import SymmetryAppLab, lab_key_press
from symmetry_lab.run_app import build_app_lab

WIDTH, HEIGHT = 800, 600
MISS = (2.0, 2.0)

SHIFT_S = Input("key", "s", frozenset({"shift"}))
M = Input("key", "m")
SHIFT_B = Input("key", "b", frozenset({"shift"}))
W = Input("key", "w")
E = Input("key", "e")
C = Input("key", "c")
ESC = Input("key", "ESCAPE")
CTRL_Z = Input("key", "z", frozenset({"ctrl"}))
CTRL_Y = Input("key", "y", frozenset({"ctrl"}))
LMB = Input("mouse", "LEFT")

#: Die neuen Lab-Module des App-Pfads (Slice 1b; Slice 2: die Drag-Kosten-Probe) —
#: Gegenstand von T-R4a/T-R4b.
LAB_APP_MODULES = (
    "symmetry_lab.lab_app",
    "symmetry_lab.lab_app_window",
    "symmetry_lab.lab_overlays",
    "symmetry_lab.run_app",
    "symmetry_lab.probe_drag_cost",
)


def make_lab(asset: str = "subd_cube") -> tuple[Application, SymmetryAppLab]:
    """Wie im Fenster: `run_app.build_app_lab` (seit Slice 2 der fensterlose Teil
    von `build_lab`, auch von `probe_drag_cost` genutzt)."""
    return build_app_lab(asset, WIDTH, HEIGHT)


def press(app: Application, lab: SymmetryAppLab, inp: Input) -> bool:
    return lab_key_press(app, lab, inp)


def screen(app: Application, vid):
    return app.camera.project_to_screen(app.scene.mesh.vertex_position(vid), WIDTH, HEIGHT)


def visible(app: Application) -> list:
    mesh = app.scene.mesh
    hits = []
    for vid in sorted(mesh.all_vertex_ids()):
        sx, sy = screen(app, vid)
        if pick_nearest_vertex(app.camera, mesh, sx, sy, WIDTH, HEIGHT, occlusion=True) == vid:
            hits.append(vid)
    assert len(hits) >= 2
    return hits


def click(app: Application, x: float, y: float, inp: Input = LMB) -> bool:
    app.pointer_press(inp, x, y)
    return app.pointer_release(inp.value, x, y)


def arm_and_move(app: Application, lab: SymmetryAppLab, key: Input = W) -> None:
    """Transform über den Lab-Pfad scharf schalten und bewegen (Ziel: Auswahl)."""
    assert press(app, lab, key)
    assert app.transform_command is not None
    app.pointer_motion(400, 300, 12.0, 7.0)
    assert app.transform_interacting


def start_knife(app: Application, lab: SymmetryAppLab) -> None:
    """C mit leerer Auswahl (Symmetrie aus) → Knife-Session über den Lab-Pfad."""
    app.pointer_motion(*MISS)
    app.selection.clear()
    assert press(app, lab, C)
    assert app.knife_active


@pytest.fixture
def lab_app():
    return make_lab()


@pytest.fixture(autouse=True)
def forbid_lab_calls(monkeypatch):
    """T-R4b: `dispatch_command`/`select_at` werfen bei einem Lab-Modul als
    unmittelbarem Aufrufer."""
    for name in ("dispatch_command", "select_at"):
        original = getattr(Application, name)

        def guarded(self, *args, __original=original, __name=name, **kwargs):
            caller = sys._getframe(1).f_globals.get("__name__", "")
            if caller in LAB_APP_MODULES:
                raise AssertionError(f"H2-R4: {caller} ruft Application.{__name} auf")
            return __original(self, *args, **kwargs)

        monkeypatch.setattr(Application, name, guarded)
    yield
