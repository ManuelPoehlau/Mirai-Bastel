"""Connect Edges Tests — Spec-Semantik vor Implementierung.

Basis: docs/research/topology/CONNECT_EDGES_SPEC.md

Diese Tests prüfen die GEWÜNSCHTE Semantik, nicht das aktuelle fehlerhafte
Verhalten. Ein rot-markierter Test zeigt, wo die aktuelle Implementierung
die Spec verletzt.

Ausführen mit: python -m tests.test_connect_edges (aus Viewport-Verzeichnis)
"""

from __future__ import annotations

import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR.parent))
sys.path.insert(0, str(_THIS_DIR.parent.parent / "mirai_bastel_core_V1"))

from mirai_bastel_core import Mesh, Scene, HistoryStack  # noqa: E402

from viewport.topology_scene import build_topology_scene  # noqa: E402
from viewport.topology_tools import connect_selected_edges, TopologyToolError  # noqa: E402

_failures = 0


def check(label: str, condition: bool) -> None:
    global _failures
    status = "PASS" if condition else "FAIL"
    if not condition:
        _failures += 1
    print(f"[{status}] {label}")


def _find_edge(mesh: Mesh, v_a, v_b):
    """Hilfsfunktion: findet Edge zwischen zwei Vertices."""
    for eid in mesh.all_edge_ids():
        if set(mesh.edge_vertices(eid)) == {v_a, v_b}:
            return eid
    raise AssertionError(f"Edge zwischen {v_a} und {v_b} nicht gefunden")


def _grid_vertices(scene, cells: int):
    """Rebaut (row, col) -> VertexId Zuordnung von build_topology_scene."""
    mesh = scene.mesh
    step = 3.0 / cells
    start = -3.0 / 2.0
    lookup = {}
    for vid in mesh.all_vertex_ids():
        x, y, _ = mesh.vertex_position(vid)
        col = round((x - start) / step)
        row = round((y - start) / step)
        lookup[(row, col)] = vid
    return lookup


def _mesh_state_equals(mesh1_state: dict, mesh2_state: dict) -> bool:
    """Vergleicht zwei export_state() Diktionäre auf Gleichheit."""
    return mesh1_state == mesh2_state


def test_two_compatible_edges_on_quad() -> None:
    print("\n--- Connect Edges: zwei kompatible Edges auf einem Quad ---")
    mesh = Mesh()
    v0 = mesh.add_vertex((0.0, 0.0, 0.0))
    v1 = mesh.add_vertex((1.0, 0.0, 0.0))
    v2 = mesh.add_vertex((1.0, 1.0, 0.0))
    v3 = mesh.add_vertex((0.0, 1.0, 0.0))
    mesh.add_face([v0, v1, v2, v3])

    e0 = _find_edge(mesh, v0, v1)  # bottom
    e2 = _find_edge(mesh, v2, v3)  # top

    scene = Scene()
    scene.mesh = mesh
    scene.history = HistoryStack()

    edge_count_before = len(mesh.all_edge_ids())
    vertex_count_before = len(mesh.all_vertex_ids())

    created = connect_selected_edges(scene, [e0, e2])

    check("Connect erzeugt genau 1 neue Edge", len(created) == 1)
    check("Vertex-Anzahl: +2 (Mittelpunkte für 2 Edges)", len(mesh.all_vertex_ids()) == vertex_count_before + 2)
    check("Edge-Anzahl: +3 (2 Split-Edges + 1 Connection)", len(mesh.all_edge_ids()) == edge_count_before + 3)


def test_three_compatible_edges_connected_not_sorted() -> None:
    print("\n--- Connect Edges: 3 kompatible Edges — Topologie statt ID-Sortierung ---")
    # Echtes zusammenhängendes 3x3-Quad-Grid.
    # Die drei ausgewählten vertikalen Edges liegen in einer gemeinsamen
    # topologischen Reihe. Die Auswahl wird absichtlich nicht sortiert übergeben.
    scene = build_topology_scene(cells=3)
    mesh = scene.mesh
    lookup = _grid_vertices(scene, cells=3)

    e1 = _find_edge(mesh, lookup[(0, 1)], lookup[(1, 1)])
    e2 = _find_edge(mesh, lookup[(1, 1)], lookup[(2, 1)])
    e3 = _find_edge(mesh, lookup[(2, 1)], lookup[(3, 1)])

    scene.history = HistoryStack()

    created = connect_selected_edges(scene, [e3, e1, e2])

    # Spec: "all valid connections implied by the topology are created"
    # In dieser linearen Reihe sind das zwei Verbindungen:
    # e1-Mitte -> e2-Mitte und e2-Mitte -> e3-Mitte.
    check("Connect 3 Edges: 2 neue Verbindungskanten erwartet", len(created) == 2)


def test_complete_edge_ring_connect() -> None:
    print("\n--- Connect Edges: kompletter Edge Ring ---")
    # Quad-Ring (4 Quads in einem Ring, sie teilen sich vertikal Kanten)
    mesh = Mesh()
    layers = []
    for layer in range(2):
        row = []
        for i in range(4):
            angle = (i + layer * 0.5) * 3.14159 / 2.0
            x, y = 2.0 + 1.5 * (1.0 if layer == 0 else 0.7) * __import__("math").cos(angle), \
                   1.0 * __import__("math").sin(angle)
            row.append(mesh.add_vertex((x, y, 0.0)))
        layers.append(row)

    # Verbinde in Ringen
    for i in range(4):
        j = (i + 1) % 4
        mesh.add_face([layers[0][i], layers[0][j], layers[1][j], layers[1][i]])

    # Wähle alle 4 Kanten zwischen den Ringen
    ring_edges = []
    for i in range(4):
        e = _find_edge(mesh, layers[0][i], layers[1][i])
        ring_edges.append(e)

    scene = Scene()
    scene.mesh = mesh
    scene.history = HistoryStack()

    # Spec: "A ring selected through the Ring tool should be usable as input"
    created = connect_selected_edges(scene, ring_edges)
    check("Connect Edge Ring: neue Kanten erzeugt", len(created) > 0)


def test_multiple_disconnected_groups_independent() -> None:
    print("\n--- Connect Edges: mehrere disjunkte Gruppen unabhängig verbunden ---")
    # 2 separate Quads, jeweils eine kompatible Kantenpaar-Gruppe
    mesh = Mesh()

    # Quad 1
    v0_1 = mesh.add_vertex((0.0, 0.0, 0.0))
    v1_1 = mesh.add_vertex((1.0, 0.0, 0.0))
    v2_1 = mesh.add_vertex((1.0, 1.0, 0.0))
    v3_1 = mesh.add_vertex((0.0, 1.0, 0.0))
    mesh.add_face([v0_1, v1_1, v2_1, v3_1])

    # Quad 2 (getrennt, kein gemeinsamer Vertex)
    v0_2 = mesh.add_vertex((5.0, 0.0, 0.0))
    v1_2 = mesh.add_vertex((6.0, 0.0, 0.0))
    v2_2 = mesh.add_vertex((6.0, 1.0, 0.0))
    v3_2 = mesh.add_vertex((5.0, 1.0, 0.0))
    mesh.add_face([v0_2, v1_2, v2_2, v3_2])

    e1_bottom = _find_edge(mesh, v0_1, v1_1)
    e1_top = _find_edge(mesh, v2_1, v3_1)
    e2_bottom = _find_edge(mesh, v0_2, v1_2)
    e2_top = _find_edge(mesh, v2_2, v3_2)

    scene = Scene()
    scene.mesh = mesh
    scene.history = HistoryStack()

    # Spec: "Disconnected compatible groups should be handled independently"
    created = connect_selected_edges(scene, [e1_bottom, e1_top, e2_bottom, e2_top])

    check("Connect disjunkte Gruppen: 2 Verbindungen erwartet", len(created) == 2)


def test_invalid_selection_leaves_mesh_unchanged() -> None:
    print("\n--- Connect Edges: ungültige Selection — Mesh unverändert (ATOMICITY) ---")
    mesh = Mesh()

    # Triangle 1
    v0_1 = mesh.add_vertex((0.0, 0.0, 0.0))
    v1_1 = mesh.add_vertex((1.0, 0.0, 0.0))
    v2_1 = mesh.add_vertex((0.5, 1.0, 0.0))
    mesh.add_face([v0_1, v1_1, v2_1])

    # Triangle 2 (vollständig getrennt)
    v0_2 = mesh.add_vertex((5.0, 0.0, 0.0))
    v1_2 = mesh.add_vertex((6.0, 0.0, 0.0))
    v2_2 = mesh.add_vertex((5.5, 1.0, 0.0))
    mesh.add_face([v0_2, v1_2, v2_2])

    e1 = _find_edge(mesh, v0_1, v1_1)
    e2 = _find_edge(mesh, v0_2, v1_2)

    scene = Scene()
    scene.mesh = mesh
    scene.history = HistoryStack()

    mesh_state_before = mesh.export_state()
    vertex_count_before = len(mesh.all_vertex_ids())
    edge_count_before = len(mesh.all_edge_ids())

    try:
        connect_selected_edges(scene, [e1, e2])
        check("Operation hätte fehlschlagen sollen", False)
    except TopologyToolError:
        check("Operation schlägt fehl (wie erwartet)", True)

    mesh_state_after = mesh.export_state()
    check("ATOMICITY: Mesh nach Fehler unverändert (Vertices)", len(mesh.all_vertex_ids()) == vertex_count_before)
    check("ATOMICITY: Mesh nach Fehler unverändert (Edges)", len(mesh.all_edge_ids()) == edge_count_before)
    check("ATOMICITY: export_state identisch", _mesh_state_equals(mesh_state_before, mesh_state_after))


def test_deterministic_result_different_order() -> None:
    print("\n--- Connect Edges: deterministische Ergebnisse unabhängig von Einfüge-Reihenfolge ---")
    scene1 = build_topology_scene(cells=3)
    scene2 = build_topology_scene(cells=3)
    lookup1 = _grid_vertices(scene1, cells=3)
    lookup2 = _grid_vertices(scene2, cells=3)

    mesh1 = scene1.mesh
    mesh2 = scene2.mesh
    scene1.history = HistoryStack()
    scene2.history = HistoryStack()

    # Wähle die 3 mittleren horizontalen Kanten, aber in verschiedenen Reihenfolgen
    e_middle_1_order1 = [
        _find_edge(mesh1, lookup1[(1, c)], lookup1[(1, c + 1)])
        for c in range(3)
    ]
    e_middle_2_order2 = [
        _find_edge(mesh2, lookup2[(1, 2)], lookup2[(1, 3)]),
        _find_edge(mesh2, lookup2[(1, 1)], lookup2[(1, 2)]),
        _find_edge(mesh2, lookup2[(1, 0)], lookup2[(1, 1)]),
    ]

    try:
        created1 = connect_selected_edges(scene1, e_middle_1_order1)
        created2 = connect_selected_edges(scene2, e_middle_2_order2)

        check("Beide Operationen erzeugen die gleiche Anzahl Kanten", len(created1) == len(created2))
        state1 = mesh1.export_state()
        state2 = mesh2.export_state()
        check("Mesh-Zustand nach Connect ist identisch", _mesh_state_equals(state1, state2))
    except TopologyToolError as e:
        check(f"Determinism-Test: Operation fehlgeschlagen ({e})", False)


def test_edge_loop_selection_valid_input() -> None:
    print("\n--- Connect Edges: Edge Loop als valide Eingabe (wo kompatibel) ---")
    scene = build_topology_scene(cells=4)
    lookup = _grid_vertices(scene, cells=4)
    mesh = scene.mesh
    scene.history = HistoryStack()

    # Eine zusammenhängende Loop-/Flow-Auswahl entlang einer Zeile.
    loop_edges = [
        _find_edge(mesh, lookup[(2, c)], lookup[(2, c + 1)])
        for c in range(4)
    ]

    try:
        created = connect_selected_edges(scene, loop_edges)
        check("Edge Loop kann als Connect-Input dienen", len(created) > 0)
    except TopologyToolError:
        check("Edge Loop Connect: noch nicht implementiert (Spec erfordert es)", False)


def test_partial_failure_no_mesh_change() -> None:
    print("\n--- Connect Edges: Teilerfolg ist nicht akzeptabel (Atomicity) ---")
    mesh = Mesh()

    # 2 Quads nebeneinander
    v0 = mesh.add_vertex((0.0, 0.0, 0.0))
    v1 = mesh.add_vertex((1.0, 0.0, 0.0))
    v2 = mesh.add_vertex((1.0, 1.0, 0.0))
    v3 = mesh.add_vertex((0.0, 1.0, 0.0))
    v4 = mesh.add_vertex((2.0, 0.0, 0.0))
    v5 = mesh.add_vertex((2.0, 1.0, 0.0))
    mesh.add_face([v0, v1, v2, v3])
    mesh.add_face([v1, v4, v5, v2])

    # Triangle (isoliert)
    v6 = mesh.add_vertex((5.0, 0.0, 0.0))
    v7 = mesh.add_vertex((6.0, 0.0, 0.0))
    v8 = mesh.add_vertex((5.5, 1.0, 0.0))
    mesh.add_face([v6, v7, v8])

    e1 = _find_edge(mesh, v0, v1)
    e2 = _find_edge(mesh, v2, v3)
    e3 = _find_edge(mesh, v6, v7)

    scene = Scene()
    scene.mesh = mesh
    scene.history = HistoryStack()

    mesh_state_before = mesh.export_state()
    vertex_count_before = len(mesh.all_vertex_ids())

    try:
        connect_selected_edges(scene, [e1, e2, e3])
        check("Teilerfolg sollte nicht auftreten", False)
    except TopologyToolError:
        check("Operation schlägt bei Inkompatibilität fehl", True)

    check("Keine Splits, wenn Operation fehlschlägt", len(mesh.all_vertex_ids()) == vertex_count_before)
    check("export_state nach Fehler unverändert", _mesh_state_equals(mesh_state_before, mesh.export_state()))


def run_all() -> None:
    global _failures
    tests = [
        test_two_compatible_edges_on_quad,
        test_three_compatible_edges_connected_not_sorted,
        test_complete_edge_ring_connect,
        test_multiple_disconnected_groups_independent,
        test_invalid_selection_leaves_mesh_unchanged,
        test_deterministic_result_different_order,
        test_edge_loop_selection_valid_input,
        test_partial_failure_no_mesh_change,
    ]
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"[CRASH] {t.__name__}: {e}")
            _failures += 1

    print()
    if _failures:
        print(f"{_failures} Check(s) fehlgeschlagen.")
        sys.exit(1)
    print("Alle Connect-Edges-Checks validiert.")


if __name__ == "__main__":
    run_all()
