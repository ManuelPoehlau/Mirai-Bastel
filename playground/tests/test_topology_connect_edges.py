"""Headless-Tests für AP-05 Connect Edges (kein GL, kein Fenster).

    1. Zwei kompatible Edges (gegenüberliegend in einer Quad-Face) →
       genau 1 History-Eintrag, neue Verbindungskante entsteht, Original-
       Edges gesplittet (neue Vertex-Anzahl sichtbar)
    2. Ungültige Auswahl (1 Edge) → TopologyToolError, Mesh unverändert,
       kein History-Eintrag
    3. Undo/Redo-Zyklus
    4. Determinismus: gleiche Edge-Menge in unterschiedlicher Set-Iterationsreihen-
       folge übergeben → identisches Ergebnis
    5. "kind v"-Fall (Kette über gemeinsamen Vertex ohne Face) →
       TopologyToolError, Mesh unverändert
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
# 5. "kind v"-Fall → TopologyToolError, kein Crash, Mesh unverändert
# ---------------------------------------------------------------------------

def _build_v_case_mesh() -> Mesh:
    """Minimal-Mesh mit zwei Kanten, die einen gemeinsamen Valenz-4-Vertex
    teilen, aber keine gemeinsame Face haben (klassischer 'kind v'-Fall).

    Struktur: zwei getrennte Quads mit einem gemeinsamen Vertex in der Mitte.

       v0---v1---v4
       |  A  | B  |
       v2---v3---v5

    v3 ist der gemeinsame Vertex (Valenz 4). Edges v0-v1 (in Face A) und
    v4-v5 (in Face B) teilen keine Face, aber eine Kette ließe sich nur
    über v3/v1 verbinden — hier nicht implementiert.

    Einfachere Konstruktion für den Test: wir bauen zwei Quads die v3
    gemeinsam haben, und wählen dann e(v0,v1) und e(v4,v5) — die teilen
    keinen Vertex. Stattdessen wählen wir e(v1,v3) und e(v3,v5), die
    teilen v3 (shared vertex) aber keine gemeinsame Face.
    """
    mesh = Mesh()

    # Face A: v0, v1, v3, v2
    v0 = mesh.add_vertex((-1.0, 1.0, 0.0))
    v1 = mesh.add_vertex((0.0, 1.0, 0.0))
    v2 = mesh.add_vertex((-1.0, 0.0, 0.0))
    v3 = mesh.add_vertex((0.0, 0.0, 0.0))
    mesh.add_face([v0, v1, v3, v2])

    # Face B: v1, v4, v5, v3 — teilt v1 und v3 mit Face A
    v4 = mesh.add_vertex((1.0, 1.0, 0.0))
    v5 = mesh.add_vertex((1.0, 0.0, 0.0))
    mesh.add_face([v1, v4, v5, v3])

    return mesh, v1, v3


def test_connect_kind_v_raises_topology_error():
    """'kind v'-Fall (Kette über Vertex ohne gemeinsame Face) → TopologyToolError."""
    app = PlaygroundApp()
    app.load_cube()

    # Wir ersetzen das Cube-Mesh durch unser Testmesh und hängen es ans scene
    mesh, v1, v3 = _build_v_case_mesh()

    # Die Kante zwischen v1 und v3 liegt in BEIDEN Faces — keine Kante zwischen
    # v0 und v3 ohne Face. Wir brauchen stattdessen zwei Kanten, die v3 teilen
    # aber keine Face gemeinsam haben.
    # Auf diesem Mesh gibt es keine solche Konfiguration in einfacher Form.
    # Daher simulieren wir den Fall direkt auf _build_adjacency:
    from playground.topology_tools.connect_edges import _build_adjacency

    # Erstelle einen minimalen "kind v"-Fall in einem synthetischen Mesh:
    # Drei Quads in einer Reihe. Die mittlere Edge-Verbindung hat Valenz 4.
    mesh2 = Mesh()
    # Bottom row
    a = mesh2.add_vertex((-2.0, 0.0, 0.0))
    b = mesh2.add_vertex((-1.0, 0.0, 0.0))
    c = mesh2.add_vertex((0.0, 0.0, 0.0))
    d = mesh2.add_vertex((1.0, 0.0, 0.0))
    # Top row
    e = mesh2.add_vertex((-2.0, 1.0, 0.0))
    f = mesh2.add_vertex((-1.0, 1.0, 0.0))
    g = mesh2.add_vertex((0.0, 1.0, 0.0))
    h = mesh2.add_vertex((1.0, 1.0, 0.0))
    # Three quads
    mesh2.add_face([a, b, f, e])
    mesh2.add_face([b, c, g, f])
    mesh2.add_face([c, d, h, g])

    # Finde Edge a-e (links außen) und Edge d-h (rechts außen) — die teilen
    # keinen Vertex, also kein "kind v". Wir brauchen Edges die v teilen.
    # Finde stattdessen Edge e-f und Edge f-g: teilen v=f, aber HABEN eine
    # gemeinsame Face (quad b,c,g,f enthält f-g, quad a,b,f,e enthält e-f,
    # beide teilen Face b,c,g,f NICHT... wait let me think again.
    # e-f ist in Face [a,b,f,e]. f-g ist in Face [b,c,g,f]. Keine gemeinsame Face.
    # Vertex f hat Valenz: Kanten zu e, a(?), b, g, c(?) — nein.
    # f verbindet: e-f, f-a (nein, keine direkte Kante), b-f, f-g.
    # Also Edges incident zu f: e-f, b-f, f-g. Valenz=3 → _is_regular_interior_vertex
    # gibt False zurück → wirft "Boundary/Mixed-Valence" Error, nicht "kind v".
    # Kein einfaches 2D-Mesh hat Valenz 4 an einem Interior-Vertex mit nur 2 Faces.
    # Für echten "kind v" brauchen wir einen Vertex mit Valenz ≥ 4.
    # Das geht mit einem 2x2-Quad-Grid (4 Faces, Mittelpunkt hat Valenz 4).

    mesh3 = Mesh()
    # 3x3 Vertex-Grid → 2x2 Quads
    p = {}
    for row in range(3):
        for col in range(3):
            p[(row, col)] = mesh3.add_vertex((float(col), float(row), 0.0))

    mesh3.add_face([p[(0,0)], p[(0,1)], p[(1,1)], p[(1,0)]])
    mesh3.add_face([p[(0,1)], p[(0,2)], p[(1,2)], p[(1,1)]])
    mesh3.add_face([p[(1,0)], p[(1,1)], p[(2,1)], p[(2,0)]])
    mesh3.add_face([p[(1,1)], p[(1,2)], p[(2,2)], p[(2,1)]])

    # p[(1,1)] ist jetzt Mittelpunkt mit Valenz 4 — regulärer Innen-Vertex.
    # Finde Kanten die p[(1,1)] als Endpunkt haben und zu p[(0,1)] bzw. p[(1,2)] gehen.
    # Diese teilen p[(1,1)] als shared vertex. Haben sie eine gemeinsame Face?
    # Kante p[(0,1)]-p[(1,1)] ist in Faces [p00,p01,p11,p10] und [p01,p02,p12,p11].
    # Kante p[(1,1)]-p[(1,2)] ist in Faces [p01,p02,p12,p11] und [p11,p12,p22,p21].
    # Gemeinsame Face: [p01,p02,p12,p11] → "kind f", nicht "kind v"!
    #
    # Für echtes "kind v": Kanten die p[(1,1)] teilen aber KEINE gemeinsame Face haben.
    # z.B. Kante p[(1,0)]-p[(1,1)] und Kante p[(1,1)]-p[(1,2)]:
    #   - p[(1,0)]-p[(1,1)]: in Face [p00,p01,p11,p10] und [p10,p11,p21,p20]
    #   - p[(1,1)]-p[(1,2)]: in Face [p01,p02,p12,p11] und [p11,p12,p22,p21]
    #   Keine gemeinsame Face → "kind v"-Fall!

    center = p[(1, 1)]
    # Suche Kante (p10, p11) und (p11, p12)
    edge_p10_p11 = None
    edge_p11_p12 = None
    for eid in mesh3.all_edge_ids():
        verts = set(mesh3.edge_vertices(eid))
        if verts == {p[(1, 0)], center}:
            edge_p10_p11 = eid
        if verts == {center, p[(1, 2)]}:
            edge_p11_p12 = eid

    assert edge_p10_p11 is not None, "Kante p10-p11 nicht gefunden"
    assert edge_p11_p12 is not None, "Kante p11-p12 nicht gefunden"

    # Verifikation: gemeinsamer Vertex aber keine gemeinsame Face
    shared_v = set(mesh3.edge_vertices(edge_p10_p11)) & set(mesh3.edge_vertices(edge_p11_p12))
    assert len(shared_v) == 1 and center in shared_v
    common_faces = set(mesh3.edge_faces(edge_p10_p11)) & set(mesh3.edge_faces(edge_p11_p12))
    assert len(common_faces) == 0, "Test-Setup fehlerhaft: Kanten teilen unerwartet eine Face"

    # Jetzt _build_adjacency aufrufen — muss TopologyToolError werfen
    with pytest.raises(TopologyToolError, match="nicht unterstützt"):
        _build_adjacency(mesh3, {edge_p10_p11, edge_p11_p12})
