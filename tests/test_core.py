"""Architekturvalidierung für V1_SPEC.md / AD-001 / AD-002 / AD-003.

Kein Feature-Test im klassischen Sinn - jeder Block prüft konkret einen
Architekturvertrag aus den archivierten Architecture Decisions. Ziel:
Belegen, dass die im Draft festgelegten Grenzen tatsächlich tragen.

Ausführen mit: python -m tests.test_core  (aus dem Projekt-Root)
"""

from __future__ import annotations

import tests._bootstrap  # noqa: F401 — Produktionspfad src/core/

from core import (
    Scene,
    SelectionMode,
    MoveOperation,
    OperationContext,
    scene_to_dict,
    scene_from_dict,
)
from core.mesh import Mesh
from tests.mesh_invariants import assert_mesh_invariants


def build_quad_scene() -> Scene:
    """Baut ein einzelnes Quad (0,0,0)-(1,0,0)-(1,1,0)-(0,1,0) via Mutation-Layer.

    Validiert implizit: add_vertex()/add_face() als einziger legitimer
    Konstruktionsweg (§7 Topologie-Grenze).
    """
    scene = Scene()
    mesh = scene.mesh
    v0 = mesh.add_vertex((0.0, 0.0, 0.0))
    v1 = mesh.add_vertex((1.0, 0.0, 0.0))
    v2 = mesh.add_vertex((1.0, 1.0, 0.0))
    v3 = mesh.add_vertex((0.0, 1.0, 0.0))
    face = mesh.add_face([v0, v1, v2, v3])
    return scene, (v0, v1, v2, v3), face


def check(label: str, condition: bool) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    assert condition, f"Architekturvertrag verletzt: {label}"


def test_ad001_stable_ids() -> None:
    print("\n--- AD-001: Stable IDs ---")
    mesh = Mesh()
    v0 = mesh.add_vertex((0, 0, 0))
    v1 = mesh.add_vertex((1, 0, 0))

    check("neu erzeugte Vertex-IDs sind gültig", mesh.is_valid_vertex(v0) and mesh.is_valid_vertex(v1))
    check("IDs sind unterschiedlich", v0 != v1)

    v2 = mesh.add_vertex((2, 0, 0))
    edge = mesh._get_or_create_edge(v0, v1)  # interner Helfer, nur für den Test
    check("IDs werden monoton vergeben (kein Recycling)", int(v2) > int(v1) > int(v0))

    # Löschen -> ID wird ungültig, aber nicht wiederverwendet.
    face = mesh.add_face([v0, v1, v2])
    mesh.remove_face(face)
    check("Face-ID nach remove_face() ungültig", not mesh.is_valid_face(face))
    v3 = mesh.add_vertex((3, 0, 0))
    check("neue ID kollidiert nicht mit zuvor genutzten Werten", int(v3) not in (int(v0), int(v1), int(v2)))


def test_ad001_id_continuity_split_edge() -> None:
    print("\n--- AD-001: ID-Kontinuität bei Topologie-Mutation (split_edge) ---")
    scene, (v0, v1, v2, v3), face = build_quad_scene()
    mesh = scene.mesh
    edges_before = set(mesh.face_edges(face))
    target_edge = mesh._get_or_create_edge(v0, v1)  # existierende Edge zwischen v0-v1
    check("Ziel-Edge existiert bereits vor dem Split", target_edge in edges_before)

    mid, new_e_a, new_e_b = mesh.split_edge(target_edge)

    check("ursprüngliche Edge-ID wird ungültig", not mesh.is_valid_edge(target_edge))
    check("neue Vertex-ID entsteht", mesh.is_valid_vertex(mid))
    check("zwei neue Edge-IDs entstehen", mesh.is_valid_edge(new_e_a) and mesh.is_valid_edge(new_e_b))
    check("ursprüngliche Endpunkt-IDs bleiben unverändert",
          mesh.is_valid_vertex(v0) and mesh.is_valid_vertex(v1))
    check("Face-ID bleibt unverändert (nur Boundary aktualisiert)", mesh.is_valid_face(face))
    check("Face-Boundary enthält jetzt den Mittelpunkt", mid in mesh.face_vertices(face))
    check("Face-Boundary hat jetzt 5 statt 4 Vertices", len(mesh.face_vertices(face)) == 5)
    assert_mesh_invariants(mesh, context="split_edge")


def test_split_edge_with_t() -> None:
    print("\n--- AD-017: split_edge with t parameter ---")
    scene, (v0, v1, v2, v3), face = build_quad_scene()
    mesh = scene.mesh
    target_edge = mesh._get_or_create_edge(v0, v1)
    p0 = mesh.vertex_position(v0)
    p1 = mesh.vertex_position(v1)

    # t=0.25: new vertex at 1/4 from v0
    mid, ea, eb = mesh.split_edge(target_edge, t=0.25)
    expected = tuple(a * 0.75 + b * 0.25 for a, b in zip(p0, p1))
    actual = mesh.vertex_position(mid)
    check("t=0.25 position is correct", actual == expected)
    assert_mesh_invariants(mesh, context="split_edge t=0.25")

    scene2, (v0b, v1b, v2b, v3b), face2 = build_quad_scene()
    mesh2 = scene2.mesh
    edge2 = mesh2._get_or_create_edge(v0b, v1b)
    p0b = mesh2.vertex_position(v0b)
    p1b = mesh2.vertex_position(v1b)

    # t=0.75: new vertex at 3/4 from v0
    mid2, _, _ = mesh2.split_edge(edge2, t=0.75)
    expected2 = tuple(a * 0.25 + b * 0.75 for a, b in zip(p0b, p1b))
    check("t=0.75 position is correct", mesh2.vertex_position(mid2) == expected2)
    assert_mesh_invariants(mesh2, context="split_edge t=0.75")

    scene3, (v0c, v1c, v2c, v3c), face3 = build_quad_scene()
    mesh3 = scene3.mesh
    edge3 = mesh3._get_or_create_edge(v0c, v1c)
    p0c = mesh3.vertex_position(v0c)
    p1c = mesh3.vertex_position(v1c)

    # default t=0.5 must be bit-identical to old midpoint formula
    mid3, _, _ = mesh3.split_edge(edge3)
    expected3 = tuple((a + b) / 2.0 for a, b in zip(p0c, p1c))
    check("default t=0.5 is bit-identical to midpoint", mesh3.vertex_position(mid3) == expected3)

    # invalid t values must raise MeshError, mesh unchanged
    scene4, (v0d, v1d, v2d, v3d), face4 = build_quad_scene()
    mesh4 = scene4.mesh
    edge4 = mesh4._get_or_create_edge(v0d, v1d)
    state_before = mesh4.export_state()
    for bad_t in [0.0, 1.0, -0.1, 1.5]:
        try:
            mesh4.split_edge(edge4, t=bad_t)
            check(f"t={bad_t} should have raised MeshError", False)
        except Exception:
            pass
        check(f"mesh unchanged after t={bad_t} rejection", mesh4.export_state() == state_before)

    print("test_split_edge_with_t: PASS")


def test_ad002_query_api_no_internal_access() -> None:
    print("\n--- AD-002: Query-API statt interner Container ---")
    scene, (v0, v1, v2, v3), face = build_quad_scene()
    mesh = scene.mesh

    verts = mesh.face_vertices(face)
    check("face_vertices() liefert geordnete Boundary", verts == [v0, v1, v2, v3])

    edges = mesh.face_edges(face)
    check("face_edges() liefert 4 Kanten für ein Quad", len(edges) == 4)

    for e in edges:
        faces_of_edge = mesh.edge_faces(e)
        check(f"edge_faces({e!r}) referenziert die Quad-Face", face in faces_of_edge)

    v_edges = mesh.vertex_edges(v0)
    check("vertex_edges(v0) liefert genau 2 Kanten (Quad-Ecke)", len(v_edges) == 2)

    # Keine öffentliche Klasse verrät hier interne Container-Typen.
    check("keine direkte Nutzung von Mesh._faces/_edges/_vertices im Test nötig", True)


def test_ad002_connect_vertices() -> None:
    print("\n--- AD-002: connect_vertices() als Mutation-Primitive ---")
    scene, (v0, v1, v2, v3), face = build_quad_scene()
    mesh = scene.mesh

    new_edge, face_a, face_b = mesh.connect_vertices(face, v0, v2)

    check("ursprüngliche Face-ID wird ungültig", not mesh.is_valid_face(face))
    check("zwei neue Face-IDs entstehen", mesh.is_valid_face(face_a) and mesh.is_valid_face(face_b))
    check("neue Edge-ID entsteht", mesh.is_valid_edge(new_edge))
    check("beteiligte Vertex-IDs bleiben unverändert",
          all(mesh.is_valid_vertex(v) for v in (v0, v1, v2, v3)))
    check("beide neuen Faces sind Dreiecke", len(mesh.face_vertices(face_a)) == 3 and len(mesh.face_vertices(face_b)) == 3)
    assert_mesh_invariants(mesh, context="connect_vertices")


def test_add_edge() -> None:
    print("\n--- add_edge() — freie Edge als öffentliche Mutation-Primitive ---")
    scene, (v0, v1, v2, v3), face = build_quad_scene()
    mesh = scene.mesh

    # Neue freie Edge zwischen zwei Vertices ohne gemeinsame Face
    v4 = mesh.add_vertex((2.0, 0.0, 0.0))
    v5 = mesh.add_vertex((2.0, 1.0, 0.0))
    eid = mesh.add_edge(v4, v5)

    check("neue EdgeId entsteht", mesh.is_valid_edge(eid))
    check("edge_faces() liefert leere Liste", mesh.edge_faces(eid) == [])
    check("beide Vertex-IDs bleiben gültig", mesh.is_valid_vertex(v4) and mesh.is_valid_vertex(v5))

    # Aufruf mit bestehendem Vertex-Paar (Face-Kante) → dieselbe EdgeId, kein Duplikat
    existing_edge = mesh._get_or_create_edge(v0, v1)
    returned_edge = mesh.add_edge(v0, v1)
    check("bereits vorhandene EdgeId wird zurückgegeben", returned_edge == existing_edge)
    check("bestehende Face bleibt unberührt", mesh.is_valid_face(face))
    check("edge_faces() der bestehenden Kante bleibt unverändert", face in mesh.edge_faces(returned_edge))

    # v_a == v_b → MeshError
    try:
        mesh.add_edge(v0, v0)
        check("v_a == v_b muss MeshError auslösen", False)
    except Exception as exc:
        check("v_a == v_b löst MeshError aus", type(exc).__name__ == "MeshError")

    # Ungültige VertexId → MeshError
    from core.ids import VertexId as _VId
    invalid = _VId(9999)
    try:
        mesh.add_edge(v0, invalid)
        check("ungültige VertexId muss MeshError auslösen", False)
    except Exception as exc:
        check("ungültige VertexId löst MeshError aus", type(exc).__name__ == "MeshError")

    assert_mesh_invariants(mesh, context="add_edge")


def test_ad002_collapse_edge() -> None:
    print("\n--- AD-002: collapse_edge() als Mutation-Primitive ---")
    scene, (v0, v1, v2, v3), face = build_quad_scene()
    mesh = scene.mesh
    edge_v0_v1 = mesh._get_or_create_edge(v0, v1)

    survivor = mesh.collapse_edge(edge_v0_v1)

    check("collapse_edge() liefert die überlebende (erste) Vertex-ID", survivor == v0)
    check("die zusammengeführte Edge-ID wird ungültig", not mesh.is_valid_edge(edge_v0_v1))
    check("der verschmolzene Vertex (v1) wird ungültig", not mesh.is_valid_vertex(v1))
    check("der überlebende Vertex (v0) bleibt gültig", mesh.is_valid_vertex(v0))
    check("Face-ID bleibt erhalten (kein degeneriertes Dreieck aus einem Quad)", mesh.is_valid_face(face))
    check("Face hat jetzt 3 statt 4 Vertices", len(mesh.face_vertices(face)) == 3)
    check("überlebender Vertex liegt in der Mitte der ursprünglichen Kante",
          abs(mesh.vertex_position(survivor)[0] - 0.5) < 1e-9)
    assert_mesh_invariants(mesh, context="collapse_edge")


def test_ad002_collapse_edge_no_stale_edges() -> None:
    print("\n--- AD-002: collapse_edge() hinterlässt keine stale Edge-Referenzen ---")
    # Fan aus drei Dreiecken um die Kante v0-v1 herum, wobei v1 zusätzlich
    # eine Kante zu v4 hat, die NICHT über v0 läuft (Face [v1, v4, v2]).
    # Das ist der Fall, der zuvor nicht abgedeckt war: die entfernte Vertex
    # (v1) hat Kanten, die nicht Teil der kollabierten Kante selbst sind.
    scene, (v0, v1, v2, v3), face_a = build_quad_scene()
    mesh = scene.mesh
    v4 = mesh.add_vertex((2.0, 2.0, 0.0))
    face_b = mesh.add_face([v1, v4, v2])  # hängt zusätzlich an v1, nicht an v0

    edge_v0_v1 = mesh._get_or_create_edge(v0, v1)
    survivor = mesh.collapse_edge(edge_v0_v1)
    check("collapse_edge() liefert v0 als Survivor", survivor == v0)
    check("die entfernte Vertex (v1) ist ungültig", not mesh.is_valid_vertex(v1))

    check(
        "KEINE verbleibende Edge referenziert die entfernte Vertex (v1)",
        all(v1 not in mesh.edge_vertices(eid) for eid in mesh.all_edge_ids()),
    )
    check(
        "die überlebende Face (vormals [v1,v4,v2]) referenziert v1 nicht mehr",
        v1 not in mesh.face_vertices(face_b),
    )
    check(
        "die überlebende Face referenziert stattdessen den Survivor v0",
        survivor in mesh.face_vertices(face_b),
    )
    # Jede Edge der überlebenden Face muss über die Query-API auflösbar sein -
    # das schlägt fehl, falls noch eine stale/doppelte Edge im Weg steht.
    edges_b = mesh.face_edges(face_b)
    check("face_edges() der überlebenden Face liefert 3 gültige Kanten",
          len(edges_b) == 3 and all(mesh.is_valid_edge(e) for e in edges_b))
    assert_mesh_invariants(mesh, context="collapse_edge_no_stale")


def test_ad003_update_is_incremental() -> None:
    print("\n--- AD-003: update()-Semantik ist inkrementell (nicht absolut zu begin()) ---")
    scene, (v0, v1, v2, v3), face = build_quad_scene()
    scene.selection.set({v0})
    context = OperationContext(target=scene.mesh, selection=scene.selection, history=scene.history)
    op = MoveOperation(context)

    op.begin()
    op.update(delta=(1.0, 0.0, 0.0))
    op.update(delta=(1.0, 0.0, 0.0))
    op.update(delta=(1.0, 0.0, 0.0))
    # Inkrementell: 3x (1,0,0) auf Live-Zustand -> Summe (3,0,0) ab Startposition (0,0,0).
    # Bei fälschlich absoluter Semantik (relativ zu begin()) stünde hier (1,0,0).
    check(
        "drei update(delta=(1,0,0))-Aufrufe akkumulieren sich zu (3,0,0)",
        scene.mesh.vertex_position(v0) == (3.0, 0.0, 0.0),
    )
    op.commit()


def test_ad003_interactive_lifecycle_commit() -> None:
    print("\n--- AD-003: Interactive Operation Lifecycle (begin -> update* -> commit) ---")
    scene, (v0, v1, v2, v3), face = build_quad_scene()
    scene.selection.mode = SelectionMode.VERTEX
    scene.selection.set({v0})

    context = OperationContext(target=scene.mesh, selection=scene.selection, history=scene.history)
    op = MoveOperation(context)

    check("History ist vor der Operation leer", len(scene.history) == 0)

    op.begin()
    check("update() vor begin() ohne Fehler nicht möglich -> begin() korrekt aktiv", op.is_active)

    # Mehrere update()-Aufrufe simulieren ein Drag mit vielen Mausereignissen.
    for _ in range(5):
        op.update(delta=(0.1, 0.0, 0.0))

    check("update() erzeugt KEINEN History-Eintrag", len(scene.history) == 0)
    check("update() schreibt direkt auf den Live-Mesh-Zustand",
          abs(scene.mesh.vertex_position(v0)[0] - 0.5) < 1e-9)

    command = op.commit()

    check("commit() erzeugt genau EINEN History-Eintrag (nicht 5)", len(scene.history) == 1)
    check("commit() liefert ein Command mit undo/redo", command is not None and hasattr(command, "undo"))
    check("Operation ist nach commit() nicht mehr aktiv", not op.is_active)

    # Undo/Redo über den generischen HistoryStack, nicht über die Operation selbst.
    scene.history.undo()
    check("undo() stellt die Ausgangsposition wieder her",
          abs(scene.mesh.vertex_position(v0)[0] - 0.0) < 1e-9)

    scene.history.redo()
    check("redo() stellt den committeten Zustand wieder her",
          abs(scene.mesh.vertex_position(v0)[0] - 0.5) < 1e-9)


def test_ad003_interactive_lifecycle_cancel() -> None:
    print("\n--- AD-003: Interactive Operation Lifecycle (begin -> update* -> cancel) ---")
    scene, (v0, v1, v2, v3), face = build_quad_scene()
    scene.selection.set({v1})

    context = OperationContext(target=scene.mesh, selection=scene.selection, history=scene.history)
    op = MoveOperation(context)

    op.begin()
    op.update(delta=(0.0, 5.0, 0.0))
    op.update(delta=(0.0, 5.0, 0.0))
    check("Live-Zustand während update() sichtbar verändert",
          abs(scene.mesh.vertex_position(v1)[1] - 10.0) < 1e-9)

    op.cancel()

    check("cancel() erzeugt KEINEN History-Eintrag", len(scene.history) == 0)
    check("cancel() stellt den Ausgangszustand exakt wieder her",
          scene.mesh.vertex_position(v1) == (1.0, 0.0, 0.0))
    check("Operation ist nach cancel() nicht mehr aktiv", not op.is_active)


def test_selection_not_in_history() -> None:
    print("\n--- §3: Selection ist nicht Teil des Modeling-Undo-Stacks ---")
    scene, (v0, v1, v2, v3), face = build_quad_scene()

    scene.selection.set({v0})
    scene.selection.add({v1})
    scene.selection.toggle(v2)
    scene.selection.remove({v0})

    check("Selection-Änderungen erzeugen keinen History-Eintrag", len(scene.history) == 0)
    check("Selection-Zustand ist wie erwartet", scene.selection.vertices == {v1, v2})


def test_ad001_serialization_roundtrip() -> None:
    print("\n--- Serialisierung: Scene-Hülle mit reservierten Subsystem-Plätzen (§12) ---")
    scene, (v0, v1, v2, v3), face = build_quad_scene()

    data = scene_to_dict(scene)
    check("Serialisiertes Format enthält reservierte Subsystem-Plätze",
          set(("mesh", "morph_targets", "rig", "animation")).issubset(data.keys()))
    check("morph_targets/rig/animation sind für V1 null", data["morph_targets"] is None and data["rig"] is None and data["animation"] is None)

    restored = scene_from_dict(data)
    check("Vertex-Anzahl bleibt nach Roundtrip erhalten", len(restored.mesh.all_vertex_ids()) == 4)
    check("Face-IDs bleiben nach Roundtrip identisch", restored.mesh.all_face_ids() == scene.mesh.all_face_ids())
    check("Vertex-Positionen bleiben nach Roundtrip identisch",
          restored.mesh.vertex_position(v0) == scene.mesh.vertex_position(v0))

    # Kollisionsfreiheit: nach dem Laden neu erzeugte ID darf nicht mit
    # einer bereits gespeicherten ID kollidieren (§8).
    new_v = restored.mesh.add_vertex((9, 9, 9))
    check("nach Deserialisierung neu erzeugte ID kollidiert nicht mit geladenen IDs",
          int(new_v) not in (int(v0), int(v1), int(v2), int(v3)))


# ----------------------------------------------------------------------
# AD-017 K1 (2026-10-01): Mesh.split_face - contract tests. The accepted
# contract is the AD-017_FINAL_DECISIONS addendum 2026-10-01.
# ----------------------------------------------------------------------

def _build_polygon(n: int):
    """Einzelnes konvexes, CCW gewundenes n-Gon in der XY-Ebene."""
    import math

    mesh = Mesh()
    verts = [
        mesh.add_vertex((math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n), 0.0))
        for i in range(n)
    ]
    return mesh, verts, mesh.add_face(verts)


def _build_grid_2x2():
    """2x2 Quads (3x3 Vertices), CCW; Rückgabe: mesh, {(x, y): VertexId}, {(x, y): FaceId}."""
    mesh = Mesh()
    p = {(x, y): mesh.add_vertex((float(x), float(y), 0.0)) for y in range(3) for x in range(3)}
    f = {
        (x, y): mesh.add_face([p[(x, y)], p[(x + 1, y)], p[(x + 1, y + 1)], p[(x, y + 1)]])
        for y in range(2) for x in range(2)
    }
    return mesh, p, f


def _signed_area_z(mesh: Mesh, face) -> float:
    pts = [mesh.vertex_position(v) for v in mesh.face_vertices(face)]
    return 0.5 * sum(
        pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
        for i in range(len(pts))
    )


def _directed_edges_unique(mesh: Mesh) -> bool:
    """Konsistente Orientierung: jede gerichtete Boundary-Kante kommt höchstens einmal vor."""
    seen = set()
    for fid in mesh.all_face_ids():
        b = mesh.face_vertices(fid)
        for i in range(len(b)):
            pair = (b[i], b[(i + 1) % len(b)])
            if pair in seen:
                return False
            seen.add(pair)
    return True


def _expect_mesh_error(label: str, mesh: Mesh, call) -> None:
    from core.mesh import MeshError

    before = mesh.export_state()
    symmetry_before = mesh.symmetry_definition
    try:
        call()
        check(f"{label}: raises MeshError", False)
    except MeshError:
        pass
    check(f"{label}: mesh unchanged incl. allocator counters", mesh.export_state() == before)
    check(f"{label}: symmetry definition untouched", mesh.symmetry_definition is symmetry_before)


def test_split_face_id_continuity() -> None:
    print("\n--- AD-017 K1: split_face ID continuity ---")
    mesh, p, f = _build_grid_2x2()
    face = f[(0, 0)]
    v_a, v_b = p[(0, 0)], p[(1, 1)]
    boundary_edges = mesh.face_edges(face)
    vids, eids, fids = set(mesh.all_vertex_ids()), set(mesh.all_edge_ids()), set(mesh.all_face_ids())
    max_v, max_e, max_f = max(map(int, vids)), max(map(int, eids)), max(map(int, fids))
    path = [(0.3, 0.2, 0.0), (0.6, 0.5, 0.0), (0.8, 0.7, 0.0)]

    new_vs, new_es, face_1, face_2 = mesh.split_face(face, v_a, v_b, path)

    check("parent face becomes invalid", not mesh.is_valid_face(face))
    check("k new VertexIds, ascending in path order", len(new_vs) == 3
          and [int(v) for v in new_vs] == list(range(max_v + 1, max_v + 4)))
    check("new vertices sit exactly at the given positions",
          [mesh.vertex_position(v) for v in new_vs] == path)
    check("k + 1 new EdgeIds, ascending in path order", len(new_es) == 4
          and [int(e) for e in new_es] == list(range(max_e + 1, max_e + 5)))
    chain = [v_a, *new_vs, v_b]
    check("edge i joins path vertices i and i + 1 (v_a -> v_b)",
          all(set(mesh.edge_vertices(e)) == {chain[i], chain[i + 1]} for i, e in enumerate(new_es)))
    check("two new FaceIds, face_1 allocated before face_2",
          (int(face_1), int(face_2)) == (max_f + 1, max_f + 2))
    check("exactly these ids appear, nothing else changes",
          set(mesh.all_vertex_ids()) == vids | set(new_vs)
          and set(mesh.all_edge_ids()) == eids | set(new_es)
          and set(mesh.all_face_ids()) == (fids - {face}) | {face_1, face_2})
    check("boundary edges keep their ids and now belong to exactly one of the two faces",
          all(mesh.is_valid_edge(e) for e in boundary_edges)
          and all(len({face_1, face_2} & set(mesh.edge_faces(e))) == 1 for e in boundary_edges))
    check("every path edge borders face_1 and face_2",
          all(sorted(mesh.edge_faces(e)) == sorted([face_1, face_2]) for e in new_es))
    check("face_1 = boundary v_a .. v_b forward, back along the path",
          mesh.face_vertices(face_1) == [v_a, p[(1, 0)], v_b, *new_vs[::-1]])
    check("face_2 = boundary v_b .. v_a forward, then along the path",
          mesh.face_vertices(face_2) == [v_b, p[(0, 1)], v_a, *new_vs])
    assert_mesh_invariants(mesh, context="split_face id continuity")

    # A second split allocates above everything ever used - no reuse (AD-001).
    new_vs2, new_es2, f1b, f2b = mesh.split_face(face_1, p[(1, 0)], new_vs[1])
    check("second split: ids keep growing (no reuse)",
          new_vs2 == [] and int(new_es2[0]) == max_e + 5 and (int(f1b), int(f2b)) == (max_f + 3, max_f + 4))
    assert_mesh_invariants(mesh, context="split_face second split")


def test_split_face_empty_path_equals_connect_vertices() -> None:
    print("\n--- AD-017 K1: split_face(positions=()) == connect_vertices ---")
    n = 6
    cases = 0
    for i in range(n):
        for j in range(n):
            if i == j or (i - j) % n in (1, n - 1):
                continue
            m_c, v_c, f_c = _build_polygon(n)
            m_s, v_s, f_s = _build_polygon(n)
            edge, fc1, fc2 = m_c.connect_vertices(f_c, v_c[i], v_c[j])
            new_vs, new_es, fs1, fs2 = m_s.split_face(f_s, v_s[i], v_s[j])
            check(f"hexagon ({i}, {j}): same return ids", (new_vs, new_es, fs1, fs2) == ([], [edge], fc1, fc2))
            check(f"hexagon ({i}, {j}): same export_state()", m_s.export_state() == m_c.export_state())
            cases += 1
    check("all non-adjacent ordered pairs of a hexagon compared", cases == n * (n - 3))

    # Existing free edge v_a-v_b inside the face: reused, as connect_vertices does.
    m_c, v_c, f_c = _build_polygon(5)
    m_s, v_s, f_s = _build_polygon(5)
    free_c, free_s = m_c.add_edge(v_c[0], v_c[2]), m_s.add_edge(v_s[0], v_s[2])
    edge, fc1, fc2 = m_c.connect_vertices(f_c, v_c[2], v_c[0])
    _vs, new_es, fs1, fs2 = m_s.split_face(f_s, v_s[2], v_s[0])
    check("existing free edge is reused (same id as connect_vertices)", new_es == [free_s] and edge == free_c)
    check("free-edge case: same export_state()", m_s.export_state() == m_c.export_state())
    assert_mesh_invariants(m_s, context="split_face reuse free edge")


def test_split_face_adjacent_ends() -> None:
    print("\n--- AD-017 K1: split_face with adjacent ends (notch) ---")
    scene, (v0, v1, v2, v3), face = build_quad_scene()
    mesh = scene.mesh
    _expect_mesh_error("adjacent ends, k = 0", mesh, lambda: mesh.split_face(face, v0, v1))

    new_vs, new_es, f1, f2 = mesh.split_face(face, v0, v1, [(0.5, 0.3, 0.0)])
    check("notch k = 1: triangle + pentagon",
          sorted((len(mesh.face_vertices(f1)), len(mesh.face_vertices(f2)))) == [3, 5])
    check("notch k = 1: the existing edge v0-v1 now borders the triangle only",
          mesh.edge_faces(mesh.face_edges(f1)[0]) == [f1])
    check("notch k = 1: one vertex, two edges", len(new_vs) == 1 and len(new_es) == 2)
    assert_mesh_invariants(mesh, context="split_face notch k=1")

    mesh2, (a, b, c), tri = _build_polygon(3)
    vs, es, g1, g2 = mesh2.split_face(tri, c, a, [(0.0, 0.2, 0.0), (0.1, -0.1, 0.0)])
    check("notch k = 2 in a triangle across the wrap: quad + pentagon",
          sorted((len(mesh2.face_vertices(g1)), len(mesh2.face_vertices(g2)))) == [4, 5])
    check("notch k = 2: two vertices, three edges", len(vs) == 2 and len(es) == 3)
    assert_mesh_invariants(mesh2, context="split_face notch k=2 triangle")


def test_split_face_rejections_leave_mesh_unchanged() -> None:
    print("\n--- AD-017 K1: split_face rejections (mesh byte-identical) ---")
    from core import SymmetryDefinition
    from core.ids import FaceId as _FId, VertexId as _VId

    mesh, p, f = _build_grid_2x2()
    mesh.symmetry_definition = SymmetryDefinition(
        plane_point=(1.0, 0.0, 0.0), plane_normal=(1.0, 0.0, 0.0),
        seam_edges=frozenset(mesh.face_edges(f[(0, 0)])[1:2]),
    )
    face = f[(0, 0)]
    a, b, c, d = p[(0, 0)], p[(1, 0)], p[(1, 1)], p[(0, 1)]
    elsewhere = p[(2, 2)]
    _expect_mesh_error("unknown face", mesh, lambda: mesh.split_face(_FId(999), a, c))
    _expect_mesh_error("v_a == v_b", mesh, lambda: mesh.split_face(face, a, a))
    _expect_mesh_error("v_a == v_b with positions (closed ring)", mesh,
                       lambda: mesh.split_face(face, a, a, [(0.2, 0.2, 0.0), (0.5, 0.2, 0.0)]))
    _expect_mesh_error("v_b not on the boundary", mesh, lambda: mesh.split_face(face, a, elsewhere))
    _expect_mesh_error("unknown vertex", mesh, lambda: mesh.split_face(face, _VId(999), c))
    _expect_mesh_error("adjacent ends, k = 0", mesh, lambda: mesh.split_face(face, b, c))
    _expect_mesh_error("position with 2 coordinates", mesh,
                       lambda: mesh.split_face(face, a, c, [(0.5, 0.5, 0.0), (0.7, 0.7)]))
    _expect_mesh_error("position that is not a sequence", mesh,
                       lambda: mesh.split_face(face, a, c, [(0.5, 0.5, 0.0), 1.0]))

    # Degenerate loop: a triangle, adjacent ends, no interior point.
    tri_mesh, (t0, t1, _t2), tri = _build_polygon(3)
    _expect_mesh_error("triangle, adjacent ends, k = 0", tri_mesh, lambda: tri_mesh.split_face(tri, t0, t1))

    # Non-manifold input 1: a face whose boundary repeats a vertex (add_face accepts it, H7).
    bad = Mesh()
    q = [bad.add_vertex((x, y, 0.0)) for x, y in ((0, 0), (1, 0), (1, 1), (0, 1))]
    pinched = bad.add_face([q[0], q[1], q[2], q[1], q[3]])
    _expect_mesh_error("boundary with a repeated vertex", bad, lambda: bad.split_face(pinched, q[0], q[2]))

    # Non-manifold input 2: the chord a-c is already an edge of another face; connect_vertices
    # would give it three faces.
    m2, p2, f2 = _build_grid_2x2()
    m2.add_face([p2[(0, 0)], p2[(1, 1)], m2.add_vertex((0.5, 0.5, 1.0))])
    _expect_mesh_error("k = 0 chord already an edge of another face", m2,
                       lambda: m2.split_face(f2[(0, 0)], p2[(0, 0)], p2[(1, 1)]))
    # With an interior point the path edges are new, so the same ends are fine.
    m2.split_face(f2[(0, 0)], p2[(0, 0)], p2[(1, 1)], [(0.6, 0.4, 0.0)])
    assert_mesh_invariants(m2, context="split_face next to an existing chord edge")


def test_split_face_winding_and_argument_order() -> None:
    print("\n--- AD-017 K1: split_face winding + determinism for both argument orders ---")
    path = [(0.9, 0.3, 0.0), (0.4, 0.6, 0.0)]
    results = []
    for swap in (False, True):
        mesh, p, f = _build_grid_2x2()
        ends = (p[(1, 0)], p[(0, 1)])
        v_a, v_b = ends[::-1] if swap else ends
        positions = path[::-1] if swap else path
        new_vs, new_es, f1, f2 = mesh.split_face(f[(0, 0)], v_a, v_b, positions)
        check(f"swap={swap}: both faces CCW like the parent",
              _signed_area_z(mesh, f1) > 0 and _signed_area_z(mesh, f2) > 0)
        check(f"swap={swap}: orientation consistent with the neighbours", _directed_edges_unique(mesh))
        check(f"swap={swap}: vertex ids follow v_a -> v_b",
              [mesh.vertex_position(v) for v in new_vs] == positions)
        assert_mesh_invariants(mesh, context=f"split_face swap={swap}")
        results.append([[mesh.vertex_position(v) for v in mesh.face_vertices(x)] for x in (f1, f2)]
                       + [(int(f1), int(f2))])
    check("both argument orders give the same faces in the same order", results[0] == results[1])

    # face_1 rule pinned: s = lower boundary index. v_a after v_b -> face_1 starts at v_b.
    mesh, v, face = _build_polygon(6)
    _vs, _es, f1, f2 = mesh.split_face(face, v[4], v[1], [(0.0, 0.0, 0.0)])
    check("v_b before v_a: face_1 = boundary v_b .. v_a forward (connect_vertices' swap)",
          mesh.face_vertices(f1)[:4] == [v[1], v[2], v[3], v[4]])
    check("v_b before v_a: face_2 = boundary v_a .. v_b through the list end",
          mesh.face_vertices(f2)[:4] == [v[4], v[5], v[0], v[1]])

    # Same call twice on twin meshes: byte-identical.
    m_x, p_x, f_x = _build_grid_2x2()
    m_y, p_y, f_y = _build_grid_2x2()
    m_x.split_face(f_x[(1, 1)], p_x[(1, 1)], p_x[(2, 2)], path)
    m_y.split_face(f_y[(1, 1)], p_y[(1, 1)], p_y[(2, 2)], path)
    check("deterministic: identical calls give identical export_state()", m_x.export_state() == m_y.export_state())


def test_split_face_serialization_undo_and_symmetry() -> None:
    print("\n--- AD-017 K1: split_face round trips (state, scene, MeshStateCommand) + symmetry ---")
    import json

    from core import HistoryStack, SymmetryDefinition
    from core.operations.topology import MeshStateCommand

    scene = Scene()
    mesh = scene.mesh
    p = {(x, y): mesh.add_vertex((float(x), float(y), 0.0)) for y in range(3) for x in range(3)}
    f = {
        (x, y): mesh.add_face([p[(x, y)], p[(x + 1, y)], p[(x + 1, y + 1)], p[(x, y + 1)]])
        for y in range(2) for x in range(2)
    }
    seam = frozenset(e for e in mesh.all_edge_ids() if all(mesh.vertex_position(v)[0] == 1.0
                                                            for v in mesh.edge_vertices(e)))
    definition = SymmetryDefinition(plane_point=(1.0, 0.0, 0.0), plane_normal=(1.0, 0.0, 0.0), seam_edges=seam)
    mesh.symmetry_definition = definition

    history = HistoryStack()
    before = mesh.export_state()
    new_vs, new_es, f1, f2 = mesh.split_face(f[(0, 0)], p[(1, 0)], p[(0, 1)], [(0.5, 0.4, 0.0)])
    after = mesh.export_state()
    history.push(MeshStateCommand(mesh=mesh, before_state=before, after_state=after))

    check("symmetry definition is the same object", mesh.symmetry_definition is definition)
    check("seam edges (incl. the split face's own) stay valid and keep their ids",
          len(seam) == 2 and all(mesh.is_valid_edge(e) for e in seam))
    check("no path edge became a seam edge", not (set(new_es) & seam))
    assert_mesh_invariants(mesh, context="split_face with symmetry")

    check("export_state/from_state round trip", Mesh.from_state(after).export_state() == after)
    restored = scene_from_dict(json.loads(json.dumps(scene_to_dict(scene))))
    check("scene JSON round trip", restored.mesh.export_state() == after)

    history.undo()
    check("undo restores the pre-split state", mesh.export_state()["faces"] == before["faces"]
          and mesh.export_state()["edges"] == before["edges"] and mesh.is_valid_face(f[(0, 0)]))
    check("undo keeps the allocator counters forward (AD-001)",
          mesh.export_state()["face_id_counter"] == after["face_id_counter"])
    history.redo()
    check("redo restores the split exactly", mesh.export_state() == after)

    history.undo()
    again = mesh.split_face(f[(0, 0)], p[(1, 0)], p[(0, 1)], [(0.5, 0.4, 0.0)])
    check("split after undo allocates fresh ids, none reused",
          all(int(x) > int(y) for x, y in zip(again[0], new_vs))
          and all(int(x) > int(y) for x, y in zip(again[1], new_es))
          and int(again[2]) > int(f2))
    assert_mesh_invariants(mesh, context="split_face after undo")


def run_all() -> None:
    tests = [
        test_ad001_stable_ids,
        test_ad001_id_continuity_split_edge,
        test_split_edge_with_t,
        test_ad002_query_api_no_internal_access,
        test_ad002_connect_vertices,
        test_add_edge,
        test_ad002_collapse_edge,
        test_ad002_collapse_edge_no_stale_edges,
        test_ad003_update_is_incremental,
        test_ad003_interactive_lifecycle_commit,
        test_ad003_interactive_lifecycle_cancel,
        test_selection_not_in_history,
        test_ad001_serialization_roundtrip,
        test_split_face_id_continuity,
        test_split_face_empty_path_equals_connect_vertices,
        test_split_face_adjacent_ends,
        test_split_face_rejections_leave_mesh_unchanged,
        test_split_face_winding_and_argument_order,
        test_split_face_serialization_undo_and_symmetry,
    ]
    for t in tests:
        t()
    print("\nAlle Architekturverträge validiert.")


if __name__ == "__main__":
    run_all()
