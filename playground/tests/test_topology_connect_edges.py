"""Headless-Tests für AP-05 Connect Edges (kein GL, kein Fenster).

    1. Zwei kompatible Edges (gegenüberliegend in einer Quad-Face) →
       genau 1 History-Eintrag, neue Verbindungskante entsteht, Original-
       Edges gesplittet (neue Vertex-Anzahl sichtbar)
    2. Ungültige Auswahl (1 Edge) → TopologyToolError, Mesh unverändert,
       kein History-Eintrag
    3. Undo/Redo-Zyklus
    4. Determinismus: gleiche Edge-Menge in unterschiedlicher Set-Iterationsreihen-
       folge übergeben → identisches Ergebnis
    5. "kind v"-Fall (Kette über gemeinsamen regulären Innen-Vertex ohne
       gemeinsame Face) → freie Verbindungskante zwischen Mittelpunkten,
       1 History-Eintrag, Undo/Redo; Boundary-Vertex-Variante → Fehler
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REPO_SRC = _REPO_ROOT / "src"
_RIGGING = _REPO_ROOT / "experiments" / "rigging-skinning-morphing"
for _p in (str(_REPO_SRC), str(_REPO_ROOT), str(_RIGGING)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from core import Mesh  # noqa: E402
from playground.app import PlaygroundApp  # noqa: E402
from playground.topology_tools.connect_edges import (  # noqa: E402
    connect_selected_edges,
    TopologyToolError,
)


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _counts(app: PlaygroundApp) -> tuple[int, int, int]:
    mesh = app.scene.mesh
    return (
        len(list(mesh.all_vertex_ids())),
        len(list(mesh.all_edge_ids())),
        len(list(mesh.all_face_ids())),
    )


def _two_opposite_edges(mesh) -> tuple:
    """Zwei gegenüberliegende Edges aus der ersten Quad-Face des Mesh."""
    for fid in mesh.all_face_ids():
        edges = mesh.face_edges(fid)
        if len(edges) == 4:
            return edges[0], edges[2]
    pytest.fail("Kein Quad-Face im Mesh gefunden")


# ---------------------------------------------------------------------------
# 1. Zwei kompatible Edges → 1 History-Eintrag, neue Kante, neue Vertices
# ---------------------------------------------------------------------------

def test_connect_pushes_exactly_one_history_entry():
    app = PlaygroundApp()
    app.load_cube()
    mesh = app.scene.mesh
    e0, e2 = _two_opposite_edges(mesh)

    assert len(app.scene.history) == 0
    connect_selected_edges(app.scene, {e0, e2})
    assert len(app.scene.history) == 1


def test_connect_creates_new_vertices_and_edge():
    app = PlaygroundApp()
    app.load_cube()
    before = _counts(app)
    mesh = app.scene.mesh
    e0, e2 = _two_opposite_edges(mesh)

    result = connect_selected_edges(app.scene, {e0, e2})

    after = _counts(app)
    assert len(result) == 1, "Genau eine neue Verbindungskante erwartet"
    assert after[0] > before[0], "Split muss neue Vertices erzeugen"
    assert after[1] > before[1], "Neue Edges erwartet"
    assert after[2] >= before[2], "Face-Anzahl darf nicht sinken"


# ---------------------------------------------------------------------------
# 2. Ungültige Auswahl (< 2 Edges) → TopologyToolError, Mesh unverändert
# ---------------------------------------------------------------------------

def test_connect_one_edge_raises_and_mesh_unchanged():
    app = PlaygroundApp()
    app.load_cube()
    before = _counts(app)
    mesh = app.scene.mesh
    edge_id = next(iter(mesh.all_edge_ids()))

    with pytest.raises(TopologyToolError):
        connect_selected_edges(app.scene, {edge_id})

    assert _counts(app) == before
    assert len(app.scene.history) == 0


def test_connect_empty_raises():
    app = PlaygroundApp()
    app.load_cube()
    with pytest.raises(TopologyToolError):
        connect_selected_edges(app.scene, set())


# ---------------------------------------------------------------------------
# 3. Undo/Redo-Zyklus
# ---------------------------------------------------------------------------

def test_connect_undo_redo_cycle():
    app = PlaygroundApp()
    app.load_cube()
    before = _counts(app)
    mesh = app.scene.mesh
    e0, e2 = _two_opposite_edges(mesh)

    connect_selected_edges(app.scene, {e0, e2})
    after_connect = _counts(app)
    assert after_connect != before

    app.undo()
    assert _counts(app) == before, "Undo muss Ausgangszustand herstellen"

    app.redo()
    assert _counts(app) == after_connect, "Redo muss Connect-Zustand herstellen"


# ---------------------------------------------------------------------------
# 4. Determinismus: Set-Iterationsreihenfolge darf Ergebnis nicht beeinflussen
# ---------------------------------------------------------------------------

def test_connect_is_deterministic_regardless_of_set_order():
    """Gleiche Edges, unterschiedliche Set-Iteration → identische Topologie."""
    def _run_connect(edge_pair: tuple) -> tuple[int, int, int]:
        app = PlaygroundApp()
        app.load_cube()
        connect_selected_edges(app.scene, set(edge_pair))
        return _counts(app)

    app0 = PlaygroundApp()
    app0.load_cube()
    e0, e2 = _two_opposite_edges(app0.scene.mesh)

    result_a = _run_connect((e0, e2))
    result_b = _run_connect((e2, e0))
    assert result_a == result_b, "Ergebnis muss ID-Reihenfolge-unabhängig sein"


# ---------------------------------------------------------------------------
# Hilfsfunktion: 2×2-Quad-Grid mit "kind v"-Konfiguration am Mittelpunkt
# ---------------------------------------------------------------------------

def _build_2x2_grid():
    """3×3 Vertex-Grid → 4 Quads. Mittelpunkt p[(1,1)] hat Valenz 4.

    Kante p[(1,0)]-p[(1,1)] und Kante p[(1,1)]-p[(1,2)] teilen den
    Mittelpunkt als shared vertex, haben aber keine gemeinsame Face →
    klassischer "kind v"-Fall.
    """
    mesh = Mesh()
    p = {}
    for row in range(3):
        for col in range(3):
            p[(row, col)] = mesh.add_vertex((float(col), float(row), 0.0))

    mesh.add_face([p[(0, 0)], p[(0, 1)], p[(1, 1)], p[(1, 0)]])
    mesh.add_face([p[(0, 1)], p[(0, 2)], p[(1, 2)], p[(1, 1)]])
    mesh.add_face([p[(1, 0)], p[(1, 1)], p[(2, 1)], p[(2, 0)]])
    mesh.add_face([p[(1, 1)], p[(1, 2)], p[(2, 2)], p[(2, 1)]])

    center = p[(1, 1)]
    edge_left = edge_right = None
    for eid in mesh.all_edge_ids():
        verts = set(mesh.edge_vertices(eid))
        if verts == {p[(1, 0)], center}:
            edge_left = eid
        if verts == {center, p[(1, 2)]}:
            edge_right = eid

    assert edge_left is not None and edge_right is not None
    return mesh, p, center, edge_left, edge_right


# ---------------------------------------------------------------------------
# 5a. "kind v" positiv — freie Verbindungskante, 1 History-Eintrag
# ---------------------------------------------------------------------------

def test_connect_kind_v_creates_free_edge():
    """'kind v': zwei Kanten teilen regulären Innen-Vertex ohne Face →
    connect_selected_edges erzeugt eine freie Verbindungskante."""
    app = PlaygroundApp()
    app.load_cube()
    mesh, p, center, e_left, e_right = _build_2x2_grid()
    app.scene.mesh = mesh

    # Verifikation Setup: keine gemeinsame Face
    common = set(mesh.edge_faces(e_left)) & set(mesh.edge_faces(e_right))
    assert len(common) == 0, "Test-Setup: Kanten sollen keine gemeinsame Face haben"

    v_before = len(list(mesh.all_vertex_ids()))
    f_before = len(list(mesh.all_face_ids()))

    result = connect_selected_edges(app.scene, {e_left, e_right})

    assert len(result) == 1, "Genau eine neue Verbindungskante erwartet"
    new_eid = result[0]
    assert mesh.is_valid_edge(new_eid), "Neue EdgeId muss gültig sein"
    assert mesh.edge_faces(new_eid) == [], "Verbindungskante ist frei (keine Faces)"
    assert len(list(mesh.all_vertex_ids())) == v_before + 2, "Beide Quell-Edges gesplittet"
    assert len(list(mesh.all_face_ids())) == f_before, "Face-Anzahl unverändert"
    assert len(app.scene.history) == 1, "Genau ein History-Eintrag"


def test_connect_kind_v_undo_redo():
    """'kind v'-Verbindung ist über Undo/Redo vollständig reversibel."""
    app = PlaygroundApp()
    app.load_cube()
    mesh, p, center, e_left, e_right = _build_2x2_grid()
    app.scene.mesh = mesh

    v_before = len(list(mesh.all_vertex_ids()))
    f_before = len(list(mesh.all_face_ids()))

    connect_selected_edges(app.scene, {e_left, e_right})
    v_after = len(list(mesh.all_vertex_ids()))
    assert v_after > v_before

    app.undo()
    assert len(list(app.scene.mesh.all_vertex_ids())) == v_before, "Undo stellt Ausgangszustand her"
    assert len(list(app.scene.mesh.all_face_ids())) == f_before

    app.redo()
    assert len(list(app.scene.mesh.all_vertex_ids())) == v_after, "Redo stellt Connect-Zustand her"


# ---------------------------------------------------------------------------
# 5b. "kind v" negativ — Boundary-/Mixed-Valence-Vertex → TopologyToolError
# ---------------------------------------------------------------------------

def test_connect_kind_v_boundary_vertex_raises():
    """Kette über Vertex mit Valenz < 4 (Rand-Vertex) → TopologyToolError."""
    from playground.topology_tools.connect_edges import _build_adjacency

    # 1×2 Quad-Strip: Mittelpunkt b-f hat Valenz 3 (Randmesh, nicht regulär)
    mesh = Mesh()
    a = mesh.add_vertex((-2.0, 0.0, 0.0))
    b = mesh.add_vertex((-1.0, 0.0, 0.0))
    c = mesh.add_vertex((0.0, 0.0, 0.0))
    e = mesh.add_vertex((-2.0, 1.0, 0.0))
    f = mesh.add_vertex((-1.0, 1.0, 0.0))
    g = mesh.add_vertex((0.0, 1.0, 0.0))
    mesh.add_face([a, b, f, e])
    mesh.add_face([b, c, g, f])

    # e-f ist in Face [a,b,f,e]; f-g ist in Face [b,c,g,f]; teilen f, keine gemeinsame Face
    edge_ef = edge_fg = None
    for eid in mesh.all_edge_ids():
        verts = set(mesh.edge_vertices(eid))
        if verts == {e, f}:
            edge_ef = eid
        if verts == {f, g}:
            edge_fg = eid

    assert edge_ef is not None and edge_fg is not None
    common = set(mesh.edge_faces(edge_ef)) & set(mesh.edge_faces(edge_fg))
    assert len(common) == 0

    with pytest.raises(TopologyToolError, match="Boundary"):
        _build_adjacency(mesh, {edge_ef, edge_fg})
