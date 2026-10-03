"""Helfer für die Re-Symmetrize-Tests auf dem App-Pfad (WP-SYM-LAB-03 Slice 3).

Wie `_app_lab_support`: headless (TraceStore), Lab gebaut über
`run_app.build_app_lab`. Auswahl entsteht nur über Klicks (öffentliche Eingänge),
Symmetrie über Shift+S, die Vorschau über M — alles durch `lab_key_press`.
"""

from __future__ import annotations

from mirai.application import Application
from mirai.interaction.input import Input
from mirai.viewport.picking import pick_nearest_vertex

from symmetry_lab.lab_app import SymmetryAppLab
from symmetry_lab.lab_topology import topology_report

from ._app_lab_support import HEIGHT, M, SHIFT_S, WIDTH, click, make_lab, press, screen

R = Input("key", "r")
X = Input("key", "x")
SHIFT_X = Input("key", "x", frozenset({"shift"}))
ALT_A = Input("key", "a", frozenset({"alt"}))
ONE, TWO, THREE = Input("key", "1"), Input("key", "2"), Input("key", "3")
D = Input("key", "d")
SHIFT_D = Input("key", "d", frozenset({"shift"}))
SHIFT_LMB = Input("mouse", "LEFT", frozenset({"shift"}))
ALT_LMB = Input("mouse", "LEFT", frozenset({"alt"}))
WHEEL_UP = Input("wheel", "UP")


def first_visible(app: Application, ids) -> object:
    """Erster eindeutig anklickbarer Vertex aus `ids` (Verdeckung wie die App:
    nur bei sichtbaren Faces)."""
    mesh = app.scene.mesh
    occlusion = app.display.show_faces
    for vid in sorted(ids, key=int):
        sx, sy = screen(app, vid)
        if pick_nearest_vertex(app.camera, mesh, sx, sy, WIDTH, HEIGHT, occlusion=occlusion) == vid:
            return vid
    raise AssertionError("kein sichtbarer Vertex")


def side_vertices(app: Application, side: int) -> list:
    sides = topology_report(app.scene.mesh).sides
    return sorted((v for v, s in sides.vertex_side.items() if s == side), key=int)


def seam_vertices(app: Application) -> list:
    return sorted(topology_report(app.scene.mesh).sides.seam_vertices, key=int)


def select(app: Application, vid) -> None:
    """Klick auf `vid` (Ersetzen), wie im Fenster."""
    click(app, *screen(app, vid))
    assert app.selection.vertices == {vid}, (vid, app.selection.vertices)


def select_on_side(app: Application, side: int):
    vid = first_visible(app, side_vertices(app, side))
    select(app, vid)
    return vid


def symmetry_to(app: Application, lab: SymmetryAppLab, axis) -> None:
    for _ in range(4):
        if lab.axis == axis:
            return
        assert press(app, lab, SHIFT_S)
    assert lab.axis == axis


def open_preview(asset: str = "man_with_shoes_basemesh", side: int = 0):
    """Symmetrie X, ein Vertex auf `side` per Klick gewählt, M → Vorschau offen.
    Rückgabe: (app, lab, source vertex)."""
    app, lab = make_lab(asset)
    symmetry_to(app, lab, "X")
    source = select_on_side(app, side)
    assert press(app, lab, M) is True
    assert lab.preview_open
    return app, lab, source


def state_snapshot(app: Application) -> tuple:
    """Modell, Auswahl, History und Constraint — was die Vorschau nie ändern darf."""
    selection = app.selection
    return (
        selection.mode,
        frozenset(selection.vertices),
        frozenset(selection.edges),
        frozenset(selection.faces),
        len(app.history),
        app.history.can_undo(),
        app.history.can_redo(),
        app.scene.mesh.export_state(),
        app.axis_constraint,
    )
