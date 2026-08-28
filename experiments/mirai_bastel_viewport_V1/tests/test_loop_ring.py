"""Reine Logik-Tests für Edge-Loop-/Edge-Ring-Erkennung (Phase 2).

Laufen bewusst OHNE Fenster/GPU - loop_ring.py ist unabhängig von
pyglet/moderngl gehalten, siehe test_camera_picking.py für dasselbe Prinzip.

Ausführen mit: python -m tests.test_loop_ring (aus diesem Ordner)
"""

from __future__ import annotations

import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR.parent))
sys.path.insert(0, str(_THIS_DIR.parent.parent / "mirai_bastel_core_V1"))

from mirai_bastel_core import Mesh  # noqa: E402

from viewport.loop_ring import edge_loop, edge_ring  # noqa: E402
from viewport.topology_scene import build_topology_scene  # noqa: E402

_failures = 0


def check(label: str, condition: bool) -> None:
    global _failures
    status = "PASS" if condition else "FAIL"
    if not condition:
        _failures += 1
    print(f"[{status}] {label}")


def _find_edge(mesh: Mesh, v_a, v_b):
    for eid in mesh.all_edge_ids():
        if set(mesh.edge_vertices(eid)) == {v_a, v_b}:
            return eid
    raise AssertionError("Edge nicht gefunden")


def _grid_vertices(scene, cells: int):
    """Rebaut die (row, col) -> VertexId Zuordnung von build_topology_scene."""
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


def _build_closed_quad_tube(count: int, rows: int = 2):
    """Baut ein geschlossenes Quad-Rohr mit `rows` Ringen aus je `count`
    Vertices, umlaufend zu Quads verbunden (letztes Segment schließt auf das
    erste zurück). Gibt (mesh, ring_vertex_lists) zurück, ring_vertex_lists[r]
    ist die Liste der `count` Vertices von Ring r.

    Bei `rows >= 3` haben die inneren Ringe (nicht erster/letzter) Valenz 4
    an jedem Vertex (2 Umfangs- + 2 Längsnachbarn) - das ist die Bedingung,
    unter der edge_loop() konservativ weiterläuft. Die äußeren Ringe eines
    offenen Rohres bleiben bewusst Valenz 3 (Rand), siehe
    test_edge_loop_stops_at_grid_boundary_vertex für denselben Fall im Grid.
    """
    if count < 3:
        raise ValueError("count muss >= 3 sein")
    if rows < 2:
        raise ValueError("rows muss >= 2 sein")
    mesh = Mesh()
    ring_vertices = [
        [mesh.add_vertex((float(i), float(r), 0.0)) for i in range(count)]
        for r in range(rows)
    ]
    for r in range(rows - 1):
        for i in range(count):
            j = (i + 1) % count
            mesh.add_face([
                ring_vertices[r][i], ring_vertices[r][j],
                ring_vertices[r + 1][j], ring_vertices[r + 1][i],
            ])
    return mesh, ring_vertices


def test_edge_loop_follows_full_grid_row() -> None:
    print("\n--- Edge Loop: folgt einer vollen Zeile im Quad-Grid ---")
    scene = build_topology_scene(cells=4)
    lookup = _grid_vertices(scene, cells=4)
    mesh = scene.mesh

    start_edge = _find_edge(mesh, lookup[(2, 1)], lookup[(2, 2)])
    result = edge_loop(mesh, start_edge)

    expected = {_find_edge(mesh, lookup[(2, c)], lookup[(2, c + 1)]) for c in range(4)}
    check("Loop ist nicht geschlossen (offenes Grid)", result.closed is False)
    check("Loop enthält genau die 4 Kanten der Zeile", result.as_set() == expected)


def test_edge_loop_stops_at_grid_boundary_vertex() -> None:
    print("\n--- Edge Loop: bricht konservativ am Rand-Vertex ab ---")
    scene = build_topology_scene(cells=4)
    lookup = _grid_vertices(scene, cells=4)
    mesh = scene.mesh

    # Vertikale Kante am linken Rand: einer der beiden Endpunkte hat
    # Randvalenz (3, nicht 4) - Loop darf dort nicht "raten".
    start_edge = _find_edge(mesh, lookup[(0, 0)], lookup[(1, 0)])
    result = edge_loop(mesh, start_edge)
    check("Loop bricht sofort ab (Randvalenz an beiden Enden)", result.as_set() == {start_edge})


def test_edge_ring_follows_full_grid_column() -> None:
    print("\n--- Edge Ring: folgt einer vollen Spalte im Quad-Grid (senkrecht zur Kante) ---")
    scene = build_topology_scene(cells=4)
    lookup = _grid_vertices(scene, cells=4)
    mesh = scene.mesh

    start_edge = _find_edge(mesh, lookup[(2, 1)], lookup[(2, 2)])
    result = edge_ring(mesh, start_edge)

    expected = {_find_edge(mesh, lookup[(r, 1)], lookup[(r, 2)]) for r in range(5)}
    check("Ring ist nicht geschlossen (offenes Grid)", result.closed is False)
    check("Ring enthält genau die 5 horizontalen Kanten der Spalte", result.as_set() == expected)


def test_edge_ring_disjoint_from_edge_loop() -> None:
    print("\n--- Edge Ring und Edge Loop derselben Kante sind unterschiedliche Kantenmengen ---")
    scene = build_topology_scene(cells=4)
    lookup = _grid_vertices(scene, cells=4)
    mesh = scene.mesh

    start_edge = _find_edge(mesh, lookup[(2, 1)], lookup[(2, 2)])
    loop_edges = edge_loop(mesh, start_edge).as_set()
    ring_edges = edge_ring(mesh, start_edge).as_set()
    check("Loop und Ring teilen sich nur die Startkante", loop_edges & ring_edges == {start_edge})


def test_edge_ring_detects_closed_ring_on_tube() -> None:
    print("\n--- Edge Ring: erkennt geschlossenen Ring auf einem Quad-Rohr ---")
    mesh, rings = _build_closed_quad_tube(6, rows=2)
    bottom, top = rings[0], rings[1]
    start_edge = _find_edge(mesh, bottom[0], top[0])
    result = edge_ring(mesh, start_edge)

    expected = {_find_edge(mesh, bottom[i], top[i]) for i in range(6)}
    check("Ring erkennt sich als geschlossen", result.closed is True)
    check("Geschlossener Ring enthält jede der 6 Umfangskanten genau einmal", result.as_set() == expected)
    check("Keine Kante ist doppelt in der Traversierungsliste", len(result.edges) == len(set(result.edges)))


def test_edge_loop_detects_closed_loop_on_tube() -> None:
    print("\n--- Edge Loop: erkennt geschlossenen Loop auf einem Quad-Rohr (mittlerer Ring, Valenz 4) ---")
    # 3 Ringe: der mittlere (rings[1]) hat an jedem Vertex Valenz 4 (2 Umfangs-
    # + 2 Längsnachbarn) - nur dort darf edge_loop() konservativ um das Rohr
    # herumlaufen. Die äußeren Ringe (Rand des offenen Rohres) bleiben
    # Valenz 3 und werden bewusst nicht als Loop-Fortsetzung getestet.
    mesh, rings = _build_closed_quad_tube(6, rows=3)
    middle = rings[1]
    start_edge = _find_edge(mesh, middle[0], middle[1])
    result = edge_loop(mesh, start_edge)

    expected = {_find_edge(mesh, middle[i], middle[(i + 1) % 6]) for i in range(6)}
    check("Loop erkennt sich als geschlossen", result.closed is True)
    check("Geschlossener Loop enthält jede der 6 Ringkanten genau einmal", result.as_set() == expected)
    check("Keine Kante ist doppelt in der Traversierungsliste", len(result.edges) == len(set(result.edges)))


def test_edge_ring_stops_at_non_quad_face() -> None:
    print("\n--- Edge Ring: bricht konservativ an einer Non-Quad-Face ab ---")
    mesh = Mesh()
    # Ein Quad neben einem Dreieck, verbunden über eine gemeinsame Kante.
    v0 = mesh.add_vertex((0.0, 0.0, 0.0))
    v1 = mesh.add_vertex((1.0, 0.0, 0.0))
    v2 = mesh.add_vertex((1.0, 1.0, 0.0))
    v3 = mesh.add_vertex((0.0, 1.0, 0.0))
    v4 = mesh.add_vertex((1.0, 2.0, 0.0))
    mesh.add_face([v0, v1, v2, v3])  # Quad
    mesh.add_face([v3, v2, v4])  # Dreieck, teilt sich Kante v2-v3 mit dem Quad

    start_edge = _find_edge(mesh, v0, v1)  # gegenüberliegende Kante im Quad zu v2-v3
    result = edge_ring(mesh, start_edge)
    expected = {start_edge, _find_edge(mesh, v2, v3)}
    check("Ring bricht ab, bevor er die Dreiecks-Face betreten müsste", result.as_set() == expected)


def run_all() -> None:
    tests = [
        test_edge_loop_follows_full_grid_row,
        test_edge_loop_stops_at_grid_boundary_vertex,
        test_edge_ring_follows_full_grid_column,
        test_edge_ring_disjoint_from_edge_loop,
        test_edge_ring_detects_closed_ring_on_tube,
        test_edge_loop_detects_closed_loop_on_tube,
        test_edge_ring_stops_at_non_quad_face,
    ]
    for t in tests:
        t()
    print()
    if _failures:
        print(f"{_failures} Check(s) fehlgeschlagen.")
        sys.exit(1)
    print("Alle Loop-/Ring-Checks validiert.")


if __name__ == "__main__":
    run_all()
